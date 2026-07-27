import inspect
from unittest import TestCase

from documentos.services.adapters.weasyprint_pdf import render_pdf_bytes_weasyprint


class WeasyPrintSecurityTests(TestCase):
    def test_presentational_hints_permanece_desabilitado(self):
        source = inspect.getsource(render_pdf_bytes_weasyprint)
        self.assertIn("presentational_hints=False", source)
