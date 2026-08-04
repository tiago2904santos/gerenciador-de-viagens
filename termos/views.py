import json
import re

from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.http import Http404
from django.http import HttpResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST

from core.retorno import voltar_para


from documentos.selectors import mapa_artefatos_pdf_termo_cadastro
from documentos.services.async_generation import enfileirar_documento
from documentos.services.types import DocumentoFormato
from eventos.services import build_evento_document_seed
from eventos.services import resolve_evento_from_request

from oficios.selectors import get_oficio_by_id
from oficios.services import redirect_para_corrigir_documento_oficio
from oficios.services import validar_oficio_para_documento

from .forms import TermoAutorizacaoForm
from .models import TermoAutorizacao
from .presenters import apresentar_linha_lista_simples_termo
from .presenters import apresentar_linha_simples_termo
from .presenters import apresentar_termo_card
from .selectors import get_servidor_do_termo_do_oficio
from .selectors import get_servidor_para_termo
from .selectors import get_termo_by_id
from django.db.models import Count

from .selectors import Q_SIMPLES
from .selectors import anotar_composicao
from .selectors import listar_termos
from .services import listar_servidores_com_termo
from .services import preview_termo_context
from .services import resolver_artefato_termo_cadastro
from .services import resolver_artefato_termo_oficio
from .services import servidores_para_termo_cadastro
from .services import termo_cadastro_assinado_info
from .services import termo_cadastro_tem_assinado
from .services import termo_oficio_tem_assinado
from cadastros.selectors import rotulo_da_sede_configurada


TERMOS_PER_PAGE = 15




# Duas listas: o termo sem servidor e sem viatura nao tem o que mostrar no card
# em camadas, entao vai para a lista de linhas simples.
ABAS_TERMO = (("especificos", "Com equipe"), ("simples", "Sem equipe"))


