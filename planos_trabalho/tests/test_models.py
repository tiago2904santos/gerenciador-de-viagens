from django.test import TestCase
from django.utils import timezone

from cadastros.models import ConfiguracaoSistema

from core.testing import area_de_teste
from planos_trabalho.models import PlanoTrabalho

from .helpers import configurar_sistema
from .helpers import criar_base_geografica


class NumeracaoPlanoTests(TestCase):
    def setUp(self):
        _, self.curitiba, *_ = criar_base_geografica()
        configurar_sistema(self.curitiba)

    def test_numeracao_sequencial_com_contador_da_configuracao(self):
        ano = timezone.localdate().year
        p1 = PlanoTrabalho(area=area_de_teste())
        p1.atribuir_numero()
        p1.save()
        p2 = PlanoTrabalho(area=area_de_teste())
        p2.atribuir_numero()
        p2.save()

        self.assertEqual((p1.numero, p1.ano), (1, ano))
        self.assertEqual((p2.numero, p2.ano), (2, ano))
        config = ConfiguracaoSistema.get_singleton()
        self.assertEqual(config.pt_ultimo_numero, 2)
        self.assertEqual(config.pt_ano, ano)

    def test_numero_formatado_inclui_sufixo(self):
        plano = PlanoTrabalho(area=area_de_teste())
        plano.atribuir_numero()
        plano.save()
        ano = timezone.localdate().year
        self.assertEqual(plano.numero_formatado, f"01/{ano}/ASCOM")

    def test_virada_de_ano_zera_contador(self):
        config = ConfiguracaoSistema.get_singleton()
        config.pt_ano = timezone.localdate().year - 1
        config.pt_ultimo_numero = 42
        config.save()

        plano = PlanoTrabalho(area=area_de_teste())
        plano.atribuir_numero()
        plano.save()

        self.assertEqual(plano.numero, 1)
        self.assertEqual(plano.ano, timezone.localdate().year)

    def test_atribuir_numero_nao_sobrescreve_numero_existente(self):
        plano = PlanoTrabalho(area=area_de_teste(), numero=20, ano=2026, sufixo_numero="ASCOM")
        plano.atribuir_numero()
        self.assertEqual((plano.numero, plano.ano), (20, 2026))
        self.assertEqual(plano.numero_formatado, "20/2026/ASCOM")
