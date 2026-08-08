import re

from django import forms

from core.forms.widgets import set_widget_style
from core.forms.widgets import WidgetStyle
from core.forms.widgets import widget_attrs
from core.forms.widgets import text_attrs
from core.normalizers import normalize_plate
from core.normalizers import normalize_upper
from core.tenancy import filter_queryset_by_area
from core.tenancy import get_current_area
from core.utils.masks import (
    RG_NAO_POSSUI_CANONICAL,
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
from .models import TabelaDiaria
from .models import Estado
from .models import Servidor
from .models import Unidade
from .models import Viatura

PLACA_RE = re.compile(r"^[A-Z]{3}(?:\d{4}|\d[A-Z]\d{2})$")


def _servidores_assinantes_queryset():
    # Assinantes/destinatários exibem apenas nome e cargo no documento (sem RG/CPF),
    # então servidores incompletos (ex.: chefias sem CPF cadastrado) também são elegíveis.
    return _servidores_queryset()


def _servidores_queryset():
    return filter_queryset_by_area(Servidor.objects).select_related("cargo", "unidade").order_by("nome")


def _normalize_nome_obrigatorio(value):
    nome = normalize_upper(value)
    if not nome:
        raise forms.ValidationError("Este campo é obrigatório.")
    return nome


class BaseCadastroForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome, field in self.fields.items():
            if getattr(field.widget, "attrs", None) is None:
                continue
            if isinstance(field.widget, forms.CheckboxInput):
                set_widget_style(
                    field.widget,
                    WidgetStyle.CARD_TOGGLE_SR_ONLY,
                    overwrite=False,
                    nome=nome,
                )
                field.widget.attrs.setdefault("role", "switch")
                continue
            # A máscara sai de `set_widget_style` e não daqui. A regra local era
            # "todo `CharField`", e `EmailField`/`URLField` são `CharField` — o
            # dia em que um cadastro ganhasse e-mail, ele seria maiusculizado em
            # silêncio. A regra central pergunta pelo widget e pelo nome.
            set_widget_style(
                field.widget,
                WidgetStyle.FORM_CONTROL,
                overwrite=False,
                nome=nome,
            )


def _servidor_option_attrs(servidor):
    cargo = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
    unidade = str(servidor.unidade) if servidor.unidade_id and servidor.unidade else ""
    unidade_nome = servidor.unidade.nome if servidor.unidade_id and servidor.unidade else ""
    cpf = servidor.cpf_formatado or ""
    rg = servidor.rg_formatado or ""
    main = " • ".join(part for part in [servidor.nome, cargo, f"CPF {cpf}" if cpf else ""] if part)
    search = " ".join(part for part in [servidor.nome, cargo, cpf, rg, unidade, unidade_nome] if part)
    return {
        "data-option-kind": "servidor",
        "data-cargo": cargo,
        "data-cpf": cpf,
        "data-main": main,
        "data-meta": unidade or "Sem unidade vinculada",
        "data-rg": rg,
        "data-search": search,
        "data-unidade": unidade,
        "data-unidade-nome": unidade_nome,
        "data-unidade-id": str(servidor.unidade_id or ""),
        "data-rascunho": "true" if servidor.status == Servidor.STATUS_RASCUNHO else "false",
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


class UnidadePorExtensoSearchSelect(forms.Select):
    """Picker de unidade exibindo o nome completo (por extenso) ao invés da sigla."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        unidade = getattr(value, "instance", None)
        if unidade is None:
            return option
        nome = unidade.nome or unidade.sigla or ""
        option["label"] = nome
        option["attrs"].update(
            {
                "data-main": nome,
                "data-meta": unidade.sigla or "",
                "data-search": " ".join(part for part in [unidade.nome, unidade.sigla] if part),
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
                **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                "data-entity-picker": "true",
                "data-entity-picker-mode": "multi",
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
        self.fields["servidores"].queryset = _servidores_queryset()
        if self.instance.pk and not self.is_bound:
            self.initial["servidores"] = list(
                _servidores_queryset().filter(unidade=self.instance).values_list("pk", flat=True)
            )

    def save(self, commit=True):
        unidade = super().save(commit=commit)
        should_sync_servidores = not self.is_bound or "servidores" in self.data
        if commit and should_sync_servidores:
            servidores = self.cleaned_data.get("servidores")
            if servidores is not None:
                selected_ids = {servidor.pk for servidor in servidores}
                servidores_area = filter_queryset_by_area(Servidor.objects)
                servidores_area.filter(pk__in=selected_ids).update(unidade=unidade)
                servidores_area.filter(unidade=unidade).exclude(pk__in=selected_ids).update(unidade=None)
        return unidade

    def clean_nome(self):
        nome = (self.cleaned_data["nome"] or "").strip()
        qs = filter_queryset_by_area(Unidade.objects).filter(nome=normalize_upper(nome))
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe uma unidade com este nome.")
        return nome

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
        set_widget_style(self.fields["estado"].widget, WidgetStyle.FORM_SELECT)
        for fname in ("latitude", "longitude"):
            if fname in self.fields:
                self.fields[fname].required = False
        if "codigo_ibge" in self.fields:
            self.fields["codigo_ibge"].required = False

    def clean_nome(self):
        return self.cleaned_data["nome"].strip()


_TOGGLE_WIDGET = forms.CheckboxInput(
    attrs={
        **widget_attrs(WidgetStyle.CARD_TOGGLE_SR_ONLY),
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
        self.fields["nome"].label = "Cargo"
        self.fields["is_padrao"].required = False
        self.fields["is_padrao"].label = "Cargo padrão"

    def clean_nome(self):
        nome = _normalize_nome_obrigatorio(self.cleaned_data.get("nome", ""))
        qs = filter_queryset_by_area(Cargo.objects).filter(nome=nome)
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
        self.fields["nome"].label = "Combustível"
        self.fields["is_padrao"].required = False
        self.fields["is_padrao"].label = "Combustível padrão"

    def clean_nome(self):
        nome = _normalize_nome_obrigatorio(self.cleaned_data.get("nome", ""))
        qs = filter_queryset_by_area(Combustivel.objects).filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um combustível com este nome.")
        return nome


class ServidorForm(BaseCadastroForm):
    cpf = forms.CharField(
        label="CPF",
        max_length=14,
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "000.000.000-00",
                "inputmode": "numeric",
                "autocomplete": "off",
                "data-mask": "cpf",
                "maxlength": "14",
                **widget_attrs(WidgetStyle.FORM_CONTROL),
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
                **widget_attrs(WidgetStyle.FORM_CONTROL),
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
                **widget_attrs(WidgetStyle.FORM_CONTROL),
            },
        ),
    )
    class Meta:
        model = Servidor
        fields = ["nome", "cargo", "cpf", "rg", "telefone", "unidade"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].required = False
        self.fields["cargo"].empty_label = "Selecione (opcional)"
        set_widget_style(self.fields["cargo"].widget, WidgetStyle.FORM_SELECT)
        self.fields["cargo"].queryset = filter_queryset_by_area(Cargo.objects).order_by("nome")
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].widget = UnidadeSearchSelect(
            attrs={
                **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                "data-entity-picker": "true",
                "data-entity-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-picker-label": "Unidade",
                "data-placeholder": "Buscar unidade",
                "data-empty-message": "Nenhuma unidade encontrada.",
            }
        )
        self.fields["unidade"].queryset = filter_queryset_by_area(Unidade.objects).order_by("nome")

        if not self.instance.pk and not self.data:
            padrao = filter_queryset_by_area(Cargo.objects).filter(is_padrao=True).first()
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
        qs = filter_queryset_by_area(Servidor.objects).filter(nome=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um servidor com este nome.")
        return nome

    def clean_cpf(self):
        digits = only_digits(self.cleaned_data.get("cpf", ""))
        if not digits:
            return ""
        if len(digits) != 11:
            raise forms.ValidationError("CPF deve conter 11 dígitos.")
        if not validar_cpf_digitos(digits):
            raise forms.ValidationError("CPF inválido.")
        qs = filter_queryset_by_area(Servidor.objects).filter(cpf=digits)
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
            qs = filter_queryset_by_area(Servidor.objects).filter(rg=raw)
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
        qs = filter_queryset_by_area(Servidor.objects).filter(telefone=digits)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe um cadastro com este telefone.")
        return digits


class ViaturaForm(BaseCadastroForm):
    class Meta:
        model = Viatura
        fields = ["placa", "modelo", "combustivel", "tipo", "unidade", "motoristas"]
        widgets = {
            "placa": forms.TextInput(
                attrs={
                    "placeholder": "AAA1234 ou AAA1A23",
                    "autocomplete": "off",
                    "data-mask": "placa",
                    **widget_attrs(WidgetStyle.FORM_CONTROL),
                },
            ),
            "tipo": forms.Select(attrs={**widget_attrs(WidgetStyle.FORM_SELECT)}),
            "motoristas": ServidorFiltroSelectMultiple(
                attrs={
                    **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                    "data-entity-picker": "true",
                    "data-entity-picker-mode": "multi",
                    "data-picker-variant": "detailed",
                    "data-picker-presentation": "people",
                    "data-picker-all-drivers": "true",
                    "data-picker-label": "Motoristas",
                    "data-picker-hide-selected-header": "true",
                    "data-placeholder": "Digite nome, cargo ou CPF",
                    "data-empty-message": "Nenhum motorista encontrado.",
                    "data-empty-selected": "Nenhum motorista selecionado.",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["combustivel"].required = False
        self.fields["combustivel"].empty_label = "Selecione (opcional)"
        set_widget_style(self.fields["combustivel"].widget, WidgetStyle.FORM_SELECT)
        self.fields["combustivel"].queryset = filter_queryset_by_area(Combustivel.objects).order_by("nome")
        self.fields["tipo"].required = False
        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = "Selecione (opcional)"
        self.fields["unidade"].label = "Unidade (opcional)"
        self.fields["unidade"].widget = UnidadeSearchSelect(
            attrs={
                **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                "data-entity-picker": "true",
                "data-entity-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-picker-label": "Unidade (opcional)",
                "data-placeholder": "Buscar unidade",
                "data-empty-message": "Nenhuma unidade encontrada.",
            }
        )
        self.fields["unidade"].queryset = filter_queryset_by_area(Unidade.objects).order_by("nome")
        self.fields["motoristas"].required = False
        self.fields["motoristas"].queryset = _servidores_queryset()
        if not self.instance.pk and not self.data:
            padrao = filter_queryset_by_area(Combustivel.objects).filter(is_padrao=True).first()
            if padrao:
                self.initial.setdefault("combustivel", padrao.pk)
            self.initial.setdefault("tipo", Viatura.TIPO_DESCARACTERIZADA)
        if self.instance.pk:
            self.initial["placa"] = format_placa(self.instance.placa)

    def clean_placa(self):
        raw = normalize_plate(self.cleaned_data.get("placa", ""))
        if not PLACA_RE.match(raw):
            raise forms.ValidationError("Placa deve estar no formato AAA1234 ou AAA1A23.")
        # `DB-05`: esta consulta nao tinha recorte de area, e a mensagem de erro
        # confirmava a existencia da placa em outra unidade — informacao de
        # outra area entregue por um formulario. O recorte sai da area da
        # propria instancia quando ela ja existe (edicao) e da area ativa quando
        # e cadastro novo, que e a area em que a viatura vai nascer.
        # `area_id` e nao `pk`: cobre os dois caminhos. Na edicao a viatura ja
        # tem area; no cadastro novo ela ainda nao tem, porque
        # `cadastros/services.py:259` so atribui **depois** da validacao — e ai
        # a area ativa e a area em que a viatura vai nascer. Testar por `pk`
        # faria a forma ignorar uma area ja atribuida na instancia, que e
        # exatamente o caso de quem chama o form fora de um request.
        area = self.instance.area if self.instance.area_id else get_current_area()
        # `BE-09`: `all_objects` — a `area` da linha de cima é a da instância quando
        # ela existe, e o parágrafo acima explica por quê. Recortar de novo pela área
        # ativa esvaziaria o queryset quando as duas divergissem, a checagem de placa
        # passaria em branco e o erro viraria `IntegrityError` em
        # `viatura_area_placa_unique` — desfazendo justamente o `DB-05`.
        qs = filter_queryset_by_area(Viatura.all_objects, area).filter(placa=raw)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe uma viatura com esta placa nesta área.")
        return raw

    def clean_modelo(self):
        return normalize_upper(self.cleaned_data.get("modelo", ""))


class ConfiguracaoSistemaForm(forms.ModelForm):
    """Singleton institucional: unidade, cidade em documentos."""

    class Meta:
        model = ConfiguracaoSistema
        fields = [
            "unidade",
            "cep",
            "logradouro",
            "numero",
            "bairro",
            "cidade_endereco",
            "uf",
            "telefone",
            "ramal",
            "email",
        ]
        widgets = {
            "cep": forms.TextInput(
                attrs={
                    **widget_attrs(WidgetStyle.FORM_CONTROL),
                    "data-mask": "cep",
                    "inputmode": "numeric",
                    "placeholder": "00000-000",
                    "autocomplete": "off",
                }
            ),
            "logradouro": forms.TextInput(attrs={**widget_attrs(WidgetStyle.FORM_CONTROL), "data-mask": "upper"}),
            "numero": forms.TextInput(attrs={**text_attrs(WidgetStyle.FORM_CONTROL), "autocomplete": "off"}),
            "bairro": forms.TextInput(attrs={**widget_attrs(WidgetStyle.FORM_CONTROL), "data-mask": "upper"}),
            "cidade_endereco": forms.TextInput(attrs={**widget_attrs(WidgetStyle.FORM_CONTROL), "data-mask": "upper"}),
            "telefone": forms.TextInput(
                attrs={
                    **widget_attrs(WidgetStyle.FORM_CONTROL),
                    "data-mask": "telefone",
                    "inputmode": "numeric",
                    "placeholder": "(00) 00000-0000",
                    "autocomplete": "off",
                }
            ),
            "ramal": forms.TextInput(
                attrs={
                    **text_attrs(WidgetStyle.FORM_CONTROL),
                    "autocomplete": "off",
                    "maxlength": "20",
                    "placeholder": "Ex.: 1234",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    **widget_attrs(WidgetStyle.FORM_CONTROL),
                    "type": "email",
                    "autocomplete": "off",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["unidade"].required = False
        self.fields["unidade"].empty_label = ""
        self.fields["unidade"].label = "Unidade"
        self.fields["unidade"].widget = UnidadePorExtensoSearchSelect(
            attrs={
                **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                "data-entity-picker": "true",
                "data-entity-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-picker-label": "Unidade",
                "data-picker-hint": "Busque por sigla ou nome da unidade.",
                "data-placeholder": "Buscar unidade",
                "data-empty-message": "Nenhuma unidade encontrada.",
            }
        )
        self.fields["unidade"].queryset = filter_queryset_by_area(Unidade.objects).order_by("nome")

        self.fields["cidade_endereco"].label = "Cidade"
        self.fields["cep"].label = "CEP"
        self.fields["email"].label = "E-mail"
        self.fields["ramal"].label = "Ramal (opcional)"
        self.fields["ramal"].required = False

        # UF não é editável diretamente: a sigla viaja num input hidden e o nome do
        # estado é exibido em campo somente leitura, preenchido pela consulta de CEP.
        self.fields["uf"].required = False
        self.fields["uf"].widget = forms.HiddenInput(attrs={"data-uf-sigla": "true"})
        self.fields["uf_nome"] = forms.CharField(
            label="UF",
            required=False,
            widget=forms.TextInput(
                attrs={
                    **text_attrs(WidgetStyle.FORM_CONTROL),
                    "readonly": "readonly",
                    "tabindex": "-1",
                    "data-uf-nome": "true",
                    "placeholder": "Preenchido pelo CEP",
                }
            ),
        )
        sigla_atual = (self.instance.uf if self.instance else "") or ""
        if sigla_atual:
            self.initial["uf"] = sigla_atual
            self.initial["uf_nome"] = _nome_estado_por_sigla(sigla_atual)

        if self.instance and self.instance.pk and not self.data:
            self.initial["cep"] = format_cep(self.instance.cep)
            self.initial["telefone"] = format_telefone(self.instance.telefone)

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

    def clean_ramal(self):
        ramal = (self.cleaned_data.get("ramal") or "").strip()
        return ramal

    def clean_uf(self):
        uf = (self.cleaned_data.get("uf") or "").strip().upper()
        if not uf:
            return ""
        if len(uf) != 2 or not uf.isalpha():
            raise forms.ValidationError("UF deve conter 2 letras.")
        return uf


def _nome_estado_por_sigla(sigla):
    """Retorna o nome do estado (ex.: PARANÁ) a partir da sigla (ex.: PR)."""
    sigla = (sigla or "").strip().upper()
    if not sigla:
        return ""
    estado = Estado.objects.filter(sigla=sigla).only("nome").first()
    return estado.nome if estado else sigla


_TIPO_FIELD_MAP = [
    (AssinaturaConfiguracao.OFICIO, "assinante_oficio", "Assinante padrão – Ofício"),
    (AssinaturaConfiguracao.JUSTIFICATIVA, "assinante_justificativa", "Assinante padrão – Justificativa"),
    (AssinaturaConfiguracao.PLANO_TRABALHO, "assinante_plano_trabalho", "Assinante padrão – Plano de Trabalho"),
    (AssinaturaConfiguracao.ORDEM_SERVICO, "assinante_ordem_servico", "Assinante padrão – Ordem de Serviço"),
]


class _AssinanteServidorSelect(forms.Select):
    """Select com metadados nas options para o cv-search-picker."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        servidor = getattr(value, "instance", None)
        if servidor is None:
            return option
        option["attrs"].update(_servidor_option_attrs(servidor))
        return option


_ASSINANTE_PICKER_LABELS = {
    "assinante_oficio": "Assinante do Ofício",
    "assinante_justificativa": "Assinante da Justificativa",
    "assinante_plano_trabalho": "Assinante do Plano de Trabalho",
    "assinante_ordem_servico": "Assinante da Ordem de Serviço",
}


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
            picker_label = _ASSINANTE_PICKER_LABELS.get(field_name, label)
            self.fields[field_name] = forms.ModelChoiceField(
                queryset=qs,
                required=False,
                label=label,
                initial=existing.get(tipo),
                widget=_AssinanteServidorSelect(
                    attrs={
                        **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                        "data-entity-picker": "true",
                        "data-entity-picker-mode": "single",
                        "data-picker-variant": "compact",
                        "data-picker-label": picker_label,
                        "data-picker-hint": "Busque por nome, cargo ou CPF.",
                        "data-placeholder": "Buscar servidor",
                        "data-empty-message": "Nenhum servidor encontrado.",
                    }
                ),
            )
            self.fields[field_name].empty_label = ""
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


class ConfiguracaoDestinatarioForm(forms.ModelForm):
    """Destinatário padrão do Ofício: nome, cargo e unidade lotada.

    O nome busca um servidor cadastrado (autocompletando cargo e unidade), mas
    também aceita texto livre quando o servidor não está no banco de dados —
    nesse caso cargo e unidade são preenchidos manualmente.
    """

    class Meta:
        model = ConfiguracaoSistema
        fields = [
            "destinatario_oficio",
            "destinatario_oficio_nome",
            "destinatario_oficio_cargo",
            "destinatario_oficio_unidade",
        ]
        widgets = {
            "destinatario_oficio_nome": forms.HiddenInput(),
            "destinatario_oficio_cargo": forms.TextInput(
                attrs={**widget_attrs(WidgetStyle.FORM_CONTROL), "data-mask": "upper", "placeholder": "Cargo do destinatário"}
            ),
            "destinatario_oficio_unidade": forms.TextInput(
                attrs={**widget_attrs(WidgetStyle.FORM_CONTROL), "data-mask": "upper", "placeholder": "Unidade lotada do destinatário"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["destinatario_oficio"].required = False
        self.fields["destinatario_oficio"].empty_label = ""
        self.fields["destinatario_oficio"].label = "Nome"
        self.fields["destinatario_oficio"].widget = _AssinanteServidorSelect(
            attrs={
                **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                "data-entity-picker": "true",
                "data-entity-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-picker-label": "Nome",
                "data-placeholder": "Buscar ou digitar nome",
                "data-empty-message": "Nenhum servidor encontrado.",
                "data-picker-allow-free-text": "true",
                "data-picker-free-text-message": "Servidor não cadastrado — pressione Enter e preencha cargo/unidade manualmente.",
            }
        )
        self.fields["destinatario_oficio"].queryset = _servidores_assinantes_queryset()
        self.fields["destinatario_oficio_nome"].required = False
        self.fields["destinatario_oficio_cargo"].required = False
        self.fields["destinatario_oficio_cargo"].label = "Cargo"
        self.fields["destinatario_oficio_unidade"].required = False
        self.fields["destinatario_oficio_unidade"].label = "Unidade lotada"

    def clean(self):
        cleaned = super().clean()
        servidor = cleaned.get("destinatario_oficio")
        if servidor:
            if not cleaned.get("destinatario_oficio_nome"):
                cleaned["destinatario_oficio_nome"] = servidor.nome
            if not cleaned.get("destinatario_oficio_cargo") and servidor.cargo_id:
                cleaned["destinatario_oficio_cargo"] = servidor.cargo.nome
            if not cleaned.get("destinatario_oficio_unidade") and servidor.unidade_id:
                cleaned["destinatario_oficio_unidade"] = servidor.unidade.nome
        return cleaned



class TabelaDiariaForm(forms.ModelForm):
    """Nova vigência de valores de diária.

    Só o valor de 24 horas é digitado. Os percentuais de 15% e 30% são
    derivados no ``save()`` do modelo — o formulário nem os expõe, para que não
    exista caminho de entrada que os contradiga.
    """

    class Meta:
        model = TabelaDiaria
        fields = ["faixa", "vigencia_inicio", "valor_24h"]
        widgets = {
            "faixa": forms.Select(attrs={**widget_attrs(WidgetStyle.FORM_CONTROL_FIELD_CONTROL)}),
            # O calendário do sistema é o componente global `cv-date-picker`;
            # o campo em si é só o hidden que ele preenche.
            "vigencia_inicio": forms.HiddenInput(attrs={"data-cv-date-picker-value": ""}),
            "valor_24h": forms.NumberInput(
                attrs={
                    **widget_attrs(WidgetStyle.FORM_CONTROL_FIELD_CONTROL),
                    "step": "0.01",
                    "min": "0.01",
                    "inputmode": "decimal",
                    "data-diaria-base": "",
                    "autocomplete": "off",
                },
            ),
        }

    def clean_valor_24h(self):
        valor = self.cleaned_data["valor_24h"]
        if valor is None or valor <= 0:
            raise forms.ValidationError("Informe um valor maior que zero.")
        return valor

    def clean(self):
        dados = super().clean()
        faixa, inicio = dados.get("faixa"), dados.get("vigencia_inicio")
        if faixa and inicio:
            existente = TabelaDiaria.objects.filter(faixa=faixa, vigencia_inicio=inicio)
            if self.instance.pk:
                existente = existente.exclude(pk=self.instance.pk)
            if existente.exists():
                raise forms.ValidationError(
                    "Já existe uma vigência desta faixa nesta data. "
                    "Edite a existente ou escolha outra data de início.",
                )
        return dados
