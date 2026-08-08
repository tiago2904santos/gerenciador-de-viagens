"""A máscara de maiúscula muda o DADO, não a aparência (`NOVO-53`).

O dono pediu "tudo uppercase" nos campos e escolheu, entre duas opções, a que
reescreve o valor digitado — não `text-transform`. A diferença importa: o que
chega ao banco vem em maiúscula, e o documento gerado sai igual à tela.

Como a regra mexe em dado, ela precisa de exceções, e as exceções precisam de
teste. Uma delas não é preferência estética, é corretude:

    `username` maiusculizado faz o usuário enviar "TIAGO" contra um registro
    gravado "tiago". O Django compara byte a byte. O sistema para de autenticar.

As outras seguem o mesmo princípio — maiusculizar destrói informação:

  senha      vira outra senha;
  e-mail     a parte local é case-sensitive (RFC 5321 §2.4);
  URL        caminho e query são case-sensitive na maioria dos servidores;
  textarea   é a exceção que o próprio dono abriu: texto corrido aceita as duas.
"""

from __future__ import annotations

from django import forms
from django.test import SimpleTestCase

from core.forms.widgets import WidgetStyle
from core.forms.widgets import aplicar_mascara_de_maiuscula
from core.forms.widgets import set_widget_style


class MascaraDeMaiusculaTests(SimpleTestCase):
    def test_campo_de_texto_comum_recebe_a_mascara(self):
        widget = forms.TextInput()

        set_widget_style(widget, WidgetStyle.FORM_CONTROL)

        self.assertEqual(widget.attrs.get("data-mask"), "upper")

    def test_username_nao_recebe_a_mascara(self):
        """A exceção que existe para o sistema continuar autenticando."""
        widget = forms.TextInput()

        set_widget_style(widget, WidgetStyle.FORM_CONTROL, nome="username")

        self.assertIsNone(widget.attrs.get("data-mask"))

    def test_so_text_input_recebe(self):
        """`Select`, `CheckboxInput` e `HiddenInput` não são campo de texto.

        A primeira versão da regra invertia a pergunta — "não está na lista de
        exceções? então marca" — e com isso 17 widgets ganhavam o atributo. Não
        quebrava nada, porque `masks.js` só liga em `input[data-mask]` e
        `textarea[data-mask]`. Mas atributo inerte no HTML é exatamente o que o
        próximo leitor interpreta como contrato.
        """
        for widget in (forms.Select(), forms.CheckboxInput(), forms.HiddenInput()):
            with self.subTest(widget=type(widget).__name__):
                set_widget_style(widget, WidgetStyle.FORM_CONTROL)
                self.assertIsNone(widget.attrs.get("data-mask"))

    def test_widgets_que_nunca_recebem(self):
        for widget in (
            forms.Textarea(),
            forms.EmailInput(),
            forms.URLInput(),
            forms.PasswordInput(),
            forms.NumberInput(),
        ):
            with self.subTest(widget=type(widget).__name__):
                set_widget_style(widget, WidgetStyle.FORM_CONTROL)
                self.assertIsNone(widget.attrs.get("data-mask"))

    def test_campo_de_busca_nao_recebe(self):
        """`*_busca_ui` é caixa de filtro, não valor persistido."""
        widget = forms.TextInput()

        aplicar_mascara_de_maiuscula(widget, "transporte_busca_ui")

        self.assertIsNone(widget.attrs.get("data-mask"))

    def test_mascara_declarada_pelo_campo_tem_precedencia(self):
        """`cep`, `cpf` e `telefone` têm máscara própria e a mantêm.

        É `setdefault`, não atribuição: sobrescrever trocaria a formatação do
        CEP por maiúscula, num campo que só tem dígitos.
        """
        widget = forms.TextInput(attrs={"data-mask": "cep"})

        set_widget_style(widget, WidgetStyle.FORM_CONTROL)

        self.assertEqual(widget.attrs.get("data-mask"), "cep")

    def test_o_motor_de_mascara_conhece_upper(self):
        """A regra do Python só vale se o JS souber o que fazer com ela.

        Sem esta asserção, `data-mask="upper"` poderia ser espalhado por todo o
        sistema apontando para um modo que o motor não implementa — e nada
        falharia: o atributo ficaria no HTML, inerte.
        """
        from pathlib import Path

        from django.conf import settings

        motor = (
            Path(settings.BASE_DIR) / "static" / "js" / "components" / "masks.js"
        ).read_text(encoding="utf-8")

        self.assertIn("upper:", motor)
