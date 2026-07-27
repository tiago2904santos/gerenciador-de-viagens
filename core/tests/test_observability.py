import json
import logging

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.logging import JsonFormatter


class MetricsEndpointTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(METRICS_TOKEN="segredo")
    def test_metrics_exige_bearer_e_expoe_formato_prometheus(self):
        self.assertEqual(self.client.get(reverse("core:metrics")).status_code, 404)

        response = self.client.get(
            reverse("core:metrics"),
            HTTP_AUTHORIZATION="Bearer segredo",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cv3_http_requests_total")
        self.assertContains(response, "cv3_document_generation_sla_violations_total")


class StructuredLoggingTests(SimpleTestCase):
    def test_formatter_gera_json_valido_com_aspas(self):
        record = logging.LogRecord(
            "teste",
            logging.INFO,
            __file__,
            1,
            'mensagem com "aspas"',
            (),
            None,
        )
        record.request_id = "req-1"
        record.request_method = "GET"
        record.request_path = "/teste/"

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["request_id"], "req-1")
        self.assertEqual(payload["message"], 'mensagem com "aspas"')
