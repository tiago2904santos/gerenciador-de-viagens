from django import forms

from .models import Evento, ModeloMotivoEvento

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


class ModeloMotivoSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        modelo = getattr(value, "instance", None)
        if modelo is None:
            return option

        option["attrs"].update(
            {
                "data-texto-motivo": (modelo.texto or "").strip(),
            },
        )
        return option


class EventoNovoCadastroForm(forms.ModelForm):
    modelo_motivo = forms.ModelChoiceField(
        label="Modelo de motivo",
        queryset=ModeloMotivoEvento.objects.none(),
        required=False,
        empty_label="Selecione um modelo (opcional)",
        widget=ModeloMotivoSelect(attrs={"class": "form-select", "data-modelo-motivo-select": "true"}),
    )
    tipo_outro = forms.CharField(
        label="Descreva o tipo",
        required=False,
        widget=forms.TextInput(attrs={"class": "cv-field__control", "placeholder": "Ex: Reunião interinstitucional"}),
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
            "tipo",
            "tipo_outro",
            "motivo",
            "data_inicio",
            "data_fim",
            "destino_uf",
            "destino_cidade",
        ]
        widgets = {
            "tipo": forms.Select(
                attrs={"class": "form-select", "data-tipo-evento-select": "true"},
                choices=[("", "Selecione o tipo")] + Evento.TIPO_CHOICES,
            ),
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
        self.fields["tipo"].required = False
        self.fields["data_inicio"].required = False
        self.fields["data_fim"].required = False
        self.fields["modelo_motivo"].queryset = ModeloMotivoEvento.objects.filter(ativo=True)
        # Populate tipo_outro from instance if available
        if self.instance and self.instance.pk:
            self.fields["tipo_outro"].initial = self.instance.tipo_outro

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
            "data_inicio": forms.DateInput(attrs={"class": "cv-field__control", "type": "date"}),
            "data_fim": forms.DateInput(attrs={"class": "cv-field__control", "type": "date"}),
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
