import logging
import re
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from justificativas.forms import JustificativaOficioForm
from justificativas.presenters import apresentar_justificativa_wizard_context
from justificativas.services import atualizar_justificativa_oficio
from justificativas.services import get_or_create_justificativa_oficio
from justificativas.services import oficio_exige_justificativa

from roteiros.forms import RoteiroForm
from roteiros.services import (
    atualizar_roteiro,
    carregar_opcoes_rotas_avulsas_salvas,
    montar_contexto_editor_roteiro,
    normalizar_destinos_e_trechos_apos_erro_post,
    preparar_estado_editor_roteiro_para_get,
    preparar_querysets_formulario_roteiro,
    validar_submissao_editor_roteiro,
)

from cadastros.models import Combustivel
from cadastros.models import Servidor
from assinaturas.services.recording import registrar_verificacao_artefato
from assinaturas.services.verification import verificar_artefato_documento
from .assinaturas_central import build_documentos_assinatura_central
from .assinaturas_central import wizard_assinaturas_post_gerar_solicitacao
from documentos.selectors import get_latest_artefato_pdf_for_oficio
from documentos.services.downloads import download_documento_or_redirect_pdf_error
from documentos.services.warm_cache import pdf_artefato_original_acessivel
from documentos.services.responses import build_inline_pdf_response_from_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from ordens_servico.services import gerar_resposta_ordem_servico_documento
from planos_trabalho.services import gerar_resposta_plano_trabalho_documento
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
from .selectors import map_assinatura_pdf_oficio_por_ids
from .selectors import buscar_viaturas_para_oficio
from .selectors import get_viatura_por_placa_normalizada
from .selectors import viatura_para_resultado_busca
from .selectors import listar_modelos_motivo
from .selectors import listar_oficios
from .selectors import listar_servidores_para_oficio
from .selectors import listar_viaturas_para_oficio
from .services import atualizar_modelo_motivo
from .services import OficioVinculadoError
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
from .services import garantir_roteiro_vinculado_ao_oficio
from .services import redirect_para_corrigir_documento_oficio
from .services import oficio_esta_completo_para_finalizar
from .services import validar_oficio_para_documento


logger = logging.getLogger(__name__)


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


def _prepare_transporte_form(form):
    form.fields["viatura"].queryset = listar_viaturas_para_oficio()
    form.fields["motorista"].queryset = listar_servidores_para_oficio()
    form.fields["transporte_combustivel_manual"].queryset = Combustivel.objects.order_by("nome")


def _wizard_dados_viajantes_context(*, form, oficio, avaliacao=None, mostrar_pendencias_documento=False):
    avaliacao = avaliacao or avaliar_oficio_dados_viajantes(oficio=oficio, form=form)
    transp_av = avaliar_oficio_transporte(oficio)
    pendencias = avaliacao["pendencias"]
    summary = apresentar_oficio_wizard_summary(oficio)
    custeio_value = ""
    if form.is_bound:
        custeio_value = form.data.get("custeio", "")
    else:
        custeio_value = getattr(form.instance, "custeio", "") if getattr(form, "instance", None) else ""
    mostrar_custeio_observacao = custeio_value == "OUTRA_INSTITUICAO"
    modelos_queryset = form.fields["modelo_motivo"].queryset
    return {
        "page_title": "Cadastro de ofício",
        **_wizard_shell_ctx(
            oficio=oficio,
            etapa_atual="dados_viajantes",
            dados_viajantes_status=avaliacao["status"],
            transporte_status=transp_av["status"],
        ),
        "pendencias": pendencias,
        "mostrar_pendencias_documento": mostrar_pendencias_documento,
        "wizard_summary": summary,
        "mostrar_custeio_observacao": mostrar_custeio_observacao,
        "modelos_motivo_url": reverse("oficios:modelos_motivo_index"),
        "tem_modelos_motivo": modelos_queryset.exists(),
        "modelo_motivo_selecionado": bool(form["modelo_motivo"].value()),
        "servidor_create_url": reverse("cadastros:servidor_create"),
        "form": form,
        "oficio": oficio,
        "wizard_back_url": reverse("oficios:index"),
        "wizard_back_label": "Voltar para lista",
        **_wizard_footer_ctx(oficio),
    }


