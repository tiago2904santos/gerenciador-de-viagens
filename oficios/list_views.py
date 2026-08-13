from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from core.pagination import contexto_paginacao
from eventos.services import resolve_evento_from_request
from .models import Oficio
from .presenters import apresentar_oficio_card
from .selectors import get_oficio_by_id
from .selectors import hidratar_oficios_da_pagina
from .selectors import listar_oficios
from .services import criar_oficio_rascunho

OFICIOS_POR_PAGINA = 20


def index(request):
    from django.db.models import OuterRef
    from core import documento_abas as tabs
    from prestacoes_contas.models import PrestacaoServidor

    q           = request.GET.get("q",          "").strip()
    status      = request.GET.get("status",     "").strip()
    aba         = tabs.normalizar_aba(request.GET.get("aba", ""))
    criacao_de  = request.GET.get("criacao_de", "").strip()
    criacao_ate = request.GET.get("criacao_ate","").strip()
    viagem_de   = request.GET.get("viagem_de",  "").strip()
    viagem_ate  = request.GET.get("viagem_ate", "").strip()
    sort        = request.GET.get("sort",       "").strip()

    base = listar_oficios(
        q=q or None,
        status=status or None,
        criacao_de=criacao_de or None,
        criacao_ate=criacao_ate or None,
        viagem_de=viagem_de or None,
        viagem_ate=viagem_ate or None,
        sort=sort or None,
    )
    # Finalizado = todos os servidores da prestação deste ofício foram finalizados.
    sub = PrestacaoServidor.objects.filter(prestacao__oficio=OuterRef("pk"))
    base = tabs.anotar_finalizacao(base, sub, sub.filter(finalizada=False))
    cancelado_q = Q(cancelado=True)
    date_field = "roteiro__saida_dt__date"

    oficios = base.filter(tabs.q_da_aba(aba, date_field=date_field, cancelado_q=cancelado_q))
    contagem = tabs.contar_por_aba(base, date_field=date_field, cancelado_q=cancelado_q)
    abas = tabs.build_abas(
        reverse("oficios:index"), aba, contagem,
        preserved={"q": q, "status": status, "sort": sort,
                   "criacao_de": criacao_de, "criacao_ate": criacao_ate,
                   "viagem_de": viagem_de, "viagem_ate": viagem_ate},
    )
    paginacao = contexto_paginacao(oficios, request, OFICIOS_POR_PAGINA)
    objetos_da_pagina = hidratar_oficios_da_pagina(paginacao["page_obj"].object_list)
    paginacao["page_obj"].object_list = objetos_da_pagina
    cards = []
    for oficio in objetos_da_pagina:
        cards.append(apresentar_oficio_card(oficio, excluir_next_url=reverse("oficios:index")))

    has_filters = any([q, status, criacao_de, criacao_ate, viagem_de, viagem_ate, sort])

    return render(
        request,
        "oficios/index.html",
        {
            "page_title": "Ofícios",
            "q":           q,
            "status":      status,
            "aba":         aba,
            "abas":        abas,
            "criacao_de":  criacao_de,
            "criacao_ate": criacao_ate,
            "viagem_de":   viagem_de,
            "viagem_ate":  viagem_ate,
            "sort":        sort,
            "has_filters": has_filters,
            "cards":       cards,
            "create_url":  reverse("oficios:novo"),
            "search_clear_url": f"{reverse('oficios:index')}?aba={aba}",
            "status_options": [{"value": "", "label": "Todos os status"}]
            + [{"value": valor, "label": rotulo} for valor, rotulo in Oficio.STATUS_CHOICES],
            "sort_options": [
                {"value": "numero_desc",  "label": "Número: maior"},
                {"value": "numero_asc",   "label": "Número: menor"},
                {"value": "criacao_desc", "label": "Criação: mais recente"},
                {"value": "criacao_asc",  "label": "Criação: mais antiga"},
                {"value": "viagem_asc",   "label": "Viagem: mais próxima"},
                {"value": "viagem_desc",  "label": "Viagem: mais distante"},
            ],
            "empty_message": "Nenhum ofício encontrado com os filtros aplicados.",
            **paginacao,
        },
    )


@require_http_methods(["GET", "POST"])
def novo(request):
    if request.method == "GET":
        return render(
            request,
            "cotton/create_draft.html",
            {
                "page_title": "Novo ofício",
                "page_description": "Confirme para reservar a numeração e iniciar o cadastro.",
                "confirm_label": "Criar ofício",
                "back_url": reverse("oficios:index"),
            },
        )
    evento = resolve_evento_from_request(request)
    oficio = criar_oficio_rascunho(evento=evento)
    return redirect("oficios:dados_viajantes", pk=oficio.pk)


def detalhe(request, pk):
    """Compatibilidade de URLs antigas: a listagem e o fluxo usam apenas o wizard de edição."""
    get_oficio_by_id(pk)
    return redirect("oficios:dados_viajantes", pk=pk)


def editar(request, pk):
    oficio = get_oficio_by_id(pk)
    return redirect("oficios:dados_viajantes", pk=oficio.pk)
