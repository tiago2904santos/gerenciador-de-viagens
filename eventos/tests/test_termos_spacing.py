"""Contrato visual da lista de termos na etapa 5 do evento."""
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class TermosSpacingTests(SimpleTestCase):
    def test_linhas_de_termo_usam_o_ritmo_global_de_registros(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "eventos" / "detalhe.html"
        ).read_text(encoding="utf-8")

        self.assertIn('body_extra_class="list-page__panel-rows"', template)

    def test_paineis_de_planejamento_usam_o_ritmo_global_entre_secoes(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "eventos" / "detalhe.html"
        ).read_text(encoding="utf-8")

        self.assertEqual(template.count('extra_class="evento-planning-panel"'), 2)

    def test_linha_de_termo_agrupa_documentos_em_menu(self):
        template = (
            Path(settings.BASE_DIR)
            / "templates"
            / "eventos"
            / "partials"
            / "_detalhe_termo_linha.html"
        ).read_text(encoding="utf-8")

        self.assertIn('icon="more" :menu_id="menu_id"', template)
        self.assertIn('title="Visualizar termo"', template)
        self.assertIn('title="Baixar PDF"', template)
        self.assertIn('title="Baixar DOCX"', template)
        self.assertNotIn('aria_label="Abrir o PDF do termo"', template)

        html = render_to_string(
            "eventos/partials/_detalhe_termo_linha.html",
            {
                "row": {
                    "title": "Termo X",
                    "meta_line": "Meta",
                    "visualizar_url": "/termo/visualizar/",
                    "pdf_url": "/termo/pdf/",
                    "docx_url": "/termo/docx/",
                },
                "row_index": 1,
            },
        )
        self.assertIn('id="evento-termo-document-menu-1"', html)
        self.assertIn('aria-controls="evento-termo-document-menu-1"', html)