def _redirect_after_dados_viajantes_save(request, oficio, *, nav_action: str, created=False):
    if nav_action in ("wizard_back", "save_draft_list"):
        messages.success(
            request,
            "Ofício cadastrado com sucesso."
            if created
            else "Dados e viajantes salvos. Retornamos à lista de ofícios.",
        )
        return redirect("oficios:index")
    if nav_action == "wizard_next":
        messages.success(
            request,
            "Ofício cadastrado com sucesso."
            if created
            else "Dados e viajantes atualizados com sucesso.",
        )
        return redirect("oficios:transporte", pk=oficio.pk)
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
        "viatura_create_url": reverse("cadastros:viatura_create"),
        "servidor_create_url": reverse("cadastros:servidor_create"),
        "equipe_servidor_ids_csv": ",".join(str(pk) for pk in equipe_ids),
        "motorista_extras_visivel": motorista_extras_visivel,
        "motorista_oficio_ano": ano_motorista_ctx,
        "motorista_oficio_numero_inicial": _motorista_oficio_numero_display(ref_raw),
        "api_viatura_placa_url": reverse("oficios:api_viatura_por_placa", args=[oficio.pk]),
        "wizard_back_url": reverse("oficios:dados_viajantes", args=[oficio.pk]),
        "wizard_back_label": "Voltar",
        **_wizard_footer_ctx(oficio),
    }


def _redirect_after_transporte_save(request, oficio, *, nav_action: str):
    if nav_action == "wizard_back":
        messages.success(request, "Transporte salvo.")
        return redirect("oficios:dados_viajantes", pk=oficio.pk)
    if nav_action == "save_draft_list":
        messages.success(request, "Transporte salvo. Retornamos à lista de ofícios.")
        return redirect("oficios:index")
    if nav_action == "wizard_next":
        messages.success(request, "Transporte salvo. Continue para a próxima etapa quando estiver pronto.")
        return redirect("oficios:wizard_roteiro", pk=oficio.pk)
    messages.success(request, "Rascunho do transporte salvo.")
    return redirect("oficios:transporte", pk=oficio.pk)


