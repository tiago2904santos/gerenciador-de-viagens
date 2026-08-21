"""Paginação e orçamento de queries da lista de Ofícios (defeito N-02).

A auditoria (`docs/historico/2026-07-refactor/auditorias/AUDITORIA_FINAL_CORRECAO_E_CUSTO.md`
§4.2/§4.3) mediu 16
queries fixas — sem N+1 — mas nenhuma paginação: 300 ofícios saíam numa resposta
só, com 5,9 MB de HTML e 300 cards no DOM. Estes testes fixam os dois lados do
contrato: página de tamanho fixo e nº de queries que **não cresce** com a base.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django_cotton.templatetags._component import CottonComponentNode

from oficios.models import Oficio
from oficios import card_rendering
from oficios import presenters
from oficios.views import OFICIOS_POR_PAGINA
from roteiros.models import Roteiro
from usuarios.models import AreaTrabalho
from usuarios.models import VinculoUsuarioArea
from core.testing import area_de_teste
from core.testing import vincular_area


def _criar_oficios(quantidade, *, area=None, primeiro_numero=1):
    """Ofícios já realizados (aba `atuais`), um roteiro cada."""
    area = area or area_de_teste()
    saida = timezone.now() - timedelta(days=3)
    for numero in range(primeiro_numero, primeiro_numero + quantidade):
        roteiro = Roteiro.objects.create(area=area, saida_dt=saida)
        Oficio.objects.create(numero=numero, ano=2026, roteiro=roteiro, area=area)


class OficioListPaginacaoTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(username="oficios_perf", password="x")
        vincular_area(user)
        self.client.force_login(user)
        self.url = reverse("oficios:index")

    def test_lista_de_300_entrega_uma_pagina_de_tamanho_fixo(self):
        _criar_oficios(300)

        response = self.client.get(f"{self.url}?aba=atuais")

        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(len(page_obj.object_list), OFICIOS_POR_PAGINA)
        self.assertEqual(len(response.context["cards"]), OFICIOS_POR_PAGINA)
        self.assertEqual(page_obj.paginator.count, 300)
        self.assertEqual(page_obj.paginator.num_pages, 15)
        # O que chega ao DOM é a página, não a base inteira.
        self.assertEqual(response.content.count(b"data-collection-item"), OFICIOS_POR_PAGINA)

    def test_numero_de_queries_nao_cresce_com_o_volume(self):
        _criar_oficios(20)
        # Requisição de aquecimento: a primeira leitura de sessão/configuração
        # custa queries que não pertencem à lista.
        self.client.get(f"{self.url}?aba=atuais")
        with CaptureQueriesContext(connection) as com_20:
            self.assertEqual(self.client.get(f"{self.url}?aba=atuais").status_code, 200)

        _criar_oficios(280, primeiro_numero=21)
        with CaptureQueriesContext(connection) as com_300:
            self.assertEqual(self.client.get(f"{self.url}?aba=atuais").status_code, 200)

        self.assertEqual(
            len(com_300),
            len(com_20),
            msg="a lista passou a emitir query por registro:\n"
            + "\n".join(q["sql"] for q in com_300.captured_queries),
        )
        # PF-05: seleção, hidratação e dimensões cabem no teto canônico atual.
        self.assertLessEqual(
            len(com_300),
            7,
            msg="\n".join(q["sql"] for q in com_300.captured_queries),
        )

    def test_cards_nao_expandem_componentes_cotton_a_cada_visita(self):
        """PF-05: o custo do interpretador de componentes é fixo por página.

        O que mudou em 2026-08-18: o cartão do ofício deixou de ser HTML
        achatado (`entity_card_flat` + `_oficio_card_body.html`) e passou a ser
        feito das peças do v2 — `record`, `person_row`, `fact`, `itinerary`.
        Manter uma cópia do desenho por tela foi justamente o que produziu o
        achatado, e essa cópia sai de sincronia sem avisar.

        O invariante continua o mesmo e é este teste que o segura: em REGIME,
        nenhuma expansão de componente por registro. Quem garante é
        `renderizar_oficio_card_cacheado`, que guarda o HTML por digest do
        conteúdo — a primeira visita paga o desenho de cada cartão novo, a
        seguinte não paga nada. Medido no servidor de desenvolvimento com 20
        cartões cheios: ~250ms na visita fria.
        """

        def contar_componentes(url):
            with patch.object(
                CottonComponentNode,
                "render",
                autospec=True,
                wraps=CottonComponentNode.render,
            ) as render:
                self.assertEqual(self.client.get(url).status_code, 200)
            return render.call_count

        sem_cards = contar_componentes(f"{self.url}?aba=atuais")
        _criar_oficios(OFICIOS_POR_PAGINA)
        # A primeira visita desenha os cartões novos e os guarda em cache.
        contar_componentes(f"{self.url}?aba=atuais")
        com_cards = contar_componentes(f"{self.url}?aba=atuais")

        self.assertLessEqual(
            com_cards,
            sem_cards,
            msg=(
                "os cartões voltaram a expandir componentes Cotton a cada "
                f"visita: página vazia={sem_cards}, página cheia={com_cards}"
            ),
        )

    def test_resolucao_de_urls_nao_cresce_com_os_cards(self):
        def contar_reverses(url):
            presenters._oficio_card_url_templates.cache_clear()
            with patch("oficios.presenters.reverse", wraps=reverse) as resolver:
                self.assertEqual(self.client.get(url).status_code, 200)
            return resolver.call_count

        _criar_oficios(1)
        com_um_card = contar_reverses(f"{self.url}?aba=atuais")
        _criar_oficios(OFICIOS_POR_PAGINA - 1, primeiro_numero=2)
        com_cards = contar_reverses(f"{self.url}?aba=atuais")

        self.assertEqual(com_cards, com_um_card)
        self.assertLessEqual(com_cards, 14)

    def test_html_do_card_reutiliza_cache_ate_o_conteudo_mudar(self):
        card = {"status_variant": "rascunho", "search_text": "Ofício 1"}
        card_rendering.cache.clear()

        with patch(
            "oficios.card_rendering.render_to_string",
            wraps=card_rendering.render_to_string,
        ) as render:
            primeiro = card_rendering.renderizar_oficio_card_cacheado(card)
            repetido = card_rendering.renderizar_oficio_card_cacheado(dict(card))
            alterado = card_rendering.renderizar_oficio_card_cacheado(
                {**card, "search_text": "Ofício alterado"}
            )

        self.assertEqual(primeiro, repetido)
        self.assertNotEqual(primeiro, alterado)
        self.assertEqual(render.call_count, 2)

    def test_html_do_card_permanece_escapado_quando_vem_do_cache(self):
        card = {
            "status_variant": "rascunho",
            "search_text": '<script>alert("xss")</script>',
        }
        card_rendering.cache.clear()

        primeiro = card_rendering.renderizar_oficio_card_cacheado(card)
        cacheado = card_rendering.renderizar_oficio_card_cacheado(dict(card))

        self.assertEqual(primeiro, cacheado)
        self.assertNotIn("<script>", cacheado)
        self.assertIn("&lt;script&gt;", cacheado)

    def test_pagina_limita_ids_antes_de_hidratar_as_dimensoes(self):
        """NOVO-50: o LIMIT não pode carregar a árvore inteira de joins.

        A consulta que escolhe os 20 registros da página precisa tocar apenas o
        documento e o campo usado pela aba/ordenação. Cidade, servidor, viatura
        e demais dimensões são hidratados depois, já sobre somente esses IDs.
        """
        _criar_oficios(25)

        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get(f"{self.url}?aba=atuais").status_code, 200)

        consultas_da_pagina = [
            item["sql"]
            for item in queries.captured_queries
            if 'FROM "oficios_oficio"' in item["sql"] and "LIMIT 20" in item["sql"]
        ]
        self.assertTrue(consultas_da_pagina, "não encontrei a consulta paginada de Ofícios")
        self.assertTrue(
            any('JOIN "cadastros_' not in sql for sql in consultas_da_pagina),
            msg="o LIMIT ainda paga os joins das dimensões:\n" + "\n".join(consultas_da_pagina),
        )

    def test_pagina_2_preserva_filtros_e_nao_repete_registros(self):
        _criar_oficios(45)

        pagina_1 = self.client.get(f"{self.url}?aba=atuais&sort=numero_asc")
        pagina_2 = self.client.get(f"{self.url}?aba=atuais&sort=numero_asc&page=2")

        self.assertEqual(pagina_2.status_code, 200)
        # O querystring dos links de página carrega os filtros — menos o `page`.
        querystring = pagina_2.context["page_querystring"]
        self.assertIn("aba=atuais", querystring)
        self.assertIn("sort=numero_asc", querystring)
        self.assertNotIn("page=", querystring)
        # A situação e a ordenação continuam valendo na página 2.
        self.assertEqual(pagina_2.context["abas_selecionadas"], ["atuais"])
        self.assertEqual(pagina_2.context["sort"], "numero_asc")

        numeros_1 = [o.numero for o in pagina_1.context["page_obj"].object_list]
        numeros_2 = [o.numero for o in pagina_2.context["page_obj"].object_list]
        self.assertEqual(numeros_1, list(range(1, 21)))
        self.assertEqual(numeros_2, list(range(21, 41)))

    def test_busca_textual_pagina_apenas_o_resultado_filtrado(self):
        _criar_oficios(30)

        response = self.client.get(f"{self.url}?aba=atuais&q=7")

        self.assertEqual(response.status_code, 200)
        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.count, 1)
        self.assertEqual([o.numero for o in page_obj.object_list], [7])

    def test_paginacao_nao_vaza_oficios_de_outra_area(self):
        minha_area = AreaTrabalho.objects.create(nome="Área A", sigla="AREA-A")
        outra_area = AreaTrabalho.objects.create(nome="Área B", sigla="AREA-B")
        user = get_user_model().objects.create_user(username="oficios_area", password="x")
        VinculoUsuarioArea.objects.create(usuario=user, area=minha_area, area_padrao=True)
        self.client.force_login(user)
        _criar_oficios(25, area=minha_area)
        _criar_oficios(40, area=outra_area, primeiro_numero=101)

        response = self.client.get(f"{self.url}?aba=atuais")

        page_obj = response.context["page_obj"]
        self.assertEqual(page_obj.paginator.count, 25)
        self.assertEqual(page_obj.paginator.num_pages, 2)
        self.assertTrue(
            all(o.area_id == minha_area.pk for o in page_obj.object_list),
        )

    def test_pagina_inexistente_cai_na_ultima(self):
        _criar_oficios(25)

        response = self.client.get(f"{self.url}?aba=atuais&page=999")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
