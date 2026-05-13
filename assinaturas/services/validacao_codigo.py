from __future__ import annotations

from typing import Any

from assinaturas.models import AssinaturaDigital
from assinaturas.services.assinatura_artefato import assinatura_arquivo_esta_integra
from assinaturas.services.codigos import normalizar_codigo_verificacao
from assinaturas.services.hash import calcular_sha256_bytes


def validar_assinatura_por_codigo(codigo: str) -> dict[str, Any]:
    c = normalizar_codigo_verificacao(codigo)
    assinatura = AssinaturaDigital.objects.filter(codigo_verificacao=c).select_related("artefato").first()
    if assinatura is None:
        return {
            "assinatura": None,
            "existe": False,
            "status_registro": "",
            "hash_esperado": "",
            "hash_atual": "",
            "integra": False,
            "motivo": "codigo_desconhecido",
            "artefato": None,
            "pdf_assinado_disponivel": False,
        }
    artefato = assinatura.artefato
    hash_esperado = (assinatura.hash_documento_assinado or "").strip().lower()
    hash_atual = ""
    if artefato.arquivo_assinado and getattr(artefato.arquivo_assinado, "name", ""):
        try:
            data = artefato.arquivo_assinado.read()
            hash_atual = calcular_sha256_bytes(data).lower()
        except OSError:
            hash_atual = ""
    pdf_ok = bool(getattr(artefato.arquivo_assinado, "name", ""))
    integra = assinatura_arquivo_esta_integra(assinatura)
    motivo = "ok"
    if not pdf_ok:
        motivo = "sem_pdf_assinado"
    elif not integra:
        motivo = "hash_alterado"
    return {
        "assinatura": assinatura,
        "existe": True,
        "status_registro": assinatura.status,
        "hash_esperado": hash_esperado,
        "hash_atual": hash_atual,
        "integra": integra,
        "motivo": motivo,
        "artefato": artefato,
        "pdf_assinado_disponivel": pdf_ok,
    }
