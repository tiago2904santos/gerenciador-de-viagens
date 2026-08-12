import re
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

    def test_listagens_nao_carregam_css_do_wizard_de_oficios(self):
        for relative_path in LIST_TEMPLATES:
            with self.subTest(template=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("css/pages/oficios.css", source)

    def test_listagens_nao_reintroduzem_folhas_sem_regra_casada(self):
        expected_absent = {
            "templates/eventos/index.html": "css/pages/eventos-list.css",
            "templates/oficios/index.html": "css/pages/oficios-documentos-inline.css",
        }
        for relative_path, stylesheet in expected_absent.items():
            with self.subTest(template=relative_path, stylesheet=stylesheet):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn(stylesheet, source)

    def test_total_de_imports_css_em_templates_so_pode_cair(self):
        imports = 0
        pattern = re.compile(r"<link[^>]+static 'css/")
        for template in (ROOT / "templates").rglob("*.html"):
            imports += len(pattern.findall(template.read_text(encoding="utf-8")))
        self.assertLessEqual(imports, 82)

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
