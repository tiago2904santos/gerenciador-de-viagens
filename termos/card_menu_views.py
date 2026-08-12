"""Menus de ação de um card de Termo, servidos sob demanda (`PF-04`).

A lista mandava 5 menus por card — um no rodapé e um por linha (servidores mais a
viatura) —, todos com `hidden`.

O card de termo é montado com uma dúzia de argumentos, e escrevê-los de novo aqui
faria o menu poder divergir da lista sem ninguém notar. Por isso o endpoint chama
`montar_card_de_termo`, o mesmo helper que a lista usa, só trocando
`menus_sob_demanda`.

O recorte de área vem de `get_termo_by_id`; consulta nova neste módulo repetiria a
regra que o `BE-09` centralizou.
"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .card_builder import montar_card_de_termo
from .selectors import get_termo_by_id


@require_http_methods(["GET"])
def card_menus(request, pk):
    """Corpos dos menus de um card, todos de uma vez."""
    termo = get_termo_by_id(pk)
    card = montar_card_de_termo(termo, menus_sob_demanda=False)
    return render(request, "termos/partials/_card_menus.html", {"card": card})
