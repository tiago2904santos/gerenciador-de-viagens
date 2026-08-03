from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from core.forms.widgets import set_widget_style
from core.forms.widgets import WidgetStyle
from core.forms.widgets import widget_attrs

from .models import AreaTrabalho
from .models import VinculoUsuarioArea


def _cv_picker_single_attrs(*, label, placeholder, empty_message):
    return {
        **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
        "data-entity-picker": "true",
        "data-entity-picker-mode": "single",
        "data-picker-variant": "compact",
        "data-picker-label": label,
        "data-picker-open-all": "true",
        "data-placeholder": placeholder,
        "data-empty-message": empty_message,
    }


class EstiloCamposMixin:
    """Aplica as classes de widget do design system (form-control / card toggle)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if getattr(field.widget, "attrs", None) is None:
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                set_widget_style(field.widget, WidgetStyle.CARD_TOGGLE_SR_ONLY, overwrite=False)
                field.widget.attrs.setdefault("role", "switch")
            else:
                set_widget_style(field.widget, WidgetStyle.FORM_CONTROL, overwrite=False)


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
    nome_completo = forms.CharField(
        label="Nome completo",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "name",
                "placeholder": "Nome e sobrenome",
            }
        ),
    )
    area = forms.ModelChoiceField(
        queryset=AreaTrabalho.objects.none(),
        label="Área de trabalho",
        widget=forms.Select(
            attrs=_cv_picker_single_attrs(
                label="Área de trabalho",
                placeholder="Buscar área...",
                empty_message="Nenhuma área encontrada.",
            )
        ),
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
            "nome_completo",
            "password1",
            "password2",
            "area",
            "papel",
        ]
        labels = {
            "username": "Nome de usuário",
            "email": "E-mail institucional",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["area"].queryset = AreaTrabalho.objects.filter(ativa=True).order_by("sigla")
        self.fields["email"].required = True
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
                "placeholder": "ex.: adm.tsantos",
            }
        )
        self.fields["email"].widget.attrs.update(
            {
                "autocomplete": "email",
                "placeholder": "adm.tsantos@pc.pr.gov.br",
            }
        )
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        nome_completo = self.cleaned_data["nome_completo"].strip()
        partes_nome = nome_completo.split(" ", 1)
        user.email = self.cleaned_data["email"]
        user.first_name = partes_nome[0]
        user.last_name = partes_nome[1].strip() if len(partes_nome) > 1 else ""
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
        widgets = {
            "usuario": forms.Select(
                attrs=_cv_picker_single_attrs(
                    label="Usuário existente",
                    placeholder="Buscar usuário...",
                    empty_message="Nenhum usuário encontrado.",
                )
            ),
            "area": forms.Select(
                attrs=_cv_picker_single_attrs(
                    label="Área de trabalho",
                    placeholder="Buscar área...",
                    empty_message="Nenhuma área encontrada.",
                )
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = get_user_model().objects.order_by("username")
        self.fields["area"].queryset = AreaTrabalho.objects.filter(ativa=True).order_by("sigla")
