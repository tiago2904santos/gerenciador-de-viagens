"""Mappers: documentos internos → payloads do eProtocolo.

Cada função recebe uma instância de model já existente (Ofício, Termo, etc.) e
devolve um ``dict`` mínimo e seguro para criar um protocolo. A lógica de
documento NÃO é duplicada aqui: apenas lemos atributos dos models e
complementamos com os códigos institucionais padrão configurados.

Regras de robustez:
    * tudo via ``getattr`` defensivo — um campo ausente nunca quebra o mapper;
    * campos institucionais (órgão, locais, assunto, espécie, palavra-chave)
      vêm de ``settings.EPROTOCOLO`` e podem estar vazios;
    * o payload é propositalmente enxuto; campos obrigatórios reais devem ser
      confirmados na documentação oficial e adicionados de forma configurável.
"""

from __future__ import annotations

from core.errors import capture

from . import settings as cfg
from .exceptions import EProtocoloValidationError


# Códigos institucionais exigidos para criar um protocolo de Ofício no modo
# real. Sem eles a API rejeita a criação; validamos antes de chamar a rede.
CAMPOS_INSTITUCIONAIS_OBRIGATORIOS = {
    "codOrgao": "EPROTOCOLO_COD_ORGAO_PADRAO",
    "codLocalOrigem": "EPROTOCOLO_COD_LOCAL_ORIGEM_PADRAO",
    "codAssunto": "EPROTOCOLO_COD_ASSUNTO_VIAGEM",
    "codEspecie": "EPROTOCOLO_COD_ESPECIE_OFICIO",
}


def _defaults_institucionais() -> dict:
    return {
        "codOrgao": cfg.get("COD_ORGAO_PADRAO", ""),
        "nomeOrgao": cfg.get("NOME_ORGAO_PADRAO", ""),
        "codLocalOrigem": cfg.get("COD_LOCAL_ORIGEM_PADRAO", ""),
        "codLocalDestino": cfg.get("COD_LOCAL_DESTINO_PADRAO", ""),
        "codAssunto": cfg.get("COD_ASSUNTO_VIAGEM", ""),
        "codEspecie": cfg.get("COD_ESPECIE_OFICIO", ""),
        "codPalavraChave": cfg.get("COD_PALAVRA_CHAVE_VIAGEM", ""),
    }


def _truncar(texto, limite=255) -> str:
    texto = (texto or "").strip()
    return texto[:limite]


def _servidores_resumo(qs) -> list[dict]:
    servidores = []
    try:
        for s in qs.all():
            servidores.append({
                "nome": getattr(s, "nome", "") or str(s),
                "cpf": getattr(s, "cpf", "") or "",
            })
    except Exception as exc:  # relação ausente/None não pode derrubar o payload
        capture(exc, "eprotocolo.mappers.servidores")
    return servidores


def mapear_oficio_para_protocolo(oficio) -> dict:
    numero = getattr(oficio, "numero", None)
    ano = getattr(oficio, "ano", None)
    numero_formatado = getattr(oficio, "numero_formatado", "") or ""

    assunto = getattr(oficio, "assunto", "") or "Ofício de viagem institucional"
    motivo = getattr(oficio, "motivo", "") or ""

    destinos = []
    roteiro = getattr(oficio, "roteiro", None)
    if roteiro is not None:
        try:
            for destino in roteiro.destinos.all():
                destinos.append(str(destino))
        except Exception as exc:  # roteiro sem destinos carregáveis não derruba o payload
            capture(exc, "eprotocolo.mappers.destinos")

    payload = _defaults_institucionais()
    payload.update({
        "tipoOrigem": "OFICIO",
        "numeroDocumento": numero,
        "anoDocumento": ano,
        "referenciaDocumento": numero_formatado,
        "protocoloInterno": getattr(oficio, "protocolo", "") or "",
        "assunto": _truncar(assunto),
        "descricao": _truncar(motivo or assunto, 1000),
        "custeio": getattr(oficio, "custeio", "") or "",
        "servidores": _servidores_resumo(getattr(oficio, "servidores", None) or _Vazio()),
        "destinos": destinos,
    })
    return payload


def validar_payload_institucional(payload: dict) -> list[str]:
    """Retorna a lista de campos institucionais obrigatórios ainda vazios."""
    faltantes = []
    for campo, env in CAMPOS_INSTITUCIONAIS_OBRIGATORIOS.items():
        if not (str(payload.get(campo) or "")).strip():
            faltantes.append(f"{campo} ({env})")
    return faltantes


