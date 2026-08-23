from __future__ import annotations

from pathlib import Path

from django.core.management.base import CommandError

from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.exceptions import (
    EProtocoloAuthError,
    EProtocoloConfigError,
    EProtocoloError,
    EProtocoloForbiddenError,
    EProtocoloNotFoundError,
    EProtocoloTimeoutError,
    EProtocoloUnavailableError,
)


CONFIRMACAO_REAL = "CONFIRMO OPERACAO REAL"
MAX_PDF_BYTES = 25 * 1024 * 1024


def exigir_real_controlado_configurado():
    info = cfg.validar_configuracao()
    if not info["real_controlado"]:
        raise CommandError(
            "Este comando exige EPROTOCOLO_AMBIENTE=real_controlado "
            f"(atual: {info['ambiente']})."
        )
    if not info["ok"]:
        faltantes = ", ".join(info["campos_faltantes"])
        raise CommandError(f"Configuracao real_controlado incompleta: {faltantes}.")


def dica_erro(exc: EProtocoloError) -> str:
    if isinstance(exc, EProtocoloAuthError):
        return "401: revisar client_id/client_secret/token_url"
    if isinstance(exc, EProtocoloForbiddenError):
        return "403: revisar consumerId, escopos, usuario, orgao/local, IP/VPN"
    if isinstance(exc, EProtocoloNotFoundError):
        return "404: revisar base_url/path"
    if isinstance(exc, EProtocoloTimeoutError):
        return "timeout: revisar rede/VPN/IP liberado"
    if isinstance(exc, EProtocoloUnavailableError):
        return "SSL/rede: revisar certificado, proxy, VPN, IP liberado ou disponibilidade"
    if getattr(exc, "status_code", None) == 422:
        return "422: revisar parametros/payload"
    if isinstance(exc, EProtocoloConfigError):
        return "configuracao: revisar .env e travas REAL_READONLY/MUTATIONS_ENABLED"
    return "resposta inesperada: revisar logs seguros e contrato da API"


def confirmar_operacao_real(stdout, resumo: list[str]) -> bool:
    stdout.write("Resumo da operacao real:")
    for linha in resumo:
        stdout.write(f"- {linha}")
    stdout.write(f"Digite exatamente '{CONFIRMACAO_REAL}' para continuar:")
    try:
        return input("> ").strip() == CONFIRMACAO_REAL
    except (EOFError, KeyboardInterrupt):
        return False


def validar_pdf(caminho: str) -> tuple[bytes, str]:
    path = Path(caminho)
    if not path.exists() or not path.is_file():
        raise CommandError(f"Arquivo nao encontrado: {caminho}")
    if path.suffix.lower() != ".pdf":
        raise CommandError("O arquivo informado deve ter extensao .pdf.")
    conteudo = path.read_bytes()
    if not conteudo.startswith(b"%PDF"):
        raise CommandError("Arquivo informado nao parece ser um PDF valido.")
    if len(conteudo) > MAX_PDF_BYTES:
        raise CommandError(f"PDF acima do limite de {MAX_PDF_BYTES} bytes.")
    return conteudo, path.name
