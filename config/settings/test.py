import os

# Garante login obrigatório na suíte de testes independente do .env local
# (dev costuma ter LOGIN_ENFORCED=false para facilitar testes manuais; sem
# isso, base.py herdaria esse valor via load_dotenv e a suíte deixaria de
# validar o middleware de autenticação).
os.environ["LOGIN_ENFORCED"] = "true"

from .base import *


DEBUG = False

# Evita escrita em disco durante a suíte de testes (FileField do núcleo documental).
DOCUMENTOS_PERSIST_ARTEFATOS = False
DOCUMENTOS_PREGENERATE_PDF = False
DOCUMENTOS_DEFAULT_PDF_ENGINE = "simple"
DOCUMENTOS_BINARY_CONVERSION_CACHE = False
DOCUMENTOS_SIMPLE_PDF_FALLBACK = True
DOCUMENTOS_PDF_AUTO_FALLBACK = False
SECRET_KEY = "django-insecure-central-viagens-3-test-key"
# Chave gerada a cada execução da suíte, nunca escrita no repositório.
#
# A suíte precisa de cifragem consistente *dentro* de uma execução, não do mesmo
# valor entre execuções: o banco de teste nasce vazio e morre no fim, então nada
# cifrado sobrevive de uma rodada para a outra.
#
# Antes havia aqui um literal — e era a MESMA chave do dev, o que significava
# que quem tivesse o repositório decifrava o que tivesse sido cifrado em
# desenvolvimento. Trocar por outro literal apenas moveria o problema: uma chave
# Fernet válida commitada é indistinguível de um segredo de verdade, para o
# scanner de segredos e para quem lê o arquivo.
from cryptography.fernet import Fernet as _Fernet

FIELD_ENCRYPTION_KEYS = (_Fernet.generate_key().decode(),)
OFICIO_NUMERACAO_USAR_CONFIGURACAO = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
if os.environ.get("TEST_USE_POSTGRES", "").lower() in {"1", "true", "yes"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "gerenciador_test"),
            "USER": os.environ.get("DB_USER", "postgres"),
            "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),
            "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# A exceção de piso de numeração é específica de produção; a suíte valida o
# algoritmo genérico (sequência a partir de 1, reaproveitamento de lacunas).

# Sem broker na suíte: tarefas do Celery (ex.: retry de upload ao Drive)
# rodam na hora, no mesmo processo, em vez de tentar conectar a um Redis.
CELERY_TASK_ALWAYS_EAGER = True
AREA_RBAC_REQUIRE_MEMBERSHIP = False

# Testes que não exercitam a integração não podem herdar GOOGLE_DRIVE_MODO=ativo
# do .env local. Os módulos de Drive habilitam explicitamente o modo necessário.
GOOGLE_DRIVE = {
    **GOOGLE_DRIVE,
    "MODO": "mock",
    "UPLOAD_EM_MOCK": False,
}
