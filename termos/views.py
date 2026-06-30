import json
import re

from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
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
from eventos.services import build_evento_document_seed
from eventos.services import resolve_evento_from_request

from oficios.selectors import get_oficio_by_id
from oficios.services import redirect_para_corrigir_documento_oficio
from oficios.services import validar_oficio_para_documento

from .forms import TermoAutorizacaoForm
from .models import TermoAutorizacao
from .presenters import apresentar_linha_lista_simples_termo
from .services import empacotar_termos_zip
from .services import fundir_termos_pdf
from .services import gerar_termo_cadastro_lote
from .services import gerar_termo_cadastro_um
from .services import gerar_termo_lote
from .services import gerar_termo_um
from .services import listar_servidores_com_termo
from .services import preview_termo_context
from .services import sha256_bytes


TERMOS_PER_PAGE = 15


def index(request):
    q = request.GET.get("q", "").strip()
    q_digits = _digits(q)
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
    if q:
        query = (
            Q(destino_cidade__nome__icontains=q)
            | Q(destino_cidade__uf__icontains=q)
            | Q(destino_estado__nome__icontains=q)
            | Q(destino_estado__sigla__icontains=q)
            | Q(oficio__numero__icontains=q)
            | Q(oficio__protocolo__icontains=q)
            | Q(oficio__servidores__nome__icontains=q)
            | Q(oficio__servidores_termo_autorizacao__nome__icontains=q)
            | Q(servidores__nome__icontains=q)
            | Q(viatura__placa__icontains=q)
            | Q(viatura__modelo__icontains=q)
            | Q(oficio__viatura__placa__icontains=q)
            | Q(oficio__viatura__modelo__icontains=q)
        )
        if q_digits:
            query |= Q(oficio__protocolo__icontains=q_digits) | Q(oficio__numero__icontains=q_digits)
        termos = termos.filter(query).distinct()
    paginator = Paginator(termos, TERMOS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    rows = [
        apresentar_linha_lista_simples_termo(
            termo,
            edit_url=reverse("termos:editar", args=[termo.pk]),
            delete_url=reverse("termos:excluir", args=[termo.pk]),
            delete_modal=True,
            pdf_url=reverse("termos:baixar_termo_cadastro_pdf", args=[termo.pk]),
            docx_url=reverse("termos:baixar_termo_cadastro_docx", args=[termo.pk]),
        )
        for termo in page_obj.object_list
    ]
    return render(
        request,
        "termos/index.html",
        {
            "page_title": "Termos de Autorizacao",
            "page_description": "Cadastre termos avulsos ou vinculados a oficios existentes.",
            "rows": rows,
            "q": q,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({"q": q}) if q else "",
            "novo_url": reverse("termos:novo"),
            "oficios_url": reverse("oficios:index"),
        },
    )


def _pagination_pages(page_obj, *, on_each_side=1, on_ends=1):
    return [
        page_number if isinstance(page_number, int) else "..."
        for page_number in page_obj.paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=on_each_side,
            on_ends=on_ends,
        )
    ]


def _termo_queryset():
    return TermoAutorizacao.objects.select_related(
        "oficio",
        "oficio__roteiro",
        "destino_estado",
        "destino_cidade",
        "viatura",
    ).prefetch_related("servidores")


def _evento_etapa_url(evento_id):
    if evento_id:
        return reverse("eventos:guiado_etapa", kwargs={"pk": evento_id, "etapa": 5})
    return ""


def _termo_evento_id(termo=None, evento=None):
    """Resolve o evento_id de um termo, incluindo via oficio vinculado."""
    evento_id = getattr(evento, "pk", None) or getattr(termo, "evento_id", None)
    if not evento_id and termo and getattr(termo, "oficio_id", None):
        evento_id = getattr(termo.oficio, "evento_id", None)
    return evento_id


def _termo_lista_url(termo=None, evento=None):
    return _evento_etapa_url(_termo_evento_id(termo=termo, evento=evento)) or reverse("termos:index")


def _termo_back_label(termo=None, evento=None):
    return "Dados do evento" if _termo_evento_id(termo=termo, evento=evento) else "Voltar a lista"


def _redirect_termo_lista(termo):
    evento_id = _termo_evento_id(termo=termo)
    if evento_id:
        return redirect("eventos:guiado_etapa", pk=evento_id, etapa=5)
    return redirect("termos:index")


def _cadastro_create_url(create_url_name, next_url):
    return f"{reverse(create_url_name)}?{urlencode({'next': next_url})}"


