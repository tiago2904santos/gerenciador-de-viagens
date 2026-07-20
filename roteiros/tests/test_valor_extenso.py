from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from cadastros.models import Cidade, Estado
from roteiros.models import Roteiro, RoteiroTrecho
from roteiros.presenters import (
    _roteiro_card_layout,
    _trechos_visiveis,
    apresentar_roteiro_card,
)
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

    def test_trechos_visiveis_mantem_ate_quatro_completos(self):
        payload = [{"destino": f"CIDADE{i}/PR"} for i in range(4)]
        visiveis, resumo = _trechos_visiveis(payload)
        self.assertEqual(len(visiveis), 4)
        self.assertIsNone(resumo)


class ApresentarRoteiroCardTrechosTests(TestCase):
    def setUp(self):
        self.estado, _ = Estado.objects.get_or_create(sigla="PR", defaults={"nome": "PARANA"})
        self.cidades = []
        for nome in ("CURITIBA", "LONDRINA", "MARINGA", "CASCAVEL", "PONTA GROSSA", "FOZ"):
            cidade, _ = Cidade.objects.get_or_create(
                nome=nome, estado=self.estado, defaults={"uf": "PR"}
            )
            self.cidades.append(cidade)

    def test_todos_trechos_true_nao_trunca_lista(self):
        roteiro = Roteiro.objects.create(tipo=Roteiro.TIPO_AVULSO)
        for i in range(5):
            RoteiroTrecho.objects.create(
                roteiro=roteiro,
                ordem=i,
                tipo=RoteiroTrecho.TIPO_IDA,
                origem_cidade=self.cidades[i],
                origem_estado=self.estado,
                destino_cidade=self.cidades[i + 1],
                destino_estado=self.estado,
            )

        card_lista = apresentar_roteiro_card(roteiro)
        card_docs = apresentar_roteiro_card(roteiro, todos_trechos=True)

        self.assertEqual(card_lista["trechos_count"], 5)
        self.assertEqual(len(card_lista["trechos"]), 3)
        self.assertIsNotNone(card_lista["trechos_resumo"])

        self.assertEqual(card_docs["trechos_count"], 5)
        self.assertEqual(len(card_docs["trechos"]), 5)
        self.assertIsNone(card_docs["trechos_resumo"])
