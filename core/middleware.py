import logging
import threading
import time
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.shortcuts import resolve_url

from core.tenancy import resolve_area_for_request

_local = threading.local()
request_logger = logging.getLogger("core.request")


def get_current_request():
    """Retorna a request da thread atual, ou ``None`` fora de um request (shell, comando, task)."""
    return getattr(_local, "request", None)


class CurrentRequestMiddleware:
    """Guarda a request da thread atual para código sem acesso direto a ela.

    Usado por integracoes.google_drive.signals para exibir uma mensagem
    (django.contrib.messages) quando um upload ao Drive falha durante um
    post_save — o signal não recebe a request como argumento.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-ID", "")[:64] or uuid.uuid4().hex
        started = time.perf_counter()
        _local.request = request
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = request.request_id
            duration_ms = int((time.perf_counter() - started) * 1000)
            from core.metrics import record_http_request

            record_http_request(status_code=response.status_code, duration_ms=duration_ms)
            request_logger.info(
                "request_completed status=%s duration_ms=%s",
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            _local.request = None


#: `PF-03`: chave privada que guarda quando a sessão foi renovada pela última vez.
#: **Não é `_session_expiry`**, e isso é deliberado: escrever ali faria
#: `get_expire_at_browser_close()` devolver `False` (`sessions/backends/base.py:403`)
#: e o cookie ganharia `expires`, sobrevivendo ao fechamento do navegador — o
#: oposto de `SESSION_EXPIRE_AT_BROWSER_CLOSE = True`, que este projeto liga de
#: propósito. Uma chave própria marca a sessão como modificada sem tocar nisso.
CHAVE_RENOVACAO_DE_SESSAO = "_renovada_em"


class RenovacaoDeSessaoMiddleware:
    """`PF-03`: renova a sessão de tempos em tempos, não a cada requisição.

    `SESSION_SAVE_EVERY_REQUEST = True` fazia **toda** requisição autenticada
    abrir transação de escrita no PostgreSQL. Medido no painel: 11 consultas, das
    quais 2 em `django_session` e 2 de `BEGIN`/`COMMIT`. Toda página, todo XHR de
    autosave, todo polling de documento.

    Desligar aquilo sozinho faria a sessão expirar 8 h **depois do login**, não da
    última ação — quem estivesse trabalhando às 8h01 seria deslogado no meio. Este
    middleware devolve o deslizamento com uma escrita a cada
    `SESSION_RENOVACAO_INTERVALO` segundos em vez de uma por requisição.

    Marcar a sessão como modificada basta: o `SessionStore.save()` regrava
    `expire_date` como "agora + `SESSION_COOKIE_AGE`". O usuário perde, no pior
    caso, o intervalo de renovação do fim da janela — com o padrão de 1 h numa
    sessão de 8 h, a janela efetiva desliza entre 7 h e 8 h.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._renovar_se_preciso(getattr(request, "session", None))
        return self.get_response(request)

    def _renovar_se_preciso(self, sessao):
        # Sessão anônima não tem chave e não vale escrita: renovar aqui criaria
        # linha em `django_session` para todo visitante não autenticado.
        if sessao is None or not sessao.session_key or sessao.is_empty():
            return

        intervalo = getattr(settings, "SESSION_RENOVACAO_INTERVALO", 0)
        if intervalo <= 0:
            return

        agora = time.time()
        ultima = sessao.get(CHAVE_RENOVACAO_DE_SESSAO)
        if isinstance(ultima, (int, float)) and (agora - ultima) < intervalo:
            return

        # A atribuição marca `modified`; quem grava é o `SessionMiddleware` na
        # resposta, com o `expire_date` recalculado a partir de agora.
        sessao[CHAVE_RENOVACAO_DE_SESSAO] = agora


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault(
            "Content-Security-Policy",
            "; ".join(
                [
                    "default-src 'self'",
                    "script-src 'self'",
                    "style-src 'self' 'unsafe-inline'",
                    # Tiles OSM do Leaflet (mapa do roteiro).
                    "img-src 'self' data: blob: https://*.tile.openstreetmap.org",
                    "font-src 'self' data:",
                    "connect-src 'self'",
                    "frame-src 'self'",
                    "object-src 'none'",
                    "base-uri 'self'",
                    "form-action 'self'",
                    "frame-ancestors 'self'",
                ],
            ),
        )
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        return response


class AjaxAwareLoginRequiredMiddleware(LoginRequiredMiddleware):
    """
    Mantem o redirect normal para paginas, mas devolve JSON para fetch/AJAX.

    Sem isso, uma sessao expirada faz endpoints JSON retornarem a pagina de
    login em HTML, causando erro "Unexpected token '<'" no navegador.
    """

    redirect_field_name = REDIRECT_FIELD_NAME

    def handle_no_permission(self, request, view_func):
        if _expects_json(request):
            return JsonResponse(
                {
                    "ok": False,
                    "error": "Sessao expirada. Faca login novamente para continuar.",
                    "login_url": resolve_url(self.get_login_url(view_func)),
                },
                status=401,
            )

        path = request.build_absolute_uri()
        resolved_login_url = resolve_url(self.get_login_url(view_func))
        login_scheme, login_netloc = urlsplit(resolved_login_url)[:2]
        current_scheme, current_netloc = urlsplit(path)[:2]
        if (not login_scheme or login_scheme == current_scheme) and (
            not login_netloc or login_netloc == current_netloc
        ):
            path = request.get_full_path()

        return redirect_to_login(
            path,
            resolved_login_url,
            self.get_redirect_field_name(view_func),
        )


def _expects_json(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return True
    return request.path.startswith("/roteiros/api/") or request.path.startswith("/roteiros/trechos/")


class CurrentAreaMiddleware:
    """Anexa a area de trabalho ativa em ``request.area``."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resolve_area_for_request(request)
        return self.get_response(request)


class AreaRoleRequiredMiddleware:
    """Impede que o papel LEITOR altere dados por endpoints não anotados."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    PERSONAL_PATHS = {
        "/logout/",
        "/perfil/",
        "/usuarios/selecionar-area/",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        vinculo = getattr(request, "vinculo_area", None)
        membership_required = getattr(
            settings,
            "AREA_RBAC_REQUIRE_MEMBERSHIP",
            True,
        )
        if (
            request.method not in self.SAFE_METHODS
            and getattr(request.user, "is_authenticated", False)
            and not getattr(request.user, "is_superuser", False)
            and (
                (vinculo is None and membership_required)
                or (vinculo is not None and vinculo.papel == "LEITOR")
            )
            and request.path not in self.PERSONAL_PATHS
        ):
            if _expects_json(request):
                return JsonResponse(
                    {"ok": False, "error": "Seu perfil possui acesso somente para leitura."},
                    status=403,
                )
            raise PermissionDenied("Seu perfil possui acesso somente para leitura.")
        return self.get_response(request)
