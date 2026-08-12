from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, override_settings

from core.errors import capture
from core.observability import initialize_error_tracking


class _Scope:
    def __init__(self):
        self.tags = {}
        self.contexts = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def set_tag(self, key, value):
        self.tags[key] = value

    def set_context(self, key, value):
        self.contexts[key] = value


class ErrorTrackingInitializationTests(SimpleTestCase):
    @override_settings(SENTRY_DSN="")
    def test_sem_dsn_permanece_desabilitado(self):
        self.assertFalse(initialize_error_tracking())

    @override_settings(
        SENTRY_DSN="https://public@example.invalid/1",
        SENTRY_ENVIRONMENT="homologacao",
        SENTRY_RELEASE="abc123",
    )
    def test_dsn_inicializa_sem_pii_e_sem_tracing(self):
        sdk = SimpleNamespace(init=mock.Mock())
        with mock.patch.dict("sys.modules", {"sentry_sdk": sdk}):
            self.assertTrue(initialize_error_tracking())

        sdk.init.assert_called_once_with(
            dsn="https://public@example.invalid/1",
            environment="homologacao",
            release="abc123",
            send_default_pii=False,
            traces_sample_rate=0.0,
        )

    @override_settings(SENTRY_DSN="https://public@example.invalid/1")
    def test_falha_de_inicializacao_nao_impede_o_boot(self):
        sdk = SimpleNamespace(init=mock.Mock(side_effect=RuntimeError("fora")))
        with mock.patch.dict("sys.modules", {"sentry_sdk": sdk}):
            with self.assertLogs("core.observability", level="ERROR"):
                self.assertFalse(initialize_error_tracking())


class CaptureRemoteTests(SimpleTestCase):
    @override_settings(SENTRY_DSN="https://public@example.invalid/1")
    def test_capture_encaminha_excecao_com_contexto_estruturado(self):
        scope = _Scope()
        sdk = SimpleNamespace(
            is_initialized=mock.Mock(return_value=True),
            new_scope=mock.Mock(return_value=scope),
            capture_exception=mock.Mock(),
        )
        error = ValueError("falha")

        with mock.patch.dict("sys.modules", {"sentry_sdk": sdk}):
            with self.assertLogs("core.errors", level="ERROR"):
                self.assertIs(capture(error, "documentos.render", oficio_id=7), error)

        sdk.capture_exception.assert_called_once_with(error)
        self.assertEqual(scope.tags, {"error.context": "documentos.render"})
        self.assertEqual(scope.contexts, {"error_data": {"oficio_id": 7}})

    @override_settings(SENTRY_DSN="https://public@example.invalid/1")
    def test_falha_do_backend_nao_mascara_erro_original(self):
        sdk = SimpleNamespace(is_initialized=mock.Mock(side_effect=RuntimeError("fora")))
        error = ValueError("falha")

        with mock.patch.dict("sys.modules", {"sentry_sdk": sdk}):
            with self.assertLogs("core.errors", level="WARNING"):
                self.assertIs(capture(error, "documentos.render"), error)
