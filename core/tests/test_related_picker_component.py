from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
CONSUMERS = (
    "eventos/partials/_documento_panel.html",
    "justificativas/partials/_oficio_picker.html",
    "ordens_servico/partials/_oficios_body.html",
    "termos/partials/_oficio_body.html",
)


class RelatedPickerComponentTests(SimpleTestCase):
    def _render(self, source: str, context: dict | None = None) -> str:
        return Template("{% load cotton %}" + source).render(Context(context or {}))

    def test_renderiza_hooks_ids_e_partes_canonicas(self):
        html = self._render(
            '{% cotton v2.related_picker input_id="picker-search" '
            'input_placeholder="Buscar" input_aria_label="Buscar documento" '
            'list_id="picker-list" empty_id="picker-empty" '
            'empty_text="Nenhum resultado" only / %}',
            {"key": "planos"},
        )

        self.assertIn("data-related-picker-root", html)
        self.assertIn('data-related-picker-presentation="card"', html)
        self.assertIn('id="picker-search"', html)
        self.assertIn("data-related-picker-search", html)
        self.assertIn('id="picker-list"', html)
        self.assertIn("data-related-picker-list", html)
        self.assertIn('id="picker-empty"', html)
        self.assertIn("data-related-picker-empty", html)
        self.assertIn("search-picker__selected-list", html)

    def test_o_v2_preserva_painel_e_lista_canonicos(self):
        html = self._render(
            '{% cotton v2.related_picker panel_extra_class="route-panel" '
            'list_id="route-list" only / %}'
        )

        self.assertIn('type="search"', html)
        self.assertIn('data-related-picker-presentation="card"', html)
        self.assertIn("search-picker__selected-list related-route-list route-panel", html)
        self.assertIn('id="route-list"', html)

    def test_consumidores_nao_reimplementam_a_raiz(self):
        templates_root = ROOT / "templates"
        for relative in CONSUMERS:
            source = (templates_root / relative).read_text(encoding="utf-8")
            self.assertIn("<c-v2.related_picker", source, relative)
            self.assertNotIn('<div class="search-picker search-picker--', source, relative)
            get_template(relative)