def index(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    oficios = listar_oficios(q=q, status=status or None)
    sig_map = map_assinatura_pdf_oficio_por_ids([o.pk for o in oficios])
    cards = []
    for oficio in oficios:
        card = apresentar_oficio_card(oficio, assinatura_pdf=sig_map.get(oficio.pk))
        card["actions"] = apresentar_acoes_oficio(
            editar_url=reverse("oficios:editar", args=[oficio.pk]),
            excluir_url=reverse("oficios:excluir", args=[oficio.pk]),
            visualizar_documento_url=reverse("oficios:wizard_documentos", args=[oficio.pk]),
        )
        cards.append(card)
    return render(
        request,
        "oficios/index.html",
        {
            "page_title": "Ofícios",
            "page_description": "CRUD mínimo inicial para gestão de ofícios e evolução documental.",
            "q": q,
            "status": status,
            "cards": cards,
            "create_url": reverse("oficios:novo"),
            "search_clear_url": reverse("oficios:index"),
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": value, "label": label} for value, label in Oficio.STATUS_CHOICES],
            "empty_message": "Nenhum ofício cadastrado ainda.",
        },
    )


def novo(request):
    oficio = criar_oficio_rascunho()
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
    _prepare_dados_viajantes_form(form)
    if request.method == "POST" and form.is_valid():
        nav_action = _wizard_normalizar_acao(request.POST)
        persist_action = _wizard_persist_action_para_dados_viajantes(nav_action)
        oficio = atualizar_oficio_dados_viajantes(oficio, form, action=persist_action)
        return _redirect_after_dados_viajantes_save(request, oficio, nav_action=nav_action, created=False)
    avaliacao = avaliar_oficio_dados_viajantes(form=form, oficio=oficio)
    mostrar_pendencias_documento = request.GET.get("documento_incompleto") == "1"
    return render(
        request,
        "oficios/wizard_dados_viajantes.html",
        _wizard_dados_viajantes_context(
            form=form,
            oficio=oficio,
            avaliacao=avaliacao,
            mostrar_pendencias_documento=mostrar_pendencias_documento,
        ),
    )


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


def wizard_roteiro(request, pk):
    oficio = get_oficio_by_id(pk)
    oficio = garantir_roteiro_vinculado_ao_oficio(oficio)
    roteiro = oficio.roteiro
    qtd_viajantes = oficio.servidores.count()

    route_options, route_state_map = carregar_opcoes_rotas_avulsas_salvas()

    if request.method == "POST":
        form = RoteiroForm(request.POST, instance=roteiro)
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=roteiro
        )
        roteiro_state, validated, diarias_resultado = validar_submissao_editor_roteiro(
            request.POST, route_state_map, roteiro=roteiro
        )
        if form.is_valid() and validated["ok"]:
            atualizar_roteiro(roteiro, form, roteiro_state, validated, diarias_resultado)
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
                return redirect("oficios:transporte", pk=oficio.pk)
            if nav_action == "save_draft_list":
                messages.success(request, "Roteiro e diárias salvos. Retornamos à lista de ofícios.")
                return redirect("oficios:index")
            messages.success(request, "Rascunho do roteiro salvo.")
            return redirect("oficios:wizard_roteiro", pk=oficio.pk)
        for error in validated.get("errors", []):
            form.add_error(None, error)
        destinos_atuais, trechos_list = normalizar_destinos_e_trechos_apos_erro_post(roteiro_state)
    else:
        destinos_atuais, trechos_list, roteiro_state = preparar_estado_editor_roteiro_para_get(
            roteiro=roteiro
        )
        form_initial = {}
        if not (roteiro.origem_estado_id or roteiro.origem_cidade_id):
            se_id = roteiro_state.get("sede_estado_id")
            sc_id = roteiro_state.get("sede_cidade_id")
            if se_id:
                form_initial["origem_estado"] = se_id
            if sc_id:
                form_initial["origem_cidade"] = sc_id
        form = RoteiroForm(
            instance=roteiro,
            initial=form_initial if form_initial else None,
        )
        preparar_querysets_formulario_roteiro(
            form, method=request.method, post=request.POST, instance=roteiro
        )

    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    transp_av = avaliar_oficio_transporte(oficio)
    roteiro_status = _wizard_roteiro_step_status(oficio)
    context = montar_contexto_editor_roteiro(
        evento=None,
        form=form,
        obj=roteiro,
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
                transporte_status=transp_av["status"],
                roteiro_status=roteiro_status,
            ),
            "wizard_summary": apresentar_oficio_wizard_summary(oficio),
            "oficio": oficio,
            "wizard_back_url": reverse("oficios:transporte", args=[oficio.pk]),
            "wizard_back_label": "Voltar",
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
            messages.success(request, "Justificativa salva. Retornamos à lista de ofícios.")
            return redirect("oficios:index")
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
            "wizard_back_url": reverse("oficios:wizard_roteiro", args=[oficio.pk]),
            "wizard_back_label": "Voltar",
            "justificativa_ctx": apresentar_justificativa_wizard_context(oficio),
            "justificativa_obrigatoria": obrigatoria,
            "modelos_justificativa_url": reverse("justificativas:index"),
            **_wizard_footer_ctx(oficio),
        },
    )


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
            oficio.save(update_fields=["status", "updated_at"])
            messages.success(request, "Ofício finalizado com sucesso.")
            return redirect("oficios:index")
        if nav_action == "wizard_back":
            from documentos.services.warm_cache import ensure_document_artifact_cached

            ensure_document_artifact_cached(oficio)
            messages.info(request, "Retornando à etapa anterior.")
            return redirect("oficios:wizard_justificativa", pk=pk)
        if nav_action == "save_draft_list":
            messages.success(request, "Retornamos à lista de ofícios.")
            return redirect("oficios:index")
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
                assinaturas_status=doc_status,
            ),
            "wizard_summary": apresentar_oficio_wizard_summary(oficio),
            "oficio": oficio,
            "wizard_back_url": reverse("oficios:wizard_justificativa", args=[oficio.pk]),
            "wizard_back_label": "Voltar",
            "wizard_finalizar": True,
            "documentos_ctx": apresentar_oficio_wizard_documentos_context(oficio),
            "pendencias_documentos": pendencias,
            "mostrar_pendencias": bool(pendencias),
            **_wizard_footer_ctx(oficio),
        },
    )


