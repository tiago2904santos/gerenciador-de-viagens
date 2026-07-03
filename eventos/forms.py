from django import forms

from cadastros.models import ConfiguracaoSistema
from oficios.forms import ModeloMotivoSelect
from oficios.models import ModeloMotivoOficio

from .models import Evento
from .models import TipoEvento

_ESTADOS_CHOICES = [
    ("", "Selecione o estado"),
    ("AC", "Acre (AC)"),
    ("AL", "Alagoas (AL)"),
    ("AP", "Amapá (AP)"),
    ("AM", "Amazonas (AM)"),
    ("BA", "Bahia (BA)"),
    ("CE", "Ceará (CE)"),
    ("DF", "Distrito Federal (DF)"),
    ("ES", "Espírito Santo (ES)"),
    ("GO", "Goiás (GO)"),
    ("MA", "Maranhão (MA)"),
    ("MT", "Mato Grosso (MT)"),
    ("MS", "Mato Grosso do Sul (MS)"),
    ("MG", "Minas Gerais (MG)"),
    ("PA", "Pará (PA)"),
    ("PB", "Paraíba (PB)"),
    ("PR", "Paraná (PR)"),
    ("PE", "Pernambuco (PE)"),
    ("PI", "Piauí (PI)"),
    ("RJ", "Rio de Janeiro (RJ)"),
    ("RN", "Rio Grande do Norte (RN)"),
    ("RS", "Rio Grande do Sul (RS)"),
    ("RO", "Rondônia (RO)"),
    ("RR", "Roraima (RR)"),
    ("SC", "Santa Catarina (SC)"),
    ("SP", "São Paulo (SP)"),
    ("SE", "Sergipe (SE)"),
    ("TO", "Tocantins (TO)"),
]


class EventoNovoCadastroForm(forms.ModelForm):
    modelo_motivo = forms.ModelChoiceField(
        label="Modelo de motivo",
        queryset=ModeloMotivoOficio.objects.none(),
        required=False,
        empty_label="Selecione um modelo (opcional)",
        widget=ModeloMotivoSelect(attrs={"class": "form-select", "data-modelo-motivo-select": "true"}),
    )
    tipos = forms.ModelMultipleChoiceField(
        label="Tipo do evento",
        queryset=TipoEvento.objects.filter(ativo=True).order_by("ordem", "nome"),
        required=False,
        widget=forms.SelectMultiple(attrs={"data-placeholder": "Selecione o(s) tipo(s)"}),
    )
    destino_uf = forms.ChoiceField(
        label="Estado",
        choices=_ESTADOS_CHOICES,
        required=False,
        widget=forms.Select(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-placeholder": "Buscar estado...",
                "data-empty-message": "Nenhum estado encontrado.",
            }
        ),
    )

    class Meta:
        model = Evento
        fields = [
            "tipos",
            "motivo",
            "data_inicio",
            "data_fim",
            "destino_uf",
            "destino_cidade",
        ]
        widgets = {
            "motivo": forms.Textarea(
                attrs={
                    "class": "cv-field__control cv-field__control--textarea",
                    "rows": 4,
                    "data-motivo-textarea": "true",
                }
            ),
            "data_inicio": forms.HiddenInput(attrs={"data-cv-date-picker-start-value": ""}),
            "data_fim": forms.HiddenInput(attrs={"data-cv-date-picker-end-value": ""}),
            "destino_cidade": forms.Select(
                choices=[("", "---------")],
                attrs={
                    "class": "cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "compact",
                    "data-placeholder": "Buscar cidade...",
                    "data-empty-message": "Nenhuma cidade encontrada.",
                    "data-destino-cidade-picker": "true",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_inicio"].required = False
        self.fields["data_fim"].required = False
        self.fields["modelo_motivo"].queryset = ModeloMotivoOficio.objects.filter(ativo=True).order_by(
            "ordem", "nome"
        )
        # Pré-preenche a UF de destino com o estado padrão das configurações (eventos sem destino definido)
        if not self.is_bound and not (self.instance and self.instance.destino_uf):
            uf_padrao = ConfiguracaoSistema.get_singleton().uf
            if uf_padrao:
                self.initial["destino_uf"] = uf_padrao

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")
        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        return cleaned


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            "titulo",
            "descricao",
            "destino_uf",
            "destino_cidade",
            "data_inicio",
            "data_fim",
            "horario_inicio",
            "horario_fim",
            "unidade_responsavel",
            "responsavel",
            "status",
            "drive_folder_url",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "cv-field__control"}),
            "descricao": forms.Textarea(attrs={"class": "cv-field__control cv-field__control--textarea", "rows": 4}),
            "destino_uf": forms.TextInput(attrs={"class": "cv-field__control", "maxlength": 2}),
            "destino_cidade": forms.TextInput(attrs={"class": "cv-field__control"}),
            "data_inicio": forms.HiddenInput(attrs={"data-cv-date-picker-start-value": ""}),
            "data_fim": forms.HiddenInput(attrs={"data-cv-date-picker-end-value": ""}),
            "horario_inicio": forms.TimeInput(attrs={"class": "cv-field__control", "type": "time"}),
            "horario_fim": forms.TimeInput(attrs={"class": "cv-field__control", "type": "time"}),
            "unidade_responsavel": forms.Select(attrs={"class": "form-select"}),
            "responsavel": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "drive_folder_url": forms.URLInput(attrs={"class": "cv-field__control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidade_responsavel"].required = False
        self.fields["responsavel"].required = False

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")
        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        destino_uf = (cleaned.get("destino_uf") or "").strip().upper()
        if destino_uf and len(destino_uf) != 2:
            self.add_error("destino_uf", "Informe a UF com 2 caracteres.")
        cleaned["destino_uf"] = destino_uf
        return cleaned


class TipoEventoForm(forms.ModelForm):
    nome = forms.CharField(
        label="Nome",
        help_text="Ex.: PCPR na Comunidade, Justiça no Bairro.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    ativo = forms.BooleanField(
        label="Ativo",
        required=False,
        initial=True,
        help_text="Desmarque para ocultar este tipo da seleção sem apagar eventos já vinculados.",
        widget=forms.CheckboxInput(attrs={"class": "app-card-toggle__input"}),
    )

    class Meta:
        model = TipoEvento
        fields = ["nome", "ativo"]
