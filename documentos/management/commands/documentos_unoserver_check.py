"""
Verifica se DOCUMENTOS_UNOSERVER_URL está acessível (porta TCP).
"""

from __future__ import annotations

import io
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.test.utils import override_settings
from docx import Document

from documentos.services.adapters.libreoffice_pdf import convert_docx_to_pdf_unoserver
from documentos.services.adapters.libreoffice_pdf import convert_xlsx_to_pdf_unoserver
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
        parser.add_argument(
            "--iterations",
            type=int,
            default=1,
            help="Quantidade de conversões reais, sem cache (padrão: 1).",
        )
        parser.add_argument(
            "--representative-resources",
            action="store_true",
            help=(
                "Mede os maiores modelos DOCX e XLSX reais do sistema, "
                "em vez do documento sintético mínimo."
            ),
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

        targets = []
        if options["representative_resources"]:
            resources_dir = Path(settings.BASE_DIR) / "documentos" / "resources"
            for suffix in (".docx", ".xlsx"):
                candidates = list(resources_dir.glob(f"*{suffix}"))
                if candidates:
                    largest = max(candidates, key=lambda path: path.stat().st_size)
                    targets.append((largest.name, suffix, largest.read_bytes()))
        if not targets:
            docx = io.BytesIO()
            document = Document()
            document.add_paragraph("Verificação de desempenho do conversor.")
            document.save(docx)
            targets = [("sintetico.docx", ".docx", docx.getvalue())]

        elapsed_values = []
        result_sizes = {}
        iterations = max(1, int(options["iterations"]))
        with override_settings(DOCUMENTOS_BINARY_CONVERSION_CACHE=False):
            for filename, suffix, payload in targets:
                for _ in range(iterations):
                    started = time.perf_counter()
                    if suffix == ".xlsx":
                        pdf = convert_xlsx_to_pdf_unoserver(
                            xlsx_bytes=payload,
                            unoserver_url=url,
                            timeout_seconds=timeout,
                        )
                    else:
                        pdf = convert_docx_to_pdf_unoserver(
                            docx_bytes=payload,
                            unoserver_url=url,
                            timeout_seconds=timeout,
                        )
                    elapsed_values.append((time.perf_counter() - started) * 1000)
                    result_sizes[filename] = len(pdf)
        elapsed_ms = max(elapsed_values)
        limit_ms = max(1.0, float(options["max_ms"]))
        resources = ", ".join(
            f"{filename}→{size} bytes"
            for filename, size in result_sizes.items()
        )
        message = (
            f"conversão real: máximo {elapsed_ms:.1f} ms; "
            f"{iterations} execução(ões) por modelo; {resources}"
        )
        if elapsed_ms >= limit_ms:
            raise CommandError(f"{message}; SLA excedido ({limit_ms:.0f} ms)")
        self.stdout.write(self.style.SUCCESS(f"{message}; SLA atendido"))
