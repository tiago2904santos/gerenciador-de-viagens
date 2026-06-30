import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Respeita ENV_FILE; se LOGIN_ENFORCED nao estiver definido, desliga login obrigatorio em dev (testes manuais / agentes).
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / os.getenv("ENV_FILE", ".env"), override=False)
if "LOGIN_ENFORCED" not in os.environ:
    os.environ["LOGIN_ENFORCED"] = "false"

from .base import *


DEBUG = True

# OAuth do Google Drive em dev usa callback http://localhost; o oauthlib
# recusa transporte não-HTTPS por padrão. Liberado apenas em dev.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

# No Windows, WeasyPrint costuma faltar GTK; LibreOffice pode não estar instalado.
# Habilita PDF mínimo (fpdf2) como último recurso, salvo override explícito no .env.
if sys.platform == "win32" and "DOCUMENTOS_SIMPLE_PDF_FALLBACK" not in os.environ:
    DOCUMENTOS_SIMPLE_PDF_FALLBACK = True

if "DOCUMENTOS_PDF_AUTO_FALLBACK" not in os.environ:
    DOCUMENTOS_PDF_AUTO_FALLBACK = True

# Pré-geração PDF na etapa documentos (GET): desligada por omissão em dev para não bloquear a página.
if "DOCUMENTOS_PREGENERATE_PDF" not in os.environ:
    DOCUMENTOS_PREGENERATE_PDF = False

db_engine = os.getenv("DB_ENGINE", "django.db.backends.postgresql")
required_db_vars = ["DB_NAME"]
if db_engine != "django.db.backends.sqlite3":
    required_db_vars.extend(["DB_USER", "DB_PASSWORD"])

missing_db_vars = [name for name in required_db_vars if not os.getenv(name)]

if missing_db_vars:
    raise RuntimeError(
        f"Variaveis de banco ausentes no .env: {', '.join(missing_db_vars)}"
    )

DATABASES = {
    "default": {
        "ENGINE": db_engine,
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PASSWORD"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}
