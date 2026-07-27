import logging
import re
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.db.models import Q
from django.http import Http404
from django.http import JsonResponse
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from core.tenancy import filter_queryset_by_area

from justificativas.forms import JustificativaOficioForm
from justificativas.presenters import apresentar_justificativa_wizard_context
from justificativas.services import atualizar_justificativa_oficio
from justificativas.services import get_or_create_justificativa_oficio
from justificativas.services import oficio_exige_justificativa

from roteiros.forms import RoteiroForm
from roteiros.models import Roteiro
from roteiros.services.autosave import ROTEIRO_AUTOSAVE_FIELDS
from roteiros.services.autosave import apply_roteiro_autosave
from roteiros.services.autosave import build_roteiro_draft
from roteiros.services.autosave import has_minimum_roteiro_content
from roteiros.services import (
    atualizar_roteiro,
    carregar_opcoes_rotas_avulsas_salvas,
    montar_contexto_editor_roteiro,
    montar_estado_editor_roteiro_evento_selecionado,
    montar_initial_roteiro_evento_sem_datas,
    normalizar_destinos_e_trechos_apos_erro_post,
    preparar_estado_editor_roteiro_para_get,
    preparar_querysets_formulario_roteiro,
    roteiro_state_equivalente_ao_roteiro,
    validar_submissao_editor_roteiro,
)

from cadastros.models import Combustivel
from cadastros.models import Servidor
from documentos.selectors import get_latest_artefato_pdf_for_oficio
from documentos.services.downloads import download_documento_or_redirect_pdf_error
from documentos.services.warm_cache import pdf_artefato_original_acessivel
from documentos.services.responses import build_inline_pdf_response_from_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from eventos.services import resolve_evento_from_request
from ordens_servico.services import gerar_resposta_ordem_servico_documento
from .forms import OficioDadosViajantesForm
from .forms import OficioTransporteForm
from .forms import ModeloMotivoOficioForm
from .models import Oficio
from .presenters import apresentar_acoes_oficio
from .presenters import apresentar_linha_lista_simples_modelo_motivo
from .presenters import apresentar_oficio_card
from .presenters import apresentar_oficio_wizard_documentos_context
from .presenters import apresentar_oficio_wizard_summary
from .presenters import apresentar_oficio_wizard_header
from .presenters import apresentar_oficio_wizard_page_steps
from .presenters import apresentar_oficio_wizard_steps
from .selectors import get_oficio_by_id
from .selectors import get_modelo_motivo_by_id
from .selectors import buscar_viaturas_para_oficio
from .selectors import get_viatura_por_placa_normalizada
from .selectors import viatura_para_resultado_busca
from .selectors import listar_modelos_motivo
from .selectors import listar_oficios
from .selectors import listar_servidores_para_oficio
from .selectors import listar_viaturas_para_oficio
from .services import atualizar_modelo_motivo
from .services import OficioVinculadoError
from .services import cancelar_oficio
from .services import retificar_oficio
from .services import desfazer_retificacao_oficio
from .services import marcar_oficio_complementar
from .services import desfazer_complementar_oficio
from .services import atualizar_oficio_dados_viajantes
from .services import atualizar_oficio_transporte
from .services import avaliar_oficio_dados_viajantes
from .services import avaliar_oficio_transporte
from .services import criar_modelo_motivo
from .services import criar_oficio_rascunho
from .services import excluir_modelo_motivo
from .services import excluir_oficio
from .services import gerar_resposta_documento_oficio
from .services import gerar_resposta_justificativa_documento
from .services import resolver_roteiro_padrao_evento
from .services import obter_roteiro_escolhido_do_post
from .services import vincular_roteiro_ao_oficio_sem_copia
from .services import redirect_para_corrigir_documento_oficio
from .services import oficio_esta_completo_para_finalizar
from .services import OficioNumeroConflitoError
from .services import tocar_data_criacao_oficio
from .services import validar_oficio_para_documento


logger = logging.getLogger(__name__)


def _evento_etapa_url(evento_id, etapa):
    if evento_id:
        return reverse("eventos:guiado_etapa", kwargs={"pk": evento_id, "etapa": etapa})
    return ""


def _oficio_back_url(oficio):
    return _evento_etapa_url(getattr(oficio, "evento_id", None), 3) or reverse("oficios:index")


def _oficio_back_label(oficio):
    return "Dados do evento" if getattr(oficio, "evento_id", None) else "Voltar à lista"


def _cadastro_create_url(create_url_name, next_url):
    return f"{reverse(create_url_name)}?{urlencode({'next': next_url})}"


def _url_with_next(url_name, next_url):
    return f"{reverse(url_name)}?{urlencode({'next': next_url})}"


