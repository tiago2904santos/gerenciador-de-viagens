"""As quatro redes do `PF-04`, aplicadas a cada domínio migrado.

O Ofícios tem as suas em `oficios/tests/test_menus_sob_demanda.py`, escritas à
mão porque ele tinha menu fora do rodapé. Daqui em diante os domínios seguem o
mesmo desenho, e escrever quatro testes iguais por domínio garantiria só uma
coisa: que um dia alguém adiciona o quinto domínio e esquece de copiar um deles.

As quatro propriedades, e por que cada uma existe:

1. **A lista não traz corpo de menu.** Se trouxer, o `PF-04` se desfez naquele
   domínio e ninguém percebe — a página só volta a ficar grande.
2. **Todo gatilho encontra o menu dele.** Gatilho apontando para `id` que ninguém
   serve não levanta erro: abre o menu de falha, que é melhor que nada e ainda
   assim é ação perdida.
3. **Paridade de ações** contra o mesmo presenter no caminho embutido. Comparar
   com uma lista escrita à mão envelheceria no dia em que o domínio ganhasse uma
   ação nova.
4. **Registro de outra área devolve 404.** Cada endpoint é uma porta nova para os
   dados de um registro. Uma que não recorte desfaz o `BE-09` por uma URL.
"""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from usuarios.models import AreaTrabalho


CORPO_DE_MENU = re.compile(r'<div[^>]*class="[^"]*\bcv-action-menu\b[^"]*"')
ID_DE_MENU = re.compile(r'<div[^>]*class="[^"]*cv-action-menu[^"]*"[^>]*id="([^"]+)"')
GATILHO = re.compile(r'data-overlay-kind="menu"[^>]*data-overlay-target="([^"]+)"')
GATILHO_INVERTIDO = re.compile(r'data-overlay-target="([^"]+)"[^>]*data-overlay-kind="menu"')


class RedeDeMenusSobDemanda:
    """Mixin: cada domínio migrado herda daqui e diz onde estão as suas coisas.

    Não herda de `TestCase` de propósito — senão o executor rodaria a classe base
    sem registro nenhum e as asserções passariam medindo página vazia, que é o
    modo de falha que o `NOVO-25` ensinou.
    """

    rota_lista: str = ""
    rota_menus: str = ""
    presenter = None

    def criar_registro(self, *, area=None):
        raise NotImplementedError

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pf04", password="x")
        self.client.force_login(self.user)
        self.registro = self.criar_registro()

    #: Query string que faz o registro criado cair numa aba visível. Sem isto a
    #: lista renderiza vazia, todas as asserções passam e a rede não mede nada —
    #: foi exatamente o que aconteceu na primeira versão deste arquivo.
    query_da_lista = "?aba=atuais"

    def _lista(self):
        resposta = self.client.get(reverse(self.rota_lista) + self.query_da_lista)
        self.assertEqual(resposta.status_code, 200)
        html = resposta.content.decode()
        # A asserção que impede a medição vazia.
        self.assertEqual(
            len(resposta.context["cards"]),
            1,
            "a lista não renderizou o registro criado; a medição não vale",
        )
        return html

    def _fragmento(self, pk=None):
        return self.client.get(reverse(self.rota_menus, args=[pk or self.registro.pk]))

    def test_a_lista_manda_gatilho_e_nao_manda_corpo_de_menu(self):
        html = self._lista()

        self.assertIn("data-overlay-src", html, "a lista não tem gatilho sob demanda")
        self.assertEqual(
            CORPO_DE_MENU.findall(html),
            [],
            "corpo de menu voltou para o HTML da lista; o PF-04 se desfez aqui",
        )

    def test_todo_gatilho_da_lista_encontra_o_menu_dele_no_fragmento(self):
        html = self._lista()
        fragmento = self._fragmento().content.decode()

        alvos = set(GATILHO.findall(html)) | set(GATILHO_INVERTIDO.findall(html))
        servidos = set(ID_DE_MENU.findall(fragmento))

        self.assertTrue(alvos, "a lista não tem gatilho de menu nenhum")
        self.assertEqual(alvos - servidos, set(), "gatilho sem menu correspondente")

    def test_paridade_de_acoes_com_o_caminho_embutido(self):
        card = type(self).presenter(self.registro, menus_sob_demanda=False)
        esperadas = {
            item.get("href") or item.get("action_url") or item.get("url")
            for menu in card["footer"]["menus"] + card["footer"]["danger_menus"]
            for item in menu["items"]
        }
        esperadas.discard(None)

        fragmento = self._fragmento().content.decode()

        self.assertTrue(esperadas, "o presenter não montou ação nenhuma")
        self.assertEqual(
            {url for url in esperadas if url not in fragmento},
            set(),
            "ação some do menu sem levantar erro",
        )

    def test_registro_de_outra_area_nao_vaza_pelo_endpoint(self):
        outra = AreaTrabalho.objects.create(sigla="XX", nome="Outra área")
        alheio = self.criar_registro(area=outra)

        self.assertEqual(self._fragmento(alheio.pk).status_code, 404)

    def test_endpoint_recusa_post(self):
        resposta = self.client.post(reverse(self.rota_menus, args=[self.registro.pk]))

        self.assertEqual(resposta.status_code, 405)


class PlanosTrabalhoMenusTests(RedeDeMenusSobDemanda, TestCase):
    rota_lista = "planos_trabalho:index"
    rota_menus = "planos_trabalho:card_menus"

    @staticmethod
    def presenter(registro, **kwargs):
        from planos_trabalho.presenters import apresentar_plano_card

        return apresentar_plano_card(registro, **kwargs)

    def criar_registro(self, *, area=None):
        from planos_trabalho.models import PlanoTrabalho

        campos = {"numero": 1 if area is None else 99, "ano": 2026}
        if area is not None:
            campos["area"] = area
        return PlanoTrabalho.all_objects.create(**campos)


class OrdensServicoMenusTests(RedeDeMenusSobDemanda, TestCase):
    rota_lista = "ordens_servico:index"
    rota_menus = "ordens_servico:card_menus"

    @staticmethod
    def presenter(registro, **kwargs):
        from ordens_servico.presenters import apresentar_ordem_servico_card

        return apresentar_ordem_servico_card(registro, **kwargs)

    def criar_registro(self, *, area=None):
        from ordens_servico.models import OrdemServico

        campos = {"numero": 1 if area is None else 99, "ano": 2026}
        if area is not None:
            campos["area"] = area
        return OrdemServico.all_objects.create(**campos)
