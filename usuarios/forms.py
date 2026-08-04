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


class AreaTrabalhoEditForm(AreaTrabalhoForm):
    """Edição no gerenciador: inclui o interruptor de área ativa."""

    class Meta(AreaTrabalhoForm.Meta):
        fields = ["nome", "sigla", "ativa"]
        labels = {
            **AreaTrabalhoForm.Meta.labels,
            "ativa": "Área ativa",
        }


class UsuarioEditForm(EstiloCamposMixin, forms.ModelForm):
    """Edição da conta na lista de usuários."""

    nome_completo = forms.CharField(
        label="Nome completo",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "name",
                "placeholder": "Nome e sobrenome",
            }
        ),
    )

    class Meta:
        model = get_user_model()
        fields = ["username", "email", "nome_completo"]
        labels = {
            "username": "Nome de usuário",
            "email": "E-mail institucional",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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
        if self.instance and self.instance.pk:
            nome = f"{self.instance.first_name} {self.instance.last_name}".strip()
            self.fields["nome_completo"].initial = nome or self.instance.get_username()

    def save(self, commit=True):
        user = super().save(commit=False)
        nome_completo = self.cleaned_data["nome_completo"].strip()
        partes_nome = nome_completo.split(" ", 1)
        user.first_name = partes_nome[0]
        user.last_name = partes_nome[1].strip() if len(partes_nome) > 1 else ""
        if commit:
            user.save()
        return user


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
        user.is_active = True
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
    """Vínculo a partir da lista: o usuário vem oculto; área e perfil no modal."""

    class Meta:
        model = VinculoUsuarioArea
        fields = ["usuario", "area", "papel"]
        labels = {
            "usuario": "Usuário existente",
            "area": "Área de trabalho",
            "papel": "Perfil na área",
        }
        widgets = {
            "usuario": forms.HiddenInput(),
            "area": forms.Select(
                attrs=_cv_picker_single_attrs(
                    label="Área de trabalho",
                    placeholder="Buscar área...",
                    empty_message="Nenhuma área encontrada.",
                )
            ),
            "papel": forms.Select(
                attrs=_cv_picker_single_attrs(
                    label="Perfil na área",
                    placeholder="Buscar perfil...",
                    empty_message="Nenhum perfil encontrado.",
                )
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["usuario"].queryset = get_user_model().objects.order_by("username")
        self.fields["area"].queryset = AreaTrabalho.objects.filter(ativa=True).order_by("sigla")


class VinculoNaAreaForm(EstiloCamposMixin, forms.ModelForm):
    """Vínculo a partir do gerenciador da área: área fixa, escolher a conta."""

    class Meta:
        model = VinculoUsuarioArea
        fields = ["usuario", "area", "papel"]
        labels = {
            "usuario": "Usuário",
            "area": "Área de trabalho",
            "papel": "Perfil na área",
        }
        widgets = {
            "area": forms.HiddenInput(),
            "usuario": forms.Select(
                attrs=_cv_picker_single_attrs(
                    label="Usuário",
                    placeholder="Buscar usuário...",
                    empty_message="Nenhum usuário disponível.",
                )
            ),
            # Mesmo picker do modal da lista: os dois campos do diálogo têm de
            # ser o mesmo controle, senão um vira busca e o outro select nativo.
            "papel": forms.Select(
                attrs=_cv_picker_single_attrs(
                    label="Perfil na área",
                    placeholder="Buscar perfil...",
                    empty_message="Nenhum perfil encontrado.",
                )
            ),
        }

    def __init__(self, *args, area=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._area = area
        if area is not None:
            self.fields["area"].initial = area.pk
            self.fields["area"].queryset = AreaTrabalho.objects.filter(pk=area.pk)
            ja_vinculados = area.vinculos_usuario.values_list("usuario_id", flat=True)
            self.fields["usuario"].queryset = (
                get_user_model()
                .objects.exclude(pk__in=ja_vinculados)
                .order_by("username")
            )
        else:
            self.fields["usuario"].queryset = get_user_model().objects.order_by("username")
            self.fields["area"].queryset = AreaTrabalho.objects.filter(ativa=True).order_by("sigla")

    def clean_area(self):
        if self._area is not None:
            return self._area
        return self.cleaned_data["area"]
