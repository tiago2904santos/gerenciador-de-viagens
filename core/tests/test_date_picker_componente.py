"""O campo de data v2 é um componente fechado, e continua funcionando.

`<c-v2.date_picker />` entrega campo, calendário, abertura em um clique e o
painel vestido pelo sistema. Nada disso está num lugar só: a marcação vem do
partial global, o comportamento de dois motores JS e a aparência de
`static/css/v2/date-picker.css`. É exatamente o tipo de peça que se desfaz aos
poucos, porque cada arquivo, lido sozinho, parece correto.

Cada asserção aqui existe por causa de um defeito que já aconteceu nesta
sessão, e nenhum deles dava erro em lugar nenhum — a página renderizava e o
campo só parava de responder, ou aparecia torto.
"""

from __future__ import annotations

import re
from pathlib import Path

from django.template import Context, Template
from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[2]
CSS = ROOT / "static" / "css" / "v2" / "date-picker.css"
JS = ROOT / "static" / "js" / "components" / "date-picker.js"
COMPONENTE = ROOT / "templates" / "cotton" / "v2" / "date_picker.html"


def render(source: str, **contexto) -> str:
    return Template("{% load cotton %}" + source).render(Context(contexto))


class MarcacaoTests(SimpleTestCase):
    def test_o_componente_delega_ao_partial_global(self):
        """Recriar o markup aqui reintroduz a divergência que o partial evita.

        Foi o que a primeira versão deste componente fez, e o
        `test_calendar_markup_exists_only_in_the_global_partial` pegou.
        """
        fonte = COMPONENTE.read_text(encoding="utf-8")
        self.assertIn("<c-ui.forms.date_picker", fonte)
        self.assertNotIn("data-cv-date-picker-days", fonte)
        self.assertNotIn("data-cv-date-picker-panel", fonte)

    def test_o_involucro_v2_existe(self):
        """`.date-field` é a raiz que a folha v2 usa para não alcançar o legado."""
        self.assertIn('class="date-field"', render("{% cotton v2.date_picker only / %}"))

    def test_modo_intervalo_entrega_os_dois_campos(self):
        html = render('{% cotton v2.date_picker mode="range" only / %}')
        self.assertIn("data-cv-date-picker-start-display", html)
        self.assertIn("data-cv-date-picker-end-display", html)


class ComportamentoTests(SimpleTestCase):
    """O JS que faz o campo responder."""

    def setUp(self):
        self.js = JS.read_text(encoding="utf-8")

    def test_abre_no_clique_e_nao_so_no_foco(self):
        """Abrir no `focus` sozinho fazia o primeiro clique abrir E fechar.

        O painel nascia embaixo do cursor antes do `mouseup`, o `click` era
        disparado no ancestral comum — o `body` — e o guarda de clique-fora
        fechava. Só o segundo clique funcionava.
        """
        self.assertIn("function bindAbertura", self.js)
        self.assertIn("focoVeioDoPonteiro", self.js)

    def test_o_painel_transplantado_leva_a_marca_do_v2(self):
        """Ele vai para o `body` e perde os ancestrais.

        Sem a marca, as regras do v2 alcançariam o calendário das telas ainda
        não migradas, que dividem o mesmo partial.
        """
        self.assertIn("date-field__panel", self.js)


class AparenciaTests(SimpleTestCase):
    """As regras que a folha precisa declarar, e o que ela não pode ter."""

    def setUp(self):
        self.css = CSS.read_text(encoding="utf-8")
        self.sem_comentario = re.sub(r"/\*.*?\*/", "", self.css, flags=re.DOTALL)

    def test_nao_usa_cor_literal(self):
        """Cor literal aqui é cor que não acompanha a troca de tema."""
        literais = re.findall(
            r"#[0-9a-fA-F]{3,8}\b|\brgba?\([^)]*\)", self.sem_comentario
        )
        self.assertEqual(literais, [], "use os tokens de `v2/tokens.css`")

    def test_a_borda_do_painel_e_a_do_sistema(self):
        """O calendário usava um traço próprio, diferente em cada tema."""
        self.assertIn("border: 1px solid var(--line);", self.sem_comentario)

    def test_os_botoes_do_painel_usam_a_altura_miuda(self):
        """Quatro botões de 44px ocupavam mais que o mês que eles navegam."""
        self.assertIn("min-height: var(--control-height-sm);", self.sem_comentario)

    def test_a_grade_dos_dias_nao_tem_vao(self):
        """Com vão, um intervalo longo vira listra em vez de faixa."""
        grade = self.sem_comentario[self.sem_comentario.index("data-cv-date-picker-days") :]
        self.assertIn("gap: 0;", grade)

    def test_o_realce_do_dia_se_ancora_na_celula(self):
        """O legado o posiciona pelo centro com deslocamento FIXO.

        Os dois só se cancelam quando metade da célula é inteira; fora disso
        sobra fração, e num intervalo longo as sobras somam e a grade parece
        ter colunas de larguras diferentes.
        """
        realce = self.sem_comentario[self.sem_comentario.index("date-picker__day::before") :]
        self.assertIn("inset: 0;", realce)
        self.assertIn("transform: none;", realce)

    def test_o_sumario_nao_aparece(self):
        """Ele repetia em texto o que os dois campos já mostram."""
        self.assertIn("date-picker__summary", self.sem_comentario)

    def test_nenhuma_regra_usa_important(self):
        """Exceto o `outline`, que é a única forma de dispensar o anel global.

        `base/base.css` impõe o anel de foco a todo controle com `!important`,
        como garantia de acessibilidade. A borda acesa cumpre a mesma função.
        """
        usos = re.findall(r"([a-z-]+)\s*:[^;]*!important", self.sem_comentario)
        self.assertEqual(set(usos) - {"outline"}, set())
