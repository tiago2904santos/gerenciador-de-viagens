import json
import logging

from django.test import SimpleTestCase

from core.errors import capture
from core.logging import JsonFormatter
from scripts.audit_django_architecture import except_exception_without_capture


class ErrorCaptureTests(SimpleTestCase):
    def test_capture_emite_contexto_estruturado_e_traceback(self):
        logger = logging.getLogger("test.core.errors")
        handler = _RecordHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        logger.propagate = False
        exc = RuntimeError("Drive indisponível")

        try:
            returned = capture(
                exc,
                "drive.upload",
                logger=logger,
                arquivo_id="arquivo-42",
            )
        finally:
            logger.removeHandler(handler)
            logger.propagate = True

        self.assertIs(returned, exc)
        self.assertEqual(len(handler.records), 1)
        record = handler.records[0]
        self.assertEqual(record.error_context, "drive.upload")
        self.assertEqual(record.error_type, "RuntimeError")
        self.assertEqual(record.error_data, {"arquivo_id": "arquivo-42"})
        self.assertEqual(record.exc_info[:2], (RuntimeError, exc))

    def test_json_formatter_inclui_campos_do_capture(self):
        record = logging.LogRecord(
            "test.core.errors",
            logging.ERROR,
            __file__,
            1,
            "falha",
            (),
            None,
        )
        record.error_context = "drive.upload"
        record.error_type = "RuntimeError"
        record.error_data = {"arquivo_id": "arquivo-42"}

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["error_context"], "drive.upload")
        self.assertEqual(payload["error_type"], "RuntimeError")
        self.assertEqual(payload["error_data"], {"arquivo_id": "arquivo-42"})


class DriveExceptionAuditTests(SimpleTestCase):
    def test_detecta_handler_generico_sem_capture(self):
        code = """
try:
    enviar()
except Exception as exc:
    logger.exception("falhou")
"""
        self.assertEqual(except_exception_without_capture(code), [4])

    def test_aceita_handler_generico_com_capture(self):
        code = """
try:
    enviar()
except Exception as exc:
    capture(exc, "drive.enviar")
"""
        self.assertEqual(except_exception_without_capture(code), [])

    def test_exige_capture_incondicional_como_primeira_instrucao(self):
        code = """
try:
    enviar()
except Exception as exc:
    if deve_logar:
        capture(exc, "drive.enviar")
"""
        self.assertEqual(except_exception_without_capture(code), [4])


class _RecordHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)
