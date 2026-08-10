from __future__ import annotations
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from eventos.services import resolve_evento_from_request
from .models import PlanoTrabalho
from .selectors import listar_planos_trabalho
from .presenters import apresentar_plano_card
from .services import criar_plano_rascunho
from .view_helpers import _get_plano


def index(request):
    from django.db.models import Q
    from core import documento_abas as tabs

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    aba = tabs.normalizar_aba(request.GET.get("aba", ""))
    viagem_de = request.GET.get("viagem_de", "").strip()
    viagem_ate = request.GET.get("viagem_ate", "").strip()
    sort = request.GET.get("sort", "").strip()

    planos = listar_planos_trabalho(
        q=q or None,
        status=status or None,
        viagem_de=parse_date(viagem_de) if viagem_de else None,
        viagem_ate=parse_date(viagem_ate) if viagem_ate else None,
        sort=sort or None,
    )

    cancelado_q = Q(cancelado=True)
    date_field = "data_evento_inicio"
    lista = planos.filter(tabs.q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q))
    contagem = tabs.contar_por_aba(planos, date_field=date_field, cancelado_q=cancelado_q)
    abas = tabs.build_abas(
        reverse("planos_trabalho:index"), aba, contagem,
        preserved={"q": q, "status": status, "sort": sort,
                   "viagem_de": viagem_de, "viagem_ate": viagem_ate},
    )

    page_obj = Paginator(lista, 20).get_page(request.GET.get("page"))
    cards = [apresentar_plano_card(plano) for plano in page_obj.object_list]
    page_querystring = request.GET.copy()
    page_querystring.pop("page", None)
    has_filters = any([q, status, viagem_de, viagem_ate, sort])
    return render(
        request,
        "planos_trabalho/index.html",
        {
            "page_title": "Planos de Trabalho",
            "page_description": "Cadastre e gerencie planos de trabalho com numeração própria.",
            "q": q,
            "status": status,
            "aba": aba,
            "abas": abas,
            "viagem_de": viagem_de,
            "viagem_ate": viagem_ate,
            "sort": sort,
            "has_filters": has_filters,
            "cards": cards,
            "page_obj": page_obj,
            "page_querystring": page_querystring.urlencode(),
            "create_url": reverse("planos_trabalho:novo"),
            "search_clear_url": f"{reverse('planos_trabalho:index')}?aba={aba}",
            "programas_url": reverse("planos_trabalho:programas_index"),
            "horarios_url": reverse("planos_trabalho:horarios_index"),
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": valor, "label": rotulo} for valor, rotulo in PlanoTrabalho.STATUS_CHOICES],
            "sort_options": [
                {"value": "numero_desc", "label": "Número: maior"},
                {"value": "numero_asc", "label": "Número: menor"},
                {"value": "criacao_desc", "label": "Criação: mais recente"},
                {"value": "criacao_asc", "label": "Criação: mais antiga"},
                {"value": "viagem_asc", "label": "Viagem: mais próxima"},
                {"value": "viagem_desc", "label": "Viagem: mais distante"},
            ],
            "empty_message": "Nenhum plano de trabalho encontrado.",
        },
    )


@require_http_methods(["GET", "POST"])
def novo(request):
    if request.method == "GET":
        return render(
            request,
            "cotton/create_draft.html",
            {
                "page_title": "Novo plano de trabalho",
                "page_description": "Confirme para reservar a numeração e iniciar o cadastro.",
                "confirm_label": "Criar plano",
                "back_url": reverse("planos_trabalho:index"),
            },
        )
    evento = resolve_evento_from_request(request)
    plano = criar_plano_rascunho(evento=evento)
    messages.success(request, f"Plano de Trabalho {plano.numero_formatado} criado como rascunho.")
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


def editar(request, pk):
    plano = _get_plano(pk)
    return redirect("planos_trabalho:wizard_identificacao", pk=plano.pk)


@require_POST
def excluir(request, pk):
    plano = _get_plano(pk)
    numero = plano.numero_formatado
    evento_id = plano.evento_id
    plano.delete()
    messages.success(request, f"Plano de Trabalho {numero} excluído.")
    if evento_id:
        return redirect("eventos:guiado_etapa", pk=evento_id, etapa=4)
    return redirect("planos_trabalho:index")
