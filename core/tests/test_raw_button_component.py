from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase

from scripts import migrar_botoes_cotton


class RawButtonComponentTests(SimpleTestCase):
    def _render(self, source: str, context: dict | None = None) -> str:
        return Template("{% load cotton %}" + source).render(Context(context or {}))

    def test_preserva_classe_conteudo_e_atributos_html(self):
        html = self._render(
            '{% cotton v2.button class_name="legacy-toggle" type="button" '
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
        # NOVO-120: o componente emite `.button` (v2); `cv-btn` saiu. A checagem
        # é pelo ATRIBUTO class e não pela palavra solta — `type="button"` está
        # no HTML e tornaria a asserção sempre falsa.
        self.assertNotIn('class="button', html)

    def test_botao_vazio_nao_ganha_span_artificial(self):
        html = self._render(
            '{% cotton v2.button class_name="sidebar-scrim" type="button" only %}'
            "{% endcotton %}"
        )

        self.assertNotIn("<span", html)

    def test_api_visual_existente_permanece_inalterada(self):
        html = self._render(
            '{% cotton v2.button label="Salvar" variant="primary" icon="check" '
            'type="submit" only / %}'
        )

        self.assertIn('class="button button--primary"', html)
        self.assertIn('type="submit"', html)
        self.assertIn("<span>Salvar</span>", html)
        self.assertIn("button__icon", html)

    def test_atributo_booleano_condicional_so_aparece_quando_verdadeiro(self):
        source = (
            '{% cotton v2.button class_name="remove" '
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

    def test_a_primitiva_flat_nao_voltou(self):
        """`includes/performance/` foi apagado em 2026-08-20.

        Eram dois parciais com botão cru — a exceção ao contrato — e **nenhum
        template os incluía**. Eles sustentavam sozinhos a última classe
        `icon-btn` do sistema, e com ela a folha `actions/buttons.css`.
        """
        self.assertFalse(
            (migrar_botoes_cotton.ROOT / "templates" / "includes" / "performance").exists()
        )

    def test_templates_migrados_compilam(self):
        for path in migrar_botoes_cotton.targets():
            if "<c-v2.button" not in path.read_text(encoding="utf-8"):
                continue
            get_template(path.relative_to(migrar_botoes_cotton.ROOT / "templates").as_posix())
