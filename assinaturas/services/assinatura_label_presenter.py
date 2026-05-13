from __future__ import annotations

from typing import Any

from django.utils import timezone

from assinaturas.models import PedidoAssinaturaDocumento
from assinaturas.services.assinatura_artefato import mascarar_cpf_assinatura


ORGANIZATION_LABEL = "Central de Viagens - PCPR"


def _document_number_label(pedido: PedidoAssinaturaDocumento) -> str:
    artefato = pedido.artefato
    oficio = getattr(artefato, "oficio", None)
    if oficio is not None:
        numero = getattr(oficio, "numero_formatado", "") or ""
        if numero:
            return numero
    snapshot = artefato.payload_snapshot or {}
    for key in ("numero_formatado", "numero", "documento_numero"):
        value = snapshot.get(key)
        if value:
            return str(value)
    return ""


def _document_subject(pedido: PedidoAssinaturaDocumento) -> str:
    artefato = pedido.artefato
    oficio = getattr(artefato, "oficio", None)
    if oficio is not None:
        for attr in ("assunto", "motivo"):
            value = getattr(oficio, attr, "") or ""
            if value:
                return str(value)
    snapshot = artefato.payload_snapshot or {}
    for key in ("assunto", "motivo", "resumo"):
        value = snapshot.get(key)
        if value:
            return str(value)
    return ""


def _document_year(pedido: PedidoAssinaturaDocumento) -> str:
    oficio = getattr(pedido.artefato, "oficio", None)
    if oficio is not None and getattr(oficio, "ano", None):
        return str(oficio.ano)
    snapshot = pedido.artefato.payload_snapshot or {}
    value = snapshot.get("ano") or snapshot.get("year")
    return str(value) if value else ""


def build_signature_label_context(
    pedido: PedidoAssinaturaDocumento,
    *,
    signed: bool = False,
) -> dict[str, Any]:
    assinatura = pedido.assinatura
    document_number = _document_number_label(pedido)
    document_label = pedido.tipo_documento.replace("_", " ").title()
    if document_number:
        document_label = f"{document_label} {document_number}"
    signed_at = pedido.assinado_em or (assinatura.criado_em if assinatura else None)
    return {
        "title": "DOCUMENTO ASSINADO ELETRONICAMENTE" if signed else "DOCUMENTO A SER ASSINADO ELETRONICAMENTE",
        "signer_name": pedido.nome_assinante_snapshot or "-",
        "signer_cpf_masked": mascarar_cpf_assinatura(pedido.cpf_assinante_snapshot),
        "signer_role": pedido.cargo_assinante_snapshot or "",
        "document_label": document_label,
        "status_label": "assinado" if signed else "aguardando confirmacao",
        "verification_code": assinatura.codigo_verificacao if signed and assinatura else "sera gerado apos assinatura",
        "signed_at": timezone.localtime(signed_at).strftime("%d/%m/%Y %H:%M:%S") if signed_at else "",
        "hash_short": (pedido.hash_documento_assinado or pedido.hash_documento_original or "")[:12],
        "organization_label": ORGANIZATION_LABEL,
    }


def build_signature_public_context(pedido: PedidoAssinaturaDocumento) -> dict[str, Any]:
    artefato = pedido.artefato
    oficio = getattr(artefato, "oficio", None)
    document_number = _document_number_label(pedido)
    document_type = pedido.tipo_documento.replace("_", " ").title()
    public_code = f"AS-{pedido.criado_em:%Y}-{str(pedido.id)[:8].upper()}"
    return {
        "document_type": document_type,
        "document_number": document_number,
        "document_year": _document_year(pedido),
        "document_subject": _document_subject(pedido),
        "document_label": f"{document_type} {document_number}".strip(),
        "issuer_label": "Polícia Civil do Paraná",
        "issuer_unit": pedido.unidade_assinante_snapshot or "Central de Viagens",
        "signer_name": pedido.nome_assinante_snapshot,
        "signer_cpf_masked": mascarar_cpf_assinatura(pedido.cpf_assinante_snapshot),
        "signer_role": pedido.cargo_assinante_snapshot,
        "status_label": pedido.get_status_display(),
        "expires_at": pedido.expira_em,
        "public_code": public_code,
        "original_hash": pedido.hash_documento_original or artefato.hash_sha256,
        "created_at": pedido.criado_em,
        "linked_document": str(artefato),
        "linked_oficio": getattr(oficio, "numero_formatado", "") if oficio is not None else "",
        "internal_responsible": getattr(pedido.criado_por, "get_full_name", lambda: "")() or getattr(pedido.criado_por, "username", "") if pedido.criado_por_id else "",
        "signature_method": "Assinatura eletrônica por link com token seguro",
    }
