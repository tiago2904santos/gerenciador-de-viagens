from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
CONSUMERS = (
    "eventos/partials/_evento_card_body.html",
    "oficios/partials/_oficio_card_body.html",
    "planos_trabalho/partials/_plano_card_body.html",
    "prestacoes_contas/partials/_prestacao_card_body.html",
    "roteiros/partials/_roteiro_card_body.html",
)


class ItineraryComponentTests(SimpleTestCase):
    def _render(self, source: str, context: dict | None = None) -> str:
        return Template("{% load cotton %}" + source).render(Context(context or {}))

    def test_renderiza_trechos_com_periodo_sem_mudar_o_contrato_visual(self):
        html = self._render(
            '{% cotton ui.lists.itinerary :items="items" only / %}',
            {
                "items": [
                    {
                        "rota": "Curitiba → Londrina",
                        "saida": "10/08 08:00",
                        "chegada": "10/08 14:00",
                    },
                    {"rota": "Londrina → Curitiba", "saida": "", "chegada": ""},
                ]
            },
        )

        self.assertIn('class="itinerary"', html)
        self.assertEqual(html.count('class="itinerary__leg"'), 2)
        self.assertIn("Curitiba → Londrina", html)
        self.assertIn("10/08 08:00 → 10/08 14:00", " ".join(html.split()))
        self.assertEqual(html.count('class="itinerary__time"'), 1)

    def test_renderiza_itens_textuais_e_estado_vazio_configuravel(self):
        text_html = self._render(
            '{% cotton ui.lists.itinerary :items="items" :text_items="True" only / %}',
            {"items": ["Fiscalização", "Atendimento"]},
        )
        empty_html = self._render(
            '{% cotton ui.lists.itinerary :items="items" empty_label="Nada selecionado" '
            'empty_class="custom-empty" only / %}',
            {"items": []},
        )

        self.assertIn("Fiscalização", text_html)
        self.assertIn("Atendimento", text_html)
        self.assertIn('class="custom-empty"', empty_html)
        self.assertIn("Nada selecionado", empty_html)
        self.assertNotIn("<ul", empty_html)

    def test_item_rico_preserva_ids_e_hooks_do_menu_de_evento(self):
        oficio_html = self._render(
            '{% cotton ui.lists.itinerary :items="items" '
            'item_extra_class="itinerary__leg--documento" '
            'item_template="eventos/partials/_itinerary_item.html" '
            'item_kind="oficio" :item_context="card" only / %}',
            {
                "card": {"pk": 17, "menus_url": "/eventos/17/menus/"},
                "items": [
                    {
                        "numero": "OF-42",
                        "oficio_pk": 9,
                        "protocolo": "123",
                        "data_evento_display": "10/08/2026",
                        "destino_display": "Curitiba",
                        "meta_display": "123 · 10/08/2026 · Curitiba",
                    }
                ],
            },
        )

        documentos_html = self._render(
            '{% cotton ui.lists.itinerary :items="items" '
            'item_extra_class="itinerary__leg--documento" '
            'item_template="eventos/partials/_itinerary_item.html" '
            'item_kind="documento" :item_context="card" only / %}',
            {
                "card": {"pk": 17, "menus_url": "/eventos/17/menus/"},
                "items": [
                    {
                        "title": "Plano",
                        "kind": "PT",
                        "meta": "A",
                        "detail": "B",
                        "meta_display": "A · B",
                    },
                    {
                        "title": "Convite",
                        "kind": "Anexo",
                        "meta": "",
                        "detail": "",
                        "meta_display": "",
                    },
                ],
            },
        )

        self.assertIn("itinerary__leg itinerary__leg--documento", oficio_html)
        self.assertIn('aria-controls="evento-oficio-menu-17-9"', oficio_html)
        self.assertIn('data-overlay-target="evento-oficio-menu-17-9"', oficio_html)
        self.assertIn('data-overlay-src="/eventos/17/menus/"', oficio_html)
        self.assertIn("123 · 10/08/2026 · Curitiba", oficio_html)
        self.assertIn('aria-controls="evento-documento-menu-17-1"', documentos_html)
        self.assertIn('aria-controls="evento-documento-menu-17-2"', documentos_html)
        self.assertIn("A · B", documentos_html)

    def test_cinco_apps_consumem_o_componente_sem_reimplementar_lista(self):
        templates_root = ROOT / "templates"
        for relative in CONSUMERS:
            source = (templates_root / relative).read_text(encoding="utf-8")
            self.assertTrue(
                "<c-ui.lists.itinerary" in source
                or 'include "cotton/ui/lists/itinerary.html"' in source,
                relative,
            )
            get_template(relative)

        raw = []
        for path in templates_root.rglob("*.html"):
            if "cotton" in path.relative_to(templates_root).parts:
                continue
            source = path.read_text(encoding="utf-8")
            if '<ul class="itinerary' in source or '<li class="itinerary__leg' in source:
                raw.append(str(path.relative_to(templates_root)))
        self.assertEqual(raw, [])
