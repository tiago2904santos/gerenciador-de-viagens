"""Formulario de demonstracao do UI Lab 2.0.

Reproduz, campo a campo, os mesmos widgets/classes usados nos cadastros reais
(ver eventos/forms.py) para que os clones de campo renderizem identicos aos do
sistema. Nao persiste nada; serve apenas para alimentar os previews de Campos,
Selects e Pickers.
"""

from django import forms
from core.forms.widgets import WidgetStyle
from core.forms.widgets import widget_attrs


UF_CHOICES = [
    ("", "Selecione..."),
    ("PR", "Parana"),
    ("SP", "Sao Paulo"),
    ("SC", "Santa Catarina"),
    ("RS", "Rio Grande do Sul"),
]

SERVIDOR_CHOICES = [
    ("1", "Ana Souza"),
    ("2", "Carlos Lima"),
    ("3", "Marina Alves"),
    ("4", "Paulo Reis"),
]


class UiLab2DemoForm(forms.Form):
    """Um campo por tipo de widget presente nos cadastros."""

    texto = forms.CharField(
        label="Campo de texto",
        required=False,
        initial="Operacao integrada",
        widget=forms.TextInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL)}),
    )
    texto_obrigatorio = forms.CharField(
        label="Campo obrigatorio",
        widget=forms.TextInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL)}),
    )
    descricao = forms.CharField(
        label="Area de texto",
        required=False,
        initial="Descricao longa para validar quebra de linha e leitura.",
        widget=forms.Textarea(
            attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL_TEXTAREA), "rows": 4}
        ),
    )
    data = forms.CharField(
        label="Data",
        required=False,
        widget=forms.TextInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL), "placeholder": "dd/mm/aaaa", "readonly": "readonly"}),
    )
    horario = forms.TimeField(
        label="Horario",
        required=False,
        widget=forms.TimeInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL), "type": "time"}),
    )
    url = forms.URLField(
        label="URL",
        required=False,
        widget=forms.URLInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL)}),
    )
    uf = forms.ChoiceField(
        label="Select simples",
        required=False,
        choices=UF_CHOICES,
        widget=forms.Select(attrs={**widget_attrs(WidgetStyle.FORM_SELECT)}),
    )
    servidores = forms.MultipleChoiceField(
        label="Multi-select",
        required=False,
        choices=SERVIDOR_CHOICES,
        widget=forms.SelectMultiple(attrs={**widget_attrs(WidgetStyle.FORM_SELECT)}),
    )
    aceite = forms.BooleanField(
        label="Confirmo os dados informados",
        required=False,
        help_text="Toggle/checkbox renderizado como card.",
    )
    motorista_ref = forms.CharField(
        label="Oficio do motorista",
        required=False,
        widget=forms.HiddenInput(),
    )
