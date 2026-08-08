"""Canonical CSS contracts for Django form widgets.

Form declarations choose a semantic style from :class:`WidgetStyle`; the
corresponding CSS class string is defined only in this module.
"""

from enum import StrEnum

from django.forms.widgets import EmailInput
from django.forms.widgets import NumberInput
from django.forms.widgets import PasswordInput
from django.forms.widgets import TextInput
from django.forms.widgets import URLInput
from django.forms.widgets import Widget


class WidgetStyle(StrEnum):
    """Exact, pre-P-04 class values emitted by the project's forms."""

    UNSTYLED = ""
    AUTH_FIELD_INPUT = "auth-field-input"
    FORM_CONTROL = "form-control"
    FORM_SELECT = "form-select"
    FIELD_CONTROL = "cv-field__control"
    SEARCH_PICKER_NATIVE = "cv-search-picker__native"
    FIELD_CONTROL_TEXTAREA = "cv-field__control cv-field__control--textarea"
    FORM_SELECT_SEARCH_PICKER = "form-select cv-search-picker__native"
    FORM_CONTROL_FIELD_CONTROL = "form-control cv-field__control"
    EVENT_DOCUMENT_SOURCE = "evento-doc-source-select"
    CARD_TOGGLE_SR_ONLY = "app-card-toggle__input sr-only"
    CARD_TOGGLE = "app-card-toggle__input"
    FORM_SELECT_FIELD_CONTROL = "form-select cv-field__control cv-field__control--select"
    FORM_SELECT_TERMS_PICKER = "form-select cv-search-picker__termos-native"
    SEARCH_PICKER_INPUT = "cv-search-picker__input"
    TERM_OFICIO_OS_SOURCE = "termo-oficio-source-select os-oficio-source-select"
    PT_PRESET_ACTIVITY_GRID = "pt-preset-activity-grid"
    PRESTACAO_FILE_INPUT = "form-control cv-field__control prestacao-file-input"
    TERM_OFICIO_SOURCE = "termo-oficio-source-select"


#: Widgets que NAO recebem a mascara de maiuscula.
#:
#: O dono pediu "tudo uppercase" e escolheu a mascara — que muda o VALOR, nao so
#: a aparencia. Entao a lista de excecoes nao e estetica, e de correcao:
#:
#: - `Textarea`  o proprio dono abriu a excecao: texto corrido aceita minuscula;
#: - `EmailInput` endereco de e-mail e case-insensitive no dominio mas NAO na
#:   parte local (RFC 5321 §2.4). Maiusculizar pode gerar endereco que nao existe;
#: - `URLInput`   caminho e query de URL sao case-sensitive na maioria dos
#:   servidores. `/Documentos` e `/documentos` sao coisas diferentes;
#: - `PasswordInput` maiusculizar senha destroi a senha;
#: - `NumberInput` nao tem letra; a mascara so custaria um listener por campo.
#: Subclasses de `TextInput` que NAO recebem a mascara. `Textarea` nao esta aqui
#: porque nem chega a ser testada: ela nao e `TextInput`, e a regra abaixo so
#: olha `TextInput`.
SEM_MAIUSCULA = (EmailInput, URLInput, PasswordInput, NumberInput)

#: Campos que nunca recebem a mascara, mesmo sendo texto simples.
#:
#: `username` e o caso que obriga esta lista a existir: a mascara reescreve o
#: valor DIGITADO, entao maiusculizar o campo de login faria o usuario enviar
#: "TIAGO" contra um registro gravado "tiago" — e o Django compara username
#: byte a byte. O sistema pararia de autenticar.
#:
#: Os de busca (`*_busca_ui`) nao sao persistidos: sao caixa de filtro, e
#: maiusculizar so atrapalharia quem digita.
NOMES_SEM_MAIUSCULA = frozenset({"username", "password", "email", "url"})


def aplicar_mascara_de_maiuscula(widget: Widget, nome: str = "") -> None:
    """Marca o widget para o motor de mascara maiusculizar o valor digitado.

    `static/js/components/masks.js` le `data-mask="upper"` e reescreve o valor
    enquanto se digita, entao o que chega ao banco ja vem em maiuscula.

    Dois apps ja faziam isto campo a campo (`cadastros/forms.py:65` e
    `oficios/forms.py:185`, ambos com `setdefault` sobre todo `CharField`); aqui
    a regra passa a valer para o sistema inteiro, num lugar so.

    `setdefault` de proposito: campo que ja declarou a propria mascara (`cep`,
    `cpf`, `telefone`) continua com a dele.
    """
    # So `TextInput` — e nao qualquer widget que nao esteja na lista de excecoes.
    #
    # A primeira versao invertia a pergunta ("nao esta na lista? entao marca"), e
    # com isso `Select`, `CheckboxInput` e `HiddenInput` ganhavam o atributo: 17
    # widgets, medidos. Nao quebrava nada — `masks.js` so liga em
    # `input[data-mask]` e `textarea[data-mask]`, entao o atributo ficava inerte
    # —, mas atributo inerte no HTML e exatamente o tipo de coisa que o proximo
    # leitor interpreta como contrato.
    if not isinstance(widget, TextInput) or isinstance(widget, SEM_MAIUSCULA):
        return
    if nome in NOMES_SEM_MAIUSCULA or nome.endswith("_busca_ui"):
        return
    widget.attrs.setdefault("data-mask", "upper")


def widget_attrs(style: WidgetStyle) -> dict[str, str]:
    """Build the canonical class attribute for a widget declaration."""

    return {"class": style.value}


def text_attrs(style: WidgetStyle) -> dict[str, str]:
    """`widget_attrs` mais a máscara de maiúscula, para campo de texto.

    Existe porque `widget_attrs` devolve um dicionário e **não sabe qual widget
    vai recebê-lo**: o mesmo estilo alimenta `TextInput`, `EmailInput` e
    `Textarea`. Decidir a máscara ali maiusculizaria e-mail e texto corrido.

    Então a escolha fica no ponto de declaração, e é explícita: quem escreve
    `text_attrs` está dizendo "este campo é texto simples e vai em maiúscula".
    Um revisor vê a decisão campo a campo, que é o que ela exige — a lista de
    exceções do `NOVO-53` não é estética, é corretude (`username` maiusculizado
    quebra a autenticação).
    """
    return {**widget_attrs(style), "data-mask": "upper"}


def set_widget_style(
    widget: Widget, style: WidgetStyle, *, overwrite: bool = True, nome: str = ""
) -> None:
    """Apply a canonical class to an existing widget.

    ``overwrite=False`` preserves the former ``dict.setdefault`` behavior used
    by forms that style model-generated widgets.
    """

    if overwrite:
        widget.attrs["class"] = style.value
    else:
        widget.attrs.setdefault("class", style.value)
    aplicar_mascara_de_maiuscula(widget, nome)
