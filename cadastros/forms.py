import re

from django import forms
from django.db.models import Q

from core.normalizers import normalize_plate
from core.normalizers import normalize_upper
from core.utils.masks import (
    RG_NAO_POSSUI_CANONICAL,
    RG_NAO_POSSUI_DISPLAY,
    format_cpf,
    format_cep,
    format_placa,
    format_rg,
    format_telefone,
    only_digits,
    validar_cpf_digitos,
)

from .models import AssinaturaConfiguracao
from .models import Cargo
from .models import Cidade
from .models import Combustivel
from .models import ConfiguracaoSistema
from .models import Estado
from .models import Servidor
from .models import Unidade
from .models import Viatura

PLACA_RE = re.compile(r"^[A-Z]{3}(?:\d{4}|\d[A-Z]\d{2})$")


def _servidores_assinantes_queryset(extra_ids=None):
    servidores = list(Servidor.objects.select_related("cargo", "unidade").order_by("nome"))
    completos_ids = [servidor.pk for servidor in servidores if servidor.esta_completo()]
    extra_ids = [pk for pk in (extra_ids or []) if pk]
    if completos_ids:
        return Servidor.objects.filter(Q(pk__in=completos_ids) | Q(pk__in=extra_ids)).order_by("nome")
    return Servidor.objects.order_by("nome")


def _normalize_nome_obrigatorio(value):
    nome = normalize_upper(value)
    if not nome:
        raise forms.ValidationError("Este campo é obrigatório.")
    return nome


class BaseCadastroForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            attrs = getattr(field.widget, "attrs", None)
            if attrs is None:
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                attrs.setdefault("class", "app-card-toggle__input sr-only")
                attrs.setdefault("role", "switch")
                continue
            attrs.setdefault("class", "form-control")
            if isinstance(field, forms.CharField):
                attrs.setdefault("data-mask", "upper")


def _servidor_option_attrs(servidor):
    cargo = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
    unidade = str(servidor.unidade) if servidor.unidade_id and servidor.unidade else ""
    cpf = servidor.cpf_formatado or ""
    rg = servidor.rg_formatado or ""
    main = " • ".join(part for part in [servidor.nome, cargo, f"CPF {cpf}" if cpf else ""] if part)
    search = " ".join(part for part in [servidor.nome, cargo, cpf, rg, unidade] if part)
    return {
        "data-option-kind": "servidor",
        "data-cargo": cargo,
        "data-cpf": cpf,
        "data-main": main,
        "data-meta": unidade or "Sem unidade vinculada",
        "data-rg": rg,
        "data-search": search,
        "data-unidade": unidade,
        "data-unidade-id": str(servidor.unidade_id or ""),
    }


