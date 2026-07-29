"""Índices compostos das entidades mais lidas (`P-03`).

A auditoria registra `roteiros`, `termos` e `justificativas` com "0 constraints
e 0 indexes". A parte de indexes precisa de uma correção: **toda FK já tem
índice** — o Django cria por padrão. O que faltava era o **composto** que casa
com a ordenação, e é ele que evita ordenar depois de buscar.

`RoteiroTrecho` é o caso quente: todo card de lista carrega os trechos de um
roteiro em ordem.
"""

from __future__ import annotations

from django.test import TestCase

from roteiros.models import RoteiroDestino
from roteiros.models import RoteiroTrecho
from termos.models import TermoAutorizacao


class IndicesDeclaradosTests(TestCase):
    def test_trecho_tem_indice_composto_casando_com_a_ordenacao(self):
        nomes = {index.name: index.fields for index in RoteiroTrecho._meta.indexes}

        self.assertIn("roteiro_trecho_ordem_idx", nomes)
        self.assertEqual(nomes["roteiro_trecho_ordem_idx"], ["roteiro", "ordem"])
        self.assertEqual(RoteiroTrecho._meta.ordering, ["roteiro", "ordem"])

    def test_destino_tem_indice_composto_casando_com_a_ordenacao(self):
        nomes = {index.name: index.fields for index in RoteiroDestino._meta.indexes}

        self.assertIn("roteiro_destino_ordem_idx", nomes)
        self.assertEqual(nomes["roteiro_destino_ordem_idx"], ["roteiro", "ordem"])
        self.assertEqual(RoteiroDestino._meta.ordering, ["roteiro", "ordem"])

    def test_termo_tem_indice_para_a_listagem_por_area(self):
        nomes = {index.name: index.fields for index in TermoAutorizacao._meta.indexes}

        self.assertIn("termo_area_created_idx", nomes)
        self.assertEqual(nomes["termo_area_created_idx"], ["area", "-created_at"])


class IndicesExistemNoBancoTests(TestCase):
    """Declarar no `Meta` não é o mesmo que existir no banco.

    Sem isto, um `Meta.indexes` sem migração passaria despercebido — que é
    exatamente o tipo de coisa que o `makemigrations --check` do CI pega, mas
    só se alguém rodar.
    """

    def test_os_indices_estao_criados(self):
        from django.db import connection

        esperados = {
            "roteiros_roteirotrecho": "roteiro_trecho_ordem_idx",
            "roteiros_roteirodestino": "roteiro_destino_ordem_idx",
            "termos_termoautorizacao": "termo_area_created_idx",
        }
        with connection.cursor() as cursor:
            for tabela, indice in esperados.items():
                with self.subTest(tabela=tabela):
                    existentes = connection.introspection.get_constraints(cursor, tabela)
                    self.assertIn(indice, existentes)
                    self.assertTrue(existentes[indice]["index"])
