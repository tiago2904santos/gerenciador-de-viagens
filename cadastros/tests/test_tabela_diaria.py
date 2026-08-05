"""Tabela de diárias com vigência (N-01) — a regra de dinheiro do sistema.

Estes testes existem antes da tela porque é aqui que o erro custa caro: um
centavo errado aqui vira valor errado em documento assinado.

Duas garantias centrais:

* **derivação** — 15% e 30% saem do valor de 24h por uma regra única
  (`ROUND_HALF_UP`), e não podem ser digitados;
* **vigência** — mudar a tabela hoje não altera o que valia ontem.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.db import transaction
from django.test import TestCase

from cadastros.models import TabelaDiaria


class DerivacaoTests(TestCase):
    def test_percentuais_sao_derivados_do_valor_de_24h(self):
        tabela = TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_INTERIOR,
            vigencia_inicio=date(2026, 1, 1),
            valor_24h=Decimal("290.55"),
        )

        self.assertEqual(tabela.valor_15, Decimal("43.58"))
        self.assertEqual(tabela.valor_30, Decimal("87.17"))

    def test_valor_digitado_nos_percentuais_e_ignorado(self):
        """Os campos são derivados: o que o operador mandar neles não vale."""
        tabela = TabelaDiaria(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio=date(2026, 1, 1),
            valor_24h=Decimal("371.26"),
        )
        tabela.valor_15 = Decimal("1.00")
        tabela.valor_30 = Decimal("2.00")
        tabela.save()

        tabela.refresh_from_db()
        self.assertEqual(tabela.valor_15, Decimal("55.69"))
        self.assertEqual(tabela.valor_30, Decimal("111.38"))

    def test_arredondamento_e_half_up_no_meio_exato(self):
        """0,005 sobe. É o caso de Brasília: 140,436 → 140,44, não 140,43."""
        quinze, trinta = TabelaDiaria.derivar(Decimal("468.12"))

        self.assertEqual(quinze, Decimal("70.22"))
        self.assertEqual(trinta, Decimal("140.44"))

    def test_alterar_o_valor_de_24h_recalcula_os_percentuais(self):
        tabela = TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_INTERIOR,
            vigencia_inicio=date(2026, 1, 1),
            valor_24h=Decimal("100.00"),
        )
        self.assertEqual(tabela.valor_15, Decimal("15.00"))

        tabela.valor_24h = Decimal("200.00")
        tabela.save()

        tabela.refresh_from_db()
        self.assertEqual(tabela.valor_15, Decimal("30.00"))
        self.assertEqual(tabela.valor_30, Decimal("60.00"))


class VigenciaTests(TestCase):
    def setUp(self):
        # A migração semeia 2000-01-01; estes testes usam datas próprias.
        TabelaDiaria.objects.all().delete()

    def criar(self, valor, inicio, faixa=TabelaDiaria.FAIXA_INTERIOR):
        return TabelaDiaria.objects.create(
            faixa=faixa, vigencia_inicio=inicio, valor_24h=Decimal(valor)
        )

    def test_vigente_em_devolve_a_tabela_que_ja_comecou_mais_recente(self):
        self.criar("100.00", date(2026, 1, 1))
        nova = self.criar("120.00", date(2026, 6, 1))

        vigente = TabelaDiaria.vigente_em(TabelaDiaria.FAIXA_INTERIOR, date(2026, 7, 15))

        self.assertEqual(vigente, nova)
        self.assertEqual(vigente.valor_24h, Decimal("120.00"))

    def test_data_anterior_a_nova_vigencia_continua_na_tabela_antiga(self):
        antiga = self.criar("100.00", date(2026, 1, 1))
        self.criar("120.00", date(2026, 6, 1))

        vigente = TabelaDiaria.vigente_em(TabelaDiaria.FAIXA_INTERIOR, date(2026, 5, 31))

        self.assertEqual(vigente, antiga)
        self.assertEqual(vigente.valor_24h, Decimal("100.00"))

    def test_vigencia_vale_a_partir_do_proprio_dia(self):
        nova = self.criar("120.00", date(2026, 6, 1))

        self.assertEqual(
            TabelaDiaria.vigente_em(TabelaDiaria.FAIXA_INTERIOR, date(2026, 6, 1)), nova
        )

    def test_sem_vigencia_iniciada_devolve_none_em_vez_de_valor_padrao(self):
        """Falhar é melhor que cobrar com valor inventado."""
        self.criar("100.00", date(2026, 6, 1))

        self.assertIsNone(
            TabelaDiaria.vigente_em(TabelaDiaria.FAIXA_INTERIOR, date(2026, 5, 31))
        )

    def test_faixas_sao_independentes(self):
        interior = self.criar("100.00", date(2026, 1, 1), TabelaDiaria.FAIXA_INTERIOR)
        self.criar("300.00", date(2026, 6, 1), TabelaDiaria.FAIXA_CAPITAL)

        vigente = TabelaDiaria.vigente_em(TabelaDiaria.FAIXA_INTERIOR, date(2026, 7, 1))

        self.assertEqual(vigente, interior)


class ConstraintTests(TestCase):
    def setUp(self):
        TabelaDiaria.objects.all().delete()

    def test_nao_permite_duas_vigencias_da_mesma_faixa_no_mesmo_dia(self):
        TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_INTERIOR,
            vigencia_inicio=date(2026, 1, 1),
            valor_24h=Decimal("100.00"),
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            TabelaDiaria.objects.create(
                faixa=TabelaDiaria.FAIXA_INTERIOR,
                vigencia_inicio=date(2026, 1, 1),
                valor_24h=Decimal("200.00"),
            )

    def test_valor_zero_ou_negativo_e_recusado_pelo_banco(self):
        for invalido in (Decimal("0.00"), Decimal("-1.00")):
            with self.subTest(valor=invalido):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    TabelaDiaria.objects.create(
                        faixa=TabelaDiaria.FAIXA_CAPITAL,
                        vigencia_inicio=date(2026, 1, 1),
                        valor_24h=invalido,
                    )


class SementeDaMigracaoTests(TestCase):
    """A migração precisa reproduzir o comportamento anterior, não mudá-lo."""

    def test_as_tres_faixas_foram_semeadas_com_os_valores_que_estavam_no_codigo(self):
        esperado = {
            TabelaDiaria.FAIXA_INTERIOR: Decimal("290.55"),
            TabelaDiaria.FAIXA_CAPITAL: Decimal("371.26"),
            TabelaDiaria.FAIXA_BRASILIA: Decimal("468.12"),
        }

        for faixa, valor in esperado.items():
            with self.subTest(faixa=faixa):
                tabela = TabelaDiaria.vigente_em(faixa, date(2026, 7, 28))
                self.assertIsNotNone(tabela, f"faixa {faixa} sem vigência semeada")
                self.assertEqual(tabela.valor_24h, valor)

    def test_a_semente_cobre_qualquer_roteiro_existente(self):
        """Início bem anterior: nenhum roteiro fica sem tabela e nada recalcula."""
        tabela = TabelaDiaria.vigente_em(TabelaDiaria.FAIXA_INTERIOR, date(2020, 1, 1))

        self.assertIsNotNone(tabela)

    def test_brasilia_30_passa_a_seguir_a_regra_unica(self):
        """Único valor que muda: 140,43 → 140,44, por adoção do arredondamento."""
        tabela = TabelaDiaria.vigente_em(TabelaDiaria.FAIXA_BRASILIA, date(2026, 7, 28))

        self.assertEqual(tabela.valor_30, Decimal("140.44"))