class ServidorFiltroSelectMultiple(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        servidor = getattr(value, "instance", None)
        if servidor is None:
            return option
        option["attrs"].update(_servidor_option_attrs(servidor))
        return option


class UnidadeSearchSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        unidade = getattr(value, "instance", None)
        if unidade is None:
            return option
        rotulo = str(unidade)
        option["attrs"].update(
            {
                "data-main": rotulo,
                "data-meta": unidade.nome if unidade.sigla else "",
                "data-search": " ".join(part for part in [unidade.sigla, unidade.nome] if part),
            }
        )
        return option


class UnidadeForm(BaseCadastroForm):
    servidores = forms.ModelMultipleChoiceField(
        label="Servidores",
        required=False,
        queryset=Servidor.objects.none(),
        widget=ServidorFiltroSelectMultiple(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "multi",
                "data-picker-variant": "compact",
                "data-picker-label": "Servidores",
                "data-picker-hint": "Busque por nome, cargo, CPF ou RG.",
                "data-panel-title": "SERVIDORES VINCULADOS",
                "data-empty-selected": "Nenhum servidor vinculado.",
                "data-empty-message": "Nenhum servidor encontrado.",
                "data-placeholder": "Digite nome, cargo, CPF ou RG",
            }
        ),
    )

    class Meta:
        model = Unidade
        fields = ["nome", "sigla"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["servidores"].queryset = Servidor.objects.select_related("cargo", "unidade").order_by("nome")
        if self.instance.pk and not self.is_bound:
            self.initial["servidores"] = list(self.instance.servidores.values_list("pk", flat=True))

    def save(self, commit=True):
        unidade = super().save(commit=commit)
        should_sync_servidores = not self.is_bound or "servidores" in self.data
        if commit and should_sync_servidores:
            servidores = self.cleaned_data.get("servidores")
            if servidores is not None:
                selected_ids = {servidor.pk for servidor in servidores}
                Servidor.objects.filter(pk__in=selected_ids).update(unidade=unidade)
                Servidor.objects.filter(unidade=unidade).exclude(pk__in=selected_ids).update(unidade=None)
        return unidade

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()

    def clean_sigla(self):
        return self.cleaned_data.get("sigla", "").strip().upper()


class EstadoForm(BaseCadastroForm):
    class Meta:
        model = Estado
        fields = ["nome", "sigla", "codigo_ibge"]

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()

    def clean_sigla(self):
        sigla = self.cleaned_data["sigla"].strip().upper()
        if len(sigla) != 2:
            raise forms.ValidationError("Sigla deve ter 2 caracteres.")
        return sigla


class CidadeForm(BaseCadastroForm):
    class Meta:
        model = Cidade
        fields = ["nome", "estado", "capital", "codigo_ibge", "latitude", "longitude"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].queryset = Estado.objects.order_by("nome")
        self.fields["estado"].empty_label = "Selecione"
        self.fields["estado"].widget.attrs["class"] = "form-select"
        for fname in ("latitude", "longitude"):
            if fname in self.fields:
                self.fields[fname].required = False
        if "codigo_ibge" in self.fields:
            self.fields["codigo_ibge"].required = False

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()


_TOGGLE_WIDGET = forms.CheckboxInput(
    attrs={
        "class": "app-card-toggle__input sr-only",
        "role": "switch",
    },
)


class CargoForm(BaseCadastroForm):
    class Meta:
        model = Cargo
        fields = ["nome", "is_padrao"]
        widgets = {
            "is_padrao": _TOGGLE_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_padrao"].required = False
        self.fields["is_padrao"].label = "Cargo padrão"

    def clean_nome(self):
        nome = _normalize_nome_obrigatorio(self.cleaned_data.get("nome", ""))
        qs = Cargo.objects.filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cargo com este nome.")
        return nome


class CombustivelForm(BaseCadastroForm):
    class Meta:
        model = Combustivel
        fields = ["nome", "is_padrao"]
        widgets = {
            "is_padrao": _TOGGLE_WIDGET,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_padrao"].required = False
        self.fields["is_padrao"].label = "Combustível padrão"

    def clean_nome(self):
        nome = _normalize_nome_obrigatorio(self.cleaned_data.get("nome", ""))
        qs = Combustivel.objects.filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um combustível com este nome.")
        return nome


class ServidorForm(BaseCadastroForm):
    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        widget=forms.TextInput(
            attrs={
                "placeholder": "000.000.000-00",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-mask": "cpf",
                "maxlength": "14",
                "class": "form-control",
            },
        ),
    )
    rg = forms.CharField(
        label="RG",
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "00.000.000-0",
                "autocomplete": "off",
                "data-mask": "rg",
                "class": "form-control",
            },
        ),
    )
    telefone = forms.CharField(
        label="Telefone",
        required=False,
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "placeholder": "(00) 00000-0000",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-mask": "telefone",
                "class": "form-control",
            },
        ),
    )
    class Meta:
        model = Servidor
        fields = ["nome", "cargo", "cpf", "rg", "telefone", "unidade"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].required = True
        self.fields["cargo"].empty_label = "Selecione"
        self.fields["cargo"].widget.attrs["class"] = "form-select"
        self.fields["cargo"].queryset = Cargo.objects.order_by("nome")
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].widget = UnidadeSearchSelect(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-picker-label": "Unidade",
                "data-picker-hint": "Busque por sigla ou nome da unidade.",
                "data-placeholder": "Buscar unidade",
                "data-empty-message": "Nenhuma unidade encontrada.",
            }
        )
        self.fields["unidade"].queryset = Unidade.objects.order_by("nome")

        if not self.instance.pk and not self.data:
            padrao = Cargo.objects.filter(is_padrao=True).first()
            if padrao:
                self.initial.setdefault("cargo", padrao.pk)

        if self.instance.pk and not self.data:
            if self.instance.cpf:
                self.initial["cpf"] = format_cpf(self.instance.cpf)
            if self.instance.telefone:
                self.initial["telefone"] = format_telefone(self.instance.telefone)
            if self.instance.rg and not self.instance.sem_rg and self.instance.rg != RG_NAO_POSSUI_CANONICAL and self.instance.rg.isdigit():
                self.initial["rg"] = format_rg(self.instance.rg)

    def clean_nome(self):
        nome = _normalize_nome_obrigatorio(self.cleaned_data.get("nome", ""))
        qs = Servidor.objects.filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um servidor com este nome.")
        return nome

    def clean_cpf(self):
        digits = only_digits(self.cleaned_data.get("cpf", ""))
        if not digits:
            raise forms.ValidationError("Informe o CPF.")
        if len(digits) != 11:
            raise forms.ValidationError("CPF deve conter 11 dígitos.")
        if not validar_cpf_digitos(digits):
            raise forms.ValidationError("CPF inválido.")
        qs = Servidor.objects.filter(cpf=digits)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cadastro com este CPF.")
        return digits

    def clean_rg(self):
        raw = "".join(c for c in self.cleaned_data.get("rg", "").upper() if c.isalnum())
        if raw.upper() in {RG_NAO_POSSUI_CANONICAL.replace(" ", ""), "NAOPOSSUIRG"}:
            return RG_NAO_POSSUI_CANONICAL
        if not raw:
            return RG_NAO_POSSUI_CANONICAL
        if raw:
            qs = Servidor.objects.filter(rg=raw)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Já existe um cadastro com este RG.")
        return raw

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data["sem_rg"] = cleaned_data.get("rg") == RG_NAO_POSSUI_CANONICAL
        return cleaned_data

    def clean_telefone(self):
        digits = only_digits(self.cleaned_data.get("telefone", ""))
        if not digits:
            return ""
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Telefone deve ter 10 ou 11 dígitos.")
        qs = Servidor.objects.filter(telefone=digits)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cadastro com este telefone.")
        return digits


