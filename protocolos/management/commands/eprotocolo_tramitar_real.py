from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo.exceptions import EProtocoloError
from protocolos import services as proto_services
from protocolos.models import Protocolo

from ._eprotocolo_real import confirmar_operacao_real, dica_erro, exigir_real_controlado_configurado


class Command(BaseCommand):
    help = "Tramita um protocolo real, com confirmacao manual forte."

    def add_arguments(self, parser):
        parser.add_argument("--protocolo", required=True)
        parser.add_argument("--local-destino", required=True)
        parser.add_argument("--parecer", required=True)
        parser.add_argument("--real", action="store_true")

    def handle(self, *args, **options):
        exigir_real_controlado_configurado()
        numero = options["protocolo"].strip()
        protocolo = Protocolo.objects.filter(numero=numero).first() or proto_services.importar_protocolo_real(numero)
        protocolo.refresh_from_db()
        confirmado = confirmar_operacao_real(
            self.stdout,
            [
                "operacao: tramitar",
                f"protocolo: {numero}",
                f"local atual: {protocolo.nome_local_atual or protocolo.cod_local_atual or '-'}",
                f"local destino: {options['local_destino']}",
                f"parecer: {options['parecer']}",
            ],
        )
        if not confirmado:
            self.stdout.write(self.style.WARNING("Operacao cancelada."))
            return
        try:
            proto_services.tramitar(
                protocolo,
                options["local_destino"],
                parecer=options["parecer"],
                real=options["real"],
                confirmado=True,
            )
            proto_services.sincronizar_protocolo(protocolo)
        except EProtocoloError as exc:
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            self.stderr.write(self.style.WARNING(dica_erro(exc)))
            raise CommandError("Tramitacao real falhou.") from exc

        self.stdout.write(self.style.SUCCESS("Protocolo tramitado e consultado novamente."))
