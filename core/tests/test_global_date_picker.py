import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class GlobalDatePickerTests(SimpleTestCase):
    def test_global_partial_renders_the_three_supported_modes(self):
        scenarios = (
            (
                "single",
                {
                    "single_input_id": "single-display",
                    "single_hidden_id": "single-value",
                    "single_hidden_name": "single_value",
                },
            ),
            (
                "range",
                {
                    "start_input_id": "range-start-display",
                    "end_input_id": "range-end-display",
                    "start_hidden_id": "range-start-value",
                    "end_hidden_id": "range-end-value",
                    "start_hidden_name": "range_start",
                    "end_hidden_name": "range_end",
                },
            ),
            ("multi", {"multi_input_id": "multi-display", "max_dates": 3}),
        )

        for mode, context in scenarios:
            with self.subTest(mode=mode):
                html = render_to_string(
                    "components/ui/forms/date_picker.html",
                    {"mode": mode, **context},
                )
                self.assertEqual(html.count("data-cv-date-picker\n"), 1)
                self.assertEqual(html.count("data-cv-date-picker-panel"), 1)
                self.assertIn(f'data-mode="{mode}"', html)

    def test_compact_variants_preserve_existing_triggers(self):
        filter_html = render_to_string(
            "components/ui/forms/date_picker.html",
            {
                "mode": "range",
                "control_variant": "filter-pill",
                "trigger_label": "Período da viagem",
                "start_hidden_name": "viagem_de",
                "end_hidden_name": "viagem_ate",
                "show_summary": False,
            },
        )
        self.assertIn('class="travel-period-filter__btn"', filter_html)
        self.assertIn("Período da viagem", filter_html)
        self.assertNotIn("data-cv-date-picker-start-display", filter_html)
        self.assertNotIn("data-cv-date-picker-end-display", filter_html)

        action_html = render_to_string(
            "components/ui/forms/date_picker.html",
            {
                "mode": "multi",
                "control_variant": "action-button",
                "trigger_label": "Preencher datas",
                "show_summary": False,
            },
        )
        self.assertIn("Preencher datas", action_html)
        self.assertNotIn("data-cv-date-picker-display", action_html)
        self.assertEqual(action_html.count("data-cv-date-picker-panel"), 1)

    def test_calendar_grid_uses_an_integer_uniform_gap(self):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "components"
            / "cv-date-picker.css"
        )
        css = css_path.read_text(encoding="utf-8")
        self.assertIn("--cv-date-picker-day-gap: 2px;", css)
        self.assertNotIn("scale(1.03)", css)
        self.assertIn("column-gap: var(--cv-date-picker-day-gap);", css)
        self.assertIn("row-gap: var(--cv-date-picker-day-gap);", css)

    def test_calendar_markup_exists_only_in_the_global_partial(self):
        templates_root = Path(settings.BASE_DIR) / "templates"
        global_partial = templates_root / "components" / "ui" / "forms" / "date_picker.html"

        offenders = []
        for template in templates_root.rglob("*.html"):
            if template == global_partial:
                continue
            source = template.read_text(encoding="utf-8")
            if "cv-date-picker__panel" in source or re.search(r"<div[^>]*\bdata-cv-date-picker\b", source):
                offenders.append(str(template.relative_to(settings.BASE_DIR)))

        scripts_root = Path(settings.BASE_DIR) / "static" / "js"
        for script in scripts_root.rglob("*.js"):
            source = script.read_text(encoding="utf-8")
            if re.search(r"<div[^>]*\bdata-cv-date-picker\b", source):
                offenders.append(str(script.relative_to(settings.BASE_DIR)))

        self.assertEqual(offenders, [])

    def test_no_alternative_calendar_ui_remains_in_source(self):
        base_dir = Path(settings.BASE_DIR)
        offenders = []

        for source_path in (
            *(base_dir / "templates").rglob("*.html"),
            *(base_dir / "static" / "js").rglob("*.js"),
            *(base_dir / "static" / "css").rglob("*.css"),
            *base_dir.rglob("forms.py"),
        ):
            if "staticfiles" in source_path.parts or "legacy" in source_path.parts:
                continue
            source = source_path.read_text(encoding="utf-8")
            is_global_css = source_path == base_dir / "static" / "css" / "components" / "cv-date-picker.css"
            is_global_js = source_path == base_dir / "static" / "js" / "components" / "cv-date-picker.js"
            is_template_or_form = source_path.suffix == ".html" or source_path.name == "forms.py"
            has_alternative = (
                (is_template_or_form and 'type="date"' in source)
                or (is_template_or_form and "type='date'" in source)
                or (source_path.name == "forms.py" and "forms.DateInput" in source)
                or ("cv-date-picker__day--" in source and not is_global_css and not is_global_js)
            )
            if has_alternative:
                offenders.append(str(source_path.relative_to(base_dir)))

        self.assertEqual(offenders, [])
