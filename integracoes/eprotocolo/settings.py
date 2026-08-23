"""Acesso à configuração da integração eProtocolo.

Centraliza a leitura de ``settings.EPROTOCOLO`` para que o restante do pacote
não dependa diretamente de ``django.conf.settings``. Expõe também o helper
``eprotocolo_esta_configurado()`` usado por views/services para decidir entre
modo real e modo mock sem nunca quebrar.
"""

from __future__ import annotations

from django.conf import settings


AMBIENTE_MOCK = "mock"
AMBIENTE_TREINAMENTO = "treinamento"
AMBIENTE_HOMOLOGACAO = "homologacao"
AMBIENTE_PRODUCAO = "producao"
AMBIENTE_REAL_CONTROLADO = "real_controlado"

# Ambientes que disparam chamadas HTTP reais quando há credenciais.
AMBIENTES_REAIS = (
    AMBIENTE_TREINAMENTO,
    AMBIENTE_HOMOLOGACAO,
    AMBIENTE_PRODUCAO,
    AMBIENTE_REAL_CONTROLADO,
)

OPERACOES_READONLY = ("consultar", "importar")
OPERACOES_MUTACAO = (
    "anexar_documento",
    "criar_pendencia",
    "tramitar",
    "criar_protocolo",
    "concluir",
)
OPERACOES_REAIS_ALLOWLIST = OPERACOES_READONLY + OPERACOES_MUTACAO

# Credenciais/URLs sem as quais o modo real não pode operar.
CAMPOS_OBRIGATORIOS_REAL = (
    "BASE_URL", "TOKEN_URL", "CLIENT_ID", "CLIENT_SECRET", "CONSUMER_ID",
)


def get_config() -> dict:
    """Retorna o dicionário de configuração (cópia rasa, segura para leitura)."""
    return dict(getattr(settings, "EPROTOCOLO", {}) or {})


def get(chave: str, default=None):
    return get_config().get(chave, default)


def ambiente() -> str:
    return (get("AMBIENTE") or AMBIENTE_MOCK).strip().lower()


def is_treinamento() -> bool:
    return ambiente() == AMBIENTE_TREINAMENTO


def is_homologacao() -> bool:
    return ambiente() == AMBIENTE_HOMOLOGACAO


def is_producao() -> bool:
    return ambiente() == AMBIENTE_PRODUCAO


def is_real_controlado() -> bool:
    return ambiente() == AMBIENTE_REAL_CONTROLADO


def is_real() -> bool:
    """True quando o ambiente configurado pretende falar com a API real."""
    return ambiente() in AMBIENTES_REAIS


def real_readonly() -> bool:
    return bool(get("REAL_READONLY", True))


def real_mutations_enabled() -> bool:
    return bool(get("REAL_MUTATIONS_ENABLED", False))


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
    return all((cfg.get(chave) or "").strip() for chave in CAMPOS_OBRIGATORIOS_REAL)


def campos_faltantes() -> list[str]:
    """Lista os campos obrigatórios do modo real que estão vazios."""
    cfg = get_config()
    return [c for c in CAMPOS_OBRIGATORIOS_REAL if not (cfg.get(c) or "").strip()]


def eprotocolo_esta_configurado() -> bool:
    """True quando há credenciais reais e o ambiente não é mock.

    Usado para informar o usuário, na UI, se as ações dispararão chamadas reais
    ou apenas o modo mock/sandbox.
    """
    return is_real() and _tem_credenciais()


def descricao_ambiente() -> str:
    """Texto curto e amigável do estado atual da integração (para a UI)."""
    if eprotocolo_esta_configurado():
        if is_real_controlado():
            return "Integração ativa (real_controlado, somente consulta)"
        return f"Integração ativa ({ambiente()})"
    if ambiente() == AMBIENTE_MOCK:
        return "Modo mock (sem integração real)"
    return f"Modo mock — credenciais do eProtocolo ausentes ({ambiente()})"


def mascarar_segredo(valor: str | None, *, visiveis: int = 4) -> str:
    """Mascara um segredo para exibição em diagnóstico (ex.: ``abcd****``).

    Nunca revela o valor inteiro. Vazio → ``"(não configurado)"``.
    """
    texto = (valor or "").strip()
    if not texto:
        return "(não configurado)"
    if len(texto) <= visiveis:
        return "*" * len(texto)
    return f"{texto[:visiveis]}{'*' * min(4, len(texto) - visiveis)}"


def validar_configuracao() -> dict:
    """Resumo seguro da configuração atual para o comando de diagnóstico.

    Não chama a rede e não expõe segredos — apenas indica presença/ausência e
    versões mascaradas dos identificadores. ``ok`` é True quando o ambiente é
    mock (sempre operável) ou quando o modo real tem todos os campos.
    """
    cfg = get_config()
    amb = ambiente()
    faltantes = campos_faltantes()
    real = amb in AMBIENTES_REAIS
    return {
        "ambiente": amb,
        "modo_real": real,
        "producao": amb == AMBIENTE_PRODUCAO,
        "base_url_configurada": bool((cfg.get("BASE_URL") or "").strip()),
        "token_url_configurada": bool((cfg.get("TOKEN_URL") or "").strip()),
        "client_id": mascarar_segredo(cfg.get("CLIENT_ID")),
        "client_secret_configurado": bool((cfg.get("CLIENT_SECRET") or "").strip()),
        "consumer_id": mascarar_segredo(cfg.get("CONSUMER_ID")),
        "timeout": cfg.get("TIMEOUT", 30),
        "verify_ssl": bool(cfg.get("VERIFY_SSL", True)),
        "read_only": real_readonly(),
        "mutations_enabled": real_mutations_enabled(),
        "real_controlado": amb == AMBIENTE_REAL_CONTROLADO,
        "campos_faltantes": faltantes,
        "ok": (not real) or not faltantes,
    }


def garantir_operacao_real_permitida(
    operacao,
    protocolo=None,
    *,
    real=False,
    confirmado=False,
    quantidade=1,
):
    """Bloqueia mutacoes reais acidentais no ambiente real_controlado."""
    from .exceptions import EProtocoloConfigError

    if operacao not in OPERACOES_REAIS_ALLOWLIST:
        raise EProtocoloConfigError(f"Operacao real nao permitida: {operacao}.")

    if not is_real_controlado():
        raise EProtocoloConfigError(
            f"Operacao real controlada exige EPROTOCOLO_AMBIENTE=real_controlado "
            f"(atual: {ambiente()})."
        )

    if quantidade != 1:
        raise EProtocoloConfigError("Operacao real deve ser limitada a um protocolo por vez.")

    if operacao in OPERACOES_READONLY:
        return True

    if real_readonly():
        raise EProtocoloConfigError("Operacao real bloqueada: EPROTOCOLO_REAL_READONLY=True.")
    if not real_mutations_enabled():
        raise EProtocoloConfigError(
            "Operacao real bloqueada: EPROTOCOLO_REAL_MUTATIONS_ENABLED=False."
        )
    if not real:
        raise EProtocoloConfigError("Operacao real bloqueada: flag --real ausente.")
    if not protocolo:
        raise EProtocoloConfigError("Operacao real bloqueada: protocolo explicito ausente.")
    if not confirmado:
        raise EProtocoloConfigError("Operacao real bloqueada: confirmacao manual ausente.")
    return True
