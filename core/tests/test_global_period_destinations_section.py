from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class GlobalPeriodDestinationsSectionTests(SimpleTestCase):
    def test_composite_owns_period_and_destination_structure(self):
        html = render_to_string(
            "cotton/travel/period_destinations_section.html",
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
        # Termos saiu em 15/08/2026: o formulário migrou para o v2 e monta
        # período e destinos com `c-v2.date_picker` + `c-v2.destinations`, que
        # emitem os MESMOS nomes de campo (`destino_estado`,
        # `destino_estado_N`) e os mesmos ganchos `data-location-*`. Quem
        # garante isso agora é `termos/tests/test_form_v2.py`. Cada tela que
        # migrar sai desta tupla; quando ela esvaziar, o composto legado morre.
        # Evento saiu em 18/08/2026, pelo mesmo caminho do termo: o painel
        # migrou para o v2 e monta período e destinos com `c-v2.date_picker` +
        # `c-v2.destinations`, com os MESMOS ganchos `data-location-*` que o
        # script da tela lê para serializar `destinos_json`.
        # Plano de Trabalho saiu em 18/08/2026, também pelo mesmo caminho: o
        # `form.destination_rows` que alimenta o `c-v2.destinations` é o mesmo
        # que o de termo, e os nomes de campo do POST não mudaram. Quem garante
        # isso agora é `planos_trabalho/tests/test_wizard_v2.py`.
        consumers = ("ordens_servico/partials/_evento_body.html",)

        for relative_path in consumers:
            with self.subTest(template=relative_path):
                source = (templates_root / relative_path).read_text(encoding="utf-8")
                self.assertIn(
                    "<c-travel.period_destinations_section",
                    source,
                )
                self.assertNotIn(
                    "<c-ui.forms.date_picker",
                    source,
                )
                self.assertNotIn(
                    "<c-travel.destination_section",
                    source,
                )
