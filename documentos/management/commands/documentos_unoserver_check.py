"""
Verifica se DOCUMENTOS_UNOSERVER_URL está acessível (porta TCP).
"""

from __future__ import annotations

import io
import statistics
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
            "--max-ms-resource",
            action="append",
            default=[],
            metavar="ARQUIVO=MS",
            help="Limite quente específico por recurso; repetível.",
        )
        parser.add_argument(
            "--iterations",
            type=int,
            default=1,
            help="Quantidade de conversões reais, sem cache (padrão: 1).",
        )
        parser.add_argument(
            "--max-cold-ms",
            type=float,
            default=None,
            help=(
                "Limite, em milissegundos, da PRIMEIRA conversão de cada modelo — "
                "a que paga o start do LibreOffice. Sem este argumento, a primeira "
                "conversão entra no mesmo limite das demais (comportamento antigo)."
            ),
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
            message = "DOCUMENTOS_UNOSERVER_URL não definido."
            if options["benchmark"]:
                raise CommandError(message)
            self.stdout.write(self.style.WARNING(message))
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

        elapsed_by_resource = {}
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
                    elapsed = (time.perf_counter() - started) * 1000
                    elapsed_by_resource.setdefault(filename, []).append(elapsed)
                    result_sizes[filename] = len(pdf)
        limit_ms = max(1.0, float(options["max_ms"]))
        cold_limit_ms = options["max_cold_ms"]
        resource_limits = self._parse_resource_limits(options["max_ms_resource"])
        unknown_resources = sorted(resource_limits.keys() - elapsed_by_resource.keys())
        if unknown_resources:
            raise CommandError(
                "limite configurado para recurso não medido: " + ", ".join(unknown_resources)
            )

        # A primeira conversão de cada modelo paga o start do LibreOffice/UNO e
        # custa uma ordem de grandeza a mais que as seguintes (medido no CI:
        # 1119 ms contra 96 e 93 ms). Somar as duas num `max` só faz o gate
        # reprovar por aquecimento e nada dizer sobre o regime estável — mas
        # jogar a primeira fora esconderia um custo que o usuário sente de
        # verdade, na primeira geração depois de um período ocioso. Por isso
        # são dois orçamentos, não um.
        frios = [] if cold_limit_ms is None else [values[0] for values in elapsed_by_resource.values()]
        warm_by_resource = {
            filename: values if cold_limit_ms is None else (values[1:] or values)
            for filename, values in elapsed_by_resource.items()
        }
        warm_statistics = {
            filename: round(
                max(values) if cold_limit_ms is None else statistics.median(values),
                1,
            )
            for filename, values in warm_by_resource.items()
        }
        elapsed_ms = max(warm_statistics.values())
        resources = ", ".join(
            f"{filename}→{size} bytes"
            for filename, size in result_sizes.items()
        )
        timings = "; ".join(
            f"{filename}: " + ", ".join(f"{value:.1f} ms" for value in values)
            for filename, values in elapsed_by_resource.items()
        )
        statistic_label = "máximo" if cold_limit_ms is None else "maior mediana quente"
        message = (
            f"conversão real: {statistic_label} {elapsed_ms:.1f} ms; "
            f"{iterations} execução(ões) por modelo; {timings}; {resources}"
        )
        if frios:
            frio_ms = max(frios)
            message = f"{message}; primeira conversão (a frio) {frio_ms:.1f} ms"
            cold_limit = max(1.0, float(cold_limit_ms))
            if frio_ms > cold_limit:
                raise CommandError(
                    f"{message}; SLA de partida a frio excedido ({cold_limit:.0f} ms)"
                )
        for filename, median_ms in warm_statistics.items():
            resource_limit = resource_limits.get(filename, limit_ms)
            if median_ms > resource_limit:
                raise CommandError(
                    f"{message}; {filename}: mediana quente {median_ms:.1f} ms; "
                    f"SLA excedido ({resource_limit:.0f} ms)"
                )
        medians = "; ".join(
            f"{filename}: mediana quente {median_ms:.1f} ms"
            for filename, median_ms in warm_statistics.items()
        )
        message = f"{message}; {medians}"
        self.stdout.write(self.style.SUCCESS(f"{message}; SLA atendido"))

    @staticmethod
    def _parse_resource_limits(raw_limits):
        limits = {}
        for raw in raw_limits:
            filename, separator, raw_value = raw.partition("=")
            filename = filename.strip()
            if not separator or not filename:
                raise CommandError(f"limite por recurso inválido: {raw!r}; use ARQUIVO=MS")
            try:
                value = float(raw_value)
            except ValueError as exc:
                raise CommandError(f"limite por recurso inválido: {raw!r}") from exc
            if value <= 0 or filename in limits:
                raise CommandError(f"limite por recurso inválido ou duplicado: {raw!r}")
            limits[filename] = value
        return limits