def _safe_next_url(request, fallback_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def _redirect_lista_oficio(request, oficio, message):
    messages.success(request, message)
    if getattr(oficio, "evento_id", None):
        return redirect("eventos:guiado_etapa", pk=oficio.evento_id, etapa=3)
    return redirect("oficios:index")


def _wizard_normalizar_acao(post, *, default: str = "wizard_next") -> str:
    action = (post.get("action") or default).strip()
    if action == "save_continue":
        return "wizard_next"
    return action


def _wizard_persist_action_para_dados_viajantes(nav_action: str) -> str:
    if nav_action == "wizard_next":
        return "save_continue"
    return "save_draft"


def _wizard_footer_ctx(oficio):
    return {"oficio_completo": oficio_esta_completo_para_finalizar(oficio)}


def _wizard_steps_ctx(*, oficio=None, etapa_atual="dados_viajantes", **kwargs):
    steps = apresentar_oficio_wizard_steps(
        oficio=oficio,
        etapa_atual=etapa_atual,
        **kwargs,
    )
    return {
        "wizard_steps": steps,
        "wizard_page_steps": apresentar_oficio_wizard_page_steps(steps),
    }


def _wizard_shell_ctx(*, oficio=None, etapa_atual, **step_kwargs):
    return {
        "wizard_header": apresentar_oficio_wizard_header(etapa_atual, oficio=oficio),
        **_wizard_steps_ctx(oficio=oficio, etapa_atual=etapa_atual, **step_kwargs),
    }


def _wizard_roteiro_step_status(oficio):
    if not getattr(oficio, "roteiro_id", None):
        return "incomplete"
    roteiro = oficio.roteiro
    return (
        "complete"
        if (roteiro.origem_cidade_id or roteiro.origem_estado_id)
        else "incomplete"
    )


def _motorista_oficio_numero_display(ref):
    ref = (ref or "").strip()
    if not ref:
        return ""
    head = ref.split("/", 1)[0]
    return re.sub(r"\D", "", head)[:3]


def _prepare_dados_viajantes_form(form):
    servidores_qs = listar_servidores_para_oficio()
    form.fields["servidores"].queryset = servidores_qs
    form.fields["servidores_termo_autorizacao"].queryset = servidores_qs
    form.fields["viatura"].queryset = listar_viaturas_para_oficio()


def _prepare_transporte_form(form):
    form.fields["viatura"].queryset = listar_viaturas_para_oficio()
    form.fields["motorista"].queryset = listar_servidores_para_oficio()
    form.fields["transporte_combustivel_manual"].queryset = filter_queryset_by_area(Combustivel.objects).order_by("nome")


def _wizard_dados_viajantes_context(
    *,
    form,
    transporte_form,
    oficio,
    avaliacao=None,
    mostrar_pendencias_documento=False,
):
    avaliacao = avaliacao or avaliar_oficio_dados_viajantes(oficio=oficio, form=form)
    pendencias = avaliacao["pendencias"]
    summary = apresentar_oficio_wizard_summary(oficio)
    custeio_value = ""
    if form.is_bound:
        custeio_value = form.data.get("custeio", "")
    else:
        custeio_value = getattr(form.instance, "custeio", "") if getattr(form, "instance", None) else ""
    mostrar_custeio_observacao = custeio_value == "OUTRA_INSTITUICAO"
    modelos_queryset = form.fields["modelo_motivo"].queryset
    equipe_ids = list(oficio.servidores.values_list("pk", flat=True))
    modo_motorista = oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR
    servidores_attrs = form.fields["servidores"].widget.attrs
    if oficio.motorista_id and oficio.motorista_id in equipe_ids:
        servidores_attrs["data-picker-driver-value"] = str(oficio.motorista_id)
    else:
        servidores_attrs.pop("data-picker-driver-value", None)
    # Card de motorista externo: só aparece quando viatura selecionada + motorista não é da equipe
    _driver_in_equipe = bool(oficio.motorista_id) and oficio.motorista_id in equipe_ids
    show_motorista_card = bool(oficio.viatura_id) and not _driver_in_equipe
    # Campos de protocolo do motorista: visíveis no card (sempre que o card aparece)
    motorista_extras_visivel = show_motorista_card
    if transporte_form.is_bound:
        ref_raw = (transporte_form.data.get("motorista_oficio_referencia") or "").strip()
    else:
        ref_raw = (oficio.motorista_oficio_referencia or "").strip()

    # Dados auxiliares para o card de viatura selecionada (modo edição).
    viatura_selecionada_unidade = ""
    viatura_selecionada_edit_url = ""
    viatura_selecionada_modelo = ""
    viatura_selecionada_combustivel = ""
    viatura_selecionada_tipo = ""
    if oficio.viatura_id and oficio.viatura:
        v = oficio.viatura
        viatura_selecionada_unidade = str(v.unidade) if v.unidade_id else "—"
        viatura_selecionada_modelo = v.modelo or ""
        viatura_selecionada_combustivel = str(v.combustivel) if v.combustivel_id else ""
        viatura_selecionada_tipo = v.tipo or ""
        try:
            viatura_selecionada_edit_url = reverse(
                "cadastros:viatura_update", args=[oficio.viatura_id]
            )
        except Exception:
            viatura_selecionada_edit_url = ""

    return {
        "page_title": "Cadastro de ofício",
        **_wizard_shell_ctx(
            oficio=oficio,
            etapa_atual="dados_viajantes",
            dados_viajantes_status=avaliacao["status"],
        ),
        "pendencias": pendencias,
        "mostrar_pendencias_documento": mostrar_pendencias_documento,
        "wizard_summary": summary,
        "mostrar_custeio_observacao": mostrar_custeio_observacao,
        "modelos_motivo_url": _url_with_next(
            "oficios:modelos_motivo_index",
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
        ),
        "tem_modelos_motivo": modelos_queryset.exists(),
        "modelo_motivo_selecionado": bool(form["modelo_motivo"].value()),
        "servidor_create_url": _cadastro_create_url(
            "cadastros:servidor_create",
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
        ),
        "viatura_create_url": _cadastro_create_url(
            "cadastros:viatura_create",
            reverse("oficios:dados_viajantes", args=[oficio.pk]),
        ),
        "api_viatura_placa_url": reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
        "equipe_servidor_ids_csv": ",".join(str(pk) for pk in equipe_ids),
        "viatura_selecionada_unidade": viatura_selecionada_unidade,
        "viatura_selecionada_edit_url": viatura_selecionada_edit_url,
        "viatura_selecionada_modelo": viatura_selecionada_modelo,
        "viatura_selecionada_combustivel": viatura_selecionada_combustivel,
        "viatura_selecionada_tipo": viatura_selecionada_tipo,
        "show_motorista_card": show_motorista_card,
        "motorista_extras_visivel": motorista_extras_visivel,
        "motorista_oficio_ano": oficio.ano or timezone.localdate().year,
        "oficio_numero_ano_hint": f"/ {oficio.ano}" if oficio.ano else "",
        "motorista_oficio_numero_inicial": _motorista_oficio_numero_display(ref_raw),
        "motorista_compact_widget": mark_safe(
            transporte_form["motorista"].as_widget(attrs={"data-picker-variant": "compact"})
        ),
        "form": form,
        "transporte_form": transporte_form,
        "oficio": oficio,
        "wizard_back_url": _oficio_back_url(oficio),
        "wizard_back_label": _oficio_back_label(oficio),
        "wizard_footer_mode": "step1_minimal",
        "wizard_show_document_actions": False,
        "wizard_show_save_draft": False,
        "wizard_autosave_url": reverse("oficios:dados_viajantes_autosave", args=[oficio.pk]),
        "wizard_autosave_step": "dados_viajantes",
        **_wizard_footer_ctx(oficio),
    }


def _redirect_after_dados_viajantes_save(request, oficio, *, nav_action: str, created=False):
    if nav_action in ("wizard_back", "save_draft_list"):
        return _redirect_lista_oficio(
            request,
            oficio,
            "Ofício cadastrado com sucesso."
            if created
            else "Dados e viajantes salvos.",
        )
    if nav_action == "wizard_next":
        messages.success(
            request,
            "Ofício cadastrado com sucesso."
            if created
            else "Dados e viajantes atualizados com sucesso.",
        )
        return redirect("oficios:wizard_roteiro", pk=oficio.pk)
    messages.success(
        request,
        "Ofício cadastrado com sucesso." if created else "Dados e viajantes atualizados com sucesso.",
    )
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


def _wizard_transporte_context(*, form, oficio):
    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    transp_av = avaliar_oficio_transporte(oficio)
    summary = apresentar_oficio_wizard_summary(oficio)
    equipe_ids = list(oficio.servidores.values_list("pk", flat=True))
    modo_motorista = oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR
    motorista_extras_visivel = modo_motorista == Oficio.MOTORISTA_MODO_MANUAL or (
        bool(oficio.motorista_id) and oficio.motorista_id not in equipe_ids
    )
    ano_motorista_ctx = oficio.ano or timezone.localdate().year
    if form.is_bound:
        ref_raw = (form.data.get("motorista_oficio_referencia") or "").strip()
    else:
        ref_raw = (oficio.motorista_oficio_referencia or "").strip()
    return {
        "page_title": "Cadastro de ofício",
        **_wizard_shell_ctx(
            oficio=oficio,
            etapa_atual="transporte",
            dados_viajantes_status=dados_av["status"],
            transporte_status=transp_av["status"],
        ),
        "wizard_summary": summary,
        "form": form,
        "oficio": oficio,
        "viatura_create_url": _cadastro_create_url(
            "cadastros:viatura_create",
            reverse("oficios:transporte", args=[oficio.pk]),
        ),
        "servidor_create_url": _cadastro_create_url(
            "cadastros:servidor_create",
            reverse("oficios:transporte", args=[oficio.pk]),
        ),
        "equipe_servidor_ids_csv": ",".join(str(pk) for pk in equipe_ids),
        "motorista_extras_visivel": motorista_extras_visivel,
        "motorista_oficio_ano": ano_motorista_ctx,
        "motorista_oficio_numero_inicial": _motorista_oficio_numero_display(ref_raw),
        "api_viatura_placa_url": reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
        "wizard_back_url": _oficio_back_url(oficio),
        "wizard_back_label": _oficio_back_label(oficio),
        "wizard_show_document_actions": True,
        "wizard_show_save_draft": True,
        "wizard_autosave_url": reverse("oficios:transporte_autosave", args=[oficio.pk]),
        "wizard_autosave_step": "transporte",
        **_wizard_footer_ctx(oficio),
    }


def _redirect_after_transporte_save(request, oficio, *, nav_action: str):
    if nav_action == "wizard_back":
        messages.success(request, "Transporte salvo.")
        return redirect("oficios:dados_viajantes", pk=oficio.pk)
    if nav_action == "save_draft_list":
        return _redirect_lista_oficio(request, oficio, "Transporte salvo.")
    if nav_action == "wizard_next":
        messages.success(request, "Transporte salvo. Continue para a próxima etapa quando estiver pronto.")
        return redirect("oficios:wizard_roteiro", pk=oficio.pk)
    messages.success(request, "Rascunho do transporte salvo.")
    return redirect("oficios:transporte", pk=oficio.pk)


def _querydict_from_pairs(pairs):
    data = QueryDict(mutable=True)
    for name, value in pairs.items():
        if isinstance(value, (list, tuple, set)):
            data.setlist(name, [str(item) for item in value if item not in (None, "")])
        elif value is not None:
            data[name] = str(value)
    return data


def _merge_payload_fields(data, clean_fields):
    for name, value in clean_fields.items():
        if isinstance(value, list):
            data.setlist(name, [str(item) for item in value if item not in (None, "")])
        elif value is None:
            data[name] = ""
        else:
            data[name] = str(value)
    return data


def _oficio_dados_viajantes_autosave_data(oficio):
    return _querydict_from_pairs(
        {
            "numero": oficio.numero or "",
            "protocolo": oficio.protocolo or "",
            "modelo_motivo": "",
            "motivo": oficio.motivo or "",
            "custeio": oficio.custeio or Oficio.CUSTEIO_UNIDADE_DPC,
            "custeio_observacao": oficio.custeio_observacao or "",
            "viatura": oficio.viatura_id or "",
            "servidores": list(oficio.servidores.values_list("pk", flat=True)),
            "servidores_termo_autorizacao_present": "1",
            "servidores_termo_autorizacao": list(
                oficio.servidores_termo_autorizacao.values_list("pk", flat=True),
            ),
            "transporte_embed": "1",
            "porte_transporte_armas": "sim" if oficio.porte_transporte_armas else "nao",
            "transporte_placa_manual": oficio.transporte_placa_manual or "",
            "transporte_modelo_manual": oficio.transporte_modelo_manual or "",
            "transporte_combustivel_manual": oficio.transporte_combustivel_manual_id or "",
            "transporte_tipo_manual": oficio.transporte_tipo_manual or "",
            "motorista_modo": oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR,
            "motorista": oficio.motorista_id or "",
            "motorista_manual_nome": oficio.motorista_manual_nome or "",
            "motorista_oficio_referencia": oficio.motorista_oficio_referencia or "",
            "motorista_protocolo_ref": oficio.motorista_protocolo_ref or "",
        }
    )


def _oficio_transporte_autosave_data(oficio):
    return _querydict_from_pairs(
        {
            "viatura": oficio.viatura_id or "",
            "porte_transporte_armas": "sim" if oficio.porte_transporte_armas else "nao",
            "transporte_placa_manual": oficio.transporte_placa_manual or "",
            "transporte_modelo_manual": oficio.transporte_modelo_manual or "",
            "transporte_combustivel_manual": oficio.transporte_combustivel_manual_id or "",
            "transporte_tipo_manual": oficio.transporte_tipo_manual or "",
            "motorista_modo": oficio.motorista_modo or Oficio.MOTORISTA_MODO_SERVIDOR,
            "motorista": oficio.motorista_id or "",
            "motorista_manual_nome": oficio.motorista_manual_nome or "",
            "motorista_oficio_referencia": oficio.motorista_oficio_referencia or "",
            "motorista_protocolo_ref": oficio.motorista_protocolo_ref or "",
        }
    )


def _oficio_autosave_version(oficio):
    oficio.refresh_from_db()
    return int(timezone.localtime(oficio.updated_at).timestamp())


def _justificativa_autosave_data(inst):
    return _querydict_from_pairs(
        {
            "modelo": inst.modelo_id or "",
            "texto": inst.texto or "",
        }
    )


def index(request):
    from django.db.models import OuterRef, Q
    from core import documento_abas as tabs
    from prestacoes_contas.models import PrestacaoServidor

    q           = request.GET.get("q",          "").strip()
    status      = request.GET.get("status",     "").strip()
    aba         = tabs.normalizar_aba(request.GET.get("aba", ""))
    criacao_de  = request.GET.get("criacao_de", "").strip()
    criacao_ate = request.GET.get("criacao_ate","").strip()
    viagem_de   = request.GET.get("viagem_de",  "").strip()
    viagem_ate  = request.GET.get("viagem_ate", "").strip()
    sort        = request.GET.get("sort",       "").strip()

    base = listar_oficios(
        q=q or None,
        status=status or None,
        criacao_de=criacao_de or None,
        criacao_ate=criacao_ate or None,
        viagem_de=viagem_de or None,
        viagem_ate=viagem_ate or None,
        sort=sort or None,
    )
    # Finalizado = todos os servidores da prestação deste ofício foram finalizados.
    sub = PrestacaoServidor.objects.filter(prestacao__oficio=OuterRef("pk"))
    base = tabs.anotar_finalizacao(base, sub, sub.filter(finalizada=False))
    cancelado_q = Q(cancelado=True)
    date_field = "roteiro__saida_dt__date"

    oficios = base.filter(tabs.q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q))
    contagem = tabs.contar_por_aba(base, date_field=date_field, cancelado_q=cancelado_q)
    abas = tabs.build_abas(
        reverse("oficios:index"), aba, contagem,
        preserved={"q": q, "status": status, "sort": sort,
                   "criacao_de": criacao_de, "criacao_ate": criacao_ate,
                   "viagem_de": viagem_de, "viagem_ate": viagem_ate},
    )
    cards = []
    for oficio in oficios:
        card = apresentar_oficio_card(oficio, excluir_next_url=reverse("oficios:index"))
        card["actions"] = apresentar_acoes_oficio(
            editar_url=reverse("oficios:editar", args=[oficio.pk]),
            excluir_url=reverse("oficios:excluir", args=[oficio.pk]),
            visualizar_documento_url=reverse("oficios:wizard_documentos", args=[oficio.pk]),
        )
        cards.append(card)

    has_filters = any([q, status, criacao_de, criacao_ate, viagem_de, viagem_ate, sort])

    return render(
        request,
        "oficios/index.html",
        {
            "page_title": "Ofícios",
            "q":           q,
            "status":      status,
            "aba":         aba,
            "abas":        abas,
            "criacao_de":  criacao_de,
            "criacao_ate": criacao_ate,
            "viagem_de":   viagem_de,
            "viagem_ate":  viagem_ate,
            "sort":        sort,
            "has_filters": has_filters,
            "cards":       cards,
            "create_url":  reverse("oficios:novo"),
            "search_clear_url": f"{reverse('oficios:index')}?aba={aba}",
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": v, "label": l} for v, l in Oficio.STATUS_CHOICES],
            "sort_options": [
                {"value": "numero_desc",  "label": "Número: maior"},
                {"value": "numero_asc",   "label": "Número: menor"},
                {"value": "criacao_desc", "label": "Criação: mais recente"},
                {"value": "criacao_asc",  "label": "Criação: mais antiga"},
                {"value": "viagem_asc",   "label": "Viagem: mais próxima"},
                {"value": "viagem_desc",  "label": "Viagem: mais distante"},
            ],
            "empty_message": "Nenhum ofício encontrado com os filtros aplicados.",
        },
    )


