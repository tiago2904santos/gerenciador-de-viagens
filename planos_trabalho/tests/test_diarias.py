"""Cálculo das diárias reproduzindo os planos reais 20/2026 (Maringá) e 18/2026 (Sarandi)."""

from datetime import date
from datetime import time
from decimal import Decimal

from django.test import TestCase

from cadastros.models import Cargo

from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import PlanoTrabalho
from planos_trabalho.services import atualizar_snapshot_diarias
from planos_trabalho.services import calcular_diarias_plano
from planos_trabalho.services import montar_valor_do_plano_texto
from core.testing import area_de_teste

from .helpers import configurar_sistema
from .helpers import criar_base_geografica
from .helpers import criar_plano_maringa


class DiariasPlanoTests(TestCase):
    def setUp(self):
        _, self.curitiba, self.maringa, self.sarandi = criar_base_geografica()
        configurar_sistema(self.curitiba)

    def test_maringa_4x100_mais_1x15_por_servidor(self):
        plano = criar_plano_maringa(self.maringa, efetivo=6)
        resultado = calcular_diarias_plano(plano)

        self.assertTrue(resultado["ok"], resultado.get("erros"))
        self.assertEqual(resultado["composicao"], "4 x 100% + 1 x 15%")
        self.assertEqual(resultado["valor_unitario"], Decimal("1205.78"))
        self.assertEqual(resultado["valor_total"], Decimal("7234.68"))
        self.assertEqual(resultado["valor_unitario_display"], "1.205,78")
        self.assertEqual(resultado["valor_total_display"], "7.234,68")

    def test_sarandi_5x100_mais_1x30_por_servidor(self):
        plano = PlanoTrabalho.objects.create(area=area_de_teste(), 
            destino_estado=self.sarandi.estado,
            destino_cidade=self.sarandi,
            # 5 pernoites + parcial de 9h (acima de 8h) => 5 x 100% + 1 x 30%
            saida_sede_data=date(2026, 6, 23),
            saida_sede_hora=time(7, 0),
            chegada_sede_data=date(2026, 6, 28),
            chegada_sede_hora=time(16, 0),
        )
        cargo = Cargo.objects.create(area=area_de_teste(), nome="Policial Civil")
        EfetivoPlano.objects.create(plano=plano, cargo=cargo, quantidade=18)

        resultado = calcular_diarias_plano(plano)

        self.assertTrue(resultado["ok"], resultado.get("erros"))
        self.assertEqual(resultado["composicao"], "5 x 100% + 1 x 30%")
        self.assertEqual(resultado["valor_unitario"], Decimal("1539.92"))
        self.assertEqual(resultado["valor_total"], Decimal("27718.56"))

    def test_snapshot_persistido_e_texto_do_valor(self):
        plano = criar_plano_maringa(self.maringa, efetivo=6)
        atualizar_snapshot_diarias(plano)
        plano.refresh_from_db()

        self.assertEqual(plano.diarias_composicao, "4 x 100% + 1 x 15%")
        self.assertEqual(plano.diarias_valor_unitario, Decimal("1205.78"))
        self.assertEqual(plano.diarias_valor_total, Decimal("7234.68"))

        texto = montar_valor_do_plano_texto(plano)
        self.assertIn("Valor total: R$7.234,68", texto)
        self.assertIn("4 x 100% + 1 x 15%", texto)
        self.assertIn("R$1.205,78", texto)
        self.assertIn("sete mil", texto.lower())

    def test_calculo_ao_vivo_com_override_de_efetivo(self):
        plano = criar_plano_maringa(self.maringa, efetivo=6)
        resultado = calcular_diarias_plano(plano, total_efetivo=10)
        self.assertTrue(resultado["ok"], resultado.get("erros"))
        self.assertEqual(resultado["valor_unitario"], Decimal("1205.78"))
        self.assertEqual(resultado["valor_total"], Decimal("12057.80"))

    def test_erros_quando_dados_incompletos(self):
        plano = PlanoTrabalho.objects.create(area=area_de_teste())
        resultado = calcular_diarias_plano(plano)
        self.assertFalse(resultado["ok"])
        self.assertTrue(resultado["erros"])

    def test_chegada_antes_da_saida_retorna_erro(self):
        plano = criar_plano_maringa(self.maringa)
        plano.chegada_sede_data = plano.saida_sede_data
        plano.chegada_sede_hora = time(6, 0)
        resultado = calcular_diarias_plano(plano)
        self.assertFalse(resultado["ok"])
