"""Geração do documento de plano de trabalho (payload canónico + modelo DOCX legado)."""

from __future__ import annotations

import logging

from django.conf import settings as django_settings

from documentos.services.document_cache import build_document_cache_key
from documentos.services.document_cache import build_template_cache_signature
from documentos.services.document_cache import get_cached_document_artifact
from documentos.services.document_cache import read_artifact_file_bytes
from documentos.services.facade import build_default_facade
from documentos.services.pdf_engine import resolve_pdf_engine
from documentos.services.persistence import persist_geracao
from documentos.services.responses import build_download_response
from documentos.services.timing import measure_step
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

from oficios.documents import build_canonical_document_payload
from oficios.models import Oficio

logger = logging.getLogger(__name__)


def _plano_chain() -> tuple[str, ...]:
    explicit = (getattr(django_settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "auto") or "auto").strip().lower()
    return resolve_pdf_engine(explicit_setting=explicit, prefer_docx_pipeline=False).attempt_chain


def _plano_cache_key(oficio: Oficio, formato: DocumentoFormato, payload: dict) -> str:
    reference = f"{oficio.numero_formatado.replace('/', '-')}-plano-trabalho"
    chain = _plano_chain() if formato == DocumentoFormato.PDF else ()
    tpl_sig = build_template_cache_signature(tipo=DocumentoTipo.PLANO_TRABALHO, formato=formato)
    return build_document_cache_key(
        tipo=DocumentoTipo.PLANO_TRABALHO,
        formato=formato,
        reference=reference,
        payload=payload,
        docxtpl_context=None,
        attempt_chain=chain if formato == DocumentoFormato.PDF else (),
        template_signature=tpl_sig,
    )


def gerar_resposta_plano_trabalho_documento(oficio: Oficio, formato: DocumentoFormato):
    """
    Modelo `plano_trabalho.docx` usa placeholders aninhados (ex.: ``{{ oficio.numero_formatado }}``).
    O contexto passado ao docxtpl é o payload canónico; não é necessário ``docxtpl_context`` plano.
    """
    with measure_step(
        "plano_trabalho_gerar_resposta_documento",
        {"oficio_id": oficio.pk, "formato": formato.value},
    ):
        payload = build_canonical_document_payload(oficio, DocumentoTipo.PLANO_TRABALHO)
        reference = f"{oficio.numero_formatado.replace('/', '-')}-plano-trabalho"
        if getattr(django_settings, "DOCUMENTOS_ARTIFACT_CACHE", True):
            ck = _plano_cache_key(oficio, formato, payload)
            art = get_cached_document_artifact(
                oficio_id=oficio.pk,
                tipo=DocumentoTipo.PLANO_TRABALHO,
                formato=formato,
                cache_key=ck,
            )
            if art is not None:
                content = read_artifact_file_bytes(art)
                response = build_download_response(
                    content=content,
                    tipo=DocumentoTipo.PLANO_TRABALHO,
                    formato=formato,
                    reference=reference,
                    cache_hit=True,
                )
                response["X-Document-SHA256"] = art.hash_sha256
                return response
        cache_key = _plano_cache_key(oficio, formato, payload)
        facade = build_default_facade()
        doc = facade.gerar(
            tipo=DocumentoTipo.PLANO_TRABALHO,
            formato=formato,
            payload=payload,
            reference=reference,
        )
        response = build_download_response(
            content=doc.conteudo,
            tipo=DocumentoTipo.PLANO_TRABALHO,
            formato=formato,
            reference=reference,
            cache_hit=False,
        )
        response["X-Document-SHA256"] = doc.hash_sha256
        try:
            persist_geracao(
                doc,
                oficio_id=oficio.pk,
                payload_snapshot=payload,
                cache_key=cache_key,
                engine=doc.pdf_engine_used or "",
            )
        except Exception:
            logger.exception("Não foi possível persistir artefato de plano de trabalho.")
        return response
