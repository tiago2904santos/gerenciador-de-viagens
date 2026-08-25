from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DownloadPickerModalTests(SimpleTestCase):
    def test_modal_preserva_shell_e_fechamento_dentro_de_formulario(self):
        template = (
            Path(settings.BASE_DIR) / "templates" / "cotton" / "v2" / "download_picker.html"
        ).read_text(encoding="utf-8")
        javascript = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "download-queue.js"
        ).read_text(encoding="utf-8")

        self.assertIn(':own_form="True"', template)
        self.assertIn('hook="data-download-picker-close"', template)
        self.assertIn('[data-download-picker-close]', javascript)
        self.assertIn("window.CV.overlay.closeDialog(dialogo)", javascript)
        self.assertIn('data-download-picker-close-bound', javascript)
        self.assertIn('fechar.addEventListener("click"', javascript)

    def test_cabecalho_do_documento_nao_bloqueia_cliques_do_modal(self):
        javascript = (
            Path(settings.BASE_DIR)
            / "static"
            / "js"
            / "pages"
            / "oficios-documentos-inline.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "dialog, [data-overlay-trigger], [data-attach-signed-trigger], "
            "[data-download-picker-trigger]",
            javascript,
        )
