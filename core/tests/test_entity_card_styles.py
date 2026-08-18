import re
from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]
#: A tupla ESVAZIOU em 2026-08-18. Cada lista migrada para o v2 saía daqui —
#: termos e ordens de serviço (08-15), roteiros (08-17), eventos e prestações
#: (08-18) — e as duas últimas, ofícios e planos de trabalho, foram as que
#: fecharam a conta. O cartão de todas elas agora é `c-v2.record`.
#:
#: O que sobrou deste arquivo é a guarda do sentido contrário: a folha
#: compartilhada MORREU, e o teste existe para que ela não volte por um
#: `<link>` esquecido numa tela nova.
LIST_TEMPLATES = ()


class EntityCardStylesTests(SimpleTestCase):
    def test_a_folha_compartilhada_de_cards_nao_existe_mais(self):
        self.assertFalse((ROOT / "static/css/lists/entity-cards.css").exists())

    def test_nenhum_template_carrega_a_folha_morta(self):
        culpados = []
        for template in (ROOT / "templates").rglob("*.html"):
            if "css/lists/entity-cards.css" in template.read_text(encoding="utf-8"):
                culpados.append(str(template.relative_to(ROOT)))
        self.assertEqual(culpados, [])

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

    def test_folhas_de_lista_legadas_continuam_apagadas(self):
        """As duas folhas de lista do sistema antigo, e nenhum `<link>` para elas.

        `roteiros-list.css` morreu antes; `lists/entity-cards.css` agora. Provar
        a ausência das duas juntas é o que impede a volta silenciosa — um
        `<link>` para folha inexistente não dá erro em dev, e em produção
        derruba o `collectstatic` inteiro.
        """
        for folha in ("static/css/pages/roteiros-list.css", "static/css/lists/entity-cards.css"):
            with self.subTest(folha=folha):
                self.assertFalse((ROOT / folha).exists())

        imports_legados = []
        for template in (ROOT / "templates").rglob("*.html"):
            texto = template.read_text(encoding="utf-8")
            for folha in ("css/pages/roteiros-list.css", "css/lists/entity-cards.css"):
                if f"static '{folha}'" in texto or f'static "{folha}"' in texto:
                    imports_legados.append(f"{template.relative_to(ROOT)}: {folha}")
        self.assertEqual(imports_legados, [])

    def test_presenters_nao_calculam_classe_sem_consumidor(self):
        for relative_path in (
            "oficios/presenters.py",
            "roteiros/presenters.py",
        ):
            with self.subTest(module=relative_path):
                source = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("faixa_lateral_class", source)
