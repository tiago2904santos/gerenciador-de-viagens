import logging
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.autosave import AutosavePayloadError
from core.autosave import autosave_json_response
from core.autosave import filter_allowed_fields
from core.autosave import parse_autosave_payload
from justificativas.forms import JustificativaOficioForm
from justificativas.presenters import apresentar_justificativa_wizard_context
from justificativas.services import atualizar_justificativa_oficio
from justificativas.services import get_or_create_justificativa_oficio
from justificativas.services import oficio_exige_justificativa
from .models import Oficio
from .presenters import apresentar_oficio_wizard_documentos_context
from .presenters import apresentar_oficio_wizard_summary
from .selectors import get_oficio_by_id
from .services import avaliar_oficio_dados_viajantes
from .services import avaliar_oficio_transporte
from .services import validar_oficio_para_documento
from .view_navigation import oficio_back_label as _oficio_back_label
from .view_navigation import oficio_back_url as _oficio_back_url
from .view_navigation import url_with_next as _url_with_next
from core.wizard import normalizar_acao_do_wizard

from .view_helpers import _redirect_lista_oficio, _wizard_footer_ctx, _wizard_shell_ctx, _wizard_roteiro_step_status, _merge_payload_fields, _oficio_autosave_version, _justificativa_autosave_data, _autosave_form_errors


def wizard_justificativa(request, pk):
    oficio = get_oficio_by_id(pk)
    obrigatoria = oficio_exige_justificativa(oficio)
    inst = get_or_create_justificativa_oficio(oficio)
    bypass_texto_obrigatorio = False
    if request.method == "POST":
        raw_action = (
            request.POST.get("wizard_action") or request.POST.get("action") or ""
        ).strip()
        if raw_action in ("wizard_back", "save_draft_list"):
            bypass_texto_obrigatorio = True
    form = JustificativaOficioForm(
        request.POST or None,
        instance=inst,
        obrigatoria=bool(obrigatoria and not bypass_texto_obrigatorio),
    )

    if request.method == "POST" and form.is_valid():
        nav_action = normalizar_acao_do_wizard(request.POST)
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
        nav_action = normalizar_acao_do_wizard(request.POST, default="save_draft")

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
