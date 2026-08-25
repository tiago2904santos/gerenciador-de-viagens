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

    def test_linha_principal_do_termo_abre_seletor_completo_de_downloads(self):
        template = (
            Path(settings.BASE_DIR)
            / "templates"
            / "eventos"
            / "partials"
            / "_detalhe_termo_linha.html"
        ).read_text(encoding="utf-8")

        self.assertIn("<c-v2.download_picker", template)
        pagina = (
            Path(settings.BASE_DIR) / "templates" / "eventos" / "detalhe.html"
        ).read_text(encoding="utf-8")
        self.assertIn("js/components/download-queue.js", pagina)

        html = render_to_string(
            "eventos/partials/_detalhe_termo_linha.html",
            {
                "row": {
                    "title": "Termo X",
                    "meta_line": "Meta",
                    "visualizar_url": "/termo/visualizar/",
                    "pdf_url": "/termo/pdf/",
                    "docx_url": "/termo/docx/",
                    "downloads_url": "/termo/downloads/",
                    "download_picker_id": "evento-termo-downloads-12",
                },
                "row_index": 1,
            },
        )
        self.assertIn("data-download-picker-trigger", html)
        self.assertIn('id="evento-termo-downloads-12"', html)
        self.assertIn('data-src="/termo/downloads/"', html)
        self.assertNotIn('id="evento-termo-document-menu-1"', html)

    def test_linha_individual_preserva_menu_do_documento_especifico(self):
        html = render_to_string(
            "eventos/partials/_detalhe_termo_linha.html",
            {
                "row": {
                    "title": "Servidor X",
                    "meta_line": "Meta",
                    "visualizar_url": "/termo/visualizar/",
                    "pdf_url": "/termo/pdf/",
                    "docx_url": "/termo/docx/",
                },
                "row_index": 2,
            },
        )

        self.assertIn('id="evento-termo-document-menu-2"', html)
        self.assertIn('aria-controls="evento-termo-document-menu-2"', html)

    def test_menu_de_documentos_fica_acima_do_stepper_fixo(self):
        css = (
            Path(settings.BASE_DIR) / "static" / "css" / "v2" / "menu.css"
        ).read_text(encoding="utf-8")
        regra = css[css.index(":is(html[data-theme]) .menu {") :]
        regra = regra[: regra.index("}")]

        self.assertIn(
            "z-index: calc(var(--z-sticky-stepper, 1100) + 10)", regra
        )
