"""Menus de ação de um card de Evento, servidos sob demanda (`PF-04`).

São quatro famílias por card — rodapé, uma por ofício vinculado, uma por documento
e uma por servidor com termo —, todas com `hidden` no HTML inicial, quando no
máximo uma fica aberta por vez.

O recorte de área não é escrito aqui de propósito: `get_evento_by_id` já o aplica.
Consulta nova neste módulo repetiria a regra que o `BE-09` centralizou — e o
auditor de arquitetura conta ORM em módulo de view.
"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .presenters import apresentar_evento_list_card
from .selectors import get_evento_by_id


@require_http_methods(["GET"])
def card_menus(request, pk):
    """Corpos dos menus de um card, todos de uma vez."""
    card = apresentar_evento_list_card(get_evento_by_id(pk), menus_sob_demanda=False)
    return render(request, "eventos/partials/_card_menus.html", {"card": card})
