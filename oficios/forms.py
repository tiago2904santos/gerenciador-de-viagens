import re

from django import forms

from core.normalizers import normalize_plate
from core.normalizers import normalize_spaces
from core.utils.masks import format_placa
from core.utils.masks import normalize_protocolo

from cadastros.form_widgets import ServidorEquipeSelectMultiple
from cadastros.form_widgets import ServidorMotoristaSelect
from cadastros.form_widgets import ViaturaSelectSingle
from cadastros.models import Viatura

from .models import ModeloMotivoOficio
from .models import Oficio

REG_MOTORISTA_OFICIO_REF = re.compile(r"^(\d{1,3})/(\d{4})$")


class _LegacyServidorEquipeSelectMultiple(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        servidor = getattr(value, "instance", None)
        if servidor is None:
            return option

        cargo = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
        unidade = str(servidor.unidade) if servidor.unidade_id and servidor.unidade else ""
        rg = servidor.rg_formatado or ""
        cpf = servidor.cpf_formatado or ""
        main_parts = [
            servidor.nome,
            f"RG {rg}" if rg else "",
            f"CPF {cpf}" if cpf else "",
            cargo,
        ]
        main = " • ".join(part for part in main_parts if part)
        search = " ".join(part for part in [servidor.nome, rg, cpf, cargo, unidade] if part)
        unidade_id = str(servidor.unidade_id) if servidor.unidade_id else ""
        option["attrs"].update(
            {
                "data-cargo": cargo,
                "data-cpf": cpf,
                "data-main": main,
                "data-meta": unidade,
                "data-rg": rg,
                "data-search": search,
                "data-unidade": unidade,
                "data-unidade-id": unidade_id,
            },
        )
        return option


class _LegacyViaturaSelectSingle(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        viatura = getattr(value, "instance", None)
        if viatura is None:
            return option

        placa = viatura.placa_formatada
        modelo = viatura.modelo or ""
        combustivel = str(viatura.combustivel) if viatura.combustivel_id and viatura.combustivel else ""
        tipo_display = dict(Viatura.TIPO_CHOICES).get(viatura.tipo, "") if viatura.tipo else ""
        unidade = str(viatura.unidade) if viatura.unidade_id and viatura.unidade else ""

        motorista_ids = ",".join(str(m.pk) for m in viatura.motoristas.all())
        unidade_id = str(viatura.unidade_id) if viatura.unidade_id else ""
        meta_parts = [p for p in [modelo, combustivel, tipo_display, unidade] if p]
        linha2_parts = [p for p in [combustivel, tipo_display, unidade] if p]
        search = " ".join(p for p in [viatura.placa, placa.replace("-", ""), modelo, combustivel, tipo_display, unidade] if p)

        option["label"] = " · ".join(p for p in [placa, modelo] if p)
        option["attrs"].update({
            "data-main": placa,
            "data-meta": " · ".join(meta_parts),
            "data-cargo": " · ".join(linha2_parts),
            "data-motorista-ids": motorista_ids,
            "data-unidade-id": unidade_id,
            "data-search": search,
        })
        return option


class _LegacyServidorMotoristaSelect(forms.Select):
    """Select simples com metadados nos options (picker de busca no cliente)."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        servidor = getattr(value, "instance", None)
        if servidor is None:
            return option

        cargo = servidor.cargo.nome if servidor.cargo_id and servidor.cargo else ""
        unidade = str(servidor.unidade) if servidor.unidade_id and servidor.unidade else ""
        rg = servidor.rg_formatado or ""
        cpf = servidor.cpf_formatado or ""
        main_parts = [
            servidor.nome,
            f"RG {rg}" if rg else "",
            f"CPF {cpf}" if cpf else "",
            cargo,
        ]
        main = " • ".join(part for part in main_parts if part)
        search = " ".join(part for part in [servidor.nome, rg, cpf, cargo, unidade] if part)
        unidade_id = str(servidor.unidade_id) if servidor.unidade_id else ""
        option["attrs"].update(
            {
                "data-cargo": cargo,
                "data-cpf": cpf,
                "data-main": main,
                "data-meta": unidade,
                "data-rg": rg,
                "data-search": search,
                "data-unidade": unidade,
                "data-unidade-id": unidade_id,
            },
        )
        return option


class ModeloMotivoSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        modelo = getattr(value, "instance", None)
        if modelo is None:
            return option

        option["attrs"].update(
            {
                "data-texto-motivo": (modelo.texto or "").strip(),
            },
        )
        return option


class OficioForm(forms.ModelForm):
    class Meta:
        model = Oficio
        fields = [
            "numero",
            "ano",
            "data_criacao",
            "protocolo",
            "assunto",
            "motivo",
            "status",
            "roteiro",
            "solicitante",
            "servidores",
            "servidores_termo_autorizacao",
            "viatura",
            "motorista",
            "custeio",
            "custeio_observacao",
        ]
        widgets = {
            "data_criacao": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "motivo": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "roteiro": forms.Select(attrs={"class": "form-select"}),
            "solicitante": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "servidores": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "servidores_termo_autorizacao": forms.SelectMultiple(attrs={"class": "form-select", "size": "8"}),
            "viatura": forms.Select(attrs={"class": "form-select"}),
            "motorista": forms.Select(attrs={"class": "form-select"}),
            "custeio": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput)):
                field.widget.attrs.setdefault("class", "form-control")
            if field_name in {"protocolo", "assunto"}:
                field.widget.attrs.setdefault("data-mask", "upper")
        for optional_field in (
            "roteiro",
            "solicitante",
            "viatura",
            "motorista",
            "servidores",
            "servidores_termo_autorizacao",
        ):
            if optional_field in self.fields:
                self.fields[optional_field].required = False

    def clean_protocolo(self):
        return normalize_protocolo(self.cleaned_data.get("protocolo", ""))

    def clean_assunto(self):
        return normalize_spaces(self.cleaned_data.get("assunto", ""))

    def clean_motivo(self):
        return normalize_spaces(self.cleaned_data.get("motivo", ""))

    def clean_custeio_observacao(self):
        return normalize_spaces(self.cleaned_data.get("custeio_observacao", ""))

    def clean(self):
        return super().clean()


class OficioDadosViajantesForm(OficioForm):
    modelo_motivo = forms.ModelChoiceField(
        label="Modelo de motivo",
        queryset=ModeloMotivoOficio.objects.none(),
        required=False,
        empty_label="Selecione um modelo (opcional)",
        widget=ModeloMotivoSelect(attrs={"class": "form-select", "data-modelo-motivo-select": "true"}),
    )

    class Meta(OficioForm.Meta):
        fields = [
            "protocolo",
            "motivo",
            "custeio",
            "custeio_observacao",
            "viatura",
            "servidores",
            "servidores_termo_autorizacao",
        ]
        widgets = {
            "protocolo": forms.TextInput(attrs={"class": "form-control", "data-mask": "protocolo"}),
            "motivo": forms.Textarea(
                attrs={
                    "class": "cv-field__control cv-field__control--textarea",
                    "rows": 4,
                    "data-motivo-textarea": "true",
                },
            ),
            "custeio": forms.Select(
                attrs={"class": "form-select", "data-oficio-custeio-field": "true"},
            ),
            "custeio_observacao": forms.TextInput(attrs={"class": "form-control"}),
            "viatura": ViaturaSelectSingle(
                attrs={
                    "class": "form-select cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "detailed",
                    "data-picker-label": "Viatura",
                    "data-picker-hint": "Busque por placa, modelo, combustível ou tipo.",
                    "data-placeholder": "Buscar por placa ou modelo",
                    "data-empty-message": "Nenhuma viatura encontrada.",
                    "data-empty-selected": "Nenhuma viatura selecionada.",
                },
            ),
            "servidores": ServidorEquipeSelectMultiple(
                attrs={
                    "class": "form-select cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "multi",
                    "data-picker-variant": "detailed",
                    "data-picker-term-control": "true",
                    "data-picker-driver-control": "true",
                    "data-picker-label": "Viajantes",
                    "data-picker-hint": "Busque por nome, CPF ou RG. Em cada card, defina se o termo de autorização será gerado.",
                    "data-cv-termos-name": "servidores_termo_autorizacao",
                    "data-panel-title": "EQUIPE DO OFÍCIO",
                    "data-placeholder": "Buscar por nome, CPF ou RG",
                    "data-empty-message": "Nenhum servidor encontrado.",
                    "data-empty-selected": "Nenhum viajante selecionado.",
                },
            ),
            "servidores_termo_autorizacao": ServidorEquipeSelectMultiple(
                attrs={
                    "class": "form-select cv-search-picker__termos-native",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modelo_motivo"].queryset = ModeloMotivoOficio.objects.order_by("ordem", "nome")
        self.fields["protocolo"].required = False
        self.fields["motivo"].required = False
        self.fields["custeio"].required = False
        self.fields["viatura"].empty_label = ""
        self.fields["servidores"].required = False
        self.fields["servidores_termo_autorizacao"].queryset = self.fields["servidores"].queryset
        self.fields["servidores_termo_autorizacao"].required = False
        if not self.is_bound and not (self.instance.motivo or "").strip():
            modelo_padrao = self.fields["modelo_motivo"].queryset.filter(is_padrao=True).first()
            if modelo_padrao:
                if not self.initial.get("modelo_motivo"):
                    self.initial["modelo_motivo"] = modelo_padrao.pk
                if not (self.initial.get("motivo") or "").strip():
                    self.initial["motivo"] = modelo_padrao.texto
        if not self.is_bound and self.instance.pk and not self.instance.servidores_termo_autorizacao.exists():
            self.initial["servidores_termo_autorizacao"] = list(
                self.instance.servidores.values_list("pk", flat=True),
            )

    def clean_protocolo(self):
        protocolo = normalize_protocolo(self.cleaned_data.get("protocolo", ""))
        action = (self.data.get("action") or "").strip() if self.is_bound else ""
        if action in {"wizard_next", "save_continue"}:
            return protocolo
        if protocolo and len(protocolo) != 9:
            raise forms.ValidationError("Informe um protocolo válido com 9 dígitos.")
        return protocolo

    def clean_motivo(self):
        return normalize_spaces(self.cleaned_data.get("motivo", ""))

    def clean(self):
        cleaned = super().clean()
        servidores = list(cleaned.get("servidores") or [])
        termos = list(cleaned.get("servidores_termo_autorizacao") or [])
        servidor_ids = {servidor.pk for servidor in servidores}

        if self.is_bound and "servidores_termo_autorizacao_present" not in self.data:
            termos = servidores
        cleaned["servidores_termo_autorizacao"] = [
            servidor for servidor in termos if servidor.pk in servidor_ids
        ]
        return cleaned


class OficioTransporteForm(forms.ModelForm):
    transporte_busca_ui = forms.CharField(
        label="BUSCAR VIATURA",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "cv-search-picker__input",
                "data-oficio-viatura-busca": "true",
                "placeholder": "Buscar por placa, unidade, combustível ou tipo",
                "autocomplete": "off",
                "type": "search",
                "role": "combobox",
                "aria-autocomplete": "list",
            },
        ),
    )

    porte_transporte_armas = forms.TypedChoiceField(
        label="Porte/transporte de armas",
        coerce=lambda v: v == "sim",
        choices=[("sim", "Sim"), ("nao", "Não")],
        widget=forms.Select(attrs={"class": "form-select", "data-oficio-porte-armas": "true"}),
    )

    class Meta:
        model = Oficio
        fields = [
            "viatura",
            "porte_transporte_armas",
            "transporte_placa_manual",
            "transporte_modelo_manual",
            "transporte_combustivel_manual",
            "transporte_tipo_manual",
            "motorista_modo",
            "motorista",
            "motorista_manual_nome",
            "motorista_oficio_referencia",
            "motorista_protocolo_ref",
        ]
        widgets = {
            "viatura": forms.HiddenInput(attrs={"data-oficio-viatura-id": "true"}),
            "motorista_modo": forms.HiddenInput(attrs={"data-oficio-motorista-modo": "true"}),
            "transporte_placa_manual": forms.HiddenInput(attrs={"data-oficio-placa-hidden": "true"}),
            "transporte_modelo_manual": forms.TextInput(
                attrs={"class": "form-control", "data-oficio-viatura-modelo": "true", "data-mask": "upper"},
            ),
            "transporte_combustivel_manual": forms.Select(
                attrs={"class": "form-select", "data-oficio-viatura-combustivel": "true"},
            ),
            "transporte_tipo_manual": forms.Select(
                attrs={"class": "form-select", "data-oficio-viatura-tipo": "true"},
            ),
            "motorista": ServidorMotoristaSelect(
                attrs={
                    "class": "form-select cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "detailed",
                    "data-empty-selected": "Nenhum motorista selecionado.",
                    "data-empty-message": "Nenhum servidor encontrado.",
                    "data-placeholder": "Buscar por nome, CPF ou RG",
                    "data-panel-title": "MOTORISTA SELECIONADO",
                },
            ),
            "motorista_manual_nome": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-mask": "upper",
                    "data-oficio-motorista-manual": "true",
                    "placeholder": "Digite o nome do motorista",
                },
            ),
            "motorista_oficio_referencia": forms.HiddenInput(
                attrs={
                    "data-oficio-motorista-hidden": "true",
                },
            ),
            "motorista_protocolo_ref": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "data-mask": "protocolo",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["viatura"].required = False
        self.fields["viatura"].empty_label = ""
        self.fields["motorista"].required = False
        self.fields["motorista"].empty_label = ""
        self.fields["transporte_combustivel_manual"].required = False
        self.fields["transporte_tipo_manual"].required = False
        self.fields["porte_transporte_armas"].required = False
        self.fields["transporte_tipo_manual"].choices = [("", "---------")] + list(Viatura.TIPO_CHOICES)
        if not self.is_bound and self.instance.pk:
            self.initial.setdefault(
                "porte_transporte_armas",
                "sim" if self.instance.porte_transporte_armas else "nao",
            )
            if not self.instance.transporte_tipo_manual and not self.instance.viatura_id:
                self.initial.setdefault("transporte_tipo_manual", Viatura.TIPO_DESCARACTERIZADA)
        elif not self.is_bound:
            self.initial.setdefault("porte_transporte_armas", "sim")
            self.initial.setdefault("motorista_modo", Oficio.MOTORISTA_MODO_SERVIDOR)
            self.initial.setdefault("transporte_tipo_manual", Viatura.TIPO_DESCARACTERIZADA)

        from django.utils import timezone as tz

        ano_motorista = None
        if self.instance and self.instance.pk and self.instance.ano:
            ano_motorista = self.instance.ano
        if not ano_motorista:
            ano_motorista = tz.localdate().year
        ano_str = str(ano_motorista)
        self.fields["motorista_oficio_referencia"].widget.attrs["data-mask-year"] = ano_str
        self.fields["motorista_oficio_referencia"].widget.attrs["data-oficio-ano"] = ano_str

        if not self.is_bound and self.instance.pk:
            modo = self.instance.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR
            self.initial.setdefault("motorista_modo", modo)
            if self.instance.viatura_id and self.instance.viatura:
                v = self.instance.viatura
                self.initial["transporte_placa_manual"] = v.placa
                self.initial["transporte_busca_ui"] = v.placa_formatada
                self.initial["transporte_modelo_manual"] = v.modelo or ""
                if v.combustivel_id:
                    self.initial["transporte_combustivel_manual"] = v.combustivel_id
                if v.tipo:
                    self.initial["transporte_tipo_manual"] = v.tipo
            elif (self.instance.transporte_placa_manual or "").strip():
                self.initial["transporte_busca_ui"] = format_placa(self.instance.transporte_placa_manual)
            if modo == Oficio.MOTORISTA_MODO_MANUAL:
                self.initial.setdefault("motorista_manual_nome", self.instance.motorista_manual_nome)
            self.initial.setdefault("motorista_oficio_referencia", self.instance.motorista_oficio_referencia)
            self.initial.setdefault("motorista_protocolo_ref", self.instance.motorista_protocolo_ref)

    def clean_porte_transporte_armas(self):
        raw = self.data.get("porte_transporte_armas")
        if raw not in ("sim", "nao"):
            if self.instance.pk:
                return self.instance.porte_transporte_armas
            return True
        return raw == "sim"

    def clean_motorista_oficio_referencia(self):
        raw = (self.cleaned_data.get("motorista_oficio_referencia") or "").strip()
        if not raw:
            return ""
        m = REG_MOTORISTA_OFICIO_REF.match(raw)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
        return raw[: self.fields["motorista_oficio_referencia"].max_length]

    def clean_motorista_protocolo_ref(self):
        return normalize_protocolo(self.cleaned_data.get("motorista_protocolo_ref", "") or "")

    def clean_transporte_placa_manual(self):
        raw = self.cleaned_data.get("transporte_placa_manual", "") or ""
        normalized = normalize_plate(raw)
        viatura = self.cleaned_data.get("viatura")
        if viatura is not None:
            return normalized if normalized else ""
        if not normalized:
            return ""
        if len(normalized) != 7:
            raise forms.ValidationError("Use o formato de placa Mercosul ou antiga (7 caracteres).")
        return normalized

    def clean(self):
        data = super().clean()
        modo = data.get("motorista_modo") or Oficio.MOTORISTA_MODO_SERVIDOR
        if modo == Oficio.MOTORISTA_MODO_MANUAL:
            data["motorista"] = None
        else:
            data["motorista_manual_nome"] = ""
        motorista = data.get("motorista")
        if modo != Oficio.MOTORISTA_MODO_MANUAL and motorista and self.instance.pk:
            equipe = set(self.instance.servidores.values_list("pk", flat=True))
            if motorista.pk in equipe:
                data["motorista_oficio_referencia"] = ""
                data["motorista_protocolo_ref"] = ""
        return data


class ModeloMotivoOficioForm(forms.ModelForm):
    nome = forms.CharField(
        label="Nome",
        help_text="Use um nome curto para identificar o modelo.",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    texto = forms.CharField(
        label="Texto do modelo",
        help_text="Este texto será copiado para o motivo do ofício e poderá ser editado antes de salvar.",
        widget=forms.Textarea(attrs={"class": "cv-field__control cv-field__control--textarea", "rows": 4}),
    )
    is_padrao = forms.BooleanField(
        label="Modelo padrão",
        required=False,
        help_text="Marque apenas se este modelo deve ser sugerido como principal.",
        widget=forms.CheckboxInput(attrs={"class": "app-card-toggle__input"}),
    )

    class Meta:
        model = ModeloMotivoOficio
        fields = ["nome", "texto", "is_padrao"]
