"""Serviços de integração com o Google Drive via OAuth 2.0.

Cada função pública recebe o usuário Django e opera sobre os tokens
armazenados em ``GoogleDriveToken``. Erros de autenticação levantam
``GoogleDriveError`` para tratamento amigável nas views.
"""

from __future__ import annotations

import json
from io import BytesIO

from . import settings as cfg
from .models import GoogleDriveToken

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


class GoogleDriveError(Exception):
    pass


def _client_config() -> dict:
    return {
        "web": {
            "client_id": cfg.client_id(),
            "client_secret": cfg.client_secret(),
            "redirect_uris": [cfg.redirect_uri()],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": TOKEN_URI,
        }
    }


def _criar_flow():
    from google_auth_oauthlib.flow import Flow
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=cfg.redirect_uri(),
    )


def obter_url_autorizacao() -> tuple[str, str]:
    """Retorna (authorization_url, state) para iniciar o fluxo OAuth."""
    flow = _criar_flow()
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url, state


def trocar_codigo_por_token(usuario, code: str) -> None:
    """Troca o código de autorização por tokens e persiste no banco."""
    flow = _criar_flow()
    flow.fetch_token(code=code)
    _salvar_credenciais(usuario, flow.credentials)


def _salvar_credenciais(usuario, creds) -> None:
    GoogleDriveToken.objects.update_or_create(
        usuario=usuario,
        defaults={
            "token": creds.token,
            "refresh_token": creds.refresh_token or "",
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": json.dumps(list(creds.scopes or SCOPES)),
        },
    )


def _obter_credenciais(usuario):
    """Retorna credenciais válidas, renovando automaticamente se expiradas."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    try:
        token_obj = GoogleDriveToken.objects.get(usuario=usuario)
    except GoogleDriveToken.DoesNotExist:
        raise GoogleDriveError("Conta Google Drive não conectada.")

    creds = Credentials(
        token=token_obj.token,
        refresh_token=token_obj.refresh_token or None,
        token_uri=token_obj.token_uri,
        client_id=token_obj.client_id,
        client_secret=token_obj.client_secret,
        scopes=json.loads(token_obj.scopes),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _salvar_credenciais(usuario, creds)

    if not creds.valid:
        raise GoogleDriveError(
            "Credenciais inválidas ou expiradas. Reconecte sua conta Google Drive."
        )

    return creds


def _get_service(usuario):
    from googleapiclient.discovery import build
    return build("drive", "v3", credentials=_obter_credenciais(usuario))


def listar_arquivos(usuario) -> list[dict]:
    """Lista os arquivos enviados pelo app no Drive do usuário (últimos 50)."""
    service = _get_service(usuario)
    resultado = service.files().list(
        q="trashed=false",
        spaces="drive",
        fields="files(id,name,webViewLink,createdTime,size,mimeType)",
        orderBy="createdTime desc",
        pageSize=50,
    ).execute()
    return resultado.get("files", [])


def fazer_upload(
    usuario,
    nome_arquivo: str,
    conteudo: bytes,
    tipo_mime: str,
    id_pasta: str | None = None,
) -> dict:
    """Faz upload de um arquivo e retorna os metadados do arquivo criado no Drive."""
    from googleapiclient.http import MediaIoBaseUpload

    service = _get_service(usuario)
    metadata: dict = {"name": nome_arquivo}
    if id_pasta:
        metadata["parents"] = [id_pasta]

    media = MediaIoBaseUpload(BytesIO(conteudo), mimetype=tipo_mime, resumable=False)
    arquivo = (
        service.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id,name,webViewLink,createdTime,size",
        )
        .execute()
    )
    return arquivo


def revogar_token(usuario) -> None:
    """Remove o token do banco (desconecta localmente)."""
    GoogleDriveToken.objects.filter(usuario=usuario).delete()


def usuario_esta_conectado(usuario) -> bool:
    return GoogleDriveToken.objects.filter(usuario=usuario).exists()
