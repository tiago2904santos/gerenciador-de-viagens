"""Menus de ação de um card de prestação, servidos sob demanda (`PF-04`).

Duas famílias por servidor — baixar documentos e o aviso de liberação por
WhatsApp —, ambas com `hidden` no HTML inicial.

Este domínio não tinha selector de registro único: a lista sempre pediu página
inteira. `get_servidor_prestacao_by_id` nasceu aqui, reusando
`_filter_servidores_by_area` em vez de escrever filtro novo — `PrestacaoServidor.
objects` filtra removidos mas **não** recorta por área, e errar isso desfaria o
`BE-09` por uma URL.
"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .presenters import apresentar_prestacao_servidor_card
from .selectors import get_servidor_prestacao_by_id


@require_http_methods(["GET"])
def card_menus(request, pk):
    """Corpos dos menus de um card de servidor da prestação."""
    ps = get_servidor_prestacao_by_id(pk)
    card = apresentar_prestacao_servidor_card(ps, menus_sob_demanda=False)
    return render(request, "prestacoes_contas/partials/_card_menus.html", {"card": card})
