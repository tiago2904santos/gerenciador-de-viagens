from __future__ import annotations

import io
import logging
from datetime import datetime, timezone

from django.conf import settings

logger = logging.getLogger(__name__)

_FOLDER_MIME = "application/vnd.google-apps.folder"
_SCOPES = ["https://www.googleapis.com/auth/drive.file"]

_MIMETYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _cfg() -> dict:
    return getattr(settings, "GOOGLE_DRIVE", {})


def mimetype_para_formato(formato: str) -> str:
    return _MIMETYPES.get((formato or "").lower(), "application/octet-stream")


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
            .create(body=metadata, media_body=media, fields="id,webViewLink")
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
        res = self._svc.files().list(q=q, fields="files(id)", pageSize=1).execute()
        files = res.get("files", [])

        if files:
            folder_id = files[0]["id"]
        else:
            meta: dict = {"name": nome, "mimeType": _FOLDER_MIME}
            if pai_id:
                meta["parents"] = [pai_id]
            folder_id = self._svc.files().create(body=meta, fields="id").execute()["id"]
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
            q=q, fields="files(id,name)", orderBy="name", pageSize=100
        ).execute()
        return res.get("files", [])

    def criar_pasta(self, nome: str, pai_id: str | None = None) -> dict:
        meta: dict = {"name": nome, "mimeType": _FOLDER_MIME}
        if pai_id:
            meta["parents"] = [pai_id]
        result = self._svc.files().create(body=meta, fields="id,name").execute()
        logger.info("[Drive] pasta criada nome=%s pai_id=%s → id=%s", nome, pai_id, result["id"])
        return result

    def nome_pasta(self, pasta_id: str) -> str:
        try:
            result = self._svc.files().get(fileId=pasta_id, fields="name").execute()
            return result.get("name", pasta_id)
        except Exception:
            return pasta_id

    def mover_renomear(self, file_id: str, novo_nome: str, nova_pasta_id: str | None = None) -> str:
        """Renomeia e/ou move um arquivo já existente (criado pelo app)."""
        kwargs: dict = {"fileId": file_id, "body": {"name": novo_nome}, "fields": "id"}
        if nova_pasta_id:
            atual = self._svc.files().get(fileId=file_id, fields="parents").execute()
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

        if modo != "mock":
            try:
                _client = _RealClient()
            except Exception as exc:
                logger.error("[Drive] falha ao criar client real (%s) — usando mock", exc)
                _client = _MockClient()
        else:
            _client = _MockClient()
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
