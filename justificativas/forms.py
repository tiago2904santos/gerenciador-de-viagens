from django import forms
from django.urls import reverse_lazy

from core.forms.widgets import WidgetStyle
from core.forms.widgets import widget_attrs
from core.forms.widgets import text_attrs
from core.tenancy import filter_queryset_by_area
from oficios.models import Oficio
from oficios.picker import renderizar_so_os_escolhidos

from .models import Justificativa
from .models import ModeloJustificativa
from .selectors import listar_modelos_justificativa


class ModeloJustificativaSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        modelo = getattr(value, "instance", None)
        if modelo is None:
            return option

        option["attrs"].update(
            {
                "data-texto-justificativa": (modelo.texto or "").strip(),
            },
        )
        return option


class JustificativaOficioForm(forms.ModelForm):
    """Formulário da etapa de justificativa no wizard do ofício."""

    class Meta:
        model = Justificativa
        fields = ("modelo", "texto")
        widgets = {
            "modelo": ModeloJustificativaSelect(
                attrs={
                    **widget_attrs(WidgetStyle.FORM_SELECT_FIELD_CONTROL),
                    "data-modelo-justificativa-select": "true",
                },
            ),
            "texto": forms.Textarea(
                attrs={
                    **widget_attrs(WidgetStyle.INPUT_V2_TEXTAREA),
                    "rows": 6,
                    "placeholder": "",
                    "data-justificativa-textarea": "true",
                }
            ),
        }

    def __init__(self, *args, obrigatoria=False, **kwargs):
        super().__init__(*args, **kwargs)
        self._obrigatoria = obrigatoria
        self.fields["modelo"].required = False
        self.fields["modelo"].queryset = listar_modelos_justificativa()
        self.fields["modelo"].empty_label = "Selecione um modelo (opcional)"
        self.fields["texto"].required = False

    def clean_texto(self):
        texto = (self.cleaned_data.get("texto") or "").strip()
        if self._obrigatoria and not texto:
            raise forms.ValidationError("Informe o texto da justificativa.")
        return texto


class JustificativaQuickAddForm(forms.Form):
    oficios = forms.ModelMultipleChoiceField(
        label="Ofícios",
        queryset=Oficio.objects.none(),
        required=True,
        widget=forms.SelectMultiple(
            attrs={
                **widget_attrs(WidgetStyle.TERM_OFICIO_SOURCE),
                "hidden": True,
                "data-source-document": "justificativas-oficios-summary",
                # `NOVO-07`: liga o modo remoto do picker. Sem este atributo ele
                # segue filtrando só o que está no DOM, como antes.
                "data-picker-source-url": reverse_lazy("justificativas:api_buscar_oficios"),
            },
        ),
    )
    modelo = forms.ModelChoiceField(
        label="Modelo de justificativa",
        queryset=ModeloJustificativa.objects.none(),
        required=False,
        empty_label="Selecione um modelo (opcional)",
        widget=ModeloJustificativaSelect(
            attrs={
                **widget_attrs(WidgetStyle.FORM_SELECT),
                "data-modelo-justificativa-select": "true",
            },
        ),
    )
    texto = forms.CharField(
        label="Justificativa",
        required=True,
        widget=forms.Textarea(
            attrs={
                **widget_attrs(WidgetStyle.FIELD_CONTROL_TEXTAREA),
                "rows": 4,
                "placeholder": "",
                "data-justificativa-textarea": "true",
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Sem o recorte, o campo aceitava ofício de outra área e dava para
        # **criar** justificativa cruzando a fronteira — não é só exibição
        # (`NOVO-06`). `ordens_servico/forms.py:201` e `termos/forms.py:124`
        # já faziam assim; justificativas era a exceção.
        campo = self.fields["oficios"]
        campo.queryset = filter_queryset_by_area(Oficio.objects).order_by("-created_at", "-pk")
        self.fields["modelo"].queryset = listar_modelos_justificativa()

        # `NOVO-07`: o campo **aceita** qualquer ofício da área (o `queryset`
        # acima, que é o que valida o pk vindo do picker) mas **renderiza** só o
        # que já está selecionado. Antes um `<option>` por ofício da área ia para
        # o HTML, e a página crescia com a tabela. A ordem importa, e o porquê
        # está em `oficios/picker.py`.
        renderizar_so_os_escolhidos(self, "oficios")

    def clean_texto(self):
        texto = (self.cleaned_data.get("texto") or "").strip()
        if not texto:
            raise forms.ValidationError("Informe o texto da justificativa.")
        return texto


class ModeloJustificativaForm(forms.ModelForm):
    """Cadastro/edição de modelos reutilizáveis (espelha ModeloMotivoOficioForm)."""

    nome = forms.CharField(
        label="Nome",
        help_text="Use um nome curto para identificar o modelo.",
        widget=forms.TextInput(attrs={**text_attrs(WidgetStyle.FORM_CONTROL)}),
    )
    texto = forms.CharField(
        label="Texto do modelo",
        help_text="Este texto será copiado para a justificativa do ofício e poderá ser editado antes de salvar.",
        widget=forms.Textarea(attrs={**widget_attrs(WidgetStyle.INPUT_V2_TEXTAREA), "rows": 4}),
    )
    is_padrao = forms.BooleanField(
        label="Modelo padrão",
        required=False,
        help_text="Marque apenas se este modelo deve ser sugerido como principal.",
        widget=forms.CheckboxInput(attrs={**widget_attrs(WidgetStyle.CARD_TOGGLE)}),
    )

    class Meta:
        model = ModeloJustificativa
        fields = ["nome", "texto", "is_padrao"]
