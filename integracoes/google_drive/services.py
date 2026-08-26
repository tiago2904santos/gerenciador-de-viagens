from __future__ import annotations

import hashlib
import io
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from django.conf import settings

from core.errors import capture
from core.middleware import get_current_request

logger = logging.getLogger(__name__)

_FOLDER_MIME = "application/vnd.google-apps.folder"
_SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
_SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    # Necessário para listar Drives Compartilhados (drives().list()) e navegar
    # pastas pré-existentes; drive.file sozinho só enxerga itens criados pelo app.
    "https://www.googleapis.com/auth/drive.readonly",
]

_MIMETYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

def _expiry_para_google_auth(expiry):
    """Converte o vencimento salvo para o formato do google-auth: naive em UTC.

    A biblioteca compara ``expiry`` com ``datetime.utcnow()`` e não olha
    tzinfo. Tirar o fuso sem converter antes erraria o vencimento na diferença
    do fuso do projeto (America/Sao_Paulo), adiantando ou atrasando a renovação
    em horas.
    """
    if not expiry:
        return None
    if expiry.tzinfo is None:
        return expiry
    return expiry.astimezone(timezone.utc).replace(tzinfo=None)


# Renova o token um pouco antes de vencer: cobre relógio fora de sincronia com
# o Google e job longo que cruza o vencimento no meio.
_MARGEM_RENOVACAO = timedelta(minutes=5)

_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"


class DriveRaizInvalidaError(RuntimeError):
    """A pasta raiz configurada não pode receber arquivos.

    O caso medido em produção (``NOVO-20260825-205014-1843068b6d33``): a raiz
    ``VIAGENS`` estava **na lixeira**. O Drive aceita criar filhos dentro de uma
    pasta lixeirada — o arquivo nasce na lixeira junto com ela —, e as buscas do
    organizador filtram ``trashed = false``, então nenhuma subpasta existente é
    reencontrada e o sistema recria a árvore inteira a cada envio, tudo
    invisível para o usuário. Sem esta checagem o upload "dá certo" e o
    documento simplesmente não aparece no Drive.
    """


class DriveReauthError(RuntimeError):
    """O refresh token não vale mais; só reconectar a conta resolve.

    Google devolve ``invalid_grant`` quando o usuário revoga o acesso, troca a
    senha, ou quando o app está com a tela de consentimento em *Testing* (aí o
    refresh token caduca em 7 dias). Sem tratar, a falha chega ao painel de
    pendências como um traceback de OAuth que não diz o que fazer.
    """


class DriveScopeError(RuntimeError):
    """A autorização OAuth salva não cobre os escopos que o app precisa.

    Acontece quando o app passou a pedir mais escopos (ex.: ``drive.readonly``)
    do que a credencial guardada concedeu: a renovação do token falha com
    ``invalid_scope`` e a solução é reconectar a conta.
    """


def _cfg() -> dict:
    return getattr(settings, "GOOGLE_DRIVE", {})


def _cache_ttl() -> float:
    """Validade (segundos) do cache de pastas e da checagem da raiz.

    Zero desliga o cache. O padrão vem de ``settings.GOOGLE_DRIVE``.
    """
    try:
        return max(0.0, float(_cfg().get("PASTA_CACHE_TTL_SECONDS") or 0))
    except (TypeError, ValueError):  # valor inválido no .env — cache curto, nunca eterno.
        logger.warning("[Drive] PASTA_CACHE_TTL_SECONDS inválido; usando 300s")
        return 300.0


def mimetype_para_formato(formato: str) -> str:
    return _MIMETYPES.get((formato or "").lower(), "application/octet-stream")


def escopo_faltante(usuario=None) -> list[str]:
    """Escopos requeridos (``_SCOPES``) que NÃO constam na credencial salva.

    Retorna lista vazia quando não há credencial (nada a comparar) ou quando o
    escopo salvo cobre tudo. Usado para avisar o usuário a reconectar a conta
    antes que a renovação do token quebre com ``invalid_scope``.
    """
    try:
        creds = get_credenciais(usuario)
    except Exception as exc:
        capture(exc, "drive.services.escopo_faltante")  # pragma: no cover
        return []
    if not creds or not (creds.scope or "").strip():
        return []
    salvos = set((creds.scope or "").split())
    return [s for s in _SCOPES if s not in salvos]


