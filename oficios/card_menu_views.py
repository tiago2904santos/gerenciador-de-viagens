"""Menus de ação de um card de Ofício, servidos sob demanda (`PF-04`).

A lista mandava 3 menus por card — 60 para 20 cards — todos com `hidden`, quando
no máximo um fica aberto por vez. Medido em `oficios:index`, volume 200: 151,2 KB
de 315,3 (48% da página), 1.960 dos 3.636 nós de elemento (54%) e 51,7 ms dos
133,8 ms de servidor (39%).

Agora a lista manda só os gatilhos, e o corpo vem daqui no primeiro clique.

O recorte de área não é escrito aqui de propósito: `get_oficio_by_id` já passa por
`filter_queryset_by_area` e devolve 404 fora da área. Escrever consulta nova neste
módulo seria repetir a regra que o `BE-09` gastou dias para centralizar — e o
auditor de arquitetura conta ORM em módulo de view.
"""

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .presenters import apresentar_oficio_card
from .selectors import get_oficio_by_id


@require_http_methods(["GET"])
def card_menus(request, pk):
    """Corpos dos menus de um card, todos de uma vez.

    De uma vez, e não um por requisição, porque quem abre "Documentos" costuma
    abrir "Mais ações" em seguida: assim é uma viagem, não duas.

    `menus_sob_demanda=False` faz o presenter devolver os menus sem `src`, que é
    o que manda o componente renderizar o corpo em vez do gatilho.

    `excluir_next_url` precisa ser o mesmo que a lista passa: é ele que faz o
    "Excluir" voltar para a lista em vez de para a raiz. Esquecê-lo aqui não
    quebra nada visível — só manda o usuário para outro lugar depois de excluir —,
    e foi o `test_index_usa_modal_para_excluir_oficio` que pegou.
    """
    oficio = get_oficio_by_id(pk)
    card = apresentar_oficio_card(
        oficio,
        excluir_next_url=reverse("oficios:index"),
        menus_sob_demanda=False,
    )
    return render(request, "oficios/partials/_card_menus.html", {"card": card})
