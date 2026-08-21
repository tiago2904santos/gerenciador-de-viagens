from __future__ import annotations
from django.contrib import messages
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_http_methods
from django.views.decorators.http import require_POST
from core.pagination import contexto_paginacao
from core.pagination import KnownCountPaginator
from core.deletion import DelecaoProtegidaError
from eventos.services import resolve_evento_from_request
from core.retorno import com_next
from core.retorno import daqui
from .selectors import hidratar_planos_da_pagina
from .selectors import listar_planos_trabalho
from .presenters import apresentar_plano_card
from .services import criar_plano_rascunho
from .services import excluir_plano
from .view_helpers import _get_plano


def index(request):
    from django.db.models import Q
    from core import documento_abas as tabs

    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    # Situação é MULTISSELEÇÃO e nasce VAZIA (2026-08-21): a lista abre inteira e
    # recortar é escolha de quem lê. Mesmo contrato de Ofícios, Eventos e
    # Roteiros — a aba padrão escondia os outros recortes sem dizer que havia
    # filtro ligado, e a tela abria mentindo o tamanho da lista.
    valores_abas = request.GET.getlist("aba")
    abas_selecionadas = tabs.normalizar_abas(valores_abas) if valores_abas else []
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
    contagem = tabs.contar_por_aba(planos, date_field=date_field, cancelado_q=cancelado_q)
    lista = planos
    if abas_selecionadas:
        lista = planos.filter(
            tabs.q_das_abas(abas_selecionadas, date_field=date_field, cancelado_q=cancelado_q)
        )
    escolhidas = set(abas_selecionadas)
    situacao_options = [
        {
            "value": chave,
            "label": f"{label} ({contagem.get(chave, 0)})",
            "selected": chave in escolhidas,
        }
        for chave, label in tabs.ABA_LABELS
    ]
    # As abas são mutuamente exclusivas E exaustivas, então somar as escolhidas —
    # ou todas, quando nenhuma foi escolhida — dá o total exato, e o
    # `KnownCountPaginator` segue sem pagar um COUNT a mais.
    chaves_contadas = abas_selecionadas or [chave for chave, _ in tabs.ABA_LABELS]
    known_count = sum(contagem.get(chave, 0) for chave in chaves_contadas)

    paginacao = contexto_paginacao(
        lista,
        request,
        20,
        paginator_class=KnownCountPaginator,
        paginator_kwargs={"known_count": known_count},
    )
    page_obj = paginacao["page_obj"]
    objetos_da_pagina = hidratar_planos_da_pagina(page_obj.object_list)
    page_obj.object_list = objetos_da_pagina
    cards = [apresentar_plano_card(plano) for plano in objetos_da_pagina]
    has_filters = any([q, status, viagem_de, viagem_ate, sort, abas_selecionadas])
    return render(
        request,
        "planos_trabalho/index.html",
        {
            "page_title": "Planos de Trabalho",
            "page_description": "Cadastre e gerencie planos de trabalho com numeração própria.",
            "q": q,
            "status": status,
            "abas_selecionadas": abas_selecionadas,
            "situacao_options": situacao_options,
            "viagem_de": viagem_de,
            "viagem_ate": viagem_ate,
            "sort": sort,
            "has_filters": has_filters,
            "cards": cards,
            **paginacao,
            "create_url": reverse("planos_trabalho:novo"),
            # "Limpar" limpa TUDO, inclusive a situação: agora que a lista abre
            # inteira, preservar a aba no limpar devolveria um filtro que quem
            # clicou acabou de pedir para tirar.
            "search_clear_url": reverse("planos_trabalho:index"),
            "programas_url": com_next(reverse("planos_trabalho:programas_index"), daqui(request)),
            "horarios_url": com_next(reverse("planos_trabalho:horarios_index"), daqui(request)),
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
    """A criação é POST, e não tem tela de confirmação (2026-08-19).

    A tela "confirme para criar" existia por uma razão técnica — transformar o
    clique num link (GET) em POST, porque criar RESERVA número. Com o botão da
    lista submetendo um formulário, ela virava um passo a mais para dizer sim ao
    que a pessoa acabou de pedir.

    O GET responde com a lista: quem chega neste endereço pela barra do
    navegador não deve criar nada por isso.
    """
    if request.method == "GET":
        return redirect("planos_trabalho:index")
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
    try:
        excluir_plano(plano)
    except DelecaoProtegidaError as exc:
        messages.error(request, str(exc))
        if evento_id:
            return redirect("eventos:guiado_etapa", pk=evento_id, etapa=4)
        return redirect("planos_trabalho:index")
    messages.success(request, f"Plano de Trabalho {numero} excluído.")
    if evento_id:
        return redirect("eventos:guiado_etapa", pk=evento_id, etapa=4)
    return redirect("planos_trabalho:index")
