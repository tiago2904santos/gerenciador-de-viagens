from django import forms

from .models import Evento


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
