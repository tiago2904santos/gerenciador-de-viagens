"""
Verifica se DOCUMENTOS_UNOSERVER_URL está acessível (porta TCP).
"""

from __future__ import annotations

import io
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from docx import Document

from documentos.services.adapters.libreoffice_pdf import convert_docx_to_pdf_unoserver
from documentos.services.adapters.libreoffice_pdf import unoserver_healthcheck


class Command(BaseCommand):
    help = "Testa conectividade TCP ao unoserver configurado em DOCUMENTOS_UNOSERVER_URL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--benchmark",
            action="store_true",
            help="Executa uma conversão DOCX→PDF real.",
        )
        parser.add_argument(
            "--max-ms",
            type=float,
            default=1000,
            help="Limite do benchmark em milissegundos (padrão: 1000).",
        )

    def handle(self, *args, **options):
        url = (getattr(settings, "DOCUMENTOS_UNOSERVER_URL", None) or "").strip()
        if not url:
            self.stdout.write(self.style.WARNING("DOCUMENTOS_UNOSERVER_URL não definido."))
            return
        timeout = float(getattr(settings, "DOCUMENTOS_UNOSERVER_TIMEOUT_SECONDS", 3) or 3)
        ok = unoserver_healthcheck(url, timeout=timeout)
        if not ok:
            raise CommandError(f"unoserver inacessível: {url}")
        self.stdout.write(self.style.SUCCESS(f"unoserver acessível: {url}"))

        if not options["benchmark"]:
            return

        docx = io.BytesIO()
        document = Document()
        document.add_paragraph("Verificação de desempenho do conversor.")
        document.save(docx)
        started = time.perf_counter()
        pdf = convert_docx_to_pdf_unoserver(
            docx_bytes=docx.getvalue(),
            unoserver_url=url,
            timeout_seconds=timeout,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        limit_ms = max(1.0, float(options["max_ms"]))
        message = f"conversão real: {elapsed_ms:.1f} ms ({len(pdf)} bytes)"
        if elapsed_ms >= limit_ms:
            raise CommandError(f"{message}; SLA excedido ({limit_ms:.0f} ms)")
        self.stdout.write(self.style.SUCCESS(f"{message}; SLA atendido"))
