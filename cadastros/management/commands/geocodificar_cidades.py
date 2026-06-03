"""
Preenche latitude/longitude de cidades que não possuem coordenadas,
consultando a API Nominatim (OpenStreetMap). Gratuita, sem chave de API.

Uso:
    python manage.py geocodificar_cidades
    python manage.py geocodificar_cidades --cidade "BALSA NOVA" --uf PR
    python manage.py geocodificar_cidades --dry-run
"""

from __future__ import annotations

import time

import requests
from django.core.management.base import BaseCommand
from django.db.models import Q

from cadastros.models import Cidade


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GerenciadorViagens/1.0"
DELAY_SEGUNDOS = 1.1  # Nominatim exige ≥ 1 req/s


def _buscar_coordenadas(nome: str, uf: str) -> tuple[float, float] | None:
    """Retorna (latitude, longitude) ou None se não encontrar."""
    params = {
        "q": f"{nome}, {uf}, Brasil",
        "format": "json",
        "limit": 1,
        "countrycodes": "br",
        "addressdetails": 0,
    }
    headers = {"User-Agent": USER_AGENT}
    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        resultados = r.json()
        if resultados:
            return float(resultados[0]["lat"]), float(resultados[0]["lon"])
    except (requests.RequestException, ValueError, KeyError):
        pass
    return None


class Command(BaseCommand):
    help = "Geocodifica cidades sem latitude/longitude via Nominatim (OpenStreetMap)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cidade",
            type=str,
            default="",
            help="Filtrar por nome de cidade (parcial).",
        )
        parser.add_argument(
            "--uf",
            type=str,
            default="",
            help="Filtrar por UF (ex.: PR, SP).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Exibe o que seria atualizado sem salvar.",
        )
        parser.add_argument(
            "--todas",
            action="store_true",
            help="Inclui cidades que já possuem coordenadas (sobrescreve).",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        sobrescrever: bool = options["todas"]
        filtro_nome: str = options["cidade"].strip().upper()
        filtro_uf: str = options["uf"].strip().upper()

        qs = Cidade.objects.select_related("estado").order_by("uf", "nome")

        if not sobrescrever:
            qs = qs.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True))

        if filtro_nome:
            qs = qs.filter(nome__icontains=filtro_nome)

        if filtro_uf:
            qs = qs.filter(uf=filtro_uf)

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS("Nenhuma cidade a geocodificar."))
            return

        self.stdout.write(
            self.style.NOTICE(f"{'[DRY-RUN] ' if dry_run else ''}Geocodificando {total} cidade(s)…\n")
        )

        atualizadas = 0
        nao_encontradas = 0
        erros = 0

        for i, cidade in enumerate(qs, start=1):
            label = f"{cidade.nome}/{cidade.uf}"
            self.stdout.write(f"  [{i}/{total}] {label}… ", ending="")

            coords = _buscar_coordenadas(cidade.nome, cidade.uf)

            if coords is None:
                self.stdout.write(self.style.WARNING("não encontrada"))
                nao_encontradas += 1
            else:
                lat, lon = coords
                self.stdout.write(self.style.SUCCESS(f"lat={lat:.7f} lon={lon:.7f}"))
                if not dry_run:
                    cidade.latitude = lat
                    cidade.longitude = lon
                    cidade.save(update_fields=["latitude", "longitude"])
                atualizadas += 1

            if i < total:
                time.sleep(DELAY_SEGUNDOS)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Resumo"))
        self.stdout.write(f"  Processadas:      {total}")
        self.stdout.write(f"  Atualizadas:      {atualizadas}")
        self.stdout.write(f"  Não encontradas:  {nao_encontradas}")
        if erros:
            self.stdout.write(self.style.ERROR(f"  Erros:            {erros}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry-run: nenhuma alteração foi salva."))
        else:
            self.stdout.write(self.style.SUCCESS("\nConcluído."))
