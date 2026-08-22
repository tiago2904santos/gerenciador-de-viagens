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
                    "cotton/v2/date_picker.html",
                    {"mode": mode, **context},
                )
                self.assertEqual(html.count("data-cv-date-picker\n"), 1)
                self.assertEqual(html.count("data-cv-date-picker-panel"), 1)
                self.assertIn(f'data-mode="{mode}"', html)

    def test_compact_variants_preserve_existing_triggers(self):
        filter_html = render_to_string(
            "cotton/v2/date_picker.html",
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
            "cotton/v2/date_picker.html",
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

    def test_multi_mode_opts_into_repeated_dates_only_when_requested(self):
        sem_repeticao = render_to_string(
            "cotton/v2/date_picker.html",
            {"mode": "multi", "multi_input_id": "multi-display", "max_dates": 3},
        )
        self.assertNotIn("data-allow-repeat-dates", sem_repeticao)
        self.assertNotIn("data-cv-date-picker-undo", sem_repeticao)

        com_repeticao = render_to_string(
            "cotton/v2/date_picker.html",
            {
                "mode": "multi",
                "multi_input_id": "multi-display",
                "max_dates": 3,
                "allow_repeat_dates": True,
            },
        )
        self.assertIn('data-allow-repeat-dates="true"', com_repeticao)
        self.assertIn("data-cv-date-picker-undo", com_repeticao)

    def test_roteiro_trechos_calendar_allows_repeated_dates(self):
        html = render_to_string(
            "cotton/v2/date_picker.html",
            {"mode": "multi", "allow_repeat_dates": True, "max_dates": 3},
        )
        self.assertIn('data-allow-repeat-dates="true"', html)
        self.assertIn('class="date-picker date-field"', html)
        self.assertIn("data-cv-date-picker-trigger", html)
        self.assertNotIn("cv-btn--secondary", html)

    def test_calendar_grid_uses_an_integer_uniform_gap(self):
        css_path = (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "v2"
            / "date-picker.css"
        )
        css = css_path.read_text(encoding="utf-8")
        self.assertIn("--date-picker-day-gap: 2px;", css)
        self.assertNotIn("scale(1.03)", css)
        self.assertIn("column-gap: var(--date-picker-day-gap);", css)
        self.assertIn("row-gap: var(--date-picker-day-gap);", css)

    def test_calendar_markup_exists_only_in_the_global_partial(self):
        templates_root = Path(settings.BASE_DIR) / "templates"
        global_partial = templates_root / "cotton" / "v2" / "date_picker.html"

        offenders = []
        for template in templates_root.rglob("*.html"):
            if template == global_partial:
                continue
            source = template.read_text(encoding="utf-8")
            if "date-picker__panel" in source or re.search(r"<div[^>]*\bdata-cv-date-picker\b", source):
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
            # NOVO-12: bundles só concatenam as fontes canônicas — auditar as fontes.
            if source_path.name.endswith((".bundle.css", ".bundle.js")) or (
                source_path.parent == base_dir / "static" / "css" / "profiles"
            ):
                continue
            source = source_path.read_text(encoding="utf-8")
            # TRÊS folhas globais, e não uma: `fields/date-picker.css` é a do
            # sistema antigo, `v2/date-picker.css` a do novo e
            # `ui/date-picker.css` a pele do trilho de filtro — todas são O
            # calendário do seu sistema, não um calendário alternativo. É a
            # mesma convivência que o resto da migração já tem.
            #
            # NOVO-20260818-213141-9f2f0d2c4c95: a terceira entrou com o trilho
            # de filtro (`ui-date-picker`, em `ui/headers/filter_page_header`) e
            # esta lista não acompanhou, deixando o contrato vermelho. Ela é
            # escopada em `.ui-date-picker` e só repinta o GATILHO e os botões
            # do painel do mesmo motor (`js/components/date-picker.js`); não há
            # segundo calendário. Quando o trilho legado sair, a folha sai com
            # ele e esta entrada volta a duas.
            is_global_css = source_path in (
                base_dir / "static" / "css" / "fields" / "date-picker.css",
                base_dir / "static" / "css" / "ui" / "date-picker.css",
                base_dir / "static" / "css" / "v2" / "date-picker.css",
            )
            is_global_js = source_path == base_dir / "static" / "js" / "components" / "date-picker.js"
            is_template_or_form = source_path.suffix == ".html" or source_path.name == "forms.py"
            has_alternative = (
                (is_template_or_form and 'type="date"' in source)
                or (is_template_or_form and "type='date'" in source)
                or (source_path.name == "forms.py" and "forms.DateInput" in source)
                or ("date-picker__day--" in source and not is_global_css and not is_global_js)
            )
            if has_alternative:
                offenders.append(str(source_path.relative_to(base_dir)))

        self.assertEqual(offenders, [])


class PainelAndaComAPaginaTests(SimpleTestCase):
    """O painel é ancorado ao campo, não à janela.

    Com `position: fixed` ele só acompanhava a âncora enquanto coubesse na tela;
    quando não cabia, a conta terminava numa trava contra as bordas da janela e
    ele parava, com a página rolando por baixo. Medido no editor de roteiro:
    120px de rolagem moviam a âncora 120 e o painel 60.
    """

    def _motor(self):
        return (
            Path(settings.BASE_DIR)
            / "static"
            / "js"
            / "components"
            / "date-picker.js"
        ).read_text(encoding="utf-8")

    def _folha(self):
        return (
            Path(settings.BASE_DIR)
            / "static"
            / "css"
            / "v2"
            / "date-picker.css"
        ).read_text(encoding="utf-8")

    def test_o_painel_e_posicionado_em_coordenadas_de_documento(self):
        motor = self._motor()
        self.assertIn("panel.style.position = 'absolute';", motor)
        self.assertIn("panel.style.top = (top + scrollY) + 'px';", motor)
        self.assertIn("panel.style.left = (left + scrollX) + 'px';", motor)
        self.assertNotIn("panel.style.position = 'fixed';", motor)

    def test_a_folha_declara_o_mesmo_posicionamento_do_motor(self):
        regra = self._folha().split(".date-picker__panel {", 1)[1].split("}", 1)[0]
        self.assertIn("position: absolute;", regra)
        self.assertNotIn("position: fixed;", regra)

    def test_nao_ha_trava_vertical_contra_a_janela(self):
        """A trava era o que descolava o painel do campo."""
        motor = self._motor()
        self.assertNotIn("vh - panelHeight - margin", motor)

    def test_o_lado_do_painel_e_escolhido_uma_vez_na_abertura(self):
        """Refazer a escolha a cada rolagem faria o painel pular de lado do
        campo enquanto o usuário lê."""
        motor = self._motor()
        self.assertIn("function positionPanel(recalcularLado) {", motor)
        self.assertIn("if (recalcularLado) {", motor)
        self.assertIn("positionPanel(true);", motor)

