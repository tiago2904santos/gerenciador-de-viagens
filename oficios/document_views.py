"""Endpoints de visualização e download de documentos de ofício."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_GET

from documentos.services.async_generation import enfileirar_documento
from documentos.services.types import DocumentoFormato

from .selectors import get_oficio_by_id
from .services import redirect_para_corrigir_documento_oficio
from .services import validar_oficio_para_documento


def _redirect_se_oficio_documento_incompleto(request, oficio):
    avaliacao = validar_oficio_para_documento(oficio)
    if avaliacao["pendencias"]:
        messages.error(request, "Documento nao gerado porque o oficio esta incompleto.")
        alvo = redirect_para_corrigir_documento_oficio(oficio)
        return redirect(f"{alvo}?documento_incompleto=1")
    return None


def _pdf_inline_response(
    request,
    oficio,
    *,
    tipo_job: str,
):
    bloqueio = _redirect_se_oficio_documento_incompleto(request, oficio)
    if bloqueio is not None:
        return bloqueio
    return enfileirar_documento(
        request,
        tipo=tipo_job,
        parametros={"object_id": oficio.pk, "formato": DocumentoFormato.PDF.value},
        disposicao="inline",
    )


@require_GET
def oficio_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    return _pdf_inline_response(
        request,
        oficio,
        tipo_job="oficio",
    )


@require_GET
def justificativa_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    return _pdf_inline_response(
        request,
        oficio,
        tipo_job="justificativa",
    )


@require_GET
def ordem_servico_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    return _pdf_inline_response(
        request,
        oficio,
        tipo_job="ordem_servico_oficio",
    )


def baixar_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        document_format = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    incomplete = _redirect_se_oficio_documento_incompleto(request, oficio)
    if incomplete is not None:
        return incomplete
    return enfileirar_documento(
        request,
        tipo="oficio",
        parametros={"object_id": oficio.pk, "formato": document_format.value},
    )


def baixar_justificativa_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        document_format = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    return enfileirar_documento(
        request,
        tipo="justificativa",
        parametros={"object_id": oficio.pk, "formato": document_format.value},
    )


def baixar_ordem_servico_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        document_format = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    incomplete = _redirect_se_oficio_documento_incompleto(request, oficio)
    if incomplete is not None:
        return incomplete
    return enfileirar_documento(
        request,
        tipo="ordem_servico_oficio",
        parametros={"object_id": oficio.pk, "formato": document_format.value},
    )