def client_config_dict() -> dict:
    cfg = _cfg()
    return {
        "web": {
            "client_id": cfg.get("CLIENT_ID", ""),
            "client_secret": cfg.get("CLIENT_SECRET", ""),
            "redirect_uris": [cfg.get("REDIRECT_URI", "")],
            "auth_uri": _AUTH_URI,
            "token_uri": _TOKEN_URI,
        }
    }


def _resolve_usuario(usuario=None):
    if usuario is not None:
        return usuario
    request = get_current_request()
    user = getattr(request, "user", None) if request is not None else None
    if user is not None and getattr(user, "is_authenticated", False):
        return user
    return None


def get_credenciais(usuario=None):
    from integracoes.google_drive.models import DriveCredenciais

    usuario = _resolve_usuario(usuario)
    if usuario is not None:
        return DriveCredenciais.objects.filter(usuario=usuario).first()
    return DriveCredenciais.objects.filter(usuario__isnull=True).order_by("pk").first()


def get_pasta_raiz_id(usuario=None) -> str:
    """Retorna o ID da pasta raiz: prioriza DB sobre .env."""
    try:
        creds = get_credenciais(usuario)
        if creds and creds.pasta_raiz_id:
            return creds.pasta_raiz_id
    except Exception as exc:
        capture(exc, "drive.services.get_pasta_raiz_id")  # pragma: no cover
        pass
    return _cfg().get("PASTA_RAIZ_ID", "")


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def _mock_id(prefixo: str, *partes: str) -> str:
    """ID determinístico e de tamanho limitado para o cliente de mock.

    IDs reais do Drive são opacos e curtos (~33 caracteres). Compor o ID
    concatenando o ID do pai fazia o valor crescer a cada nível de pasta,
    estourando os campos ``varchar(200)`` de ``DriveArquivo`` em bancos que
    aplicam o limite — o SQLite ignora, o PostgreSQL rejeita.

    O hash preserva a propriedade de que os testes dependem: mesmo nome e
    mesmo pai devolvem sempre o mesmo ID. O trecho legível existe só para
    manter o log de mock inteligível.
    """
    chave = "|".join(partes)
    digest = hashlib.sha1(chave.encode("utf-8")).hexdigest()[:16]
    legivel = "".join(c if c.isalnum() else "-" for c in (partes[-1] if partes else ""))[:40]
    return f"{prefixo}-{legivel}-{digest}".strip("-") if legivel else f"{prefixo}-{digest}"


