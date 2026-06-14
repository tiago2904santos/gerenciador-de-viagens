from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory
from django.utils.text import slugify

from cadastros.form_widgets import ServidorMotoristaSelect
from cadastros.models import Cargo
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Unidade
from cadastros.services import resolver_sede_ids_desde_configuracao

from .models import AtividadePlanoTrabalho
from .models import EfetivoPlano
from .models import HorarioAtendimento
from .models import PlanoDestino
from .models import PlanoTrabalho
from .models import ProgramaSolicitante


def _servidor_picker_widget(panel_title: str, field_label: str) -> forms.Select:
    return ServidorMotoristaSelect(
        attrs={
            "class": "form-select cv-search-picker__native",
            "data-cv-search-picker": "true",
            "data-pt-coordenador-picker": "true",
            "data-picker-mode": "single",
            "data-picker-variant": "compact",
            "data-picker-label": field_label,
            "data-panel-title": panel_title,
            "data-placeholder": "Nome completo",
            "data-empty-message": "Nenhum servidor encontrado. Continue digitando para usar este nome.",
        },
    )


class PlanoIdentificacaoForm(forms.ModelForm):
    """Etapa 1 — contextualização, destino/datas (clonado de termos), coordenadores."""

    PROGRAMA_OUTRO_VALUE = "__outro__"

    programa = forms.ChoiceField(
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-select",
                "data-pt-programa-select": "true",
                "data-pt-programa-outro-value": PROGRAMA_OUTRO_VALUE,
            },
        ),
    )
    horario_atendimento = forms.ChoiceField(
        required=False,
        widget=forms.Select(
            attrs={
                "class": "form-select",
            },
        ),
    )

    class Meta:
        model = PlanoTrabalho
        fields = [
            "programa",
            "programa_outros",
            "destino_estado",
            "destino_cidade",
            "data_evento_inicio",
            "data_evento_fim",
            "horario_atendimento",
            "contextualizacao",
            "consideracao_final",
            "coordenador_adm_modo",
            "coordenador_adm",
            "coordenador_adm_nome_manual",
            "coordenador_adm_cargo_manual",
            "coordenador_op_modo",
            "coordenador_op",
            "coordenador_op_nome_manual",
            "coordenador_op_cargo_manual",
        ]
        widgets = {
            "programa_outros": forms.TextInput(
                attrs={
                    "class": "cv-field__control",
                    "placeholder": "Informe o programa quando não estiver na lista",
                    "autocomplete": "off",
                },
            ),
            "destino_estado": forms.Select(
                attrs={
                    "class": "cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "compact",
                    "data-placeholder": "Buscar estado...",
                    "data-empty-message": "Nenhum estado encontrado.",
                },
            ),
            "destino_cidade": forms.Select(
                attrs={
                    "class": "cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "compact",
                    "data-placeholder": "Buscar cidade...",
                    "data-empty-message": "Nenhuma cidade encontrada.",
                },
            ),
            "data_evento_inicio": forms.HiddenInput(attrs={"data-cv-date-picker-start-value": "true"}),
            "data_evento_fim": forms.HiddenInput(attrs={"data-cv-date-picker-end-value": "true"}),
            "contextualizacao": forms.Textarea(
                attrs={
                    "rows": 7,
                    "class": "cv-field__control cv-field__control--textarea",
                    "placeholder": "Deixe em branco para gerar automaticamente a partir do destino e do programa.",
                },
            ),
            "consideracao_final": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "cv-field__control cv-field__control--textarea",
                    "placeholder": "Deixe em branco para gerar automaticamente a partir do destino.",
                },
            ),
            "coordenador_adm_modo": forms.HiddenInput(attrs={"data-pt-coordenador-modo": "adm"}),
            "coordenador_op_modo": forms.HiddenInput(attrs={"data-pt-coordenador-modo": "op"}),
            "coordenador_adm_nome_manual": forms.HiddenInput(
                attrs={"data-pt-coordenador-nome-manual": "adm"},
            ),
            "coordenador_adm_cargo_manual": forms.Select(
                attrs={"class": "form-select"},
            ),
            "coordenador_op_nome_manual": forms.HiddenInput(
                attrs={"data-pt-coordenador-nome-manual": "op"},
            ),
            "coordenador_op_cargo_manual": forms.Select(
                attrs={"class": "form-select"},
            ),
        }

    def __init__(self, *args, **kwargs):
        if args and args[0] is not None:
            data = args[0].copy()
            if not (data.get("programa") or "").strip() and (data.get("programa_outros") or "").strip():
                data["programa"] = self.PROGRAMA_OUTRO_VALUE
            args = (data, *args[1:])
        elif kwargs.get("data") is not None:
            data = kwargs["data"].copy()
            if not (data.get("programa") or "").strip() and (data.get("programa_outros") or "").strip():
                data["programa"] = self.PROGRAMA_OUTRO_VALUE
            kwargs["data"] = data

        super().__init__(*args, **kwargs)
        estado_id, cidade_id = self._resolve_destino_inicial()
        programa_choices = [("", "Selecione um programa (opcional)"), (self.PROGRAMA_OUTRO_VALUE, "Outro")]
        programa_choices.extend(
            [
                (str(programa.pk), programa.nome)
                for programa in ProgramaSolicitante.objects.filter(ativo=True).order_by("ordem", "nome")
            ]
        )

        for name in self.fields:
            self.fields[name].required = False

        self.fields["programa"].choices = programa_choices
        programa_inicial = ""
        if self.is_bound:
            programa_inicial = (self.data.get("programa") or "").strip()
        elif self.instance and self.instance.pk:
            if self.instance.programa_id:
                programa_inicial = str(self.instance.programa_id)
            elif self.instance.programa_outros:
                programa_inicial = self.PROGRAMA_OUTRO_VALUE
        self.initial["programa"] = programa_inicial
        self.programa_outros_selected = programa_inicial == self.PROGRAMA_OUTRO_VALUE

        horarios_ativos = list(HorarioAtendimento.objects.filter(ativo=True).order_by("ordem", "faixa"))
        horario_choices = [("", "Selecione um horário (opcional)")]
        horario_choices.extend([(horario.faixa, horario.faixa) for horario in horarios_ativos])
        horario_inicial = ""
        if self.is_bound:
            horario_inicial = (self.data.get("horario_atendimento") or "").strip()
        elif self.instance and self.instance.pk:
            horario_inicial = (self.instance.horario_atendimento or "").strip()
        if horario_inicial and horario_inicial not in {valor for valor, _ in horario_choices}:
            horario_choices.append((horario_inicial, horario_inicial))
        self.fields["horario_atendimento"].choices = horario_choices
        self.initial["horario_atendimento"] = horario_inicial

        self.fields["destino_estado"].empty_label = ""
        self.fields["destino_estado"].queryset = Estado.objects.order_by("nome")
        self.fields["destino_estado"].initial = estado_id
        self.initial["destino_estado"] = estado_id
        self.fields["destino_estado"].widget.attrs["data-picker-initial-value"] = str(estado_id or "")

        self.fields["destino_cidade"].empty_label = ""
        if estado_id:
            self.fields["destino_cidade"].queryset = (
                Cidade.objects.select_related("estado").filter(estado_id=estado_id).order_by("nome")
            )
            self.fields["destino_cidade"].widget.attrs.pop("disabled", None)
        else:
            self.fields["destino_cidade"].queryset = Cidade.objects.select_related("estado").none()
            self.fields["destino_cidade"].widget.attrs["disabled"] = True
        self.fields["destino_cidade"].initial = cidade_id
        self.initial["destino_cidade"] = cidade_id
        self.fields["destino_cidade"].widget.attrs["data-picker-initial-value"] = str(cidade_id or "")
        self.destination_rows = self._build_destination_rows(estado_id, cidade_id)

        cargo_choices = [("", "Selecione um cargo")]
        cargo_choices.extend([(cargo.nome, cargo.nome) for cargo in Cargo.objects.order_by("nome")])
        for campo in ("coordenador_adm_cargo_manual", "coordenador_op_cargo_manual"):
            valor_atual = ""
            if self.is_bound:
                valor_atual = (self.data.get(campo) or "").strip()
            elif self.instance and self.instance.pk:
                valor_atual = (getattr(self.instance, campo, "") or "").strip()
            if valor_atual and valor_atual not in {valor for valor, _ in cargo_choices}:
                cargo_choices.append((valor_atual, valor_atual))
            self.fields[campo].widget.choices = cargo_choices

        servidores_qs = Servidor.objects.select_related("cargo", "unidade").order_by("nome")
        for campo, titulo, papel, rotulo in (
            ("coordenador_adm", "COORDENADOR ADMINISTRATIVO", "adm", "Coordenador administrativo"),
            ("coordenador_op", "COORDENADOR OPERACIONAL", "op", "Coordenador operacional (opcional)"),
        ):
            field = self.fields[campo]
            field.queryset = servidores_qs
            field.empty_label = ""
            widget = _servidor_picker_widget(titulo, rotulo)
            widget.choices = field.choices
            field.widget = widget
            valor = None
            if self.is_bound:
                valor = self.data.get(campo) or None
            elif self.instance and self.instance.pk:
                valor = getattr(self.instance, f"{campo}_id", None)
            elif self.initial.get(campo):
                valor = getattr(self.initial.get(campo), "pk", self.initial.get(campo))
            field.widget.attrs["data-picker-initial-value"] = str(valor or "")
            field.widget.attrs["data-pt-coordenador-picker"] = papel
            field.widget.attrs["data-pt-coordenador-manual-name"] = f"coordenador_{papel}_nome_manual"
            field.widget.attrs["data-pt-coordenador-cargo-name"] = f"coordenador_{papel}_cargo_manual"
            field.widget.attrs["data-pt-coordenador-modo-name"] = f"coordenador_{papel}_modo"

    def clean_programa(self):
        valor = (self.cleaned_data.get("programa") or "").strip()
        self.programa_outros_selected = valor == self.PROGRAMA_OUTRO_VALUE
        if not valor or self.programa_outros_selected:
            return None
        try:
            return ProgramaSolicitante.objects.get(pk=valor, ativo=True)
        except (ProgramaSolicitante.DoesNotExist, TypeError, ValueError):
            raise forms.ValidationError("Selecione um programa válido.")

    def clean_horario_atendimento(self):
        return (self.cleaned_data.get("horario_atendimento") or "").strip()

    def _resolve_destino_inicial(self):
        cidade_id = None
        estado_id = None

        if self.is_bound:
            cidade_id = self.data.get("destino_cidade") or None
            estado_id = self.data.get("destino_estado") or None
        elif self.instance and self.instance.pk and self.instance.destino_estado_id:
            cidade_id = self.instance.destino_cidade_id
            estado_id = self.instance.destino_estado_id
        else:
            cfg_estado_id, _cfg_cidade_id, _ = resolver_sede_ids_desde_configuracao()
            estado_id = cfg_estado_id
            cidade_id = None

        if cidade_id:
            cidade_obj = Cidade.objects.select_related("estado").filter(pk=cidade_id).first()
            if cidade_obj:
                cidade_id = cidade_obj.pk
                estado_id = cidade_obj.estado_id

        return estado_id, cidade_id

    def _build_destination_rows(self, estado_id, cidade_id):
        rows = []
        if self.is_bound:
            rows.append(self._destination_row_from_values(0, self.data.get("destino_estado"), self.data.get("destino_cidade")))
            extra_indexes = sorted(
                {
                    int(name.rsplit("_", 1)[1])
                    for name in self.data.keys()
                    if name.startswith("destino_estado_") and name.rsplit("_", 1)[1].isdigit()
                }
            )
            for idx in extra_indexes:
                rows.append(
                    self._destination_row_from_values(
                        idx,
                        self.data.get(f"destino_estado_{idx}"),
                        self.data.get(f"destino_cidade_{idx}"),
                    )
                )
        else:
            destinos = []
            if self.instance and self.instance.pk:
                destinos = list(self.instance.destinos.select_related("cidade", "estado").order_by("ordem", "pk"))
            if destinos:
                rows.append(self._destination_row_from_values(0, destinos[0].estado_id, destinos[0].cidade_id))
                for idx, destino in enumerate(destinos[1:], 1):
                    rows.append(self._destination_row_from_values(idx, destino.estado_id, destino.cidade_id))
            else:
                rows.append(self._destination_row_from_values(0, estado_id, cidade_id))

        return rows or [self._destination_row_from_values(0, estado_id, cidade_id)]

    def _destination_row_from_values(self, index, estado_id, cidade_id):
        estado_id = str(estado_id or "").strip()
        cidade_id = str(cidade_id or "").strip()
        cidade_qs = Cidade.objects.select_related("estado").none()
        if estado_id:
            cidade_qs = Cidade.objects.select_related("estado").filter(estado_id=estado_id).order_by("nome")
        return {
            "index": index,
            "is_primary": index == 0,
            "estado_id": estado_id,
            "cidade_id": cidade_id,
            "cidades": list(cidade_qs),
        }

    def clean(self):
        cleaned = super().clean()
        cidade = cleaned.get("destino_cidade")
        estado = cleaned.get("destino_estado")
        inicio = cleaned.get("data_evento_inicio")
        fim = cleaned.get("data_evento_fim")

        if cidade:
            cleaned["destino_estado"] = cidade.estado
        elif estado and not cidade:
            self.add_error("destino_cidade", "Informe a cidade do destino.")

        if inicio and not fim:
            cleaned["data_evento_fim"] = inicio
        if inicio and fim and fim < inicio:
            self.add_error("data_evento_fim", "A data final não pode ser anterior à data inicial.")

        self._normalize_coordenador(cleaned, "adm")
        self._normalize_coordenador(cleaned, "op")

        if self.programa_outros_selected:
            if not (cleaned.get("programa_outros") or "").strip():
                self.add_error("programa_outros", "Informe o outro programa.")
            cleaned["programa"] = None
        else:
            cleaned["programa_outros"] = ""

        destinos = []
        cidade = cleaned.get("destino_cidade")
        if cidade:
            destinos.append((cidade.estado_id, cidade.pk))

        extra_indexes = sorted(
            {
                int(name.rsplit("_", 1)[1])
                for name in self.data.keys()
                if name.startswith("destino_estado_") and name.rsplit("_", 1)[1].isdigit()
            }
        )
        for idx in extra_indexes:
            estado_raw = (self.data.get(f"destino_estado_{idx}") or "").strip()
            cidade_raw = (self.data.get(f"destino_cidade_{idx}") or "").strip()
            if not estado_raw and not cidade_raw:
                continue
            if estado_raw and not cidade_raw:
                self.add_error(None, f"Informe a cidade do destino adicional {idx}.")
                continue
            cidade_obj = Cidade.objects.select_related("estado").filter(pk=cidade_raw).first() if cidade_raw else None
            if not cidade_obj:
                self.add_error(None, f"Selecione uma cidade válida para o destino adicional {idx}.")
                continue
            destinos.append((cidade_obj.estado_id, cidade_obj.pk))

        self.cleaned_destinos = destinos

        return cleaned

    def _normalize_coordenador(self, cleaned, papel):
        servidor_key = f"coordenador_{papel}"
        modo_key = f"coordenador_{papel}_modo"
        nome_key = f"coordenador_{papel}_nome_manual"
        cargo_key = f"coordenador_{papel}_cargo_manual"

        servidor = cleaned.get(servidor_key)
        nome_manual = (cleaned.get(nome_key) or "").strip()
        cargo_manual = (cleaned.get(cargo_key) or "").strip()

        cleaned[nome_key] = nome_manual
        cleaned[cargo_key] = cargo_manual

        if servidor:
            cleaned[modo_key] = PlanoTrabalho.COORDENADOR_MODO_SERVIDOR
            cleaned[nome_key] = ""
            cleaned[cargo_key] = ""
            return

        cleaned[modo_key] = PlanoTrabalho.COORDENADOR_MODO_MANUAL
        cleaned[servidor_key] = None
        if not nome_manual:
            cleaned[cargo_key] = ""

    def save(self, commit=True):
        instance = super().save(commit=False)
        if getattr(self, "cleaned_destinos", None):
            estado_id, cidade_id = self.cleaned_destinos[0]
            instance.destino_estado_id = estado_id
            instance.destino_cidade_id = cidade_id
        else:
            instance.destino_estado = None
            instance.destino_cidade = None
        if commit:
            instance.save()
            self._save_destinos(instance)
        return instance

    def _save_destinos(self, instance):
        PlanoDestino.objects.filter(plano=instance).delete()
        destinos = getattr(self, "cleaned_destinos", []) or []
        PlanoDestino.objects.bulk_create(
            [
                PlanoDestino(plano=instance, estado_id=estado_id, cidade_id=cidade_id, ordem=ordem)
                for ordem, (estado_id, cidade_id) in enumerate(destinos, 1)
            ]
        )


