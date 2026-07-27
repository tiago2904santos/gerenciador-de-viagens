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
SECRET_KEY = "django-insecure-central-viagens-3-test-key"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# A exceção de piso de numeração é específica de produção; a suíte valida o
# algoritmo genérico (sequência a partir de 1, reaproveitamento de lacunas).
OFICIO_NUMERO_INICIAL = {}

# Sem broker na suíte: tarefas do Celery (ex.: retry de upload ao Drive)
# rodam na hora, no mesmo processo, em vez de tentar conectar a um Redis.
CELERY_TASK_ALWAYS_EAGER = True

# Testes que não exercitam a integração não podem herdar GOOGLE_DRIVE_MODO=ativo
# do .env local. Os módulos de Drive habilitam explicitamente o modo necessário.
GOOGLE_DRIVE = {
    **GOOGLE_DRIVE,
    "MODO": "mock",
    "UPLOAD_EM_MOCK": False,
}
