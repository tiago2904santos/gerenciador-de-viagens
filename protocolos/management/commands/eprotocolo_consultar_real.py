from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from integracoes.eprotocolo.exceptions import EProtocoloError
from protocolos import services as proto_services
from protocolos.models import mascarar_cpf

from ._eprotocolo_real import dica_erro, exigir_real_controlado_configurado


class Command(BaseCommand):
    help = "Consulta um unico protocolo real em modo somente consulta."

    def add_arguments(self, parser):
        parser.add_argument("--protocolo", required=True, help="Numero do protocolo autorizado.")

    def handle(self, *args, **options):
        exigir_real_controlado_configurado()
        numero = options["protocolo"].strip()
        try:
            dados = proto_services.consultar_protocolo_real(numero)
        except EProtocoloError as exc:
            self.stderr.write(self.style.ERROR(f"Falha: {exc}"))
            self.stderr.write(self.style.WARNING(dica_erro(exc)))
            raise CommandError("Consulta real falhou.") from exc

        protocolo = dados["protocolo"]
        self.stdout.write(f"Protocolo consultado: {numero}")
        self.stdout.write(f"Situacao: {protocolo.get('situacao', '') or '-'}")
        self.stdout.write(
            f"Local atual: {protocolo.get('nomeLocalAtual') or protocolo.get('codLocalAtual') or '-'}"
        )
        responsavel = protocolo.get("nomeResponsavelAtual") or "-"
        cpf = mascarar_cpf(protocolo.get("cpfResponsavelAtual", ""))
        self.stdout.write(f"Responsavel atual: {responsavel} {cpf}".strip())
        self.stdout.write(
            f"Documentos encontrados: {len(proto_services._extrair_itens(dados['documentos'], 'documentos'))}"
        )
        self.stdout.write(
            f"Documentos do volume encontrados: {len(proto_services._extrair_itens(dados['documentos_volume'], 'documentos'))}"
        )
        self.stdout.write(
            f"Tramitacoes encontradas: {len(proto_services._extrair_itens(dados['tramitacoes'], 'tramitacoes'))}"
        )
        self.stdout.write(
            f"Movimentacoes encontradas: {len(proto_services._extrair_itens(dados['movimentacoes'], 'movimentacoes'))}"
        )
        self.stdout.write(
            f"Pendencias encontradas: {len(proto_services._extrair_itens(dados['pendencias'], 'pendencias'))}"
        )
        self.stdout.write(f"Assinaturas consultadas: {len(dados['assinaturas'])}")
        self.stdout.write("Operacao: somente consulta")
        self.stdout.write("Alteracoes no eProtocolo: nenhuma")
