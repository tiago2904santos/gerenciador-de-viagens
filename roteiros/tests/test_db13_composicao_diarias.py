"""DB-13 — caracteriza o dinheiro antes de estruturar sua composição."""

from datetime import datetime
from decimal import Decimal

from django.test import TestCase

from core.testing import area_de_teste
from roteiros.models import Roteiro
from roteiros.services.diarias import PeriodMarker
from roteiros.services.diarias import calculate_periodized_diarias
from roteiros.services.editor_persistence import persistir_diarias_roteiro


class ComposicaoDiariasCaracterizacaoTests(TestCase):
    def test_demonstrativo_oficial_persistido_mantem_texto_e_total(self):
        """Curitiba→São Paulo→Abatiá→Curitiba continua em R$ 773,19."""
        resultado = calculate_periodized_diarias(
            [
                PeriodMarker(
                    saida=datetime(2026, 8, 12, 8, 0),
                    chegada=datetime(2026, 8, 12, 18, 0),
                    destino_cidade="SAO PAULO",
                    destino_uf="SP",
                ),
                PeriodMarker(
                    saida=datetime(2026, 8, 13, 8, 0),
                    chegada=datetime(2026, 8, 13, 18, 0),
                    destino_cidade="ABATIA",
                    destino_uf="PR",
                ),
                PeriodMarker(
                    saida=datetime(2026, 8, 14, 8, 0),
                    chegada=datetime(2026, 8, 14, 18, 0),
                    destino_cidade="CURITIBA",
                    destino_uf="PR",
                ),
            ],
            datetime(2026, 8, 14, 18, 0),
            quantidade_servidores=1,
            sede_cidade="CURITIBA",
            sede_uf="PR",
        )
        roteiro = Roteiro.objects.create(
            area=area_de_teste(),
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
        )

        persistir_diarias_roteiro(roteiro, resultado)
        roteiro.refresh_from_db()

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("773.19"))
        self.assertEqual(roteiro.quantidade_diarias, "2 x 100% + 1 x 30%")
        self.assertEqual(roteiro.valor_diarias, Decimal("773.19"))
        self.assertEqual(
            [(item["tipo"], item["n_diarias"], item["percentual_adicional"])
             for item in resultado["periodos"]],
            [("CAPITAL", 1, 30), ("INTERIOR", 1, 0)],
        )
