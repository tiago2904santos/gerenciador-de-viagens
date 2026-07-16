from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from .models import AreaTrabalho
from .models import VinculoUsuarioArea


class EstiloCamposMixin:
    """Aplica as classes de widget do design system (form-control / card toggle)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            attrs = getattr(field.widget, "attrs", None)
            if attrs is None:
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                attrs.setdefault("class", "app-card-toggle__input sr-only")
                attrs.setdefault("role", "switch")
            else:
                attrs.setdefault("class", "form-control")


class AreaTrabalhoForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = AreaTrabalho
        fields = ["nome", "sigla"]
        labels = {
            "nome": "Nome da área",
            "sigla": "Sigla",
        }
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Assessoria de Comunicação Social"}),
            "sigla": forms.TextInput(attrs={"placeholder": "ASCOM"}),
        }


class UsuarioAreaCreationForm(EstiloCamposMixin, UserCreationForm):
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
        user.is_staff = False
        if commit:
            user.save()
            # Primeira (e única) área do usuário → vira a padrão, garantindo
            # que ele tenha uma área carregada ao entrar no sistema.
            VinculoUsuarioArea.objects.create(
                usuario=user,
                area=self.cleaned_data["area"],
                papel=self.cleaned_data["papel"],
                area_padrao=True,
                ativo=True,
            )
        return user


class VinculoUsuarioAreaForm(EstiloCamposMixin, forms.ModelForm):
    class Meta:
        model = VinculoUsuarioArea
        fields = ["usuario", "area", "papel"]
        labels = {
            "usuario": "Usuário existente",
            "area": "Área de trabalho",
            "papel": "Perfil na área",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = get_user_model().objects.order_by("username")
        self.fields["area"].queryset = AreaTrabalho.objects.filter(ativa=True).order_by("sigla")
