"""Homologação controlada de um Ofício contra o eProtocolo de TREINAMENTO.

Fluxo seguro em três modos:

    # 1) Apenas valida (NÃO chama API, NÃO altera nada):
    python manage.py eprotocolo_homologar --oficio <ID> --dry-run

    # 2) Executa de verdade no ambiente de TREINAMENTO (exige confirmação):
    python manage.py eprotocolo_homologar --oficio <ID> --real

    # 3) Idem, concluindo o cadastro ao final:
    python manage.py eprotocolo_homologar --oficio <ID> --real --concluir

O modo ``--real`` só roda se: ambiente == ``treinamento`` (nunca produção),
credenciais configuradas, PDF válido, payload válido e confirmação explícita
``CONFIRMO TREINAMENTO`` digitada no terminal.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo import mappers
from integracoes.eprotocolo import services as epro
from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.exceptions import EProtocoloError

from protocolos import services as proto_services

CONFIRMACAO = "CONFIRMO TREINAMENTO"


class Command(BaseCommand):
    help = "Homologa um Ofício no eProtocolo de treinamento (dry-run por padrão)."

    def add_arguments(self, parser):
        parser.add_argument("--oficio", dest="oficio_id", type=int, required=True,
                            help="ID (pk) do Ofício a homologar.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Apenas valida; não chama API nem altera dados (padrão).")
        parser.add_argument("--real", action="store_true",
                            help="Executa de verdade no ambiente de treinamento.")
        parser.add_argument("--concluir", action="store_true",
                            help="Conclui o cadastro do protocolo ao final (só com --real).")
        parser.add_argument("--sim", action="store_true",
                            help="Pula a confirmação interativa (uso em automações controladas).")

    # -- handle ------------------------------------------------------------
    def handle(self, *args, **options):
        oficio = self._obter_oficio(options["oficio_id"])
        real = options.get("real", False)

        self.stdout.write(self.style.NOTICE(f"eProtocolo: {cfg.descricao_ambiente()}"))
        self.stdout.write(f"Ofício encontrado: {oficio} (id={oficio.pk})")

        # 1) Payload validado
        try:
            payload = mappers.mapear_oficio_para_payload_eprotocolo(oficio)
        except EProtocoloError as exc:
            raise CommandError(f"Payload inválido: {exc}") from exc
        self.stdout.write(self.style.SUCCESS("Payload válido: sim"))

        # 2) PDF
        conteudo, nome_arquivo, tipo = proto_services.resolver_pdf_documento(oficio)
        if conteudo is None:
            raise CommandError(
                "PDF do Ofício não pôde ser gerado neste ambiente. Verifique as "
                "dependências de conversão (LibreOffice/unoserver) ou anexe manualmente."
            )
        if not conteudo[:5].startswith(b"%PDF"):
            raise CommandError("Arquivo gerado não é um PDF válido (assinatura %PDF ausente).")
        md5 = epro.calcular_md5(conteudo)
        self.stdout.write(self.style.SUCCESS(f"PDF gerado: sim ({nome_arquivo}, {len(conteudo)} bytes)"))
        self.stdout.write(f"MD5: {md5}")

        if not real:
            self._resumo_dry_run(payload)
            return

        self._executar_real(oficio, options)

    # -- dry-run -----------------------------------------------------------
    def _resumo_dry_run(self, payload):
        self.stdout.write(self.style.NOTICE("\n== Resumo (dry-run) =="))
        self.stdout.write(f"tipoOrigem: {payload.get('tipoOrigem')}")
        self.stdout.write(f"numeroDocumento: {payload.get('numeroDocumento')}/{payload.get('anoDocumento')}")
        self.stdout.write(f"assunto: {payload.get('assunto')}")
        self.stdout.write(f"codOrgao: {payload.get('codOrgao')}  codLocalOrigem: {payload.get('codLocalOrigem')}")
        self.stdout.write(f"codAssunto: {payload.get('codAssunto')}  codEspecie: {payload.get('codEspecie')}")
        self.stdout.write(f"Ambiente: {cfg.ambiente()}")
        self.stdout.write("Operação real: não")
        self.stdout.write(self.style.SUCCESS("Pronto para homologação real."))

    # -- real --------------------------------------------------------------
    def _executar_real(self, oficio, options):
        # Guardas de segurança
        if not cfg.is_treinamento():
            raise CommandError(
                f"--real só é permitido no ambiente de treinamento "
                f"(ambiente atual: {cfg.ambiente()})."
            )
        if cfg.em_modo_mock():
            raise CommandError(
                "Credenciais ausentes — sistema em modo mock. Configure o .env "
                "antes de usar --real. Rode: python manage.py eprotocolo_check"
            )

        if not options.get("sim") and not self._confirmar():
            self.stdout.write(self.style.WARNING("Operação cancelada pelo usuário."))
            return

        try:
            self.stdout.write("Criando protocolo no eProtocolo (treinamento)...")
            protocolo = proto_services.criar_protocolo_a_partir_de_documento(oficio)
            self.stdout.write(self.style.SUCCESS(f"Protocolo criado: {protocolo.numero_display}"))

            self.stdout.write("Enviando PDF...")
            doc = proto_services.enviar_documento_principal(protocolo)
            if doc is None:
                self.stdout.write(self.style.WARNING("PDF não enviado (geração indisponível)."))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Documento enviado: código {doc.codigo_documento_eprotocolo or '(s/ código)'}"
                ))

            if options.get("concluir"):
                self.stdout.write("Concluindo cadastro...")
                proto_services.concluir_cadastro_eprotocolo(protocolo)
                self.stdout.write(self.style.SUCCESS("Cadastro concluído."))

            self.stdout.write("Consultando situação e coleções...")
            proto_services.sincronizar_protocolo(protocolo)
            protocolo.refresh_from_db()
            self.stdout.write(self.style.SUCCESS(
                f"Situação atual: {protocolo.situacao_eprotocolo or '(s/ situação)'} "
                f"| local: {protocolo.nome_local_atual or protocolo.cod_local_atual or '-'}"
            ))
            self.stdout.write(self.style.SUCCESS(
                f"Concluído. Veja o protocolo {protocolo.numero_display} (id={protocolo.pk})."
            ))
        except EProtocoloError as exc:
            raise CommandError(
                f"Falha na homologação real ({getattr(exc, 'status_code', '-')}): {exc}"
            ) from exc

    def _confirmar(self) -> bool:
        self.stdout.write(self.style.WARNING(
            f"\nIsto fará chamadas REAIS ao eProtocolo de treinamento.\n"
            f"Digite exatamente '{CONFIRMACAO}' para continuar:"
        ))
        try:
            resposta = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            return False
        return resposta == CONFIRMACAO

    # -- helpers -----------------------------------------------------------
    def _obter_oficio(self, oficio_id):
        from oficios.models import Oficio
        try:
            return Oficio.objects.get(pk=oficio_id)
        except Oficio.DoesNotExist as exc:
            raise CommandError(f"Ofício com id={oficio_id} não encontrado.") from exc
