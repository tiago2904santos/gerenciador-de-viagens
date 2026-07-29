"""Caracterização do custo de banco das telas de Plano de Trabalho, antes do `P-01`.

Último dos quatro apps. Mesmo instrumento dos anteriores: número exato de queries
por tela, medido no `main` antes de mexer, exigido igual depois.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Unidade
from planos_trabalho.models import EfetivoEvento
from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import EventoPlano
from planos_trabalho.models import PlanoDestino
from planos_trabalho.models import PlanoTrabalho
from planos_trabalho.models import ProgramaSolicitante


class OrcamentoDeQueriesPlanoTrabalhoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        estado = Estado.objects.create(nome="Parana", sigla="PR")
        cidade = Cidade.objects.create(nome="Curitiba", estado=estado, uf="PR")
        cargo = Cargo.objects.create(nome="Investigador")
        unidade = Unidade.objects.create(nome="Unidade", sigla="UN")
        programa = ProgramaSolicitante.objects.create(nome="Programa", ordem=1)

        inicio = timezone.localdate() - timedelta(days=3)
        for numero in range(1, 26):
            plano = PlanoTrabalho.objects.create(
                numero=numero,
                ano=2026,
                programa=programa,
                destino_estado=estado,
                destino_cidade=cidade,
                contextualizacao="Apoio logistico ao evento institucional.",
                data_evento_inicio=inicio,
                data_evento_fim=inicio + timedelta(days=1),
            )
            # Cada plano carrega os filhos que a lista faz `prefetch_related`.
            # Sem eles o teste nao guarda nada: um prefetch removido nao muda a
            # contagem quando a relacao esta vazia — foi o que o canario mostrou.
            PlanoDestino.objects.create(plano=plano, estado=estado, cidade=cidade, ordem=0)
            EfetivoPlano.objects.create(plano=plano, unidade=unidade, cargo=cargo, quantidade=2)
            for ordem in range(2):
                evento = EventoPlano.objects.create(
                    plano=plano,
                    ordem=ordem,
                    programa=programa,
                    data_evento_inicio=inicio,
                    data_evento_fim=inicio + timedelta(days=1),
                )
                EfetivoEvento.objects.create(
                    evento=evento, unidade=unidade, cargo=cargo, quantidade=3
                )
            if numero == 1:
                cls.plano = plano

    def setUp(self):
        user = get_user_model().objects.create_user(username="pt_orcamento")
        self.client.force_login(user)
        # Aquecimento: singleton de configuracao e sessao nao sao da tela medida.
        self.client.get(reverse("planos_trabalho:index") + "?aba=atuais")

    def _contar(self, url):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(queries), queries

    def test_a_lista_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("planos_trabalho:index") + "?aba=atuais")

        self.assertEqual(
            total,
            self.QUERIES_LISTA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_lista_com_busca_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(
            reverse("planos_trabalho:index") + "?aba=atuais&q=Apoio"
        )

        self.assertEqual(
            total,
            self.QUERIES_LISTA_BUSCA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_primeira_etapa_do_wizard_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(
            reverse("planos_trabalho:wizard_identificacao", args=[self.plano.pk])
        )

        self.assertEqual(
            total,
            self.QUERIES_WIZARD,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    # Medidos no `main` em 29/07/2026, antes da camada de selectors, com o
    # fixture cheio (plano com destinos, efetivo e dois eventos, cada um com
    # efetivo proprio). O fixture magro que eu tinha antes dava 16/16/21 e nao
    # exercitava os `prefetch_related` — foi exatamente essa cegueira que
    # escondeu o `NOVO-13`.
    QUERIES_LISTA = 20
    QUERIES_LISTA_BUSCA = 20
    QUERIES_WIZARD = 23