class _MockClient:
    def upload(self, nome: str, conteudo: bytes, mimetype: str, pasta_id: str | None = None) -> tuple[str, str]:
        fake_id = _mock_id("mock", pasta_id or "root", nome)
        fake_url = f"https://drive.google.com/mock/{fake_id}"
        logger.info("[Drive MOCK] upload nome=%s pasta_id=%s → id=%s", nome, pasta_id, fake_id)
        return fake_id, fake_url

    def get_or_create_pasta(self, nome: str, pai_id: str | None = None) -> str:
        fake_id = _mock_id("mock-pasta", pai_id or "root", nome)
        logger.debug("[Drive MOCK] get_or_create_pasta nome=%s pai_id=%s", nome, pai_id)
        return fake_id

    def mover_renomear(self, file_id: str, novo_nome: str, nova_pasta_id: str | None = None) -> str:
        logger.info(
            "[Drive MOCK] mover_renomear file_id=%s nome=%s pasta_id=%s",
            file_id,
            novo_nome,
            nova_pasta_id,
        )
        return file_id

    def criar_ou_atualizar_atalho(
        self, nome: str, target_id: str, pasta_id: str, existing_id: str | None = None
    ) -> str:
        fake_id = existing_id or _mock_id("mock-atalho", pasta_id, nome)
        logger.info(
            "[Drive MOCK] atalho nome=%s target=%s pasta_id=%s → %s",
            nome,
            target_id,
            pasta_id,
            fake_id,
        )
        return fake_id

    def atualizar_conteudo(
        self, file_id: str, novo_nome: str, conteudo: bytes, mimetype: str, pasta_id: str | None = None
    ) -> tuple[str, str]:
        logger.info(
            "[Drive MOCK] atualizar_conteudo (sobrescrever) file_id=%s nome=%s pasta_id=%s",
            file_id, novo_nome, pasta_id,
        )
        return file_id, f"https://drive.google.com/mock/{file_id}"

    def excluir_arquivo(self, file_id: str) -> None:
        logger.info("[Drive MOCK] excluir_arquivo file_id=%s", file_id)

    def mover_para_lixeira(self, file_id: str) -> None:
        logger.info("[Drive MOCK] mover_para_lixeira file_id=%s", file_id)

    def buscar_arquivo_por_nome(self, nome: str, pasta_id: str) -> str | None:
        return None

    def buscar_pasta_por_nome(self, nome: str, pasta_id: str) -> str | None:
        return None

    def listar_arquivos(self, pasta_id: str) -> list[dict]:
        return []

    def listar_pastas(self, pai_id: str | None = None) -> list[dict]:
        return [
            {"id": "mock-pasta-documentos", "name": "Documentos (mock)"},
            {"id": "mock-pasta-viagens", "name": "Viagens (mock)"},
        ]

    def criar_pasta(self, nome: str, pai_id: str | None = None) -> dict:
        fake_id = f"mock-nova-{nome}"
        return {"id": fake_id, "name": nome}

    def nome_pasta(self, pasta_id: str) -> str:
        return pasta_id

    def listar_drives_compartilhados(self) -> list[dict]:
        return [
            {"id": "mock-shared-drive-1", "name": "Drive Compartilhado Viagens (mock)"},
            {"id": "mock-shared-drive-2", "name": "Drive Compartilhado Arquivo (mock)"},
        ]

    def listar_compartilhados_comigo(self) -> list[dict]:
        return [
            {"id": "mock-compartilhada-1", "name": "Pasta Compartilhada Exemplo (mock)"},
        ]

    def inspecionar_pasta(self, pasta_id: str) -> dict:
        return {
            "id": pasta_id,
            "name": pasta_id,
            "mimeType": _FOLDER_MIME,
            "trashed": False,
            "capabilities": {"canAddChildren": True},
        }


_CREDENCIAIS_CLS = None


def _credenciais_cls():
    """Classe de credenciais que grava no banco todo token novo do Google.

    ``AuthorizedHttp`` renova o token sozinho quando a API responde 401, mas o
    valor renovado só existia na memória do processo: o ``access_token`` salvo
    envelhecia para sempre e todo worker novo começava com um token morto,
    gastando um 401 antes da primeira chamada útil. Persistindo aqui, a
    renovação vale para todos os processos.

    A classe é montada sob demanda porque ``google-auth`` é import pesado e o
    modo mock não deve pagar por ele.
    """
    global _CREDENCIAIS_CLS
    if _CREDENCIAIS_CLS is not None:
        return _CREDENCIAIS_CLS

    from google.auth.exceptions import RefreshError
    from google.oauth2.credentials import Credentials

    class _CredenciaisPersistentes(Credentials):
        registro = None

        def refresh(self, request):
            try:
                super().refresh(request)
            except RefreshError as exc:
                if "invalid_grant" in str(exc):
                    raise DriveReauthError(
                        "A autorização do Google Drive não vale mais (o acesso foi "
                        "revogado, a senha da conta mudou, ou o app está com a tela "
                        "de consentimento em modo de teste, onde o token caduca em 7 "
                        "dias). Reconecte a conta em Meu perfil > Conta Google."
                    ) from exc
                raise
            self._persistir()

        def _persistir(self) -> None:
            registro = self.registro
            if registro is None or not self.token:
                return
            registro.access_token = self.token
            if self.expiry:
                registro.token_expiry = self.expiry.replace(tzinfo=timezone.utc)
            try:
                registro.save(
                    update_fields=["access_token", "token_expiry", "atualizado_em"]
                )
            except Exception as exc:
                # Credencial apagada (usuário desconectou) durante o job em
                # andamento: a chamada corrente ainda funciona com o token em
                # memória, então não derruba o envio por causa da gravação.
                capture(exc, "drive.services._CredenciaisPersistentes._persistir")
                logger.warning("[Drive] token renovado não pôde ser salvo: %s", exc)

    _CREDENCIAIS_CLS = _CredenciaisPersistentes
    return _CREDENCIAIS_CLS


