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
from django.views.decorators.http import require_http_methods

from cadastros.models import Servidor

from documentos.services.responses import build_inline_pdf_response
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

from oficios.selectors import get_oficio_by_id
from oficios.services import redirect_para_corrigir_documento_oficio
from oficios.services import validar_oficio_para_documento

from .forms import TermoAutorizacaoForm
from .models import TermoAutorizacao
from .services import empacotar_termos_zip
from .services import fundir_termos_pdf
from .services import gerar_termo_cadastro_lote
from .services import gerar_termo_lote
from .services import gerar_termo_um
from .services import listar_servidores_com_termo
from .services import preview_termo_context
from .services import sha256_bytes


def index(request):
    termos = (
        TermoAutorizacao.objects.select_related(
            "oficio",
            "destino_estado",
            "destino_cidade",
            "viatura",
        )
        .prefetch_related("servidores")
        .order_by("-created_at")
    )
    return render(
        request,
        "termos/index.html",
        {
            "page_title": "Termos de Autorizacao",
            "page_description": "Cadastre termos avulsos ou vinculados a oficios existentes.",
            "termos": termos,
            "novo_url": reverse("termos:novo"),
            "oficios_url": reverse("oficios:index"),
        },
    )


def _termo_queryset():
    return TermoAutorizacao.objects.select_related(
        "oficio",
        "oficio__roteiro",
        "destino_estado",
        "destino_cidade",
        "viatura",
    ).prefetch_related("servidores")


def _oficio_summary(oficio):
    roteiro = oficio.roteiro
    destino = ""
    periodo = ""
    if roteiro:
        destino_obj = roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "pk").first()
        destino = str(destino_obj) if destino_obj else ""
        if roteiro.saida_dt:
            inicio = roteiro.saida_dt.strftime("%d/%m/%Y")
            retorno = roteiro.retorno_chegada_dt or roteiro.retorno_saida_dt
            fim = retorno.strftime("%d/%m/%Y") if retorno else inicio
            periodo = inicio if fim == inicio else f"{inicio} a {fim}"
    return {
        "id": oficio.pk,
        "label": f"Oficio {oficio.numero_formatado}",
        "destino": destino,
        "periodo": periodo,
        "servidores": oficio.servidores_termo_autorizacao.count(),
        "viatura": str(oficio.viatura) if oficio.viatura_id else "",
    }


def _form_context(*, form, termo=None):
    oficios = form.fields["oficio"].queryset
    summaries = {}
    for oficio in oficios:
        summary = _oficio_summary(oficio)
        summaries[str(summary["id"])] = summary
    return {
        "page_title": "Cadastro de termo",
        "form": form,
        "termo": termo,
        "index_url": reverse("termos:index"),
        "servidor_create_url": reverse("cadastros:servidor_create"),
        "viatura_create_url": reverse("cadastros:viatura_create"),
        "oficios_summary": summaries,
    }


@require_http_methods(["GET", "POST"])
def novo(request):
    termo = TermoAutorizacao()
    if request.method == "POST":
        form = TermoAutorizacaoForm(request.POST, instance=termo)
        if form.is_valid():
            termo = form.save()
            messages.success(request, "Termo cadastrado.")
            if request.POST.get("action") == "save_preview":
                return redirect("termos:preview_cadastro", pk=termo.pk)
            return redirect("termos:editar", pk=termo.pk)
    else:
        form = TermoAutorizacaoForm(instance=termo)
    return render(request, "termos/form.html", _form_context(form=form, termo=None))


