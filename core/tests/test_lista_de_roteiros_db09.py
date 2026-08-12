"""`DB-09` — a lista de roteiros agregava as tabelas filhas antes do `LIMIT`.

`Count('trechos')` + `Count('destinos')` obriga o Postgres a agrupar tudo antes de
saber quais linhas ficam. O `GroupAggregate` varria as duas tabelas filhas
inteiras — independentemente do recorte por área, que já reduz `Roteiro` por
índice — para entregar 15 cards.

A troca é por `~Exists(...)` correlacionado, que não conta: pergunta se há
**alguma** linha e para na primeira.

**O risco desta troca não é desempenho, é semântica.** `.exclude()` com quatro
argumentos é `NOT (a E b E c E d)`, **não** quatro exclusões. Um roteiro que tenha
qualquer um dos quatro sinais fica na lista; só o que não tem nenhum sai. Errar
isso some com rascunho legítimo da tela do usuário, em silêncio.

Daí a tabela-verdade caso a caso abaixo: é ela, e não o número de milissegundos,
que decide se esta fatia pode entrar.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import connection
from django.test import TestCase
from django.utils import timezone

from cadastros.models import Cidade, Estado
from core.testing import area_de_teste, com_request
from roteiros.models import Roteiro, RoteiroDestino, RoteiroTrecho
from roteiros.selectors import listar_roteiros

#: Volume do teste de plano. Com poucas linhas o planner varre sequencialmente
#: porque é mais barato, e o teste passaria a medir a heurística dele.
VOLUME_DO_PLANO = 400


class TabelaVerdadeDoRascunhoVazioTests(TestCase):
    """Quatro sinais; basta **um** para o roteiro ficar na lista.

    Cada teste liga exatamente um sinal e nenhum outro. Se a troca virasse quatro
    exclusões separadas — o erro natural de quem lê `.exclude()` rápido — os
    quatro primeiros testes reprovariam de uma vez.
    """

    @classmethod
    def setUpTestData(cls):
        cls.area = area_de_teste(sigla="DB09")
        cls.estado = Estado.objects.create(nome="Ceará", sigla="CE")
        cls.cidade = Cidade.objects.create(nome="Fortaleza", estado=cls.estado)

    def roteiro(self, **campos):
        return Roteiro.all_objects.create(area=self.area, **campos)

    def listados(self):
        with com_request(self.area):
            return set(listar_roteiros().values_list("pk", flat=True))

    def test_sem_nenhum_dos_quatro_sinais_o_rascunho_sai_da_lista(self):
        """O caso que a regra existe para tirar: rascunho que o autosave criou e ninguém tocou."""
        vazio = self.roteiro()

        self.assertNotIn(vazio.pk, self.listados())

    def test_so_com_destino_o_roteiro_fica(self):
        r = self.roteiro()
        RoteiroDestino.objects.create(
            roteiro=r, estado=self.estado, cidade=self.cidade, ordem=0,
        )

        self.assertIn(r.pk, self.listados())

    def test_so_com_trecho_o_roteiro_fica(self):
        r = self.roteiro()
        RoteiroTrecho.objects.create(
            roteiro=r,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade,
            destino_estado=self.estado,
            destino_cidade=self.cidade,
        )

        self.assertIn(r.pk, self.listados())

    def test_so_com_saida_o_roteiro_fica(self):
        r = self.roteiro(saida_dt=timezone.now() + timedelta(days=1))

        self.assertIn(r.pk, self.listados())

    def test_so_com_origem_o_roteiro_fica(self):
        r = self.roteiro(origem_estado=self.estado, origem_cidade=self.cidade)

        self.assertIn(r.pk, self.listados())

    def test_com_todos_os_quatro_o_roteiro_fica(self):
        r = self.roteiro(
            saida_dt=timezone.now() + timedelta(days=1),
            origem_estado=self.estado,
            origem_cidade=self.cidade,
        )
        RoteiroDestino.objects.create(
            roteiro=r, estado=self.estado, cidade=self.cidade, ordem=0,
        )
        RoteiroTrecho.objects.create(
            roteiro=r,
            ordem=0,
            tipo=RoteiroTrecho.TIPO_IDA,
            origem_estado=self.estado,
            origem_cidade=self.cidade,
            destino_estado=self.estado,
            destino_cidade=self.cidade,
        )

        self.assertIn(r.pk, self.listados())

    def test_o_roteiro_de_outra_area_nao_aparece(self):
        """A troca mexe no `exclude`, não no recorte — e isso precisa continuar valendo."""
        outra = area_de_teste(sigla="DB09B", nome="Outra área")
        alheio = Roteiro.all_objects.create(
            area=outra, saida_dt=timezone.now() + timedelta(days=1),
        )

        self.assertNotIn(alheio.pk, self.listados())


class PlanoDaListaDeRoteirosTests(TestCase):
    """O motivo da troca, no plano — só no PostgreSQL e com volume."""

    @classmethod
    def setUpTestData(cls):
        if connection.vendor != "postgresql":
            return
        cls.area = area_de_teste(sigla="DB09P")
        agora = timezone.now()
        Roteiro.all_objects.bulk_create(
            [
                Roteiro(area=cls.area, saida_dt=agora + timedelta(days=i % 30))
                for i in range(VOLUME_DO_PLANO)
            ]
        )
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE roteiros_roteiro")

    def test_a_lista_nao_agrega_mais_as_tabelas_filhas(self):
        """`GroupAggregate` era o que varria `roteirotrecho` e `roteirodestino` inteiras."""
        if connection.vendor != "postgresql":
            self.skipTest("plano de consulta só vale no PostgreSQL")

        with com_request(self.area):
            plano = listar_roteiros()[:15].explain(analyze=True)

        self.assertNotIn(
            "GroupAggregate", plano, f"a lista voltou a agregar antes do LIMIT:\n{plano}"
        )
        self.assertNotIn(
            "HashAggregate", plano, f"a lista voltou a agregar antes do LIMIT:\n{plano}"
        )

    def test_a_lista_usa_o_indice_de_ordenacao(self):
        """O índice do `DB-09` só serve depois que a agregação saiu — ver a migração 0015."""
        if connection.vendor != "postgresql":
            self.skipTest("plano de consulta só vale no PostgreSQL")

        with com_request(self.area):
            plano = listar_roteiros()[:15].explain(analyze=True)

        self.assertIn("roteiro_area_updated_idx", plano, f"o índice não foi usado:\n{plano}")
