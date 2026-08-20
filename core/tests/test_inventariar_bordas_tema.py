from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from scripts.inventariar_bordas_tema import (
    normalize_selector,
    parse_viewports,
    rule_key,
    rule_removes_border,
    split_selectors,
)


class InventarioBordasTemaTests(SimpleTestCase):
    def test_parseia_as_tres_larguras_da_regua(self):
        self.assertEqual(parse_viewports("1440,800,500"), (1440, 800, 500))

    def test_identidade_da_regra_nao_depende_da_rota(self):
        base = {
            "selector": 'html[data-theme="dark"] .card',
            "declarations": [["border", "0px", ""]],
            "cssText": "border: 0px;",
        }
        outra_rota = {**base, "affected": 12, "href": "shell.bundle.css"}
        self.assertEqual(rule_key(base), rule_key(outra_rota))

    def test_separa_lista_sem_quebrar_is(self):
        self.assertEqual(
            split_selectors('html[data-theme="dark"] :is(.a, .b), .c'),
            ['html[data-theme="dark"] :is(.a, .b)', ".c"],
        )

    def test_normaliza_espaco_sem_mudar_a_estrutura(self):
        self.assertEqual(normalize_selector(".a  >  :is(.b, .c)"), ".a>:is(.b,.c)")

    def test_classifica_remocao_de_um_lado_da_borda(self):
        item = {
            "examples": [
                {
                    "light": ["1px", "0px", "0px", "0px", "solid", "none", "none", "none"],
                    "dark": ["0px", "0px", "0px", "0px", "none", "none", "none", "none"],
                }
            ]
        }
        self.assertTrue(rule_removes_border(item))

    def test_nao_confunde_borda_redesenhada_com_remocao(self):
        item = {
            "examples": [
                {
                    "light": ["3px", "1px", "1px", "1px", "solid", "solid", "solid", "solid"],
                    "dark": ["1px", "1px", "1px", "1px", "solid", "solid", "solid", "solid"],
                }
            ]
        }
        self.assertFalse(rule_removes_border(item))


class SuperficiesClarasContratoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        root = Path(settings.BASE_DIR)
        cls.tokens = (root / "static/css/base/tokens.css").read_text(encoding="utf-8")
        # A folha vigiada aqui foi DISSOLVIDA em 2026-08-20. As cinco regras que
        # este teste proibia (`search-picker--vehicle`, `form-card__footer`,
        # `date-picker__footer-action`, `roteiro-trecho-card__leg`) nao voltaram
        # para lugar nenhum: das 80 regras das duas folhas de tema, 63 foram
        # apagadas por nao pintarem nada, e as 17 herdeiras estao nos arquivos
        # abaixo. A proibicao passa a valer sobre elas.
        cls.components = "
".join(
            (root / caminho).read_text(encoding="utf-8")
            for caminho in (
                "static/css/base/base.css",
                "static/css/v2/module-card.css",
                "static/css/v2/select.css",
            )
        )

    def test_tema_claro_tem_tres_niveis_de_superficie(self):
        self.assertIn("--color-surface: #ffffff;", self.tokens)
        self.assertIn("--color-surface-muted: #f7fbff;", self.tokens)
        self.assertIn("--color-surface-soft: #e3eaf2;", self.tokens)

    def test_componentes_redesenhados_nao_ficam_predicados_no_escuro(self):
        for pattern in (
            r'data-theme="dark"[^\{]{0,160}\.search-picker--vehicle',
            r'data-theme="dark"[^\{]{0,160}\.search-picker--people\.search-picker--roster',
            r'data-theme="dark"[^\{]{0,160}\.form-card__footer',
            r'data-theme="dark"[^\{]{0,160}\.date-picker__footer \.date-picker__footer-action',
            r'data-theme="dark"[^\{]{0,160}\.roteiro-trecho-card__leg',
        ):
            with self.subTest(pattern=pattern):
                self.assertNotRegex(self.components, pattern)

        # `lists/list-header.css` foi apagada em 2026-08-20 (nenhum template
        # emitia `.list-header`), e com ela a faixa do wizard que este trecho
        # vigiava. A proibição continua valendo para as folhas vivas, medidas
        # acima.
        self.assertFalse(
            (Path(settings.BASE_DIR) / "static/css/lists").exists(),
            "a pasta `lists/` voltou — ela morreu com a barra de lista antiga",
        )
