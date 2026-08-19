"""A lista v2 filtra e pagina — e continua fazendo isso.

Uma barra de filtros que renderiza certo e não filtra é o defeito mais caro
desta migração: a tela fica perfeita, ninguém vê erro nenhum, e o campo está
morto. Já aconteceu duas vezes nesta sessão (o gancho do picker no invólucro
errado, o `data-entity-picker` fora do `<select>`), então cada gancho que o
`js/components/collection.js` procura tem uma asserção aqui.

O motor procura tudo DENTRO da raiz `[data-collection]`. É por isso que os
testes de escopo existem: um filtro fora da raiz não é encontrado, e nada avisa.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.core.paginator import Paginator
from django.template import Context, Template
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "static" / "css" / "v2" / "pagination.css"
PAGINA_CSS = ROOT / "static" / "css" / "v2" / "list-page.css"
TOOLTIP_CSS = ROOT / "static" / "css" / "v2" / "tooltip.css"
JS = ROOT / "static" / "js" / "components" / "collection.js"
BUILDER = ROOT / "scripts" / "build_shell_bundles.py"


def render(source: str, **contexto) -> str:
    return Template("{% load cotton %}" + source).render(Context(contexto))


def pagina(numero: int = 2, total: int = 48, por_pagina: int = 10):
    return Paginator(range(total), por_pagina).page(numero)


class ColecaoTests(SimpleTestCase):
    """Os ganchos que ligam a lista ao motor de filtros."""

    def setUp(self):
        self.html = render(
            '{% cotton v2.list_page title="Termos" only %}'
            '{% cotton:slot controls %}'
            '{% cotton v2.input filter="search" aria_label="Buscar" only / %}'
            '{% cotton v2.select filter="status" aria_label="Status" only / %}'
            "{% endcotton:slot %}"
            '{% cotton:slot rows %}'
            '{% cotton v2.record title="Um" status="Ativo" search_text="um ativo" only / %}'
            "{% endcotton:slot %}"
            "{% endcotton %}"
        )

    def test_a_raiz_declara_a_colecao(self):
        self.assertRegex(self.html, r"data-collection\s")
        self.assertIn('data-collection-mode="client"', self.html)

    def test_os_filtros_ficam_dentro_da_raiz(self):
        """Fora dela o motor não os acha, e o campo fica na tela sem filtrar."""
        raiz = self.html[self.html.index('class="list-page') :]
        self.assertIn('data-collection-filter="search"', raiz)
        self.assertIn('data-collection-filter="status"', raiz)

    def test_o_registro_e_um_item_filtravel(self):
        self.assertIn("data-collection-item", self.html)

    def test_o_registro_declara_por_que_palavras_responde(self):
        """Sem `search_text` o motor cai no texto visível — que não alcança
        protocolo nem CPF, justamente o que se digita para achar um registro."""
        self.assertIn('data-search-text="um ativo"', self.html)
        self.assertIn('data-status-value="Ativo"', self.html)

    def test_o_vazio_de_filtro_nasce_oculto_e_e_outro_texto(self):
        """São dois vazios diferentes: lista sem nada × filtro sem resultado.

        Mostrar "nenhum registro cadastrado" quando o filtro escondeu tudo faz
        uma busca por termo errado parecer perda de dados.
        """
        self.assertIn("data-collection-empty hidden", self.html)
        self.assertIn("Nenhum registro para este filtro", self.html)

    def test_o_modo_padrao_e_o_do_cliente(self):
        """"server" exige `[data-collection-form]` e um `.list-panel`; sem eles
        o motor desiste calado e a lista não filtra."""
        self.assertIn('data-collection-mode="client"', self.html)

    def test_o_motor_le_exatamente_estes_ganchos(self):
        js = JS.read_text(encoding="utf-8")
        self.assertIn('var COLLECTION_SELECTOR = "[data-collection]"', js)
        self.assertIn('var FILTER_SELECTOR = "[data-collection-filter]"', js)
        self.assertIn('var ITEM_SELECTOR = "[data-collection-item]"', js)
        self.assertIn('collection.querySelector("[data-collection-empty]")', js)


class PaginacaoTests(SimpleTestCase):
    def test_lista_de_uma_pagina_nao_mostra_controles(self):
        """Uma fileira de páginas com um botão só é ruído."""
        html = render(
            "{% cotton v2.pagination :page_obj=p only / %}", p=pagina(1, total=4)
        )
        self.assertNotIn("pagination__controls", html)

    def test_pagina_vazia_nao_derruba_o_componente(self):
        """`Page` vazia é falsy em Django: testar `page_obj` some com tudo."""
        vazia = Paginator([], 10).page(1)
        html = render("{% cotton v2.pagination :page_obj=p required=1 only / %}", p=vazia)
        self.assertNotIn("pagination--erro", html)

    def test_lista_paginada_sem_page_obj_denuncia_na_tela(self):
        """Falha silenciosa aqui é a tela parecer ter só a primeira página."""
        html = render("{% cotton v2.pagination required=1 only / %}")
        self.assertIn("pagination--erro", html)
        self.assertIn('role="alert"', html)

    def test_sem_required_e_sem_page_obj_nao_renderiza_nada(self):
        self.assertEqual(render("{% cotton v2.pagination only / %}").strip(), "")

    def test_a_pagina_atual_nao_e_link(self):
        page = pagina()
        html = render(
            "{% cotton v2.pagination :page_obj=p :pages=r only / %}",
            p=page,
            r=page.paginator.page_range,
        )
        atual = html[html.index("pagination__page--current") :]
        self.assertIn('aria-current="page"', atual[: atual.index(">")])
        self.assertNotIn("<a", atual[: atual.index("</span>")])

    def test_os_filtros_da_url_sobrevivem_a_troca_de_pagina(self):
        """Sem isso, ir para a página 2 devolve a lista inteira sem filtro.

        A verificação é por AUSÊNCIA: basta um link esquecer a querystring para
        o filtro cair, e um `assertIn` num link só não pega o vizinho — foi
        exatamente o que a primeira versão deste teste deixou passar.
        """
        page = pagina()
        html = render(
            '{% cotton v2.pagination :page_obj=p :pages=r page_querystring="q=curitiba" only / %}',
            p=page,
            r=page.paginator.page_range,
        )
        self.assertIn("?q=curitiba&page=3", html)
        self.assertNotIn('href="?page=', html)

    def test_a_regua_com_reticencias_vem_da_view(self):
        """Decidir a régua aqui daria 48 botões numa lista de 48 páginas."""
        html = render(
            "{% cotton v2.pagination :page_obj=p :pages=r only / %}",
            p=pagina(),
            r=(1, 2, "...", 5),
        )
        self.assertIn("pagination__ellipsis", html)
        self.assertEqual(html.count("pagination__page"), 4)

    def test_seta_sem_destino_mantem_a_caixa(self):
        """Some o alvo, não o lugar: senão a fileira encolhe na última página."""
        page = pagina(1)
        html = render(
            "{% cotton v2.pagination :page_obj=p :pages=r only / %}",
            p=page,
            r=page.paginator.page_range,
        )
        self.assertIn('class="pagination__nav" aria-disabled="true"', html)


class AparenciaTests(SimpleTestCase):
    def setUp(self):
        self.css = re.sub(
            r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL
        )

    def test_nao_usa_cor_literal(self):
        literais = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)", self.css)
        self.assertEqual(literais, [], "use os tokens de `v2/tokens.css`")

    def test_a_seta_apagada_continua_ocupando_o_lugar(self):
        bloco = self.css[self.css.index('.pagination__nav[aria-disabled="true"]') :]
        bloco = bloco[: bloco.index("}")]
        self.assertIn("opacity: 0.4;", bloco)
        self.assertNotIn("display: none", bloco)

    def test_a_folha_e_entregue(self):
        """Folha fora do `UI_CSS` é folha que não chega ao navegador — e a
        `surface.css` tem de continuar por último, senão a escada de cor some.
        """
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"css/v2/pagination.css"', builder)
        self.assertLess(
            builder.index('"css/v2/pagination.css"'),
            builder.index('"css/v2/surface.css"'),
        )


class AcaoFlutuanteTests(SimpleTestCase):
    """A ação principal da lista, fixa no canto inferior direito.

    Ela saiu da faixa de controles porque numa lista longa o topo some da tela
    justamente quando a pessoa termina de percorrer tudo e conclui que precisa
    de um registro novo.
    """

    def test_a_acao_nao_fica_na_faixa_de_controles(self):
        html = render(
            '{% cotton v2.list_page title="X" action_label="Novo" action_url="/novo/" only / %}'
        )
        rail = html[html.index('class="rail') :] if 'class="rail' in html else ""
        self.assertNotIn("/novo/", rail)
        self.assertIn('class="list-page__action" href="/novo/"', html)

    def test_sem_url_nao_ha_botao_flutuante(self):
        html = render('{% cotton v2.list_page title="X" only / %}')
        self.assertNotIn("list-page__action", html)

    def test_o_botao_flutua_e_nao_cobre_a_paginacao(self):
        css = re.sub(r"/\*.*?\*/", "", PAGINA_CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
        bloco = css[css.index(".list-page__action {") :]
        self.assertIn("position: fixed;", bloco[: bloco.index("}")])
        self.assertIn(".list-page:has(.list-page__action)", css)


class RitmoDaListaTests(SimpleTestCase):
    def setUp(self):
        self.css = re.sub(
            r"/\*.*?\*/", "", PAGINA_CSS.read_text(encoding="utf-8"), flags=re.DOTALL
        )

    def test_a_lista_tem_vao_entre_as_pecas(self):
        """Sem isto o painel de registros nasce colado na faixa de controles."""
        bloco = self.css[self.css.index(".list-page {") :]
        bloco = bloco[: bloco.index("}")]
        self.assertIn("display: grid;", bloco)
        self.assertIn("gap: var(--gap);", bloco)

    def test_header_e_rail_continuam_encostados(self):
        """A forma já os une (o rail perde os cantos de cima); o vão os separaria."""
        bloco = self.css[self.css.index(".list-page > .header + .rail") :]
        self.assertIn("margin-top: calc(var(--gap) * -1);", bloco[: bloco.index("}")])

    def test_a_folha_e_entregue(self):
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"css/v2/list-page.css"', builder)
        self.assertLess(
            builder.index('"css/v2/list-page.css"'),
            builder.index('"css/v2/surface.css"'),
        )


class TooltipTests(SimpleTestCase):
    """O tooltip global precisa de desenho numa folha que não seja podada.

    O `icon-tooltips.js` cria a caixinha no `<body>` e a posiciona à mão. O
    desenho morava em `actions/buttons.css`, que passa pelo podador de perfis:
    numa tela v2 sobrou só a regra que DESLIGA o tooltip de `::after`, e o
    `<div>` real ficou `position: static` — o texto "Visualizar e baixar"
    aparecia solto no fim da página, empurrando a altura e criando barra de
    rolagem.
    """

    def setUp(self):
        self.css = re.sub(
            r"/\*.*?\*/", "", TOOLTIP_CSS.read_text(encoding="utf-8"), flags=re.DOTALL
        )

    def test_a_caixinha_e_tirada_do_fluxo(self):
        bloco = self.css[self.css.index(".global-tooltip {") :]
        bloco = bloco[: bloco.index("}")]
        self.assertIn("position: fixed;", bloco)
        self.assertIn("pointer-events: none;", bloco)

    def test_nasce_invisivel_e_aparece_pela_classe_do_motor(self):
        bloco = self.css[self.css.index(".global-tooltip {") :]
        self.assertIn("opacity: 0;", bloco[: bloco.index("}")])
        self.assertIn(".global-tooltip.is-visible", self.css)

    def test_o_nome_da_classe_e_o_que_o_motor_cria(self):
        js = (ROOT / "static" / "js" / "components" / "icon-tooltips.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('tooltip.className = "global-tooltip"', js)
        self.assertIn('tooltip.classList.add("is-visible")', js)

    def test_a_folha_e_entregue_fora_do_podador(self):
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"css/v2/tooltip.css"', builder)
