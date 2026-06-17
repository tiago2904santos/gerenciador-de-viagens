from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo.exceptions import EProtocoloError
from protocolos import services as proto_services

from ._eprotocolo_real import confirmar_operacao_real, dica_erro, exigir_real_controlado_configurado


class Command(BaseCommand):
    help = "Cria protocolo real a partir de um Oficio, com confirmacao manual forte."

    def add_arguments(self, parser):
        parser.add_argument("--oficio", type=int, required=True)
        parser.add_argument("--real", action="store_true")
        parser.add_argument("--concluir", action="store_true")

    def handle(self, *args, **options):
        exigir_real_controlado_configurado()
        from oficios.models import Oficio

        try:
            oficio = Oficio.objects.get(pk=options["oficio"])
        except Oficio.DoesNotExist as exc:
            raise CommandError(f"Oficio com id={options['oficio']} nao encontrado.") from exc

        conteudo, nome_arquivo, _tipo = proto_services.resolver_pdf_documento(oficio)
        if conteudo is None or not conteudo.startswith(b"%PDF"):
            raise CommandError("PDF do Oficio indisponivel ou invalido.")

        confirmado = confirmar_operacao_real(
            self.stdout,
            [
                "operacao: criar_protocolo",
                f"oficio: {oficio}",
                f"pdf: {nome_arquivo}",
                f"concluir: {'sim' if options['concluir'] else 'nao'}",
            ],
        )
        if not confirmado:
            self.stdout.write(self.style.WARNING("Operacao cancelada."))
            return

        try:
            protocolo = proto_services.criar_protocolo_a_partir_de_documento(
                oficio,
                real=options["real"],
                confirmado=True,
            )
            proto_services.enviar_documento_principal(
                protocolo,
                real=options["real"],
                confirmado=True,
            )
            if options["concluir"]:
                proto_services.concluir_cadastro_eprotocolo(
                    protocolo,
                    real=options["real"],
                    confirmado=True,
                )
            proto_services.sincronizar_protocolo(protocolo)
        except EProtocoloError as exc:
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            self.stderr.write(self.style.WARNING(dica_erro(exc)))
            raise CommandError("Criacao real falhou.") from exc

        self.stdout.write(self.style.SUCCESS(f"Protocolo criado: {protocolo.numero_display}"))
