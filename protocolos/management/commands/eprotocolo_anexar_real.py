from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo.exceptions import EProtocoloError
from protocolos import services as proto_services
from protocolos.models import Protocolo

from ._eprotocolo_real import (
    confirmar_operacao_real,
    dica_erro,
    exigir_real_controlado_configurado,
    validar_pdf,
)


class Command(BaseCommand):
    help = "Anexa um PDF a um protocolo real, com confirmacao manual forte."

    def add_arguments(self, parser):
        parser.add_argument("--protocolo", required=True)
        parser.add_argument("--arquivo", required=True)
        parser.add_argument("--real", action="store_true")

    def handle(self, *args, **options):
        exigir_real_controlado_configurado()
        numero = options["protocolo"].strip()
        conteudo, nome_arquivo = validar_pdf(options["arquivo"])
        md5 = epro.calcular_md5(conteudo)
        confirmado = confirmar_operacao_real(
            self.stdout,
            [
                f"operacao: anexar_documento",
                f"protocolo: {numero}",
                f"arquivo: {nome_arquivo}",
                f"tamanho: {len(conteudo)} bytes",
                f"md5: {md5}",
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
        try:
            proto_services.anexar_documento(
                protocolo,
                tipo="ANEXO",
                nome_arquivo=nome_arquivo,
                conteudo=conteudo,
                real=options["real"],
                confirmado=True,
            )
            proto_services.sincronizar_protocolo(protocolo)
        except EProtocoloError as exc:
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            self.stderr.write(self.style.WARNING(dica_erro(exc)))
            raise CommandError("Anexo real falhou.") from exc

        self.stdout.write(self.style.SUCCESS("Documento anexado e documentos consultados novamente."))
