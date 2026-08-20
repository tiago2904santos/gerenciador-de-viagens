"""Os menus de ação do card vêm sob demanda, e vêm inteiros (`PF-04`).

A lista mandava 3 menus por card — 60 para 20 cards — todos com `hidden`. Medido
em `oficios:index`, volume 200: 151,2 KB de 315,3 (48% da página), 1.960 dos
3.636 nós de elemento (54%) e 51,7 ms dos 133,8 ms de servidor (39%).

Tirar marcação da página é fácil; o difícil é garantir que ela reaparece igual e
para quem tem direito. As duas redes que importam aqui são:

* **paridade** — o conjunto de ações do fragmento é o mesmo que estava embutido.
  Perder um item não levanta erro: o botão simplesmente some do menu.
* **recorte de área** — o endpoint é uma porta nova para dados de um ofício. Se
  ela não respeitar a área, o `BE-09` foi desfeito por uma URL.
"""

from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from cadastros.models import Cargo
from cadastros.models import Servidor
from oficios.models import Oficio
from oficios.presenters import apresentar_oficio_card
from usuarios.models import AreaTrabalho
from core.testing import area_de_teste
from core.testing import vincular_area


CORPO_DE_MENU = re.compile(r'<div[^>]*class="[^"]*\baction-menu\b[^"]*"')


class MenusSobDemandaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="menus", password="x")
        vincular_area(self.user)
        self.client.force_login(self.user)
        cargo = Cargo.objects.create(area=area_de_teste(), nome="Analista")
        self.servidor = Servidor.objects.create(area=area_de_teste(), nome="Servidor", cargo=cargo, cpf="12345678901")
        self.oficio = Oficio.objects.create(area=area_de_teste(), 
            numero=1, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC
        )
        self.oficio.servidores.add(self.servidor)

    def _lista(self):
        return self.client.get(reverse("oficios:index") + "?aba=atuais")

    def _menus(self, pk=None):
        return self.client.get(reverse("oficios:card_menus", args=[pk or self.oficio.pk]))

    def test_a_lista_manda_gatilho_e_nao_manda_corpo_de_menu(self):
        html = self._lista().content.decode()

        self.assertIn(reverse("oficios:card_menus", args=[self.oficio.pk]), html)
        self.assertIn("data-overlay-src", html)
        self.assertEqual(
            CORPO_DE_MENU.findall(html),
            [],
            "corpo de menu voltou para o HTML da lista; o PF-04 se desfez",
        )

    def test_o_fragmento_traz_os_menus_do_card(self):
        resposta = self._menus()

        self.assertEqual(resposta.status_code, 200)
        corpos = CORPO_DE_MENU.findall(resposta.content.decode())
        self.assertTrue(corpos, "o fragmento não trouxe menu nenhum")

    def test_todo_gatilho_da_lista_encontra_o_menu_dele_no_fragmento(self):
        """Sem isto, um gatilho pode apontar para um `id` que ninguém serve.

        O clique não levanta erro — abre o menu de falha, que é melhor que nada,
        mas continua sendo ação perdida.
        """
        html = self._lista().content.decode()
        fragmento = self._menus().content.decode()

        alvos = set(re.findall(r'data-overlay-kind="menu"[^>]*data-overlay-target="([^"]+)"', html))
        alvos |= set(re.findall(r'data-overlay-target="([^"]+)"[^>]*data-overlay-kind="menu"', html))
        servidos = set(re.findall(r'<div[^>]*class="[^"]*action-menu[^"]*"[^>]*id="([^"]+)"', fragmento))

        self.assertTrue(alvos, "a lista não tem gatilho de menu nenhum")
        self.assertEqual(alvos - servidos, set(), "gatilho sem menu correspondente")

    def test_paridade_de_acoes_com_o_caminho_embutido(self):
        """O fragmento tem exatamente as ações que ficariam embutidas.

        Compara contra o mesmo presenter com `menus_sob_demanda=False`, que é o
        caminho antigo — assim a rede não depende de eu listar as ações à mão e
        esquecer uma quando o domínio ganhar outra.
        """
        card = apresentar_oficio_card(
            self.oficio,
            excluir_next_url=reverse("oficios:index"),
            menus_sob_demanda=False,
        )
        esperadas = set()
        for menu in card["footer"]["menus"] + card["footer"]["danger_menus"]:
            for item in menu["items"]:
                esperadas.add(item.get("href") or item.get("action_url") or item.get("url"))
        esperadas.discard(None)

        fragmento = self._menus().content.decode()

        self.assertTrue(esperadas, "o presenter não montou ação nenhuma")
        faltando = {url for url in esperadas if url not in fragmento}
        self.assertEqual(faltando, set(), "ação some do menu sem levantar erro")

    def test_oficio_de_outra_area_nao_vaza_pelo_endpoint(self):
        """A rede que importa: o endpoint é porta nova para dados de um ofício."""
        outra = AreaTrabalho.objects.create(sigla="XX", nome="Outra área")
        alheio = Oficio.objects.create(
            numero=99, ano=2026, custeio=Oficio.CUSTEIO_UNIDADE_DPC, area=outra
        )

        self.assertEqual(self._menus(alheio.pk).status_code, 404)

    def test_anonimo_nao_recebe_o_fragmento(self):
        self.client.logout()

        resposta = self._menus()

        self.assertIn(resposta.status_code, (302, 403))

    def test_endpoint_recusa_post(self):
        resposta = self.client.post(reverse("oficios:card_menus", args=[self.oficio.pk]))

        self.assertEqual(resposta.status_code, 405)


class ComponenteDeMenuTests(TestCase):
    """A regra que protege os domínios que ainda não migraram.

    `eventos`, `termos`, `prestacoes_contas`, `planos_trabalho`, `ordens_servico`
    e `roteiros` continuam com o corpo embutido. Se o componente parar de embutir
    quando não há `src`, todos perdem os menus de uma vez, e em silêncio.
    """

    def test_sem_src_o_corpo_continua_embutido(self):
        from django.template.loader import render_to_string
        from core import entity_cards

        menu = entity_cards.menu(
            "menu-teste", "Título", "Subtítulo",
            [entity_cards.menu_link("/x/", "Item", "Descrição", "eye", "view")],
        )

        html = render_to_string("cotton/v2/menu_body.html", {"menu": menu})

        self.assertIn('id="menu-teste"', html)
        self.assertIn("/x/", html)
        self.assertNotIn("data-overlay-src", html)

    def test_com_src_o_corpo_nao_vai_junto(self):
        # O `entity_cards.menu(...)` que ficava aqui era sobra da cópia do teste
        # acima: ele era montado e nunca chegava a lugar nenhum, porque quem
        # renderiza abaixo é o `icon_button`, e ele recebe `menu_src` por
        # atributo, não o objeto. Com ele iam junto dois imports órfãos.
        from django.template import Context, Template

        html = Template(
            "{% load cotton %}{% cotton v2.icon_button icon='more' "
            "aria_label='Ações' menu_id='menu-teste' menu_src='/menus/' only / %}"
        ).render(Context())

        self.assertIn('data-overlay-src="/menus/"', html)
        self.assertNotIn("/x/", html)
        self.assertEqual(CORPO_DE_MENU.findall(html), [])
