from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods

from documentos.services.responses import build_inline_pdf_response_from_download_response
from documentos.services.types import DocumentoTipo
from eventos.services import build_evento_document_seed
from eventos.services import resolve_evento_from_request

from .forms import OrdemServicoForm
from .models import OrdemServico
from .presenters import apresentar_ordem_servico_card
from .services import gerar_os_docx_response
from .services import gerar_os_pdf_response


def index(request):
    q = request.GET.get("q", "").strip()
    ordens = (
        OrdemServico.objects
        .prefetch_related(
            "destinos__estado",
            "servidores__cargo",
            "servidores__unidade",
            "oficios",
        )
        .order_by("-ano", "-numero")
    )
    if q:
        filters = (
            Q(motivo__icontains=q)
            | Q(destinos__nome__icontains=q)
            | Q(servidores__nome__icontains=q)
        )
        if q.isdigit():
            filters |= Q(numero=int(q)) | Q(ano=int(q)) | Q(oficios__numero=int(q))
        ordens = ordens.filter(filters).distinct()

    cards = [apresentar_ordem_servico_card(ordem) for ordem in ordens]

    return render(
        request,
        "ordens_servico/index.html",
        {
            "page_title": "Ordens de Serviço",
            "page_description": "Cadastre e gerencie ordens de serviço.",
            "q": q,
            "cards": cards,
            "nova_url": reverse("ordens_servico:nova"),
            "search_clear_url": reverse("ordens_servico:index"),
            "empty_message": "Nenhuma OS encontrada com os filtros aplicados." if q else "Nenhuma OS cadastrada ainda.",
        },
    )


def _os_queryset():
    return OrdemServico.objects.prefetch_related("destinos__estado", "servidores", "oficios")


def _evento_etapa_url(evento_id):
    if evento_id:
        return reverse("eventos:guiado_etapa", kwargs={"pk": evento_id, "etapa": 4})
    return ""


def _ordem_lista_url(ordem=None, evento=None):
    evento_id = getattr(evento, "pk", None) or getattr(ordem, "evento_id", None)
    return _evento_etapa_url(evento_id) or reverse("ordens_servico:index")


def _ordem_back_label(ordem=None, evento=None):
    return "Dados do evento" if (getattr(evento, "pk", None) or getattr(ordem, "evento_id", None)) else "Voltar a lista"


def _redirect_ordem_lista(ordem):
    if getattr(ordem, "evento_id", None):
        return redirect("eventos:guiado_etapa", pk=ordem.evento_id, etapa=4)
    return redirect("ordens_servico:editar", pk=ordem.pk)


def _build_oficio_summary(oficio):
    data_inicio = data_fim = None
    cidade_ids = []
    estado_id = ""
    cidade_id = ""

    roteiro = oficio.roteiro
    if roteiro:
        if roteiro.saida_dt:
            data_inicio = roteiro.saida_dt.date().isoformat()
        retorno = getattr(roteiro, "retorno_chegada_dt", None) or getattr(roteiro, "retorno_saida_dt", None)
        if retorno:
            data_fim = retorno.date().isoformat()
        elif data_inicio:
            data_fim = data_inicio
        destinos_values = list(
            roteiro.destinos
            .filter(cidade__isnull=False)
            .values("cidade_id", "estado_id")
            .order_by("ordem", "pk")
        )
        cidade_ids = [d["cidade_id"] for d in destinos_values]
        estado_id = destinos_values[0]["estado_id"] or "" if destinos_values else ""
        cidade_id = destinos_values[0]["cidade_id"] or "" if destinos_values else ""

    servidor_ids = list(oficio.servidores.values_list("pk", flat=True))

    return {
        "id": oficio.pk,
        "label": f"Ofício {oficio.numero_formatado}",
        "data_inicio": data_inicio or "",
        "data_fim": data_fim or "",
        "cidade_ids": cidade_ids,
        "estado_id": estado_id,
        "cidade_id": cidade_id,
        "servidor_ids": servidor_ids,
        "motivo": oficio.motivo or "",
    }


def _evento_selected_dates_json(form):
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


