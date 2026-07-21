from __future__ import annotations

from django import forms
from django.db.models import Q

from cadastros.form_widgets import ServidorEquipeSelectMultiple
from cadastros.form_widgets import ServidorMotoristaSelect
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.services import resolver_sede_ids_desde_configuracao
from core.tenancy import filter_queryset_by_area
from oficios.forms import ModeloMotivoSelect
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio

from .models import OrdemServico

FUNCOES_SERVIDOR_VALIDAS = {
    OrdemServico.FUNCAO_CONDUCAO,
    OrdemServico.FUNCAO_TECNICO,
    OrdemServico.FUNCAO_APOIO,
    OrdemServico.FUNCAO_COORDENACAO,
    OrdemServico.FUNCAO_PREPARACAO,
}


class OficioMultiSelectWidget(forms.SelectMultiple):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        oficio = getattr(value, "instance", None)
        if oficio is None:
            return option
        protocolo = oficio.protocolo or ""
        assunto = oficio.assunto or ""
        main = f"Ofício {oficio.numero_formatado}"
        option["label"] = main
        option["attrs"].update({
            "data-main": main,
            "data-meta": " - ".join(p for p in [protocolo, assunto] if p),
            "data-search": " ".join(p for p in [oficio.numero_formatado, protocolo, assunto, str(oficio.pk)] if p),
        })
        return option


