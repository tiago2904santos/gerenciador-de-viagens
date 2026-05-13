from decimal import Decimal

from django.test import SimpleTestCase

from roteiros.presenters import _roteiro_card_layout, _trechos_visiveis
from roteiros.services.valor_extenso import valor_por_extenso_ptbr


class ValorExtensoPtBrTests(SimpleTestCase):
    def test_valores_monetarios_por_extenso(self):
        casos = {
            "0,00": "zero reais",
            "1,00": "um real",
            "2,00": "dois reais",
            "1,01": "um real e um centavo",
            "624.68": "seiscentos e vinte e quatro reais e sessenta e oito centavos",
            Decimal("174.34"): "cento e setenta e quatro reais e trinta e quatro centavos",
            Decimal("624.68"): "seiscentos e vinte e quatro reais e sessenta e oito centavos",
        }
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(valor_por_extenso_ptbr(valor), esperado)


class RoteiroCardLayoutPresenterTests(SimpleTestCase):
    def test_layout_por_quantidade_de_trechos(self):
        self.assertEqual(_roteiro_card_layout(1), "compact")
        self.assertEqual(_roteiro_card_layout(2), "compact")
        self.assertEqual(_roteiro_card_layout(3), "expanded-3")
        self.assertEqual(_roteiro_card_layout(4), "diarias-dashboard")
        self.assertEqual(_roteiro_card_layout(5), "diarias-dashboard")

    def test_trechos_visiveis_resume_mais_de_quatro_trechos(self):
        payload = [
            {"destino": "PONTA GROSSA/PR"},
            {"destino": "MARINGÁ/PR"},
            {"destino": "LONDRINA/PR"},
            {"destino": "CURITIBA/PR"},
            {"destino": "CASCAVEL/PR"},
        ]

        visiveis, resumo = _trechos_visiveis(payload)

        self.assertEqual(len(visiveis), 3)
        self.assertEqual(resumo["count"], 2)
        self.assertEqual(resumo["texto"], "CURITIBA/PR, CASCAVEL/PR")
