from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
LIST_TEMPLATES = (
    "templates/oficios/index.html",
    "templates/eventos/index.html",
    "templates/roteiros/index.html",
    "templates/prestacoes_contas/index.html",
    "templates/termos/index.html",
    "templates/planos_trabalho/index.html",
    "templates/ordens_servico/index.html",
)


class EntityCardStylesTests(SimpleTestCase):
    def test_listagens_de_cards_carregam_folha_compartilhada(self):
        for relative_path in LIST_TEMPLATES:
            with self.subTest(template=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("css/lists/entity-cards.css", source)

    def test_somente_lista_de_oficios_carrega_css_do_wizard(self):
        for relative_path in LIST_TEMPLATES:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            if relative_path == "templates/oficios/index.html":
                self.assertIn("css/pages/oficios.css", source)
            else:
                with self.subTest(template=relative_path):
                    self.assertNotIn("css/pages/oficios.css", source)

    def test_seletores_base_tem_dono_unico(self):
        shared = (ROOT / "static/css/lists/entity-cards.css").read_text(encoding="utf-8")
        wizard = (ROOT / "static/css/pages/oficios.css").read_text(encoding="utf-8")

        for selector in (".record-card {", ".person-list {", ".fact-grid {"):
            with self.subTest(selector=selector):
                self.assertIn(selector, shared)
                self.assertNotIn(selector, wizard)