def mapear_oficio_para_payload_eprotocolo(oficio) -> dict:
    """Mapper validado de Ofício → payload do eProtocolo (modo real).

    Diferente de :func:`mapear_oficio_para_protocolo` (que nunca quebra, p/ mock),
    esta função valida os campos obrigatórios e levanta
    :class:`EProtocoloValidationError` com mensagem clara quando algo essencial
    está faltando — para uso no fluxo de homologação real.
    """
    payload = mapear_oficio_para_protocolo(oficio)

    if not (str(payload.get("numeroDocumento") or "")).strip():
        raise EProtocoloValidationError(
            "Ofício sem número definido — não é possível gerar o protocolo."
        )
    if not (payload.get("assunto") or "").strip():
        raise EProtocoloValidationError("Ofício sem assunto/motivo para o protocolo.")

    faltantes = validar_payload_institucional(payload)
    if faltantes:
        raise EProtocoloValidationError(
            "Códigos institucionais ausentes no .env: " + ", ".join(faltantes)
        )
    return payload


def mapear_termo_para_protocolo(termo) -> dict:
    payload = _defaults_institucionais()
    payload.update({
        "tipoOrigem": "TERMO_AUTORIZACAO",
        "referenciaDocumento": f"Termo #{getattr(termo, 'pk', '')}",
        "assunto": _truncar(getattr(termo, "destino_display", "") or "Termo de autorização"),
        "descricao": _truncar(getattr(termo, "periodo_display", "") or "", 1000),
        "servidores": _servidores_resumo(getattr(termo, "servidores", None) or _Vazio()),
    })
    return payload


def mapear_justificativa_para_protocolo(justificativa) -> dict:
    oficio = getattr(justificativa, "oficio", None)
    payload = _defaults_institucionais()
    payload.update({
        "tipoOrigem": "JUSTIFICATIVA",
        "referenciaDocumento": f"Justificativa #{getattr(justificativa, 'pk', '')}",
        "protocoloInterno": getattr(oficio, "protocolo", "") if oficio else "",
        "assunto": _truncar("Justificativa de viagem"),
        "descricao": _truncar(getattr(justificativa, "texto", "") or "", 1000),
    })
    return payload


def mapear_plano_trabalho_para_protocolo(plano) -> dict:
    payload = _defaults_institucionais()
    payload.update({
        "tipoOrigem": "PLANO_TRABALHO",
        "numeroDocumento": getattr(plano, "numero", None),
        "anoDocumento": getattr(plano, "ano", None),
        "referenciaDocumento": f"Plano de Trabalho #{getattr(plano, 'pk', '')}",
        "assunto": _truncar("Plano de Trabalho"),
        "descricao": _truncar(getattr(plano, "contextualizacao", "") or "", 1000),
    })
    return payload


def mapear_ordem_servico_para_protocolo(ordem) -> dict:
    payload = _defaults_institucionais()
    payload.update({
        "tipoOrigem": "ORDEM_SERVICO",
        "numeroDocumento": getattr(ordem, "numero", None),
        "anoDocumento": getattr(ordem, "ano", None),
        "referenciaDocumento": f"Ordem de Serviço #{getattr(ordem, 'pk', '')}",
        "assunto": _truncar("Ordem de Serviço"),
        "descricao": _truncar(getattr(ordem, "motivo", "") or "", 1000),
        "servidores": _servidores_resumo(getattr(ordem, "servidores", None) or _Vazio()),
    })
    return payload


class _Vazio:
    """Stub de manager vazio para getattr defensivo."""

    def all(self):
        return []


# Registro por nome de model → mapper, usado pela camada de serviço interna.
MAPPERS_POR_MODEL = {
    "Oficio": mapear_oficio_para_protocolo,
    "TermoAutorizacao": mapear_termo_para_protocolo,
    "Justificativa": mapear_justificativa_para_protocolo,
    "PlanoTrabalho": mapear_plano_trabalho_para_protocolo,
    "OrdemServico": mapear_ordem_servico_para_protocolo,
}


def mapear_documento(documento) -> dict:
    """Despacha para o mapper correto a partir do nome da classe do model."""
    nome = type(documento).__name__
    mapper = MAPPERS_POR_MODEL.get(nome)
    if mapper is None:
        # Fallback genérico: nunca quebra, gera payload mínimo.
        payload = _defaults_institucionais()
        payload.update({
            "tipoOrigem": nome.upper(),
            "referenciaDocumento": str(documento),
            "assunto": _truncar(str(documento)),
            "descricao": "",
        })
        return payload
    return mapper(documento)
