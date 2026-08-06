"""O custo da lista de roteiros não cresce com o número de cards (`NOVO-27`).

O `NOVO-26` tirou o mapa de capitais da memória do processo, porque ele ficava
velho e `classify` decide valor de diária. A rede que escrevi lá media o eixo
errado: **marcadores dentro de um cálculo**. O que estourou foi o outro eixo —
**cálculos por página**.

`roteiros/views.py` monta um card por roteiro, e cada card chamava
`capitais_por_uf()`. Com 15 cards, 15 consultas a mais: o teto do `PF-07` para
`roteiros:index` foi de 32 para **47**, e derrubou a `main` (run 651).

Corrigido resolvendo o mapa **uma vez por página** e passando adiante, no mesmo
desenho que `classify` e `build_periods` já usavam. Sobra **uma** consulta por
requisição — o teto subiu de 32 para 33 de propósito, porque é o preço de o mapa
não ficar velho, e é a diferença entre "o admin marcou uma capital" valer na
requisição seguinte ou só depois de reiniciar o worker.

Este teste guarda o eixo que faltava: dobrar o número de roteiros na página não
pode dobrar consulta nenhuma.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from cadastros.models import Cidade
from cadastros.models import Estado
from roteiros.models import Roteiro
from roteiros.models import RoteiroDestino


class CustoDaListaDeRoteirosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estado = Estado.objects.create(sigla="PR", nome="Parana")
        cls.capital = Cidade.objects.create(
            nome="CURITIBA", estado=cls.estado, uf="PR", capital=True
        )
        cls.interior = Cidade.objects.create(nome="ABATIA", estado=cls.estado, uf="PR")

    def setUp(self):
        self.client.force_login(get_user_model().objects.create_user(username="lista_roteiros"))

    def _criar_roteiros(self, quantidade):
        """`saida_dt` é obrigatório para o roteiro cair em alguma aba.

        Sem data ele some da lista, e o teste passa medindo uma página vazia —
        que foi exatamente o que aconteceu na primeira versão disto.
        """
        for numero in range(quantidade):
            roteiro = Roteiro.objects.create(
                origem_estado=self.estado,
                origem_cidade=self.capital,
                saida_dt=timezone.now() + timedelta(days=numero + 1),
                chegada_dt=timezone.now() + timedelta(days=numero + 1, hours=6),
            )
            RoteiroDestino.objects.create(
                roteiro=roteiro,
                estado=self.estado,
                cidade=self.capital if numero % 2 else self.interior,
                ordem=0,
            )

    def _consultas_de_capitais(self, *, cards_esperados):
        with CaptureQueriesContext(connection) as capturadas:
            resposta = self.client.get(reverse("roteiros:index"))
        self.assertEqual(resposta.status_code, 200)
        # Sem esta asserção o teste mede uma lista vazia e passa sempre.
        self.assertEqual(
            len(resposta.context["cards"]),
            cards_esperados,
            "a lista não renderizou os cards esperados; a medição não vale",
        )
        # O filtro precisa ser o `WHERE`, não a palavra "capital" solta: ela
        # aparece na lista de colunas de QUALQUER select de `Cidade`, e contar
        # assim mede o carregamento de origem/destino junto — foi o que me fez
        # ler 4 onde havia 1.
        return sum(
            1
            for consulta in capturadas.captured_queries
            if 'WHERE "cadastros_cidade"."capital"' in consulta["sql"]
        )

    def test_o_mapa_de_capitais_e_resolvido_uma_vez_por_pagina(self):
        self._criar_roteiros(3)
        self.assertEqual(
            self._consultas_de_capitais(cards_esperados=3),
            1,
            "cada card resolvendo o mapa por conta própria é o NOVO-27: com 15 "
            "roteiros na página vira 15 consultas, e o teto do PF-07 estoura",
        )

    def test_dobrar_os_roteiros_nao_dobra_as_consultas(self):
        self._criar_roteiros(2)
        poucos = self._consultas_de_capitais(cards_esperados=2)

        self._criar_roteiros(6)
        muitos = self._consultas_de_capitais(cards_esperados=8)

        self.assertEqual(
            poucos,
            muitos,
            "o custo do mapa de capitais passou a crescer com o tamanho da lista",
        )
