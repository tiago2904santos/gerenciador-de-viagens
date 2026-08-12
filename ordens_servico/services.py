"""Geração do documento de Ordem de Serviço."""

from __future__ import annotations

import logging

from django.conf import settings as django_settings
from django.db import transaction

from documentos.services.adapters.docxtpl_render import render_docx_bytes
from documentos.services.document_cache import build_document_cache_key
from documentos.services.document_cache import build_template_cache_signature
from documentos.services.document_cache import documento_gerado_from_artifact
from documentos.services.document_cache import get_cached_document_artifact
from documentos.services.document_cache import read_artifact_file_bytes
from documentos.services.facade import build_default_facade
from documentos.services.pdf_engine import resolve_pdf_engine
from documentos.services.persistence import persist_geracao
from documentos.services.resources_paths import resolve_resource_docx
from documentos.services.responses import build_download_response
from documentos.services.timing import measure_step
from documentos.services.timing import track_document_generation
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo

from oficios.documents import build_canonical_document_payload
from oficios.models import Oficio

from .docxtpl_context import build_os_docxtpl_context
from .models import OrdemServico
from .models import OrdemServicoNumeroLacuna

logger = logging.getLogger(__name__)


@transaction.atomic
def excluir_ordem_servico(ordem: OrdemServico) -> None:
    """Exclui a OS e registra somente o número que ela efetivamente liberou."""
    numero, ano, area = ordem.numero, ordem.ano, ordem.area
    ordem.delete()
    if numero and ano:
        # `BE-09`: `all_objects` é deliberado. A lacuna pertence à área explícita da
        # OS excluída, mesmo se este serviço rodar fora do request ou sob outra área.
        OrdemServicoNumeroLacuna.all_objects.get_or_create(
            area=area,
            ano=ano,
            numero=numero,
        )


def _template_ordem_servico(ordem: OrdemServico) -> str:
    if ordem.tipo_necessidade == OrdemServico.TIPO_PADRAO:
        return "ordem_servico.docx"
    return "ordem_servico_modelos.docx"


def _ordem_chain() -> tuple[str, ...]:
    explicit = (getattr(django_settings, "DOCUMENTOS_DEFAULT_PDF_ENGINE", "auto") or "auto").strip().lower()
    return resolve_pdf_engine(explicit_setting=explicit, prefer_docx_pipeline=False).attempt_chain


def _ordem_cache_key(oficio: Oficio, formato: DocumentoFormato, payload: dict) -> str:
    reference = f"{oficio.numero_formatado.replace('/', '-')}-ordem-servico"
    chain = _ordem_chain() if formato == DocumentoFormato.PDF else ()
    tpl_sig = build_template_cache_signature(tipo=DocumentoTipo.ORDEM_SERVICO, formato=formato)
    return build_document_cache_key(
        tipo=DocumentoTipo.ORDEM_SERVICO,
        formato=formato,
        reference=reference,
        payload=payload,
        docxtpl_context=None,
        attempt_chain=chain if formato == DocumentoFormato.PDF else (),
        template_signature=tpl_sig,
    )


def gerar_resposta_ordem_servico_documento(oficio: Oficio, formato: DocumentoFormato):
    """Gera OS vinculada a um Ofício (fluxo do wizard de oficios)."""
    with measure_step(
        "ordem_servico_gerar_resposta_documento",
        {"oficio_id": oficio.pk, "formato": formato.value},
        track_sla=True,
    ):
        payload = build_canonical_document_payload(oficio, DocumentoTipo.ORDEM_SERVICO)
        reference = f"{oficio.numero_formatado.replace('/', '-')}-ordem-servico"
        cache_key = _ordem_cache_key(oficio, formato, payload)
        if getattr(django_settings, "DOCUMENTOS_ARTIFACT_CACHE", True):
            art = get_cached_document_artifact(
                oficio_id=oficio.pk,
                tipo=DocumentoTipo.ORDEM_SERVICO,
                formato=formato,
                cache_key=cache_key,
            )
            if art is not None:
                content = read_artifact_file_bytes(art)
                response = build_download_response(
                    content=content,
                    tipo=DocumentoTipo.ORDEM_SERVICO,
                    formato=formato,
                    reference=reference,
                    cache_hit=True,
                )
                response["X-Document-SHA256"] = art.hash_sha256
                return response
        facade = build_default_facade()
        doc = facade.gerar(
            tipo=DocumentoTipo.ORDEM_SERVICO,
            formato=formato,
            payload=payload,
            reference=reference,
        )
        response = build_download_response(
            content=doc.conteudo,
            tipo=DocumentoTipo.ORDEM_SERVICO,
            formato=formato,
            reference=reference,
            cache_hit=False,
        )
        response["X-Document-SHA256"] = doc.hash_sha256
        if not payload.get("em_elaboracao"):
            # Nunca persiste a versão RASCUNHO (em_elaboracao=True): ela não sabe
            # quais servidores foram efetivamente designados na OS e, se virasse
            # um DocumentoArtefato, bloquearia para sempre o backfill da versão
            # real (gerar_os_pdf_response) feito por
            # integracoes.google_drive.organizer._garantir_ordens_servico, que só
            # gera quando o ofício ainda não tem nenhum artefato tipo=ordem_servico.
            try:
                persist_geracao(
                    doc,
                    oficio_id=oficio.pk,
                    payload_snapshot=payload,
                    cache_key=cache_key,
                    engine=doc.pdf_engine_used or "",
                )
            except Exception:
                logger.exception("Não foi possível persistir artefato de ordem de serviço.")
        return response


