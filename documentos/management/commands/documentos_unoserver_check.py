"""
Verifica se DOCUMENTOS_UNOSERVER_URL está acessível (porta TCP).
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from documentos.services.adapters.libreoffice_pdf import unoserver_healthcheck


class Command(BaseCommand):
    help = "Testa conectividade TCP ao unoserver configurado em DOCUMENTOS_UNOSERVER_URL."

    def handle(self, *args, **options):
        url = (getattr(settings, "DOCUMENTOS_UNOSERVER_URL", None) or "").strip()
        if not url:
            self.stdout.write(self.style.WARNING("DOCUMENTOS_UNOSERVER_URL não definido."))
            return
        timeout = float(getattr(settings, "DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS", 3) or 3)
        ok = unoserver_healthcheck(url, timeout=timeout)
        if ok:
            self.stdout.write(self.style.SUCCESS(f"unoserver acessível: {url}"))
        else:
            self.stdout.write(self.style.ERROR(f"unoserver inacessível: {url}"))