class ViaturaForm(BaseCadastroForm):
    tem_motorista_fixo = forms.BooleanField(
        label="Possui motorista fixo",
        required=False,
        initial=False,
        widget=_TOGGLE_WIDGET,
    )

    class Meta:
        model = Viatura
        fields = ["placa", "modelo", "combustivel", "tipo", "unidade", "motoristas"]
        widgets = {
            "placa": forms.TextInput(
                attrs={
                    "placeholder": "AAA1234 ou AAA1A23",
                    "autocomplete": "off",
                    "data-mask": "placa",
                    "class": "form-control",
                },
            ),
            "tipo": forms.Select(attrs={"class": "form-select"}),
            "motoristas": ServidorFiltroSelectMultiple(
                attrs={
                    "class": "cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "multi",
                    "data-picker-variant": "compact",
                    "data-picker-label": "Motoristas",
                    "data-panel-title": "MOTORISTAS SELECIONADOS",
                    "data-placeholder": "Digite nome, cargo ou CPF",
                    "data-empty-message": "Nenhum motorista encontrado.",
                    "data-empty-selected": "Nenhum motorista selecionado.",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["combustivel"].required = True
        self.fields["combustivel"].empty_label = "Selecione"
        self.fields["combustivel"].widget.attrs["class"] = "form-select"
        self.fields["combustivel"].queryset = Combustivel.objects.order_by("nome")
        self.fields["tipo"].required = True
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].label = "Unidade (opcional)"
        self.fields["unidade"].widget = UnidadeSearchSelect(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-placeholder": "Buscar unidade",
                "data-empty-message": "Nenhuma unidade encontrada.",
            }
        )
        self.fields["unidade"].queryset = Unidade.objects.order_by("nome")
        self.fields["motoristas"].required = False
        self.fields["motoristas"].queryset = Servidor.objects.select_related("cargo", "unidade").order_by("nome")
        if self.instance.pk and not self.is_bound:
            self.initial["tem_motorista_fixo"] = self.instance.motoristas.exists()
        if not self.instance.pk and not self.data:
            padrao = Combustivel.objects.filter(is_padrao=True).first()
            if padrao:
                self.initial.setdefault("combustivel", padrao.pk)
            self.initial.setdefault("tipo", Viatura.TIPO_DESCARACTERIZADA)
            self.initial.setdefault("tem_motorista_fixo", False)
        if self.instance.pk:
            self.initial["placa"] = format_placa(self.instance.placa)

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("tem_motorista_fixo"):
            cleaned_data["motoristas"] = []
        return cleaned_data

    def clean_placa(self):
        raw = normalize_plate(self.cleaned_data.get("placa", ""))
        if not PLACA_RE.match(raw):
            raise forms.ValidationError("Placa deve estar no formato AAA1234 ou AAA1A23.")
        qs = Viatura.objects.filter(placa=raw)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe uma viatura com esta placa.")
        return raw

    def clean_modelo(self):
        modelo = normalize_upper(self.cleaned_data.get("modelo", ""))
        if not modelo:
            raise forms.ValidationError("Informe o modelo.")
        return modelo


class ConfiguracaoSistemaForm(forms.ModelForm):
    """Singleton institucional: unidade, cidade em documentos."""

    class Meta:
        model = ConfiguracaoSistema
        fields = [
            "divisao",
            "unidade",
            "cep",
            "logradouro",
            "numero",
            "bairro",
            "cidade_endereco",
            "uf",
            "telefone",
            "email",
            "nome_chefia",
            "cargo_chefia",
            "pt_sufixo_numero",
        ]
        widgets = {
            "divisao": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "unidade": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "cep": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-mask": "cep",
                    "inputmode": "numeric",
                    "placeholder": "00000-000",
                    "autocomplete": "off",
                }
            ),
            "logradouro": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "numero": forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}),
            "bairro": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "cidade_endereco": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "uf": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-mask": "upper",
                    "maxlength": "2",
                    "autocomplete": "off",
                }
            ),
            "telefone": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-mask": "telefone",
                    "inputmode": "numeric",
                    "placeholder": "(00) 00000-0000",
                    "autocomplete": "off",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "type": "email",
                    "autocomplete": "off",
                }
            ),
            "nome_chefia": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "cargo_chefia": forms.TextInput(attrs={"class": "form-control", "data-mask": "upper"}),
            "pt_sufixo_numero": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-mask": "upper",
                    "maxlength": "20",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["divisao"].label = "Divisão"
        self.fields["unidade"].label = "Unidade"
        self.fields["cidade_endereco"].label = "Cidade"
        self.fields["cep"].label = "CEP"
        self.fields["uf"].label = "UF"
        self.fields["email"].label = "E-mail"
        self.fields["nome_chefia"].label = "Nome da chefia"
        self.fields["cargo_chefia"].label = "Cargo da chefia"
        self.fields["pt_sufixo_numero"].label = "Sufixo do nº do Plano de Trabalho"

        if self.instance and self.instance.pk and not self.data:
            self.initial["cep"] = format_cep(self.instance.cep)
            self.initial["telefone"] = format_telefone(self.instance.telefone)

    def clean_divisao(self):
        raw = (self.cleaned_data.get("divisao") or "").strip()
        return " ".join(raw.split()).upper() if raw else ""

    def clean_unidade(self):
        raw = (self.cleaned_data.get("unidade") or "").strip()
        return " ".join(raw.split()).upper() if raw else ""

    def clean_cidade_endereco(self):
        raw = (self.cleaned_data.get("cidade_endereco") or "").strip()
        return " ".join(raw.split()).upper() if raw else ""

    def clean_cep(self):
        digits = only_digits(self.cleaned_data.get("cep", ""))
        if not digits:
            return ""
        if len(digits) != 8:
            raise forms.ValidationError("CEP deve conter 8 dígitos.")
        return digits

    def clean_telefone(self):
        digits = only_digits(self.cleaned_data.get("telefone", ""))
        if not digits:
            return ""
        if len(digits) not in (10, 11):
            raise forms.ValidationError("Telefone deve ter 10 ou 11 dígitos.")
        return digits

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        return email

    def clean_uf(self):
        uf = (self.cleaned_data.get("uf") or "").strip().upper()
        if not uf:
            return ""
        if len(uf) != 2 or not uf.isalpha():
            raise forms.ValidationError("UF deve conter 2 letras.")
        return uf


