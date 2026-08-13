"""DB-13 - caracteriza e prova a composicao oficial persistida das diarias."""

from datetime import datetime
from decimal import Decimal
from importlib import import_module
from unittest.mock import patch

from django.apps import apps
from django.db import models
from django.db.models import Q
from django.db.models import Sum
from django.test import TestCase

from cadastros.models import TabelaDiaria
from core.testing import area_de_teste
from roteiros.models import Roteiro
from roteiros.models import RoteiroDiariaComponente
from roteiros.services.diarias import PeriodMarker
from roteiros.services.diarias import calculate_periodized_diarias
from roteiros.services.editor_persistence import persistir_diarias_roteiro


class ComposicaoDiariasCaracterizacaoTests(TestCase):
    def _resultado_oficial(self):
        return calculate_periodized_diarias(
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

    def _roteiro(self):
        return Roteiro.objects.create(
            area=area_de_teste(),
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
        )

    def test_demonstrativo_oficial_persistido_mantem_texto_e_total(self):
        """Curitiba-SP-Abatia-Curitiba continua em R$ 773,19."""
        resultado = self._resultado_oficial()
        roteiro = self._roteiro()

        persistir_diarias_roteiro(roteiro, resultado)
        roteiro.refresh_from_db()

        self.assertEqual(resultado["totais"]["total_valor_decimal"], Decimal("773.19"))
        self.assertEqual(roteiro.quantidade_diarias, "2 x 100% + 1 x 30%")
        self.assertEqual(roteiro.valor_diarias, Decimal("773.19"))
        self.assertEqual(set(resultado), {"periodos", "totais"})
        self.assertEqual(
            [
                (item["tipo"], item["n_diarias"], item["percentual_adicional"])
                for item in resultado["periodos"]
            ],
            [("CAPITAL", 1, 30), ("INTERIOR", 1, 0)],
        )

    def test_persiste_componentes_reconciliaveis_com_a_tabela_usada(self):
        roteiro = self._roteiro()

        persistir_diarias_roteiro(roteiro, self._resultado_oficial())

        componentes = list(roteiro.componentes_diarias.select_related("tabela_diaria"))
        self.assertEqual(
            [
                (c.faixa, c.percentual, c.quantidade, c.valor_unitario, c.subtotal)
                for c in componentes
            ],
            [
                ("CAPITAL", 100, 1, Decimal("371.26"), Decimal("371.26")),
                ("CAPITAL", 30, 1, Decimal("111.38"), Decimal("111.38")),
                ("INTERIOR", 100, 1, Decimal("290.55"), Decimal("290.55")),
            ],
        )
        self.assertTrue(all(c.tabela_diaria_id for c in componentes))
        self.assertEqual(
            sum((c.subtotal for c in componentes), Decimal("0.00")),
            roteiro.valor_diarias,
        )

    def test_consulta_estruturada_conta_percentuais_sem_parsear_texto(self):
        roteiro = self._roteiro()
        persistir_diarias_roteiro(roteiro, self._resultado_oficial())

        agregado = RoteiroDiariaComponente.objects.aggregate(
            trinta=Sum("quantidade", filter=Q(percentual=30)),
            integrais=Sum("quantidade", filter=Q(percentual=100)),
        )

        self.assertEqual(agregado, {"trinta": 1, "integrais": 2})

    def test_snapshot_nao_muda_e_tarifa_usada_nao_pode_ser_apagada(self):
        roteiro = self._roteiro()
        persistir_diarias_roteiro(roteiro, self._resultado_oficial())
        componente = roteiro.componentes_diarias.get(faixa="CAPITAL", percentual=30)
        tabela = componente.tabela_diaria

        TabelaDiaria.objects.filter(pk=tabela.pk).update(valor_30=Decimal("999.99"))
        componente.refresh_from_db()

        self.assertEqual(componente.valor_unitario, Decimal("111.38"))
        self.assertIs(
            RoteiroDiariaComponente._meta.get_field("tabela_diaria").remote_field.on_delete,
            models.PROTECT,
        )

    def test_recalculo_substitui_componentes_sem_deixar_linhas_antigas(self):
        roteiro = self._roteiro()
        resultado = self._resultado_oficial()
        persistir_diarias_roteiro(roteiro, resultado)
        ids_anteriores = set(roteiro.componentes_diarias.values_list("pk", flat=True))
        resultado.componentes = resultado.componentes[:1]
        resultado["totais"]["total_diarias"] = "1 x 100%"
        resultado["totais"]["total_valor_decimal"] = Decimal("371.26")

        persistir_diarias_roteiro(roteiro, resultado)

        atuais = list(roteiro.componentes_diarias.all())
        self.assertEqual(len(atuais), 1)
        self.assertNotIn(atuais[0].pk, ids_anteriores)

    def test_falha_ao_substituir_componentes_reverte_tambem_o_total(self):
        roteiro = self._roteiro()
        resultado = self._resultado_oficial()
        persistir_diarias_roteiro(roteiro, resultado)
        ids_anteriores = list(roteiro.componentes_diarias.values_list("pk", flat=True))
        resultado["totais"]["total_valor_decimal"] = Decimal("1.00")

        with (
            patch.object(
                RoteiroDiariaComponente.objects,
                "bulk_create",
                side_effect=RuntimeError("falha"),
            ),
            self.assertRaises(RuntimeError),
        ):
            persistir_diarias_roteiro(roteiro, resultado)

        roteiro.refresh_from_db()
        self.assertEqual(roteiro.valor_diarias, Decimal("773.19"))
        self.assertEqual(
            list(roteiro.componentes_diarias.values_list("pk", flat=True)),
            ids_anteriores,
        )


class ComposicaoDiariasBackfillTests(TestCase):
    def test_backfill_extrai_so_percentuais_inequivocos_sem_inventar_valores(self):
        estruturado = Roteiro.objects.create(
            area=area_de_teste(), quantidade_diarias="2 x 100% + 1 x 30%"
        )
        ambiguo = Roteiro.objects.create(
            area=area_de_teste(), quantidade_diarias="2,5", valor_diarias=Decimal("9.99")
        )
        migracao = import_module("roteiros.migrations.0016_roteirodiariacomponente")

        migracao.estruturar_resumos_legados(apps, None)

        self.assertEqual(
            list(
                estruturado.componentes_diarias.values_list(
                    "origem", "percentual", "quantidade", "tabela_diaria_id",
                    "valor_unitario", "subtotal",
                )
            ),
            [
                ("LEGADO", 100, 2, None, None, None),
                ("LEGADO", 30, 1, None, None, None),
            ],
        )
        self.assertFalse(ambiguo.componentes_diarias.exists())
        ambiguo.refresh_from_db()
        self.assertEqual(ambiguo.valor_diarias, Decimal("9.99"))
