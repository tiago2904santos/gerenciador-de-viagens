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
from cadastros.selectors import get_configuracao_sistema
from planos_trabalho.models import EfetivoEvento
from planos_trabalho.models import EfetivoPlano
from planos_trabalho.models import EventoPlano
from planos_trabalho.models import PlanoDestino
from planos_trabalho.models import PlanoTrabalho
from planos_trabalho.models import ProgramaSolicitante
from core.testing import area_de_teste
from core.testing import vincular_area


class OrcamentoDeQueriesPlanoTrabalhoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        estado = Estado.objects.create(nome="Parana", sigla="PR")
        cidade = Cidade.objects.create(nome="Curitiba", estado=estado, uf="PR")
        cargo = Cargo.objects.create(area=area_de_teste(), nome="Investigador")
        unidade = Unidade.objects.create(area=area_de_teste(), nome="Unidade", sigla="UN")
        programa = ProgramaSolicitante.objects.create(area=area_de_teste(), nome="Programa", ordem=1)

        inicio = timezone.localdate() - timedelta(days=3)
        for numero in range(1, 26):
            plano = PlanoTrabalho.objects.create(area=area_de_teste(), 
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
        vincular_area(user)
        # Aquecimento: singleton de configuracao e sessao nao sao da tela medida.
        self.client.get(reverse("planos_trabalho:index") + "?aba=atuais")
        # A lista nao le a configuracao da area; o wizard passa a ler, pela secao
        # de destinos do v2 (a UF da sede pre-seleciona o estado da primeira
        # linha). Sem criar o singleton aqui, o `get_or_create` dele — SELECT,
        # SAVEPOINT, INSERT e RELEASE — entraria na conta da tela medida.
        get_configuracao_sistema()

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

    def test_a_pagina_limita_ids_antes_de_hidratar_as_dimensoes(self):
        """NOVO-50: os 20 IDs são escolhidos antes dos joins de catálogo."""
        _total, queries = self._contar(reverse("planos_trabalho:index") + "?aba=atuais")

        consultas_da_pagina = [
            item["sql"]
            for item in queries.captured_queries
            if 'FROM "planos_trabalho_planotrabalho"' in item["sql"]
            and "LIMIT 20" in item["sql"]
        ]
        self.assertTrue(consultas_da_pagina, "não encontrei a consulta paginada de Planos")
        self.assertTrue(
            any('JOIN "cadastros_' not in sql for sql in consultas_da_pagina),
            msg="o LIMIT ainda paga os joins das dimensões:\n" + "\n".join(consultas_da_pagina),
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

    # `PF-03` (07/08/2026): a sessão saiu do caminho de escrita de toda requisição
    # (`cached_db` + `SESSION_SAVE_EVERY_REQUEST = False` + renovação periódica).
    # Em regime, some 1 leitura + 1 escrita + 2 comandos de transação = **-4**.
    # Onde o corte é **-1**, o teste mede a **primeira** requisição depois do
    # login: ali `core/tenancy.py:52` grava a área na sessão, que por isso é
    # salva de qualquer jeito, e só a leitura é economizada.
    # `NOVO-50`: a página passou a escolher IDs antes de hidratar dimensões.
    # O prefetch de destinos agora resolve cidade/estado na mesma consulta e o
    # card não busca mais `eventos__programa`, relação que ele não lê: -2.
    QUERIES_LISTA = 10
    QUERIES_LISTA_BUSCA = 10
    # 19 -> 20 na migracao do wizard para o v2 (2026-08-18): a secao de destinos
    # passou a ser o `c-v2.destinations`, que busca os proprios dados em vez de
    # exigi-los da view (`core/templatetags/destinos.py`). A consulta a mais e a
    # leitura da configuracao da area, de onde sai a UF da sede que pre-seleciona
    # o estado da primeira linha; ela e memoizada por REQUISICAO, entao nao cresce
    # com o numero de destinos. Em troca, a lista de estados deixou de vir do
    # queryset do formulario e a tela deixou de depender de a view lembrar de
    # passar `estados` — o modo de falha era silencioso: o campo abria vazio.
    QUERIES_WIZARD = 20
