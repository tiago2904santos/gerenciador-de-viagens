from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm

from .widgets import set_widget_style
from .widgets import text_attrs
from .widgets import WidgetStyle
from .widgets import widget_attrs


class LoginForm(AuthenticationForm):
    """Formulario de login com foco inicial no usuario e classes para auth.css."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autofocus": True,
                "autocomplete": "username",
                **widget_attrs(WidgetStyle.AUTH_FIELD_INPUT),
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "autocomplete": "current-password",
                **widget_attrs(WidgetStyle.AUTH_FIELD_INPUT),
            }
        )

    def full_clean(self):
        """`HT-09`: liga cada campo ao `<div>` de erro que o template renderiza.

        Os `id` de erro existiam em `templates/core/login.html` e nunca eram
        referenciados — quem usa leitor de tela ouvia "Usuário, campo de edição"
        e nada sobre o que deu errado.

        Feito aqui, e não no `__init__`, porque em `__init__` os erros ainda não
        existem: `self._errors` só é populado por este `full_clean`. Apontar
        `aria-describedby` para um `id` ausente seria pior que não apontar — o
        leitor de tela ignora a referência quebrada e o atributo vira ruído no
        HTML de toda tela de login que carrega sem erro nenhum.
        """
        super().full_clean()
        for nome in ("username", "password"):
            if self.has_error(nome):
                self.fields[nome].widget.attrs["aria-describedby"] = f"id_{nome}-error"
                self.fields[nome].widget.attrs["aria-invalid"] = "true"


class PerfilUsuarioForm(forms.ModelForm):
    nome_completo = forms.CharField(
        label="Nome completo",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "name", **text_attrs(WidgetStyle.FORM_CONTROL)}),
    )

    class Meta:
        model = get_user_model()
        fields = ["username", "email"]
        labels = {
            "username": "Nome de usuário",
            "email": "E-mail institucional",
        }
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username", **widget_attrs(WidgetStyle.FORM_CONTROL)}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", **widget_attrs(WidgetStyle.FORM_CONTROL)}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["nome_completo"].initial = self.instance.get_full_name()

    def save(self, commit=True):
        user = super().save(commit=False)
        nome = (self.cleaned_data.get("nome_completo") or "").strip()
        partes = nome.split(" ", 1)
        user.first_name = partes[0] if partes[0] else ""
        user.last_name = partes[1].strip() if len(partes) > 1 else ""
        if commit:
            user.save()
        return user


class AlterarSenhaForm(PasswordChangeForm):
    """PasswordChangeForm com as classes de widget do design system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            set_widget_style(field.widget, WidgetStyle.FORM_CONTROL, overwrite=False)
            field.widget.attrs.setdefault(
                "autocomplete",
                "current-password" if field_name == "old_password" else "new-password",
            )