@require_http_methods(["GET", "POST"])
def novo(request):
    if request.method == "GET":
        return render(
            request,
            "components/create_draft.html",
            {
                "page_title": "Novo ofício",
                "page_description": "Confirme para reservar a numeração e iniciar o cadastro.",
                "confirm_label": "Criar ofício",
                "back_url": reverse("oficios:index"),
            },
        )
    evento = resolve_evento_from_request(request)
    oficio = criar_oficio_rascunho(evento=evento)
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


def detalhe(request, pk):
    """Compatibilidade de URLs antigas: a listagem e o fluxo usam apenas o wizard de edição."""
    get_oficio_by_id(pk)
    return redirect("oficios:dados_viajantes", pk=pk)


def editar(request, pk):
    oficio = get_oficio_by_id(pk)
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


def dados_viajantes(request, pk):
    oficio = get_oficio_by_id(pk)
    form = OficioDadosViajantesForm(request.POST or None, instance=oficio)
    transporte_form = OficioTransporteForm(request.POST or None, instance=Oficio.objects.get(pk=oficio.pk))
    _prepare_dados_viajantes_form(form)
    _prepare_transporte_form(transporte_form)
    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST)
        dados_ok = form.is_valid()
        save_transport = request.POST.get("transporte_embed") == "1"
        transporte_valido = bool(save_transport and transporte_form.is_valid())
        transp_ok = (not save_transport) or transporte_valido or nav_action == "wizard_next"
        if dados_ok and transp_ok:
            persist_action = _wizard_persist_action_para_dados_viajantes(nav_action)
            try:
                oficio = atualizar_oficio_dados_viajantes(oficio, form, action=persist_action)
            except OficioNumeroConflitoError as exc:
                form.add_error("numero", str(exc))
            else:
                if transporte_valido:
                    transporte_form = OficioTransporteForm(request.POST, instance=oficio)
                    _prepare_transporte_form(transporte_form)
                    transporte_form.is_valid()
                    oficio = atualizar_oficio_transporte(
                        oficio,
                        transporte_form,
                        action="save_continue" if nav_action == "wizard_next" else "save_draft",
                    )
                return _redirect_after_dados_viajantes_save(request, oficio, nav_action=nav_action, created=False)
    avaliacao = avaliar_oficio_dados_viajantes(form=form, oficio=oficio)
    mostrar_pendencias_documento = request.GET.get("documento_incompleto") == "1"
    return render(
        request,
        "oficios/wizard_dados_viajantes.html",
        _wizard_dados_viajantes_context(
            form=form,
            transporte_form=transporte_form,
            oficio=oficio,
            avaliacao=avaliacao,
            mostrar_pendencias_documento=mostrar_pendencias_documento,
        ),
    )