@require_http_methods(["GET", "POST"])
def editar(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    if request.method == "POST":
        form = TermoAutorizacaoForm(request.POST, instance=termo)
        if form.is_valid():
            termo = form.save()
            messages.success(request, "Termo atualizado.")
            if request.POST.get("action") == "save_preview":
                return redirect("termos:preview_cadastro", pk=termo.pk)
            return redirect("termos:editar", pk=termo.pk)
    else:
        form = TermoAutorizacaoForm(instance=termo)
    return render(request, "termos/form.html", _form_context(form=form, termo=termo))


def preview_cadastro(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    servidores = list(termo.servidores_efetivos())
    preview = {
        "termo": termo,
        "destino": termo.destino_display,
        "periodo": termo.periodo_display,
        "servidores": servidores,
        "viatura": termo.viatura_efetiva(),
        "oficio": termo.oficio,
    }
    if request.GET.get("format") == "json":
        data = {
            "id": termo.pk,
            "destino": preview["destino"],
            "periodo": preview["periodo"],
            "servidores": [servidor.nome for servidor in servidores],
            "viatura": str(preview["viatura"]) if preview["viatura"] else "",
            "oficio": termo.oficio.numero_formatado if termo.oficio_id else "",
        }
        return HttpResponse(
            json.dumps(data, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
            content_type="application/json; charset=utf-8",
        )
    return render(
        request,
        "termos/preview_cadastro.html",
        {
            "page_title": f"Preview termo #{termo.pk}",
            "termo": termo,
            "preview": preview,
            "editar_url": reverse("termos:editar", args=[termo.pk]),
        },
    )


def _termo_cadastro_docs_or_none(termo, formato):
    docs = gerar_termo_cadastro_lote(termo, formato)
    return docs or None


@require_GET
def termo_cadastro_pdf_inline(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    docs = _termo_cadastro_docs_or_none(termo, DocumentoFormato.PDF)
    if docs is None:
        messages.error(request, "Nenhum termo gerado.")
        return redirect("termos:editar", pk=termo.pk)
    content = docs[0].conteudo if len(docs) == 1 else fundir_termos_pdf(docs)
    return build_inline_pdf_response(
        request,
        content=content,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        reference=f"termo-{termo.pk}",
        now=timezone.now(),
        x_document_sha256=sha256_bytes(content),
    )


@require_GET
def baixar_termo_cadastro_pdf(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    docs = _termo_cadastro_docs_or_none(termo, DocumentoFormato.PDF)
    if docs is None:
        messages.error(request, "Nenhum termo gerado.")
        return redirect("termos:editar", pk=termo.pk)
    content = docs[0].conteudo if len(docs) == 1 else fundir_termos_pdf(docs)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="termo_{termo.pk}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = sha256_bytes(content)
    return response


@require_GET
def baixar_termo_cadastro_docx(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    docs = _termo_cadastro_docs_or_none(termo, DocumentoFormato.DOCX)
    if docs is None:
        messages.error(request, "Nenhum termo gerado.")
        return redirect("termos:editar", pk=termo.pk)
    if len(docs) == 1:
        doc = docs[0]
        response = HttpResponse(doc.conteudo, content_type=doc.content_type)
        response["Content-Disposition"] = f'attachment; filename="{doc.nome_arquivo}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Document-SHA256"] = doc.hash_sha256
        return response
    zip_bytes = empacotar_termos_zip(docs)
    response = HttpResponse(zip_bytes, content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="termo_{termo.pk}_docx.zip"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = sha256_bytes(zip_bytes)
    return response


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
            "page_title": f"Preview termo - Oficio {oficio.numero_formatado}",
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


def baixar_termos_todos_pdf(request, pk):
    oficio = get_oficio_by_id(pk)
    aval = validar_oficio_para_documento(oficio)
    if aval["pendencias"]:
        messages.error(request, "Termos nao gerados: oficio incompleto.")
        return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    if not listar_servidores_com_termo(oficio).exists():
        messages.error(request, "Nenhum servidor selecionado para Termo de Autorizacao.")
        return redirect("termos:index")

    docs = gerar_termo_lote(oficio, DocumentoFormato.PDF)
    pdf_bytes = fundir_termos_pdf(docs)
    nome = f"termos_oficio_{oficio.numero_formatado.replace('/', '-')}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{nome}"'
    response["X-Content-Type-Options"] = "nosniff"
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