class OrdemServicoForm(forms.ModelForm):
    destino_estado = forms.ModelChoiceField(
        queryset=Estado.objects.none(),
        required=False,
        widget=forms.Select(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-picker-open-all": "true",
                "data-placeholder": "Buscar estado...",
                "data-empty-message": "Nenhum estado encontrado.",
            },
        ),
    )
    destino_cidade = forms.ModelChoiceField(
        queryset=Cidade.objects.none(),
        required=False,
        widget=forms.Select(
            attrs={
                "class": "cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-picker-open-all": "true",
                "data-placeholder": "Buscar cidade...",
                "data-empty-message": "Nenhuma cidade encontrada.",
            },
        ),
    )
    modelo_motivo = forms.ModelChoiceField(
        label="Modelo de motivo",
        queryset=ModeloMotivoOficio.objects.none(),
        required=False,
        empty_label="Selecione um modelo (opcional)",
        widget=ModeloMotivoSelect(attrs={
            "class": "form-select",
            "data-modelo-motivo-select": "true",
        }),
    )

    class Meta:
        model = OrdemServico
        fields = [
            "oficios",
            "data_evento_inicio",
            "data_evento_fim",
            "servidores",
            "tipo_necessidade",
            "motorista_equipe",
            "tecnico_equipe",
            "apoio_montagem",
            "apoio_escolta",
            "coordenador_cerimonial",
            "apoio_cerimonial",
            "apoio_preparacao",
            "motivo",
        ]
        widgets = {
            "oficios": OficioMultiSelectWidget(attrs={
                "class": "termo-oficio-source-select os-oficio-source-select",
                "hidden": True,
            }),
            "data_evento_inicio": forms.HiddenInput(attrs={"data-cv-date-picker-start-value": "true"}),
            "data_evento_fim": forms.HiddenInput(attrs={"data-cv-date-picker-end-value": "true"}),
            "servidores": ServidorEquipeSelectMultiple(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "multi",
                "data-picker-variant": "detailed",
                "data-picker-presentation": "people",
                "data-picker-label": "Adicionar à equipe",
                "data-picker-hint": "Opcional. Se vazio e houver ofícios vinculados, usa os servidores desses ofícios.",
                "data-panel-title": "Equipe da OS",
                "data-placeholder": "Buscar por nome, CPF ou RG",
                "data-empty-message": "Nenhum servidor encontrado.",
                "data-empty-selected": "Nenhum servidor selecionado.",
            }),
            "tipo_necessidade": forms.RadioSelect(attrs={
                "data-os-model-option": "true",
            }),
            "motorista_equipe": ServidorMotoristaSelect(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "detailed",
                "data-placeholder": "Selecionar motorista...",
                "data-empty-message": "Nenhum servidor encontrado.",
            }),
            "tecnico_equipe": ServidorMotoristaSelect(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "detailed",
                "data-placeholder": "Selecionar técnico...",
                "data-empty-message": "Nenhum servidor encontrado.",
            }),
            "apoio_montagem": ServidorMotoristaSelect(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "detailed",
                "data-placeholder": "Selecionar apoio de montagem...",
                "data-empty-message": "Nenhum servidor encontrado.",
            }),
            "apoio_escolta": ServidorMotoristaSelect(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "detailed",
                "data-placeholder": "Selecionar apoio de escolta...",
                "data-empty-message": "Nenhum servidor encontrado.",
            }),
            "coordenador_cerimonial": ServidorMotoristaSelect(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "detailed",
                "data-placeholder": "Selecionar coordenação...",
                "data-empty-message": "Nenhum servidor encontrado.",
            }),
            "apoio_cerimonial": ServidorMotoristaSelect(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "detailed",
                "data-placeholder": "Selecionar apoio de cerimonial...",
                "data-empty-message": "Nenhum servidor encontrado.",
            }),
            "apoio_preparacao": ServidorMotoristaSelect(attrs={
                "class": "form-select cv-search-picker__native",
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "detailed",
                "data-placeholder": "Selecionar apoio de preparação...",
                "data-empty-message": "Nenhum servidor encontrado.",
            }),
            "motivo": forms.Textarea(attrs={
                "rows": 5,
                "class": "cv-field__control cv-field__control--textarea",
                "placeholder": "Descreva o motivo ou finalidade desta ordem de serviço...",
                "data-motivo-textarea": "true",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        ja_vinculados = list(self.instance.oficios.values_list("pk", flat=True)) if self.instance.pk else []
        self.fields["oficios"].required = False
        self.fields["oficios"].queryset = (
            filter_queryset_by_area(Oficio.objects)
            .select_related("roteiro", "viatura")
            .filter(Q(cancelado=False) | Q(pk__in=ja_vinculados))
            .order_by("-data_criacao", "-created_at")
        )

        self.fields["data_evento_inicio"].required = False
        self.fields["data_evento_fim"].required = False

        estado_id, cidade_id = self._resolve_destino_inicial()
        self.fields["destino_estado"].queryset = Estado.objects.order_by("nome")
        self.fields["destino_estado"].initial = estado_id
        self.initial["destino_estado"] = estado_id
        self.fields["destino_estado"].widget.attrs["data-picker-initial-value"] = str(estado_id or "")

        if estado_id:
            self.fields["destino_cidade"].queryset = (
                Cidade.objects.select_related("estado")
                .filter(estado_id=estado_id)
                .order_by("nome")
            )
            self.fields["destino_cidade"].widget.attrs.pop("disabled", None)
        else:
            self.fields["destino_cidade"].queryset = Cidade.objects.select_related("estado").none()
            self.fields["destino_cidade"].widget.attrs["disabled"] = True
        self.fields["destino_cidade"].initial = cidade_id
        self.initial["destino_cidade"] = cidade_id
        self.fields["destino_cidade"].widget.attrs["data-picker-initial-value"] = str(cidade_id or "")

        self.fields["servidores"].required = False
        self.fields["servidores"].queryset = (
            filter_queryset_by_area(Servidor.objects).select_related("cargo", "unidade").order_by("nome")
        )

        role_queryset = filter_queryset_by_area(Servidor.objects).select_related("cargo", "unidade").order_by("nome")
        role_fields = (
            "motorista_equipe",
            "tecnico_equipe",
            "apoio_montagem",
            "apoio_escolta",
            "coordenador_cerimonial",
            "apoio_cerimonial",
            "apoio_preparacao",
        )
        for field_name in role_fields:
            self.fields[field_name].required = False
            self.fields[field_name].queryset = role_queryset

        self.fields["tipo_necessidade"].required = True
        self.fields["motivo"].required = False
        self.fields["modelo_motivo"].queryset = (
            ModeloMotivoOficio.objects.filter(ativo=True).order_by("ordem", "nome")
        )
        self.destination_rows = self._build_destination_rows(estado_id, cidade_id)

    def _resolve_destino_inicial(self):
        cidade_id = None
        estado_id = None

        if self.is_bound:
            cidade_id = self.data.get("destino_cidade") or None
            estado_id = self.data.get("destino_estado") or None
        elif self.initial.get("destino_cidade") or self.initial.get("destino_estado"):
            cidade_id = self.initial.get("destino_cidade") or None
            estado_id = self.initial.get("destino_estado") or None
        elif self.instance and self.instance.pk:
            cidades = list(
                self.instance.destinos
                .select_related("estado")
                .order_by("nome", "pk")
                [:2]
            )
            if len(cidades) == 1:
                cidade = cidades[0]
                cidade_id = cidade.pk
                estado_id = cidade.estado_id
            else:
                estado_id, _, _ = resolver_sede_ids_desde_configuracao()
        else:
            estado_id, _, _ = resolver_sede_ids_desde_configuracao()

        if cidade_id:
            cidade_obj = Cidade.objects.select_related("estado").filter(pk=cidade_id).first()
            if cidade_obj:
                cidade_id = cidade_obj.pk
                estado_id = cidade_obj.estado_id

        return estado_id, cidade_id

    def _build_destination_rows(self, estado_id, cidade_id):
        rows = []
        if self.is_bound:
            rows.append(
                self._destination_row_from_values(
                    0,
                    self.data.get("destino_estado"),
                    self.data.get("destino_cidade"),
                )
            )
            for idx in self._extra_destination_indexes():
                rows.append(
                    self._destination_row_from_values(
                        idx,
                        self.data.get(f"destino_estado_{idx}"),
                        self.data.get(f"destino_cidade_{idx}"),
                    )
                )
        elif self.instance and self.instance.pk:
            destinos = list(self.instance.destinos.select_related("estado").order_by("nome", "pk"))
            if destinos:
                for idx, cidade in enumerate(destinos):
                    rows.append(self._destination_row_from_values(idx, cidade.estado_id, cidade.pk))
            else:
                rows.append(self._destination_row_from_values(0, estado_id, cidade_id))
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

    def _extra_destination_indexes(self):
        return sorted(
            {
                int(name.rsplit("_", 1)[1])
                for name in self.data.keys()
                if name.startswith("destino_estado_") and name.rsplit("_", 1)[1].isdigit()
            }
        )

    def clean(self):
        cleaned = super().clean()
        cidade = cleaned.get("destino_cidade")
        estado = cleaned.get("destino_estado")

        if estado and not cidade:
            self.add_error("destino_cidade", "Informe a cidade do destino.")

        destinos = []
        if cidade:
            destinos.append(cidade.pk)
        for idx in self._extra_destination_indexes():
            estado_raw = (self.data.get(f"destino_estado_{idx}") or "").strip()
            cidade_raw = (self.data.get(f"destino_cidade_{idx}") or "").strip()
            if not estado_raw and not cidade_raw:
                continue
            if estado_raw and not cidade_raw:
                self.add_error(None, f"Informe a cidade do destino adicional {idx}.")
                continue
            cidade_obj = Cidade.objects.select_related("estado").filter(pk=cidade_raw).first() if cidade_raw else None
            if not cidade_obj:
                self.add_error(None, f"Selecione uma cidade valida para o destino adicional {idx}.")
                continue
            destinos.append(cidade_obj.pk)
        self.cleaned_destinos = destinos
        self.cleaned_funcoes_servidores = self._clean_funcoes_servidores(cleaned)

        return cleaned

    def _clean_funcoes_servidores(self, cleaned):
        if cleaned.get("tipo_necessidade") not in {
            OrdemServico.TIPO_CAMINHAO,
            OrdemServico.TIPO_MICROONIBUS,
            OrdemServico.TIPO_CERIMONIAL_ANTECIPADO,
        }:
            return {}
        servidores = cleaned.get("servidores")
        servidor_ids = {str(servidor.pk) for servidor in servidores} if servidores is not None else set()
        funcoes = {}
        for name, value in self.data.items():
            if not name.startswith("funcao_servidor_"):
                continue
            servidor_id = name.removeprefix("funcao_servidor_").strip()
            funcao = (value or "").strip().upper()
            if not servidor_id or servidor_id not in servidor_ids:
                continue
            if not funcao:
                continue
            if funcao not in FUNCOES_SERVIDOR_VALIDAS:
                self.add_error(None, "Selecione uma função válida para os servidores da equipe.")
                continue
            funcoes[servidor_id] = funcao
        return funcoes

    def save(self, commit=True):
        ordem = super().save(commit=commit)
        destino_ids = getattr(self, "cleaned_destinos", []) or []
        if not destino_ids and self.cleaned_data.get("destino_cidade"):
            destino_ids = [self.cleaned_data["destino_cidade"].pk]
        ordem.funcoes_servidores = getattr(self, "cleaned_funcoes_servidores", {}) or {}

        if commit:
            ordem.destinos.set(destino_ids)
            ordem.save(update_fields=["funcoes_servidores", "updated_at"])

        return ordem