def index(request):
    q = request.GET.get("q", "").strip()
    q_digits = _digits(q)
    aba = request.GET.get("aba", "")
    if aba not in dict(ABAS_TERMO):
        aba = "especificos"
    simples = aba == "simples"

    busca = {"q": q or None, "q_digits": q_digits or None}
    termos = listar_termos(**busca, simples=simples)
    # Uma agregacao condicional em vez de dois .count(): as abas custam 1 query.
    contagem = anotar_composicao(listar_termos(**busca)).aggregate(
        simples=Count("pk", filter=Q_SIMPLES),
        especificos=Count("pk", filter=~Q_SIMPLES),
    )
    preservado = urlencode({"q": q}) if q else ""
    abas = [
        {
            "key": chave,
            "label": label,
            "count": contagem[chave],
            "url": f"{reverse('termos:index')}?aba={chave}" + (f"&{preservado}" if preservado else ""),
            "is_active": chave == aba,
        }
        for chave, label in ABAS_TERMO
    ]

    paginator = Paginator(termos, TERMOS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    def _servidor_url(termo_pk):
        def build(servidor_pk, formato):
            return reverse(
                "termos:baixar_termo_cadastro_servidor",
                args=[termo_pk, servidor_pk, formato],
            )
        return build

    def _servidor_view_url(termo_pk):
        def build(servidor_pk):
            return reverse(
                "termos:termo_cadastro_servidor_pdf_inline",
                args=[termo_pk, servidor_pk],
            )
        return build

    rows = [
        apresentar_linha_simples_termo(
            termo,
            edit_url=reverse("termos:editar", args=[termo.pk]),
            delete_url=reverse("termos:excluir", args=[termo.pk]),
            pdf_url=reverse("termos:baixar_termo_cadastro_generico", args=[termo.pk, "pdf"]),
            docx_url=reverse("termos:baixar_termo_cadastro_generico", args=[termo.pk, "docx"]),
            **termo_cadastro_assinado_info(termo, None),
        )
        for termo in page_obj.object_list
    ] if simples else []

    cards = [] if simples else [
        apresentar_termo_card(
            termo,
            edit_url=reverse("termos:editar", args=[termo.pk]),
            delete_url=reverse("termos:excluir", args=[termo.pk]),
            delete_modal=True,
            pdf_url=reverse("termos:baixar_termo_cadastro_pdf", args=[termo.pk]),
            docx_url=reverse("termos:baixar_termo_cadastro_docx", args=[termo.pk]),
            generico_pdf_url=reverse("termos:baixar_termo_cadastro_generico", args=[termo.pk, "pdf"]),
            generico_docx_url=reverse("termos:baixar_termo_cadastro_generico", args=[termo.pk, "docx"]),
            servidor_url_builder=_servidor_url(termo.pk),
            servidor_view_url_builder=_servidor_view_url(termo.pk),
            viatura_view_url=reverse("termos:termo_cadastro_viatura_pdf_inline", args=[termo.pk]),
            viatura_pdf_url=reverse("termos:baixar_termo_cadastro_viatura", args=[termo.pk, "pdf"]),
            viatura_docx_url=reverse("termos:baixar_termo_cadastro_viatura", args=[termo.pk, "docx"]),
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
            "cards": cards,
            "rows": rows,
            "aba": aba,
            "abas": abas,
            "simples": simples,
            "q": q,
            "page_obj": page_obj,
            "pagination_pages": _pagination_pages(page_obj),
            "page_querystring": urlencode({k: v for k, v in {"q": q, "aba": aba}.items() if v}),
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
    # Uma query para o termo inteiro em vez de uma por servidor (NOVO-26).
    artefatos = mapa_artefatos_pdf_termo_cadastro(termo.pk)
    return {
        "generico": {
            "titulo": "Termo genérico",
            "inline_url": reverse("termos:termo_cadastro_generico_pdf_inline", args=[termo.pk]),
            "download_pdf_url": reverse("termos:baixar_termo_cadastro_pdf", args=[termo.pk]),
            "download_docx_url": reverse("termos:baixar_termo_cadastro_docx", args=[termo.pk]),
            **termo_cadastro_assinado_info(termo, None, artefatos),
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
                **termo_cadastro_assinado_info(termo, servidor.pk, artefatos),
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
    index_url = _termo_lista_url(termo=termo, evento=evento)
    back_label = _termo_back_label(termo=termo, evento=evento)
    return {
        "page_title": "Cadastro de termo",
        "form": form,
        "termo": termo,
        "index_url": index_url,
        "back_label": back_label,
        "flow_eyebrow": "TERMOS",
        "flow_description": "Cadastro independente de termo de autorização",
        "flow_icon_label": "TM",
        "flow_module_label": "Termos",
        "flow_back_label": back_label,
        "flow_back_url": index_url,
        "servidor_create_url": _cadastro_create_url("cadastros:servidor_create", next_url),
        "viatura_create_url": _cadastro_create_url("cadastros:viatura_create", next_url),
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "oficios_summary": summaries,
        "sede_config_label": rotulo_da_sede_configurada(),
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
    termo = get_termo_by_id(pk)
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
    termo = get_termo_by_id(pk)
    termo.delete()
    messages.success(request, "Termo excluido.")
    return redirect("termos:index")


@require_GET
def termo_cadastro_pdf_inline(request, pk):
    termo = get_termo_by_id(pk)
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "formato": DocumentoFormato.PDF.value,
            "modo": "selecionados",
        },
        disposicao="inline",
    )


@require_GET
def termo_cadastro_generico_pdf_inline(request, pk):
    termo = get_termo_by_id(pk)
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "formato": DocumentoFormato.PDF.value,
            "modo": "generico",
        },
        disposicao="inline",
    )


@require_GET
def termo_cadastro_servidor_pdf_inline(request, pk, servidor_pk):
    termo = get_termo_by_id(pk)
    servidor = get_servidor_para_termo(servidor_pk)
    if not termo.servidores_efetivos().filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para este termo.")
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "servidor_id": servidor.pk,
            "formato": DocumentoFormato.PDF.value,
            "modo": "servidor",
        },
        disposicao="inline",
    )


@require_GET
def baixar_termo_cadastro_generico(request, pk, formato):
    """Termo em branco (variante SEMIPREENCHIDO), sem servidor nem viatura."""
    termo = get_termo_by_id(pk)
    try:
        fmt = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato nao suportado.") from exc
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "formato": fmt.value,
            "modo": "generico",
        },
    )


@require_GET
def termo_cadastro_viatura_pdf_inline(request, pk):
    termo = get_termo_by_id(pk)
    if termo.viatura_efetiva() is None:
        raise Http404("Termo sem viatura.")
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "formato": DocumentoFormato.PDF.value,
            "modo": "viatura",
        },
        disposicao="inline",
    )


@require_GET
def baixar_termo_cadastro_viatura(request, pk, formato):
    """Termo preenchido so com a viatura, sem servidor."""
    termo = get_termo_by_id(pk)
    if termo.viatura_efetiva() is None:
        raise Http404("Termo sem viatura.")
    try:
        fmt = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato nao suportado.") from exc
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "formato": fmt.value,
            "modo": "viatura",
        },
    )


@require_GET
def baixar_termo_cadastro_servidor(request, pk, servidor_pk, formato):
    """Termo de um servidor. A viatura do termo decide a variante do template."""
    termo = get_termo_by_id(pk)
    try:
        fmt = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato nao suportado.") from exc
    servidor = get_servidor_para_termo(servidor_pk)
    if not termo.servidores_efetivos().filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para este termo.")
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "servidor_id": servidor.pk,
            "formato": fmt.value,
            "modo": "servidor",
        },
    )


