import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "usuarios",
    "cadastros",
    "roteiros",
    "eventos",
    "documentos",
    "oficios",
    "termos",
    "justificativas",
    "planos_trabalho",
    "ordens_servico",
    "prestacoes_contas",
    "diario_bordo",
    "assinaturas",
    "integracoes.google_drive",
]

_MIDDLEWARE_CORE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
_MIDDLEWARE_TAIL = [
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Exige login em todas as rotas (exceto as isentas pelo Django) quando True.
# Em desenvolvimento, `config.settings.dev` define LOGIN_ENFORCED=false por padrao para facilitar testes.
_LOGIN_ENFORCED = os.getenv("LOGIN_ENFORCED", "true").lower() in ("1", "true", "yes")

MIDDLEWARE = list(_MIDDLEWARE_CORE)
if _LOGIN_ENFORCED:
    MIDDLEWARE.append("core.middleware.AjaxAwareLoginRequiredMiddleware")
MIDDLEWARE.extend(_MIDDLEWARE_TAIL)

LOGIN_URL = "core:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "core:login"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.navigation",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "pt-br")
TIME_ZONE = os.getenv("TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Rotas (OpenRouteService via backend — nunca expor OPENROUTESERVICE_API_KEY ao navegador)
ROUTE_PROVIDER = (os.getenv("ROUTE_PROVIDER") or "openrouteservice").strip().lower()
OPENROUTESERVICE_API_KEY = (os.getenv("OPENROUTESERVICE_API_KEY") or "").strip()
ROUTE_CACHE_ENABLED = os.getenv("ROUTE_CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
ROUTE_REQUEST_TIMEOUT_SECONDS = int(os.getenv("ROUTE_REQUEST_TIMEOUT_SECONDS", "12"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Armazenamento de artefatos documentais gerados (assinatura, auditoria).
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Núcleo documental (DOCX/PDF, conversão opcional, assinatura).
DOCUMENTOS_RESOURCES_DIR = BASE_DIR / "documentos" / "resources"
DOCUMENTOS_BASE_URL = os.getenv("DOCUMENTOS_BASE_URL", "").strip() or None
DOCUMENTOS_DEFAULT_PDF_ENGINE = (os.getenv("DOCUMENTOS_DEFAULT_PDF_ENGINE") or "auto").strip().lower()
DOCUMENTOS_PDF_AUTO_FALLBACK = os.getenv("DOCUMENTOS_PDF_AUTO_FALLBACK", "").lower() in (
    "1",
    "true",
    "yes",
)
DOCUMENTOS_ENABLE_LIBREOFFICE = os.getenv("DOCUMENTOS_ENABLE_LIBREOFFICE", "").lower() in (
    "1",
    "true",
    "yes",
)
DOCUMENTOS_LIBREOFFICE_BINARY = (os.getenv("DOCUMENTOS_LIBREOFFICE_BINARY") or "").strip() or None
DOCUMENTOS_UNOSERVER_URL = (os.getenv("DOCUMENTOS_UNOSERVER_URL") or "").strip() or None
DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS = int(os.getenv("DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS", "3"))
DOCUMENTOS_GENERATOR_VERSION = (os.getenv("DOCUMENTOS_GENERATOR_VERSION") or "1").strip() or "1"
DOCUMENTOS_ARTIFACT_CACHE = os.getenv("DOCUMENTOS_ARTIFACT_CACHE", "true").lower() in ("1", "true", "yes")
DOCUMENTOS_PREGENERATE_PDF = os.getenv("DOCUMENTOS_PREGENERATE_PDF", "true").lower() in ("1", "true", "yes")
DOCUMENTOS_TMP_DIR = Path(os.getenv("DOCUMENTOS_TMP_DIR", str(BASE_DIR / "media" / "tmp_documentos")))
DOCUMENTOS_PERSIST_ARTEFATOS = os.getenv("DOCUMENTOS_PERSIST_ARTEFATOS", "true").lower() in (
    "1",
    "true",
    "yes",
)
# Último recurso: PDF texto simples (fpdf2), sem fidelidade visual ao HTML — desligado em produção por padrão.
DOCUMENTOS_SIMPLE_PDF_FALLBACK = os.getenv("DOCUMENTOS_SIMPLE_PDF_FALLBACK", "").lower() in (
    "1",
    "true",
    "yes",
)

SIGNATURE_BACKEND = (os.getenv("SIGNATURE_BACKEND") or "disabled").strip().lower()
SIGNATURE_PKCS12_PATH = (os.getenv("SIGNATURE_PKCS12_PATH") or "").strip() or None
SIGNATURE_PKCS12_PASSWORD = (os.getenv("SIGNATURE_PKCS12_PASSWORD") or "").strip() or None
SIGNATURE_REASON = os.getenv("SIGNATURE_REASON", "Documento institucional")
SIGNATURE_LOCATION = os.getenv("SIGNATURE_LOCATION", "")
SIGNATURE_VISIBLE = os.getenv("SIGNATURE_VISIBLE", "true").lower() in ("1", "true", "yes")
SIGNATURE_FIELD_NAME = (os.getenv("SIGNATURE_FIELD_NAME") or "AssinaturaCentralViagens").strip()

TIMESTAMP_URL = (os.getenv("TIMESTAMP_URL") or "").strip() or None
