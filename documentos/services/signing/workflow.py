"""Fluxo de assinatura de artefatos (reutilizável por views de página e download)."""

from __future__ import annotations

import io
from typing import Any

from django.http import HttpRequest
from django.urls import reverse

from assinaturas.services.recording import registrar_assinatura_concluida

from documentos.models import DocumentoArtefato
from documentos.services.access import ensure_request_may_view_artefato_pdf
from documentos.services.persistence import atualizar_apos_assinatura
from documentos.services.signing import assinar_pdf_final
from documentos.services.signing.label_overlay import aplicar_etiqueta_assinatura_pdf
from documentos.services.signing.position import SignaturePositionNormalizada

from pypdf import PdfReader


def _read_artefato_pdf_bytes(artefato: DocumentoArtefato) -> bytes:
    """
    Lê o PDF persistido desde o início do ficheiro.

    O `FieldFile` do Django mantém o cursor após `read()`; a view chama
    `contar_paginas_pdf_artefato` antes de `assinar_artefato_pdf`, logo sem
    `seek(0)` a segunda leitura devolve bytes vazios e o motor de assinatura
    falha (ex.: "Cannot read an empty file").
    """
    f = artefato.arquivo
    try:
        if hasattr(f, "seek"):
            f.seek(0)
    except (OSError, ValueError, io.UnsupportedOperation):
        pass
    return f.read()


def _nome_assinante(request: HttpRequest) -> str:
    u = getattr(request, "user", None)
    if u is None or not getattr(u, "is_authenticated", False):
        return ""
    full = (getattr(u, "get_full_name", lambda: "")() or "").strip()
    if full:
        return full
    return (getattr(u, "get_username", lambda: "")() or "").strip()


def _url_verificacao_artefato(request: HttpRequest, artefato: DocumentoArtefato) -> str:
    rel = reverse("documentos:artefato_pdf_visualizar", args=[artefato.pk])
    return request.build_absolute_uri(rel)


def assinar_artefato_pdf(
    request: HttpRequest,
    artefato: DocumentoArtefato,
    *,
    signature_position: SignaturePositionNormalizada | None = None,
) -> dict[str, Any]:
    """
    Valida permissão, opcionalmente aplica etiqueta visual, assina o PDF, persiste `arquivo_assinado`
    e regista auditoria.
    """
    ensure_request_may_view_artefato_pdf(request, artefato)
    pdf_bytes = _read_artefato_pdf_bytes(artefato)
    stamp_meta: dict[str, Any] = {}
    if signature_position is not None:
        pdf_bytes, stamp_meta = aplicar_etiqueta_assinatura_pdf(
            pdf_bytes,
            signature_position,
            signer_name=_nome_assinante(request),
            verification_url=_url_verificacao_artefato(request, artefato),
            code_short="",
        )
    pos_audit = signature_position.to_audit_dict() if signature_position else None
    signed, meta = assinar_pdf_final(pdf_bytes, signature_position=pos_audit)
    meta.update(stamp_meta)
    atualizar_apos_assinatura(artefato, pdf_assinado=signed, backend=str(meta.get("backend", "")))
    registrar_assinatura_concluida(artefato, meta)
    return {"pdf_bytes": signed, "meta": meta, "backend": str(meta.get("backend", ""))}


def contar_paginas_pdf_artefato(artefato: DocumentoArtefato) -> int:
    """Número de páginas do PDF original persistido (para normalizar sig_page)."""
    try:
        raw = _read_artefato_pdf_bytes(artefato)
        return max(1, len(PdfReader(io.BytesIO(raw)).pages))
    except Exception:
        return 1