class PlanoDiariasForm(forms.ModelForm):
    """Etapa 2 — saída/chegada na sede (4 inputs simples para o motor de diárias)."""

    class Meta:
        model = PlanoTrabalho
        fields = [
            "saida_sede_data",
            "saida_sede_hora",
            "chegada_sede_data",
            "chegada_sede_hora",
        ]
        widgets = {
            "saida_sede_data": forms.HiddenInput(attrs={"data-cv-date-picker-value": "true", "data-pt-diarias-input": "true"}),
            "saida_sede_hora": forms.TimeInput(
                attrs={"type": "time", "class": "cv-field__control", "data-pt-diarias-input": "true"},
                format="%H:%M",
            ),
            "chegada_sede_data": forms.HiddenInput(attrs={"data-cv-date-picker-value": "true", "data-pt-diarias-input": "true"}),
            "chegada_sede_hora": forms.TimeInput(
                attrs={"type": "time", "class": "cv-field__control", "data-pt-diarias-input": "true"},
                format="%H:%M",
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        saida_data = cleaned.get("saida_sede_data")
        saida_hora = cleaned.get("saida_sede_hora")
        chegada_data = cleaned.get("chegada_sede_data")
        chegada_hora = cleaned.get("chegada_sede_hora")
        if saida_data and chegada_data and saida_hora and chegada_hora:
            from datetime import datetime

            if datetime.combine(chegada_data, chegada_hora) <= datetime.combine(saida_data, saida_hora):
                self.add_error("chegada_sede_data", "A chegada na sede deve ser depois da saída.")
        return cleaned


class EfetivoPlanoForm(forms.ModelForm):
    class Meta:
        model = EfetivoPlano
        fields = ["unidade", "cargo", "quantidade"]
        widgets = {
            "unidade": forms.Select(
                attrs={
                    "class": "cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "compact",
                    "data-placeholder": "Buscar unidade...",
                    "data-empty-message": "Nenhuma unidade encontrada.",
                    "data-pt-efetivo-unidade": "true",
                }
            ),
            "cargo": forms.Select(attrs={"class": "form-select", "data-pt-efetivo-cargo": "true"}),
            "quantidade": forms.NumberInput(
                attrs={"class": "cv-field__control", "min": "1", "step": "1", "data-pt-efetivo-qtd": "true"},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidade"].queryset = Unidade.objects.order_by("nome")
        self.fields["unidade"].empty_label = ""
        self.fields["cargo"].queryset = Cargo.objects.order_by("nome")
        self.fields["cargo"].empty_label = "Selecione o cargo"

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned

        unidade = cleaned.get("unidade")
        cargo = cleaned.get("cargo")
        quantidade = cleaned.get("quantidade")
        if not any([unidade, cargo, quantidade]):
            return cleaned
        if not unidade:
            self.add_error("unidade", "Selecione a unidade.")
        if not cargo:
            self.add_error("cargo", "Selecione o cargo.")
        return cleaned


EfetivoPlanoFormSet = inlineformset_factory(
    PlanoTrabalho,
    EfetivoPlano,
    form=EfetivoPlanoForm,
    extra=0,
    min_num=1,
    validate_min=False,
    can_delete=True,
)


class ProgramaSolicitanteForm(forms.ModelForm):
    class Meta:
        model = ProgramaSolicitante
        fields = ["nome", "ativo", "ordem"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "cv-field__control", "data-mask": "upper"}),
            "ordem": forms.NumberInput(attrs={"class": "cv-field__control", "min": "0", "step": "1"}),
        }


class AtividadePlanoTrabalhoForm(forms.ModelForm):
    """CRUD do catálogo de atividades (meta obrigatória, recurso opcional)."""

    class Meta:
        model = AtividadePlanoTrabalho
        fields = ["codigo", "nome", "meta", "recurso_necessario", "ordem", "ativo"]
        widgets = {
            "codigo": forms.TextInput(
                attrs={"class": "cv-field__control", "placeholder": "Ex.: CIN", "autocomplete": "off"},
            ),
            "nome": forms.TextInput(
                attrs={"class": "cv-field__control", "autocomplete": "off"},
            ),
            "meta": forms.Textarea(
                attrs={"rows": 4, "class": "cv-field__control cv-field__control--textarea"},
            ),
            "recurso_necessario": forms.Textarea(
                attrs={"rows": 4, "class": "cv-field__control cv-field__control--textarea"},
            ),
            "ordem": forms.NumberInput(attrs={"class": "cv-field__control", "min": "0", "step": "10"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["meta"].required = True
        self.fields["recurso_necessario"].required = False

    def clean_codigo(self):
        codigo = (self.cleaned_data.get("codigo") or "").strip()
        if not codigo:
            raise forms.ValidationError("Informe o código da atividade.")
        normalizado = slugify(codigo).replace("-", "_").upper()
        if not normalizado:
            raise forms.ValidationError("Código inválido.")
        qs = AtividadePlanoTrabalho.objects.filter(codigo=normalizado)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Já existe uma atividade com este código.")
        return normalizado


class HorarioAtendimentoForm(forms.ModelForm):
    class Meta:
        model = HorarioAtendimento
        fields = ["faixa", "ativo", "ordem"]
        widgets = {
            "faixa": forms.TextInput(attrs={"class": "cv-field__control", "placeholder": "Ex.: 09:00 até 17:00"}),
            "ordem": forms.NumberInput(attrs={"class": "cv-field__control", "min": "0", "step": "1"}),
        }
