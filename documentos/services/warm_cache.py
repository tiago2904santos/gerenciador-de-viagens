"""
Pré-materialização de artefatos (ex.: PDF) quando o ofício está completo — sem Celery.
"""

from __future__ import annotations

import logging

from django.conf import settings

from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

logger = logging.getLogger(__name__)


def pdf_artefato_original_acessivel(artefato) -> bool:
    arq = getattr(artefato, "arquivo", None)
    if arq is None or not getattr(arq, "name", ""):
        return False
    try:
        return bool(arq.storage.exists(arq.name))
    except OSError:
        return False


def ensure_document_artifact_cached(oficio, *, tipo: DocumentoTipo = DocumentoTipo.OFICIO) -> None:
    """
    Garante PDF em cache para o ofício completo (best-effort; falhas de motor não rebentam a view).

    Em `dev.py` a pré-geração global pode estar desligada (`DOCUMENTOS_PREGENERATE_PDF=false`)
    para não bloquear o GET; com persistência de artefatos ativa ainda assim tentamos **uma**
    geração quando não existe `DocumentoArtefato` PDF válido, para o wizard mostrar Assinar/Verificar.
    """
    pre = getattr(settings, "DOCUMENTOS_PREGENERATE_PDF", True)
    persist = getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False)

    need_warm = bool(pre)
    if not need_warm and persist and tipo == DocumentoTipo.OFICIO:
        from documentos.selectors import get_latest_artefato_pdf_for_oficio

        latest = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.OFICIO.value)
        if latest is None or not pdf_artefato_original_acessivel(latest):
            need_warm = True

    if not need_warm:
        return None

    from oficios.services import validar_oficio_para_documento

    if validar_oficio_para_documento(oficio).get("pendencias"):
        return None
    try:
        if tipo == DocumentoTipo.OFICIO:
            from oficios.services import gerar_resposta_documento_oficio

            gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF)
    except Exception:
        logger.warning(
            "Pré-geração PDF ignorada (motor ou dados). O download tentará de novo.",
            exc_info=True,
        )
    return None
