"""Caracterização do custo de banco das telas de Termo, antes do `P-01`.

Mesmo raciocínio do teste equivalente em `eventos`: a camada de selectors muda
*onde* a consulta mora, não *qual* consulta roda — então o número exato de
queries de cada tela é fixado antes de mexer e exigido de novo depois.

Igualdade, não `assertLessEqual`: um teto com folga passa igual se o refactor
enfiar um N+1 dentro dela.
"""

from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from core.testing import com_request
from termos.models import TermoAutorizacao
from termos.selectors import listar_termos
from core.testing import area_de_teste
from core.testing import vincular_area
from oficios.models import Oficio


class OrcamentoDeQueriesTermoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.estado = Estado.objects.create(nome="Parana", sigla="PR")
        cls.cidade = Cidade.objects.create(nome="Curitiba", estado=cls.estado, uf="PR")
        cargo = Cargo.objects.create(area=area_de_teste(), nome="Investigador")
        unidade = Unidade.objects.create(area=area_de_teste(), nome="Unidade", sigla="UN")

        cls.servidores = [
            Servidor.objects.create(area=area_de_teste(), 
                nome=f"Servidor {numero}",
                cargo=cargo,
                unidade=unidade,
                cpf=f"1111111111{numero}",
                rg=f"123456{numero}",
            )
            for numero in range(3)
        ]

        cls.servidor_oficio = Servidor.objects.create(
            area=area_de_teste(),
            nome="Participante do oficio",
            cargo=cargo,
            unidade=unidade,
            cpf="22222222220",
            rg="6543210",
        )
        cls.servidor_termo_oficio = Servidor.objects.create(
            area=area_de_teste(),
            nome="Participante marcado para termo",
            cargo=cargo,
            unidade=unidade,
            cpf="22222222221",
            rg="6543211",
        )
        cls.oficio = Oficio.objects.create(area=area_de_teste(), numero=91, ano=2026)
        cls.oficio.servidores.add(cls.servidor_oficio)
        cls.oficio.servidores_termo_autorizacao.add(cls.servidor_termo_oficio)
        cls.termo_do_oficio = TermoAutorizacao.objects.create(
            area=area_de_teste(),
            oficio=cls.oficio,
        )

        for numero in range(20):
            termo = TermoAutorizacao.objects.create(area=area_de_teste(), 
                destino_estado=cls.estado,
                destino_cidade=cls.cidade,
                data_evento_inicio=date(2026, 6, 1),
                data_evento_fim=date(2026, 6, 2),
            )
            termo.servidores.set(cls.servidores)
            if numero == 0:
                cls.termo = termo

    def setUp(self):
        user = get_user_model().objects.create_user(username="termos_orcamento")
        self.client.force_login(user)
        vincular_area(user)

    def _contar(self, url):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(queries), queries

    def test_a_lista_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("termos:index"))

        self.assertEqual(
            total,
            self.QUERIES_LISTA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_lista_com_busca_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("termos:index") + "?q=Curitiba")

        self.assertEqual(
            total,
            self.QUERIES_LISTA_BUSCA,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    def test_a_busca_pesada_nao_e_repetida_so_para_contar_a_pagina(self):
        """A contagem das abas ja conhece o total usado pelo paginador (`DB-11`)."""
        _total, queries = self._contar(reverse("termos:index") + "?q=Curitiba")

        consultas_da_busca = [
            query["sql"]
            for query in queries.captured_queries
            if 'FROM "termos_termoautorizacao"' in query["sql"]
            and "CURITIBA" in query["sql"].upper()
        ]
        self.assertEqual(
            len(consultas_da_busca),
            2,
            msg="\n\n".join(consultas_da_busca),
        )

    def test_a_busca_m2m_preserva_as_tres_origens_sem_multiplicar_termos(self):
        with com_request(area_de_teste()):
            ids_servidor_proprio = list(
                listar_termos(q="Servidor 0").values_list("pk", flat=True)
            )
            ids_servidor_oficio = list(
                listar_termos(q="Participante do oficio").values_list("pk", flat=True)
            )
            ids_servidor_termo_oficio = list(
                listar_termos(q="Participante marcado para termo").values_list("pk", flat=True)
            )

        self.assertEqual(len(ids_servidor_proprio), 20)
        self.assertEqual(len(ids_servidor_proprio), len(set(ids_servidor_proprio)))
        self.assertEqual(ids_servidor_oficio, [self.termo_do_oficio.pk])
        self.assertEqual(ids_servidor_termo_oficio, [self.termo_do_oficio.pk])

    def test_o_formulario_de_edicao_custa_o_mesmo_numero_de_queries(self):
        total, queries = self._contar(reverse("termos:editar", args=[self.termo.pk]))

        self.assertEqual(
            total,
            self.QUERIES_EDITAR,
            msg="\n".join(q["sql"] for q in queries.captured_queries),
        )

    # Medidos no `main` em 29/07/2026, antes da camada de selectors.
    # 54 -> 55: a lista ganhou as abas "Com equipe"/"Sem equipe", e a contagem
    # das duas custa 1 query (agregacao condicional unica sobre a mesma base,
    # nao dois .count()). Ver termos.views.index.

    # `NOVO-08` (06/08/2026): a catraca desceu 55 -> 11 na lista e 28 -> 26 na
    # edição. Três causas, todas por linha da página e nenhuma por tamanho do
    # banco: `servidores_efetivos()` clonava o related manager e descartava o
    # cache do prefetch (2 consultas por termo), e `termo_cadastro_assinado_info`
    # buscava o artefato assinado uma vez por linha (1 por termo). Medido pela
    # régua do `PF-07` no volume 200: `/termos/` foi de 55 para 11.

    # `PF-03` (07/08/2026): a sessão saiu do caminho de escrita de toda requisição
    # (`cached_db` + `SESSION_SAVE_EVERY_REQUEST = False` + renovação periódica).
    # Em regime, some 1 leitura + 1 escrita + 2 comandos de transação = **-4**.
    # Onde o corte é **-1**, o teste mede a **primeira** requisição depois do
    # login: ali `core/tenancy.py:52` grava a área na sessão, que por isso é
    # salva de qualquer jeito, e só a leitura é economizada.
    # `DB-11`: a agregacao das abas ja conhece o total da aba ativa e alimenta o
    # paginador. Sai a repeticao da consulta de contagem, com ou sem busca.
    QUERIES_LISTA = 9
    QUERIES_LISTA_BUSCA = 9
    # 21 -> 28 na edicao. Duas causas separadas, e so uma era defeito:
    #  (a) N+1 REAL, corrigido: `termo_cadastro_assinado_info` consultava
    #      DocumentoArtefato uma vez por servidor. Agora e uma query so, via
    #      `mapa_artefatos_pdf_termo_cadastro`. Medido: 4 -> 1 com 3 servidores,
    #      e o total parou de crescer com o tamanho da equipe.
    #  (b) custo CONSTANTE novo: a previa de destinos passou a resolver a sede
    #      das Configuracoes, e `ConfiguracaoSistema.get_singleton()` e relido
    #      por request. Nao escala com dados; fica registrado como NOVO-27.
    # Se este numero subir de novo, comece por (a): e o que volta sozinho.
    #
    # 26 -> 24 (`NOVO-07`): sairam as duas varreduras da tabela de oficios que a
    # tela fazia sem precisar. Uma montava o `json_script` com a area inteira; a
    # outra era a renderizacao do `<select>`, um `<option>` por oficio. As duas
    # cresciam com o banco e nenhuma aparecia na contagem, porque contagem de
    # query nao mede quantas linhas cada uma traz. Agora o campo renderiza so o
    # que esta selecionado — aqui, nada — e o resto vem de `api_buscar_oficios`.
    #
    # O 26 aqui e o do `NOVO-08`, nao o 28 antigo: os dois IDs baixaram esta
    # mesma catraca por motivos diferentes e o merge tinha de somar as duas
    # quedas, nao repetir uma. Este numero e medido depois do merge.
    QUERIES_EDITAR = 17  # remedido no DB-02: usuário de teste passou a ter vínculo de área
