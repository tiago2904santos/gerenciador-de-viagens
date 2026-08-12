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
from urllib.parse import urlencode

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


def contexto_paginacao(
    queryset,
    request,
    por_pagina,
    *,
    paginator_class=Paginator,
    paginator_kwargs=None,
    query_params=None,
):
    """Pagina uma coleção e preserva o contrato único do componente.

    ``paginator_class``/``paginator_kwargs`` mantêm casos especializados, como o
    total já agregado dos Termos. ``query_params`` permite preservar exatamente
    os filtros reconhecidos pela tela; omitido, copia o GET menos ``page``.
    """
    paginator = paginator_class(
        queryset,
        por_pagina,
        **(paginator_kwargs or {}),
    )
    page_obj = paginator.get_page(request.GET.get("page"))
    if query_params is None:
        querystring = request.GET.copy()
        querystring.pop("page", None)
        page_querystring = querystring.urlencode()
    else:
        page_querystring = urlencode(
            {chave: valor for chave, valor in query_params.items() if valor not in (None, "")}
        )
    return {
        "page_obj": page_obj,
        "pagination_pages": paginas_elididas(page_obj),
        "page_querystring": page_querystring,
    }
