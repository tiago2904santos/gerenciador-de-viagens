"""Caracterização do custo de banco das telas de Evento, antes do `P-01`.

A camada de selectors deste app é uma mudança de *onde* a consulta mora, não de
*qual* consulta roda. O jeito de provar isso é fixar o número exato de queries
das duas telas antes de mexer e exigir o mesmo número depois — um `assertLessEqual`
não serviria: ele passa igual se o refactor introduzir um N+1 dentro da folga.

Os números vêm de uma medição real neste fixture, não de estimativa. Se mudarem,
a diferença é para ser explicada no PR, não ajustada em silêncio.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from cadastros.models import Cidade
from cadastros.models import Estado
from eventos.models import Evento
from ordens_servico.models import OrdemServico
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino
from termos.models import TermoAutorizacao


class OrcamentoDeQueriesEventoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estado = Estado.objects.create(sigla="PR", nome="Parana")
        cls.cidade = Cidade.objects.create(nome="CURITIBA", estado=cls.estado, uf="PR")

        cls.eventos = Evento.objects.bulk_create(
            [
                Evento(
                    titulo=f"Evento {numero}",
                    data_inicio=date(2026, 6, 1),
                    data_fim=date(2026, 6, 2),
                )
                for numero in range(25)
            ],
        )
        cls.evento = Evento.objects.order_by("pk").first()

        roteiro = Roteiro.objects.create(
            evento=cls.evento,
            origem_estado=cls.estado,
            origem_cidade=cls.cidade,
        )
        RoteiroDestino.objects.create(roteiro=roteiro, estado=cls.estado, cidade=cls.cidade, ordem=0)

        TermoAutorizacao.objects.create(
            evento=cls.evento,
            destino_estado=cls.estado,
            destino_cidade=cls.cidade,
            data_evento_inicio=date(2026, 6, 1),
            data_evento_fim=date(2026, 6, 2),
        )

    def setUp(self):
        user = get_user_model().objects.create_user(username="eventos_orcamento")
        self.client.force_login(user)

    def _contar(self, url):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(queries), queries

    def test_a_lista_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("eventos:index") + "?aba=atuais")

        self.assertEqual(
            total,
            self.QUERIES_LISTA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_lista_com_busca_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("eventos:index") + "?q=Evento&aba=atuais")

        self.assertEqual(
            total,
            self.QUERIES_LISTA_BUSCA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_o_detalhe_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("eventos:detalhe", args=[self.evento.pk]))

        self.assertEqual(
            total,
            self.QUERIES_DETALHE,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_lista_de_tipos_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("eventos:tipos_index"))

        self.assertEqual(
            total,
            self.QUERIES_TIPOS,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    # Medidos no `main` em 29/07/2026, antes da camada de selectors.
    # Atualizado em 02/08/2026 (+4): lista unificada de termos na etapa 5 e
    # limpeza visual das etapas 4/5 do guiado — mesma montagem de contexto,
    # orçamento re-medido no fixture desta classe.
    # O detalhe é caro e este teste NÃO tenta baratear: o `P-01` move consulta
    # de lugar. Baixar esse número é trabalho de outro defeito, com outra medição.
    QUERIES_LISTA = 18
    QUERIES_LISTA_BUSCA = 18
    # `NOVO-08` (06/08/2026): 78 -> 77. O detalhe do evento passou a usar o
    # `Prefetch` de servidores na forma que `TermoAutorizacao.servidores_efetivos()`
    # consome (`termos.selectors.prefetch_servidores_efetivos`), então a
    # consulta que o prefetch cru desperdiçava deixou de existir.
    QUERIES_DETALHE = 77
    QUERIES_TIPOS = 7


class OrcamentoDeQueriesEventoComOrdensTests(TestCase):
    """O detalhe do evento também monta cards de Ordem de Serviço.

    O fixture da classe acima não tem OS, então ele não exercita esse caminho —
    e sem este teste dá para apagar o `assinante=` do `eventos/views.py` sem
    nada falhar, devolvendo a consulta por card que o `NOVO-07` tirou (o do ciclo
    2026-07 — a numeracao recomecou, e o `NOVO-07` de agosto e outra coisa).
    """

    @classmethod
    def setUpTestData(cls):
        estado = Estado.objects.create(sigla="PR", nome="Parana")
        cidade = Cidade.objects.create(nome="CURITIBA", estado=estado, uf="PR")
        cls.evento = Evento.objects.create(
            titulo="Evento com OS",
            data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 2),
        )
        for numero in range(1, 4):
            ordem = OrdemServico.objects.create(
                evento=cls.evento,
                numero=numero,
                ano=2026,
                motivo="Apoio logistico.",
                data_evento_inicio=date(2026, 6, 1),
                data_evento_fim=date(2026, 6, 2),
            )
            ordem.destinos.set([cidade])

    def setUp(self):
        user = get_user_model().objects.create_user(username="evento_com_os")
        self.client.force_login(user)

    def test_o_assinante_da_os_e_resolvido_uma_vez_por_pagina(self):
        url = reverse("eventos:detalhe", args=[self.evento.pk])
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["ordem_cards"]), 3)
        self.assertEqual(
            len(queries),
            self.QUERIES_DETALHE_COM_OS,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    # Três OS na página. Se este número crescer de três em três, o assinante
    # voltou a ser resolvido por card.
    # Atualizado em 02/08/2026 (+4) junto com QUERIES_DETALHE (mesmo delta).
    QUERIES_DETALHE_COM_OS = 68
