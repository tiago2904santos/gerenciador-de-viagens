"""O cálculo de diárias passa a ler a tabela vigente (N-01).

Os testes de `test_diarias_service.py` provam que a **conta** não mudou. Estes
provam a garantia nova: o valor vem do banco, e mudar a tabela hoje não altera
o que valia ontem.

É a diferença que motivou o `N-01`. Antes, alterar um valor exigia deploy **e**
recalculava todo o histórico, porque não havia vigência.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase

from cadastros.models import TabelaDiaria
from roteiros.services.diarias import (
    PeriodMarker,
    calculate_periodized_diarias,
    tabela_vigente_em,
)


def _marker(saida: datetime, cidade="CURITIBA", uf="PR"):
    return PeriodMarker(saida=saida, destino_cidade=cidade, destino_uf=uf)


def _totais(markers, chegada_final):
    return calculate_periodized_diarias(
        markers, chegada_final, quantidade_servidores=1,
        sede_cidade="CURITIBA", sede_uf="PR",
    )["totais"]["total_valor_decimal"]


class TabelaVigenteEmTests(TestCase):
    def test_resolve_as_tres_faixas_no_formato_do_calculo(self):
        tabela = tabela_vigente_em(date(2026, 7, 28))

        self.assertEqual(set(tabela), {"INTERIOR", "CAPITAL", "BRASILIA"})
        for faixa, valores in tabela.items():
            with self.subTest(faixa=faixa):
                self.assertEqual(set(valores), {"24h", "15", "30"})

    def test_devolve_os_valores_semeados_pela_migracao(self):
        tabela = tabela_vigente_em(date(2026, 7, 28))

        self.assertEqual(tabela["CAPITAL"]["24h"], Decimal("371.26"))
        self.assertEqual(tabela["CAPITAL"]["15"], Decimal("55.69"))
        self.assertEqual(tabela["CAPITAL"]["30"], Decimal("111.38"))

    def test_data_posterior_a_uma_vigencia_nova_usa_a_nova(self):
        TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio=date(2026, 8, 1),
            valor_24h=Decimal("400.00"),
        )

        antes = tabela_vigente_em(date(2026, 7, 31))
        depois = tabela_vigente_em(date(2026, 8, 1))

        self.assertEqual(antes["CAPITAL"]["24h"], Decimal("371.26"))
        self.assertEqual(depois["CAPITAL"]["24h"], Decimal("400.00"))


class CalculoUsaVigenciaTests(TestCase):
    """O ponto do N-01: mudar a tabela não reescreve o passado."""

    def test_roteiro_novo_usa_a_tabela_nova(self):
        TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio=date(2026, 8, 1),
            valor_24h=Decimal("400.00"),
        )

        total = _totais(
            [_marker(datetime(2026, 8, 10, 8, 0))], datetime(2026, 8, 12, 20, 0)
        )

        # Dois pernoites + complemento de 30%, todos pela tabela nova.
        nova = tabela_vigente_em(date(2026, 8, 10))["CAPITAL"]
        self.assertEqual(total, nova["24h"] * 2 + nova["30"])
        self.assertEqual(total, Decimal("920.00"))

    def test_roteiro_anterior_a_mudanca_mantem_o_valor_antigo(self):
        """A garantia central: cadastrar tabela nova hoje não altera ontem."""
        total_antes = _totais(
            [_marker(datetime(2026, 7, 10, 8, 0))], datetime(2026, 7, 12, 20, 0)
        )

        TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio=date(2026, 8, 1),
            valor_24h=Decimal("999.00"),
        )

        recalculado = _totais(
            [_marker(datetime(2026, 7, 10, 8, 0))], datetime(2026, 7, 12, 20, 0)
        )

        self.assertEqual(recalculado, total_antes)

    def test_a_vigencia_do_roteiro_e_decidida_pela_saida_mais_antiga(self):
        """Roteiro que atravessa a virada cobra uma tabela só, a da saída.

        Resolver por trecho faria o mesmo roteiro cobrar dois valores — o tipo
        de detalhe que ninguém confere e que aparece como divergência de
        centavos meses depois.
        """
        TabelaDiaria.objects.create(
            faixa=TabelaDiaria.FAIXA_CAPITAL,
            vigencia_inicio=date(2026, 8, 1),
            valor_24h=Decimal("999.00"),
        )

        # Saída em 30/07, antes da virada: a conta inteira usa a tabela antiga.
        atravessa = _totais(
            [_marker(datetime(2026, 7, 30, 8, 0))], datetime(2026, 7, 31, 20, 0)
        )

        antiga = tabela_vigente_em(date(2026, 7, 30))["CAPITAL"]
        self.assertEqual(atravessa, antiga["24h"] + antiga["30"])
        self.assertEqual(atravessa, Decimal("482.64"))

    def test_sem_vigencia_para_a_data_cai_na_tabela_historica(self):
        """Dado ausente não derruba a calculadora — o operador precisa de saída."""
        TabelaDiaria.objects.all().delete()

        tabela = tabela_vigente_em(date(2026, 7, 28))

        self.assertEqual(tabela["CAPITAL"]["24h"], Decimal("371.26"))