def _digits(value):
    return re.sub(r"\D", "", str(value or ""))


def _oficio_summary(oficio):
    roteiro = oficio.roteiro
    destino = ""
    roteiro_label = ""
    periodo = ""
    data_inicio = ""
    data_fim = ""
    sede = ""
    estado_id = ""
    cidade_id = ""
    if roteiro:
        sede_obj = roteiro.origem_cidade or roteiro.origem_estado
        sede = str(sede_obj) if sede_obj else ""
        destinos = list(roteiro.destinos.select_related("cidade", "estado").order_by("ordem", "pk"))
        destino_obj = destinos[0] if destinos else None
        destino = str(destino_obj) if destino_obj else ""
        destinos_label = ", ".join(str(item) for item in destinos if item)
        roteiro_label = " -> ".join(part for part in [sede, destinos_label or destino] if part)
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
    servidores_termo = list(oficio.servidores_termo_autorizacao.all())
    servidores_oficio = list(oficio.servidores.all())
    servidor_ids = [s.pk for s in servidores_termo]
    servidores_nomes = []
    seen_servidores = set()
    for servidor in servidores_termo + servidores_oficio:
        if servidor.pk in seen_servidores:
            continue
        seen_servidores.add(servidor.pk)
        servidores_nomes.append(servidor.nome)
    viatura_id = oficio.viatura_id or ""
    viatura = str(oficio.viatura) if viatura_id else ""
    viatura_modelo = getattr(oficio.viatura, "modelo", "") if viatura_id else ""
    return {
        "id": oficio.pk,
        "label": f"Oficio {oficio.numero_formatado}",
        "numero": oficio.numero_formatado,
        "numero_busca": " ".join(
            part
            for part in [
                str(oficio.numero or ""),
                f"{oficio.numero:02d}" if oficio.numero else "",
                str(oficio.ano or ""),
                _digits(oficio.numero_formatado),
            ]
            if part
        ),
        "protocolo": oficio.protocolo or "",
        "protocolo_busca": _digits(oficio.protocolo),
        "sede": sede,
        "destino": destino,
        "roteiro": roteiro_label,
        "periodo": periodo,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "estado_id": estado_id,
        "cidade_id": cidade_id,
        "servidor_ids": servidor_ids,
        "viatura_id": viatura_id,
        "servidores": len(servidor_ids),
        "servidores_nomes": servidores_nomes,
        "servidores_label": ", ".join(servidores_nomes),
        "viatura": viatura,
        "viatura_modelo": viatura_modelo,
        "search_text": " ".join(
            part
            for part in [
                oficio.numero_formatado,
                str(oficio.numero or ""),
                f"{oficio.numero:02d}" if oficio.numero else "",
                str(oficio.ano or ""),
                _digits(oficio.numero_formatado),
                oficio.protocolo or "",
                _digits(oficio.protocolo),
                sede,
                destino,
                roteiro_label,
                periodo,
                viatura,
                viatura_modelo,
                " ".join(servidores_nomes),
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


def _termo_preview_documents(termo):
    if not termo or not termo.pk:
        return {}
    servidores = list(termo.servidores_efetivos())
    return {
        "generico": {
            "titulo": "Termo generico",
            "inline_url": reverse("termos:termo_cadastro_generico_pdf_inline", args=[termo.pk]),
        },
        "servidores": [
            {
                "id": servidor.pk,
                "titulo": f"Termo - {servidor.nome}",
                "servidor_nome": servidor.nome,
                "inline_url": reverse("termos:termo_cadastro_servidor_pdf_inline", args=[termo.pk, servidor.pk]),
            }
            for servidor in servidores
        ],
    }


def _form_context(*, request, form, termo=None, evento=None):
    next_url = request.get_full_path()
    oficios = (
        form.fields["oficio"]
        .queryset.select_related(
            "roteiro__origem_cidade",
            "roteiro__origem_estado",
            "viatura",
            "viatura__combustivel",
            "viatura__unidade",
        )
        .prefetch_related(
            "roteiro__destinos",
            "roteiro__destinos__cidade",
            "roteiro__destinos__estado",
            "servidores",
            "servidores__cargo",
            "servidores__unidade",
            "servidores_termo_autorizacao",
            "servidores_termo_autorizacao__cargo",
            "servidores_termo_autorizacao__unidade",
        )
    )
    summaries = {}
    for oficio in oficios:
        summary = _oficio_summary(oficio)
        summaries[str(summary["id"])] = summary
    return {
        "page_title": "Cadastro de termo",
        "form": form,
        "termo": termo,
        "index_url": _termo_lista_url(termo=termo, evento=evento),
        "back_label": _termo_back_label(termo=termo, evento=evento),
        "servidor_create_url": _cadastro_create_url("cadastros:servidor_create", next_url),
        "viatura_create_url": _cadastro_create_url("cadastros:viatura_create", next_url),
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "oficios_summary": summaries,
        "termo_preview_documents": _termo_preview_documents(termo),
        "termo_page_steps": _termo_page_steps(form, termo=termo),
        "termo_evento_selected_dates_json": _termo_evento_selected_dates_json(form),
        "termo_evento_display": _termo_evento_display_values(form),
    }


@require_http_methods(["GET", "POST"])
def novo(request):
    evento = resolve_evento_from_request(request)
    seed = build_evento_document_seed(evento) if evento is not None else {}
    termo = TermoAutorizacao(
        evento=evento,
        oficio=seed.get("oficio"),
        destino_estado=seed.get("estado"),
        destino_cidade=seed.get("cidade"),
        data_evento_inicio=seed.get("data_inicio"),
        data_evento_fim=seed.get("data_fim") or seed.get("data_inicio"),
        viatura=seed.get("viatura"),
    )
    servidores_seed = seed.get("servidores_termo") or seed.get("servidores") or []
    initial = {}
    if seed.get("oficio"):
        initial["oficio"] = seed["oficio"].pk
    if seed.get("estado"):
        initial["destino_estado"] = seed["estado"].pk
    if seed.get("cidade"):
        initial["destino_cidade"] = seed["cidade"].pk
    if servidores_seed:
        initial["servidores"] = [servidor.pk for servidor in servidores_seed]
    if seed.get("viatura"):
        initial["viatura"] = seed["viatura"].pk
    if request.method == "POST":
        form = TermoAutorizacaoForm(request.POST, instance=termo)
        if form.is_valid():
            termo = form.save()
            messages.success(request, "Termo cadastrado.")
            return _redirect_termo_lista(termo)
    else:
        form = TermoAutorizacaoForm(instance=termo, initial=initial)
    return render(request, "termos/form.html", _form_context(request=request, form=form, termo=None, evento=evento))


@require_http_methods(["GET", "POST"])
def editar(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    if request.method == "POST":
        form = TermoAutorizacaoForm(request.POST, instance=termo)
        if form.is_valid():
            termo = form.save()
            messages.success(request, "Termo atualizado.")
            return _redirect_termo_lista(termo)
    else:
        form = TermoAutorizacaoForm(instance=termo)
    return render(request, "termos/form.html", _form_context(request=request, form=form, termo=termo))


@require_http_methods(["POST"])
def excluir(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    termo.delete()
    messages.success(request, "Termo excluido.")
    return redirect("termos:index")


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
def termo_cadastro_generico_pdf_inline(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    doc = gerar_termo_cadastro_um(termo, None, DocumentoFormato.PDF)
    return build_inline_pdf_response(
        request,
        content=doc.conteudo,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        reference=f"termo-{termo.pk}-generico",
        now=timezone.now(),
        x_document_sha256=doc.hash_sha256,
    )


@require_GET
def termo_cadastro_servidor_pdf_inline(request, pk, servidor_pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    servidor = get_object_or_404(Servidor, pk=servidor_pk)
    if not termo.servidores_efetivos().filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para este termo.")
    doc = gerar_termo_cadastro_um(termo, servidor, DocumentoFormato.PDF)
    return build_inline_pdf_response(
        request,
        content=doc.conteudo,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        reference=f"termo-{termo.pk}-servidor-{servidor.pk}",
        now=timezone.now(),
        x_document_sha256=doc.hash_sha256,
    )


def _termo_cadastro_docs_com_generico(termo, formato):
    """Termo genérico + termos individuais de cada servidor selecionado."""
    docs = [gerar_termo_cadastro_um(termo, None, formato)]
    docs.extend(gerar_termo_cadastro_lote(termo, formato))
    return docs


@require_GET
def baixar_termo_cadastro_pdf(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    docs = _termo_cadastro_docs_com_generico(termo, DocumentoFormato.PDF)
    content = docs[0].conteudo if len(docs) == 1 else fundir_termos_pdf(docs)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="termo_{termo.pk}.pdf"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = sha256_bytes(content)
    return response


@require_GET
def baixar_termo_cadastro_docx(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    docs = _termo_cadastro_docs_com_generico(termo, DocumentoFormato.DOCX)
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