def wizard_resumo(request, pk):
    """Compatibilidade: `/resumo/` é alias da etapa 5 — mesmo conteúdo de `wizard_documentos`."""
    return wizard_documentos(request, pk)


def wizard_assinaturas_redirect_assinar(request, pk):
    """Alias de URL legada `/oficios/<pk>/assinar/` → etapa 6."""
    return redirect(reverse("oficios:wizard_assinaturas", args=[pk]))


def wizard_assinaturas_documentos(request, pk):
    oficio = get_oficio_by_id(pk)
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        messages.error(
            request,
            "Assinatura digital requer DOCUMENTOS_PERSIST_ARTEFATOS=true no ambiente.",
        )
        return redirect(reverse("oficios:wizard_documentos", args=[pk]))

    if request.method == "POST":
        if (request.POST.get("gerar_solicitacao") or "").strip() != "1":
            messages.error(request, "Ação inválida.")
            return redirect(reverse("oficios:wizard_assinaturas", args=[pk]))
        return wizard_assinaturas_post_gerar_solicitacao(request, oficio)

    central_ctx = build_documentos_assinatura_central(oficio, request=request)
    aval_doc = validar_oficio_para_documento(oficio)
    doc_status = "complete" if aval_doc["status"] == "complete" else "incomplete"
    dados_av = avaliar_oficio_dados_viajantes(oficio=oficio)
    transp_av = avaliar_oficio_transporte(oficio)
    roteiro_av = _wizard_roteiro_step_status(oficio)

    return render(
        request,
        "oficios/wizard_assinaturas.html",
        {
            "page_title": "Central de assinaturas",
            **_wizard_shell_ctx(
                oficio=oficio,
                etapa_atual="assinaturas",
                dados_viajantes_status=dados_av["status"],
                transporte_status=transp_av["status"],
                roteiro_status=roteiro_av,
                documentos_status=doc_status,
                assinaturas_status=doc_status,
            ),
            "wizard_summary": apresentar_oficio_wizard_summary(oficio),
            "oficio": oficio,
            "wizard_use_outer_form": False,
            "wizard_back_url": reverse("oficios:wizard_documentos", args=[oficio.pk]),
            "wizard_back_label": "Voltar para documentos",
            "documentos_assinatura": central_ctx["documentos_assinatura"],
            "assinaturas_kpis": central_ctx["assinaturas_kpis"],
        },
    )


def wizard_assinar_pdf_oficio(request, pk):
    """Legado: GET/POST redirecionam para a etapa 6 (assinatura só via solicitação)."""
    if request.method == "GET":
        return redirect(reverse("oficios:wizard_assinaturas", args=[pk]))
    messages.info(
        request,
        "A assinatura direta neste URL foi descontinuada. Use «Gerar solicitação» na etapa de assinaturas.",
    )
    return redirect(reverse("oficios:wizard_assinaturas", args=[pk]))


@require_GET
def wizard_verificar_pdf_oficio(request, pk):
    oficio = get_oficio_by_id(pk)
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        return JsonResponse(
            {"ok": False, "reason": "persist_disabled", "detail": "DOCUMENTOS_PERSIST_ARTEFATOS está desligado."},
            status=422,
        )
    aval = validar_oficio_para_documento(oficio)
    if aval.get("pendencias"):
        raise Http404()
    art = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.OFICIO.value)
    if art is None or not pdf_artefato_original_acessivel(art):
        try:
            gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF)
        except Exception as exc:  # noqa: BLE001
            return JsonResponse({"ok": False, "reason": "pdf_prepare_error", "detail": str(exc)}, status=422)
        art = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.OFICIO.value)
    if art is None or not pdf_artefato_original_acessivel(art):
        return JsonResponse({"ok": False, "reason": "no_file"}, status=422)
    resultado = verificar_artefato_documento(art)
    registrar_verificacao_artefato(art, resultado)
    status = 200 if resultado.get("ok") else 422
    return JsonResponse(resultado, status=status)