class _RealClient:
    def __init__(self, usuario=None):
        import httplib2
        from google.auth.transport.requests import Request
        from google_auth_httplib2 import AuthorizedHttp
        from googleapiclient.discovery import build

        creds_obj = get_credenciais(usuario)
        if not creds_obj:
            raise RuntimeError(
                "Google Drive: nenhuma credencial OAuth armazenada. "
                "Acesse /integracoes/google-drive/oauth/iniciar/ para autorizar."
            )

        if not (creds_obj.refresh_token or "").strip():
            raise DriveReauthError(
                "A credencial salva do Google Drive não tem refresh token, então "
                "não há como renovar o acesso quando ele expira (cerca de 1 hora). "
                "Reconecte a conta em Meu perfil > Conta Google."
            )

        cfg = _cfg()
        creds = _credenciais_cls()(
            token=creds_obj.access_token,
            refresh_token=creds_obj.refresh_token,
            token_uri=_TOKEN_URI,
            client_id=cfg.get("CLIENT_ID", ""),
            client_secret=cfg.get("CLIENT_SECRET", ""),
            scopes=_SCOPES,
        )
        creds.registro = creds_obj

        expiry = creds_obj.token_expiry
        if expiry and expiry.tzinfo is None:
            from django.utils import timezone as dj_tz
            expiry = dj_tz.make_aware(expiry)
        # Informar o vencimento ao google-auth é o que faz ``AuthorizedHttp``
        # renovar ANTES de gastar uma chamada: sem ``expiry`` a credencial se
        # diz válida para sempre e a renovação só acontece depois de um 401.
        creds.expiry = _expiry_para_google_auth(expiry)

        # Margem: um job longo (reorganização em massa) pode cruzar o
        # vencimento no meio, e relógio de VPS costuma andar alguns segundos
        # fora do relógio do Google.
        vencido = expiry is None or expiry <= datetime.now(tz=timezone.utc) + _MARGEM_RENOVACAO
        if vencido:
            logger.info("[Drive] token vencido ou sem validade conhecida, renovando...")
            creds.refresh(Request())

        timeout = float(cfg.get("HTTP_TIMEOUT_SECONDS") or 30)
        authed_http = AuthorizedHttp(creds, http=httplib2.Http(timeout=timeout))
        self._svc = build("drive", "v3", http=authed_http, cache_discovery=False)
        # Valor = (id da pasta, instante em que foi resolvido). Ver `_cache_ttl`.
        self._cache: dict[tuple[str | None, str], tuple[str, float]] = {}

    def upload(self, nome: str, conteudo: bytes, mimetype: str, pasta_id: str | None = None) -> tuple[str, str]:
        from googleapiclient.http import MediaIoBaseUpload

        metadata: dict = {"name": nome}
        if pasta_id:
            metadata["parents"] = [pasta_id]

        media = MediaIoBaseUpload(io.BytesIO(conteudo), mimetype=mimetype, resumable=False)
        result = (
            self._svc.files()
            .create(body=metadata, media_body=media, fields="id,webViewLink", supportsAllDrives=True)
            .execute()
        )
        logger.info("[Drive] upload nome=%s → id=%s", nome, result["id"])
        return result["id"], result.get("webViewLink", "")

    def get_or_create_pasta(self, nome: str, pai_id: str | None = None) -> str:
        key = (pai_id, nome)
        # `NOVO-20260825-205015-e2fe5114f230`: o cache era eterno, e o gunicorn
        # de produção roda com processos que vivem dias. Bastava alguém mover ou
        # lixeirar uma pasta pelo próprio Drive para que todo envio seguinte
        # daquele worker fosse para um ID morto — sem erro nenhum, porque o
        # Drive aceita criar filho em pasta lixeirada. Com validade, a árvore é
        # reconferida periodicamente e o estrago se limita à janela do TTL.
        em_cache = self._cache.get(key)
        if em_cache is not None:
            folder_id, resolvido_em = em_cache
            if time.monotonic() - resolvido_em < _cache_ttl():
                return folder_id
            del self._cache[key]

        q = f"name = '{nome}' and mimeType = '{_FOLDER_MIME}' and trashed = false"
        if pai_id:
            q += f" and '{pai_id}' in parents"
        res = self._svc.files().list(
            q=q, fields="files(id)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])

        if files:
            folder_id = files[0]["id"]
        else:
            meta: dict = {"name": nome, "mimeType": _FOLDER_MIME}
            if pai_id:
                meta["parents"] = [pai_id]
            folder_id = (
                self._svc.files().create(body=meta, fields="id", supportsAllDrives=True).execute()["id"]
            )
            logger.info("[Drive] pasta criada nome=%s pai_id=%s → id=%s", nome, pai_id, folder_id)

        self._cache[key] = (folder_id, time.monotonic())
        return folder_id

    def listar_pastas(self, pai_id: str | None = None) -> list[dict]:
        q = f"mimeType = '{_FOLDER_MIME}' and trashed = false"
        if pai_id:
            q += f" and '{pai_id}' in parents"
        else:
            q += " and 'root' in parents"
        res = self._svc.files().list(
            q=q, fields="files(id,name)", orderBy="name", pageSize=100,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        return res.get("files", [])

    def listar_drives_compartilhados(self) -> list[dict]:
        res = self._svc.drives().list(pageSize=100, fields="drives(id,name)").execute()
        drives = res.get("drives", [])
        return sorted(drives, key=lambda d: (d.get("name") or "").lower())

    def listar_compartilhados_comigo(self) -> list[dict]:
        """Pastas de nível superior compartilhadas diretamente com a conta (não em ``root``)."""
        q = f"sharedWithMe = true and mimeType = '{_FOLDER_MIME}' and trashed = false"
        res = self._svc.files().list(
            q=q, fields="files(id,name)", orderBy="name", pageSize=100,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        return res.get("files", [])

    def criar_pasta(self, nome: str, pai_id: str | None = None) -> dict:
        meta: dict = {"name": nome, "mimeType": _FOLDER_MIME}
        if pai_id:
            meta["parents"] = [pai_id]
        result = self._svc.files().create(body=meta, fields="id,name", supportsAllDrives=True).execute()
        logger.info("[Drive] pasta criada nome=%s pai_id=%s → id=%s", nome, pai_id, result["id"])
        return result

    def inspecionar_pasta(self, pasta_id: str) -> dict:
        """Metadados que dizem se a pasta serve de destino (existe, não está na lixeira, aceita filhos)."""
        return self._svc.files().get(
            fileId=pasta_id,
            fields="id,name,mimeType,trashed,capabilities(canAddChildren)",
            supportsAllDrives=True,
        ).execute()

    def nome_pasta(self, pasta_id: str) -> str:
        try:
            result = self._svc.files().get(
                fileId=pasta_id, fields="name", supportsAllDrives=True
            ).execute()
            return result.get("name", pasta_id)
        except Exception as exc:
            capture(exc, "drive.services.nome_pasta")  # pragma: no cover
            return pasta_id

    def mover_renomear(self, file_id: str, novo_nome: str, nova_pasta_id: str | None = None) -> str:
        """Renomeia e/ou move um arquivo já existente (criado pelo app)."""
        from googleapiclient.errors import HttpError

        kwargs: dict = {
            "fileId": file_id,
            "body": {"name": novo_nome},
            "fields": "id",
            "supportsAllDrives": True,
        }
        if nova_pasta_id:
            atual = self._svc.files().get(
                fileId=file_id, fields="parents", supportsAllDrives=True
            ).execute()
            pais_atuais = atual.get("parents", []) or []
            if nova_pasta_id not in pais_atuais or len(pais_atuais) > 1:
                kwargs["addParents"] = nova_pasta_id
                if pais_atuais:
                    kwargs["removeParents"] = ",".join(pais_atuais)
        try:
            self._svc.files().update(**kwargs).execute()
        except HttpError as exc:
            if exc.resp.status != 403 or "cannotMoveTrashedItemOutOfTeamDrive" not in str(exc):
                raise
            # Item foi movido pra lixeira (fora do app) mas o Drive não deixa
            # mover item lixado pra fora de um Drive Compartilhado: restaura antes.
            logger.warning(
                "[Drive] file_id %s estava na lixeira; restaurando antes de mover", file_id,
            )
            self._svc.files().update(
                fileId=file_id, body={"trashed": False}, supportsAllDrives=True,
            ).execute()
            self._svc.files().update(**kwargs).execute()
        logger.info(
            "[Drive] mover_renomear file_id=%s nome=%s pasta_id=%s",
            file_id,
            novo_nome,
            nova_pasta_id,
        )
        return file_id

    def criar_ou_atualizar_atalho(
        self, nome: str, target_id: str, pasta_id: str, existing_id: str | None = None
    ) -> str:
        """Cria (ou renomeia/move) um atalho do Drive apontando para ``target_id``."""
        if existing_id:
            try:
                self.mover_renomear(existing_id, nome, pasta_id)
                return existing_id
            except Exception as exc:
                capture(exc, "drive.services.criar_ou_atualizar_atalho")  # pragma: no cover
                logger.warning("[Drive] atalho %s inválido, recriando: %s", existing_id, exc)
        meta = {
            "name": nome,
            "mimeType": _SHORTCUT_MIME,
            "parents": [pasta_id],
            "shortcutDetails": {"targetId": target_id},
        }
        result = self._svc.files().create(body=meta, fields="id", supportsAllDrives=True).execute()
        logger.info("[Drive] atalho criado nome=%s target=%s → id=%s", nome, target_id, result["id"])
        return result["id"]

    def atualizar_conteudo(
        self, file_id: str, novo_nome: str, conteudo: bytes, mimetype: str, pasta_id: str | None = None
    ) -> tuple[str, str]:
        """Sobrescreve o conteúdo de um arquivo já existente (mesmo ``file_id``).

        Usado quando o usuário edita e regera um documento: em vez de criar um
        segundo arquivo no Drive, substitui o conteúdo do arquivo já enviado.
        """
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(io.BytesIO(conteudo), mimetype=mimetype, resumable=False)
        result = (
            self._svc.files()
            .update(
                fileId=file_id, body={"name": novo_nome}, media_body=media,
                fields="id,webViewLink", supportsAllDrives=True,
            )
            .execute()
        )
        if pasta_id:
            self.mover_renomear(file_id, novo_nome, pasta_id)
        logger.info("[Drive] conteúdo sobrescrito file_id=%s nome=%s", file_id, novo_nome)
        return result["id"], result.get("webViewLink", "")

    def excluir_arquivo(self, file_id: str) -> None:
        """Exclui (definitivamente) um arquivo/atalho do Drive pelo ID."""
        try:
            self._svc.files().delete(fileId=file_id, supportsAllDrives=True).execute()
            logger.info("[Drive] arquivo excluído file_id=%s", file_id)
        except Exception as exc:
            capture(exc, "drive.services.excluir_arquivo")  # pragma: no cover
            logger.warning("[Drive] falha ao excluir file_id=%s: %s", file_id, exc)

    def mover_para_lixeira(self, file_id: str) -> None:
        """Move um arquivo/atalho para a lixeira do Drive (reversível, ~30 dias)."""
        try:
            self._svc.files().update(
                fileId=file_id, body={"trashed": True}, supportsAllDrives=True,
            ).execute()
            logger.info("[Drive] arquivo movido para a lixeira file_id=%s", file_id)
        except Exception as exc:
            capture(exc, "drive.services.mover_para_lixeira")  # pragma: no cover
            logger.warning("[Drive] falha ao mover para a lixeira file_id=%s: %s", file_id, exc)

    def buscar_arquivo_por_nome(self, nome: str, pasta_id: str) -> str | None:
        """Procura um arquivo (não-pasta) com esse nome exato dentro de ``pasta_id``.

        Rede de segurança contra duplicar: usada antes de criar um arquivo novo,
        caso o registro local (``DriveArquivo``) tenha se perdido/dessincronizado
        mas o arquivo já exista de verdade no Drive.
        """
        nome_escapado = nome.replace("'", "\\'")
        q = (
            f"name = '{nome_escapado}' and mimeType != '{_FOLDER_MIME}' and trashed = false"
            f" and '{pasta_id}' in parents"
        )
        res = self._svc.files().list(
            q=q, fields="files(id)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def buscar_pasta_por_nome(self, nome: str, pasta_id: str) -> str | None:
        """Procura uma PASTA com esse nome exato dentro de ``pasta_id``.

        Usada pra detectar quando uma pasta (ex.: de um evento) já existe do
        lado "errado" da árvore (ex.: em "Eventos/" quando o evento acabou de
        ser cancelado) — permite mover em vez de duplicar.
        """
        nome_escapado = nome.replace("'", "\\'")
        q = (
            f"name = '{nome_escapado}' and mimeType = '{_FOLDER_MIME}' and trashed = false"
            f" and '{pasta_id}' in parents"
        )
        res = self._svc.files().list(
            q=q, fields="files(id)", pageSize=1,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def listar_arquivos(self, pasta_id: str) -> list[dict]:
        """Lista arquivos (não-pastas) diretamente dentro de ``pasta_id``."""
        q = f"mimeType != '{_FOLDER_MIME}' and trashed = false and '{pasta_id}' in parents"
        res = self._svc.files().list(
            q=q, fields="files(id,name,modifiedTime)", pageSize=1000, orderBy="name",
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        return res.get("files", [])


# ---------------------------------------------------------------------------
# Singleton lazy
# ---------------------------------------------------------------------------

_clients: dict[int | None, _MockClient | _RealClient] = {}


def _reset_client() -> None:
    _clients.clear()
    _raiz_estados.clear()


def get_client(usuario=None) -> _MockClient | _RealClient:
    usuario = _resolve_usuario(usuario)
    key = usuario.pk if usuario is not None else None
    if key not in _clients:
        cfg = _cfg()
        modo = cfg.get("MODO", "mock").lower()

        if modo == "mock":
            _clients[key] = _MockClient()
        else:
            # Modo ativo: NUNCA cair para o mock em silêncio — isso mascarava
            # falhas de token/escopo (uploads "sumiam" no mock enquanto o sistema
            # se dizia ativo). Propagamos o erro para que o signal registre a
            # pendência e avise o usuário, em vez de fingir sucesso.
            faltando = escopo_faltante(usuario)
            if faltando:
                raise DriveScopeError(
                    "A conexão com o Google Drive precisa ser refeita: a "
                    "autorização salva não inclui " + ", ".join(faltando) + ". "
                    "Reconecte a conta em Configurações > Google Drive."
                )
            _clients[key] = _RealClient(usuario)
    return _clients[key]


def is_mock(usuario=None) -> bool:
    return isinstance(get_client(usuario), _MockClient)


# ---------------------------------------------------------------------------
# Pasta raiz: existe, não está na lixeira e aceita filhos?
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RaizEstado:
    """Resultado da checagem da pasta raiz configurada."""

    pasta_id: str
    ok: bool
    motivo: str = ""
    nome: str = ""

    @property
    def configurada(self) -> bool:
        return bool(self.pasta_id)


_raiz_estados: dict[tuple[int | None, str], tuple[RaizEstado, float]] = {}


def estado_pasta_raiz(usuario=None, *, usar_cache: bool = True) -> RaizEstado:
    """Confere se a pasta raiz configurada pode receber arquivos.

    Nunca levanta: devolve o diagnóstico para quem quiser mostrar na tela.
    Use ``validar_pasta_raiz`` quando a operação deve parar.
    """
    usuario = _resolve_usuario(usuario)
    pasta_id = get_pasta_raiz_id(usuario)
    if not pasta_id:
        return RaizEstado(
            pasta_id="",
            ok=False,
            motivo="Nenhuma pasta raiz escolhida. Selecione uma em Meu perfil > Diretório de destino.",
        )

    chave = (getattr(usuario, "pk", None), pasta_id)
    if usar_cache:
        registrado = _raiz_estados.get(chave)
        if registrado is not None and time.monotonic() - registrado[1] < _cache_ttl():
            return registrado[0]

    try:
        meta = get_client(usuario).inspecionar_pasta(pasta_id)
    except Exception as exc:
        capture(exc, "drive.services.estado_pasta_raiz")
        estado = RaizEstado(
            pasta_id=pasta_id,
            ok=False,
            motivo=f"A pasta raiz não pôde ser lida no Drive ({exc}).",
        )
    else:
        nome = meta.get("name") or pasta_id
        if meta.get("trashed"):
            estado = RaizEstado(
                pasta_id=pasta_id,
                ok=False,
                nome=nome,
                motivo=(
                    f'A pasta raiz "{nome}" está na LIXEIRA do Drive. Tudo que o '
                    "sistema enviar nasce na lixeira junto com ela e some da "
                    "visão do usuário. Restaure a pasta no Drive ou escolha outra "
                    "em Meu perfil > Diretório de destino."
                ),
            )
        elif meta.get("mimeType") not in (None, _FOLDER_MIME):
            estado = RaizEstado(
                pasta_id=pasta_id,
                ok=False,
                nome=nome,
                motivo=f'"{nome}" não é uma pasta do Drive.',
            )
        elif not (meta.get("capabilities") or {}).get("canAddChildren", True):
            estado = RaizEstado(
                pasta_id=pasta_id,
                ok=False,
                nome=nome,
                motivo=(
                    f'A conta conectada não tem permissão de escrita na pasta "{nome}". '
                    "Peça acesso de Editor ao dono da pasta."
                ),
            )
        else:
            estado = RaizEstado(pasta_id=pasta_id, ok=True, nome=nome)

    _raiz_estados[chave] = (estado, time.monotonic())
    if not estado.ok:
        logger.warning("[Drive] pasta raiz inutilizável: %s", estado.motivo)
    return estado


def validar_pasta_raiz(usuario=None) -> str:
    """Devolve o ID da raiz utilizável; levanta ``DriveRaizInvalidaError`` se não for.

    É o portão que impede o sistema de encher a lixeira do Drive achando que
    está arquivando documento (``NOVO-20260825-205014-1843068b6d33``).
    """
    estado = estado_pasta_raiz(usuario)
    if not estado.ok:
        raise DriveRaizInvalidaError(estado.motivo)
    return estado.pasta_id


def esta_autorizado(usuario=None) -> bool:
    try:
        return get_credenciais(usuario) is not None
    except Exception as exc:
        capture(exc, "drive.services.esta_autorizado")  # pragma: no cover
        return False


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def upload_artefato(artefato) -> tuple[str, str] | None:
    """Envia um artefato ao Drive, organizado por evento/categoria com nome bonito.

    Delega ao ``organizer`` (import tardio para evitar import circular). O
    organizador é idempotente: cria/atualiza o ``DriveArquivo`` correspondente.
    """
    try:
        from . import organizer

        return organizer.organizar_artefato(artefato)
    except Exception as exc:
        capture(exc, "drive.services.upload_artefato")  # pragma: no cover
        logger.error("[Drive] falha ao enviar artefato %s: %s", getattr(artefato, "pk", "?"), exc, exc_info=True)
        return None


def sincronizar_assinatura_manual(artefato) -> tuple[str, str] | None:
    """Reenvia ao Drive o conteúdo efetivo de um artefato após anexar/remover um assinado manual.

    Best-effort: nunca derruba a request que anexou/removeu o arquivo por causa
    de uma falha no Drive.
    """
    if _cfg().get("MODO", "mock").lower() == "mock" and not _cfg().get("UPLOAD_EM_MOCK", False):
        return None
    try:
        from . import organizer

        return organizer.sincronizar_conteudo_assinado(artefato)
    except Exception as exc:
        capture(exc, "drive.services.sincronizar_assinatura_manual")  # pragma: no cover
        logger.error(
            "[Drive] falha ao sincronizar assinatura manual do artefato %s: %s",
            getattr(artefato, "pk", "?"), exc, exc_info=True,
        )
        return None


def agendar_sincronizacao_assinatura_manual(artefato, *, usuario=None) -> None:
    """Salva a request do usuário sem aguardar rede ou API do Google Drive."""
    if _cfg().get("MODO", "mock").lower() == "mock" and not _cfg().get("UPLOAD_EM_MOCK", False):
        return

    from django.db import transaction

    from . import status, tasks

    usuario_id = getattr(usuario, "pk", None)

    def enviar():
        try:
            tasks.sincronizar_assinatura_manual.delay(
                artefato.pk,
                usuario_id=usuario_id,
            )
        except Exception as exc:
            capture(exc, "drive.services.enviar")  # pragma: no cover
            status.registrar_falha(artefato, exc, usuario=usuario)
            logger.warning(
                "[Drive] assinatura do artefato %s ficou pendente: %s",
                getattr(artefato, "pk", "?"),
                exc,
            )

    transaction.on_commit(enviar)