def _autosave_form_errors(*forms):
    errors = {}
    for form in forms:
        for field, messages_list in form.errors.items():
            errors[field] = [str(item) for item in messages_list]
    return errors


@require_POST
def dados_viajantes_autosave(request, pk):
    oficio = get_oficio_by_id(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="oficio")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    dados_fields = set(OficioDadosViajantesForm.Meta.fields) | {"modelo_motivo"}
    transporte_fields = set(OficioTransporteForm.Meta.fields)
    allowed_fields = dados_fields | transporte_fields
    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, allowed_fields)
    if not clean_fields:
        return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))

    data = _merge_payload_fields(_oficio_dados_viajantes_autosave_data(oficio), clean_fields)
    dirty_names = set(clean_fields)
    if dirty_names & dados_fields:
        form = OficioDadosViajantesForm(data, instance=oficio)
        _prepare_dados_viajantes_form(form)
        if not form.is_valid():
            return autosave_json_response(
                ok=False,
                message="Alguns campos ainda precisam de ajuste antes do autosave.",
                errors=_autosave_form_errors(form),
            )
        try:
            oficio = atualizar_oficio_dados_viajantes(oficio, form, action="save_draft")
        except OficioNumeroConflitoError as exc:
            form.add_error("numero", str(exc))
            return autosave_json_response(
                ok=False,
                message=str(exc),
                errors=_autosave_form_errors(form),
            )

    if dirty_names & transporte_fields:
        transporte_form = OficioTransporteForm(data, instance=oficio)
        _prepare_transporte_form(transporte_form)
        if not transporte_form.is_valid():
            return autosave_json_response(
                ok=False,
                message="Alguns campos de transporte ainda precisam de ajuste antes do autosave.",
                errors=_autosave_form_errors(transporte_form),
            )
        oficio = atualizar_oficio_transporte(oficio, transporte_form, action="save_draft")

    return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))


def transporte(request, pk):
    oficio = get_oficio_by_id(pk)
    form = OficioTransporteForm(request.POST or None, instance=oficio)
    _prepare_transporte_form(form)
    if request.method == "POST" and form.is_valid():
        nav_action = _wizard_normalizar_acao(request.POST)
        oficio = atualizar_oficio_transporte(
            oficio,
            form,
            action="save_continue" if nav_action == "wizard_next" else "save_draft",
        )
        return _redirect_after_transporte_save(request, oficio, nav_action=nav_action)
    return render(
        request,
        "oficios/wizard_transporte.html",
        _wizard_transporte_context(form=form, oficio=oficio),
    )


@require_POST
def transporte_autosave(request, pk):
    oficio = get_oficio_by_id(pk)
    try:
        payload = parse_autosave_payload(request, expected_model="oficio")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(
        payload.fields,
        payload.dirty_fields,
        set(OficioTransporteForm.Meta.fields),
    )
    if not clean_fields:
        return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))

    data = _merge_payload_fields(_oficio_transporte_autosave_data(oficio), clean_fields)
    form = OficioTransporteForm(data, instance=oficio)
    _prepare_transporte_form(form)
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns campos de transporte ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )

    oficio = atualizar_oficio_transporte(oficio, form, action="save_draft")
    return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))