@require_GET
def api_viatura_por_placa(request, pk):
    """Busca viaturas por texto (`q`) ou compatível com consulta só por placa (`placa`)."""
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

    if len(q) < 2 and not equipe_ids:
        return JsonResponse({"results": []})

    encontradas = buscar_viaturas_para_oficio(q, equipe_servidor_ids=equipe_ids or None)
    return JsonResponse({"results": [viatura_para_resultado_busca(v) for v in encontradas]})


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
def plano_trabalho_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    ref = f"{oficio.numero_formatado.replace('/', '-')}-plano-trabalho"
    return _pdf_inline_response(
        request,
        oficio,
        gerar=lambda: gerar_resposta_plano_trabalho_documento(oficio, DocumentoFormato.PDF),
        tipo=DocumentoTipo.PLANO_TRABALHO,
        reference=ref,
        step_name="http_plano_trabalho_pdf_inline",
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

    avaliacao = validar_oficio_para_documento(oficio)
    if avaliacao["pendencias"]:
        messages.error(request, "Documento nao gerado porque o oficio esta incompleto.")
        alvo = redirect_para_corrigir_documento_oficio(oficio)
        return redirect(f"{alvo}?documento_incompleto=1")
    with measure_step(
        "http_baixar_justificativa_documento",
        {"oficio_id": oficio.pk, "formato": formato_documento.value},
    ):
        return download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=formato_documento,
            gerar=lambda: gerar_resposta_justificativa_documento(oficio, formato_documento),
        )


def baixar_plano_trabalho_documento(request, pk, formato):
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
        "http_baixar_plano_trabalho_documento",
        {"oficio_id": oficio.pk, "formato": formato_documento.value},
    ):
        return download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=formato_documento,
            gerar=lambda: gerar_resposta_plano_trabalho_documento(oficio, formato_documento),
        )


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
    if request.method == "POST":
        try:
            excluir_oficio(oficio)
        except OficioVinculadoError:
            messages.error(
                request,
                "Não foi possível excluir o ofício porque ele está vinculado a outros registros.",
            )
            return redirect("oficios:index")
        messages.success(request, "Ofício excluído com sucesso.")
        return redirect("oficios:index")
    return render(
        request,
        "oficios/confirm_delete.html",
        {
            "page_title": "Excluir ofício",
            "page_description": "A exclusão é física e pode ser bloqueada quando houver vínculos.",
            "object": oficio,
            "back_url": reverse("oficios:index"),
        },
    )


def modelos_motivo_index(request):
    q = request.GET.get("q", "").strip()
    modelos = listar_modelos_motivo(q=q or None, incluir_inativos=True)
    rows = [
        apresentar_linha_lista_simples_modelo_motivo(
            modelo,
            edit_url=reverse("oficios:modelo_motivo_editar", args=[modelo.pk]),
            delete_url=reverse("oficios:modelo_motivo_excluir", args=[modelo.pk]),
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
            "new_url": reverse("oficios:modelo_motivo_novo"),
        },
    )


def modelo_motivo_novo(request):
    form = ModeloMotivoOficioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        criar_modelo_motivo(form)
        messages.success(request, "Modelo de motivo criado com sucesso.")
        return redirect("oficios:modelos_motivo_index")
    return render(
        request,
        "oficios/modelos_motivo/form.html",
        {
            "page_title": "Novo modelo de motivo",
            "page_description": "Crie textos reutilizáveis para agilizar o preenchimento do motivo nos ofícios.",
            "form": form,
            "back_url": reverse("oficios:modelos_motivo_index"),
            "submit_label": "Salvar modelo",
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
    modelo = get_modelo_motivo_by_id(pk)
    form = ModeloMotivoOficioForm(request.POST or None, instance=modelo)
    if request.method == "POST" and form.is_valid():
        atualizar_modelo_motivo(modelo, form)
        messages.success(request, "Modelo de motivo atualizado com sucesso.")
        return redirect("oficios:modelos_motivo_index")
    return render(
        request,
        "oficios/modelos_motivo/form.html",
        {
            "page_title": "Editar modelo de motivo",
            "page_description": "Crie textos reutilizáveis para agilizar o preenchimento do motivo nos ofícios.",
            "form": form,
            "back_url": reverse("oficios:modelos_motivo_index"),
            "submit_label": "Salvar alterações",
        },
    )


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
