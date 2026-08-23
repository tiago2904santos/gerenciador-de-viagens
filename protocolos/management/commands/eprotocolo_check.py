"""Diagnóstico de configuração da integração eProtocolo (não chama a rede).

Mostra o ambiente ativo, se está em mock ou modo real, e valida a presença das
variáveis obrigatórias — sempre com credenciais mascaradas. Nunca exibe o
``client_secret`` nem toca a API.

Exemplos:
    python manage.py eprotocolo_check
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from integracoes.eprotocolo import settings as cfg
from integracoes.eprotocolo.schemas import ESCOPOS_ESPERADOS


class Command(BaseCommand):
    help = "Valida a configuração da integração eProtocolo (sem chamar a API)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--escopos", action="store_true",
            help="Lista os escopos OAuth2 esperados pelo barramento spi-servicos.",
        )

    def handle(self, *args, **options):
        info = cfg.validar_configuracao()

        def linha(rotulo, valor):
            self.stdout.write(f"{rotulo}: {valor}")

        self.stdout.write(self.style.NOTICE("== Diagnóstico eProtocolo =="))
        linha("Ambiente", info["ambiente"])
        linha("Base URL", "configurada" if info["base_url_configurada"] else "AUSENTE")
        linha("Token URL", "configurada" if info["token_url_configurada"] else "AUSENTE")
        linha("Client ID", info["client_id"])
        linha("Client Secret", "configurado" if info["client_secret_configurado"] else "AUSENTE")
        linha("Consumer ID", info["consumer_id"])
        linha("Modo real", "sim" if info["modo_real"] else "não")
        linha("Produção", "sim" if info["producao"] else "não")

        if info["producao"]:
            self.stdout.write(self.style.WARNING(
                "Atenção: ambiente de PRODUÇÃO. Esta etapa só prevê mock/treinamento."
            ))

        if info["ok"]:
            self.stdout.write(self.style.SUCCESS("Status: configuração mínima OK"))
        else:
            faltantes = ", ".join(info["campos_faltantes"]) or "(desconhecido)"
            self.stdout.write(self.style.ERROR(
                f"Status: configuração incompleta — faltam: {faltantes}"
            ))

        if not info["modo_real"]:
            self.stdout.write(
                "Observação: em modo mock nenhuma chamada real é feita — o sistema "
                "opera normalmente sem credenciais."
            )

        if options.get("escopos"):
            self.stdout.write(self.style.NOTICE("\nEscopos OAuth2 esperados:"))
            for escopo in ESCOPOS_ESPERADOS:
                self.stdout.write(f"  - {escopo}")