def _resolver_roteiro_rascunho_autosave(post, *, oficio):
    """Resolve um rascunho de Roteiro ja criado por autosave nesta mesma edicao
    (o JS guarda o pk em `autosave_obj_id` assim que o primeiro autosave cria a linha)."""
    raw = (post.get("autosave_obj_id") or "").strip()
    if not raw:
        return None
    try:
        pk = int(raw)
    except (TypeError, ValueError):
        return None
    return (
        Roteiro.objects.filter(
            pk=pk,
            area_id=oficio.area_id,
            tipo=Roteiro.TIPO_AVULSO,
            status=Roteiro.STATUS_RASCUNHO,
        )
        .filter(Q(oficios__isnull=True) | Q(oficios=oficio))
        .distinct()
        .first()
    )


@require_POST
def wizard_roteiro_autosave_criar(request, pk):
    """Cria (via autosave) o rascunho de roteiro proprio do oficio e ja vincula ao oficio.

    Sem isso, desmarcar o roteiro do evento (item "Roteiro novo") e comecar a preencher
    um roteiro proprio nao sobrevive a uma nova visita a etapa: como `oficio.roteiro_id`
    continua None ate o save final, a proxima GET volta a sugerir o roteiro do evento
    (ver `resolver_roteiro_padrao_evento`), fazendo parecer que "desmarcar" nao funciona.
    """
    oficio = get_oficio_by_id(pk)
    if oficio.roteiro_id:
        return autosave_json_response(ok=True, object_id=oficio.roteiro_id, created=False)

    try:
        payload = parse_autosave_payload(request, expected_model="roteiro")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(payload.fields, payload.dirty_fields, ROTEIRO_AUTOSAVE_FIELDS)
    if not has_minimum_roteiro_content(clean_fields, payload.snapshots):
        return autosave_json_response(ok=False, message="Conteúdo insuficiente para criar rascunho.")

    roteiro = build_roteiro_draft()
    version = apply_roteiro_autosave(roteiro, clean_fields, payload.snapshots)
    if not roteiro.origem_cidade_id and not roteiro.origem_estado_id:
        # A sede exibida na tela (herdada do evento/config) nao chega "suja" no payload de
        # autosave se o usuario nunca clicou nela — sem isso o rascunho nasceria sem sede.
        from cadastros.services import resolver_sede_ids_desde_configuracao

        estado_id, cidade_id, _aviso = resolver_sede_ids_desde_configuracao()
        if estado_id and cidade_id:
            roteiro.origem_estado_id = estado_id
            roteiro.origem_cidade_id = cidade_id
            roteiro.save(update_fields=["origem_estado", "origem_cidade", "updated_at"])
    oficio.roteiro = roteiro
    oficio.save(update_fields=["roteiro", "updated_at"])
    return autosave_json_response(ok=True, object_id=roteiro.pk, created=True, version=version)


def wizard_roteiro(request, pk):
    oficio = get_oficio_by_id(pk)
    # Nao cria mais um Roteiro vazio so por abrir a etapa: enquanto o oficio nao tiver
    # roteiro proprio, o form so ganha uma linha no banco quando o autosave (mesmo
    # mecanismo ja usado no fluxo avulso) detectar conteudo minimo, ou no save final.
    roteiro_vinculado = oficio.roteiro
    qtd_viajantes = oficio.servidores.count()

    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas(
        evento=oficio.evento, excluir_pk=roteiro_vinculado.pk if roteiro_vinculado else None
    )

    if request.method == "POST":
        if roteiro_vinculado is None:
            roteiro_vinculado = _resolver_roteiro_rascunho_autosave(
                request.POST,
                oficio=oficio,
            )
        form = RoteiroForm(request.POST, instance=roteiro_vinculado)
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=roteiro_vinculado
        )
        roteiro_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
            request.POST, route_state_map, roteiro=roteiro_vinculado
        )
        if form.is_valid() and validated["ok"]:
            roteiro_escolhido = obter_roteiro_escolhido_do_post(
                request.POST,
                evento=oficio.evento,
                area=oficio.area,
            )
            if roteiro_escolhido and roteiro_state_equivalente_ao_roteiro(roteiro_escolhido, roteiro_state, validated):
                # Sem alterações: vincular diretamente ao roteiro selecionado
                rascunho_antigo = roteiro_vinculado if (roteiro_vinculado and roteiro_vinculado.status == Roteiro.STATUS_RASCUNHO) else None
                vincular_roteiro_ao_oficio_sem_copia(oficio, roteiro_escolhido, rascunho_antigo=rascunho_antigo)
            else:
                # Com alterações (ou roteiro próprio): salvar sempre num rascunho
                # Nunca modificar um roteiro não-rascunho que pertence a outros ofícios
                if roteiro_vinculado is None or roteiro_vinculado.status != Roteiro.STATUS_RASCUNHO:
                    roteiro_vinculado = Roteiro(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
                    form.instance = roteiro_vinculado
                roteiro_salvo = atualizar_roteiro(roteiro_vinculado, form, roteiro_state, validated, diarias_resultado)
                if oficio.roteiro_id != roteiro_salvo.pk:
                    oficio.roteiro = roteiro_salvo
                    oficio.save(update_fields=["roteiro", "updated_at"])
            oficio = tocar_data_criacao_oficio(oficio)
            nav_action = _wizard_normalizar_acao(request.POST)
            if nav_action == "wizard_next":
                messages.success(
                    request,
                    "Roteiro e diárias salvos. Continue para a próxima etapa quando estiver pronto.",
                )
                if oficio_exige_justificativa(oficio):
                    return redirect("oficios:wizard_justificativa", pk=oficio.pk)
                return redirect("oficios:wizard_documentos", pk=oficio.pk)
            if nav_action == "wizard_back":
                messages.success(request, "Roteiro e diárias salvos.")
                return redirect("oficios:dados_viajantes", pk=oficio.pk)
            if nav_action == "save_draft_list":
                return _redirect_lista_oficio(request, oficio, "Roteiro e diárias salvos.")
            messages.success(request, "Rascunho do roteiro salvo.")
            return redirect("oficios:wizard_roteiro", pk=oficio.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(roteiro_state)
    elif roteiro_vinculado is not None:
        destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
            roteiro=roteiro_vinculado
        )
        form_initial = {}
        if not (roteiro_vinculado.origem_estado_id or roteiro_vinculado.origem_cidade_id):
            se_id = roteiro_state.get("sede_estado_id")
            sc_id = roteiro_state.get("sede_cidade_id")
            if se_id:
                form_initial["origem_estado"] = se_id
            if sc_id:
                form_initial["origem_cidade"] = sc_id
        form = RoteiroForm(
            instance=roteiro_vinculado,
            initial=form_initial if form_initial else None,
        )
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=roteiro_vinculado
        )
    else:
        # Oficio ainda sem roteiro proprio: pre-seleciona o roteiro do evento (se houver
        # um completo pronto pra reuso) ou parte de sede+destino do evento, sem datas e
        # sem persistir nada ainda.
        roteiro_padrao_evento = resolver_roteiro_padrao_evento(oficio.evento)
        if roteiro_padrao_evento is not None:
            destinos_atuais, trechos_list, roteiro_state = montar_estado_editor_roteiro_evento_selecionado(
                roteiro_padrao_evento
            )
            form_instance = Roteiro(
                tipo=Roteiro.TIPO_AVULSO,
                status=Roteiro.STATUS_RASCUNHO,
                origem_cidade=roteiro_padrao_evento.origem_cidade,
                origem_estado=roteiro_padrao_evento.origem_estado,
                observacoes=roteiro_padrao_evento.observacoes,
            )
        else:
            initial = montar_initial_roteiro_evento_sem_datas(oficio.evento)
            destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
                initial=initial
            )
            form_instance = Roteiro(tipo=Roteiro.TIPO_AVULSO, status=Roteiro.STATUS_RASCUNHO)
            if initial.get("origem_cidade"):
                form_instance.origem_cidade_id = initial["origem_cidade"]
            if initial.get("origem_estado"):
                form_instance.origem_estado_id = initial["origem_estado"]
        form = RoteiroForm(instance=form_instance)
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=form_instance
        )

    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    roteiro_status = _wizard_roteiro_step_status(oficio)
    context = montar_contexto_editor_roteiro(
        evento=None,
        form=form,
        obj=roteiro_vinculado,
        destinos_atuais=destinos_atuais,
        trechos_list=trechos_list,
        is_avulso=True,
        roteiro_state=roteiro_state,
        route_options=route_options,
        diarias_quantidade_servidores=qtd_viajantes,
    )
    context.update(
        {
            "page_title": "Cadastro de ofício",
            **_wizard_shell_ctx(
                oficio=oficio,
                etapa_atual="roteiro",
                dados_viajantes_status=dados_av["status"],
                roteiro_status=roteiro_status,
            ),
            "wizard_summary": apresentar_oficio_wizard_summary(oficio),
            "oficio": oficio,
            "wizard_back_url": _oficio_back_url(oficio),
            "wizard_back_label": _oficio_back_label(oficio),
            "roteiro_editor_oficio": True,
            "wizard_use_outer_form": False,
            **_wizard_footer_ctx(oficio),
        }
    )
    return render(request, "oficios/wizard_roteiro.html", context)


