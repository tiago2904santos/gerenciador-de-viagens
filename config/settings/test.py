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