@track_document_generation("ordem_servico_gerar_docx")
def gerar_os_docx_response(ordem: OrdemServico):
    """Gera e retorna HttpResponse com o DOCX da Ordem de Serviço."""
    ctx = build_os_docxtpl_context(ordem)
    template_path = resolve_resource_docx(_template_ordem_servico(ordem))
    conteudo = render_docx_bytes(template_path=template_path, context=ctx)
    reference = (
        f"os-{ordem.numero:03d}-{ordem.ano}"
        if ordem.numero and ordem.ano
        else f"os-{ordem.pk}"
    )
    return build_download_response(
        content=conteudo,
        tipo=DocumentoTipo.ORDEM_SERVICO,
        formato=DocumentoFormato.DOCX,
        reference=reference,
    )


def _persistir_ordem_servico_artefato(
    ordem: OrdemServico,
    doc,
    *,
    cache_key: str = "",
    payload_snapshot: dict | None = None,
) -> None:
    """Persiste a OS gerada (conteúdo real, com os servidores designados) como
    ``DocumentoArtefato`` — para auto-organização/upload no Drive.

    Idempotente por conteúdo (hash). Nunca quebra a geração/download em caso de falha.
    """
    try:
        from documentos.models import DocumentoArtefato
        from documentos.services.persistence import persist_geracao
        from integracoes.google_drive import naming

        if DocumentoArtefato.objects.filter(
            tipo=DocumentoTipo.ORDEM_SERVICO.value, hash_sha256=doc.hash_sha256
        ).exists():
            return
        oficio = ordem.oficios.first()
        if oficio is None:
            return
        persist_geracao(
            doc,
            oficio_id=oficio.pk,
            evento_id=getattr(oficio, "evento_id", None),
            nome_drive=naming.nome_os(ordem),
            payload_snapshot=payload_snapshot,
            cache_key=cache_key,
            engine=doc.pdf_engine_used or "",
        )
    except Exception:
        logger.warning("Não foi possível persistir artefato da ordem de serviço.", exc_info=True)


@track_document_generation("ordem_servico_gerar_pdf")
def gerar_os_pdf_response(ordem: OrdemServico):
    """Gera e retorna HttpResponse com o PDF da Ordem de Serviço."""
    ctx = build_os_docxtpl_context(ordem)
    reference = (
        f"os-{ordem.numero:03d}-{ordem.ano}"
        if ordem.numero and ordem.ano
        else f"os-{ordem.pk}"
    )
    template_path = _template_ordem_servico(ordem)
    payload = {"institucional": {}, "oficio": {}}
    chain = _ordem_chain()
    cache_key = build_document_cache_key(
        tipo=DocumentoTipo.ORDEM_SERVICO,
        formato=DocumentoFormato.PDF,
        reference=reference,
        payload=payload,
        docxtpl_context=ctx,
        attempt_chain=chain,
        template_signature=build_template_cache_signature(
            tipo=DocumentoTipo.ORDEM_SERVICO,
            formato=DocumentoFormato.PDF,
            docx_template_path=template_path,
        ),
    )
    oficio = ordem.oficios.first()
    if oficio is not None:
        cached = get_cached_document_artifact(
            oficio_id=oficio.pk,
            tipo=DocumentoTipo.ORDEM_SERVICO,
            formato=DocumentoFormato.PDF,
            cache_key=cache_key,
        )
        if cached is not None:
            doc = documento_gerado_from_artifact(
                cached,
                tipo=DocumentoTipo.ORDEM_SERVICO,
                formato=DocumentoFormato.PDF,
                reference=reference,
            )
            return build_download_response(
                content=doc.conteudo,
                tipo=DocumentoTipo.ORDEM_SERVICO,
                formato=DocumentoFormato.PDF,
                reference=reference,
                cache_hit=True,
            )

    facade = build_default_facade()
    doc = facade.gerar(
        tipo=DocumentoTipo.ORDEM_SERVICO,
        formato=DocumentoFormato.PDF,
        payload=payload,
        docxtpl_context=ctx,
        docx_template_path=template_path,
        reference=reference,
    )
    _persistir_ordem_servico_artefato(
        ordem,
        doc,
        cache_key=cache_key,
        payload_snapshot=payload,
    )
    return build_download_response(
        content=doc.conteudo,
        tipo=DocumentoTipo.ORDEM_SERVICO,
        formato=DocumentoFormato.PDF,
        reference=reference,
        cache_hit=False,
    )
