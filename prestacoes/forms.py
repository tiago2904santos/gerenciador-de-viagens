from django import forms

from .models import DiarioBordo
from .models import DiarioBordoRegistro
from .models import PrestacaoContas
from .models import RelatorioTecnico


TEXTAREA_CLASS = "cv-field__control cv-field__control--textarea"
CONTROL_CLASS = "cv-field__control"
SELECT_CLASS = "form-select"


class RelatorioTecnicoForm(forms.ModelForm):
    class Meta:
        model = RelatorioTecnico
        fields = [
            "evento",
            "titulo",
            "objetivo",
            "periodo",
            "local",
            "servidores_participantes",
            "atividades_realizadas",
            "resultados_obtidos",
            "intercorrencias",
            "conclusao",
            "status",
            "assinatura_status",
        ]
        widgets = {
            "evento": forms.Select(attrs={"class": SELECT_CLASS}),
            "titulo": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "objetivo": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 4}),
            "periodo": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "local": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "servidores_participantes": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 4}),
            "atividades_realizadas": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 5}),
            "resultados_obtidos": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 5}),
            "intercorrencias": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 4}),
            "conclusao": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 4}),
            "status": forms.Select(attrs={"class": SELECT_CLASS}),
            "assinatura_status": forms.Select(attrs={"class": SELECT_CLASS}),
        }

    def __init__(self, *args, evento_locked=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["evento"].required = False
        if evento_locked:
            self.fields["evento"].disabled = True


class DiarioBordoForm(forms.ModelForm):
    class Meta:
        model = DiarioBordo
        fields = ["evento", "titulo", "destino", "periodo", "status", "assinatura_status"]
        widgets = {
            "evento": forms.Select(attrs={"class": SELECT_CLASS}),
            "titulo": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "destino": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "periodo": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "status": forms.Select(attrs={"class": SELECT_CLASS}),
            "assinatura_status": forms.Select(attrs={"class": SELECT_CLASS}),
        }

    def __init__(self, *args, evento_locked=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["evento"].required = False
        if evento_locked:
            self.fields["evento"].disabled = True


class DiarioBordoRegistroForm(forms.ModelForm):
    class Meta:
        model = DiarioBordoRegistro
        fields = [
            "data",
            "hora_saida",
            "hora_chegada",
            "origem",
            "destino",
            "viatura",
            "motorista",
            "km_inicial",
            "km_final",
            "atividades",
            "observacoes",
        ]
        widgets = {
            "data": forms.DateInput(attrs={"class": CONTROL_CLASS, "type": "date"}),
            "hora_saida": forms.TimeInput(attrs={"class": CONTROL_CLASS, "type": "time"}),
            "hora_chegada": forms.TimeInput(attrs={"class": CONTROL_CLASS, "type": "time"}),
            "origem": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "destino": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "viatura": forms.Select(attrs={"class": SELECT_CLASS}),
            "motorista": forms.Select(attrs={"class": SELECT_CLASS}),
            "km_inicial": forms.NumberInput(attrs={"class": CONTROL_CLASS}),
            "km_final": forms.NumberInput(attrs={"class": CONTROL_CLASS}),
            "atividades": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 4}),
            "observacoes": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        km_inicial = cleaned.get("km_inicial")
        km_final = cleaned.get("km_final")
        if km_inicial is not None and km_final is not None and km_final < km_inicial:
            self.add_error("km_final", "O KM final não pode ser menor que o KM inicial.")
        return cleaned


class PrestacaoContasForm(forms.ModelForm):
    class Meta:
        model = PrestacaoContas
        fields = [
            "evento",
            "relatorio_tecnico",
            "diario_bordo",
            "status",
            "observacoes",
            "assinatura_responsavel_status",
        ]
        widgets = {
            "evento": forms.Select(attrs={"class": SELECT_CLASS}),
            "relatorio_tecnico": forms.Select(attrs={"class": SELECT_CLASS}),
            "diario_bordo": forms.Select(attrs={"class": SELECT_CLASS}),
            "status": forms.Select(attrs={"class": SELECT_CLASS}),
            "observacoes": forms.Textarea(attrs={"class": TEXTAREA_CLASS, "rows": 4}),
            "assinatura_responsavel_status": forms.Select(attrs={"class": SELECT_CLASS}),
        }

    def __init__(self, *args, evento=None, **kwargs):
        super().__init__(*args, **kwargs)
        if evento:
            self.fields["evento"].disabled = True
            self.fields["relatorio_tecnico"].queryset = evento.relatorios_tecnicos.all()
            self.fields["diario_bordo"].queryset = evento.diarios_bordo.all()
