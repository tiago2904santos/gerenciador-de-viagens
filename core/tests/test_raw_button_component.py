from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase

from scripts import migrar_botoes_cotton


class RawButtonComponentTests(SimpleTestCase):
    def _render(self, source: str, context: dict | None = None) -> str:
        return Template("{% load cotton %}" + source).render(Context(context or {}))

    def test_preserva_classe_conteudo_e_atributos_html(self):
        html = self._render(
            '{% cotton ui.buttons.button class_name="legacy-toggle" type="button" '
            'id="legacy-id" aria-pressed="false" data-state-trigger only %}'
            'Texto <em>original</em>'
            "{% endcotton %}"
        )

        self.assertIn('class="legacy-toggle"', html)
        self.assertIn('type="button"', html)
        self.assertIn('id="legacy-id"', html)
        self.assertIn('aria-pressed="false"', html)
        self.assertIn("data-state-trigger", html)
        self.assertIn("Texto <em>original</em>", html)
        self.assertNotIn("cv-btn", html)

    def test_botao_vazio_nao_ganha_span_artificial(self):
        html = self._render(
            '{% cotton ui.buttons.button class_name="sidebar-scrim" type="button" only %}'
            "{% endcotton %}"
        )

        self.assertNotIn("<span", html)

    def test_api_visual_existente_permanece_inalterada(self):
        html = self._render(
            '{% cotton ui.buttons.button label="Salvar" variant="primary" icon="check" '
            'type="submit" only / %}'
        )

        self.assertIn('class="cv-btn cv-btn--primary"', html)
        self.assertIn('type="submit"', html)
        self.assertIn("<span>Salvar</span>", html)
        self.assertIn("cv-btn__icon", html)

    def test_atributo_booleano_condicional_so_aparece_quando_verdadeiro(self):
        source = (
            '{% cotton ui.buttons.button class_name="remove" '
            ':hidden="{% if should_hide %}True{% else %}False{% endif %}" only %}'
            "Remover{% endcotton %}"
        )

        self.assertIn(" hidden", self._render(source, {"should_hide": True}))
        self.assertNotIn(" hidden", self._render(source, {"should_hide": False}))

    def test_templates_de_aplicacao_nao_reimplementam_button(self):
        failures = []
        for path in migrar_botoes_cotton.targets():
            _converted, count = migrar_botoes_cotton.convert(
                path.read_text(encoding="utf-8")
            )
            if count:
                failures.append(str(path.relative_to(migrar_botoes_cotton.ROOT)))

        self.assertEqual(failures, [])

    def test_primitiva_flat_e_a_unica_excecao_e_preserva_acessibilidade(self):
        self.assertEqual(
            migrar_botoes_cotton.CANONICAL_RAW_BUTTON_TEMPLATES,
            {"includes/performance/icon_control_flat.html"},
        )
        source = (
            migrar_botoes_cotton.ROOT
            / "templates"
            / "includes"
            / "performance"
            / "icon_control_flat.html"
        ).read_text(encoding="utf-8")

        self.assertIn('type="button"', source)
        self.assertIn('aria-label="{{ aria_label }}"', source)

    def test_templates_migrados_compilam(self):
        for path in migrar_botoes_cotton.targets():
            if "<c-ui.buttons.button" not in path.read_text(encoding="utf-8"):
                continue
            get_template(path.relative_to(migrar_botoes_cotton.ROOT / "templates").as_posix())
