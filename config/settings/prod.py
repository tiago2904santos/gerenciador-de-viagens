import os

from .base import *


DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]
PRIVATE_MEDIA_X_ACCEL_REDIRECT = True
PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS = os.getenv(
    "PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS",
    "true",
).lower() in {"1", "true", "yes"}
if not FIELD_ENCRYPTION_KEYS:
    raise RuntimeError("FIELD_ENCRYPTION_KEYS é obrigatória em produção.")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

# NOVO-12, mesma regra do REDIS_URL logo abaixo: falhar cedo no settings em vez
# de degradar calado. Com DEBUG=False e esta lista vazia, TODA requisição vira
# 400 — o Django só avisa com `security.W020` (Warning), que o gate
# `--fail-level ERROR` do deploy não trava.
if not ALLOWED_HOSTS:
    raise RuntimeError(
        "ALLOWED_HOSTS é obrigatória em produção: vazia, toda requisição "
        "responde 400 com DEBUG=False.",
    )

required_db_vars = ["DB_NAME", "DB_USER", "DB_PASSWORD"]
missing_db_vars = [name for name in required_db_vars if not os.getenv(name)]

if missing_db_vars:
    raise RuntimeError(
        f"Variaveis de banco ausentes no ambiente: {', '.join(missing_db_vars)}"
    )

# QA-02: sem REDIS_URL o `base.py` cai para LocMemCache, que é por processo. Com os
# 3 workers do gunicorn documentados em DEPLOY_VPS.md, o rate limit de login
# (core/views.py: 5 tentativas / 15 min) vira até ~15 tentativas antes de um worker
# bloquear sozinho — e zera a cada `systemctl restart`, que o próprio deploy executa.
# O mesmo cache alimenta /metrics/, que passa a contar só o worker que atendeu.
# Falhar cedo, como já se faz com FIELD_ENCRYPTION_KEYS, em vez de degradar calado.
if not os.getenv("REDIS_URL", "").strip():
    raise RuntimeError(
        "REDIS_URL é obrigatória em producao: o cache é compartilhado entre os "
        "workers do gunicorn e sustenta o rate limit de login e as métricas.",
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
        "BACKEND": "config.staticfiles.VersionedStaticFilesStorage",
    },
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": "core.logging.JsonFormatter",
        },
    },
    "filters": {
        "request_context": {"()": "core.logging.RequestContextFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "filters": ["request_context"],
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
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
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True

# Domínios HTTPS confiáveis para CSRF (obrigatório no Django 4+ atrás de proxy).
# Ex.: CSRF_TRUSTED_ORIGINS=https://viagens.exemplo.gov.br,https://www.viagens.exemplo.gov.br
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
