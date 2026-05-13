"""
Baixa estados e municípios brasileiros da API oficial do IBGE e importa via ``services_importacao``.
"""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

import requests
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from cadastros.services_importacao import importar_base_geografica


IBGE_ESTADOS = "https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=id"
IBGE_MUNICIPIOS = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=id"


def _fetch_json(url: str, timeout: int) -> list | dict:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _uf_municipio(m: dict) -> str | None:
    try:
        return m["microrregiao"]["mesorregiao"]["UF"]["sigla"]
    except (KeyError, TypeError):
        pass
    try:
        return m["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]
    except (KeyError, TypeError):
        return None


def _write_temp_csv(content: str) -> Path:
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8-sig",
        newline="",
        suffix=".csv",
        prefix="ibge_",
        delete=False,
    ) as f:
        f.write(content)
        return Path(f.name)


class Command(BaseCommand):
    help = "Baixa estados e todos os municípios do IBGE (API) e grava na base (estados + cidades)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simula importação (rollback ao final).",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=180,
            help="Timeout HTTP em segundos (municípios ~5,5k linhas).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        timeout: int = options["timeout"]

        self.stdout.write(self.style.NOTICE("A descarregar estados (IBGE)…"))
        estados_json = _fetch_json(IBGE_ESTADOS, timeout=timeout)
        if not isinstance(estados_json, list):
            raise CommandError("Resposta inesperada da API de estados.")

        buf_est = io.StringIO()
        w_est = csv.writer(buf_est, delimiter=",")
        w_est.writerow(["COD", "NOME", "SIGLA"])
        for e in estados_json:
            w_est.writerow([e.get("id"), e.get("nome"), e.get("sigla")])

        self.stdout.write(self.style.NOTICE("A descarregar municípios (IBGE)…"))
        mun_json = _fetch_json(IBGE_MUNICIPIOS, timeout=timeout)
        if not isinstance(mun_json, list):
            raise CommandError("Resposta inesperada da API de municípios.")

        buf_mun = io.StringIO()
        w_mun = csv.writer(buf_mun, delimiter=";")
        w_mun.writerow(["id_municipio", "uf", "municipio", "longitude", "latitude"])
        for m in mun_json:
            uf = _uf_municipio(m)
            if not uf:
                self.stdout.write(self.style.WARNING(f"Município sem UF: id={m.get('id')}"))
                continue
            nome = m.get("nome") or ""
            mid = m.get("id")
            w_mun.writerow([mid, uf, nome, "", ""])

        est_path = _write_temp_csv(buf_est.getvalue())
        mun_path = _write_temp_csv(buf_mun.getvalue())
        try:
            self.stdout.write(
                self.style.NOTICE(
                    f"A importar {len(estados_json)} estados e {len(mun_json)} municípios…",
                ),
            )
            resultado = importar_base_geografica(
                est_path,
                municipios_code_path=mun_path,
                dry_run=dry_run,
                encoding="utf-8-sig",
            )

            for ln, msg in resultado.estados.erros:
                self.stdout.write(self.style.ERROR(f"Estados L{ln}: {msg}"))
            for ln, msg in resultado.cidades.erros:
                if ln > 0:
                    self.stdout.write(self.style.ERROR(f"Cidades L{ln}: {msg}"))

            self.stdout.write(self.style.MIGRATE_HEADING("Estados"))
            self.stdout.write(f"  Linhas: {resultado.estados.total_linhas}")
            self.stdout.write(f"  Criados: {resultado.estados.criados}")
            self.stdout.write(f"  Existentes: {resultado.estados.existentes}")
            self.stdout.write(f"  Atualizados: {resultado.estados.atualizados}")

            self.stdout.write(self.style.MIGRATE_HEADING("Municípios"))
            self.stdout.write(f"  Linhas: {resultado.cidades.total_linhas}")
            self.stdout.write(f"  Criadas: {resultado.cidades.criadas}")
            self.stdout.write(f"  Existentes: {resultado.cidades.existentes}")
            self.stdout.write(f"  Capitais marcadas: {resultado.cidades.capitais_marcadas}")

            if dry_run:
                self.stdout.write(self.style.WARNING("Dry-run: alterações revertidas."))
            else:
                self.stdout.write(self.style.SUCCESS("Importação geográfica concluída."))
        finally:
            est_path.unlink(missing_ok=True)
            mun_path.unlink(missing_ok=True)
