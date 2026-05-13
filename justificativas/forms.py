from django import forms

from .models import Justificativa
from .models import ModeloJustificativa
from .selectors import listar_modelos_justificativa


class JustificativaOficioForm(forms.ModelForm):
    """Formulário da etapa de justificativa no wizard do ofício."""

    class Meta:
        model = Justificativa
        fields = ("modelo", "texto")
        widgets = {
            "modelo": forms.Select(attrs={"class": "form-select app-form-control"}),
            "texto": forms.Textarea(
                attrs={
                    "class": "form-control app-form-control",
                    "rows": 8,
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
