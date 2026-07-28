"""Contrato do componente de paginação (defeito N-07).

`components/lists/list_page_cards.html` incluía a paginação em todas as listas em
cards, mas o `{% if page_obj %}` do componente falhava em silêncio nas listas que
nunca puseram `page_obj` no contexto: a interface parecia paginada e não era.

Agora o shell de cards declara `paginacao_obrigatoria=True` e o componente
denuncia a ausência na tela. Shells que ainda hospedam listas não paginadas
(`list_page_standard`, `list_page_quick_add`) incluem sem a flag e seguem mudos.
"""
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse


ALERTA = "Paginação indisponível"
COMPONENTE = "components/ui/lists/pagination.html"

# Toda lista que usa o shell de cards — nenhuma pode renderizar o alerta.
LISTAS_EM_CARDS = [
    "eventos:index",
    "oficios:index",
    "ordens_servico:index",
    "planos_trabalho:index",
    "prestacoes_contas:index",
]


def _page(total, por_pagina=20, numero=1):
    return Paginator(list(range(total)), por_pagina).get_page(numero)


class PaginationComponentContractTests(TestCase):
    def test_sem_page_obj_e_com_contrato_declarado_denuncia_na_tela(self):
        html = render_to_string(COMPONENTE, {"paginacao_obrigatoria": True})

        self.assertIn(ALERTA, html)
        self.assertIn('role="alert"', html)

    def test_sem_page_obj_e_sem_contrato_nao_renderiza_nada(self):
        html = render_to_string(COMPONENTE, {})

        self.assertEqual(html.strip(), "")

    def test_pagina_vazia_nao_e_confundida_com_contexto_ausente(self):
        # Page sem itens é falsy: o teste do componente olha o paginator, não o
        # valor-verdade da página, senão toda lista vazia acusaria falha.
        html = render_to_string(
            COMPONENTE,
            {"page_obj": _page(0), "paginacao_obrigatoria": True},
        )

        self.assertNotIn(ALERTA, html)
        self.assertEqual(html.strip(), "")

    def test_pagina_unica_nao_renderiza_navegacao(self):
        html = render_to_string(
            COMPONENTE,
            {"page_obj": _page(12), "paginacao_obrigatoria": True},
        )

        self.assertNotIn(ALERTA, html)
        self.assertEqual(html.strip(), "")

    def test_varias_paginas_renderizam_navegacao_com_filtros_preservados(self):
        html = render_to_string(
            COMPONENTE,
            {
                "page_obj": _page(300, numero=2),
                "pagination_pages": [1, 2, 3, "...", 15],
                "page_querystring": "aba=atuais&q=teste",
                "paginacao_obrigatoria": True,
            },
        )

        self.assertNotIn(ALERTA, html)
        self.assertIn('aria-label="Paginação"', html)
        self.assertIn("21-40", html)
        self.assertIn("300", html)
        # Cada link de página carrega o filtro corrente junto.
        self.assertIn("?aba=atuais&amp;q=teste&page=3", html)
        self.assertIn("?aba=atuais&amp;q=teste&page=1", html)


class ListasEmCardsEntregamPageObjTests(TestCase):
    """Catraca: nenhuma lista em cards pode voltar a ser incluída sem `page_obj`."""

    def setUp(self):
        user = get_user_model().objects.create_user(username="paginacao", password="x")
        self.client.force_login(user)

    def test_nenhuma_lista_em_cards_renderiza_o_alerta_de_contrato(self):
        for nome in LISTAS_EM_CARDS:
            with self.subTest(lista=nome):
                response = self.client.get(reverse(nome))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, ALERTA)
                self.assertIn("page_obj", response.context)
