"""Ping de conectividade com o eProtocolo.

Gera um token e faz UMA consulta simples (órgãos) — não cria protocolo, não
envia documento, não tramita. Em modo mock, confirma o fluxo sem tocar a rede.

Exemplos:
    python manage.py eprotocolo_ping
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.exceptions import (
    EProtocoloAuthError,
    EProtocoloConfigError,
    EProtocoloForbiddenError,
    EProtocoloNotFoundError,
    EProtocoloTimeoutError,
    EProtocoloUnavailableError,
    EProtocoloError,
)


# Dicas acionáveis por tipo/status de erro.
_DICAS = {
    EProtocoloConfigError: "configuração ausente: revisar BASE_URL/TOKEN_URL/CLIENT_ID/CLIENT_SECRET/CONSUMER_ID no .env",
    EProtocoloAuthError: "401: revisar client_id/client_secret/token_url",
    EProtocoloForbiddenError: "403: revisar escopos/consumerId/permissões/IP/VPN",
    EProtocoloNotFoundError: "404: revisar base_url/path",
    EProtocoloTimeoutError: "timeout: revisar VPN/IP/rede",
    EProtocoloUnavailableError: "serviço indisponível: revisar VPN/IP/rede ou status do barramento",
}


class Command(BaseCommand):
    help = "Testa autenticação e uma consulta simples ao eProtocolo (read-only)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(f"eProtocolo: {cfg.descricao_ambiente()}"))

        try:
            self.stdout.write("Gerando token...")
            auth = epro.testar_autenticacao()
            self.stdout.write(self.style.SUCCESS(
                "Token OK." + (" (mock)" if auth.mock else "")
            ))

            self.stdout.write("Chamando endpoint de consulta (órgãos)...")
            conexao = epro.testar_conexao()
            self.stdout.write(self.style.SUCCESS(
                "Resposta OK." + (" (mock)" if conexao.mock else "")
            ))
            self.stdout.write(self.style.SUCCESS(
                "Integração acessível." if not conexao.mock
                else "Fluxo validado em modo mock."
            ))
        except EProtocoloError as exc:
            dica = self._dica(exc)
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            if dica:
                self.stderr.write(self.style.WARNING(dica))

    def _dica(self, exc):
        for classe, texto in _DICAS.items():
            if isinstance(exc, classe):
                return texto
        status = getattr(exc, "status_code", None)
        if status == 422:
            return "422: payload inválido (não aplicável a consulta simples)"
        if status and status >= 500:
            return "5xx: serviço indisponível — tentar novamente mais tarde"
        return "verifique a configuração com: python manage.py eprotocolo_check"