def wizard_justificativa(request, pk):
    oficio = get_oficio_by_id(pk)
    obrigatoria = oficio_exige_justificativa(oficio)
    inst = get_or_create_justificativa_oficio(oficio)
    bypass_texto_obrigatorio = False
    if request.method == "POST":
        raw_action = (request.POST.get("action") or "").strip()
        if raw_action in ("wizard_back", "save_draft_list"):
            bypass_texto_obrigatorio = True
    form = JustificativaOficioForm(
        request.POST or None,
        instance=inst,
        obrigatoria=bool(obrigatoria and not bypass_texto_obrigatorio),
    )

    if request.method == "POST" and form.is_valid():
        nav_action = _wizard_normalizar_acao(request.POST)
        atualizar_justificativa_oficio(
            oficio,
            form,
            action="save_continue" if nav_action == "wizard_next" else "save_draft",
        )
        if nav_action == "wizard_back":
            messages.success(request, "Justificativa salva.")
            return redirect("oficios:wizard_roteiro", pk=oficio.pk)
        if nav_action == "save_draft_list":
            return _redirect_lista_oficio(request, oficio, "Justificativa salva.")
        if nav_action == "wizard_next":
            messages.success(
                request,
                "Justificativa salva. Continue para documentos quando estiver pronto.",
            )
            return redirect("oficios:wizard_documentos", pk=oficio.pk)
        messages.success(request, "Rascunho da justificativa salvo.")
        return redirect("oficios:wizard_justificativa", pk=oficio.pk)

    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    transp_av = avaliar_oficio_transporte(oficio)
    roteiro_av = _wizard_roteiro_step_status(oficio)

    return render(
        request,
        "oficios/wizard_justificativa.html",
        {
            "page_title": "Cadastro de ofício",
            **_wizard_shell_ctx(
                oficio=oficio,
                etapa_atual="justificativa",
                dados_viajantes_status=dados_av["status"],
                transporte_status=transp_av["status"],
                roteiro_status=roteiro_av,
            ),
            "wizard_summary": apresentar_oficio_wizard_summary(oficio),
            "oficio": oficio,
            "form": form,
            "wizard_back_url": _oficio_back_url(oficio),
            "wizard_back_label": _oficio_back_label(oficio),
            "justificativa_ctx": apresentar_justificativa_wizard_context(oficio),
            "justificativa_obrigatoria": obrigatoria,
            "modelos_justificativa_url": _url_with_next(
                "justificativas:modelos_index",
                reverse("oficios:wizard_justificativa", args=[oficio.pk]),
            ),
            "wizard_autosave_url": reverse("oficios:justificativa_autosave", args=[oficio.pk]),
            "wizard_autosave_step": "justificativa",
            **_wizard_footer_ctx(oficio),
        },
    )


@require_POST
def justificativa_autosave(request, pk):
    oficio = get_oficio_by_id(pk)
    inst = get_or_create_justificativa_oficio(oficio)
    try:
        payload = parse_autosave_payload(request, expected_model="oficio")
    except AutosavePayloadError as exc:
        return autosave_json_response(ok=False, message=str(exc))

    clean_fields = filter_allowed_fields(
        payload.fields,
        payload.dirty_fields,
        set(JustificativaOficioForm.Meta.fields),
    )
    if not clean_fields:
        return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))

    data = _merge_payload_fields(_justificativa_autosave_data(inst), clean_fields)
    form = JustificativaOficioForm(data, instance=inst, obrigatoria=False)
    if not form.is_valid():
        return autosave_json_response(
            ok=False,
            message="Alguns campos da justificativa ainda precisam de ajuste antes do autosave.",
            errors=_autosave_form_errors(form),
        )

    atualizar_justificativa_oficio(oficio, form, action="save_draft")
    return autosave_json_response(ok=True, object_id=oficio.pk, version=_oficio_autosave_version(oficio))


