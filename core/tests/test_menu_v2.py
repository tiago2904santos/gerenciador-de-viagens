"""O menu de ações v2 abre, aparece certo e some quando deve.

Três defeitos desta migração vivem aqui, e nenhum deles dá erro em lugar nenhum:

1. o `display` do componente vence o `[hidden]` do navegador, e o menu FECHADO
   fica visível no meio da lista;
2. o menu aberto é transplantado para o `<body>` e perde todos os ancestrais,
   então qualquer regra que dependa de um pai deixa de valer no instante em que
   ele abre;
3. o corpo servido sob demanda é procurado por `.action-menu` — seletor literal
   no `overlay.js`. Sem a classe, o clique busca, recebe a marcação certa e
   conclui "resposta sem menu".
"""

from __future__ import annotations

import re
from pathlib import Path

from django.template import Context, Template
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "static" / "css" / "v2" / "menu.css"
PESSOA_CSS = ROOT / "static" / "css" / "v2" / "person-row.css"
JS = ROOT / "static" / "js" / "components" / "overlay.js"
BUILDER = ROOT / "scripts" / "build_shell_bundles.py"

MENU = {
    "id": "menu-x",
    "title": "Documentos",
    "subtitle": "ARAPONGAS/PR",
    "src": "",
    "items": [
        {"type": "link", "href": "/a.pdf", "title": "Baixar PDF", "description": "d",
         "icon": "pdf", "tone": "pdf", "download": True, "target_blank": False},
        {"type": "delete", "url": "/x/excluir/", "label": "ARAPONGAS/PR",
         "title": "Excluir", "description": "d"},
        {"type": "attach_signed", "url": "/x/anexar/", "doc_label": "ARAPONGAS/PR",
         "assinado": False, "current_name": "", "current_view_url": "", "current_remove_url": ""},
    ],
}


def render(source: str, **contexto) -> str:
    return Template("{% load cotton %}" + source).render(Context(contexto))


class AberturaTests(SimpleTestCase):
    def setUp(self):
        self.html = render("{% cotton v2.menu_body :menu=m only / %}", m=MENU)

    def test_nasce_oculto(self):
        self.assertIn("hidden", self.html[: self.html.index(">")])

    def test_leva_a_classe_que_o_carregamento_sob_demanda_procura(self):
        """`overlay.js` acha os menus da resposta por `.action-menu`."""
        self.assertIn('class="menu action-menu"', self.html)
        self.assertIn('doc.querySelectorAll(".action-menu")', JS.read_text(encoding="utf-8"))

    def test_a_marca_do_v2_viaja_no_proprio_elemento(self):
        """Ele vai para o `<body>`; nenhum ancestral sobrevive."""
        self.assertIn("data-menu-v2", self.html)

    def test_o_gatilho_declara_os_tres_atributos_do_motor(self):
        html = render(
            '{% cotton v2.icon_button icon="folder" menu_id="menu-x" aria_label="Docs" only / %}'
        )
        self.assertIn("data-overlay-trigger", html)
        self.assertIn('data-overlay-kind="menu"', html)
        self.assertIn('data-overlay-target="menu-x"', html)

    def test_sem_menu_id_o_botao_nao_vira_gatilho(self):
        html = render('{% cotton v2.icon_button icon="edit" aria_label="Editar" only / %}')
        self.assertNotIn("data-overlay", html)


class GanchosDosItensTests(SimpleTestCase):
    """Cada tipo de item responde a um motor diferente. Nome trocado = item morto."""

    def setUp(self):
        self.html = render("{% cotton v2.menu_body :menu=m only / %}", m=MENU)

    def test_excluir_abre_o_dialogo_global(self):
        self.assertIn('data-overlay-target="delete-confirm-modal"', self.html)
        self.assertIn('data-delete-url="/x/excluir/"', self.html)
        self.assertIn('data-delete-label="ARAPONGAS/PR"', self.html)

    def test_anexar_assinado_usa_os_cinco_atributos(self):
        for atributo in (
            "data-attach-signed-trigger",
            "data-attach-signed-url",
            "data-attach-signed-doc-label",
            "data-attach-signed-current-name",
            "data-attach-signed-current-view-url",
            "data-attach-signed-current-remove-url",
        ):
            self.assertIn(atributo, self.html)

    def test_o_botao_de_excluir_avulso_carrega_os_mesmos_ganchos(self):
        html = render(
            '{% cotton v2.delete_button url="/x/" label="Termo" aria_label="Excluir" only / %}'
        )
        self.assertIn('data-overlay-target="delete-confirm-modal"', html)
        self.assertIn('data-delete-url="/x/"', html)

    def test_baixar_marca_o_download(self):
        self.assertIn("download", self.html)


class AparenciaTests(SimpleTestCase):
    def setUp(self):
        self.css = re.sub(r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL)

    def test_o_menu_fechado_some(self):
        """Sem este guarda o `display: grid` do componente vence o `[hidden]`."""
        self.assertIn(".menu[hidden]", self.css)
        bloco = self.css[self.css.index(".menu[hidden]") :]
        self.assertIn("display: none;", bloco[: bloco.index("}")])

    def test_o_menu_transplantado_declara_o_proprio_degrau(self):
        bloco = self.css[self.css.index(".menu[data-menu-v2]") :]
        bloco = bloco[: bloco.index("}")]
        self.assertIn("--surface: var(--surface-field);", bloco)
        self.assertIn("--surface-contrast: var(--surface-rail);", bloco)

    def test_item_botao_perde_o_desenho_do_navegador(self):
        """Link e botão ficam lado a lado no mesmo menu."""
        bloco = self.css[self.css.index("button.menu__item") :]
        bloco = bloco[: bloco.index("}")]
        self.assertIn("background: none;", bloco)
        self.assertIn("font: inherit;", bloco)

    def test_nao_usa_cor_literal_fora_da_sombra(self):
        literais = re.findall(r"#[0-9a-fA-F]{3,8}\b", self.css)
        self.assertEqual(literais, [], "use os tokens de `v2/tokens.css`")


class FaixaDeEquipeTests(SimpleTestCase):
    def setUp(self):
        self.css = re.sub(
            r"/\*.*?\*/", "", PESSOA_CSS.read_text(encoding="utf-8"), flags=re.DOTALL
        )

    def test_a_faixa_nao_pinta_com_a_variavel_que_ela_redefine(self):
        """Referência circular: o `background` leria o valor novo.

        Na primeira versão desta folha faixa e linha saíam da mesma cor e a
        escada sumia da tela, sem erro em lugar nenhum.
        """
        bloco = self.css[self.css.index(".person-list {") :]
        bloco = bloco[: bloco.index("}")]
        self.assertIn("--surface-contrast: var(--surface-field);", bloco)
        self.assertIn("background: var(--surface-rail);", bloco)

    def test_a_linha_sobe_um_degrau(self):
        bloco = self.css[self.css.index(".person-row {") :]
        self.assertIn("background: var(--surface-contrast, var(--surface-field));", bloco[: bloco.index("}")])

    def test_a_folha_e_entregue(self):
        builder = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"css/v2/person-row.css"', builder)
        self.assertLess(
            builder.index('"css/v2/person-row.css"'),
            builder.index('"css/v2/surface.css"'),
        )
