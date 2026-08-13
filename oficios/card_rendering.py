"""Renderização quente dos cards de Ofícios, separada do presenter de dados."""

import hashlib
import json

from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe


def renderizar_oficio_card_cacheado(card):
    """Renderiza novamente só quando algum conteúdo apresentado mudar."""
    payload = json.dumps(
        card,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.blake2s(payload, digest_size=16).hexdigest()
    key = f"oficios:list-card:v1:{digest}"
    html = cache.get(key)
    if html is None:
        html = render_to_string("oficios/partials/oficio_list_card.html", {"card": card})
        cache.set(key, html, timeout=3600)
    # O valor só entra no cache depois de o template Django escapar os dados.
    return mark_safe(html)
