from __future__ import annotations

import json
from datetime import datetime

from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import OrdemServicoForm
from .models import OrdemServico
from .services import gerar_os_docx_response


def index(request):
    ordens = (
        OrdemServico.objects
        .prefetch_related("destinos__estado", "servidores", "oficios")
        .order_by("-ano", "-numero")
    )
    return render(
        request,
        "ordens_servico/index.html",
        {
            "page_title": "Ordens de Serviço",
            "page_description": "Cadastre e gerencie ordens de serviço.",
            "ordens": ordens,
            "nova_url": reverse("ordens_servico:nova"),
        },
    )


def _os_queryset():
    return OrdemServico.objects.prefetch_related("destinos__estado", "servidores", "oficios")


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


def _form_context(*, form, ordem=None):
    oficios_qs = form.fields["oficios"].queryset.select_related("roteiro").prefetch_related(
        "roteiro__destinos__cidade",
        "servidores",
    )
    summaries = {}
    for oficio in oficios_qs:
        s = _build_oficio_summary(oficio)
        summaries[str(s["id"])] = s

    return {
        "page_title": "Nova Ordem de Serviço" if ordem is None or not ordem.pk else f"Editar {ordem.numero_formatado}",
        "form": form,
        "ordem": ordem,
        "index_url": reverse("ordens_servico:index"),
        "servidor_create_url": reverse("cadastros:servidor_create"),
        "modelos_motivo_url": reverse("oficios:modelos_motivo_index"),
        "tem_modelos_motivo": form.fields["modelo_motivo"].queryset.exists(),
        "api_cidades_por_estado_url": reverse("roteiros:api_cidades_por_estado", kwargs={"estado_id": 0}),
        "evento_selected_dates_json": _evento_selected_dates_json(form),
        "evento_display": _evento_display_values(form),
        "os_oficios_summary": summaries,
    }


@require_http_methods(["GET", "POST"])
def nova(request):
    ordem = OrdemServico()
    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, "Ordem de Serviço cadastrada.")
            return redirect("ordens_servico:editar", pk=ordem.pk)
    else:
        form = OrdemServicoForm(instance=ordem)
    return render(request, "ordens_servico/form.html", _form_context(form=form, ordem=None))


@require_http_methods(["GET", "POST"])
def editar(request, pk):
    ordem = get_object_or_404(_os_queryset(), pk=pk)
    if request.method == "POST":
        form = OrdemServicoForm(request.POST, instance=ordem)
        if form.is_valid():
            ordem = form.save()
            messages.success(request, "Ordem de Serviço atualizada.")
            return redirect("ordens_servico:editar", pk=ordem.pk)
    else:
        form = OrdemServicoForm(instance=ordem)
    return render(request, "ordens_servico/form.html", _form_context(form=form, ordem=ordem))


@require_http_methods(["GET"])
def baixar_docx(request, pk):
    ordem = get_object_or_404(_os_queryset(), pk=pk)
    return gerar_os_docx_response(ordem)
