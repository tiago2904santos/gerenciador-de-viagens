"""Acesso à configuração da integração Google Drive.

Centraliza a leitura de ``settings.GOOGLE_DRIVE`` para que o restante
do pacote não dependa diretamente de ``django.conf.settings``.
"""

from __future__ import annotations

from django.conf import settings


def get_config() -> dict:
    return dict(getattr(settings, "GOOGLE_DRIVE", {}) or {})


def get(chave: str, default=None):
    return get_config().get(chave, default)


def client_id() -> str:
    return (get("CLIENT_ID") or "").strip()


def client_secret() -> str:
    return (get("CLIENT_SECRET") or "").strip()


def redirect_uri() -> str:
    return (get("REDIRECT_URI") or "").strip()


def esta_configurado() -> bool:
    """True quando as três credenciais obrigatórias estão presentes."""
    return bool(client_id() and client_secret() and redirect_uri())