@require_GET
def baixar_termo_cadastro_pdf(request, pk):
    termo = get_termo_by_id(pk)
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "formato": DocumentoFormato.PDF.value,
            "modo": "todos",
        },
    )


@require_GET
def baixar_termo_cadastro_docx(request, pk):
    termo = get_termo_by_id(pk)
    return enfileirar_documento(
        request,
        tipo="termo_cadastro",
        parametros={
            "object_id": termo.pk,
            "formato": DocumentoFormato.DOCX.value,
            "modo": "todos",
        },
    )


def preview_termo_oficio(request, pk):
    oficio = get_oficio_by_id(pk)
    aval = validar_oficio_para_documento(oficio)
    modo = request.GET.get("semipreenchido") == "1"
    servidor_pk = request.GET.get("servidor")
    servidor = None
    if servidor_pk:
        servidor = get_servidor_para_termo(int(servidor_pk))
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
    servidor = get_servidor_para_termo(servidor_pk)
    if not oficio.servidores.filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao participa deste oficio.")
    if not listar_servidores_com_termo(oficio).filter(pk=servidor.pk).exists():
        raise Http404("Servidor nao selecionado para Termo de Autorizacao neste oficio.")

    if not termo_oficio_tem_assinado(oficio, servidor):
        aval = validar_oficio_para_documento(oficio)
        if aval["pendencias"]:
            messages.error(request, "Termo nao gerado: oficio incompleto.")
            return redirect(f"{redirect_para_corrigir_documento_oficio(oficio)}?documento_incompleto=1")

    return enfileirar_documento(
        request,
        tipo="termo_oficio",
        parametros={
            "object_id": oficio.pk,
            "servidor_id": servidor.pk,
            "formato": DocumentoFormato.PDF.value,
            "modo": "servidor",
        },
        disposicao="inline",
    )


def baixar_termo_servidor(request, pk, servidor_pk, formato):
    oficio = get_oficio_by_id(pk)
    try:
        fmt = DocumentoFormato(formato)
    except ValueError as exc:
        raise Http404("Formato nao suportado.") from exc

    servidor = get_servidor_para_termo(servidor_pk)
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

    return enfileirar_documento(
        request,
        tipo="termo_oficio",
        parametros={
            "object_id": oficio.pk,
            "servidor_id": servidor.pk,
            "formato": fmt.value,
            "modo": "servidor",
        },
    )


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

    return enfileirar_documento(
        request,
        tipo="termo_oficio",
        parametros={
            "object_id": oficio.pk,
            "formato": DocumentoFormato.PDF.value,
            "modo": "todos",
        },
    )


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

    return enfileirar_documento(
        request,
        tipo="termo_oficio",
        parametros={
            "object_id": oficio.pk,
            "formato": fmt.value,
            "modo": "todos",
        },
    )




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
        return redirect(voltar_para(request, fallback_url))
    artefato = resolver()
    if artefato is None:
        messages.error(request, "Não foi possível gerar o termo para anexar o assinado.")
        return redirect(voltar_para(request, fallback_url))
    try:
        anexar_arquivo_assinado(artefato, upload)
    except ArquivoAssinadoInvalido as exc:
        messages.error(request, str(exc))
        return redirect(voltar_para(request, fallback_url))
    agendar_sincronizacao_assinatura_manual(artefato, usuario=request.user)
    messages.success(request, "Documento assinado anexado.")
    return redirect(voltar_para(request, fallback_url))


@require_POST
def termo_oficio_assinado_anexar(request, pk, servidor_pk):
    oficio = get_oficio_by_id(pk)
    # Servidor precisa pertencer ao termo do ofício; não filtrar só por área do
    # cadastro — registros legados com area nula quebravam o anexo em produção.
    servidor = get_servidor_do_termo_do_oficio(oficio, servidor_pk)
    fallback = reverse("oficios:wizard_documentos", args=[oficio.pk])
    return _anexar_assinado_resolver(
        request, fallback, lambda: resolver_artefato_termo_oficio(oficio, servidor)
    )


@require_POST
def termo_cadastro_generico_assinado_anexar(request, pk):
    termo = get_termo_by_id(pk)
    fallback = reverse("termos:editar", args=[termo.pk])
    return _anexar_assinado_resolver(
        request, fallback, lambda: resolver_artefato_termo_cadastro(termo, None)
    )


@require_POST
def termo_cadastro_servidor_assinado_anexar(request, pk, servidor_pk):
    termo = get_termo_by_id(pk)
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
