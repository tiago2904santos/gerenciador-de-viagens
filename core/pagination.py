"""Paginação compartilhada das listas em cards.

Toda lista que usa ``cotton/lists/list_page_cards.html`` é paginada: o
componente de paginação declara ``paginacao_obrigatoria`` e denuncia na tela a
ausência de ``page_obj`` em vez de sumir em silêncio (defeito N-07).

``contexto_paginacao`` devolve as três chaves que o componente consome, prontas
para desempacotar no dicionário da view:

    return render(request, "oficios/index.html", {
        ...,
        **contexto_paginacao(lista, request, OFICIOS_POR_PAGINA),
    })

``page_querystring`` preserva os filtros da URL (busca, aba, período, ordenação)
menos o próprio ``page``, para que navegar entre páginas não descarte o filtro.
"""
from django.core.paginator import Paginator


def paginas_elididas(page_obj, *, on_each_side=1, on_ends=1):
    """Faixa de páginas com reticências, para listas com muitas páginas."""
    return [
        numero if isinstance(numero, int) else "..."
        for numero in page_obj.paginator.get_elided_page_range(
            page_obj.number,
            on_each_side=on_each_side,
            on_ends=on_ends,
        )
    ]


def contexto_paginacao(queryset, request, por_pagina):
    page_obj = Paginator(queryset, por_pagina).get_page(request.GET.get("page"))
    querystring = request.GET.copy()
    querystring.pop("page", None)
    return {
        "page_obj": page_obj,
        "pagination_pages": paginas_elididas(page_obj),
        "page_querystring": querystring.urlencode(),
    }
