from django import forms

from core.forms.widgets import WidgetStyle
from core.forms.widgets import widget_attrs
from oficios.models import Oficio

from .models import Justificativa
from .models import ModeloJustificativa
from .selectors import listar_modelos_justificativa


class OficioJustificativaSelectMultiple(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        oficio = getattr(value, "instance", None)
        if oficio is None:
            return option

        numero = f"Oficio {oficio.numero_formatado}"
        protocolo = oficio.protocolo or ""
        assunto = oficio.assunto or ""
        data = oficio.data_criacao.strftime("%d/%m/%Y") if oficio.data_criacao else ""
        search = " ".join(part for part in [numero, protocolo, assunto, data, str(oficio.pk)] if part)
        option["label"] = " - ".join(part for part in [numero, protocolo] if part)
        option["attrs"].update(
            {
                "data-main": numero,
                "data-cargo": " - ".join(part for part in [protocolo, data] if part),
                "data-meta": assunto,
                "data-search": search,
            },
        )
        return option


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
                    **widget_attrs(WidgetStyle.FIELD_CONTROL_TEXTAREA),
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
        label="Oficios",
        queryset=Oficio.objects.none(),
        required=True,
        widget=OficioJustificativaSelectMultiple(
            attrs={
                **widget_attrs(WidgetStyle.FORM_SELECT_SEARCH_PICKER),
                "data-entity-picker": "true",
                "data-entity-picker-mode": "multi",
                "data-picker-variant": "detailed",
                "data-picker-label": "Oficios",
                "data-panel-title": "OFICIOS DA JUSTIFICATIVA",
                "data-placeholder": "Buscar por numero, protocolo ou assunto",
                "data-empty-message": "Nenhum oficio encontrado.",
                "data-empty-selected": "Nenhum oficio selecionado.",
            },
        ),
    )
    modelo = forms.ModelChoiceField(
        label="Modelo",
        queryset=ModeloJustificativa.objects.none(),
        required=False,
        empty_label="Selecione um modelo (opcional)",
        widget=ModeloJustificativaSelect(
            attrs={
                **widget_attrs(WidgetStyle.FORM_SELECT_FIELD_CONTROL),
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
                "rows": 6,
                "placeholder": "",
                "data-justificativa-textarea": "true",
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["oficios"].queryset = Oficio.objects.order_by("-data_criacao", "-created_at")
        self.fields["modelo"].queryset = listar_modelos_justificativa()

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
        widget=forms.TextInput(attrs={**widget_attrs(WidgetStyle.FORM_CONTROL)}),
    )
    texto = forms.CharField(
        label="Texto do modelo",
        help_text="Este texto será copiado para a justificativa do ofício e poderá ser editado antes de salvar.",
        widget=forms.Textarea(attrs={**widget_attrs(WidgetStyle.FORM_CONTROL), "rows": 4}),
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
