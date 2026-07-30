from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class GlobalPeriodDestinationsSectionTests(SimpleTestCase):
    def test_composite_owns_period_and_destination_structure(self):
        html = render_to_string(
            "components/travel/period_destinations_section.html",
            {
                "period_title_id": "audit-period-title",
                "picker_id": "audit-date-picker",
                "start_input_id": "audit-start-display",
                "end_input_id": "audit-end-display",
                "destination_section_id": "audit-destinations",
                "destination_title_id": "audit-destinations-title",
                "destination_add_button_id": "audit-add-destination",
                "destination_list_id": "audit-destinations-list",
            },
        )

        self.assertEqual(html.count("data-travel-schedule"), 1)
        self.assertEqual(html.count("data-cv-date-picker\n"), 1)
        self.assertEqual(html.count("data-location-rows"), 1)
        self.assertEqual(html.count("data-location-add"), 1)
        self.assertEqual(html.count("data-location-list"), 1)
        self.assertIn('id="audit-period-title"', html)
        self.assertIn('id="audit-destinations"', html)

    def test_operational_travel_forms_use_the_composite(self):
        templates_root = Path(settings.BASE_DIR) / "templates"
        consumers = (
            "eventos/partials/_detalhe_dados_body.html",
            "termos/partials/_evento_body.html",
            "ordens_servico/partials/_evento_body.html",
            "planos_trabalho/partials/_identificacao_evento_body.html",
        )

        for relative_path in consumers:
            with self.subTest(template=relative_path):
                source = (templates_root / relative_path).read_text(encoding="utf-8")
                self.assertIn(
                    "components/travel/period_destinations_section.html",
                    source,
                )
                self.assertNotIn(
                    "components/ui/forms/date_picker.html",
                    source,
                )
                self.assertNotIn(
                    "components/travel/destination_section.html",
                    source,
                )
