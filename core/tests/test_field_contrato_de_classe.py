"""`D-41` — `field.html` tem de emitir UM contrato de classe, não três.

O componente escolhia classes diferentes por tipo de widget: `select` e
multiselect recebiam `field app-form-field cv-field` com rótulo
`app-form-label cv-field__label`; input de texto recebia só
`field app-form-field` com rótulo `app-form-label`. Consequência prática:
escrever CSS para "todo campo do sistema" era impossível — qualquer regra
precisava listar as duas variantes, e quem esquecia uma metade estilizava só
metade dos campos.

O `checkbox` fica **fora** do contrato de propósito: ele delega para
`card_toggle.html`, que é cartão clicável e não campo em grade.
"""

from django import forms
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class FormularioDeSonda(forms.Form):
    """Um campo de cada tipo que `field.html` trata por caminho diferente."""

    texto = forms.CharField(label="Texto")
    numero = forms.IntegerField(label="Número")
    data = forms.DateField(label="Data")
    escolha = forms.ChoiceField(label="Escolha", choices=[("a", "A")])
    varias = forms.MultipleChoiceField(
        label="Várias",
        choices=[("a", "A")],
        widget=forms.SelectMultiple,
    )
    marcado = forms.BooleanField(label="Marcado", required=False)


CONTAINER_ESPERADO = {"field", "app-form-field", "cv-field"}
ROTULO_ESPERADO = {"app-form-label", "cv-field__label"}

# `checkbox` sai por `card_toggle.html`: contrato deliberadamente diferente.
CAMPOS_EM_GRADE = ["texto", "numero", "data", "escolha", "varias"]


def _classes(html, marcador):
    """Classes do primeiro elemento cuja lista de classes contém `marcador`."""
    import re

    for match in re.finditer(r'class="([^"]*)"', html):
        classes = set(match.group(1).split())
        if marcador in classes:
            return classes
    return set()


class ContratoDeClasseDoFieldTests(SimpleTestCase):
    def setUp(self):
        self.form = FormularioDeSonda()

    def _render(self, nome):
        return render_to_string(
            "cotton/ui/forms/field.html",
            {"field": self.form[nome], "label": self.form[nome].label},
        )

    def test_todo_campo_em_grade_emite_o_mesmo_contrato_de_container(self):
        contratos = {}
        for nome in CAMPOS_EM_GRADE:
            html = self._render(nome)
            contratos[nome] = _classes(html, "field") & CONTAINER_ESPERADO

        self.assertEqual(
            contratos,
            {nome: CONTAINER_ESPERADO for nome in CAMPOS_EM_GRADE},
            "tipos de widget diferentes ainda emitem contratos de container diferentes",
        )

    def test_todo_rotulo_em_grade_emite_o_mesmo_contrato(self):
        contratos = {}
        for nome in CAMPOS_EM_GRADE:
            html = self._render(nome)
            contratos[nome] = _classes(html, "app-form-label") & ROTULO_ESPERADO

        self.assertEqual(
            contratos,
            {nome: ROTULO_ESPERADO for nome in CAMPOS_EM_GRADE},
            "tipos de widget diferentes ainda emitem contratos de rótulo diferentes",
        )

    def test_o_checkbox_segue_por_card_toggle_e_fica_fora_do_contrato(self):
        """Documentado, não esquecido: cartão clicável não é campo em grade."""
        html = self._render("marcado")

        self.assertIn("app-card-toggle", html)
        self.assertNotIn("cv-field__label", html)

    def test_o_size_class_continua_indo_para_o_container(self):
        """`size_class` é como as páginas controlam largura na grade — não pode sumir."""
        for nome in CAMPOS_EM_GRADE:
            with self.subTest(campo=nome):
                html = render_to_string(
                    "cotton/ui/forms/field.html",
                    {"field": self.form[nome], "size_class": "field-size-4"},
                )
                self.assertIn("field-size-4", html)
