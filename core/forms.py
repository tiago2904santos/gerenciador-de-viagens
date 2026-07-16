from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm


class LoginForm(AuthenticationForm):
    """Formulario de login com foco inicial no usuario e classes para auth.css."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autofocus": True,
                "autocomplete": "username",
                "class": "auth-field-input",
            }
        )
        self.fields["password"].widget.attrs.update(
            {
                "autocomplete": "current-password",
                "class": "auth-field-input",
            }
        )


class PerfilUsuarioForm(forms.ModelForm):
    nome_completo = forms.CharField(
        label="Nome completo",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "name", "class": "form-control"}),
    )

    class Meta:
        model = get_user_model()
        fields = ["username", "email"]
        labels = {
            "username": "Nome de usuário",
            "email": "E-mail institucional",
        }
        widgets = {
            "username": forms.TextInput(attrs={"autocomplete": "username", "class": "form-control"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "class": "form-control"}),
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
            field.widget.attrs.setdefault("class", "form-control")
            field.widget.attrs.setdefault(
                "autocomplete",
                "current-password" if field_name == "old_password" else "new-password",
            )