_TIPO_FIELD_MAP = [
    (AssinaturaConfiguracao.OFICIO, "assinante_oficio", "Assinante padrão – Ofício"),
    (AssinaturaConfiguracao.JUSTIFICATIVA, "assinante_justificativa", "Assinante padrão – Justificativa"),
    (AssinaturaConfiguracao.PLANO_TRABALHO, "assinante_plano_trabalho", "Assinante padrão – Plano de Trabalho"),
    (AssinaturaConfiguracao.ORDEM_SERVICO, "assinante_ordem_servico", "Assinante padrão – Ordem de Serviço"),
]


class ConfiguracaoAssinaturasForm(forms.Form):
    """Seleção de assinante padrão por tipo de documento."""

    def __init__(self, *args, configuracao=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = _servidores_assinantes_queryset()
        existing: dict[str, "Servidor | None"] = {}
        if configuracao and configuracao.pk:
            for ass in configuracao.assinaturas.filter(ordem=1).select_related("servidor"):
                existing[ass.tipo] = ass.servidor

        for tipo, field_name, label in _TIPO_FIELD_MAP:
            self.fields[field_name] = forms.ModelChoiceField(
                queryset=qs,
                required=False,
                label=label,
                initial=existing.get(tipo),
                widget=forms.Select(attrs={"class": "form-select"}),
            )
            if configuracao and configuracao.pk and not self.data:
                self.initial[field_name] = existing.get(tipo)

    def save(self, configuracao):
        for tipo, field_name, _label in _TIPO_FIELD_MAP:
            servidor = self.cleaned_data.get(field_name)
            if servidor:
                AssinaturaConfiguracao.objects.update_or_create(
                    configuracao=configuracao,
                    tipo=tipo,
                    ordem=1,
                    defaults={"servidor": servidor, "ativo": True},
                )
            else:
                AssinaturaConfiguracao.objects.filter(configuracao=configuracao, tipo=tipo, ordem=1).delete()

