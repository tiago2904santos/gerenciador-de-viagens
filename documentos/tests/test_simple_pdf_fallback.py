from django.test import SimpleTestCase

from documentos.services.adapters.simple_pdf_fallback import render_simple_pdf_bytes
from documentos.services.types import DocumentoTipo


class SimplePdfFallbackTests(SimpleTestCase):
    def test_emits_valid_pdf_magic(self):
        raw = render_simple_pdf_bytes(
            tipo=DocumentoTipo.OFICIO,
            payload={
                "institucional": {"nome_orgao": "Órgão"},
                "oficio": {"numero_formatado": "1/2026", "motivo": "Viagem à Brasília"},
                "justificativa": {"exigida": False, "texto": ""},
            },
        )
        self.assertTrue(raw.startswith(b"%PDF"))
