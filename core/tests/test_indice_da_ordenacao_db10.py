"""`DB-10` — a lista ordena por uma chave que nenhum índice cobre.

O sintoma não é consulta a mais: é o banco ler **a área inteira**, ordenar em
memória e descartar tudo menos os 20 da página. A régua do `PF-07` não pega isso,
porque conta consulta e byte, e nenhum dos dois muda — o que muda é tempo e
buffer, e tempo não é catraca lá (por bom motivo: variação de relógio em runner
compartilhado).

Daí estes dois testes, que são de naturezas diferentes de propósito:

1. **O contrato** — a chave de ordenação que o selector emite tem de estar coberta
   por um índice declarado. Roda nos dois bancos, custa nada, e é o que pega a
   regressão real: alguém muda o `order_by` do selector e o índice fica órfão.
2. **O plano** — só no PostgreSQL e com volume: o banco não pode mais ordenar em
   memória. É a prova de que o contrato acima descreve alguma coisa.

**O que a medição não sustentou fica registrado aqui**, para ninguém repetir o
trabalho: as outras quatro listas que ordenavam em memória (`oficios`,
`planos_trabalho`, `justificativas`, `roteiros`) foram medidas com o índice
análogo e **não ganham** — em `roteiros` o índice até piora. Ver a migração
`ordens_servico/0013` para os números.
"""

from __future__ import annotations

import re

from django.db import connection
from django.test import TestCase

from core.testing import area_de_teste, com_request
from ordens_servico.models import OrdemServico
from ordens_servico.selectors import listar_ordens_servico

#: Quantas OS o teste de plano cria. Com poucas linhas o planner escolhe varredura
#: sequencial — e o teste passaria a medir a heurística de custo dele, não o
#: índice. Medido: com 400 na área ativa o índice já é escolhido.
VOLUME_DO_PLANO = 400


def _chave_de_ordenacao(sql: str) -> list[str]:
    """As colunas do `ORDER BY` da consulta, na ordem, com o sentido."""
    m = re.search(r"ORDER BY (.+?)(?: LIMIT|$)", sql, re.S)
    if not m:
        return []
    partes = []
    for termo in m.group(1).split(","):
        termo = termo.strip()
        coluna = termo.split('."')[-1].split('"')[0] if '."' in termo else termo
        sentido = "DESC" if " DESC" in termo.upper() else "ASC"
        partes.append(f"{coluna} {sentido}")
    return partes


def _indices_declarados(modelo) -> list[list[str]]:
    """Cada índice do modelo como lista de `coluna SENTIDO`, no formato acima."""
    saida = []
    for indice in modelo._meta.indexes:
        colunas = []
        for campo in indice.fields:
            desc = campo.startswith("-")
            nome = campo.lstrip("-")
            colunas.append(f"{modelo._meta.get_field(nome).column} {'DESC' if desc else 'ASC'}")
        saida.append(colunas)
    return saida


class ContratoDeOrdenacaoTests(TestCase):
    """A chave que o selector emite está coberta por índice declarado?"""

    def test_a_lista_de_os_ordena_por_chave_indexada(self):
        """O defeito, escrito como regra.

        Antes do `DB-10`, `OrdemServico.Meta.indexes` estava vazio e este teste
        reprovava com a chave real na mensagem. Ele também reprova no caminho
        inverso — mudar o `order_by` do selector sem mexer no índice.
        """
        area = area_de_teste()
        with com_request(area):
            sql = str(listar_ordens_servico().query)

        chave = _chave_de_ordenacao(sql)
        self.assertTrue(chave, "não achei ORDER BY na consulta da lista")

        declarados = _indices_declarados(OrdemServico)
        # Basta um índice cujo prefixo, depois da coluna de área, case com a chave.
        coberta = any(
            idx[1:][: len(chave)] == chave and idx[0].startswith("area")
            for idx in declarados
        )
        self.assertTrue(
            coberta,
            f"a lista ordena por {chave} e nenhum índice de "
            f"`OrdemServico` cobre isso depois da área. Declarados: {declarados}",
        )


class PlanoDaListaTests(TestCase):
    """O plano de verdade, no PostgreSQL, com volume.

    Sem volume o teste não vale: o planner varre sequencialmente uma tabela
    pequena porque é mais barato, e isso não diz nada sobre o índice.
    """

    @classmethod
    def setUpTestData(cls):
        if connection.vendor != "postgresql":
            return
        cls.area = area_de_teste(sigla="DB10")
        OrdemServico.all_objects.bulk_create(
            [
                OrdemServico(area=cls.area, ano=2020 + (i % 7), numero=i)
                for i in range(VOLUME_DO_PLANO)
            ]
        )
        with connection.cursor() as cursor:
            cursor.execute("ANALYZE ordens_servico_ordemservico")

    def test_a_lista_nao_ordena_mais_em_memoria(self):
        """A prova. Sem o índice, o plano traz `Sort Method: top-N heapsort`."""
        if connection.vendor != "postgresql":
            self.skipTest("plano de consulta só vale no PostgreSQL")

        with com_request(self.area):
            plano = "\n".join(
                str(linha)
                for linha in listar_ordens_servico()[:20].explain(analyze=True).splitlines()
            )

        self.assertNotIn(
            "Sort Method",
            plano,
            f"a lista voltou a ordenar em memória:\n{plano}",
        )
        self.assertIn("os_area_ano_numero_idx", plano, f"o índice não foi usado:\n{plano}")
