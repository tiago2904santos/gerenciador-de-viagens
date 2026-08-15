"""O picker v2 é o modelo base: o que outras variações herdam.

Cada asserção aqui corresponde a um defeito desta sessão, e nenhum deles dava
erro em lugar nenhum — a página renderizava e o campo ficava morto, ou o botão
de remover só existia para quem passasse o mouse por cima por acaso.

O caso mais caro: o gancho `data-entity-picker` estava no invólucro `<div>` e o
motor procura `select[data-entity-picker]`. O componente parecia certo lido
sozinho, aparecia na tela, e simplesmente não inicializava.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.template import Context, Template
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "static" / "css" / "v2" / "picker.css"
JS = ROOT / "static" / "js" / "components" / "picker.js"
COMPONENTE = ROOT / "templates" / "cotton" / "v2" / "picker.html"

MINIMO = '{% cotton v2.picker mode="multi" name="equipe" only / %}'


def render(source: str, **contexto) -> str:
    return Template("{% load cotton %}" + source).render(Context(contexto))


class MarcacaoTests(SimpleTestCase):
    def test_o_gancho_vai_no_select(self):
        """No invólucro, o motor não acha o campo — e nada avisa.

        A comparação é EXATA (`data-entity-picker="true"`), não por substring:
        `data-entity-picker-mode` e `data-entity-picker-x` também contêm o
        prefixo, e a primeira versão deste teste passava com o gancho renomeado.
        """
        html = render(MINIMO)
        select = html[html.index("<select") : html.index("</select>")]
        self.assertIn('data-entity-picker="true"', select)

    def test_o_involucro_nao_carrega_o_gancho(self):
        html = render(MINIMO)
        involucro = html[: html.index("<select")]
        self.assertNotIn("data-entity-picker", involucro)
        self.assertNotIn("data-entity-picker-root", involucro)
        self.assertIn('class="picker', involucro)

    def test_declara_ser_do_v2(self):
        """`data-picker-v2` é o que separa esta lista da do legado."""
        self.assertIn("data-picker-v2", render(MINIMO))

    def test_o_rotulo_dos_escolhidos_nao_vem_em_caixa_alta(self):
        """O padrão do motor é "SELECIONADOS", herança do desenho antigo."""
        html = render(MINIMO)
        self.assertIn('data-panel-title="Selecionados"', html)

    def test_aceita_opcoes_sem_form(self):
        html = render(
            '{% cotton v2.picker name="x" :options="opcoes" only / %}',
            opcoes=[{"value": "1", "label": "Um"}],
        )
        self.assertIn('<option value="1">Um</option>', html)


class ContratoComOMotorTests(SimpleTestCase):
    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")

    def test_a_marca_do_v2_e_atributo_no_dropdown(self):
        """JS-06: nome de classe não é condição de lógica.

        O dropdown é transplantado para o `body` e perde os ancestrais; a marca
        vai no próprio elemento para o CSS e o motor o reconhecerem.
        """
        self.assertIn('dropdown.setAttribute("data-entity-picker-v2"', self.js)
        self.assertIn('select.hasAttribute("data-picker-v2")', self.js)

    def test_o_check_e_montado_por_dom_e_nao_por_html(self):
        """`innerHTML` é proibido em produção — e aqui evita outra armadilha.

        Sem o namespace correto, o elemento vira um "svg" de HTML: tem caixa,
        responde a getComputedStyle e NÃO desenha nada.
        """
        self.assertIn('document.createElementNS(SVG_NS, "svg")', self.js)
        self.assertIn('document.createElementNS(SVG_NS, "path")', self.js)
        self.assertNotIn("status.innerHTML", self.js)


class AparenciaTests(SimpleTestCase):
    def setUp(self):
        self.css = re.sub(
            r"/\*.*?\*/", "", CSS.read_text(encoding="utf-8"), flags=re.DOTALL
        )

    def _bloco(self, marca: str) -> str:
        i = self.css.index(marca)
        return self.css[i : self.css.index("}", i)]

    def test_nao_usa_cor_literal(self):
        literais = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)", self.css)
        self.assertEqual(literais, [], "use os tokens de `v2/tokens.css`")

    def test_o_campo_de_busca_nao_tem_sombra(self):
        """O legado punha relevo só neste campo, e em nenhum outro do sistema."""
        self.assertIn("box-shadow: none;", self._bloco(".search-picker__control {"))

    def test_a_caixa_dos_escolhidos_tem_o_desenho_do_form_block(self):
        bloco = self._bloco(".search-picker__selected-panel {")
        self.assertIn("border: 0;", bloco)
        self.assertIn("border-radius: var(--radius-field);", bloco)
        self.assertIn("padding: var(--gap);", bloco)

    def test_a_caixa_declara_o_degrau_dos_filhos(self):
        """Sem isso, caixa e itens caem na mesma cor e a lista fica chapada."""
        bloco = self._bloco(".search-picker__selected-panel {")
        self.assertIn("--surface-contrast: var(--surface-rail);", bloco)

    def test_a_lista_para_em_tres_e_rola(self):
        bloco = self._bloco(".search-picker__selected-list {")
        self.assertIn("* 3", bloco)
        self.assertIn("overflow-y: auto;", bloco)

    def test_o_remover_esta_sempre_visivel_e_a_direita(self):
        """O legado o escondia com `opacity: 0` até o hover."""
        bloco = self._bloco(".search-picker__remove,")
        self.assertIn("opacity: 1;", bloco)
        self.assertIn("margin: 0 0 0 auto;", bloco)

    def test_o_remover_nao_se_move_em_estado_nenhum(self):
        """Botão que se move sob o cursor é botão que se erra."""
        bloco = self._bloco(".search-picker__remove,")
        self.assertIn("transform: none;", bloco)
        self.assertIn("translate: none;", bloco)

    def test_o_anel_e_exclusivo_do_teclado(self):
        """O legado desenha `outline` no HOVER, e parecia foco."""
        self.assertIn(
            ".search-picker__remove:focus:not(:focus-visible)", self.css
        )
        self.assertIn(".search-picker__remove:focus-visible", self.css)
        anel = self._bloco(".search-picker__remove:focus-visible {")
        self.assertIn("border-radius: var(--radius-pill);", anel)

    def test_o_hover_do_remover_muda_so_a_cor(self):
        bloco = self._bloco(".search-picker__remove:hover {")
        self.assertIn("color: var(--danger);", bloco)
        self.assertNotIn("background", bloco)
        self.assertNotIn("border", bloco)
