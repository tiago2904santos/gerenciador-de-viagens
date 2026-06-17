"""Acesso à configuração da integração eProtocolo.

Centraliza a leitura de ``settings.EPROTOCOLO`` para que o restante do pacote
não dependa diretamente de ``django.conf.settings``. Expõe também o helper
``eprotocolo_esta_configurado()`` usado por views/services para decidir entre
modo real e modo mock sem nunca quebrar.
"""

from __future__ import annotations

from django.conf import settings


AMBIENTE_MOCK = "mock"
AMBIENTE_HOMOLOGACAO = "homologacao"
AMBIENTE_PRODUCAO = "producao"


def get_config() -> dict:
    """Retorna o dicionário de configuração (cópia rasa, segura para leitura)."""
    return dict(getattr(settings, "EPROTOCOLO", {}) or {})


def get(chave: str, default=None):
    return get_config().get(chave, default)


def ambiente() -> str:
    return (get("AMBIENTE") or AMBIENTE_MOCK).strip().lower()


def em_modo_mock() -> bool:
    """True quando o client não deve tocar a rede.

    É o caso quando o ambiente é explicitamente ``mock`` ou quando faltam
    credenciais para falar com a API real.
    """
    if ambiente() == AMBIENTE_MOCK:
        return True
    return not _tem_credenciais()


def _tem_credenciais() -> bool:
    cfg = get_config()
    obrigatorias = ("BASE_URL", "TOKEN_URL", "CLIENT_ID", "CLIENT_SECRET", "CONSUMER_ID")
    return all((cfg.get(chave) or "").strip() for chave in obrigatorias)


def eprotocolo_esta_configurado() -> bool:
    """True quando há credenciais reais e o ambiente não é mock.

    Usado para informar o usuário, na UI, se as ações dispararão chamadas reais
    ou apenas o modo mock/sandbox.
    """
    return ambiente() != AMBIENTE_MOCK and _tem_credenciais()


def descricao_ambiente() -> str:
    """Texto curto e amigável do estado atual da integração (para a UI)."""
    if eprotocolo_esta_configurado():
        return f"Integração ativa ({ambiente()})"
    if ambiente() == AMBIENTE_MOCK:
        return "Modo mock (sem integração real)"
    return "Modo mock — credenciais do eProtocolo ausentes"
