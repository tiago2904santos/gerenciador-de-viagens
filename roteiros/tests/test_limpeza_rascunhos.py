"""DB-03 — a limpeza de rascunhos órfãos apagava rascunho alheio.

`roteiros/services/roteiro_editor.py:_limpar_rascunhos_vazios` roda a cada
`criar_roteiro` e a cada edição. Ela existe para varrer sobra de corrida do
autosave: roteiro sem sede, sem destino, sem trecho e sem saída.

Só que ela varria **o banco inteiro**:

    Roteiro.objects.filter(...).exclude(pk=roteiro_atual_pk).delete()

Sem recorte de área — que é o defeito catalogado — e **sem limite de idade**,
que é pior e não estava no catálogo. `Roteiro` não tem dono: só `area`
(`roteiros/models.py:46`). Então recortar por área conserta o vazamento entre
áreas e **não** conserta o caso de duas pessoas da mesma área: quem salvasse
primeiro apagava o rascunho em andamento da outra, sem aviso e sem desfazer.

Os dois testes que provam isso são o primeiro e o segundo desta classe; os
demais existem para garantir que a função **não parou de fazer o que ela
deveria** — a correção fácil aqui é desligar a limpeza, e isso não é conserto.

Rascunho vazio não aparece em lugar nenhum da interface: `listar_roteiros`
(`roteiros/selectors.py:42`) já exclui roteiro com zero destinos. Por isso o
limite de idade não tem custo visível — o órfão fica escondido de qualquer
jeito, e some algumas horas depois em vez de na hora.
"""

from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.models import Roteiro
from roteiros.services.roteiro_editor import IDADE_MINIMA_RASCUNHO_ORFAO
from roteiros.services.roteiro_editor import _limpar_rascunhos_vazios
from usuarios.models import AreaTrabalho


class LimpezaDeRascunhosOrfaosTests(TestCase):
    def setUp(self):
        self.area = AreaTrabalho.objects.create(nome="Área A", sigla="RA-A")
        self.outra = AreaTrabalho.objects.create(nome="Área B", sigla="RA-B")
        self.estado = Estado.objects.create(nome="Parana", sigla="PR")
        self.cidade = Cidade.objects.create(nome="Curitiba", estado=self.estado, uf="PR")

    def _rascunho_vazio(self, area, *, idade=None):
        """Um órfão: sem sede, sem destino, sem trecho e sem saída.

        `created_at` é `auto_now_add`, então envelhecer exige `update()` — o
        `save()` sobrescreveria.
        """
        roteiro = Roteiro.objects.create(area=area)
        if idade is not None:
            Roteiro.objects.filter(pk=roteiro.pk).update(created_at=timezone.now() - idade)
        return roteiro

    def _velho(self):
        return IDADE_MINIMA_RASCUNHO_ORFAO + timedelta(minutes=1)

    # ── os dois defeitos ──

    def test_nao_apaga_rascunho_de_outra_area(self):
        """O defeito catalogado: a varredura não tinha recorte de área nenhum."""
        alheio = self._rascunho_vazio(self.outra, idade=self._velho())
        atual = Roteiro.objects.create(area=self.area)

        _limpar_rascunhos_vazios(atual)

        self.assertTrue(
            Roteiro.objects.filter(pk=alheio.pk).exists(),
            msg="a limpeza apagou rascunho de outra área",
        )

    def test_nao_apaga_rascunho_recem_criado_da_propria_area(self):
        """O defeito que o catálogo não viu, e que o recorte por área não cobre.

        Duas pessoas da **mesma** área criando roteiro ao mesmo tempo: sem
        limite de idade, quem salva primeiro apaga o rascunho em andamento da
        outra. `Roteiro` não tem dono, então não há como distinguir "meu órfão"
        de "trabalho alheio em curso" a não ser pelo tempo.
        """
        em_andamento = self._rascunho_vazio(self.area)  # criado agora
        atual = Roteiro.objects.create(area=self.area)

        _limpar_rascunhos_vazios(atual)

        self.assertTrue(
            Roteiro.objects.filter(pk=em_andamento.pk).exists(),
            msg="a limpeza apagou o rascunho que outra pessoa da mesma área estava editando",
        )

    # ── a função não pode ter parado de funcionar ──

    def test_continua_apagando_o_orfao_antigo_da_propria_area(self):
        """Desligar a limpeza passaria nos dois testes acima e não seria conserto."""
        orfao = self._rascunho_vazio(self.area, idade=self._velho())
        atual = Roteiro.objects.create(area=self.area)

        _limpar_rascunhos_vazios(atual)

        self.assertFalse(
            Roteiro.objects.filter(pk=orfao.pk).exists(),
            msg="a limpeza deixou de varrer o órfão que ela existe para varrer",
        )

    def test_nao_apaga_o_roteiro_que_acabou_de_ser_salvo(self):
        atual = Roteiro.objects.create(area=self.area)

        _limpar_rascunhos_vazios(atual)

        self.assertTrue(Roteiro.objects.filter(pk=atual.pk).exists())

    def test_nao_apaga_roteiro_com_conteudo(self):
        """Ter sede já basta para não ser órfão, por mais velho que seja."""
        com_sede = Roteiro.objects.create(area=self.area, origem_cidade=self.cidade)
        Roteiro.objects.filter(pk=com_sede.pk).update(created_at=timezone.now() - self._velho())
        atual = Roteiro.objects.create(area=self.area)

        _limpar_rascunhos_vazios(atual)

        self.assertTrue(Roteiro.objects.filter(pk=com_sede.pk).exists())
