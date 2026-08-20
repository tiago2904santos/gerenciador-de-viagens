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

DIVISA = "/* === DELTA v2 === */"


def delta(caminho: Path) -> str:
    """A metade v2 da folha — o que vem depois da divisa.

    As folhas do v2 passaram a guardar a BASE do componente junto com o delta
    (fusão de 2026-08-20, que apagou a pasta `fields/`). Sem o corte, cada
    asserção daqui encontra primeiro a regra base que o delta sobrescreve — e
    reprova descrevendo corretamente o que a tela mostra.
    """
    texto = caminho.read_text(encoding="utf-8")
    return texto[texto.index(DIVISA) + len(DIVISA) :]



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
        self.assertRegex(html, r'<option\s+value="1"[^>]*>Um</option>')

    def test_a_segunda_linha_viaja_nos_dois_atributos_que_o_motor_le(self):
        """Padrão lê `data-meta`; "people"/"vehicle" montam de `data-cargo`.

        Mandando só `data-meta`, a variação de duas linhas renderizava certinho
        e mostrava o texto genérico ("Servidor cadastrado") no lugar do dado.
        """
        html = render(
            '{% cotton v2.picker name="x" presentation="people" :options="opcoes" only / %}',
            opcoes=[{"value": "1", "label": "Um", "meta": "Agente • 1ª DP"}],
        )
        self.assertIn('data-meta="Agente • 1ª DP"', html)
        self.assertIn('data-cargo="Agente • 1ª DP"', html)
        self.assertIn('data-picker-presentation="people"', html)
        self.assertIn('data-picker-variant="detailed"', html)


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
        self.css = re.sub(r"/\*.*?\*/", "", delta(CSS), flags=re.DOTALL)

    def _bloco(self, marca: str) -> str:
        i = self.css.index(marca)
        return self.css[i : self.css.index("}", i)]

    def test_nao_usa_cor_literal(self):
        literais = re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)", self.css)
        self.assertEqual(literais, [], "use os tokens de `v2/tokens.css`")

    def test_o_campo_de_busca_nao_tem_sombra(self):
        """O legado punha relevo só neste campo, e em nenhum outro do sistema."""
        self.assertIn("box-shadow: none;", self._bloco(".search-picker__control {"))

    def test_a_caixa_dos_escolhidos_nao_desenha_nada(self):
        """Quem faz o box é o `form_block` em volta.

        Enquanto o painel tinha caixa própria, era caixa dentro de caixa: dois
        raios, dois recuos e duas superfícies para uma seção só.
        """
        bloco = self._bloco(".search-picker__selected-panel {")
        self.assertIn("background: none;", bloco)
        self.assertIn("border: 0;", bloco)
        self.assertIn("border-radius: 0;", bloco)
        self.assertIn("padding: 0;", bloco)

    def test_o_cabecalho_dos_escolhidos_sai_junto(self):
        """O título do `form_block` já nomeia a seção; repetir dizia duas vezes."""
        bloco = self._bloco(".search-picker__selected-header {")
        self.assertIn("display: none;", bloco)

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

    def test_a_apresentacao_detalhada_nao_desenha_caixa_propria(self):
        """O legado cerca pessoas e veículos com fundo e contorno TRACEJADO.

        É herança de quando o campo era uma área de soltar. No v2 quem faz a
        caixa é o `form_block` em volta, e o tracejado aparecia como um
        retângulo pontilhado dentro de outro retângulo.
        """
        bloco = self._bloco(".picker .search-picker--detailed,")
        self.assertIn("border: 0;", bloco)
        self.assertIn("background: none;", bloco)
        self.assertIn("padding: 0;", bloco)
        # As combinações exatas do legado: um seletor mais curto empata e perde.
        self.assertIn(".search-picker--people.search-picker--roster", self.css)
        self.assertIn(".search-picker--vehicle", self.css)

    def test_o_escolhido_detalhado_usa_a_superficie_do_sistema(self):
        """O legado descreve pessoa e veículo com uma classe A MAIS e vencia.

        O cartão saía com o fundo do próprio bloco — sem se destacar de nada —,
        raio de 12px que não é o do sistema e uma grade de coluna fixa.
        """
        bloco = self._bloco(
            ".picker .search-picker--people.search-picker--roster .search-picker__selected-card,"
        )
        self.assertIn("background: var(--surface-contrast, var(--surface-rail));", bloco)
        self.assertIn("border-radius: var(--radius-field);", bloco)
        self.assertIn("border: 0;", bloco)
        self.assertIn("min-height: var(--escolhido-height);", bloco)

    def test_o_remover_do_escolhido_detalhado_nao_tem_divisoria(self):
        """A linha vertical fazia o cartão parecer tabela de duas células."""
        bloco = self._bloco(
            ".search-picker__selected-actions .search-picker__remove,"
        )
        self.assertIn("border: 0;", bloco)
        self.assertIn("height: var(--control-height-sm);", bloco)
        self.assertIn("border-radius: var(--radius-pill);", bloco)

    def test_a_ancora_do_escolhido_e_a_mesma_da_opcao(self):
        """O item que se escolhe e o que fica escolhido são a mesma coisa.

        O contorno vinha de uma regra legada, num azul que não era o accent do
        tema — e por isso não acompanhava a troca.
        """
        bloco = self._bloco(".search-picker__selected-avatar {")
        self.assertIn(
            "border: 1px solid color-mix(in srgb, var(--accent) 32%, transparent);", bloco
        )
        self.assertIn(
            "background: color-mix(in srgb, var(--accent) 16%, transparent);", bloco
        )
        self.assertIn("color: var(--accent);", bloco)
