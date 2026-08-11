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

    def test_modificador_de_roteiro_nao_exige_folha_legada(self):
        shared = (ROOT / "static/css/lists/entity-cards.css").read_text(encoding="utf-8")

        self.assertIn(
            ".record-card--roteiro .record-card__info-value--rota",
            shared,
        )
        self.assertIn(
            ".record-card--roteiro .fact-block__value--strong--fit",
            shared,
        )
        self.assertFalse((ROOT / "static/css/pages/roteiros-list.css").exists())

        imports_legados = []
        for template in (ROOT / "templates").rglob("*.html"):
            if "css/pages/roteiros-list.css" in template.read_text(encoding="utf-8"):
                imports_legados.append(str(template.relative_to(ROOT)))
        self.assertEqual(imports_legados, [])

    def test_presenters_nao_calculam_classe_sem_consumidor(self):
        for relative_path in (
            "oficios/presenters.py",
            "roteiros/presenters.py",
        ):
            with self.subTest(module=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("faixa_lateral_class", source)
