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
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

from cadastros.models import Servidor
from core.tenancy import filter_queryset_by_area
from core.normalizers import remove_accents

from documentos.services.exceptions import DocumentValidationError
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
from .services import fundir_termos_docx
from .services import fundir_termos_pdf_bytes
from .services import gerar_termo_cadastro_um
from .services import gerar_termo_lote
from .services import gerar_termos_pdf_consolidado
from .services import gerar_termo_um
from .services import listar_servidores_com_termo
from .services import pdf_termo_cadastro_assinado_ou_gerado
from .services import pdf_termo_oficio_assinado_ou_gerado
from .services import preview_termo_context
from .services import resolver_artefato_termo_cadastro
from .services import resolver_artefato_termo_oficio
from .services import servidores_para_termo_cadastro
from .services import sha256_bytes
from .services import termo_cadastro_assinado_info
from .services import termo_cadastro_tem_assinado
from .services import termo_oficio_tem_assinado


TERMOS_PER_PAGE = 15


def index(request):
    q = request.GET.get("q", "").strip()
    q_digits = _digits(q)
    termos = (
        filter_queryset_by_area(TermoAutorizacao.objects)
        .select_related(
            "oficio",
            "destino_estado",
            "destino_cidade",
            "viatura",
        )
        .prefetch_related("servidores")
        .order_by("-created_at")
    )
    if q:
        q_unaccent = remove_accents(q)
        query = (
            Q(destino_cidade__nome__unaccent__icontains=q_unaccent)
            | Q(destino_cidade__uf__unaccent__icontains=q_unaccent)
            | Q(destino_estado__nome__unaccent__icontains=q_unaccent)
            | Q(destino_estado__sigla__unaccent__icontains=q_unaccent)
            | Q(oficio__numero__icontains=q)
            | Q(oficio__protocolo__icontains=q)
            | Q(oficio__servidores__nome__unaccent__icontains=q_unaccent)
            | Q(oficio__servidores_termo_autorizacao__nome__unaccent__icontains=q_unaccent)
            | Q(servidores__nome__unaccent__icontains=q_unaccent)
            | Q(viatura__placa__icontains=q)
            | Q(viatura__modelo__unaccent__icontains=q_unaccent)
            | Q(oficio__viatura__placa__icontains=q)
            | Q(oficio__viatura__modelo__unaccent__icontains=q_unaccent)
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
            **termo_cadastro_assinado_info(termo, None),
        )
        for termo in page_obj.object_list
    ]
    return render(
        request,
        "termos/index.html",
        {
            "page_title": "Termos de Autorização",
            "page_description": "Cadastre termos avulsos ou vinculados a ofícios existentes.",
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
    return filter_queryset_by_area(TermoAutorizacao.objects).select_related(
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


def _roteiro_destino_label(item):
    if not item:
        return ""
    if item.cidade_id:
        return str(item.cidade)
    if item.estado_id:
        return str(item.estado)
    return str(item)


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
        destino = _roteiro_destino_label(destino_obj)
        destinos_label = ", ".join(_roteiro_destino_label(item) for item in destinos if item)
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


def _termo_preview_documents(termo):
    if not termo or not termo.pk:
        return {}
    servidores = list(termo.servidores_efetivos())
    return {
        "generico": {
            "titulo": "Termo genérico",
            "inline_url": reverse("termos:termo_cadastro_generico_pdf_inline", args=[termo.pk]),
            "download_pdf_url": reverse("termos:baixar_termo_cadastro_pdf", args=[termo.pk]),
            "download_docx_url": reverse("termos:baixar_termo_cadastro_docx", args=[termo.pk]),
            **termo_cadastro_assinado_info(termo, None),
        },
        "download_todos_pdf_url": reverse("termos:baixar_termo_cadastro_pdf", args=[termo.pk]),
        "download_todos_docx_url": reverse("termos:baixar_termo_cadastro_docx", args=[termo.pk]),
        "servidores": [
            {
                "id": servidor.pk,
                "titulo": f"Termo de Autorização — {servidor.nome}",
                "servidor_nome": servidor.nome,
                "inline_url": reverse(
                    "termos:termo_cadastro_servidor_pdf_inline", args=[termo.pk, servidor.pk]
                ),
                **termo_cadastro_assinado_info(termo, servidor.pk),
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
    for index, oficio in enumerate(oficios):
        summary = _oficio_summary(oficio)
        summary["order"] = index
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


def _termo_pdf_error_redirect(request, termo, exc: DocumentValidationError):
    messages.error(request, str(exc))
    return redirect("termos:editar", pk=termo.pk)


@require_GET
def termo_cadastro_pdf_inline(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    servidores = servidores_para_termo_cadastro(termo)
    try:
        conteudos = [pdf_termo_cadastro_assinado_ou_gerado(termo, servidor) for servidor in servidores]
    except DocumentValidationError as exc:
        return _termo_pdf_error_redirect(request, termo, exc)
    content = conteudos[0] if len(conteudos) == 1 else fundir_termos_pdf_bytes(conteudos)
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
    try:
        content = pdf_termo_cadastro_assinado_ou_gerado(termo, None)
    except DocumentValidationError as exc:
        return _termo_pdf_error_redirect(request, termo, exc)
    return build_inline_pdf_response(
        request,
        content=content,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        reference=f"termo-{termo.pk}-generico",
        now=timezone.now(),
        x_document_sha256=sha256_bytes(content),
    )


@require_GET
def termo_cadastro_servidor_pdf_inline(request, pk, servidor_pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    servidor = get_object_or_404(filter_queryset_by_area(Servidor.objects), pk=servidor_pk)
    if not termo.servidores_efetivos().filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para este termo.")
    try:
        content = pdf_termo_cadastro_assinado_ou_gerado(termo, servidor)
    except DocumentValidationError as exc:
        return _termo_pdf_error_redirect(request, termo, exc)
    return build_inline_pdf_response(
        request,
        content=content,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        reference=f"termo-{termo.pk}-servidor-{servidor.pk}",
        now=timezone.now(),
        x_document_sha256=sha256_bytes(content),
    )


def _termo_cadastro_docs_com_generico(termo, formato):
    """Termo genérico + termos individuais de cada servidor efetivo (sempre gerados).

    Usado só pelo DOCX (não tem versão assinada equivalente). Não usa
    ``gerar_termo_cadastro_lote`` porque este faz fallback para ``[None]``
    quando não há servidores — o que duplicaria o termo genérico. Aqui o genérico
    é gerado exatamente uma vez e os individuais só quando há servidores.
    """
    docs = [gerar_termo_cadastro_um(termo, None, formato)]
    for servidor in termo.servidores_efetivos():
        docs.append(gerar_termo_cadastro_um(termo, servidor, formato))
    return docs


def _termo_cadastro_pdf_bytes_com_generico(termo):
    """Como ``_termo_cadastro_docs_com_generico``, mas em PDF preferindo o assinado de cada parte."""
    conteudos = [pdf_termo_cadastro_assinado_ou_gerado(termo, None)]
    for servidor in termo.servidores_efetivos():
        conteudos.append(pdf_termo_cadastro_assinado_ou_gerado(termo, servidor))
    return conteudos


def _termo_oficio_pdf_error_redirect(request, oficio, exc: DocumentValidationError):
    messages.error(request, str(exc))
    return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")


@require_GET
def baixar_termo_cadastro_pdf(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    try:
        conteudos = _termo_cadastro_pdf_bytes_com_generico(termo)
    except DocumentValidationError as exc:
        return _termo_pdf_error_redirect(request, termo, exc)
    content = conteudos[0] if len(conteudos) == 1 else fundir_termos_pdf_bytes(conteudos)
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
        content = doc.conteudo
        content_hash = doc.hash_sha256
    else:
        content = fundir_termos_docx(docs)
        content_hash = sha256_bytes(content)
    response = HttpResponse(content, content_type=docs[0].content_type)
    response["Content-Disposition"] = f'attachment; filename="termo_{termo.pk}.docx"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = content_hash
    return response


def preview_termo_oficio(request, pk):
    oficio = get_oficio_by_id(pk)
    aval = validar_oficio_para_documento(oficio)
    modo = request.GET.get("semipreenchido") == "1"
    servidor_pk = request.GET.get("servidor")
    servidor = None
    if servidor_pk:
        servidor = get_object_or_404(filter_queryset_by_area(Servidor.objects), pk=int(servidor_pk))
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
    servidor = get_object_or_404(filter_queryset_by_area(Servidor.objects), pk=servidor_pk)
    if not oficio.servidores.filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao participa deste oficio.")
    if not listar_servidores_com_termo(oficio).filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para Termo de Autorizacao neste oficio.")

    if not termo_oficio_tem_assinado(oficio, servidor):
        aval = validar_oficio_para_documento(oficio)
        if aval["pendencias"]:
            messages.error(request, "Termo nao gerado: oficio incompleto.")
            return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    try:
        content = pdf_termo_oficio_assinado_ou_gerado(oficio, servidor)
    except DocumentValidationError as exc:
        return _termo_oficio_pdf_error_redirect(request, oficio, exc)
    ref = f"{oficio.numero_formatado.replace('/', '-')}-termo-{servidor.pk}"
    return build_inline_pdf_response(
        request,
        content=content,
        tipo=DocumentoTipo.TERMO_AUTORIZACAO,
        reference=ref,
        now=timezone.now(),
        x_document_sha256=sha256_bytes(content),
    )


def baixar_termo_servidor(request, pk, servidor_pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        fmt = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato nao suportado.") from exc

    servidor = get_object_or_404(filter_queryset_by_area(Servidor.objects), pk=servidor_pk)
    if not oficio.servidores.filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao participa deste oficio.")
    if not listar_servidores_com_termo(oficio).filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para Termo de Autorizacao neste oficio.")

    tem_assinado = fmt == DocumentoFormato.PDF and termo_oficio_tem_assinado(oficio, servidor)
    if not tem_assinado:
        aval = validar_oficio_para_documento(oficio)
        if aval["pendencias"]:
            messages.error(request, "Termo nao gerado: oficio incompleto.")
            return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    try:
        if fmt == DocumentoFormato.PDF:
            content = pdf_termo_oficio_assinado_ou_gerado(oficio, servidor)
            content_type = "application/pdf"
            nome_arquivo = f"termo_{oficio.numero_formatado.replace('/', '-')}_{servidor.pk}.pdf"
        else:
            doc = gerar_termo_um(oficio, servidor, fmt)
            content = doc.conteudo
            content_type = doc.content_type
            nome_arquivo = doc.nome_arquivo
    except DocumentValidationError as exc:
        return _termo_oficio_pdf_error_redirect(request, oficio, exc)
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Document-SHA256"] = sha256_bytes(content)
    return response


def baixar_termos_todos_pdf(request, pk):
    oficio = get_oficio_by_id(pk)
    servidores = list(listar_servidores_com_termo(oficio))
    if not servidores:
        messages.error(request, "Nenhum servidor selecionado para Termo de Autorizacao.")
        return redirect("termos:index")

    if not all(termo_oficio_tem_assinado(oficio, s) for s in servidores):
        aval = validar_oficio_para_documento(oficio)
        if aval["pendencias"]:
            messages.error(request, "Termos nao gerados: oficio incompleto.")
            return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    try:
        assinados = [termo_oficio_tem_assinado(oficio, s) for s in servidores]
        if len(servidores) > 1 and not any(assinados):
            pdf_bytes = gerar_termos_pdf_consolidado(oficio)
        else:
            conteudos = [pdf_termo_oficio_assinado_ou_gerado(oficio, s) for s in servidores]
            pdf_bytes = conteudos[0] if len(conteudos) == 1 else fundir_termos_pdf_bytes(conteudos)
    except DocumentValidationError as exc:
        return _termo_oficio_pdf_error_redirect(request, oficio, exc)
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

    servidores = list(listar_servidores_com_termo(oficio))
    if not servidores:
        messages.error(request, "Nenhum servidor selecionado para Termo de Autorizacao.")
        return redirect("termos:index")

    tem_assinado = fmt == DocumentoFormato.PDF and all(termo_oficio_tem_assinado(oficio, s) for s in servidores)
    if not tem_assinado:
        aval = validar_oficio_para_documento(oficio)
        if aval["pendencias"]:
            messages.error(request, "Lote nao gerado: oficio incompleto.")
            return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    try:
        if fmt == DocumentoFormato.PDF:
            assinados = [termo_oficio_tem_assinado(oficio, s) for s in servidores]
            if len(servidores) > 1 and not any(assinados):
                content = gerar_termos_pdf_consolidado(oficio)
            else:
                conteudos = [pdf_termo_oficio_assinado_ou_gerado(oficio, s) for s in servidores]
                content = conteudos[0] if len(conteudos) == 1 else fundir_termos_pdf_bytes(conteudos)
            content_type = "application/pdf"
        else:
            docs = gerar_termo_lote(oficio, fmt)
            content = docs[0].conteudo if len(docs) == 1 else fundir_termos_docx(docs)
            content_type = docs[0].content_type
    except DocumentValidationError as exc:
        return _termo_oficio_pdf_error_redirect(request, oficio, exc)
    nome = f"termos_oficio_{oficio.numero_formatado.replace('/', '-')}.{fmt.value}"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{nome}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _safe_next_url(request, fallback_url):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


def _anexar_assinado_resolver(request, fallback_url, resolver):
    """Miolo comum: resolve (gera se preciso) o artefato e anexa o PDF enviado.

    ``resolver`` é uma função sem argumentos que devolve o ``DocumentoArtefato``
    (ou ``None`` se não conseguiu gerar). Usado pelos dois wrappers finos
    (termo embutido no ofício e termo avulso/cadastro) para não duplicar a
    validação/anexação/sincronização com o Drive, que já vivem em `documentos`.
    """
    from documentos.services.exceptions import ArquivoAssinadoInvalido
    from documentos.services.persistence import anexar_arquivo_assinado
    from integracoes.google_drive.services import agendar_sincronizacao_assinatura_manual

    upload = request.FILES.get("arquivo")
    if not upload:
        messages.error(request, "Selecione um arquivo PDF para anexar.")
        return redirect(_safe_next_url(request, fallback_url))
    artefato = resolver()
    if artefato is None:
        messages.error(request, "Não foi possível gerar o termo para anexar o assinado.")
        return redirect(_safe_next_url(request, fallback_url))
    try:
        anexar_arquivo_assinado(artefato, upload)
    except ArquivoAssinadoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(_safe_next_url(request, fallback_url))
    agendar_sincronizacao_assinatura_manual(artefato, usuario=request.user)
    messages.success(request, "Documento assinado anexado.")
    return redirect(_safe_next_url(request, fallback_url))


@require_POST
def termo_oficio_assinado_anexar(request, pk, servidor_pk):
    oficio = get_oficio_by_id(pk)
    # Servidor precisa pertencer ao termo do ofício; não filtrar só por área do
    # cadastro — registros legados com area nula quebravam o anexo em produção.
    servidor = get_object_or_404(oficio.servidores_termo_autorizacao.all(), pk=servidor_pk)
    fallback = reverse("oficios:wizard_documentos", args=[oficio.pk])
    return _anexar_assinado_resolver(
        request, fallback, lambda: resolver_artefato_termo_oficio(oficio, servidor)
    )


@require_POST
def termo_cadastro_generico_assinado_anexar(request, pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    fallback = reverse("termos:editar", args=[termo.pk])
    return _anexar_assinado_resolver(
        request, fallback, lambda: resolver_artefato_termo_cadastro(termo, None)
    )


@require_POST
def termo_cadastro_servidor_assinado_anexar(request, pk, servidor_pk):
    termo = get_object_or_404(_termo_queryset(), pk=pk)
    # Resolve somente dentro dos servidores efetivos do termo (próprios ou
    # herdados do ofício vinculado), sem consultar um cadastro de outra área.
    servidor = next(
        (
            item
            for item, _oficio in termo.servidores_efetivos_com_oficio()
            if item.pk == servidor_pk
        ),
        None,
    )
    if servidor is None:
        raise Http404("Servidor não pertence a este termo.")
    fallback = reverse("termos:editar", args=[termo.pk])
    return _anexar_assinado_resolver(
        request, fallback, lambda: resolver_artefato_termo_cadastro(termo, servidor)
    )
