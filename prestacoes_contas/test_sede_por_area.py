"""BE-06 — a cidade-sede do relatório técnico é a da área do documento.

`_sede()` lia `ConfiguracaoSistema.objects.first()`: a configuração de qualquer
área, sem recorte. Era o único ponto de produção que fazia isso — todo o resto
resolve por `get_singleton()`/`get_for_area()`.

O sintoma aparecia exatamente na área recém-criada, a que ainda não preencheu a
configuração: o relatório técnico saía com o município de outra unidade, sem erro
visível em lugar nenhum.
"""

from __future__ import annotations

from django.test import TestCase

from cadastros.models import ConfiguracaoSistema
from prestacoes_contas.services import _sede
from usuarios.models import AreaTrabalho


class SedeDoRelatorioTecnicoTests(TestCase):
    def setUp(self):
        self.area_antiga = AreaTrabalho.objects.create(nome="Área Antiga", sigla="ANTIGA")
        self.area_nova = AreaTrabalho.objects.create(nome="Área Nova", sigla="NOVA")

        # A área antiga está configurada; a nova ainda não preencheu nada.
        configuracao = ConfiguracaoSistema.get_for_area(self.area_antiga)
        configuracao.cidade_endereco = "Curitiba"
        configuracao.save(update_fields=["cidade_endereco"])

    def test_usa_a_cidade_da_propria_area(self):
        configuracao = ConfiguracaoSistema.get_for_area(self.area_nova)
        configuracao.cidade_endereco = "Maringá"
        configuracao.save(update_fields=["cidade_endereco"])

        # `ConfiguracaoSistema.save()` normaliza para caixa alta — o documento sai assim.
        self.assertEqual(_sede(self.area_nova), "MARINGÁ")

    def test_area_sem_configuracao_sai_vazia_em_vez_de_pegar_a_de_outra(self):
        """Campo em branco é problema; município errado num documento oficial é pior."""
        # O que a implementação antiga fazia, deixado à vista: `objects.first()` pega
        # a configuração de QUALQUER área — aqui, a da área antiga, já preenchida.
        primeira_de_qualquer_area = ConfiguracaoSistema.objects.first()
        self.assertEqual(primeira_de_qualquer_area.cidade_endereco, "CURITIBA")

        # E o que a corrigida faz para a área que ainda não configurou nada.
        self.assertEqual(_sede(self.area_nova), "")

    def test_sem_area_sai_vazio(self):
        self.assertEqual(_sede(None), "")
