"""Caracterização do custo de banco das telas de Ordem de Serviço, antes do `P-01`.

Mesmo raciocínio dos testes equivalentes em `eventos` e `termos`: a camada de
selectors muda *onde* a consulta mora, não *qual* consulta roda.

O app já tem `test_list_performance.py`, mas ele responde a outra pergunta — se o
custo **cresce** com o volume, com teto de 140 para uma página que custa bem
menos. Um refactor que enfiasse um N+1 dentro dessa folga passaria lá e falha
aqui, porque aqui a comparação é de igualdade.
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
from cadastros.models import Servidor
from cadastros.models import Unidade
from ordens_servico.models import OrdemServico


class OrcamentoDeQueriesOrdemServicoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        estado = Estado.objects.create(nome="Parana", sigla="PR")
        Cidade.objects.create(nome="Curitiba", estado=estado, uf="PR")
        cargo = Cargo.objects.create(nome="Investigador")
        unidade = Unidade.objects.create(nome="Unidade", sigla="UN")
        servidores = [
            Servidor.objects.create(
                nome=f"Servidor {numero}",
                cargo=cargo,
                unidade=unidade,
                cpf=f"2222222222{numero}",
                rg=f"765432{numero}",
            )
            for numero in range(3)
        ]

        inicio = timezone.localdate() - timedelta(days=3)
        for numero in range(1, 26):
            ordem = OrdemServico.objects.create(
                numero=numero,
                ano=2026,
                motivo="Apoio logistico ao evento institucional.",
                data_evento_inicio=inicio,
                data_evento_fim=inicio + timedelta(days=1),
            )
            ordem.servidores.set(servidores)
            if numero == 1:
                cls.ordem = ordem

    def setUp(self):
        user = get_user_model().objects.create_user(username="os_orcamento")
        self.client.force_login(user)
        # Aquecimento: a primeira leitura do singleton de configuracao e da
        # sessao custa queries que nao sao da tela medida.
        self.client.get(reverse("ordens_servico:index") + "?aba=atuais")

    def _contar(self, url):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(queries), queries

    def test_a_lista_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("ordens_servico:index") + "?aba=atuais")

        self.assertEqual(
            total,
            self.QUERIES_LISTA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_lista_com_busca_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(
            reverse("ordens_servico:index") + "?aba=atuais&q=Apoio"
        )

        self.assertEqual(
            total,
            self.QUERIES_LISTA_BUSCA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_o_formulario_de_edicao_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(
            reverse("ordens_servico:editar", args=[self.ordem.pk])
        )

        self.assertEqual(
            total,
            self.QUERIES_EDITAR,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    # Medidos no `main` em 29/07/2026, antes da camada de selectors.
    QUERIES_LISTA = 137
    QUERIES_LISTA_BUSCA = 137
    QUERIES_EDITAR = 23
