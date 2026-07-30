from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.core.signing import BadSignature
from django.core.signing import SignatureExpired
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST

from core.retorno import voltar_para
from core.tenancy import filter_queryset_by_area

from .models import DocumentoArtefato
from .services.async_generation import geracao_resultado as _geracao_resultado
from .services.async_generation import geracao_status as _geracao_status
from .services import default_document_registry
from .services.access import artefato_pdf_download_filename
from .services.access import build_pdf_http_response_for_artefato
from .services.access import ensure_request_may_view_artefato_pdf
from .services.access import select_artefato_pdf_fieldfile
from .services.exceptions import ArquivoAssinadoInvalido
from .services.persistence import anexar_arquivo_assinado
from .services.persistence import remover_arquivo_assinado
from .services.temporary_links import build_artefato_pdf_public_conteudo_url
from .services.temporary_links import create_artefato_pdf_temp_token
from .services.temporary_links import parse_artefato_pdf_temp_token


def index(request):
    document_types = default_document_registry.all()
    available_count = sum(1 for item in document_types if item.formatos_permitidos)
    return render(
        request,
        "documentos/index.html",
        {
            "page_title": "Documentos",
            "page_description": (
                "Nucleo documental ativo: tipos, contratos de validacao, nomes de arquivo e "
                "renderers seguros para evolucao dos modulos de dominio."
            ),
            "core_status": "Núcleo base disponível",
            "core_types_total": len(document_types),
            "core_types_with_format": available_count,
        },
    )


@require_GET
def geracao_status(request, pk):
    return _geracao_status(request, pk)


@require_GET
def geracao_resultado(request, pk):
    return _geracao_resultado(request, pk)


@require_GET
def artefato_pdf_conteudo(request, pk):
    artefato = get_object_or_404(filter_queryset_by_area(DocumentoArtefato.objects), pk=pk)
    ensure_request_may_view_artefato_pdf(request, artefato)
    return build_pdf_http_response_for_artefato(request, artefato)


@login_not_required
@require_GET
def artefato_pdf_conteudo_publico(request):
    token = (request.GET.get("t") or "").strip()
    if not token:
        raise Http404()
    try:
        payload = parse_artefato_pdf_temp_token(token)
    except (BadSignature, SignatureExpired):
        raise Http404()
    pk = payload.get("pk")
    if not pk:
        raise Http404()
    artefato = get_object_or_404(DocumentoArtefato, pk=pk, formato="pdf")
    return build_pdf_http_response_for_artefato(request, artefato)


@require_GET
def artefato_pdf_visualizar(request, pk):
    artefato = get_object_or_404(filter_queryset_by_area(DocumentoArtefato.objects), pk=pk)
    ensure_request_may_view_artefato_pdf(request, artefato)
    if select_artefato_pdf_fieldfile(artefato) is None:
        raise Http404("Ficheiro PDF não disponível.")
    nome = artefato_pdf_download_filename(artefato)
    conteudo_url = reverse("documentos:artefato_pdf_conteudo", args=[artefato.pk])
    share_url = ""
    if getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        tok = create_artefato_pdf_temp_token(str(artefato.pk))
        share_url = request.build_absolute_uri(build_artefato_pdf_public_conteudo_url(tok))
    worker_src = static("vendor/pdfjs/pdf.worker.min.js")
    return render(
        request,
        "documentos/pdf_viewer.html",
        {
            "page_title": f"PDF — {nome}",
            "pdf_conteudo_url": conteudo_url,
            "pdf_filename": nome,
            "pdf_js_worker_src": worker_src,
            "share_temporario_url": share_url,
        },
    )




def _artefato_fallback_url(artefato: DocumentoArtefato) -> str:
    """Para onde voltar quando não há ``next``: a tela "dona" do documento.

    ``termo_id`` primeiro: um termo avulso pode ter ``oficio_id`` preenchido
    (vinculado só para fins de nome no Drive), mas a tela relevante pra quem
    anexou/removeu o assinado é a do cadastro do termo, não o wizard do ofício.
    """
    if artefato.termo_id:
        return reverse("termos:editar", args=[artefato.termo_id])
    if artefato.oficio_id:
        return reverse("oficios:wizard_documentos", args=[artefato.oficio_id])
    return reverse("documentos:index")


@require_POST
def artefato_assinado_anexar(request, pk):
    artefato = get_object_or_404(filter_queryset_by_area(DocumentoArtefato.objects), pk=pk)
    ensure_request_may_view_artefato_pdf(request, artefato)
    fallback = _artefato_fallback_url(artefato)
    upload = request.FILES.get("arquivo")
    if not upload:
        messages.error(request, "Selecione um arquivo PDF para anexar.")
        return redirect(voltar_para(request, fallback))
    try:
        anexar_arquivo_assinado(artefato, upload)
    except ArquivoAssinadoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(voltar_para(request, fallback))
    from integracoes.google_drive.services import agendar_sincronizacao_assinatura_manual

    agendar_sincronizacao_assinatura_manual(artefato, usuario=request.user)
    messages.success(request, "Documento assinado anexado.")
    return redirect(voltar_para(request, fallback))


@require_POST
def artefato_assinado_remover(request, pk):
    artefato = get_object_or_404(filter_queryset_by_area(DocumentoArtefato.objects), pk=pk)
    ensure_request_may_view_artefato_pdf(request, artefato)
    fallback = _artefato_fallback_url(artefato)
    remover_arquivo_assinado(artefato)
    from integracoes.google_drive.services import agendar_sincronizacao_assinatura_manual

    agendar_sincronizacao_assinatura_manual(artefato, usuario=request.user)
    messages.success(request, "Documento assinado removido.")
    return redirect(voltar_para(request, fallback))
