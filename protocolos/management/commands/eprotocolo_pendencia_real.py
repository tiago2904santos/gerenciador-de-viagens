from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo.exceptions import EProtocoloError
from protocolos import services as proto_services
from protocolos.models import Protocolo, ProtocoloDocumento, mascarar_cpf

from ._eprotocolo_real import confirmar_operacao_real, dica_erro, exigir_real_controlado_configurado


class Command(BaseCommand):
    help = "Cria pendencia/assinatura real, com confirmacao manual forte."

    def add_arguments(self, parser):
        parser.add_argument("--protocolo", required=True)
        parser.add_argument("--documento", required=True)
        parser.add_argument("--cpf", required=True)
        parser.add_argument("--tipo", choices=["assinatura"], required=True)
        parser.add_argument("--real", action="store_true")

    def handle(self, *args, **options):
        exigir_real_controlado_configurado()
        numero = options["protocolo"].strip()
        cpf = "".join(ch for ch in options["cpf"] if ch.isdigit())
        if len(cpf) != 11:
            raise CommandError("CPF invalido.")
        confirmado = confirmar_operacao_real(
            self.stdout,
            [
                "operacao: criar_pendencia",
                f"protocolo: {numero}",
                f"documento: {options['documento']}",
                f"cpf: {mascarar_cpf(cpf)}",
                "tipo: assinatura",
            ],
        )
        if not confirmado:
            self.stdout.write(self.style.WARNING("Operacao cancelada."))
            return

        protocolo = Protocolo.objects.filter(numero=numero).first() or Protocolo.objects.create(
            numero=numero,
            origem_tipo=Protocolo.ORIGEM_EPROTOCOLO_REAL,
            status_local=Protocolo.STATUS_CRIADO,
        )
        documento = ProtocoloDocumento.objects.filter(
            protocolo=protocolo,
            codigo_documento_eprotocolo=options["documento"],
        ).first()
        try:
            proto_services.solicitar_assinatura_documento(
                protocolo,
                documento,
                cpf,
                real=options["real"],
                confirmado=True,
            )
            proto_services.sincronizar_protocolo(protocolo)
        except EProtocoloError as exc:
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            self.stderr.write(self.style.WARNING(dica_erro(exc)))
            raise CommandError("Pendencia real falhou.") from exc

        self.stdout.write(self.style.SUCCESS("Pendencia criada e pendencias consultadas novamente."))
