"""
Estado de geração documental para UX (cache PDF, motor, disponibilidade).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings

from documentos.services.document_cache import build_document_cache_key
from documentos.services.document_cache import build_template_cache_signature
from documentos.services.document_cache import get_cached_document_artifact
from documentos.services.pdf_engine import resolve_pdf_engine
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

from oficios.documents import build_canonical_document_payload
from oficios.docxtpl_context import build_oficio_docxtpl_context
from oficios.models import Oficio


@dataclass(frozen=True)
class DocumentGenerationStatus:
    docx_available: bool
    pdf_available: bool
    pdf_cached: bool
    pdf_engine: str
    pdf_message: str
    last_generated_at: str | None
    cache_status: str


def get_document_generation_status(oficio: Oficio) -> dict[str, Any]:
    from oficios.services import validar_oficio_para_documento

    pend = list(validar_oficio_para_documento(oficio).get("pendencias") or [])
    complete = not pend
    docx_available = complete

    explicit = (getattr(settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "auto") or "auto").strip().lower()
    resolution = resolve_pdf_engine(explicit_setting=explicit, prefer_docx_pipeline=True)
    pdf_available = bool(resolution.attempt_chain)
    pdf_engine = ",".join(resolution.attempt_chain) if resolution.attempt_chain else "—"

    pdf_cached = False
    cache_status = "n/a"
    last_generated_at: str | None = None
    art_cached: Any = None

    if complete and pdf_available and getattr(settings, "DOCUMENTOS_ARTIFACT_CACHE", True):
        payload = build_canonical_document_payload(oficio, DocumentoTipo.OFICIO)
        docxtpl = build_oficio_docxtpl_context(oficio)
        reference = oficio.numero_formatado.replace("/", "-")
        tpl_sig = build_template_cache_signature(tipo=DocumentoTipo.OFICIO, formato=DocumentoFormato.PDF)
        key = build_document_cache_key(
            tipo=DocumentoTipo.OFICIO,
            formato=DocumentoFormato.PDF,
            reference=reference,
            payload=payload,
            docxtpl_context=docxtpl,
            attempt_chain=resolution.attempt_chain,
            template_signature=tpl_sig,
        )
        art_cached = get_cached_document_artifact(
            oficio_id=oficio.pk,
            tipo=DocumentoTipo.OFICIO,
            formato=DocumentoFormato.PDF,
            cache_key=key,
        )
        pdf_cached = art_cached is not None
        cache_status = "HIT" if pdf_cached else "MISS"
        if art_cached is not None and art_cached.criado_em:
            last_generated_at = art_cached.criado_em.isoformat()

    # Cache MISS ainda pode haver PDF persistido (ex.: gerado antes sem bater a chave atual):
    # expõe o último artefato para a barra "Assinar / Verificar" do wizard.
    if (
        art_cached is None
        and complete
        and pdf_available
        and getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False)
    ):
        from documentos.selectors import get_latest_artefato_pdf_for_oficio

        from documentos.services.warm_cache import pdf_artefato_original_acessivel

        cand = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.OFICIO.value)
        if cand is not None and pdf_artefato_original_acessivel(cand):
            art_cached = cand

    if not pdf_available:
        pdf_message = "PDF indisponível: configure Word, LibreOffice ou unoserver."
    elif pdf_cached:
        pdf_message = "PDF pronto."
    else:
        pdf_message = "Pode levar alguns segundos na primeira geração."

    st = DocumentGenerationStatus(
        docx_available=docx_available,
        pdf_available=pdf_available,
        pdf_cached=pdf_cached,
        pdf_engine=pdf_engine,
        pdf_message=pdf_message,
        last_generated_at=last_generated_at,
        cache_status=cache_status,
    )
    out: dict[str, Any] = {
        "docx_available": st.docx_available,
        "pdf_available": st.pdf_available,
        "pdf_cached": st.pdf_cached,
        "pdf_engine": st.pdf_engine,
        "pdf_message": st.pdf_message,
        "last_generated_at": st.last_generated_at,
        "cache_status": st.cache_status,
        "pdf_link_label": "PDF" if st.pdf_cached else "Gerar PDF",
        "documentos_persist_artefatos": bool(getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False)),
        "oficio_pdf_botoes_assinatura": bool(
            complete
            and pdf_available
            and getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False),
        ),
    }
    if art_cached is not None:
        out["oficio_pdf_artefato_id"] = str(art_cached.pk)
        has_signed = False
        try:
            # `DocumentoArtefato` não guarda mais uma versão assinada embutida,
            # mas mantemos este cálculo compatível com instalações antigas.
            ass = getattr(art_cached, "arquivo_assinado", None)
            if ass and getattr(ass, "name", ""):
                has_signed = bool(ass.storage.exists(ass.name))
        except OSError:
            has_signed = False
        out["oficio_pdf_signature_status"] = "signed" if has_signed else "unsigned"
    return out
