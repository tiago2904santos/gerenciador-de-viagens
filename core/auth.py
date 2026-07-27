from __future__ import annotations

from django.conf import settings
from django.contrib.auth.middleware import RemoteUserMiddleware
from django.core.exceptions import PermissionDenied


class TrustedProxyRemoteUserMiddleware(RemoteUserMiddleware):
    """Aceita identidade SSO somente de proxy explicitamente confiável."""

    header = "HTTP_X_AUTHENTICATED_USER"

    def process_request(self, request):
        remote_addr = request.META.get("REMOTE_ADDR", "")
        mfa_header = getattr(settings, "SSO_MFA_ASSERTION_HEADER", "HTTP_X_AUTH_MFA")
        if remote_addr not in getattr(settings, "TRUSTED_PROXY_IPS", ()):
            request.META.pop(self.header, None)
            request.META.pop(mfa_header, None)
            return

        if getattr(settings, "SSO_MFA_REQUIRED", True):
            accepted = {
                value.strip().lower()
                for value in getattr(settings, "SSO_MFA_ACCEPTED_VALUES", ("true", "1", "yes"))
            }
            asserted = str(request.META.get(mfa_header, "")).strip().lower()
            if self.header in request.META and asserted not in accepted:
                raise PermissionDenied("A autenticação institucional exige MFA.")
        return super().process_request(request)
