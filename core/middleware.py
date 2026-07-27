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
                    "img-src 'self' data: blob:",
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
