from __future__ import annotations

from django import forms

from cadastros.form_widgets import ServidorEquipeSelectMultiple
from cadastros.form_widgets import ViaturaSelectSingle
from cadastros.models import Cidade
from cadastros.models import Estado
from cadastros.models import Servidor
from cadastros.models import Viatura
from cadastros.services import resolver_sede_ids_desde_configuracao
from oficios.models import Oficio

from .models import TermoAutorizacao


class OficioSelectSingle(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        oficio = getattr(value, "instance", None)
        if oficio is None:
            return option
        protocolo = oficio.protocolo or ""
        assunto = oficio.assunto or ""
        main = f"Oficio {oficio.numero_formatado}"
        option["label"] = main
        option["attrs"].update(
            {
                "data-main": main,
                "data-meta": " - ".join(part for part in [protocolo, assunto] if part),
                "data-search": " ".join(
                    part
                    for part in [oficio.numero_formatado, protocolo, assunto, str(oficio.pk)]
                    if part
                ),
            },
        )
        return option


class TermoAutorizacaoForm(forms.ModelForm):
    class Meta:
        model = TermoAutorizacao
        fields = [
            "oficio",
            "destino_estado",
            "destino_cidade",
            "data_evento_inicio",
            "data_evento_fim",
            "servidores",
            "viatura",
        ]
        widgets = {
            "oficio": OficioSelectSingle(
                attrs={
                    "class": "termo-oficio-source-select",
                    "hidden": True,
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
            "servidores": ServidorEquipeSelectMultiple(
                attrs={
                    "class": "form-select cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "multi",
                    "data-picker-variant": "detailed",
                    "data-picker-label": "Servidores",
                    "data-picker-hint": "Opcional. Se vazio e houver oficio vinculado, usa os servidores do termo no oficio.",
                    "data-panel-title": "SERVIDORES DO TERMO",
                    "data-placeholder": "Buscar por nome, CPF ou RG",
                    "data-empty-message": "Nenhum servidor encontrado.",
                    "data-empty-selected": "Nenhum servidor selecionado.",
                },
            ),
            "viatura": ViaturaSelectSingle(
                attrs={
                    "class": "form-select cv-search-picker__native",
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "detailed",
                    "data-picker-label": "Viatura",
                    "data-picker-hint": "Opcional. Se vazio e houver oficio vinculado, usa a viatura do oficio.",
                    "data-placeholder": "Buscar por placa ou modelo",
                    "data-empty-message": "Nenhuma viatura encontrada.",
                    "data-empty-selected": "Nenhuma viatura selecionada.",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estado_id, cidade_id = self._resolve_destino_inicial()

        self.fields["oficio"].required = False
        self.fields["oficio"].empty_label = ""
        self.fields["oficio"].queryset = Oficio.objects.select_related("roteiro", "viatura").order_by("-data_criacao", "-created_at")

        self.fields["destino_estado"].required = False
        self.fields["destino_estado"].empty_label = ""
        self.fields["destino_estado"].queryset = Estado.objects.order_by("nome")
        self.fields["destino_estado"].initial = estado_id
        self.initial["destino_estado"] = estado_id
        self.fields["destino_estado"].widget.attrs["data-picker-initial-value"] = str(estado_id or "")

        self.fields["destino_cidade"].required = False
        self.fields["destino_cidade"].empty_label = ""
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

        self.fields["data_evento_inicio"].required = False
        self.fields["data_evento_fim"].required = False
        self.fields["servidores"].required = False
        self.fields["servidores"].queryset = Servidor.objects.select_related("cargo", "unidade").order_by("nome")
        self.fields["viatura"].required = False
        self.fields["viatura"].empty_label = ""
        self.fields["viatura"].queryset = (
            Viatura.objects.select_related("combustivel", "unidade")
            .prefetch_related("motoristas")
            .order_by("placa")
        )

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
            cidade_id = self.instance.destino_cidade_id
            estado_id = self.instance.destino_estado_id
        else:
            cfg_estado_id, _cfg_cidade_id, _ = resolver_sede_ids_desde_configuracao()
            estado_id = estado_id or cfg_estado_id
            cidade_id = None

        cidade_obj = None
        if cidade_id:
            cidade_obj = Cidade.objects.select_related("estado").filter(pk=cidade_id).first()
            if cidade_obj:
                cidade_id = cidade_obj.pk
                estado_id = cidade_obj.estado_id

        return estado_id, cidade_id

    def clean(self):
        cleaned = super().clean()
        oficio = cleaned.get("oficio")
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
            fim = inicio

        if inicio and fim and fim < inicio:
            self.add_error("data_evento_fim", "A data final nao pode ser anterior a data inicial.")

        if not cidade and not self._oficio_tem_destino(oficio):
            self.add_error("destino_cidade", "Informe o destino ou selecione um oficio com roteiro.")

        if not inicio and not self._oficio_tem_periodo(oficio):
            self.add_error("data_evento_inicio", "Informe a data do evento ou selecione um oficio com periodo.")

        return cleaned

    @staticmethod
    def _oficio_tem_destino(oficio):
        if not oficio or not oficio.roteiro_id:
            return False
        return oficio.roteiro.destinos.exists()

    @staticmethod
    def _oficio_tem_periodo(oficio):
        if not oficio or not oficio.roteiro_id:
            return False
        return bool(oficio.roteiro.saida_dt)
