"""Services de alto nível da integração eProtocolo.

Cada função representa uma operação de negócio sobre o barramento. Elas
decidem entre **modo mock** (sem rede) e **modo real** (via ``client``) usando
``settings.em_modo_mock()`` e sempre retornam um :class:`ResultadoOperacao`,
de modo que a camada de ``protocolos.services`` saiba se a chamada foi real ou
simulada sem inspecionar credenciais.

Os campos obrigatórios reais de cada payload devem ser confirmados na
documentação oficial; aqui eles são repassados como recebidos do mapper e
ficam claramente configuráveis. Nada institucional é hardcoded.
"""

from __future__ import annotations

import hashlib

from . import mocks
from . import settings as cfg
from .client import get_client
from .schemas import Endpoints, ResultadoOperacao


def _mock(dados: dict, mensagem: str = "") -> ResultadoOperacao:
    return ResultadoOperacao(sucesso=True, dados=dados, mock=True, mensagem=mensagem)


def _real(dados: dict, mensagem: str = "") -> ResultadoOperacao:
    return ResultadoOperacao(sucesso=True, dados=dados, mock=False, mensagem=mensagem)


def calcular_md5(conteudo: bytes) -> str:
    """MD5 hexadecimal do conteúdo de um documento (usado no envio)."""
    return hashlib.md5(conteudo).hexdigest()


# ---------------------------------------------------------------------------
# Diagnóstico / autenticação (usados por eprotocolo_check / eprotocolo_ping)
# ---------------------------------------------------------------------------
def testar_autenticacao() -> ResultadoOperacao:
    """Confirma que é possível obter um token (ou simula em modo mock).

    Nunca retorna o token; apenas indica sucesso. Erros sobem como
    ``EProtocoloError`` para tratamento amigável na camada de comando/view.
    """
    if cfg.em_modo_mock():
        return _mock(mocks.autenticar(), "Autenticação simulada (modo mock).")
    get_client().garantir_token()
    return _real({"autenticado": True}, "Autenticação no eProtocolo bem-sucedida.")


def testar_conexao() -> ResultadoOperacao:
    """Faz uma consulta simples (órgãos) para validar o acesso ao barramento."""
    if cfg.em_modo_mock():
        return _mock(mocks.listar_orgaos(), "Conexão simulada (modo mock).")
    dados = get_client().get(Endpoints.ORGAOS)
    return _real(dados, "Conexão com o eProtocolo bem-sucedida.")


def listar_orgaos() -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_orgaos())
    return _real(get_client().get(Endpoints.ORGAOS))


def listar_locais(cod_orgao: str | None = None) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_locais(cod_orgao))
    params = {"codOrgao": cod_orgao} if cod_orgao else None
    return _real(get_client().get(Endpoints.LOCAIS, params=params))


def listar_assuntos() -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_assuntos())
    return _real(get_client().get(Endpoints.ASSUNTOS))


def listar_especies() -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_especies())
    return _real(get_client().get(Endpoints.ESPECIES))


# ---------------------------------------------------------------------------
# Protocolo
# ---------------------------------------------------------------------------
def criar_protocolo(payload: dict) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.criar_protocolo(payload), "Protocolo criado em modo mock.")
    dados = get_client().post(Endpoints.CRIAR_PROTOCOLO, json=payload)
    return _real(dados, "Protocolo criado no eProtocolo.")


def consultar_protocolo(numero: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.consultar_protocolo(numero))
    dados = get_client().get(Endpoints.CONSULTAR_PROTOCOLO.format(numero=numero))
    return _real(dados)


def concluir_protocolo(numero: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.concluir_protocolo(numero), "Cadastro concluído em modo mock.")
    dados = get_client().post(Endpoints.CONCLUIR_PROTOCOLO.format(numero=numero))
    return _real(dados, "Cadastro concluído no eProtocolo.")


# ---------------------------------------------------------------------------
# Documentos
# ---------------------------------------------------------------------------
def enviar_documento(numero: str, arquivo_pdf: bytes, nome_arquivo: str,
                     metadata: dict | None = None) -> ResultadoOperacao:
    md5 = calcular_md5(arquivo_pdf)
    if cfg.em_modo_mock():
        dados = mocks.enviar_documento(numero, nome_arquivo, md5)
        dados.update({"tamanhoBytes": len(arquivo_pdf)})
        return _mock(dados, "Documento registrado em modo mock.")
    files = {"arquivo": (nome_arquivo, arquivo_pdf, "application/pdf")}
    data = {"md5": md5, **(metadata or {})}
    dados = get_client().post(
        Endpoints.DOCUMENTOS.format(numero=numero), files=files, data=data
    )
    dados.setdefault("md5", md5)
    dados.setdefault("tamanhoBytes", len(arquivo_pdf))
    return _real(dados, "Documento enviado ao eProtocolo.")


def listar_documentos_protocolo(numero: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_documentos(numero))
    return _real(get_client().get(Endpoints.DOCUMENTOS.format(numero=numero)))


def listar_documentos_volume(numero: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_documentos(numero))
    return _real(get_client().get(Endpoints.DOCUMENTOS_VOLUME.format(numero=numero)))


# ---------------------------------------------------------------------------
# Pendências / Assinaturas
# ---------------------------------------------------------------------------
def listar_pendencias(numero: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_pendencias(numero))
    return _real(get_client().get(Endpoints.PENDENCIAS.format(numero=numero)))


def criar_pendencia(numero: str, payload: dict) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.criar_pendencia(numero, payload), "Pendência criada em modo mock.")
    dados = get_client().post(Endpoints.PENDENCIAS.format(numero=numero), json=payload)
    return _real(dados, "Pendência criada no eProtocolo.")


def cancelar_pendencia(numero: str, codigo_pendencia: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.cancelar_pendencia(numero, codigo_pendencia), "Pendência cancelada em modo mock.")
    dados = get_client().post(
        Endpoints.PENDENCIA_CANCELAR.format(numero=numero, codigo=codigo_pendencia)
    )
    return _real(dados, "Pendência cancelada no eProtocolo.")


def listar_assinaturas_documento(numero: str, codigo_documento: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_assinaturas_documento(numero, codigo_documento))
    return _real(get_client().get(
        Endpoints.ASSINATURAS_DOCUMENTO.format(numero=numero, codigo=codigo_documento)
    ))


# ---------------------------------------------------------------------------
# Tramitações / Movimentações
# ---------------------------------------------------------------------------
def listar_tramitacoes(numero: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_tramitacoes(numero))
    return _real(get_client().get(Endpoints.TRAMITACOES.format(numero=numero)))


def tramitar_protocolo(numero: str, payload: dict) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.tramitar_protocolo(numero, payload), "Tramitação registrada em modo mock.")
    dados = get_client().post(Endpoints.TRAMITACOES.format(numero=numero), json=payload)
    return _real(dados, "Protocolo tramitado no eProtocolo.")


def listar_movimentacoes(numero: str) -> ResultadoOperacao:
    if cfg.em_modo_mock():
        return _mock(mocks.listar_movimentacoes(numero))
    return _real(get_client().get(Endpoints.MOVIMENTACOES.format(numero=numero)))
