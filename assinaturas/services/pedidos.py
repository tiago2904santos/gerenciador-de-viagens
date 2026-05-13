from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import transaction
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from assinaturas.models import PedidoAssinaturaDocumento
from assinaturas.services.hash import calcular_sha256_bytes
from assinaturas.services.resolvedores import resolver_assinante_para_artefato
from documentos.models import DocumentoArtefato


def _gerar_token() -> str:
    while True:
        token = secrets.token_urlsafe(36)
        if not PedidoAssinaturaDocumento.objects.filter(token=token).exists():
            return token


def _hash_original(artefato: DocumentoArtefato) -> str:
    if (artefato.hash_sha256 or "").strip():
        return artefato.hash_sha256
    if not artefato.arquivo or not getattr(artefato.arquivo, "name", ""):
        return ""
    artefato.arquivo.open("rb")
    try:
        return calcular_sha256_bytes(artefato.arquivo.read())
    finally:
        artefato.arquivo.close()


def _request_auditoria(request: HttpRequest | None) -> dict:
    if request is None:
        return {}
    return {
        "ip_criacao": request.META.get("REMOTE_ADDR") or "",
        "user_agent_criacao": (request.META.get("HTTP_USER_AGENT") or "")[:4000],
    }


@transaction.atomic
def criar_ou_obter_pedido_assinatura(
    artefato: DocumentoArtefato,
    *,
    criado_por=None,
    request: HttpRequest | None = None,
    forcar_novo: bool = False,
) -> PedidoAssinaturaDocumento:
    now = timezone.now()
    abertos = PedidoAssinaturaDocumento.objects.select_for_update().filter(
        artefato=artefato,
        status__in=[
            PedidoAssinaturaDocumento.STATUS_PENDENTE,
            PedidoAssinaturaDocumento.STATUS_VISUALIZADA,
        ],
    )
    if not forcar_novo:
        existente = abertos.filter(expira_em__gt=now).order_by("-criado_em").first()
        if existente is not None:
            return existente

    abertos.update(status=PedidoAssinaturaDocumento.STATUS_SUBSTITUIDO if forcar_novo else PedidoAssinaturaDocumento.STATUS_EXPIRADO)

    assinante = resolver_assinante_para_artefato(artefato)
    auditoria = _request_auditoria(request)
    auditoria.update(
        {
            "assinante_origem": "cadastros.AssinaturaConfiguracao",
            "hash_documento_original": _hash_original(artefato),
        }
    )
    return PedidoAssinaturaDocumento.objects.create(
        artefato=artefato,
        token=_gerar_token(),
        assinante_usuario=assinante.usuario,
        assinante_servidor=assinante.servidor,
        nome_assinante_snapshot=assinante.nome[:160],
        cpf_assinante_snapshot=assinante.cpf[:14],
        email_assinante_snapshot=assinante.email[:254],
        cargo_assinante_snapshot=assinante.cargo[:160],
        unidade_assinante_snapshot=assinante.unidade[:160],
        tipo_documento=(artefato.tipo or "")[:64],
        criado_por=criado_por if getattr(criado_por, "is_authenticated", False) else None,
        expira_em=now + timedelta(days=7),
        hash_documento_original=auditoria["hash_documento_original"],
        auditoria=auditoria,
    )


def url_publica_pedido_assinatura(request: HttpRequest | None, pedido: PedidoAssinaturaDocumento) -> str:
    rel = reverse("assinaturas:assinatura-token", kwargs={"token": pedido.token})
    if request is not None:
        return request.build_absolute_uri(rel)
    return rel
