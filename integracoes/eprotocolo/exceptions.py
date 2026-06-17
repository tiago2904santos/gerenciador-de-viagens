"""Hierarquia de exceções da integração eProtocolo.

Toda falha de comunicação externa é convertida para uma destas classes pelo
``client``. As camadas superiores (services internos / views) tratam estas
exceções e nunca precisam conhecer detalhes de ``requests`` ou status HTTP.
"""

from __future__ import annotations


class EProtocoloError(Exception):
    """Erro base de qualquer falha na integração com o eProtocolo."""

    mensagem_usuario = "Falha na comunicação com o eProtocolo."

    def __init__(self, mensagem: str | None = None, *, status_code: int | None = None,
                 payload=None):
        self.status_code = status_code
        self.payload = payload
        super().__init__(mensagem or self.mensagem_usuario)


class EProtocoloAuthError(EProtocoloError):
    """Falha de autenticação (token inválido/expirado) — HTTP 401."""

    mensagem_usuario = "Não foi possível autenticar no eProtocolo (credenciais inválidas)."


class EProtocoloForbiddenError(EProtocoloError):
    """Acesso negado ao recurso — HTTP 403."""

    mensagem_usuario = "Acesso negado pelo eProtocolo para esta operação."


class EProtocoloNotFoundError(EProtocoloError):
    """Recurso não encontrado — HTTP 404."""

    mensagem_usuario = "Protocolo ou recurso não encontrado no eProtocolo."


class EProtocoloValidationError(EProtocoloError):
    """Dados inválidos enviados — HTTP 400/422."""

    mensagem_usuario = "O eProtocolo recusou os dados enviados (validação)."


class EProtocoloUnavailableError(EProtocoloError):
    """Serviço indisponível — HTTP 5xx ou erro de conexão."""

    mensagem_usuario = "O serviço do eProtocolo está indisponível no momento."


class EProtocoloTimeoutError(EProtocoloUnavailableError):
    """Tempo limite excedido na chamada."""

    mensagem_usuario = "Tempo limite excedido ao chamar o eProtocolo."


class EProtocoloNaoConfiguradoError(EProtocoloError):
    """Integração não configurada (sem credenciais) e modo real exigido."""

    mensagem_usuario = "A integração real do eProtocolo ainda não está configurada."


def excecao_para_status(status_code: int, mensagem: str | None = None, payload=None) -> EProtocoloError:
    """Mapeia um status HTTP para a exceção apropriada."""
    if status_code in (400, 422):
        return EProtocoloValidationError(mensagem, status_code=status_code, payload=payload)
    if status_code == 401:
        return EProtocoloAuthError(mensagem, status_code=status_code, payload=payload)
    if status_code == 403:
        return EProtocoloForbiddenError(mensagem, status_code=status_code, payload=payload)
    if status_code == 404:
        return EProtocoloNotFoundError(mensagem, status_code=status_code, payload=payload)
    if status_code >= 500:
        return EProtocoloUnavailableError(mensagem, status_code=status_code, payload=payload)
    return EProtocoloError(mensagem, status_code=status_code, payload=payload)
