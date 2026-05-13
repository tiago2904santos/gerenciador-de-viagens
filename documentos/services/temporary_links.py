"""URLs temporárias assinadas para acesso ao PDF sem sessão (partilha controlada)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from django.core.signing import TimestampSigner
from django.urls import reverse


_SALT = "documentos-artefato-pdf-temp"


def _signer() -> TimestampSigner:
    return TimestampSigner(salt=_SALT)


def create_artefato_pdf_temp_token(artefato_id: str) -> str:
    """Gera token URL-safe com expiração validada em `parse_artefato_pdf_temp_token`."""
    return _signer().sign_object({"pk": str(artefato_id)})


def parse_artefato_pdf_temp_token(token: str, *, max_age_seconds: int = 900) -> dict[str, Any]:
    """Valida token; levanta `BadSignature` ou `SignatureExpired` do Django em caso de falha."""
    return _signer().unsign_object(token, max_age=max_age_seconds)


def build_artefato_pdf_public_conteudo_url(token: str) -> str:
    """Path relativo com query `t` para uso em `request.build_absolute_uri`."""
    base = reverse("documentos:artefato_pdf_conteudo_publico")
    return f"{base}?t={quote(token, safe='')}"
