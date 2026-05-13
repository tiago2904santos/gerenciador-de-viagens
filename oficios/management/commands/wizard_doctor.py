"""Diagnóstico rápido: qual código do app `oficios` está carregado e se as rotas do wizard resolvem."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse

import oficios.urls


class Command(BaseCommand):
    help = (
        "Imprime o caminho de oficios/urls.py carregado, BASE_DIR e reverse() das rotas do wizard."
    )

    def handle(self, *args, **options):
        self.stdout.write(f"oficios.urls.__file__ = {oficios.urls.__file__}")
        self.stdout.write(f"settings.BASE_DIR      = {settings.BASE_DIR}")
        routes = (
            "oficios:wizard_justificativa",
            "oficios:wizard_documentos",
            "oficios:wizard_resumo",
            "oficios:wizard_roteiro",
        )
        for name in routes:
            try:
                url = reverse(name, args=[1])
                self.stdout.write(self.style.SUCCESS(f"{name:40} -> {url}"))
            except NoReverseMatch as exc:
                self.stdout.write(self.style.ERROR(f"{name:40} -> ERRO: {exc}"))
