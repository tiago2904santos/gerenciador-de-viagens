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

import importlib
import inspect

from django import forms
from django.apps import apps
from django.test import SimpleTestCase
from django.test import TestCase

from core.forms.widgets import NOMES_SEM_MAIUSCULA
from core.forms.widgets import SEM_MAIUSCULA
from core.forms.widgets import WidgetStyle
from core.forms.widgets import aplicar_mascara_de_maiuscula
from core.forms.widgets import set_widget_style


def formularios_do_projeto():
    """Todo formulário declarado num módulo `forms` de app do projeto."""
    for config in apps.get_app_configs():
        if config.name.startswith("django."):
            continue
        try:
            modulo = importlib.import_module(f"{config.name}.forms")
        except ModuleNotFoundError:
            continue
        for objeto in vars(modulo).values():
            if not inspect.isclass(objeto):
                continue
            if not issubclass(objeto, forms.BaseForm):
                continue
            if objeto.__module__ != modulo.__name__:
                continue
            yield objeto


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


#: Formulários que legitimamente não instanciam sem argumento.
#:
#: Não são defeito, e por isso a lista é fechada em vez de o teste ignorar
#: qualquer falha: cada nome aqui é um campo que o inventário do
#: `normalizar_maiusculas` não enxerga, e a lista crescer é o sinal.
SEM_CONSTRUCAO_DIRETA = {
    # `PasswordChangeForm.__init__` exige o usuário. Todos os campos são
    # `PasswordInput`, protegidos pelo tipo.
    "core.forms.AlterarSenhaForm",
    # Base abstrata: `ModelForm` sem `Meta.model`. Não é usada como formulário.
    "cadastros.forms.BaseCadastroForm",
}


class MascaraNosFormulariosReaisTests(TestCase):
    """A regra vale onde o usuário digita, não só onde ela foi escrita.

    Todos os testes acima passavam enquanto `UsuarioEditForm` e
    `UsuarioAreaCreationForm` maiusculizavam `username` (`NOVO-56`). Eles
    chamavam `set_widget_style` iterando `self.fields.values()`, que descarta o
    nome do campo — e sem o nome, a exceção que protege o login nunca é
    consultada. O helper estava certo; a chamada é que perdia o argumento.

    Por isso este caso não testa a função: ele instancia os formulários do
    projeto e olha o atributo que vai para o HTML.
    """

    def test_nenhum_campo_mascarado_viola_a_regra(self):
        violacoes = []
        for classe in formularios_do_projeto():
            try:
                instancia = classe()
            except Exception:  # noqa: BLE001 - exige argumento; cai no caso abaixo
                continue
            for nome, campo in instancia.fields.items():
                if campo.widget.attrs.get("data-mask") != "upper":
                    continue
                alvo = f"{classe.__module__}.{classe.__name__}.{nome}"
                if nome in NOMES_SEM_MAIUSCULA:
                    violacoes.append(f"{alvo}: nome reservado")
                elif nome.endswith("_busca_ui"):
                    violacoes.append(f"{alvo}: campo de busca")
                elif isinstance(campo.widget, SEM_MAIUSCULA):
                    violacoes.append(f"{alvo}: {type(campo.widget).__name__}")
                elif not isinstance(campo.widget, forms.TextInput):
                    violacoes.append(
                        f"{alvo}: {type(campo.widget).__name__} não é campo de texto",
                    )
        self.assertEqual(violacoes, [], "\n".join(violacoes))

    def test_o_ponto_cego_da_inspecao_nao_cresce(self):
        """Formulário que não instancia é ponto cego — do teste e do inventário.

        O teste acima e o `normalizar_maiusculas` descobrem campos instanciando
        formulário. Um formulário que passe a exigir argumento no construtor
        sairia dos dois **em silêncio**: nenhum erro, só menos cobertura.

        Então o conjunto é fixado. Se crescer, o teste diz qual entrou, e a
        decisão de aceitá-lo (com o motivo) é de quem mexeu.
        """
        nao_lidos = set()
        for classe in formularios_do_projeto():
            try:
                classe()
            except Exception:  # noqa: BLE001 - só interessa que não instanciou
                nao_lidos.add(f"{classe.__module__}.{classe.__name__}")
        self.assertEqual(
            nao_lidos,
            SEM_CONSTRUCAO_DIRETA,
            "entraram: "
            f"{sorted(nao_lidos - SEM_CONSTRUCAO_DIRETA)}; "
            f"saíram: {sorted(SEM_CONSTRUCAO_DIRETA - nao_lidos)}",
        )