def wizard_documentos(request, pk):
    oficio = get_oficio_by_id(pk)
    if request.method == "GET":
        from documentos.services.warm_cache import ensure_document_artifact_cached

        ensure_document_artifact_cached(oficio)
    aval_doc = validar_oficio_para_documento(oficio)
    pendencias = list(aval_doc["pendencias"])
    doc_status = "complete" if aval_doc["status"] == "complete" else "incomplete"

    if request.method == "POST":
        nav_action = _wizard_normalizar_acao(request.POST, default="save_draft")

        if nav_action == "finalizar":
            aval = validar_oficio_para_documento(oficio)
            if aval["pendencias"]:
                for msg in aval["pendencias"]:
                    messages.error(request, msg)
                return redirect("oficios:wizard_documentos", pk=pk)
            oficio.status = Oficio.STATUS_FINALIZADO
            oficio.data_criacao = timezone.localdate()
            oficio.save(update_fields=["status", "data_criacao", "updated_at"])
            return _redirect_lista_oficio(request, oficio, "Ofício finalizado com sucesso.")
        if nav_action == "wizard_back":
            from documentos.services.warm_cache import ensure_document_artifact_cached

            ensure_document_artifact_cached(oficio)
            messages.info(request, "Retornando à etapa anterior.")
            return redirect("oficios:wizard_justificativa", pk=pk)
        if nav_action == "save_draft_list":
            oficio.save(update_fields=["updated_at"])
            return _redirect_lista_oficio(request, oficio, "Rascunho salvo.")
        messages.success(request, "Rascunho salvo.")
        return redirect("oficios:wizard_documentos", pk=pk)

    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    transp_av = avaliar_oficio_transporte(oficio)
    roteiro_av = _wizard_roteiro_step_status(oficio)

    return render(
        request,
        "oficios/wizard_documentos.html",
        {
            "page_title": "Cadastro de ofício",
            **_wizard_shell_ctx(
                oficio=oficio,
                etapa_atual="documentos",
                dados_viajantes_status=dados_av["status"],
                transporte_status=transp_av["status"],
                roteiro_status=roteiro_av,
                documentos_status=doc_status,
            ),
            "wizard_summary": apresentar_oficio_wizard_summary(oficio),
            "oficio": oficio,
            "wizard_back_url": _oficio_back_url(oficio),
            "wizard_back_label": _oficio_back_label(oficio),
            "wizard_finalizar": True,
            "wizard_show_document_actions": False,
            "wizard_show_save_draft": False,
            "documentos_ctx": apresentar_oficio_wizard_documentos_context(oficio),
            "pendencias_documentos": pendencias,
            "mostrar_pendencias": bool(pendencias),
            **_wizard_footer_ctx(oficio),
        },
    )


def wizard_resumo(request, pk):
    """Compatibilidade: `/resumo/` é alias da etapa 5 — mesmo conteúdo de `wizard_documentos`."""
    return wizard_documentos(request, pk)


@require_GET
def api_viatura_por_placa(request, pk):
    """Busca viaturas por texto (`q`) ou compatível com consulta só por placa (`placa`).

    Parâmetros opcionais para o picker do wizard:
    - ``motorista_id``: prioriza viaturas vinculadas ao motorista selecionado
      (chip ``suggestion_reason="motorista"``).
    - Por padrão também considera ``equipe`` do ofício para sugestões por unidade.
    """
    from .selectors import _unidade_ids_dos_servidores

    oficio = get_oficio_by_id(pk)
    legado_placa = request.GET.get("placa", "").strip()
    q = request.GET.get("q", "").strip()

    if legado_placa and not q:
        viatura = get_viatura_por_placa_normalizada(legado_placa)
        if viatura is None:
            return JsonResponse({"found": False})
        return JsonResponse(
            {
                "found": True,
                "id": viatura.pk,
                "placa_formatada": viatura.placa_formatada,
                "modelo": viatura.modelo or "",
                "combustivel_id": viatura.combustivel_id,
                "tipo": viatura.tipo or "",
            }
        )

    equipe_ids = list(oficio.servidores.values_list("pk", flat=True))

    motorista_id_raw = request.GET.get("motorista_id", "").strip()
    try:
        motorista_id = int(motorista_id_raw) if motorista_id_raw else None
    except (TypeError, ValueError):
        motorista_id = None

    if len(q) < 2 and not equipe_ids and not motorista_id:
        return JsonResponse({"results": []})

    encontradas = buscar_viaturas_para_oficio(
        q,
        equipe_servidor_ids=equipe_ids or None,
        motorista_id=motorista_id,
    )
    unidade_match_ids = _unidade_ids_dos_servidores(equipe_ids)
    results = [
        viatura_para_resultado_busca(
            v,
            motorista_id=motorista_id,
            unidade_match_ids=unidade_match_ids,
        )
        for v in encontradas
    ]
    # Ordenar: motorista_match -> unidade_match -> demais (mantém ordem por placa do queryset).
    reason_order = {"motorista": 0, "unidade": 1}
    results.sort(key=lambda r: reason_order.get(r.get("suggestion_reason") or "", 2))
    return JsonResponse({"results": results})


def _redirect_se_oficio_documento_incompleto(request, oficio):
    avaliacao = validar_oficio_para_documento(oficio)
    if avaliacao["pendencias"]:
        messages.error(request, "Documento nao gerado porque o oficio esta incompleto.")
        alvo = redirect_para_corrigir_documento_oficio(oficio)
        return redirect(f"{alvo}?documento_incompleto=1")
    return None


def _pdf_inline_response(request, oficio, *, gerar, tipo: DocumentoTipo, reference: str, step_name: str):
    bloqueio = _redirect_se_oficio_documento_incompleto(request, oficio)
    if bloqueio is not None:
        return bloqueio
    with measure_step(step_name, {"oficio_id": oficio.pk}):
        resp = download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=DocumentoFormato.PDF,
            gerar=gerar,
        )
    if getattr(resp, "status_code", 200) in (301, 302, 303, 307, 308):
        return resp
    return build_inline_pdf_response_from_download_response(
        request,
        resp,
        tipo=tipo,
        reference=reference,
        now=timezone.now(),
    )


@require_GET
def oficio_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    ref = oficio.numero_formatado.replace("/", "-")
    return _pdf_inline_response(
        request,
        oficio,
        gerar=lambda: gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF),
        tipo=DocumentoTipo.OFICIO,
        reference=ref,
        step_name="http_oficio_pdf_inline",
    )


@require_GET
def justificativa_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    ref = f"{oficio.numero_formatado.replace('/', '-')}-justificativa"
    return _pdf_inline_response(
        request,
        oficio,
        gerar=lambda: gerar_resposta_justificativa_documento(oficio, DocumentoFormato.PDF),
        tipo=DocumentoTipo.JUSTIFICATIVA,
        reference=ref,
        step_name="http_justificativa_pdf_inline",
    )


@require_GET
def ordem_servico_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    ref = f"{oficio.numero_formatado.replace('/', '-')}-ordem-servico"
    return _pdf_inline_response(
        request,
        oficio,
        gerar=lambda: gerar_resposta_ordem_servico_documento(oficio, DocumentoFormato.PDF),
        tipo=DocumentoTipo.ORDEM_SERVICO,
        reference=ref,
        step_name="http_ordem_servico_pdf_inline",
    )


def baixar_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        formato_documento = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    avaliacao = validar_oficio_para_documento(oficio)
    if avaliacao["pendencias"]:
        messages.error(request, "Documento nao gerado porque o oficio esta incompleto.")
        alvo = redirect_para_corrigir_documento_oficio(oficio)
        return redirect(f"{alvo}?documento_incompleto=1")
    with measure_step(
        "http_baixar_documento",
        {"oficio_id": oficio.pk, "formato": formato_documento.value},
    ):
        return download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=formato_documento,
            gerar=lambda: gerar_resposta_documento_oficio(oficio, formato_documento),
        )


def baixar_justificativa_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        formato_documento = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    with measure_step(
        "http_baixar_justificativa_documento",
        {"oficio_id": oficio.pk, "formato": formato_documento.value},
    ):
        response = download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=formato_documento,
            gerar=lambda: gerar_resposta_justificativa_documento(oficio, formato_documento),
        )
    if hasattr(response, "headers") and response.get("Content-Disposition", "").startswith("attachment"):
        ext = "pdf" if formato_documento == DocumentoFormato.PDF else "docx"
        safe_numero = oficio.numero_formatado.replace("/", "-")
        response["Content-Disposition"] = f'attachment; filename="Justificativa {safe_numero}.{ext}"'
    return response


