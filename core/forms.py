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


class UiLabFieldDemoForm(forms.Form):
    """BoundFields reais usados para provar o contrato canônico no UI Lab."""

    nome = forms.CharField(
        label="Nome completo",
        initial="Ana Souza",
        widget=forms.TextInput(attrs={"autocomplete": "name", "class": "form-control"}),
    )
    email = forms.EmailField(
        label="E-mail institucional",
        required=False,
        initial="ana.souza@pc.pr.gov.br",
        help_text="Usado para notificações e identificação da conta.",
        widget=forms.EmailInput(attrs={"autocomplete": "email", "class": "form-control"}),
    )
    senha = forms.CharField(
        label="Senha de acesso",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "class": "form-control"}),
    )
    quantidade = forms.IntegerField(
        label="Quantidade de diárias",
        required=False,
        initial=2,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    data_saida = forms.DateField(
        label="Data de saída",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "dd/mm/aaaa",
                "inputmode": "numeric",
                "data-mask": "date",
            }
        ),
    )
    motivo = forms.CharField(
        label="Motivo da viagem",
        required=False,
        initial="Atendimento institucional em outra unidade.",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
    )
    unidade = forms.ChoiceField(
        label="Unidade responsável",
        required=False,
        choices=(("", "Selecione..."), ("dpc", "DPC"), ("dti", "DTI")),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    participantes = forms.MultipleChoiceField(
        label="Participantes",
        required=False,
        choices=(("ana", "Ana Souza"), ("carlos", "Carlos Lima"), ("marina", "Marina Alves")),
        widget=forms.SelectMultiple(attrs={"class": "form-select"}),
    )
    destino_picker = forms.ChoiceField(
        label="Destino",
        required=False,
        initial="curitiba",
        choices=(
            ("", "Selecione..."),
            ("curitiba", "Curitiba/PR"),
            ("londrina", "Londrina/PR"),
            ("joinville", "Joinville/SC"),
        ),
        widget=forms.Select(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-field-label": "Destino",
                "data-placeholder": "Buscar destino...",
                "data-picker-open-all": "true",
            }
        ),
    )
    servidores_picker = forms.MultipleChoiceField(
        label="Servidores",
        required=False,
        initial=("ana", "marina"),
        choices=(
            ("ana", "Ana Souza — Analista"),
            ("carlos", "Carlos Lima — Motorista"),
            ("marina", "Marina Alves — Coordenadora"),
            ("paulo", "Paulo Reis — Técnico"),
        ),
        widget=forms.SelectMultiple(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "multi",
                "data-picker-variant": "detailed",
                "data-field-label": "Servidores",
                "data-placeholder": "Buscar servidor...",
                "data-panel-title": "Selecionados",
                "data-empty-selected": "Nenhum servidor selecionado.",
                "data-picker-open-all": "true",
            }
        ),
    )
    protocolo = forms.CharField(
        label="Protocolo gerado",
        required=False,
        initial="2026.07.17.0042",
        widget=forms.TextInput(attrs={"readonly": "readonly", "class": "form-control"}),
    )
    status = forms.CharField(
        label="Status bloqueado",
        required=False,
        initial="Finalizado",
        disabled=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    confirmacao = forms.BooleanField(
        label="Confirmo os dados informados",
        required=False,
        help_text="Revise as informações antes de prosseguir.",
    )
