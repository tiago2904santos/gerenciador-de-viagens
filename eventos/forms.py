from django import forms
from django.db.models import Q
from django.utils import timezone

from cadastros.models import ConfiguracaoSistema
from core.forms.widgets import WidgetStyle
from core.forms.widgets import widget_attrs
from core.tenancy import filter_queryset_by_area
from core.tenancy import get_current_area
from oficios.forms import ModeloMotivoSelect
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio
from ordens_servico.forms import OficioMultiSelectWidget
from ordens_servico.models import OrdemServico
from planos_trabalho.models import PlanoTrabalho
from roteiros.models import Roteiro
from termos.models import TermoAutorizacao

from .models import Evento
from .models import TipoEvento

_DOCUMENTOS_VINCULAVEIS = [
    ("oficios_vinculados", "oficios"),
    ("ordens_servico_vinculadas", "ordens_servico"),
    ("planos_trabalho_vinculados", "planos_trabalho"),
    ("termos_vinculados", "termos_autorizacao"),
    ("roteiros_vinculados", "roteiros"),
]


def _periodo_roteiro(roteiro) -> str:
    inicio = roteiro.saida_dt
    fim = roteiro.retorno_chegada_dt or roteiro.chegada_dt or roteiro.retorno_saida_dt
    if not inicio:
        return ""

    def _fmt(dt):
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        return dt.strftime("%d/%m/%Y")

    if not fim or fim == inicio:
        return _fmt(inicio)
    return f"{_fmt(inicio)} a {_fmt(fim)}"


class _VinculoMultiSelectWidget(forms.SelectMultiple):
    """Base dos pickers de documentos já existentes vinculáveis a um evento."""

    def option_display(self, instance):
        raise NotImplementedError

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        instance = getattr(value, "instance", None)
        if instance is None:
            return option
        main, meta = self.option_display(instance)
        option["label"] = main
        option["attrs"].update({
            "data-main": main,
            "data-meta": meta,
            "data-search": " ".join(p for p in [main, meta, str(instance.pk)] if p),
        })
        return option


class OrdemServicoMultiSelectWidget(_VinculoMultiSelectWidget):
    def option_display(self, ordem):
        return ordem.numero_formatado, f"{ordem.periodo_display} - {ordem.destinos_display}"


class PlanoTrabalhoMultiSelectWidget(_VinculoMultiSelectWidget):
    def option_display(self, plano):
        return f"PT {plano.numero_formatado}", f"{plano.programa_display} - {plano.periodo_display}"


class TermoAutorizacaoMultiSelectWidget(_VinculoMultiSelectWidget):
    def option_display(self, termo):
        return f"Termo #{termo.pk}", f"{termo.destino_display} - {termo.periodo_display}"


class RoteiroMultiSelectWidget(_VinculoMultiSelectWidget):
    def option_display(self, roteiro):
        return str(roteiro), _periodo_roteiro(roteiro)

_ESTADOS_CHOICES = [
    ("", "Selecione o estado"),
    ("AC", "Acre (AC)"),
    ("AL", "Alagoas (AL)"),
    ("AP", "Amapá (AP)"),
    ("AM", "Amazonas (AM)"),
    ("BA", "Bahia (BA)"),
    ("CE", "Ceará (CE)"),
    ("DF", "Distrito Federal (DF)"),
    ("ES", "Espírito Santo (ES)"),
    ("GO", "Goiás (GO)"),
    ("MA", "Maranhão (MA)"),
    ("MT", "Mato Grosso (MT)"),
    ("MS", "Mato Grosso do Sul (MS)"),
    ("MG", "Minas Gerais (MG)"),
    ("PA", "Pará (PA)"),
    ("PB", "Paraíba (PB)"),
    ("PR", "Paraná (PR)"),
    ("PE", "Pernambuco (PE)"),
    ("PI", "Piauí (PI)"),
    ("RJ", "Rio de Janeiro (RJ)"),
    ("RN", "Rio Grande do Norte (RN)"),
    ("RS", "Rio Grande do Sul (RS)"),
    ("RO", "Rondônia (RO)"),
    ("RR", "Roraima (RR)"),
    ("SC", "Santa Catarina (SC)"),
    ("SP", "São Paulo (SP)"),
    ("SE", "Sergipe (SE)"),
    ("TO", "Tocantins (TO)"),
]