def baixar_ordem_servico_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        formato_documento = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    avaliacao = validar_oficio_para_documento(oficio)
    if avaliacao["pendencias"]:
        messages.error(request, "Documento nao gerado porque o oficio esta incompleto.")
        alvo = redirect_para_corrigir_documento_oficio(oficio)
        return redirect(f"{alvo}?documento_incompleto=1")
    with measure_step(
        "http_baixar_ordem_servico_documento",
        {"oficio_id": oficio.pk, "formato": formato_documento.value},
    ):
        return download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=formato_documento,
            gerar=lambda: gerar_resposta_ordem_servico_documento(oficio, formato_documento),
        )


def excluir(request, pk):
    oficio = get_oficio_by_id(pk)
    evento_id = oficio.evento_id

    def _fallback_url():
        if evento_id:
            return redirect("eventos:guiado_etapa", pk=evento_id, etapa=3)
        return redirect("oficios:index")

    if request.method == "POST":
        next_url = _safe_next_url(request, "")
        try:
            excluir_oficio(oficio)
        except OficioVinculadoError:
            messages.error(
                request,
                "Não foi possível excluir o ofício porque ele está vinculado a outros registros.",
            )
            return redirect(next_url) if next_url else _fallback_url()
        messages.success(request, "Ofício excluído com sucesso.")
        return redirect(next_url) if next_url else _fallback_url()
    return redirect(_oficio_back_url(oficio))


@require_POST
def cancelar(request, pk):
    oficio = get_oficio_by_id(pk)
    next_url = _safe_next_url(request, "")

    def _fallback_url():
        if oficio.evento_id:
            return redirect("eventos:guiado_etapa", pk=oficio.evento_id, etapa=3)
        return redirect("oficios:index")

    if oficio.cancelado:
        messages.error(request, "Este ofício já está cancelado.")
        return redirect(next_url) if next_url else _fallback_url()

    motivo = (request.POST.get("motivo") or "").strip()
    if not motivo:
        messages.error(request, "Informe o motivo do cancelamento.")
        return redirect(next_url) if next_url else _fallback_url()

    cancelar_oficio(oficio, motivo)
    messages.success(request, "Ofício cancelado. Ele não gera mais prestação de contas nem pode ser usado em novas Ordens de Serviço.")
    return redirect(next_url) if next_url else _fallback_url()


@require_POST
def retificar(request, pk):
    oficio = get_oficio_by_id(pk)
    next_url = _safe_next_url(request, "")

    def _fallback_url():
        if oficio.evento_id:
            return redirect("eventos:guiado_etapa", pk=oficio.evento_id, etapa=3)
        return redirect("oficios:index")

    if oficio.retificado_documento:
        desfazer_retificacao_oficio(oficio)
        messages.success(request, "Retificação removida. O ofício voltou ao rótulo padrão do documento.")
        return redirect(next_url) if next_url else _fallback_url()

    retificar_oficio(oficio)
    messages.success(request, "Ofício marcado como retificado. Edite o que for necessário — o documento passará a exibir \"Retificado\" ao lado do número.")
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


@require_POST
def marcar_complementar(request, pk):
    oficio = get_oficio_by_id(pk)
    next_url = _safe_next_url(request, "")

    def _fallback_url():
        if oficio.evento_id:
            return redirect("eventos:guiado_etapa", pk=oficio.evento_id, etapa=3)
        return redirect("oficios:index")

    if oficio.complementar_documento:
        desfazer_complementar_oficio(oficio)
        messages.success(request, "Marcação de complementar removida do ofício.")
        return redirect(next_url) if next_url else _fallback_url()

    marcar_oficio_complementar(oficio)
    messages.success(request, "Ofício marcado como complementar. Edite o que for necessário — o documento passará a exibir \"Complementar\" ao lado do número.")
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


def modelos_motivo_index(request):
    q = request.GET.get("q", "").strip()
    back_url = _safe_next_url(request, reverse("oficios:novo"))
    _os_prefix = reverse("ordens_servico:index")
    if back_url.startswith(_os_prefix):
        back_label = "Voltar para a Ordem de Serviço"
        back_aria_label = "Voltar para o cadastro de Ordem de Serviço"
    else:
        back_label = "Voltar para o ofício"
        back_aria_label = "Voltar para o cadastro de ofício"
    form = ModeloMotivoOficioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_modelo_motivo(form)
        messages.success(request, "Modelo de motivo criado com sucesso.")
        return redirect(_url_with_next("oficios:modelos_motivo_index", back_url))
    modelos = listar_modelos_motivo(q=q or None, incluir_inativos=True)
    rows = [
        apresentar_linha_lista_simples_modelo_motivo(
            modelo,
            edit_url=reverse("oficios:modelo_motivo_editar", args=[modelo.pk]),
            delete_url=reverse("oficios:modelo_motivo_excluir", args=[modelo.pk]),
            delete_modal=True,
        )
        for modelo in modelos
    ]
    return render(
        request,
        "oficios/modelos_motivo/index.html",
        {
            "page_title": "Modelos de motivo",
            "page_description": "Cadastre textos reutilizáveis para preencher rapidamente o motivo dos ofícios.",
            "q": q,
            "rows": rows,
            "quick_add_form": form,
            "quick_add_next_url": back_url,
            "back_to_oficio_url": back_url,
            "back_label": back_label,
            "back_aria_label": back_aria_label,
        },
    )


@require_POST
def modelo_motivo_definir_padrao(request, pk):
    modelo = get_modelo_motivo_by_id(pk)
    modelo.is_padrao = True
    modelo.save()
    messages.success(request, "Modelo definido como padrão.")
    return redirect("oficios:modelos_motivo_index")


def modelo_motivo_editar(request, pk):
    """Edição inline via quick edit da lista; a página standalone foi removida."""
    modelo = get_modelo_motivo_by_id(pk)
    form = ModeloMotivoOficioForm(request.POST or None, instance=modelo)
    if request.method == "POST":
        if form.is_valid():
            atualizar_modelo_motivo(modelo, form)
            messages.success(request, "Modelo de motivo atualizado com sucesso.")
        else:
            messages.error(request, "Não foi possível salvar o modelo. Verifique os dados informados.")
    return redirect("oficios:modelos_motivo_index")


def modelo_motivo_excluir(request, pk):
    modelo = get_modelo_motivo_by_id(pk)
    if request.method == "POST":
        excluir_modelo_motivo(modelo)
        messages.success(request, "Modelo de motivo excluído com sucesso.")
        return redirect("oficios:modelos_motivo_index")
    return render(
        request,
        "oficios/modelos_motivo/confirm_delete.html",
        {
            "page_title": "Excluir modelo de motivo",
            "page_description": "Confirme a remoção deste modelo de motivo.",
            "object": modelo,
            "back_url": reverse("oficios:modelos_motivo_index"),
        },
    )
