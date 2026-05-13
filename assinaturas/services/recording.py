from __future__ import annotations

from typing import Any

from django.utils import timezone

from assinaturas.models import AssinaturaDigital
from assinaturas.models import ConfiguracaoChaveAssinatura
from assinaturas.models import EventoAssinatura
from assinaturas.services.codigos import gerar_codigo_verificacao
from documentos.models import DocumentoArtefato


def registrar_assinatura_concluida(artefato: DocumentoArtefato, meta: dict[str, Any]) -> AssinaturaDigital | None:
    """Regista assinatura e evento após `atualizar_apos_assinatura` (artefato já atualizado em disco)."""
    if (meta.get("backend") or "") == "disabled":
        return None

    chave = ConfiguracaoChaveAssinatura.objects.filter(ativo=True).first()
    field_name = str(meta.get("field_name") or "AssinaturaCentralViagens")
    hash_in = str(meta.get("sha256_in") or artefato.hash_sha256)
    hash_out = str(meta.get("sha256_out") or artefato.hash_sha256_assinado or "")

    reg = AssinaturaDigital.objects.create(
        artefato=artefato,
        chave=chave,
        status=AssinaturaDigital.STATUS_VALID,
        codigo_verificacao=gerar_codigo_verificacao(),
        hash_documento=hash_in,
        hash_documento_assinado=hash_out,
        signature_field_name=field_name,
        evidencias=dict(meta),
        appearance={
            "visible": bool(meta.get("visible")),
            "reason": meta.get("reason", ""),
            "location": meta.get("location", ""),
            "signature_position": meta.get("signature_position"),
        },
    )
    EventoAssinatura.objects.create(
        assinatura=reg,
        tipo="assinatura_concluida",
        payload={"backend": meta.get("backend"), "field_name": field_name},
    )
    return reg


def registrar_verificacao_artefato(artefato: DocumentoArtefato, resultado: dict[str, Any]) -> None:
    """Associa o último resultado de verificação ao registo mais recente do artefato, se existir."""
    reg = (
        AssinaturaDigital.objects.filter(artefato=artefato)
        .order_by("-criado_em")
        .first()
    )
    if reg is None:
        return
    ok = bool(resultado.get("ok"))
    reg.status = AssinaturaDigital.STATUS_VALID if ok else AssinaturaDigital.STATUS_INVALID
    reg.validado_em = timezone.now()
    ev = dict(reg.evidencias or {})
    ev["ultima_verificacao"] = resultado
    reg.evidencias = ev
    reg.save(update_fields=["status", "validado_em", "evidencias"])
    EventoAssinatura.objects.create(
        assinatura=reg,
        tipo="verificacao",
        payload=resultado,
    )
