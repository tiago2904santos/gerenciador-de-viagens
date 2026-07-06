from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

from django.conf import settings

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

_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"


class DriveScopeError(RuntimeError):
    """A autorização OAuth salva não cobre os escopos que o app precisa.

    Acontece quando o app passou a pedir mais escopos (ex.: ``drive.readonly``)
    do que a credencial guardada concedeu: a renovação do token falha com
    ``invalid_scope`` e a solução é reconectar a conta.
    """


def _cfg() -> dict:
    return getattr(settings, "GOOGLE_DRIVE", {})


def mimetype_para_formato(formato: str) -> str:
    return _MIMETYPES.get((formato or "").lower(), "application/octet-stream")


def escopo_faltante() -> list[str]:
    """Escopos requeridos (``_SCOPES``) que NÃO constam na credencial salva.

    Retorna lista vazia quando não há credencial (nada a comparar) ou quando o
    escopo salvo cobre tudo. Usado para avisar o usuário a reconectar a conta
    antes que a renovação do token quebre com ``invalid_scope``.
    """
    try:
        from integracoes.google_drive.models import DriveCredenciais

        creds = DriveCredenciais.objects.first()
    except Exception:
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


def get_pasta_raiz_id() -> str:
    """Retorna o ID da pasta raiz: prioriza DB sobre .env."""
    try:
        from integracoes.google_drive.models import DriveCredenciais
        creds = DriveCredenciais.objects.first()
        if creds and creds.pasta_raiz_id:
            return creds.pasta_raiz_id
    except Exception:
        pass
    return _cfg().get("PASTA_RAIZ_ID", "")


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

class _MockClient:
    def upload(self, nome: str, conteudo: bytes, mimetype: str, pasta_id: str | None = None) -> tuple[str, str]:
        fake_id = f"mock-{nome}"
        fake_url = f"https://drive.google.com/mock/{fake_id}"
        logger.info("[Drive MOCK] upload nome=%s pasta_id=%s → id=%s", nome, pasta_id, fake_id)
        return fake_id, fake_url

    def get_or_create_pasta(self, nome: str, pai_id: str | None = None) -> str:
        fake_id = f"mock-pasta-{pai_id or 'root'}-{nome}"
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
        fake_id = existing_id or f"mock-atalho-{pasta_id}-{nome}"
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


class _RealClient:
    def __init__(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        from integracoes.google_drive.models import DriveCredenciais

        creds_obj = DriveCredenciais.objects.first()
        if not creds_obj:
            raise RuntimeError(
                "Google Drive: nenhuma credencial OAuth armazenada. "
                "Acesse /integracoes/google-drive/oauth/iniciar/ para autorizar."
            )

        cfg = _cfg()
        creds = Credentials(
            token=creds_obj.access_token,
            refresh_token=creds_obj.refresh_token,
            token_uri=_TOKEN_URI,
            client_id=cfg.get("CLIENT_ID", ""),
            client_secret=cfg.get("CLIENT_SECRET", ""),
            scopes=_SCOPES,
        )

        expiry = creds_obj.token_expiry
        if expiry and expiry.tzinfo is None:
            from django.utils import timezone as dj_tz
            expiry = dj_tz.make_aware(expiry)

        if expiry and expiry <= datetime.now(tz=timezone.utc):
            logger.info("[Drive] token expirado, renovando...")
            creds.refresh(Request())
            creds_obj.access_token = creds.token
            if creds.expiry:
                creds_obj.token_expiry = creds.expiry.replace(tzinfo=timezone.utc)
            creds_obj.save(update_fields=["access_token", "token_expiry", "atualizado_em"])

        self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._cache: dict[tuple[str | None, str], str] = {}

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
        if key in self._cache:
            return self._cache[key]

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

        self._cache[key] = folder_id
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

    def nome_pasta(self, pasta_id: str) -> str:
        try:
            result = self._svc.files().get(
                fileId=pasta_id, fields="name", supportsAllDrives=True
            ).execute()
            return result.get("name", pasta_id)
        except Exception:
            return pasta_id

    def mover_renomear(self, file_id: str, novo_nome: str, nova_pasta_id: str | None = None) -> str:
        """Renomeia e/ou move um arquivo já existente (criado pelo app)."""
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


# ---------------------------------------------------------------------------
# Singleton lazy
# ---------------------------------------------------------------------------

_client: _MockClient | _RealClient | None = None


def _reset_client() -> None:
    global _client
    _client = None


def get_client() -> _MockClient | _RealClient:
    global _client
    if _client is None:
        cfg = _cfg()
        modo = cfg.get("MODO", "mock").lower()

        if modo == "mock":
            _client = _MockClient()
        else:
            # Modo ativo: NUNCA cair para o mock em silêncio — isso mascarava
            # falhas de token/escopo (uploads "sumiam" no mock enquanto o sistema
            # se dizia ativo). Propagamos o erro para que o signal registre a
            # pendência e avise o usuário, em vez de fingir sucesso.
            faltando = escopo_faltante()
            if faltando:
                raise DriveScopeError(
                    "A conexão com o Google Drive precisa ser refeita: a "
                    "autorização salva não inclui " + ", ".join(faltando) + ". "
                    "Reconecte a conta em Configurações > Google Drive."
                )
            _client = _RealClient()
    return _client


def is_mock() -> bool:
    return isinstance(get_client(), _MockClient)


def esta_autorizado() -> bool:
    try:
        from integracoes.google_drive.models import DriveCredenciais
        return DriveCredenciais.objects.exists()
    except Exception:
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
        logger.error("[Drive] falha ao enviar artefato %s: %s", getattr(artefato, "pk", "?"), exc, exc_info=True)
        return None
