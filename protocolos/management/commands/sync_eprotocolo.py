"""Sincroniza protocolos com o eProtocolo.

Exemplos:
    python manage.py sync_eprotocolo --ativos
    python manage.py sync_eprotocolo --protocolo 24.123.456-7

Sem credenciais reais, roda em modo mock (não toca a rede) — útil para validar
o fluxo end-to-end em desenvolvimento.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo import settings as epro_cfg
from integracoes.eprotocolo.exceptions import EProtocoloError

from protocolos import services
from protocolos.models import Protocolo


class Command(BaseCommand):
    help = "Sincroniza a situação de protocolos com o eProtocolo."

    def add_arguments(self, parser):
        parser.add_argument("--protocolo", dest="numero", default=None,
                            help="Sincroniza apenas o protocolo com este número.")
        parser.add_argument("--ativos", action="store_true",
                            help="Sincroniza todos os protocolos ativos com número.")

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE(f"eProtocolo: {epro_cfg.descricao_ambiente()}"))

        numero = options.get("numero")
        if numero:
            protocolo = Protocolo.objects.filter(numero=numero).first()
            if protocolo is None:
                raise CommandError(f"Nenhum protocolo com número {numero}.")
            self._sincronizar_um(protocolo)
            return

        if options.get("ativos"):
            ok, falhas = services.sincronizar_protocolos_ativos()
            self.stdout.write(self.style.SUCCESS(
                f"Sincronização concluída: {ok} ok, {falhas} com falha."
            ))
            return

        raise CommandError("Informe --ativos ou --protocolo <numero>.")

    def _sincronizar_um(self, protocolo):
        try:
            services.sincronizar_protocolo(protocolo)
            self.stdout.write(self.style.SUCCESS(f"OK: {protocolo.numero_display}"))
        except EProtocoloError as exc:
            raise CommandError(f"Falha ao sincronizar {protocolo.numero_display}: {exc}") from exc
