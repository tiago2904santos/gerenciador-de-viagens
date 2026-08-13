from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class CssClassLogicContractTests(SimpleTestCase):
    """NOVO-14: comportamento não depende do nome visual do componente."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)

    def source(self, relative_path):
        return (self.root / relative_path).read_text(encoding="utf-8")

    def test_selected_picker_option_uses_aria_state(self):
        source = self.source("static/js/components/picker-select.js")
        self.assertNotIn(
            "classList.contains('custom-select__option--selected')", source
        )
        self.assertIn("getAttribute('aria-selected') === 'true'", source)

    def test_overlay_reads_visibility_instead_of_open_class(self):
        source = self.source("static/js/components/overlay.js")
        self.assertNotIn('classList.contains("action-menu--open")', source)
        self.assertIn("var wasOpen = !menu.hidden", source)

    def test_tooltip_tone_has_semantic_hook(self):
        source = self.source("static/js/components/icon-tooltips.js")
        field_button = self.source(
            "templates/cotton/ui/buttons/field_manage_button.html"
        )
        self.assertNotIn('classList.contains("icon-btn--field-manage")', source)
        self.assertIn('getAttribute("data-tooltip-tone") === "accent"', source)
        self.assertIn('data_tooltip_tone="accent"', field_button)
        rendered = render_to_string(
            "cotton/ui/buttons/field_manage_button.html",
            {"action_label": "Gerenciar campo"},
        )
        self.assertIn('data-tooltip-tone="accent"', rendered)

    def test_route_time_kind_has_data_hook_in_both_renderers(self):
        editor = self.source("static/js/pages/roteiros/editor/index.js")
        dynamic_renderer = self.source("static/js/pages/roteiros/editor/trechos.js")
        return_template = self.source(
            "templates/roteiros/partials/roteiro/_retorno_body.html"
        )
        self.assertNotIn("classList.contains('trecho-tempo-viagem-hhmm')", editor)
        self.assertNotIn(
            "classList.contains('trecho-tempo-adicional-hhmm')", editor
        )
        self.assertIn('data-route-time-kind="travel"', dynamic_renderer)
        self.assertIn('data-route-time-kind="additional"', dynamic_renderer)
        self.assertIn('data-route-time-kind="additional"', return_template)
