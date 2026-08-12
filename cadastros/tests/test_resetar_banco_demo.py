from __future__ import annotations

from django.core.management import call_command
from django.test import TransactionTestCase

from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from cadastros.models import Unidade
from oficios.models import Oficio
from ordens_servico.models import OrdemServico
from ordens_servico.models import OrdemServicoNumeroLacuna
from planos_trabalho.models import PlanoTrabalho
from roteiros.models import Roteiro
from termos.models import TermoAutorizacao
from usuarios.models import AreaTrabalho


class ResetarBancoDemoTests(TransactionTestCase):
    reset_sequences = True

    def test_seed_respeita_area_obrigatoria_e_mantem_cinco_linhas(self):
        call_command("resetar_banco_demo", verbosity=0)

        self.assertEqual(AreaTrabalho.objects.filter(ativa=True).count(), 5)
        for model in (
            ConfiguracaoSistema,
            Unidade,
            Servidor,
            Roteiro,
            Oficio,
            PlanoTrabalho,
            TermoAutorizacao,
            OrdemServico,
            OrdemServicoNumeroLacuna,
        ):
            with self.subTest(model=model._meta.label):
                self.assertEqual(model._base_manager.count(), 5)
                self.assertFalse(model._base_manager.filter(area__isnull=True).exists())
