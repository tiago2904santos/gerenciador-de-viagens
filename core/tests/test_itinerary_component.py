from pathlib import Path

from django.conf import settings
from django.template import Context, Template
from django.template.loader import get_template
from django.test import SimpleTestCase


ROOT = Path(settings.BASE_DIR)
CONSUMERS = (
    "oficios/partials/oficio_list_card.html",
    "oficios/partials/documentos/_route_summary_grid.html",
)


class ItineraryComponentTests(SimpleTestCase):
    def _render(self, legs) -> str:
        source = '{% load cotton %}{% cotton v2.itinerary :legs="legs" only / %}'
        return Template(source).render(Context({"legs": legs}))

    def test_renderiza_trechos_com_periodo_no_modelo_v2(self):
        html = self._render(
            [
                {
                    "rota": "Curitiba → Londrina",
                    "saida": "10/08 08:00",
                    "chegada": "10/08 14:00",
                },
                {"rota": "Londrina → Curitiba", "saida": "", "chegada": ""},
            ]
        )

        self.assertIn('class="route-legs"', html)
        self.assertEqual(html.count('class="route-legs__leg"'), 2)
        self.assertIn("Curitiba → Londrina", html)
        self.assertIn("10/08 08:00 → 10/08 14:00", " ".join(html.split()))
        self.assertEqual(html.count('class="route-legs__time"'), 1)

    def test_sem_trechos_nao_renderiza_lista_vazia(self):
        self.assertNotIn("<ul", self._render([]))

    def test_consumidores_de_producao_usam_o_itinerario_v2(self):
        templates_root = ROOT / "templates"
        for relative in CONSUMERS:
            source = (templates_root / relative).read_text(encoding="utf-8")
            self.assertIn("<c-v2.itinerary", source, relative)
            get_template(relative)

        raw = []
        for path in templates_root.rglob("*.html"):
            relative_parts = path.relative_to(templates_root).parts
            if "cotton" in relative_parts:
                continue
            source = path.read_text(encoding="utf-8")
            if '<ul class="route-legs' in source or '<li class="route-legs__leg' in source:
                raw.append(str(path.relative_to(templates_root)))
        self.assertEqual(raw, [])
