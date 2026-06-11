import json

from datetime import datetime

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
    data_inicio = ""
    data_fim = ""
    estado_id = ""
    cidade_id = ""
    if roteiro:
        destino_obj = roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "pk").first()
        destino = str(destino_obj) if destino_obj else ""
        if destino_obj:
            estado_id = destino_obj.estado_id or ""
            cidade_id = destino_obj.cidade_id or ""
        if roteiro.saida_dt:
            inicio = roteiro.saida_dt.strftime("%d/%m/%Y")
            data_inicio = roteiro.saida_dt.date().isoformat()
            retorno = roteiro.retorno_chegada_dt or roteiro.retorno_saida_dt
            fim = retorno.strftime("%d/%m/%Y") if retorno else inicio
            data_fim = retorno.date().isoformat() if retorno else data_inicio
            periodo = inicio if fim == inicio else f"{inicio} a {fim}"
    servidor_ids = [s.pk for s in oficio.servidores_termo_autorizacao.all()]
    viatura_id = oficio.viatura_id or ""
    return {
        "id": oficio.pk,
        "label": f"Oficio {oficio.numero_formatado}",
        "numero": oficio.numero_formatado,
        "protocolo": oficio.protocolo or "",
        "destino": destino,
        "periodo": periodo,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "estado_id": estado_id,
        "cidade_id": cidade_id,
        "servidor_ids": servidor_ids,
        "viatura_id": viatura_id,
        "servidores": len(servidor_ids),
        "viatura": str(oficio.viatura) if viatura_id else "",
        "search_text": " ".join(
            part
            for part in [
                oficio.numero_formatado,
                oficio.protocolo or "",
                destino,
                periodo,
                oficio.assunto or "",
            ]
            if part
        ),
    }


def _termo_evento_selected_dates_json(form):
    def as_iso(value):
        if not value:
            return ""
        if hasattr(value, "isoformat"):
            return value.isoformat()
        value = str(value).strip()
        if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
            return value
        return ""

    if form.is_bound:
        inicio = as_iso(form.data.get("data_evento_inicio"))
        fim = as_iso(form.data.get("data_evento_fim"))
    else:
        inicio = as_iso(getattr(form.instance, "data_evento_inicio", None))
        fim = as_iso(getattr(form.instance, "data_evento_fim", None))

    if not inicio and not fim:
        return "[]"
    if inicio and not fim:
        return json.dumps([inicio], cls=DjangoJSONEncoder)
    if fim and not inicio:
        return json.dumps([fim], cls=DjangoJSONEncoder)
    if inicio == fim:
        return json.dumps([inicio], cls=DjangoJSONEncoder)
    return json.dumps([inicio, fim], cls=DjangoJSONEncoder)


def _termo_evento_display_values(form):
    def as_display(value):
        if not value:
            return ""
        if hasattr(value, "strftime"):
            return value.strftime("%d/%m/%Y")
        value = str(value).strip()
        if len(value) == 10 and value[4:5] == "-" and value[7:8] == "-":
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return value
            return parsed.strftime("%d/%m/%Y")
        return value

    if form.is_bound:
        return {
            "inicio": as_display(form.data.get("data_evento_inicio")),
            "fim": as_display(form.data.get("data_evento_fim")),
        }
    return {
        "inicio": as_display(getattr(form.instance, "data_evento_inicio", None)),
        "fim": as_display(getattr(form.instance, "data_evento_fim", None)),
    }


def _termo_page_steps(form, termo=None):
    oficio_val = None
    servidores_val = []
    viatura_val = None
    if form.is_bound:
        oficio_val = form.data.get("oficio") or None
        servidores_val = form.data.getlist("servidores") if hasattr(form.data, "getlist") else []
        viatura_val = form.data.get("viatura") or None
    elif termo and termo.pk:
        oficio_val = termo.oficio_id
        servidores_val = list(termo.servidores.values_list("pk", flat=True))
        viatura_val = termo.viatura_id

    return [
        {
            "marker": "1",
            "step_label": "OFÍCIO",
            "title": "Oficio vinculado",
            "status": "Opcional",
            "url": "#termo-card-oficio",
            "state_class": "is-complete" if oficio_val else "",
        },
        {
            "marker": "2",
            "step_label": "EVENTO",
            "title": "Evento",
            "status": "Obrigatório",
            "url": "#termo-card-evento",
            "state_class": "is-current",
            "aria_current": "step",
        },
        {
            "marker": "3",
            "step_label": "SERVIDORES",
            "title": "Servidores",
            "status": "Opcional",
            "url": "#termo-card-servidores",
            "state_class": "is-complete" if servidores_val else "",
        },
        {
            "marker": "4",
            "step_label": "VIATURA",
            "title": "Viatura",
            "status": "Opcional",
            "url": "#termo-card-viatura",
            "state_class": "is-complete" if viatura_val else "",
        },
        {
            "marker": "5",
            "step_label": "REVISÃO",
            "title": "Salvar termo",
            "status": "Acoes finais",
            "url": "#termo-form-footer",
        },
    ]


def _form_context(*, form, termo=None):
    oficios = form.fields["oficio"].queryset.prefetch_related("servidores_termo_autorizacao")
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
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "oficios_summary": summaries,
        "termo_page_steps": _termo_page_steps(form, termo=termo),
        "termo_evento_selected_dates_json": _termo_evento_selected_dates_json(form),
        "termo_evento_display": _termo_evento_display_values(form),
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
