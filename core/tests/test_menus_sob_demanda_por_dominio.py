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

from core.testing import area_de_teste
from core.testing import vincular_area
from usuarios.models import AreaTrabalho


CORPO_DE_MENU = re.compile(r'<div[^>]*class="[^"]*\bcv-action-menu\b[^"]*"')
ID_DE_MENU = re.compile(r'<div[^>]*class="[^"]*action-menu[^"]*"[^>]*id="([^"]+)"')
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
        """`area=None` significa "a área do usuário logado" (DB-02: sempre há uma)."""
        raise NotImplementedError

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="pf04", password="x")
        vincular_area(self.user)
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
        campos["area"] = area or area_de_teste()
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
        campos["area"] = area or area_de_teste()
        return OrdemServico.all_objects.create(**campos)


class EventosMenusTests(RedeDeMenusSobDemanda, TestCase):
    """Eventos tem quatro famílias de menu, três delas escritas à mão no template.

    O `id` do menu de documento usa `forloop.counter`, então o fragmento precisa
    percorrer `card.documentos` na mesma ordem que o card. Se a ordem divergir, o
    gatilho aponta para um `id` que ninguém serve — e é o teste de correspondência
    de gatilho que pega.
    """

    rota_lista = "eventos:index"
    rota_menus = "eventos:card_menus"

    @staticmethod
    def presenter(registro, **kwargs):
        from eventos.presenters import apresentar_evento_list_card

        return apresentar_evento_list_card(registro, **kwargs)

    def criar_registro(self, *, area=None):
        """O evento precisa vir COM ofício vinculado.

        Um `Evento` pelado tem `card.oficios` vazio, e aí as três famílias de menu
        escritas à mão simplesmente não aparecem: a rede passa sem exercitar nada
        do que este PR move. Foi o que aconteceu na primeira versão — apagar a
        família inteira do fragmento não derrubava teste nenhum.
        """
        from eventos.models import Evento
        from oficios.models import Oficio

        campos = {"titulo": "Evento" if area is None else "Evento alheio"}
        campos["area"] = area or area_de_teste()
        evento = Evento.all_objects.create(**campos)

        oficio = {"numero": 1 if area is None else 99, "ano": 2026, "evento": evento}
        oficio["area"] = campos["area"]
        Oficio.all_objects.create(**oficio)
        return evento

    def test_fragmento_manual_usa_exatamente_a_caixa_de_menu_v2(self):
        html = self._fragmento().content.decode()

        self.assertIn('class="menu action-menu"', html)
        self.assertIn("data-menu-v2", html)
        self.assertIn("data-overlay-panel", html)
        self.assertIn('class="menu__item"', html)
        self.assertNotIn("action-menu--rich", html)
        self.assertNotIn("action-menu__item--rich", html)


# Termos saiu desta rede em 2026-08-18: o cartão perdeu o menu "Documentos" —
# era um segundo caminho para o mesmo download que o seletor da linha já faz — e
# com ele o endpoint `termos:card_menus`. Sem gatilho não há o que medir aqui;
# o que restou do cartão é coberto por `termos/tests`.


class PrestacoesMenusTests(RedeDeMenusSobDemanda, TestCase):
    """Prestações é o único domínio cujo card é por servidor, não por documento.

    E o único com menu de JS próprio: `prestacoes-diaria-wa.js` volta do menu para
    o gatilho pelo `id`, porque o overlay sempre moveu o menu para o `<body>` ao
    abrir. Materializar sob demanda não muda isso — conferido no navegador.

    O `PrestacaoServidor.objects` filtra removidos mas **não** recorta por área;
    quem recorta é `_filter_servidores_by_area`. O teste de área é o que garante
    que o endpoint usa o caminho certo.
    """

    rota_lista = "prestacoes_contas:index"
    rota_menus = "prestacoes_contas:card_menus"
    query_da_lista = ""

    @staticmethod
    def presenter(registro, **kwargs):
        from prestacoes_contas.presenters import apresentar_prestacao_servidor_card

        return apresentar_prestacao_servidor_card(registro, **kwargs)

    def criar_registro(self, *, area=None):
        from cadastros.models import Cargo
        from cadastros.models import Servidor
        from oficios.models import Oficio
        from prestacoes_contas.models import PrestacaoContas
        from prestacoes_contas.models import PrestacaoServidor

        propria = area is None
        extra = {"area": area or area_de_teste()}
        cargo = Cargo.all_objects.create(nome="Analista", **extra)
        servidor = Servidor.all_objects.create(
            nome="Servidor" if propria else "Alheio",
            cargo=cargo,
            cpf="9876543210" + ("1" if propria else "2"),
            **extra,
        )
        oficio = Oficio.all_objects.create(
            numero=1 if propria else 99,
            ano=2026,
            protocolo="123456789" if propria else "987654321",
            **extra,
        )
        # A prestação nasce por sinal junto do ofício — criar outra estoura a
        # unicidade de `oficio_id`. Pega-se a que já existe.
        prestacao, _ = PrestacaoContas.all_objects.get_or_create(
            oficio=oficio, defaults=extra
        )
        return PrestacaoServidor.objects.create(prestacao=prestacao, servidor=servidor)

    def test_paridade_de_acoes_com_o_caminho_embutido(self):
        """Prestações não usa `footer.menus`: os dois menus são escritos à mão.

        A paridade aqui é a do teste de correspondência de gatilho, que já cobre
        as duas famílias. Sobrescrever é melhor que herdar um teste que afirmaria
        `assertTrue(esperadas)` sobre um conjunto vazio e falharia por engano.
        """
        card = type(self).presenter(self.registro, menus_sob_demanda=False)
        rodape = card.get("footer") or {}

        self.assertEqual(
            (rodape.get("menus") or []) + (rodape.get("danger_menus") or []),
            [],
            "o domínio ganhou menu de rodapé; a paridade precisa voltar a valer",
        )
