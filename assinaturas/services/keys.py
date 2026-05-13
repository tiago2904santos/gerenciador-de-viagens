from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class LoadedSigningKey:
    storage_kind: str
    pkcs12_path: str
    password: bytes | None


def load_active_signing_key_from_settings() -> LoadedSigningKey | None:
    """
    Caminho atual do projeto: credenciais em variáveis de ambiente / settings.
    Quando existir `ConfiguracaoChaveAssinatura` ativa, pode estender-se para ler o path do modelo.
    """
    backend = (getattr(settings, "SIGNATURE_BACKEND", "disabled") or "disabled").lower()
    if backend != "pkcs12":
        return None
    path = getattr(settings, "SIGNATURE_PKCS12_PATH", None)
    if not path:
        return None
    password = getattr(settings, "SIGNATURE_PKCS12_PASSWORD", None) or ""
    passphrase = password.encode("utf-8") if password else None
    return LoadedSigningKey(storage_kind="pkcs12", pkcs12_path=path, password=passphrase)
