from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo.exceptions import EProtocoloError
from protocolos import services as proto_services

from ._eprotocolo_real import dica_erro, exigir_real_controlado_configurado


class Command(BaseCommand):
    help = "Gera token e faz uma consulta simples read-only no eProtocolo real_controlado."

    def handle(self, *args, **options):
        exigir_real_controlado_configurado()
        try:
            self.stdout.write("Gerando token...")
            auth = epro.testar_autenticacao()
            self.stdout.write(self.style.SUCCESS("Token OK."))
            self.stdout.write("Chamando consulta simples...")
            consulta = epro.testar_conexao()
            self.stdout.write(self.style.SUCCESS("Resposta OK."))
            self.stdout.write(self.style.SUCCESS("Integracao real acessivel."))
            self.stdout.write("Nenhuma alteracao feita no eProtocolo.")
            proto_services.registrar_log(
                None,
                "ping_real",
                resultado=consulta if consulta else auth,
                endpoint="consulta_simples",
                metodo="GET",
            )
        except EProtocoloError as exc:
            proto_services.registrar_log(None, "ping_real", erro=exc, endpoint="consulta_simples", metodo="GET")
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            self.stderr.write(self.style.WARNING(dica_erro(exc)))
            raise CommandError("Ping real falhou.") from exc
