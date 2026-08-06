"""
Chave de cache e leitura de artefatos documentais já persistidos (PDF/DOCX).

A chave incorpora tipo, formato, referência, inputs (payload + docxtpl), templates
e cadeia de motores PDF resolvida — não basta `updated_at` do Ofício.
"""

from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from django.conf import settings

from documentos.models import DocumentoArtefato
from documentos.services.resources_paths import resolve_resource_docx
from documentos.services.templates import default_template_registry
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

logger = logging.getLogger(__name__)


def _json_default(o: object) -> str:
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (bytes, memoryview)):
        return bytes(o).hex()[:128]
    return str(o)


def canonical_json_blob(data: Mapping[str, Any] | None) -> str:
    if not data:
        return "{}"
    return json.dumps(data, sort_keys=True, separators=(",", ":"), default=_json_default)


def _file_fp(path: Path) -> str:
    try:
        st = path.stat()
        return f"{path.resolve()}:{st.st_mtime_ns}:{st.st_size}"
    except OSError:
        return f"{path}:missing"


def build_template_cache_signature(
    *,
    tipo: DocumentoTipo,
    formato: DocumentoFormato,
    docx_template_path: str | None = None,
) -> str:
    """DOCX + (para PDF) HTML e CSS registados — invalida cache quando o modelo muda."""
    parts: list[str] = []
    docx_def = default_template_registry.get(tipo, DocumentoFormato.DOCX)
    parts.append(
        _file_fp(
            resolve_resource_docx(
                docx_template_path or docx_def.template_path,
            )
        )
    )
    if formato == DocumentoFormato.PDF:
        html_def = default_template_registry.get(tipo, DocumentoFormato.PDF)
        base = Path(settings.BASE_DIR)
        parts.append(_file_fp(base / html_def.template_path))
        for rel in html_def.stylesheet_paths:
            parts.append(_file_fp(base / rel))
    return "|".join(parts)


def build_document_cache_key(
    *,
    tipo: DocumentoTipo,
    formato: DocumentoFormato,
    reference: str | None,
    payload: Mapping[str, Any],
    docxtpl_context: Mapping[str, Any] | None,
    attempt_chain: tuple[str, ...] | None,
    template_signature: str,
) -> str:
    """
    Gera chave estável (hex SHA-256 truncada a 128 chars) para bater com `DocumentoArtefato.cache_key`.
    """
    gen_ver = str(getattr(settings, "DOCUMENTOS_GENERATOR_VERSION", "1") or "1")
    chain = ",".join(attempt_chain or ()) if attempt_chain is not None else ""

    parts = "|".join(
        [
            gen_ver,
            tipo.value,
            formato.value,
            (reference or "").strip(),
            canonical_json_blob(dict(payload)),
            canonical_json_blob(dict(docxtpl_context or {})),
            template_signature,
            chain,
        ],
    )
    return hashlib.sha256(parts.encode("utf-8")).hexdigest()[:128]


def get_cached_document_artifact(
    *,
    oficio_id: int | None = None,
    evento_id: int | None = None,
    termo_id: int | None = None,
    servidor_id: int | None = None,
    tipo: DocumentoTipo,
    formato: DocumentoFormato,
    cache_key: str,
) -> DocumentoArtefato | None:
    # `DB-04`: pelo menos uma referencia e **obrigatoria**.
    #
    # A `cache_key` e um SHA-256 de conteudo (`build_cache_key`, acima) e nao
    # inclui area: dois oficios de areas diferentes com o mesmo conteudo
    # produzem a mesma chave. Quem separa as areas aqui e a **referencia** — um
    # oficio pertence a uma area so, entao filtrar por `oficio_id` implica
    # filtrar por area, transitivamente.
    #
    # Os cinco chamadores de hoje passam referencia, e por isso o catalogo
    # classificou este defeito como latente. O problema e que nada os obrigava:
    # sem referencia, `filters` ficava so com tipo, formato e chave, e a busca
    # varria o sistema inteiro por hash de conteudo — o primeiro artefato que
    # casasse voltava, de qualquer area.
    #
    # Recusar a chamada e melhor que recortar por `get_current_area()`: a
    # geracao documental roda **assincrona** em worker do Celery
    # (`documentos/services/async_generation.py`), onde nao existe area
    # ambiente. Um recorte por estado ambiente ficaria correto no request e
    # devolveria `None` sempre na worker, transformando cache em nada — de
    # forma silenciosa.
    if oficio_id is None and evento_id is None and termo_id is None and servidor_id is None:
        raise ValueError(
            "get_cached_document_artifact exige ao menos uma referência "
            "(oficio_id, evento_id, termo_id ou servidor_id): sem ela a busca "
            "casaria artefato de qualquer área pelo hash de conteúdo (`DB-04`).",
        )
    if not cache_key or not getattr(settings, "DOCUMENTOS_ARTIFACT_CACHE", True):
        return None
    try:
        filters: dict[str, Any] = {
            "tipo": tipo.value,
            "formato": formato.value,
            "cache_key": cache_key,
        }
        if oficio_id is not None:
            filters["oficio_id"] = oficio_id
        if evento_id is not None:
            filters["evento_id"] = evento_id
        if termo_id is not None:
            filters["termo_id"] = termo_id
        if servidor_id is not None:
            filters["servidor_id"] = servidor_id
        art = DocumentoArtefato.objects.filter(**filters).order_by("-criado_em").first()
    except Exception:
        logger.exception("Falha ao consultar cache documental.")
        return None
    if art is None or not art.arquivo:
        return None
    try:
        name = art.arquivo.name
        if not name:
            return None
        if not art.arquivo.storage.exists(name):
            return None
    except Exception:
        return None
    return art


def read_artifact_file_bytes(artefato: DocumentoArtefato) -> bytes:
    with artefato.arquivo.open("rb") as fh:
        return fh.read()


def documento_gerado_from_artifact(
    artefato: DocumentoArtefato,
    *,
    tipo: DocumentoTipo,
    formato: DocumentoFormato,
    reference: str | None,
):
    """Reconstrói o valor de domínio sem executar novamente o renderizador."""
    from documentos.services.facade import DocumentoGerado
    from documentos.services.filenames import build_document_filename
    from documentos.services.responses import get_content_type_for_format

    return DocumentoGerado(
        tipo=tipo,
        formato=formato,
        nome_arquivo=build_document_filename(tipo, formato, reference=reference),
        content_type=get_content_type_for_format(formato),
        conteudo=read_artifact_file_bytes(artefato),
        hash_sha256=artefato.hash_sha256,
        pdf_engine_used=artefato.engine or None,
    )
