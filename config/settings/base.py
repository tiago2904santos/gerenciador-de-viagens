import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]


def env_path(name, default):
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else BASE_DIR / value


ENV_FILE = os.getenv("ENV_FILE", ".env")
load_dotenv(BASE_DIR / ENV_FILE)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key")
FIELD_ENCRYPTION_KEYS = tuple(
    key.strip()
    for key in os.getenv("FIELD_ENCRYPTION_KEYS", "").split(",")
    if key.strip()
)
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
CSS_ROUTE_PROFILES_ENABLED = os.getenv("CSS_ROUTE_PROFILES_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}

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
    "django.contrib.postgres",
    "django_cotton.apps.SimpleAppConfig",
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
    "integracoes.google_drive",
    "protocolos",
    "prestacoes_contas",
]

_MIDDLEWARE_CORE = [
    "core.middleware.CurrentRequestMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # `PF-03`: logo depois do `SessionMiddleware`, porque precisa de
    # `request.session` e age na ida — o `SessionMiddleware` grava na volta.
    "core.middleware.RenovacaoDeSessaoMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.CurrentAreaMiddleware",
    "core.middleware.AreaRoleRequiredMiddleware",
]
SSO_REMOTE_USER_ENABLED = os.getenv("SSO_REMOTE_USER_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
SSO_MFA_REQUIRED = os.getenv("SSO_MFA_REQUIRED", "true").lower() in {"1", "true", "yes"}
SSO_MFA_ASSERTION_HEADER = os.getenv("SSO_MFA_ASSERTION_HEADER", "HTTP_X_AUTH_MFA")
SSO_MFA_ACCEPTED_VALUES = tuple(
    value.strip().lower()
    for value in os.getenv("SSO_MFA_ACCEPTED_VALUES", "true,1,yes").split(",")
    if value.strip()
)
if SSO_REMOTE_USER_ENABLED:
    _auth_index = _MIDDLEWARE_CORE.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    _MIDDLEWARE_CORE.insert(_auth_index + 1, "core.auth.TrustedProxyRemoteUserMiddleware")

AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
if SSO_REMOTE_USER_ENABLED:
    AUTHENTICATION_BACKENDS.insert(0, "django.contrib.auth.backends.RemoteUserBackend")
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
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", "28800"))

# `PF-03`. Três decisões que só fazem sentido juntas — medido no painel, com
# `CaptureQueriesContext`, quatro combinações na mesma rota:
#
#     db        + save_every=True  (como estava)   11 consultas   2 em django_session   2 BEGIN/COMMIT
#     cached_db + save_every=True                  10             1                     2
#     cached_db + save_every=False                  7             0                     0
#     cache     + save_every=True                   7             0                     0
#
# `cached_db` sozinho economiza **1 de 11**: ele tira a leitura, não a escrita —
# `cached_db.SessionStore.save()` chama o backend de banco antes de gravar no
# cache. Quem tira as outras três é desligar `SESSION_SAVE_EVERY_REQUEST`.
#
# `cache` puro chegaria no mesmo 7 sem middleware nenhum, e está fora: a sessão
# viveria só no Redis, e um reinício dele deslogaria todo mundo de uma vez.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_SAVE_EVERY_REQUEST = False

# Com `SESSION_SAVE_EVERY_REQUEST` desligado, a sessão expiraria 8 h depois do
# **login**, não da última ação. `core.middleware.RenovacaoDeSessaoMiddleware`
# devolve o deslizamento com uma escrita a cada N segundos. Padrão: um oitavo da
# janela, ou seja 1 h numa sessão de 8 h — a janela efetiva desliza entre 7 h e
# 8 h. Zero desliga a renovação (e aí a sessão volta a contar do login).
SESSION_RENOVACAO_INTERVALO = int(
    os.getenv("SESSION_RENOVACAO_INTERVALO", str(SESSION_COOKIE_AGE // 8))
)

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

_redis_url = os.getenv("REDIS_URL", "").strip()
CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.redis.RedisCache"
            if _redis_url
            else "django.core.cache.backends.locmem.LocMemCache"
        ),
        **({"LOCATION": _redis_url} if _redis_url else {}),
    }
}
TRUSTED_PROXY_IPS = tuple(
    value.strip()
    for value in os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    if value.strip()
)
METRICS_TOKEN = os.getenv("METRICS_TOKEN", "")
SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()
SENTRY_ENVIRONMENT = os.getenv("SENTRY_ENVIRONMENT", "production").strip() or "production"
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE", "").strip()

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "OPTIONS": {
            "loaders": [
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django_cotton.cotton_loader.Loader",
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                )
            ],
            "builtins": ["django_cotton.templatetags.cotton"],
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.area_permissions",
                "core.context_processors.navigation",
                "core.context_processors.shell_css_profile",
            ],
        },
    },
]

