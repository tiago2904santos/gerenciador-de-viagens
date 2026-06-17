from __future__ import annotations

from django.core.management.base import BaseCommand

from integracoes.eprotocolo import settings as cfg


class Command(BaseCommand):
    help = "Valida a configuracao real_controlado do eProtocolo sem rede e sem banco."

    def handle(self, *args, **options):
        info = cfg.validar_configuracao()
        self.stdout.write(f"Ambiente: {info['ambiente']}")
        self.stdout.write(f"Read-only: {'ativo' if info['read_only'] else 'inativo'}")
        self.stdout.write(
            f"Mutacoes reais: {'liberadas' if info['mutations_enabled'] else 'bloqueadas'}"
        )
        self.stdout.write(
            f"Modo real controlado: {'sim' if info['real_controlado'] else 'nao'}"
        )
        self.stdout.write(
            f"Base URL: {'configurada' if info['base_url_configurada'] else 'AUSENTE'}"
        )
        self.stdout.write(
            f"Token URL: {'configurada' if info['token_url_configurada'] else 'AUSENTE'}"
        )
        self.stdout.write(f"Client ID: {info['client_id']}")
        self.stdout.write(
            f"Client Secret: {'configurado' if info['client_secret_configurado'] else 'AUSENTE'}"
        )
        self.stdout.write(f"Consumer ID: {info['consumer_id']}")
        self.stdout.write(f"Timeout: {info['timeout']}")
        self.stdout.write(f"SSL: {'verificado' if info['verify_ssl'] else 'desativado'}")

        if info["ok"] and info["real_controlado"]:
            self.stdout.write(self.style.SUCCESS("Status: configuracao minima OK"))
            return
        faltantes = ", ".join(info["campos_faltantes"]) or "ambiente real_controlado"
        self.stdout.write(self.style.ERROR(f"Status: configuracao incompleta - {faltantes}"))
