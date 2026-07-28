"""Endpoints de visualização e download de documentos de ofício."""

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

from documentos.services.downloads import download_documento_or_redirect_pdf_error
from documentos.services.responses import build_inline_pdf_response_from_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from ordens_servico.services import gerar_resposta_ordem_servico_documento

from .selectors import get_oficio_by_id
from .services import gerar_resposta_documento_oficio
from .services import gerar_resposta_justificativa_documento
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
    gerar,
    tipo: DocumentoTipo,
    reference: str,
    step_name: str,
):
    bloqueio = _redirect_se_oficio_documento_incompleto(request, oficio)
    if bloqueio is not None:
        return bloqueio
    with measure_step(step_name, {"oficio_id": oficio.pk}):
        response = download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=DocumentoFormato.PDF,
            gerar=gerar,
        )
    if getattr(response, "status_code", 200) in (301, 302, 303, 307, 308):
        return response
    return build_inline_pdf_response_from_download_response(
        request,
        response,
        tipo=tipo,
        reference=reference,
        now=timezone.now(),
    )


@require_GET
def oficio_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    reference = oficio.numero_formatado.replace("/", "-")
    return _pdf_inline_response(
        request,
        oficio,
        gerar=lambda: gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF),
        tipo=DocumentoTipo.OFICIO,
        reference=reference,
        step_name="http_oficio_pdf_inline",
    )


@require_GET
def justificativa_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    reference = f"{oficio.numero_formatado.replace('/', '-')}-justificativa"
    return _pdf_inline_response(
        request,
        oficio,
        gerar=lambda: gerar_resposta_justificativa_documento(
            oficio,
            DocumentoFormato.PDF,
        ),
        tipo=DocumentoTipo.JUSTIFICATIVA,
        reference=reference,
        step_name="http_justificativa_pdf_inline",
    )


@require_GET
def ordem_servico_pdf_inline(request, pk):
    oficio = get_oficio_by_id(pk)
    reference = f"{oficio.numero_formatado.replace('/', '-')}-ordem-servico"
    return _pdf_inline_response(
        request,
        oficio,
        gerar=lambda: gerar_resposta_ordem_servico_documento(
            oficio,
            DocumentoFormato.PDF,
        ),
        tipo=DocumentoTipo.ORDEM_SERVICO,
        reference=reference,
        step_name="http_ordem_servico_pdf_inline",
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
    with measure_step(
        "http_baixar_documento",
        {"oficio_id": oficio.pk, "formato": document_format.value},
    ):
        return download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=document_format,
            gerar=lambda: gerar_resposta_documento_oficio(oficio, document_format),
        )


def baixar_justificativa_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        document_format = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    with measure_step(
        "http_baixar_justificativa_documento",
        {"oficio_id": oficio.pk, "formato": document_format.value},
    ):
        response = download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=document_format,
            gerar=lambda: gerar_resposta_justificativa_documento(
                oficio,
                document_format,
            ),
        )
    disposition = response.get("Content-Disposition", "") if hasattr(response, "headers") else ""
    if disposition.startswith("attachment"):
        extension = "pdf" if document_format == DocumentoFormato.PDF else "docx"
        safe_number = oficio.numero_formatado.replace("/", "-")
        response["Content-Disposition"] = (
            f'attachment; filename="Justificativa {safe_number}.{extension}"'
        )
    return response


def baixar_ordem_servico_documento(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        document_format = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato documental nao suportado.") from exc

    incomplete = _redirect_se_oficio_documento_incompleto(request, oficio)
    if incomplete is not None:
        return incomplete
    with measure_step(
        "http_baixar_ordem_servico_documento",
        {"oficio_id": oficio.pk, "formato": document_format.value},
    ):
        return download_documento_or_redirect_pdf_error(
            request,
            oficio_id=oficio.pk,
            formato=document_format,
            gerar=lambda: gerar_resposta_ordem_servico_documento(
                oficio,
                document_format,
            ),
        )
