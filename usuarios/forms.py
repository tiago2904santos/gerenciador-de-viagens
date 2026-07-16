from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from .models import AreaTrabalho
from .models import VinculoUsuarioArea


class AreaTrabalhoForm(forms.ModelForm):
    class Meta:
        model = AreaTrabalho
        fields = ["nome", "sigla", "ativa"]
        labels = {
            "nome": "Nome da área",
            "sigla": "Sigla",
            "ativa": "Área ativa",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Assessoria de Comunicação Social"}),
            "sigla": forms.TextInput(attrs={"placeholder": "ASCOM"}),
        }


class UsuarioAreaCreationForm(UserCreationForm):
    area = forms.ModelChoiceField(
        queryset=AreaTrabalho.objects.none(),
        label="Área de trabalho",
        help_text="Área que o usuário acessará ao entrar no sistema.",
    )
    papel = forms.ChoiceField(
        choices=VinculoUsuarioArea.PAPEL_CHOICES,
        initial=VinculoUsuarioArea.PAPEL_EDITOR,
        label="Perfil na área",
    )
    area_padrao = forms.BooleanField(
        required=False,
        initial=True,
        label="Definir como área padrão",
    )
    is_staff = forms.BooleanField(
        required=False,
        label="Administrador do sistema",
        help_text="Permite acessar esta página administrativa.",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = [
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
            "area",
            "papel",
            "area_padrao",
            "is_staff",
        ]
        labels = {
            "username": "Login",
            "email": "E-mail institucional",
            "first_name": "Nome",
            "last_name": "Sobrenome",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = AreaTrabalho.objects.filter(ativa=True).order_by("sigla")
        self.fields["email"].required = True
        self.fields["email"].widget.attrs.update({"placeholder": "adm.tsantos@pc.pr.gov.br"})

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.is_staff = self.cleaned_data.get("is_staff", False)
        if commit:
            user.save()
            VinculoUsuarioArea.objects.create(
                usuario=user,
                area=self.cleaned_data["area"],
                papel=self.cleaned_data["papel"],
                area_padrao=self.cleaned_data.get("area_padrao", False),
                ativo=True,
            )
        return user


class VinculoUsuarioAreaForm(forms.ModelForm):
    class Meta:
        model = VinculoUsuarioArea
        fields = ["usuario", "area", "papel", "area_padrao", "ativo"]
        labels = {
            "usuario": "Usuário existente",
            "area": "Área de trabalho",
            "papel": "Perfil na área",
            "area_padrao": "Definir como área padrão",
            "ativo": "Vínculo ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = get_user_model().objects.order_by("username")
        self.fields["area"].queryset = AreaTrabalho.objects.filter(ativa=True).order_by("sigla")

    @transaction.atomic
    def save(self, commit=True):
        vinculo = super().save(commit=False)
        if commit:
            if vinculo.area_padrao and vinculo.ativo:
                VinculoUsuarioArea.objects.filter(usuario=vinculo.usuario, area_padrao=True).exclude(
                    pk=vinculo.pk
                ).update(area_padrao=False)
            vinculo.save()
        return vinculo
