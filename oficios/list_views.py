from django.db.models import Q
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from core.pagination import contexto_paginacao
from core.pagination import KnownCountPaginator
from eventos.services import resolve_evento_from_request
from .presenters import apresentar_oficio_card
from .card_rendering import renderizar_oficio_card_cacheado
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
    # Situação é MULTISSELEÇÃO e nasce VAZIA, como em Eventos: a lista abre
    # inteira e recortar é escolha de quem lê. A aba padrão (`futuras`) escondia
    # os outros três recortes sem que ninguém tivesse pedido filtro nenhum, e a
    # tela abria mentindo o tamanho da lista.
    valores_abas = request.GET.getlist("aba")
    abas_selecionadas = tabs.normalizar_abas(valores_abas) if valores_abas else []
    criacao_de  = request.GET.get("criacao_de", "").strip()
    criacao_ate = request.GET.get("criacao_ate","").strip()
    viagem_de   = request.GET.get("viagem_de",  "").strip()
    viagem_ate  = request.GET.get("viagem_ate", "").strip()
    sort        = request.GET.get("sort",       "").strip()

    base = listar_oficios(
        q=q or None,
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

    contagem = tabs.contar_por_aba(base, date_field=date_field, cancelado_q=cancelado_q)
    oficios = base
    if abas_selecionadas:
        oficios = base.filter(
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
    # As abas são mutuamente exclusivas E exaustivas (garantido por
    # `test_abas_sao_mutuamente_exclusivas_e_exaustivas`), então somar as
    # escolhidas — ou todas, quando nenhuma foi escolhida — dá o total exato. É
    # o que mantém o `KnownCountPaginator` sem pagar um COUNT a mais agora que a
    # lista abre inteira.
    chaves_contadas = abas_selecionadas or [chave for chave, _ in tabs.ABA_LABELS]
    known_count = sum(contagem.get(chave, 0) for chave in chaves_contadas)
    paginacao = contexto_paginacao(
        oficios,
        request,
        OFICIOS_POR_PAGINA,
        paginator_class=KnownCountPaginator,
        paginator_kwargs={"known_count": known_count},
    )
    objetos_da_pagina = hidratar_oficios_da_pagina(paginacao["page_obj"].object_list)
    paginacao["page_obj"].object_list = objetos_da_pagina
    cards = []
    for oficio in objetos_da_pagina:
        cards.append(apresentar_oficio_card(oficio, excluir_next_url=reverse("oficios:index")))
    for card in cards:
        card["rendered_html"] = renderizar_oficio_card_cacheado(card)

    has_filters = any(
        [q, criacao_de, criacao_ate, viagem_de, viagem_ate, sort, abas_selecionadas]
    )

    return render(
        request,
        "oficios/index.html",
        {
            "page_title": "Ofícios",
            "q":           q,
            "abas_selecionadas": abas_selecionadas,
            "situacao_options": situacao_options,
            "criacao_de":  criacao_de,
            "criacao_ate": criacao_ate,
            "viagem_de":   viagem_de,
            "viagem_ate":  viagem_ate,
            "sort":        sort,
            "has_filters": has_filters,
            "cards":       cards,
            "create_url":  reverse("oficios:novo"),
            "search_clear_url": reverse("oficios:index"),
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
    """A criação é POST, e não tem tela de confirmação (2026-08-19).

    A tela "confirme para criar" existia por uma razão técnica — transformar o
    clique num link (GET) em POST, porque criar RESERVA número. Com o botão da
    lista submetendo um formulário, ela virava um passo a mais para dizer sim ao
    que a pessoa acabou de pedir.

    O GET responde com a lista: quem chega neste endereço pela barra do
    navegador não deve criar nada por isso.
    """
    if request.method == "GET":
        return redirect("oficios:index")
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
