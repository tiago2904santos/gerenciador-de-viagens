import re
from pathlib import Path

from django import forms
from django.core.validators import FileExtensionValidator
from django.forms import modelformset_factory
from django.forms.renderers import TemplatesSetting

from core.normalizers import normalize_spaces

from .models import DiarioBordoTrecho
from .models import ModeloTextoRelatorioTecnico
from .models import PRESTACAO_DOCUMENTO_EXTENSOES
from .models import PrestacaoContas
from .models import PrestacaoDocumentoAnexo
from .models import RelatorioTecnico


ABASTECIMENTO_CHOICES = [
    ("sim", "Sim"),
    ("nao", "Não"),
]


class DiarioBordoTrechoForm(forms.ModelForm):
    """KM inicial/final e necessidade de abastecimento de um trecho do diário."""

    abastecimento = forms.ChoiceField(
        label="Necessidade de abastecimento",
        choices=ABASTECIMENTO_CHOICES,
        required=False,
        widget=forms.Select(),
    )
    km_inicial = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "cv-field__control",
                "inputmode": "numeric",
                "placeholder": "0",
                "autocomplete": "off",
                "data-mask": "milhar",
            },
        ),
    )
    km_final = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "cv-field__control",
                "inputmode": "numeric",
                "placeholder": "0",
                "autocomplete": "off",
                "data-mask": "milhar",
            },
        ),
    )

    class Meta:
        model = DiarioBordoTrecho
        fields = ["km_inicial", "km_final", "abastecimento"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            valor = getattr(self.instance, "abastecimento", None)
            # Padrão: "Sim" (inclusive quando ainda não preenchido).
            self.fields["abastecimento"].initial = "nao" if valor is False else "sim"

    def clean_abastecimento(self):
        return self.cleaned_data.get("abastecimento") != "nao"

    def _parse_km(self, campo):
        digitos = re.sub(r"\D", "", str(self.cleaned_data.get(campo) or ""))
        return int(digitos) if digitos else None

    def clean_km_inicial(self):
        return self._parse_km("km_inicial")

    def clean_km_final(self):
        return self._parse_km("km_final")


DiarioBordoTrechoFormSet = modelformset_factory(
    DiarioBordoTrecho,
    form=DiarioBordoTrechoForm,
    extra=0,
    can_delete=False,
)


# Campos de texto longo que recebem select de modelos + textarea (estilo "motivo" do ofício).
CAMPOS_COM_MODELO = [
    ("motivo", "Descrição do evento"),
    ("atividade", "Objetivo da participação"),
    ("conclusao", "Conclusão"),
    ("medidas", "Medidas a serem adotadas pelo órgão"),
    ("info_complementares", "Informações complementares"),
]


OUTRO_VALUE = "__outro__"
CAMPOS_CUSTEIO_COM_OUTRO = [
    ("translado", "Translado"),
    ("combustivel", "Combustível"),
    ("passagem", "Passagem"),
]
CUSTEIO_CHOICES = [
    ("", "Selecione"),
    ("Não houve", "Não houve"),
    ("Houve", "Houve"),
    ("Cartão Prime", "Cartão Prime"),
    (OUTRO_VALUE, "Outro"),
]
CUSTEIO_CHOICES_BY_FIELD = {
    "translado": [
        ("Não houve", "Não houve"),
        (OUTRO_VALUE, "Outro"),
    ],
    "combustivel": [
        ("Cartão Prime", "Cartão Prime"),
        (OUTRO_VALUE, "Outro"),
    ],
    "passagem": [
        ("Não houve", "Não houve"),
        (OUTRO_VALUE, "Outro"),
    ],
}
DEFAULT_CUSTEIO_VALUES = {
    "translado": "Não houve",
    "combustivel": "Cartão Prime",
    "passagem": "Não houve",
}
_CUSTEIO_VALORES_FIXOS = {
    campo: {
        value
        for value, _label in CUSTEIO_CHOICES_BY_FIELD.get(campo, CUSTEIO_CHOICES)
        if value and value != OUTRO_VALUE
    }
    for campo, _label in CAMPOS_CUSTEIO_COM_OUTRO
}


def get_custeio_choices(campo):
    return CUSTEIO_CHOICES_BY_FIELD.get(campo, CUSTEIO_CHOICES)


def get_custeio_valores_fixos(campo):
    return _CUSTEIO_VALORES_FIXOS.get(campo, set())


class ModeloTextoSelect(forms.Select):
    """Select que injeta o texto do modelo em cada <option> via data-attr."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        modelo = getattr(value, "instance", None)
        if modelo is not None:
            option["attrs"]["data-texto-modelo"] = (modelo.texto or "").strip()
        return option


class PrestacaoMultipleFileInput(forms.FileInput):
    allow_multiple_selected = True
    template_name = "prestacoes_contas/widgets/multiple_file_input.html"
    project_template_renderer = TemplatesSetting()

    def _render(self, template_name, context, renderer=None):
        return super()._render(template_name, context, self.project_template_renderer)


class PrestacaoMultipleFileField(forms.FileField):
    widget = PrestacaoMultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_file_clean(item, initial) for item in data]
        return [single_file_clean(data, initial)]


class PrestacaoDocumentosForm(forms.ModelForm):
    despacho_arquivos = PrestacaoMultipleFileField(
        label="Despacho assinado do ofício",
        required=False,
        validators=[FileExtensionValidator(PRESTACAO_DOCUMENTO_EXTENSOES)],
        help_text="Anexe PDF, PNG, JPG ou JPEG.",
        widget=PrestacaoMultipleFileInput(
            attrs={
                "class": "form-control cv-field__control prestacao-file-input",
                "accept": "application/pdf,image/png,image/jpeg,image/*",
            },
        ),
    )
    comprovante_arquivos = PrestacaoMultipleFileField(
        label="Comprovante de saque/transferência",
        required=False,
        validators=[FileExtensionValidator(PRESTACAO_DOCUMENTO_EXTENSOES)],
        help_text="Anexe PDF, PNG, JPG ou JPEG.",
        widget=PrestacaoMultipleFileInput(
            attrs={
                "class": "form-control cv-field__control prestacao-file-input",
                "accept": "application/pdf,image/png,image/jpeg,image/*",
            },
        ),
    )

    DOCUMENTO_TIPOS = {
        "despacho_arquivos": PrestacaoDocumentoAnexo.TIPO_DESPACHO,
        "comprovante_arquivos": PrestacaoDocumentoAnexo.TIPO_COMPROVANTE,
    }

    class Meta:
        model = PrestacaoContas
        fields = [
            "numero_solicitacao",
        ]
        labels = {
            "numero_solicitacao": "Número da solicitação",
            "despacho_assinado": "Despacho assinado do ofício",
            "comprovante_saque_transferencia": "Comprovante de saque/transferência",
        }
        help_texts = {
            "despacho_assinado": "Anexe PDF, PNG, JPG ou JPEG.",
            "comprovante_saque_transferencia": "Anexe PDF, PNG, JPG ou JPEG.",
        }
        widgets = {
            "numero_solicitacao": forms.TextInput(
                attrs={
                    "class": "form-control cv-field__control",
                    "placeholder": "Informe o número da solicitação",
                    "autocomplete": "off",
                },
            ),
        }

    def save(self, commit=True):
        prestacao = super().save(commit=commit)
        if commit:
            self.save_anexos(prestacao)
        return prestacao

    def save_anexos(self, prestacao):
        for field_name, tipo in self.DOCUMENTO_TIPOS.items():
            for arquivo in self.cleaned_data.get(field_name) or []:
                PrestacaoDocumentoAnexo.objects.create(
                    prestacao=prestacao,
                    tipo=tipo,
                    arquivo=arquivo,
                    nome_original=Path(getattr(arquivo, "name", "") or "").name,
                )


class PrestacaoSolicitacaoForm(forms.ModelForm):
    class Meta:
        model = PrestacaoContas
        fields = ["numero_solicitacao"]
        labels = {"numero_solicitacao": "Número da solicitação"}
        widgets = {
            "numero_solicitacao": forms.TextInput(
                attrs={
                    "class": "form-control cv-field__control",
                    "placeholder": "Número da solicitação",
                    "autocomplete": "off",
                },
            ),
        }


class RelatorioTecnicoForm(forms.ModelForm):
    translado_outro = forms.CharField(
        label="Translado - outro",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control cv-field__control", "data-rt-other-input": "translado"}),
    )
    combustivel_outro = forms.CharField(
        label="Combustível - outro",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control cv-field__control", "data-rt-other-input": "combustivel"}),
    )
    passagem_outro = forms.CharField(
        label="Passagem - outro",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control cv-field__control", "data-rt-other-input": "passagem"}),
    )

    class Meta:
        model = RelatorioTecnico
        fields = [
            "diaria",
            "translado",
            "combustivel",
            "passagem",
            "motivo",
            "atividade",
            "conclusao",
            "medidas",
            "info_complementares",
        ]
        labels = {
            "diaria": "Diária",
            "translado": "Translado",
            "combustivel": "Combustível",
            "passagem": "Passagem",
            "motivo": "Descrição do evento",
            "atividade": "Objetivo da participação",
            "conclusao": "Conclusão",
            "medidas": "Medidas a serem adotadas pelo órgão",
            "info_complementares": "Informações complementares",
        }
        help_texts = {
            "diaria": 'Ex.: "R$ 150,00" ou "não houve"',
            "translado": 'Ex.: "R$ 45,00" ou "não houve"',
            "combustivel": 'Ex.: "R$ 120,00" ou "não houve"',
            "passagem": 'Ex.: "R$ 280,00" ou "não houve"',
        }

    def __init__(self, *args, relatorio=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._relatorio = relatorio

        self.fields["diaria"].widget.attrs.setdefault("class", "form-control cv-field__control")
        for campo, label in CAMPOS_CUSTEIO_COM_OUTRO:
            self.fields[campo] = forms.ChoiceField(
                label=label,
                choices=get_custeio_choices(campo),
                required=False,
                widget=forms.Select(
                    attrs={
                        "class": "form-select",
                        "data-rt-other-select": campo,
                        "data-rt-other-value": OUTRO_VALUE,
                    },
                ),
            )
            self.fields[f"{campo}_outro"].widget.attrs.setdefault(
                "placeholder",
                f"Informe {label.lower()}",
            )
            self._set_initial_custeio_value(campo)

        # Textareas dos campos com modelo: classe padrão + data-attr para o JS encontrar.
        rows = {"motivo": 4, "atividade": 4, "conclusao": 4, "medidas": 3, "info_complementares": 3}
        for campo, _label in CAMPOS_COM_MODELO:
            self.fields[campo].required = False
            self.fields[campo].widget = forms.Textarea(
                attrs={
                    "class": "cv-field__control cv-field__control--textarea",
                    "rows": rows.get(campo, 4),
                    "data-rt-textarea": campo,
                },
            )

        # Um select de modelos por campo, filtrado por `campo`.
        for campo, label in CAMPOS_COM_MODELO:
            field_name = f"modelo_{campo}"
            field = forms.ModelChoiceField(
                label=f"Modelo de {label.lower()}",
                queryset=ModeloTextoRelatorioTecnico.objects.filter(campo=campo).order_by("ordem", "nome"),
                required=False,
                empty_label="Selecione um modelo (opcional)",
                widget=ModeloTextoSelect(
                    attrs={
                        "class": "form-select",
                        "data-rt-modelo-select": "true",
                        "data-rt-target": campo,
                    },
                ),
            )
            field.label_from_instance = lambda obj: obj.nome
            self.fields[field_name] = field

    def _set_initial_custeio_value(self, campo):
        if self.is_bound:
            return
        valor = normalize_spaces(self.initial.get(campo) or getattr(self.instance, campo, "") or "")
        if not valor:
            valor = DEFAULT_CUSTEIO_VALUES.get(campo, "")
        if not valor:
            return
        if valor in get_custeio_valores_fixos(campo):
            self.initial[campo] = valor
            return
        self.initial[campo] = OUTRO_VALUE
        self.initial[f"{campo}_outro"] = valor

    def clean(self):
        cleaned = super().clean()
        for campo, label in CAMPOS_CUSTEIO_COM_OUTRO:
            valor = cleaned.get(campo) or ""
            outro = normalize_spaces(cleaned.get(f"{campo}_outro") or "")
            if valor == OUTRO_VALUE:
                if not outro:
                    self.add_error(f"{campo}_outro", f"Informe o valor de {label.lower()}.")
                cleaned[campo] = outro
            else:
                cleaned[campo] = normalize_spaces(valor)
        return cleaned


class ModeloTextoRelatorioTecnicoForm(forms.ModelForm):
    campo = forms.ChoiceField(
        label="Campo do relatório",
        choices=ModeloTextoRelatorioTecnico.CAMPO_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    nome = forms.CharField(
        label="Nome",
        help_text="Use um nome curto para identificar o modelo.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    texto = forms.CharField(
        label="Texto do modelo",
        help_text="Este texto será copiado para o campo do relatório e poderá ser editado antes de gerar.",
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 6, "style": "width: 100%; height: 150px;"},
        ),
    )

    class Meta:
        model = ModeloTextoRelatorioTecnico
        fields = ["campo", "nome", "texto"]
