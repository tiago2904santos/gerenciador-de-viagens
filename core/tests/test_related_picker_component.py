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
    "roteiros/partials/roteiro/_fonte_body.html",
    "termos/partials/_oficio_body.html",
)

# NOVO-20260818-213141-8c4bb8d9f0d5: o picker tem DUAS raízes enquanto a
# migração corre — `c-ui.forms.related_picker` e `c-v2.related_picker` —, e a
# lista acima mistura consumidores das duas. O contrato original exigia a raiz
# legada dos cinco e ficou vermelho quando três migraram; exigir a raiz v2 dos
# cinco seria o mesmo erro na direção oposta, porque o v2 ainda não tem
# `hide_search`, `plain_list`, `presentation` nem `disabled`, de que os dois
# restantes dependem.
#
# O que o contrato protege é o que sempre protegeu: NENHUM dos cinco
# reimplementa a raiz à mão. A lista abaixo é CATRACA — nomeia quem ainda está
# na raiz legada e só pode encolher. Quem migrar sai daqui no mesmo PR; quem
# voltar reprova.
NA_RAIZ_LEGADA = frozenset(
    {
        "justificativas/partials/_oficio_picker.html",
        "roteiros/partials/roteiro/_fonte_body.html",
    }
)


class RelatedPickerComponentTests(SimpleTestCase):
    def _render(self, source: str, context: dict | None = None) -> str:
        return Template("{% load cotton %}" + source).render(Context(context or {}))

    def test_renderiza_hooks_ids_e_partes_canonicas(self):
        html = self._render(
            '{% cotton ui.forms.related_picker input_id="picker-search" '
            'input_placeholder="Buscar" input_aria_label="Buscar documento" '
            'input_data_hook="doc-search" :input_data_value="key" '
            'list_id="picker-list" list_data_hook="doc-list" '
            ':list_data_value="key" empty_data_hook="doc-empty" '
            ':empty_data_value="key" empty_text="Nenhum resultado" only / %}',
            {"key": "planos"},
        )

        self.assertIn("data-related-picker-root", html)
        self.assertIn('data-related-picker-presentation="card"', html)
        self.assertIn('id="picker-search"', html)
        self.assertIn('data-doc-search="planos"', html)
        self.assertIn('id="picker-list"', html)
        self.assertIn('data-doc-list="planos"', html)
        self.assertIn('data-doc-empty="planos"', html)
        self.assertIn("search-picker__selected-list", html)

    def test_variante_sem_busca_preserva_painel_e_lista_simples(self):
        html = self._render(
            '{% cotton ui.forms.related_picker :hide_search="True" '
            ':plain_list="True" panel_extra_class="route-panel" '
            'list_id="route-list" only / %}'
        )

        self.assertNotIn('type="search"', html)
        self.assertIn('data-related-picker-presentation="card"', html)
        self.assertIn("search-picker__selected-panel route-panel", html)
        self.assertNotIn("search-picker__selected-list", html)
        self.assertIn('id="route-list"', html)

    def test_cinco_consumidores_nao_reimplementam_a_raiz(self):
        templates_root = ROOT / "templates"
        for relative in CONSUMERS:
            source = (templates_root / relative).read_text(encoding="utf-8")
            raiz = (
                "<c-ui.forms.related_picker"
                if relative in NA_RAIZ_LEGADA
                else "<c-v2.related_picker"
            )
            self.assertIn(raiz, source, relative)
            self.assertNotIn('<div class="search-picker search-picker--', source, relative)
            get_template(relative)

    def test_a_catraca_da_raiz_legada_so_encolhe(self):
        """Sem isto a lista acima vira inventário: quem migrasse ficaria nela
        para sempre, e o contrato pararia de dizer quanto falta."""
        templates_root = ROOT / "templates"
        ja_migrados = sorted(
            relative
            for relative in NA_RAIZ_LEGADA
            if "<c-v2.related_picker"
            in (templates_root / relative).read_text(encoding="utf-8")
        )
        self.assertEqual(ja_migrados, [], "consumidor migrado ainda listado como legado")
        self.assertLessEqual(len(NA_RAIZ_LEGADA), 2, "a catraca da raiz legada subiu")
