import json

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET

from cadastros.models import Servidor

from documentos.services.responses import build_inline_pdf_response
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

from oficios.selectors import get_oficio_by_id
from oficios.services import redirect_para_corrigir_documento_oficio
from oficios.services import validar_oficio_para_documento

from .services import empacotar_termos_zip
from .services import gerar_termo_lote
from .services import gerar_termo_um
from .services import listar_servidores_com_termo
from .services import preview_termo_context


def index(request):
    return render(
        request,
        "termos/index.html",
        {
            "page_title": "Termos de Autorizacao",
            "page_description": (
                "Gere termos por ofício a partir da etapa de documentos ou pelos atalhos abaixo "
                "quando o ofício estiver completo."
            ),
            "oficios_url": reverse("oficios:index"),
        },
    )


def preview_termo_oficio(request, pk):
    oficio = get_oficio_by_id(pk)
    aval = validar_oficio_para_documento(oficio)
    modo = request.GET.get("semipreenchido") == "1"
    servidor_pk = request.GET.get("servidor")
    servidor = None
    if servidor_pk:
        servidor = get_object_or_404(Servidor, pk=int(servidor_pk))
    ctx = preview_termo_context(oficio, servidor, modo_semipreenchido=modo)
    if request.GET.get("format") == "json":
        return HttpResponse(
            json.dumps(ctx, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
            content_type="application/json; charset=utf-8",
        )
    return render(
        request,
        "termos/preview.html",
        {
            "page_title": f"Preview termo — Ofício {oficio.numero_formatado}",
            "oficio": oficio,
            "preview": ctx,
            "preview_json": json.dumps(ctx, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
            "validacao": aval,
        },
    )


@require_GET
def termo_servidor_pdf_inline(request, pk, servidor_pk):
    oficio = get_oficio_by_id(pk)
    aval = validar_oficio_para_documento(oficio)
    if aval["pendencias"]:
        messages.error(request, "Termo nao gerado: oficio incompleto.")
        return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    servidor = get_object_or_404(Servidor, pk=servidor_pk)
    if not oficio.servidores.filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao participa deste oficio.")
    if not listar_servidores_com_termo(oficio).filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para Termo de Autorizacao neste oficio.")

    doc = gerar_termo_um(oficio, servidor, DocumentoFormato.PDF)
    ref = f"{oficio.numero_formatado.replace('/', '-')}-termo-{servidor.pk}"
    return build_inline_pdf_response(
        request,
        content=doc.conteudo,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        reference=ref,
        now=timezone.now(),
        x_document_sha256=doc.hash_sha256,
    )


def baixar_termo_servidor(request, pk, servidor_pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        fmt = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato nao suportado.") from exc

    aval = validar_oficio_para_documento(oficio)
    if aval["pendencias"]:
        messages.error(request, "Termo nao gerado: oficio incompleto.")
        return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    servidor = get_object_or_404(Servidor, pk=servidor_pk)
    if not oficio.servidores.filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao participa deste oficio.")
    if not listar_servidores_com_termo(oficio).filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para Termo de Autorizacao neste oficio.")

    doc = gerar_termo_um(oficio, servidor, fmt)
    response = HttpResponse(doc.conteudo, content_type=doc.content_type)
    response["Content-Disposition"] = f'attachment; filename="{doc.nome_arquivo}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = doc.hash_sha256
    return response


def baixar_termo_lote_zip(request, pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        fmt = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato nao suportado.") from exc

    aval = validar_oficio_para_documento(oficio)
    if aval["pendencias"]:
        messages.error(request, "Lote nao gerado: oficio incompleto.")
        return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    if not listar_servidores_com_termo(oficio).exists():
        messages.error(request, "Nenhum servidor selecionado para Termo de Autorizacao.")
        return redirect("termos:index")

    docs = gerar_termo_lote(oficio, fmt)
    zip_bytes = empacotar_termos_zip(docs)
    nome = f"termos_oficio_{oficio.numero_formatado.replace('/', '-')}.zip"
    response = HttpResponse(zip_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{nome}"'
    return response
