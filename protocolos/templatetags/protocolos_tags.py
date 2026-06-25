"""Template tags da Central de Protocolos."""

from __future__ import annotations

from django import template

register = template.Library()


@register.simple_tag
def bloco_protocolo(documento):
    """Mantem compatibilidade com templates antigos sem renderizar o bloco."""
    return ""
