"""Contrato visual da lista de termos na etapa 5 do evento."""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TermosSpacingTests(SimpleTestCase):
    def test_linhas_de_termo_usam_o_ritmo_global_de_registros(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "eventos" / "detalhe.html"
        ).read_text(encoding="utf-8")

        self.assertIn('body_extra_class="list-page__panel-rows"', template)
