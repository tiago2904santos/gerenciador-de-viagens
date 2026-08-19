from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class GlobalPeriodDestinationsSectionTests(SimpleTestCase):
    def test_composite_v2_owns_period_and_destination_slot(self):
        html = render_to_string(
            "cotton/v2/period_destinations.html",
            {
                "period_id": "audit-date-picker",
                "title": "Período e destinos",
                "destinations": '<div data-location-rows></div>',
            },
        )

        self.assertEqual(html.count("data-cv-date-picker\n"), 1)
        self.assertIn('id="audit-date-picker"', html)
        self.assertIn("Período e destinos", html)
        self.assertIn("data-location-rows", html)
        self.assertNotIn("c-travel.", html)

    def test_operational_travel_forms_compose_only_v2(self):
        templates_root = Path(settings.BASE_DIR) / "templates"
        consumers = (
            "eventos/partials/_detalhe_dados_body.html",
            "termos/partials/_termo_form_body.html",
            "ordens_servico/partials/_os_form_body.html",
            "planos_trabalho/partials/_identificacao_evento_body.html",
        )

        for relative_path in consumers:
            with self.subTest(template=relative_path):
                source = (templates_root / relative_path).read_text(encoding="utf-8")
                self.assertIn("<c-v2.date_picker", source)
                self.assertIn("<c-v2.destinations", source)
                self.assertNotIn("<c-travel.", source)
                self.assertNotIn("<c-ui.forms.date_picker", source)
