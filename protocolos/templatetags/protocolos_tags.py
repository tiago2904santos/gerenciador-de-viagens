"""Template tags da Central de Protocolos.

Fornece o bloco compacto de integração eProtocolo reutilizável nos detalhes/
resumos dos documentos (Ofício, Termo, Justificativa, Plano de Trabalho, Ordem
de Serviço), sem duplicar a Central de Protocolos dentro de cada módulo.

Uso no template de um documento:
    {% load protocolos_tags %}
    {% bloco_protocolo documento %}
"""

from __future__ import annotations

from django import template
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.http import urlencode

from integracoes.eprotocolo import settings as epro_cfg

from ..models import Protocolo

register = template.Library()


@register.inclusion_tag("protocolos/partials/bloco_compacto.html")
def bloco_protocolo(documento):
    """Renderiza o bloco compacto de integração para ``documento``."""
    protocolo = None
    gerar_url = None
    if documento is not None and getattr(documento, "pk", None):
        ct = ContentType.objects.get_for_model(documento.__class__)
        protocolo = (
            Protocolo.objects.filter(
                origem_content_type=ct, origem_object_id=documento.pk, ativo=True
            )
            .order_by("-criado_no_sistema_em")
            .first()
        )
        query = urlencode({
            "content_type_id": ct.id,
            "object_id": documento.pk,
            "enviar_documento": "1",
        })
        gerar_url = f"{reverse('protocolos:vincular')}?{query}"
    return {
        "protocolo": protocolo,
        "gerar_url": gerar_url,
        "eprotocolo_configurado": epro_cfg.eprotocolo_esta_configurado(),
        "eprotocolo_descricao": epro_cfg.descricao_ambiente(),
        "eprotocolo_modo_demo": epro_cfg.em_modo_mock(),
    }
