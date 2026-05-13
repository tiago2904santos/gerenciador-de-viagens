"""Contexto e ações da central de assinaturas (etapa 6 do wizard de ofícios)."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from assinaturas.models import PedidoAssinaturaDocumento
from assinaturas.services.assinatura_artefato import mascarar_cpf_assinatura
from assinaturas.services.pedidos import criar_ou_obter_pedido_assinatura
from assinaturas.services.pedidos import url_publica_pedido_assinatura
from assinaturas.services.resolvedores import AssinanteNaoConfiguradoError
from cadastros.models import Servidor
from documentos.models import DocumentoArtefato
from documentos.selectors import get_latest_artefato_pdf_for_oficio
from documentos.selectors import get_latest_artefato_pdf_termo
from documentos.services.persistence import persist_geracao
from documentos.services.types import DocumentoFormato
from documentos.services.types import DocumentoTipo
from documentos.services.warm_cache import pdf_artefato_original_acessivel
from termos.services import gerar_termo_um
from termos.services import listar_servidores_com_termo

from .documents import build_termo_payload
from .services import gerar_resposta_documento_oficio
from .services import gerar_resposta_justificativa_documento
from .services import validar_oficio_para_documento

logger = logging.getLogger(__name__)


def mensagem_preview_assinatura(erro: str, detalhe: str | None) -> str:
    base = {
        "persist_disabled": "Artefatos persistidos estão desligados neste ambiente.",
        "oficio_incompleto": "Complete o ofício antes de assinar os documentos.",
        "sem_pdf": "Não foi possível obter o PDF persistido. Verifique o motor de PDF e tente novamente.",
        "geracao": "Não foi possível preparar o PDF.",
    }
    msg = base.get(erro, "Não foi possível preparar o documento.")
    if erro == "geracao" and detalhe:
        return f"{msg} ({detalhe})"
    return msg


def preview_artefato_pdf_oficio(oficio) -> dict:
    out: dict[str, Any] = {"artefato": None, "erro": None}
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        out["erro"] = "persist_disabled"
        return out
    aval = validar_oficio_para_documento(oficio)
    if aval.get("pendencias"):
        out["erro"] = "oficio_incompleto"
        return out
    art = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.OFICIO.value)
    if art is not None and pdf_artefato_original_acessivel(art):
        out["artefato"] = art
        return out
    try:
        gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF)
    except Exception as exc:  # noqa: BLE001
        out["erro"] = "geracao"
        out["detalhe"] = str(exc)
        return out
    art = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.OFICIO.value)
    if art is None or not pdf_artefato_original_acessivel(art):
        out["erro"] = "sem_pdf"
        return out
    out["artefato"] = art
    return out


def preview_artefato_pdf_justificativa(oficio) -> dict:
    out: dict[str, Any] = {"artefato": None, "erro": None}
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        out["erro"] = "persist_disabled"
        return out
    aval = validar_oficio_para_documento(oficio)
    if aval.get("pendencias"):
        out["erro"] = "oficio_incompleto"
        return out
    art = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.JUSTIFICATIVA.value)
    if art is not None and pdf_artefato_original_acessivel(art):
        out["artefato"] = art
        return out
    try:
        gerar_resposta_justificativa_documento(oficio, DocumentoFormato.PDF)
    except Exception as exc:  # noqa: BLE001
        out["erro"] = "geracao"
        out["detalhe"] = str(exc)
        return out
    art = get_latest_artefato_pdf_for_oficio(oficio.pk, DocumentoTipo.JUSTIFICATIVA.value)
    if art is None or not pdf_artefato_original_acessivel(art):
        out["erro"] = "sem_pdf"
        return out
    out["artefato"] = art
    return out


def preview_artefato_pdf_termo(oficio, servidor: Servidor) -> dict:
    out: dict[str, Any] = {"artefato": None, "erro": None}
    if not getattr(settings, "DOCUMENTOS_PERSIST_ARTEFATOS", False):
        out["erro"] = "persist_disabled"
        return out
    aval = validar_oficio_para_documento(oficio)
    if aval.get("pendencias"):
        out["erro"] = "oficio_incompleto"
        return out
    art = get_latest_artefato_pdf_termo(oficio.pk, servidor.pk)
    if art is not None and pdf_artefato_original_acessivel(art):
        out["artefato"] = art
        return out
    try:
        doc = gerar_termo_um(oficio, servidor, DocumentoFormato.PDF)
        payload = build_termo_payload(oficio, servidor, modo_semipreenchido=False)
        try:
            persist_geracao(
                doc,
                oficio_id=oficio.pk,
                servidor_id=servidor.pk,
                payload_snapshot=payload,
                engine=doc.pdf_engine_used or "",
            )
        except Exception:
            logger.exception(
                "Não foi possível persistir artefato do termo (ofício %s, servidor %s).",
                oficio.pk,
                servidor.pk,
            )
    except Exception as exc:  # noqa: BLE001
        out["erro"] = "geracao"
        out["detalhe"] = str(exc)
        return out
    art = get_latest_artefato_pdf_termo(oficio.pk, servidor.pk)
    if art is None or not pdf_artefato_original_acessivel(art):
        out["erro"] = "sem_pdf"
        return out
    out["artefato"] = art
    return out


def _ja_assinado(art: DocumentoArtefato | None) -> bool:
    if art is None:
        return False
    return bool((art.hash_sha256_assinado or "").strip() and getattr(art.arquivo_assinado, "name", ""))


def _pedido_aberto_nao_expirado(art: DocumentoArtefato) -> PedidoAssinaturaDocumento | None:
    now = timezone.now()
    return (
        PedidoAssinaturaDocumento.objects.filter(
            artefato=art,
            status__in=[
                PedidoAssinaturaDocumento.STATUS_PENDENTE,
                PedidoAssinaturaDocumento.STATUS_VISUALIZADA,
            ],
            expira_em__gt=now,
        )
        .order_by("-criado_em")
        .first()
    )


def _iniciais(nome: str) -> str:
    parts = [p for p in (nome or "").strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return (parts[0][:2] or "?").upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _status_destinatario_key(p: PedidoAssinaturaDocumento) -> str:
    if p.status == PedidoAssinaturaDocumento.STATUS_ASSINADO:
        return "assinado"
    if p.status in {PedidoAssinaturaDocumento.STATUS_PENDENTE, PedidoAssinaturaDocumento.STATUS_VISUALIZADA}:
        return "pendente"
    if p.status == PedidoAssinaturaDocumento.STATUS_EXPIRADO:
        return "expirado"
    if p.status == PedidoAssinaturaDocumento.STATUS_RECUSADA:
        return "recusado"
    if p.status in {PedidoAssinaturaDocumento.STATUS_REVOGADA, PedidoAssinaturaDocumento.STATUS_CANCELADO}:
        return "revogado"
    return "outro"


def _montar_destinatarios(art: DocumentoArtefato | None, *, limite: int = 12) -> list[dict[str, Any]]:
    if art is None:
        return []
    rows: list[dict[str, Any]] = []
    for p in PedidoAssinaturaDocumento.objects.filter(artefato=art).order_by("-criado_em")[:limite]:
        rows.append(
            {
                "nome": p.nome_assinante_snapshot,
                "iniciais": _iniciais(p.nome_assinante_snapshot),
                "cpf_mascarado": mascarar_cpf_assinatura(p.cpf_assinante_snapshot),
                "cargo": (p.cargo_assinante_snapshot or "").strip() or "—",
                "status_key": _status_destinatario_key(p),
                "status_label": p.get_status_display(),
                "enviado_em": p.criado_em,
                "visualizado_em": p.visualizado_em,
                "assinado_em": p.assinado_em,
                "expiracao": p.expira_em,
            }
        )
    return rows


def _montar_item_documento(
    *,
    oficio_pk: int,
    key: str,
    tipo: str,
    tipo_label: str,
    titulo: str,
    descricao: str,
    preview: dict,
    servidor: Servidor | None,
    request: HttpRequest | None = None,
) -> dict[str, Any]:
    art = preview.get("artefato")
    erro = preview.get("erro")
    disponivel = art is not None and not erro
    ja = _ja_assinado(art if isinstance(art, DocumentoArtefato) else None)
    pedido_aberto = _pedido_aberto_nao_expirado(art) if isinstance(art, DocumentoArtefato) else None

    if not disponivel:
        status_key = "indisponivel"
        status_label = "Indisponível"
    elif ja:
        status_key = "assinado"
        status_label = "Assinado"
    elif pedido_aberto:
        status_key = "solicitacao"
        status_label = (
            "Solicitação enviada"
            if pedido_aberto.status == PedidoAssinaturaDocumento.STATUS_PENDENTE
            else "Pendente de assinatura"
        )
    else:
        status_key = "nao_assinado"
        status_label = "Não assinado"

    hash_o = (art.hash_sha256 if isinstance(art, DocumentoArtefato) else "") or ""
    hash_a = ""
    if isinstance(art, DocumentoArtefato):
        hash_a = (art.hash_sha256_assinado or "").strip()

    atualizado = None
    if isinstance(art, DocumentoArtefato):
        atualizado = art.assinado_em or art.criado_em

    n_dest = (
        PedidoAssinaturaDocumento.objects.filter(artefato=art).count()
        if isinstance(art, DocumentoArtefato)
        else 0
    )

    pode = (
        disponivel
        and not ja
        and pedido_aberto is None
        and isinstance(art, DocumentoArtefato)
    )

    pdf_url = ""
    if isinstance(art, DocumentoArtefato):
        pdf_url = reverse("documentos:artefato_pdf_conteudo", args=[art.pk])

    link_pedido_assinatura = ""
    if pedido_aberto is not None and request is not None:
        link_pedido_assinatura = url_publica_pedido_assinatura(request, pedido_aberto)

    return {
        "key": key,
        "tipo": tipo,
        "tipo_label": tipo_label,
        "titulo": titulo,
        "descricao": descricao,
        "artefato": art,
        "servidor": servidor,
        "servidor_pk": servidor.pk if servidor is not None else None,
        "disponivel": disponivel,
        "erro": mensagem_preview_assinatura(erro, preview.get("detalhe")) if erro else "",
        "ja_assinado": ja,
        "status_key": status_key,
        "status_label": status_label,
        "hash_original": hash_o,
        "hash_assinado": hash_a,
        "hash_assinado_exibicao": hash_a if hash_a else "",
        "hash_assinado_placeholder": not bool(hash_a),
        "pdf_estado_atual_url": pdf_url,
        "pdf_versao_label": (
            "Exibindo versão assinada"
            if ja
            else "Exibindo versão original ainda não assinada"
        ),
        "pode_gerar_solicitacao": pode,
        "gerar_solicitacao_url": reverse("oficios:wizard_assinaturas", args=[oficio_pk]),
        "atualizado_em": atualizado,
        "n_destinatarios": n_dest,
        "destinatarios": _montar_destinatarios(art if isinstance(art, DocumentoArtefato) else None),
        "link_pedido_assinatura": link_pedido_assinatura,
    }


def build_documentos_assinatura_central(oficio, *, request: HttpRequest | None = None) -> dict[str, Any]:
    """Lista única de documentos + KPIs para a etapa 6 (URLs públicos de pedido exigem `request`)."""
    pk = oficio.pk
    documentos: list[dict[str, Any]] = []

    po = preview_artefato_pdf_oficio(oficio)
    documentos.append(
        _montar_item_documento(
            oficio_pk=pk,
            key="oficio",
            tipo="oficio",
            tipo_label="Ofício",
            titulo="Ofício (PDF)",
            descricao="Documento principal do expediente.",
            preview=po,
            servidor=None,
            request=request,
        )
    )

    # Sempre listar justificativa (igual à etapa 5 «documentos para conferência»), não só quando a regra de prazo a torna obrigatória.
    pj = preview_artefato_pdf_justificativa(oficio)
    documentos.append(
        _montar_item_documento(
            oficio_pk=pk,
            key="justificativa",
            tipo="justificativa",
            tipo_label="Justificativa",
            titulo="Justificativa (PDF)",
            descricao="Fundamentação vinculada a este ofício.",
            preview=pj,
            servidor=None,
            request=request,
        )
    )

    for servidor in listar_servidores_com_termo(oficio):
        pt = preview_artefato_pdf_termo(oficio, servidor)
        documentos.append(
            _montar_item_documento(
                oficio_pk=pk,
                key=f"termo_{servidor.pk}",
                tipo="termo_autorizacao",
                tipo_label="Termo de Autorização",
                titulo=f"Termo de Autorização — {servidor.nome}",
                descricao="Autorização de viagem para o servidor indicado.",
                preview=pt,
                servidor=servidor,
                request=request,
            )
        )

    total = len(documentos)
    assinados = sum(1 for d in documentos if d["ja_assinado"])
    pendentes = sum(
        1
        for d in documentos
        if d["disponivel"] and not d["ja_assinado"] and d["status_key"] in {"nao_assinado", "solicitacao"}
    )
    n_dest = sum(d["n_destinatarios"] for d in documentos)

    return {
        "documentos_assinatura": documentos,
        "assinaturas_kpis": {
            "documentos": total,
            "destinatarios": n_dest,
            "assinados": assinados,
            "pendentes": pendentes,
        },
    }


def artefato_permitido_no_oficio(art: DocumentoArtefato, oficio) -> bool:
    if art.oficio_id != oficio.pk:
        return False
    if (art.tipo or "").strip().lower() == DocumentoTipo.TERMO_AUTORIZACAO.value:
        sid = art.servidor_id
        if not sid:
            return False
        return listar_servidores_com_termo(oficio).filter(pk=sid).exists()
    return True


def wizard_assinaturas_post_gerar_solicitacao(request, oficio):
    """POST: cria ou reutiliza pedido de assinatura para o artefato indicado."""
    pk = oficio.pk
    dest = redirect(reverse("oficios:wizard_assinaturas", args=[pk]))
    raw = (request.POST.get("artefato_id") or "").strip()
    if not raw:
        messages.error(request, "Identificador do documento em falta.")
        return dest
    try:
        art = DocumentoArtefato.objects.get(pk=raw)
    except (DocumentoArtefato.DoesNotExist, ValueError):
        messages.error(request, "Documento não encontrado.")
        return dest
    if not artefato_permitido_no_oficio(art, oficio):
        raise Http404("Documento não pertence a este ofício.")

    if _ja_assinado(art):
        messages.info(request, "Este documento já está assinado.")
        return dest

    existente = _pedido_aberto_nao_expirado(art)
    if existente is not None:
        messages.info(request, "Já existe uma solicitação em aberto para este documento.")
        return dest

    try:
        criar_ou_obter_pedido_assinatura(art, criado_por=request.user, request=request)
    except AssinanteNaoConfiguradoError as exc:
        messages.error(request, str(exc))
        return dest
    except Exception as exc:  # noqa: BLE001
        messages.error(request, f"Não foi possível gerar a solicitação: {exc}")
        return dest

    messages.success(request, "Solicitação de assinatura gerada com sucesso.")
    return dest