class EventoNovoCadastroForm(forms.ModelForm):
    modelo_motivo = forms.ModelChoiceField(
        label="Modelo de motivo",
        queryset=ModeloMotivoOficio.objects.none(),
        required=False,
        empty_label="Selecione um modelo (opcional)",
        widget=ModeloMotivoSelect(attrs={**widget_attrs(WidgetStyle.FORM_SELECT), "data-modelo-motivo-select": "true"}),
    )
    tipos = forms.ModelMultipleChoiceField(
        label="Tipo do evento",
        queryset=TipoEvento.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"data-placeholder": "Selecione o(s) tipo(s)"}),
    )
    destino_uf = forms.ChoiceField(
        label="Estado",
        choices=_ESTADOS_CHOICES,
        required=False,
        widget=forms.Select(
            attrs={
                **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                "data-cv-search-picker": "true",
                "data-picker-mode": "single",
                "data-picker-variant": "compact",
                "data-placeholder": "Buscar estado...",
                "data-empty-message": "Nenhum estado encontrado.",
            }
        ),
    )
    # Os documentos vinculáveis usam um picker de busca próprio (mesmo cartão dos
    # ofícios da OS), montado pelo JS a partir dos resumos servidos no template.
    # Aqui o campo é apenas o <select multiple> oculto que carrega a seleção no
    # submit — sem o enhancer genérico de cv-search-picker.
    oficios_vinculados = forms.ModelMultipleChoiceField(
        label="Ofícios já existentes",
        queryset=Oficio.objects.none(),
        required=False,
        widget=OficioMultiSelectWidget(attrs={
            **widget_attrs(WidgetStyle.EVENT_DOCUMENT_SOURCE),
            "hidden": True,
            "data-evento-doc-field": "oficios",
        }),
    )
    ordens_servico_vinculadas = forms.ModelMultipleChoiceField(
        label="Ordens de serviço já existentes",
        queryset=OrdemServico.objects.none(),
        required=False,
        widget=OrdemServicoMultiSelectWidget(attrs={
            **widget_attrs(WidgetStyle.EVENT_DOCUMENT_SOURCE),
            "hidden": True,
            "data-evento-doc-field": "os",
        }),
    )
    planos_trabalho_vinculados = forms.ModelMultipleChoiceField(
        label="Planos de trabalho já existentes",
        queryset=PlanoTrabalho.objects.none(),
        required=False,
        widget=PlanoTrabalhoMultiSelectWidget(attrs={
            **widget_attrs(WidgetStyle.EVENT_DOCUMENT_SOURCE),
            "hidden": True,
            "data-evento-doc-field": "pt",
        }),
    )
    termos_vinculados = forms.ModelMultipleChoiceField(
        label="Termos de autorização já existentes",
        queryset=TermoAutorizacao.objects.none(),
        required=False,
        widget=TermoAutorizacaoMultiSelectWidget(attrs={
            **widget_attrs(WidgetStyle.EVENT_DOCUMENT_SOURCE),
            "hidden": True,
            "data-evento-doc-field": "termos",
        }),
    )
    roteiros_vinculados = forms.ModelMultipleChoiceField(
        label="Roteiros já existentes",
        queryset=Roteiro.objects.none(),
        required=False,
        widget=RoteiroMultiSelectWidget(attrs={
            **widget_attrs(WidgetStyle.EVENT_DOCUMENT_SOURCE),
            "hidden": True,
            "data-evento-doc-field": "roteiros",
        }),
    )

    class Meta:
        model = Evento
        fields = [
            "tipos",
            "motivo",
            "data_inicio",
            "data_fim",
            "destino_uf",
            "destino_cidade",
        ]
        widgets = {
            "motivo": forms.Textarea(
                attrs={
                    **widget_attrs(WidgetStyle.FIELD_CONTROL_TEXTAREA),
                    "rows": 4,
                    "data-motivo-textarea": "true",
                }
            ),
            "data_inicio": forms.HiddenInput(attrs={"data-cv-date-picker-start-value": ""}),
            "data_fim": forms.HiddenInput(attrs={"data-cv-date-picker-end-value": ""}),
            "destino_cidade": forms.Select(
                choices=[("", "---------")],
                attrs={
                    **widget_attrs(WidgetStyle.SEARCH_PICKER_NATIVE),
                    "data-cv-search-picker": "true",
                    "data-picker-mode": "single",
                    "data-picker-variant": "compact",
                    "data-placeholder": "Buscar cidade...",
                    "data-empty-message": "Nenhuma cidade encontrada.",
                    "data-destino-cidade-picker": "true",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["data_inicio"].required = False
        self.fields["data_fim"].required = False
        self.fields["tipos"].queryset = filter_queryset_by_area(TipoEvento.objects).filter(ativo=True).order_by(
            "ordem", "nome"
        )
        self.fields["modelo_motivo"].queryset = filter_queryset_by_area(ModeloMotivoOficio.objects).filter(ativo=True).order_by(
            "ordem", "nome"
        )
        # Pré-preenche a UF de destino com o estado padrão das configurações (eventos sem destino definido)
        if not self.is_bound and not (self.instance and self.instance.destino_uf):
            uf_padrao = ConfiguracaoSistema.get_for_area(get_current_area()).uf
            if uf_padrao:
                self.initial["destino_uf"] = uf_padrao

        evento_pk = self.instance.pk if self.instance else None
        # Documentos cancelados não entram como opção para NOVA vinculação, mas
        # continuam visíveis se já estiverem vinculados a este evento.
        nao_vinculado_ou_deste_evento = Q(evento_id=evento_pk) | Q(evento__isnull=True, cancelado=False)

        self.fields["oficios_vinculados"].queryset = (
            filter_queryset_by_area(Oficio.objects).select_related("roteiro", "viatura")
            .filter(nao_vinculado_ou_deste_evento)
            .order_by("-data_criacao", "-created_at")
        )
        self.fields["ordens_servico_vinculadas"].queryset = (
            OrdemServico.objects.filter(nao_vinculado_ou_deste_evento).order_by("-ano", "-numero")
        )
        self.fields["planos_trabalho_vinculados"].queryset = (
            PlanoTrabalho.objects.filter(nao_vinculado_ou_deste_evento).order_by("-ano", "-numero")
        )
        self.fields["termos_vinculados"].queryset = (
            TermoAutorizacao.objects.select_related("destino_cidade", "destino_estado")
            .filter(nao_vinculado_ou_deste_evento)
            .order_by("-created_at")
        )
        self.fields["roteiros_vinculados"].queryset = (
            Roteiro.objects.select_related("origem_cidade", "origem_estado")
            .filter(nao_vinculado_ou_deste_evento)
            .order_by("-created_at")
        )

        if evento_pk and not self.is_bound:
            self.initial["oficios_vinculados"] = list(self.instance.oficios.values_list("pk", flat=True))
            self.initial["ordens_servico_vinculadas"] = list(
                self.instance.ordens_servico.values_list("pk", flat=True)
            )
            self.initial["planos_trabalho_vinculados"] = list(
                self.instance.planos_trabalho.values_list("pk", flat=True)
            )
            self.initial["termos_vinculados"] = list(
                self.instance.termos_autorizacao.values_list("pk", flat=True)
            )
            self.initial["roteiros_vinculados"] = list(self.instance.roteiros.values_list("pk", flat=True))

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")
        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        return cleaned

    def sincronizar_documentos_vinculados(self, evento):
        """Vincula/desvincula ofícios, OS, planos, termos e roteiros conforme a seleção do form."""
        for field_name, related_name in _DOCUMENTOS_VINCULAVEIS:
            if field_name not in self.cleaned_data:
                continue
            manager = getattr(evento, related_name)
            selecionados_ids = {obj.pk for obj in self.cleaned_data[field_name]}
            atuais_ids = set(manager.values_list("pk", flat=True))
            para_adicionar = selecionados_ids - atuais_ids
            para_remover = atuais_ids - selecionados_ids
            if para_adicionar:
                manager.model.objects.filter(pk__in=para_adicionar).update(evento=evento)
            if para_remover:
                manager.model.objects.filter(pk__in=para_remover).update(evento=None)


class EventoForm(forms.ModelForm):
    class Meta:
        model = Evento
        fields = [
            "titulo",
            "descricao",
            "destino_uf",
            "destino_cidade",
            "data_inicio",
            "data_fim",
            "horario_inicio",
            "horario_fim",
            "unidade_responsavel",
            "responsavel",
            "status",
            "drive_folder_url",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL)}),
            "descricao": forms.Textarea(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL_TEXTAREA), "rows": 4}),
            "destino_uf": forms.TextInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL), "maxlength": 2}),
            "destino_cidade": forms.TextInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL)}),
            "data_inicio": forms.HiddenInput(attrs={"data-cv-date-picker-start-value": ""}),
            "data_fim": forms.HiddenInput(attrs={"data-cv-date-picker-end-value": ""}),
            "horario_inicio": forms.TimeInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL), "type": "time"}),
            "horario_fim": forms.TimeInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL), "type": "time"}),
            "unidade_responsavel": forms.Select(attrs={**widget_attrs(WidgetStyle.FORM_SELECT)}),
            "responsavel": forms.Select(attrs={**widget_attrs(WidgetStyle.FORM_SELECT)}),
            "status": forms.Select(attrs={**widget_attrs(WidgetStyle.FORM_SELECT)}),
            "drive_folder_url": forms.URLInput(attrs={**widget_attrs(WidgetStyle.FIELD_CONTROL)}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["unidade_responsavel"].required = False
        self.fields["responsavel"].required = False
        self.fields["unidade_responsavel"].queryset = filter_queryset_by_area(
            self.fields["unidade_responsavel"].queryset.model.objects
        ).order_by("nome")
        self.fields["responsavel"].queryset = filter_queryset_by_area(
            self.fields["responsavel"].queryset.model.objects
        ).order_by("nome")

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")
        if data_inicio and data_fim and data_fim < data_inicio:
            self.add_error("data_fim", "A data final não pode ser anterior à data inicial.")
        destino_uf = (cleaned.get("destino_uf") or "").strip().upper()
        if destino_uf and len(destino_uf) != 2:
            self.add_error("destino_uf", "Informe a UF com 2 caracteres.")
        cleaned["destino_uf"] = destino_uf
        return cleaned


class TipoEventoForm(forms.ModelForm):
    nome = forms.CharField(
        label="Nome",
        help_text="Ex.: PCPR na Comunidade, Justiça no Bairro.",
        widget=forms.TextInput(attrs={**widget_attrs(WidgetStyle.FORM_CONTROL)}),
    )
    ativo = forms.BooleanField(
        label="Ativo",
        required=False,
        initial=True,
        help_text="Desmarque para ocultar este tipo da seleção sem apagar eventos já vinculados.",
        widget=forms.CheckboxInput(attrs={**widget_attrs(WidgetStyle.CARD_TOGGLE)}),
    )

    class Meta:
        model = TipoEvento
        fields = ["nome", "ativo"]
