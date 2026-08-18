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
    # A versão sobe SEMPRE que o desenho do cartão muda: o digest é do dado, e
    # sem isso a lista serviria o HTML antigo até o próprio ofício mudar.
    # v2 (2026-08-18): cartão migrado para as peças do v2.
    key = f"oficios:list-card:v2:{digest}"
    html = cache.get(key)
    if html is None:
        html = render_to_string("oficios/partials/oficio_list_card.html", {"card": card})
        cache.set(key, html, timeout=3600)
    # O valor só entra no cache depois de o template Django escapar os dados.
    return mark_safe(html)
