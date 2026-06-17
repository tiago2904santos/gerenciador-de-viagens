from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo.exceptions import EProtocoloError
from protocolos import services as proto_services

from ._eprotocolo_real import dica_erro, exigir_real_controlado_configurado


class Command(BaseCommand):
    help = "Importa/espelha localmente um unico protocolo real sem alterar o eProtocolo."

    def add_arguments(self, parser):
        parser.add_argument("--protocolo", required=True, help="Numero do protocolo autorizado.")

    def handle(self, *args, **options):
        exigir_real_controlado_configurado()
        numero = options["protocolo"].strip()
        try:
            protocolo = proto_services.importar_protocolo_real(numero)
        except EProtocoloError as exc:
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            self.stderr.write(self.style.WARNING(dica_erro(exc)))
            raise CommandError("Importacao real falhou.") from exc

        self.stdout.write(self.style.SUCCESS(f"Protocolo importado/atualizado: {protocolo.numero_display}"))
        self.stdout.write(f"Documentos locais: {protocolo.documentos.count()}")
        self.stdout.write(f"Tramitacoes locais: {protocolo.tramitacoes.count()}")
        self.stdout.write(f"Movimentacoes locais: {protocolo.movimentacoes.count()}")
        self.stdout.write(f"Pendencias locais: {protocolo.pendencias.count()}")
        self.stdout.write("Alteracoes no eProtocolo: nenhuma")
