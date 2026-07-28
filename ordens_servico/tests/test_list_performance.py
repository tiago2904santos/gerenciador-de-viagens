"""Paginação e orçamento de queries da lista de Ordens de Serviço (defeito N-02).

A lista carregava a base inteira: 300 OS = 2,6 MB de HTML e 1.814 queries. A
paginação corta as duas coisas — e, sobretudo, desliga o crescimento: o custo de
uma página passa a ser o mesmo com 20 ou com 300 registros cadastrados.

O custo por página ainda é alto (`NOVO-07`: o presenter do card emite queries por
card). Este teste trava o crescimento; o teto continua alto de propósito, para
ser baixado pelo PR que corrigir `NOVO-07`.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from ordens_servico.models import OrdemServico
from ordens_servico.views import ORDENS_POR_PAGINA
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea


# Teto atual de queries por página, medido. Não é um alvo: é uma catraca.
TETO_QUERIES_POR_PAGINA = 140


def _criar_ordens(quantidade, *, area=None, primeiro_numero=1):
    """OS já realizadas (aba `atuais`)."""
    inicio = timezone.localdate() - timedelta(days=3)
    OrdemServico.objects.bulk_create(
        [
            OrdemServico(
                numero=numero,
                ano=2026,
                area=area,
                motivo="Apoio logístico ao evento institucional.",
                data_evento_inicio=inicio,
                data_evento_fim=inicio + timedelta(days=1),
            )
            for numero in range(primeiro_numero, primeiro_numero + quantidade)
        ],
    )


class OrdemServicoListPaginacaoTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="os_perf", password="x")
        self.client.force_login(user)
        self.url = reverse("ordens_servico:index")

    def test_lista_de_300_entrega_uma_pagina_de_tamanho_fixo(self):
        _criar_ordens(300)

        response = self.client.get(f"{self.url}?aba=atuais")

        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj.object_list), ORDENS_POR_PAGINA)
        self.assertEqual(len(response.context["cards"]), ORDENS_POR_PAGINA)
        self.assertEqual(page_obj.paginator.count, 300)
        self.assertEqual(page_obj.paginator.num_pages, 15)
        self.assertEqual(response.content.count(b"data-cv-filter-item"), ORDENS_POR_PAGINA)

    def test_numero_de_queries_nao_cresce_com_o_volume(self):
        _criar_ordens(20)
        # Requisição de aquecimento: a primeira criação/leitura do singleton de
        # configuração e da sessão custa queries que não são da lista.
        self.client.get(f"{self.url}?aba=atuais")
        with CaptureQueriesContext(connection) as com_20:
            self.assertEqual(self.client.get(f"{self.url}?aba=atuais").status_code, 200)

        _criar_ordens(280, primeiro_numero=21)
        with CaptureQueriesContext(connection) as com_300:
            self.assertEqual(self.client.get(f"{self.url}?aba=atuais").status_code, 200)

        self.assertEqual(
            len(com_300),
            len(com_20),
            msg="a lista voltou a emitir query por registro da base:\n"
            + "\n".join(q["sql"] for q in com_300.captured_queries),
        )
        self.assertLessEqual(
            len(com_300),
            TETO_QUERIES_POR_PAGINA,
            msg="\n".join(q["sql"] for q in com_300.captured_queries),
        )

    def test_pagina_2_preserva_filtros_e_nao_repete_registros(self):
        _criar_ordens(45)

        pagina_1 = self.client.get(f"{self.url}?aba=atuais&sort=numero_asc")
        pagina_2 = self.client.get(f"{self.url}?aba=atuais&sort=numero_asc&page=2")

        self.assertEqual(pagina_2.status_code, 200)
        querystring = pagina_2.context["page_querystring"]
        self.assertIn("aba=atuais", querystring)
        self.assertIn("sort=numero_asc", querystring)
        self.assertNotIn("page=", querystring)
        self.assertEqual(pagina_2.context["sort"], "numero_asc")

        numeros_1 = [o.numero for o in pagina_1.context["page_obj"].object_list]
        numeros_2 = [o.numero for o in pagina_2.context["page_obj"].object_list]
        self.assertEqual(numeros_1, list(range(1, 21)))
        self.assertEqual(numeros_2, list(range(21, 41)))

    def test_busca_textual_pagina_apenas_o_resultado_filtrado(self):
        _criar_ordens(30)

        response = self.client.get(f"{self.url}?aba=atuais&q=7")

        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual([o.numero for o in page_obj.object_list], [7])

    def test_paginacao_nao_vaza_ordens_de_outra_area(self):
        minha_area = AreaTrabalho.objects.create(nome="Área A", sigla="AREA-A")
        outra_area = AreaTrabalho.objects.create(nome="Área B", sigla="AREA-B")
        user = get_user_model().objects.create_user(username="os_area", password="x")
        VinculoUsuarioArea.objects.create(usuario=user, area=minha_area, area_padrao=True)
        self.client.force_login(user)
        _criar_ordens(25, area=minha_area)
        _criar_ordens(40, area=outra_area, primeiro_numero=101)

        response = self.client.get(f"{self.url}?aba=atuais")

        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.count, 25)
        self.assertTrue(all(o.area_id == minha_area.pk for o in page_obj.object_list))
