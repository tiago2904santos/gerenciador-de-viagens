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

def _exigir_chave_de_cifragem(chaves):
    """Falha no boot, com instrução, em vez de estourar na primeira cifragem.

    Sem validar o formato, o placeholder do `.env.example` passaria batido aqui
    e só quebraria mais tarde, num ponto sem relação aparente com a causa.
    """
    from cryptography.fernet import Fernet

    if not chaves:
        motivo = "não está definida"
    else:
        try:
            Fernet(chaves[0].encode() if isinstance(chaves[0], str) else chaves[0])
        except (TypeError, ValueError):
            motivo = "não é uma chave Fernet válida (o valor do .env.example é só um lembrete)"
        else:
            return
    raise RuntimeError(
        f"FIELD_ENCRYPTION_KEYS {motivo}.\n"
        "Gere a sua e coloque no .env (ela nunca vai para o repositório):\n"
        '  python -c "from cryptography.fernet import Fernet; '
        'print(Fernet.generate_key().decode())"\n'
        "Consulte docs/AMBIENTES.md."
    )


_exigir_chave_de_cifragem(FIELD_ENCRYPTION_KEYS)


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