# E5 / HT-14: componentes Cotton recebem somente atributos e slots declarados.
# Context processors continuam disponíveis pelo RequestContext do próprio Cotton.
COTTON_ENABLE_CONTEXT_ISOLATION = True

WSGI_APPLICATION = "config.wsgi.application"

LANGUAGE_CODE = os.getenv("LANGUAGE_CODE", "pt-br")
TIME_ZONE = os.getenv("TIME_ZONE", "America/Sao_Paulo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env_path("STATIC_ROOT", "staticfiles")

# Rotas (OpenRouteService via backend — nunca expor OPENROUTESERVICE_API_KEY ao navegador)
ROUTE_PROVIDER = (os.getenv("ROUTE_PROVIDER") or "openrouteservice").strip().lower()
OPENROUTESERVICE_API_KEY = (os.getenv("OPENROUTESERVICE_API_KEY") or "").strip()
ROUTE_CACHE_ENABLED = os.getenv("ROUTE_CACHE_ENABLED", "true").lower() in ("1", "true", "yes")
ROUTE_REQUEST_TIMEOUT_SECONDS = int(os.getenv("ROUTE_REQUEST_TIMEOUT_SECONDS", "12"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Piso de numeração de Ofícios por ano (exceção/override de início de sequência).
# Quando definido, o próximo número gerado nunca fica abaixo do piso para aquele ano;
# a sequência segue normalmente em diante (piso, piso+1, ...). Não afeta números já existentes.
# Ex.: {2026: 75} faz o próximo ofício de 2026 ser 75/2026 (se o maior atual for < 75).

# Armazenamento de artefatos documentais gerados (assinatura, auditoria).
MEDIA_URL = "/media/"
PRIVATE_MEDIA_X_ACCEL_REDIRECT = False
PRIVATE_MEDIA_INTERNAL_URL = "/_protected_media/"
OFICIO_NUMERACAO_USAR_CONFIGURACAO = True
PRIVATE_UPLOAD_MAX_BYTES = int(os.getenv("PRIVATE_UPLOAD_MAX_BYTES", str(20 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(25 * 1024 * 1024)),
)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)),
)
DATA_UPLOAD_MAX_NUMBER_FILES = int(os.getenv("DATA_UPLOAD_MAX_NUMBER_FILES", "20"))
PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS = os.getenv(
    "PRIVATE_UPLOAD_REQUIRE_ANTIVIRUS",
    "false",
).lower() in {"1", "true", "yes"}
# Aceita flags (o valor passa por `shlex.split` em core/uploads.py).
# `--fdpass` entrega o descritor já aberto ao clamd, que roda como usuário
# `clamav` e não consegue ler o arquivo temporário 0600 do gunicorn.
CLAMAV_SCAN_COMMAND = os.getenv("CLAMAV_SCAN_COMMAND", "clamdscan --fdpass")
MEDIA_ROOT = env_path("MEDIA_ROOT", "media")

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
DOCUMENTOS_ENGINE_PROBE_CACHE_SECONDS = int(
    os.getenv("DOCUMENTOS_ENGINE_PROBE_CACHE_SECONDS", "60")
)
DOCUMENTOS_GENERATOR_VERSION = (os.getenv("DOCUMENTOS_GENERATOR_VERSION") or "1").strip() or "1"
DOCUMENTOS_ARTIFACT_CACHE = os.getenv("DOCUMENTOS_ARTIFACT_CACHE", "true").lower() in ("1", "true", "yes")
DOCUMENTOS_BINARY_CONVERSION_CACHE = os.getenv(
    "DOCUMENTOS_BINARY_CONVERSION_CACHE",
    "true",
).lower() in ("1", "true", "yes")
DOCUMENTOS_BINARY_CACHE_SECONDS = int(os.getenv("DOCUMENTOS_BINARY_CACHE_SECONDS", "86400"))
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


def _env_flag(name, default="false"):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Integração Google Drive
#
# Sem credenciais (MODO=mock), o sistema nunca chama a API — uploads são
# apenas registrados em log. A autorização é OAuth 2.0 por usuário (cada login
# conecta a própria conta em Meu perfil); não existe caminho por Service
# Account, apesar do que dizia este comentário até 25/08/2026. Para ativar:
#   1. Ative a Google Drive API e crie um ID de cliente OAuth (Aplicativo Web).
#   2. Registre GOOGLE_REDIRECT_URI como URI de redirecionamento autorizado.
#   3. Defina GOOGLE_DRIVE_MODO=ativo, GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET.
#   4. Conecte a conta e escolha a pasta raiz pela tela Meu perfil.
#
# Diagnóstico: python manage.py gdrive_check [--e2e]
# Reprocessar pendentes: python manage.py gdrive_upload_pendentes
# ---------------------------------------------------------------------------
# O Google costuma devolver o token com escopos concedidos anteriormente somados
# aos recém-pedidos (ex.: ao ampliar o escopo, o retorno inclui o antigo + o
# novo). Sem isso, oauthlib trata a diferença como erro ("Scope has changed").
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

GOOGLE_DRIVE = {
    "MODO": (os.getenv("GOOGLE_DRIVE_MODO") or "mock").strip().lower(),
    # Credenciais OAuth 2.0 (geradas no Google Cloud Console)
    "CLIENT_ID": (os.getenv("GOOGLE_CLIENT_ID") or "").strip(),
    "CLIENT_SECRET": (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip(),
    "REDIRECT_URI": (os.getenv("GOOGLE_REDIRECT_URI") or "").strip(),
    # ID da pasta raiz no Google Drive (trecho após /folders/ na URL)
    "PASTA_RAIZ_ID": (os.getenv("GOOGLE_DRIVE_PASTA_RAIZ_ID") or "").strip(),
    # Em modo mock, faz o upload simulado mas ainda persiste DriveArquivo no banco
    "UPLOAD_EM_MOCK": _env_flag("GOOGLE_DRIVE_UPLOAD_EM_MOCK", "false"),
    # Timeout (segundos) de cada chamada HTTP à API do Drive. Sem isso, uma
    # conexão travada (ex.: falha de TLS no meio do handshake) trava pra
    # sempre a chamada, e junto com ela a reorganização em massa inteira
    # (roda sequencial numa única thread) — sem nunca lançar exceção pro
    # try/except que já existe em cada artefato.
    "HTTP_TIMEOUT_SECONDS": float(os.getenv("GOOGLE_DRIVE_HTTP_TIMEOUT_SECONDS") or 30),
    # Validade do cache de pastas e da checagem da pasta raiz. O gunicorn de
    # produção mantém processos vivos por dias; com cache eterno, uma pasta
    # movida ou lixeirada pelo Drive fazia todo envio seguinte daquele worker ir
    # para um ID morto, sem erro nenhum.
    "PASTA_CACHE_TTL_SECONDS": float(os.getenv("GOOGLE_DRIVE_PASTA_CACHE_TTL_SECONDS") or 300),
}

# ---------------------------------------------------------------------------
# Celery (fila de retry em segundo plano — ex.: reenvio automático ao Drive
# quando o upload falha na hora). Sem CELERY_BROKER_URL configurado, aponta
# para um Redis local; se não houver worker/broker disponível, o objeto fica
# registrado como pendente sem executar rede no request do usuário.
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_TASK_ALWAYS_EAGER = _env_flag("CELERY_TASK_ALWAYS_EAGER", "false")
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_BEAT_SCHEDULE = {
    "google-drive-reorganizacoes-orfas": {
        "task": "integracoes.google_drive.tasks.marcar_reorganizacoes_orfas",
        "schedule": 600.0,
    },
    "documentos-geracoes-orfas-e-expiradas": {
        "task": "documentos.tasks.manter_geracoes_documentais",
        "schedule": 600.0,
    },
}

# Em produção, qualquer escrita exige vínculo ativo com uma área. A opção
# existe apenas para que suítes legadas possam construir objetos sem todo o
# contexto de tenancy; não deve ser desativada no ambiente implantado.
AREA_RBAC_REQUIRE_MEMBERSHIP = _env_flag("AREA_RBAC_REQUIRE_MEMBERSHIP", "true")
# Sem isso, ".delay()" pode ficar preso indefinidamente tentando conectar num
# broker inalcançável (rede instável, host errado) — o mesmo tipo de trava sem
# timeout que já mordeu a integração com o Google Drive. Falha rápido em vez
# de travar quem chamou (ex.: a view "Tentar novamente agora").
CELERY_BROKER_CONNECTION_TIMEOUT = float(os.getenv("CELERY_BROKER_CONNECTION_TIMEOUT") or 0.2)
CELERY_TASK_PUBLISH_RETRY = False
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "socket_connect_timeout": CELERY_BROKER_CONNECTION_TIMEOUT,
    "socket_timeout": CELERY_BROKER_CONNECTION_TIMEOUT,
}
# Fila própria para o Google Drive. Antes, tudo dividia a fila padrão e o mesmo
# worker: finalizar um ofício enfileira `organizar_oficio`, que gera de verdade
# ofício + justificativa + OS + um termo POR SERVIDOR — e o job de download que
# o usuário acabou de pedir ficava atrás dessas conversões, no mesmo worker e no
# mesmo unoserver (LibreOffice residente, uma conversão por vez).
#
# Com a rota abaixo, geração documental fica na fila padrão e o Drive vai para a
# sua; em produção são dois workers (ver docs/DEPLOY_VPS.md §5.3). ATENÇÃO: sem o
# segundo worker consumindo `CELERY_DRIVE_QUEUE`, as tarefas do Drive param na
# fila. Para voltar ao comportamento antigo (um worker só), defina
# CELERY_DRIVE_QUEUE=celery.
CELERY_TASK_DEFAULT_QUEUE = (os.getenv("CELERY_TASK_DEFAULT_QUEUE") or "celery").strip()
CELERY_DRIVE_QUEUE = (os.getenv("CELERY_DRIVE_QUEUE") or "drive").strip()
CELERY_TASK_ROUTES = (
    {"integracoes.google_drive.tasks.*": {"queue": CELERY_DRIVE_QUEUE}}
    if CELERY_DRIVE_QUEUE and CELERY_DRIVE_QUEUE != CELERY_TASK_DEFAULT_QUEUE
    else {}
)

EPROTOCOLO = {
    "AMBIENTE": (os.getenv("EPROTOCOLO_AMBIENTE") or "mock").strip().lower(),
    "BASE_URL": (os.getenv("EPROTOCOLO_BASE_URL") or "").strip(),
    "TOKEN_URL": (os.getenv("EPROTOCOLO_TOKEN_URL") or "").strip(),
    "CLIENT_ID": (os.getenv("EPROTOCOLO_CLIENT_ID") or "").strip(),
    "CLIENT_SECRET": (os.getenv("EPROTOCOLO_CLIENT_SECRET") or "").strip(),
    "CONSUMER_ID": (os.getenv("EPROTOCOLO_CONSUMER_ID") or "").strip(),
    "TIMEOUT": int(os.getenv("EPROTOCOLO_TIMEOUT", "30") or "30"),
    "VERIFY_SSL": _env_flag("EPROTOCOLO_VERIFY_SSL", "true"),
    "REAL_READONLY": _env_flag("EPROTOCOLO_REAL_READONLY", "true"),
    "REAL_MUTATIONS_ENABLED": _env_flag("EPROTOCOLO_REAL_MUTATIONS_ENABLED", "false"),
    # Códigos institucionais padrão (não sensíveis) — usados pelos mappers
    # quando o documento não traz a informação. Podem ficar vazios.
    "COD_ORGAO_PADRAO": (os.getenv("EPROTOCOLO_COD_ORGAO_PADRAO") or "").strip(),
    "NOME_ORGAO_PADRAO": (os.getenv("EPROTOCOLO_NOME_ORGAO_PADRAO") or "").strip(),
    "COD_LOCAL_ORIGEM_PADRAO": (os.getenv("EPROTOCOLO_COD_LOCAL_ORIGEM_PADRAO") or "").strip(),
    "COD_LOCAL_DESTINO_PADRAO": (os.getenv("EPROTOCOLO_COD_LOCAL_DESTINO_PADRAO") or "").strip(),
    "COD_ASSUNTO_VIAGEM": (os.getenv("EPROTOCOLO_COD_ASSUNTO_VIAGEM") or "").strip(),
    "COD_ESPECIE_OFICIO": (os.getenv("EPROTOCOLO_COD_ESPECIE_OFICIO") or "").strip(),
    "COD_PALAVRA_CHAVE_VIAGEM": (os.getenv("EPROTOCOLO_COD_PALAVRA_CHAVE_VIAGEM") or "").strip(),
    "COD_TIPO_TRAMITACAO_PADRAO": (os.getenv("EPROTOCOLO_COD_TIPO_TRAMITACAO_PADRAO") or "").strip(),
    "CPF_USUARIO_SISTEMA": (os.getenv("EPROTOCOLO_CPF_USUARIO_SISTEMA") or "").strip(),
}
