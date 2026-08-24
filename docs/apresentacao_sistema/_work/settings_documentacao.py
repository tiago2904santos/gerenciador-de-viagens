"""Configuração isolada para capturas da documentação funcional.

O banco e a mídia abaixo contêm somente os dados sintéticos criados por
``resetar_banco_demo``. Nada nesta configuração alcança o PostgreSQL de
desenvolvimento.
"""

from pathlib import Path

from config.settings.test import *  # noqa: F403


_WORK_DIR = Path(__file__).resolve().parent

DEBUG = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _WORK_DIR / "documentacao.sqlite3",
    },
}
MEDIA_ROOT = _WORK_DIR / "media_documentacao"
STATIC_ROOT = _WORK_DIR / "static_documentacao"
DOCUMENTOS_PERSIST_ARTEFATOS = True
LOGIN_ENFORCED = True
