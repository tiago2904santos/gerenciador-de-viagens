from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)


class AlertAutoDismissTests(SimpleTestCase):
    def test_mensagens_django_entram_no_descarte_de_cinco_segundos(self):
        js = (ROOT / "static/js/components/notice-auto-dismiss.js").read_text(
            encoding="utf-8"
        )

        self.assertIn(".alert-stack .alert", js)
        self.assertIn("var ESPERA = 5000", js)
        self.assertIn('aviso.getAttribute("data-tone")', js)

    def test_pilha_das_mensagens_tem_respiro_e_transicao(self):
        css = (ROOT / "static/css/v2/alert.css").read_text(encoding="utf-8")

        self.assertIn(":is(html[data-theme]) .alert-stack {", css)
        self.assertIn(":is(html[data-theme]) .alert-stack .alert {", css)
        self.assertIn("margin-bottom: var(--gap);", css)
        self.assertIn("padding-bottom: var(--gap-tight);", css)
