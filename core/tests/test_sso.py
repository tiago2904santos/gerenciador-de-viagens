from unittest import mock

from django.contrib.auth.middleware import RemoteUserMiddleware
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase, override_settings

from core.auth import TrustedProxyRemoteUserMiddleware


class TrustedProxyRemoteUserMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.middleware = TrustedProxyRemoteUserMiddleware(lambda request: None)
        self.factory = RequestFactory()

    @override_settings(TRUSTED_PROXY_IPS=("127.0.0.1",), SSO_MFA_REQUIRED=True)
    def test_rejeita_identidade_sem_assercao_mfa(self):
        request = self.factory.get(
            "/",
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_AUTHENTICATED_USER="servidor",
        )

        with self.assertRaises(PermissionDenied):
            self.middleware.process_request(request)

    @override_settings(TRUSTED_PROXY_IPS=("127.0.0.1",), SSO_MFA_REQUIRED=True)
    @mock.patch.object(RemoteUserMiddleware, "process_request")
    def test_aceita_identidade_com_mfa_de_proxy_confiavel(self, parent):
        request = self.factory.get(
            "/",
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_AUTHENTICATED_USER="servidor",
            HTTP_X_AUTH_MFA="true",
        )

        self.middleware.process_request(request)

        parent.assert_called_once_with(request)

    @override_settings(TRUSTED_PROXY_IPS=("10.0.0.1",), SSO_MFA_REQUIRED=True)
    def test_remove_cabecalhos_de_origem_nao_confiavel(self):
        request = self.factory.get(
            "/",
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_AUTHENTICATED_USER="invasor",
            HTTP_X_AUTH_MFA="true",
        )

        self.middleware.process_request(request)

        self.assertNotIn("HTTP_X_AUTHENTICATED_USER", request.META)
        self.assertNotIn("HTTP_X_AUTH_MFA", request.META)
