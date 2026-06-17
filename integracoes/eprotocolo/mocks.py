"""Respostas determinísticas para o modo mock/sandbox.

Usadas quando não há credenciais reais ou quando ``EPROTOCOLO_AMBIENTE=mock``.
Permitem desenvolver e testar todo o fluxo (criar protocolo, enviar documento,
tramitar, sincronizar) sem nenhuma dependência externa.

As respostas imitam o formato esperado da API real de modo intencionalmente
simples; quando a documentação oficial for confirmada, basta ajustar os
mappers/parse — o contrato do mock segue o mesmo "shape" de saída.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gerar_numero_mock(seed: str | int | None = None) -> str:
    """Gera um número de protocolo fictício, estável por seed.

    Formato semelhante ao do eProtocolo/PR: ``NN.NNN.NNN-D``.
    """
    base = hashlib.sha256(str(seed or _agora_iso()).encode("utf-8")).hexdigest()
    digitos = "".join(ch for ch in base if ch.isdigit()).ljust(9, "0")[:9]
    return f"{digitos[0:2]}.{digitos[2:5]}.{digitos[5:8]}-{digitos[8]}"


def criar_protocolo(payload: dict) -> dict:
    numero = gerar_numero_mock(payload.get("assunto") or payload.get("descricao"))
    return {
        "numero": numero,
        "situacao": "CRIADO",
        "codOrgao": payload.get("codOrgao", ""),
        "codLocalAtual": payload.get("codLocalOrigem", ""),
        "nomeLocalAtual": payload.get("nomeLocalOrigem", ""),
        "criadoEm": _agora_iso(),
        "_mock": True,
    }


def consultar_protocolo(numero: str) -> dict:
    return {
        "numero": numero,
        "situacao": "EM_TRAMITACAO",
        "codLocalAtual": "0001",
        "nomeLocalAtual": "Local de Trâmite (mock)",
        "cpfResponsavelAtual": "00000000000",
        "nomeResponsavelAtual": "Responsável Mock",
        "ultimaMovimentacao": _agora_iso(),
        "_mock": True,
    }


def concluir_protocolo(numero: str) -> dict:
    return {"numero": numero, "situacao": "CONCLUIDO", "concluidoEm": _agora_iso(), "_mock": True}


def enviar_documento(numero: str, nome_arquivo: str, md5: str) -> dict:
    codigo = "DOC-" + hashlib.sha1(f"{numero}:{nome_arquivo}:{md5}".encode("utf-8")).hexdigest()[:10].upper()
    return {
        "numero": numero,
        "codigoDocumento": codigo,
        "nomeArquivo": nome_arquivo,
        "md5": md5,
        "estaNoVolume": True,
        "enviadoEm": _agora_iso(),
        "_mock": True,
    }


def listar_documentos(numero: str) -> dict:
    return {"numero": numero, "documentos": [], "_mock": True}


def listar_pendencias(numero: str) -> dict:
    return {"numero": numero, "pendencias": [], "_mock": True}


def criar_pendencia(numero: str, payload: dict) -> dict:
    codigo = "PEND-" + hashlib.sha1(f"{numero}:{payload}".encode("utf-8")).hexdigest()[:8].upper()
    return {
        "numero": numero,
        "codigoPendencia": codigo,
        "tipo": payload.get("tipo", "ASSINATURA"),
        "status": "PENDENTE",
        "cpfDestinatario": payload.get("cpfDestinatario", ""),
        "nomeDestinatario": payload.get("nomeDestinatario", ""),
        "criadoEm": _agora_iso(),
        "_mock": True,
    }


def cancelar_pendencia(numero: str, codigo: str) -> dict:
    return {"numero": numero, "codigoPendencia": codigo, "status": "CANCELADA", "_mock": True}


def listar_tramitacoes(numero: str) -> dict:
    return {"numero": numero, "tramitacoes": [], "_mock": True}


def tramitar_protocolo(numero: str, payload: dict) -> dict:
    return {
        "numero": numero,
        "codLocalDe": payload.get("codLocalDe", ""),
        "codLocalPara": payload.get("codLocalPara", ""),
        "cpfDestinatario": payload.get("cpfDestinatario", ""),
        "parecer": payload.get("parecer", ""),
        "dataTramitacao": _agora_iso(),
        "situacao": "EM_TRAMITACAO",
        "_mock": True,
    }


def listar_movimentacoes(numero: str) -> dict:
    return {
        "numero": numero,
        "movimentacoes": [
            {"tipo": "CRIACAO", "descricao": "Protocolo criado (mock)", "data": _agora_iso()},
        ],
        "_mock": True,
    }


def listar_assinaturas_documento(numero: str, codigo_documento: str) -> dict:
    return {"numero": numero, "codigoDocumento": codigo_documento, "assinaturas": [], "_mock": True}
