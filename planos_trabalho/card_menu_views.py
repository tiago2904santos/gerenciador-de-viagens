"""Menus de ação de um card de Plano de Trabalho, servidos sob demanda (`PF-04`).

A lista mandava o corpo de cada menu no HTML inicial, com `hidden`, quando no
máximo um fica aberto por vez. Agora vai só o gatilho, e o corpo vem daqui no
primeiro clique.

O recorte de área não é escrito aqui de propósito: `get_plano_by_id` já o aplica.
Consulta nova neste módulo repetiria a regra que o `BE-09` centralizou — e o
auditor de arquitetura conta ORM em módulo de view.
"""

from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .presenters import apresentar_plano_card
from .selectors import get_plano_by_id


@require_http_methods(["GET"])
def card_menus(request, pk):
    """Corpos dos menus de um card."""
    card = apresentar_plano_card(get_plano_by_id(pk), menus_sob_demanda=False)
    return render(request, "planos_trabalho/partials/_card_menus.html", {"card": card})
