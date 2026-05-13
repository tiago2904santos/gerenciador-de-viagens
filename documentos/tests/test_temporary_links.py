from django.test import SimpleTestCase

from documentos.services.temporary_links import build_artefato_pdf_public_conteudo_url
from documentos.services.temporary_links import create_artefato_pdf_temp_token
from documentos.services.temporary_links import parse_artefato_pdf_temp_token


class TemporaryLinksTests(SimpleTestCase):
    def test_round_trip_token(self):
        tok = create_artefato_pdf_temp_token("550e8400-e29b-41d4-a716-446655440000")
        data = parse_artefato_pdf_temp_token(tok, max_age_seconds=3600)
        self.assertEqual(data.get("pk"), "550e8400-e29b-41d4-a716-446655440000")

    def test_public_url_contains_token(self):
        tok = "abc-def"
        url = build_artefato_pdf_public_conteudo_url(tok)
        self.assertIn("t=abc-def", url)