def _evento_display_values(form):
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


def _form_context(*, request, form, ordem=None, evento=None):
    oficios_qs = form.fields["oficios"].queryset.select_related("roteiro").prefetch_related(
        "roteiro__destinos__cidade",
        "servidores",
    )
    summaries = {}
    for oficio in oficios_qs:
        s = _build_oficio_summary(oficio)
        summaries[str(s["id"])] = s

    servidor_create_url = (
        f"{reverse('cadastros:servidor_create')}"
        f"?{urlencode({'next': request.get_full_path()})}"
    )

    return {
        "page_title": "Nova Ordem de Serviço" if ordem is None or not ordem.pk else f"Editar {ordem.numero_formatado}",
        "form": form,
        "ordem": ordem,
        "index_url": _ordem_lista_url(ordem=ordem, evento=evento),
        "back_label": _ordem_back_label(ordem=ordem, evento=evento),
        "servidor_create_url": servidor_create_url,
        "modelos_motivo_url": f"{reverse('oficios:modelos_motivo_index')}?{urlencode({'next': request.get_full_path()})}",
        "tem_modelos_motivo": form.fields["modelo_motivo"].queryset.exists(),
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "evento_selected_dates_json": _evento_selected_dates_json(form),
        "evento_display": _evento_display_values(form),
        "os_oficios_summary": summaries,
    }


@require_http_methods(["GET", "POST"])
def nova(request):
    evento = resolve_evento_from_request(request)
    seed = build_evento_document_seed(evento) if evento is not None else {}
    ordem = OrdemServico(
        evento=evento,
        data_evento_inicio=seed.get("data_inicio"),
        data_evento_fim=seed.get("data_fim") or seed.get("data_inicio"),
        motivo=seed.get("motivo") or "",
    )
    initial = {}
    if seed.get("estado"):
        initial["destino_estado"] = seed["estado"].pk
    if seed.get("cidade"):
        initial["destino_cidade"] = seed["cidade"].pk
    if seed.get("servidores"):
        initial["servidores"] = [servidor.pk for servidor in seed["servidores"]]
    if seed.get("oficios"):
        initial["oficios"] = [oficio.pk for oficio in seed["oficios"]]
    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, "Ordem de Serviço cadastrada.")
            return _redirect_ordem_lista(ordem)
    else:
        form = OrdemServicoForm(instance=ordem, initial=initial)
    return render(request, "ordens_servico/form.html", _form_context(request=request, form=form, ordem=None, evento=evento))


@require_http_methods(["GET", "POST"])
def editar(request, pk):
    ordem = get_object_or_404(_os_queryset(), pk=pk)
    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, "Ordem de Serviço atualizada.")
            return _redirect_ordem_lista(ordem)
    else:
        form = OrdemServicoForm(instance=ordem)
    return render(request, "ordens_servico/form.html", _form_context(request=request, form=form, ordem=ordem))


@require_http_methods(["GET"])
def baixar_docx(request, pk):
    ordem = get_object_or_404(_os_queryset(), pk=pk)
    return gerar_os_docx_response(ordem)


@require_GET
def baixar_pdf(request, pk):
    ordem = get_object_or_404(_os_queryset(), pk=pk)
    return gerar_os_pdf_response(ordem)


@require_GET
def pdf_inline(request, pk):
    ordem = get_object_or_404(_os_queryset(), pk=pk)
    reference = (
        f"os-{ordem.numero:03d}-{ordem.ano}"
        if ordem.numero and ordem.ano
        else f"os-{ordem.pk}"
    )
    download_resp = gerar_os_pdf_response(ordem)
    return build_inline_pdf_response_from_download_response(
        request,
        download_resp,
        tipo=DocumentoTipo.ORDEM_SERVICO,
        reference=reference,
    )


@require_http_methods(["POST"])
def excluir(request, pk):
    ordem = get_object_or_404(OrdemServico, pk=pk)
    numero = ordem.numero_formatado
    ordem.delete()
    messages.success(request, f"Ordem de Serviço {numero} excluída.")
    return redirect("ordens_servico:index")
