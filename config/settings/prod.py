import os

from .base import *


DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

required_db_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD"]
missing_db_vars = [name for name in required_db_vars if not os.getenv(name)]

if missing_db_vars:
    raise RuntimeError(
        f"Variaveis de banco ausentes no ambiente: {', '.join(missing_db_vars)}"
    )

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DB_ENGINE", "django.db.backends.postgresql"),
        "NAME": os.environ.get("DB_NAME"),
        "USER": os.environ.get("DB_USER"),
        "PASSWORD": os.environ.get("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,
        "CONN_HEALTH_CHECKS": True,
    }
}

# WhiteNoise: serve arquivos estáticos diretamente pelo Python sem depender do Nginx para /static/.
# Deve ficar logo após SecurityMiddleware.
_whitenoise = "whitenoise.middleware.WhiteNoiseMiddleware"
if _whitenoise not in MIDDLEWARE:
    try:
        _idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
        MIDDLEWARE.insert(_idx + 1, _whitenoise)
    except ValueError:
        MIDDLEWARE.insert(0, _whitenoise)

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "class": "logging.FileHandler",
            "filename": "/var/www/gerenciador-viagens/logs/django.log",
        },
    },
    "loggers": {
        "django": {"handlers": ["file"], "level": "ERROR", "propagate": True},
    },
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
# Gunicorn só é acessível via socket unix atrás do Nginx (que seta
# X-Forwarded-Proto). Sem isso, request.is_secure()/build_absolute_uri()
# devolvem "http://" mesmo em produção, quebrando fluxos que dependem do
# esquema real (ex.: redirect_uri do OAuth do Google).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Domínios HTTPS confiáveis para CSRF (obrigatório no Django 4+ atrás de proxy).
# Ex.: CSRF_TRUSTED_ORIGINS=https://viagens.exemplo.gov.br,https://www.viagens.exemplo.gov.br
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
