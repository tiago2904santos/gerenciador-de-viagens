from django import forms

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
                    "class": "form-select cv-field__control cv-field__control--select",
                    "data-modelo-justificativa-select": "true",
                },
            ),
            "texto": forms.Textarea(
                attrs={
                    "class": "cv-field__control cv-field__control--textarea",
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


class ModeloJustificativaForm(forms.ModelForm):
    """Cadastro/edição de modelos reutilizáveis (espelha ModeloMotivoOficioForm)."""

    nome = forms.CharField(
        label="Nome",
        help_text="Use um nome curto para identificar o modelo.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    texto = forms.CharField(
        label="Texto do modelo",
        help_text="Este texto será copiado para a justificativa do ofício e poderá ser editado antes de salvar.",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}),
    )
    is_padrao = forms.BooleanField(
        label="Modelo padrão",
        required=False,
        help_text="Marque apenas se este modelo deve ser sugerido como principal.",
        widget=forms.CheckboxInput(attrs={"class": "app-card-toggle__input"}),
    )

    class Meta:
        model = ModeloJustificativa
        fields = ["nome", "texto", "is_padrao"]
