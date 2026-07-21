"""Atribui a area informada a registros legados com area nula.

Uso tipico apos ativar multi-tenant numa instalacao que ja tinha dados::

    python manage.py backfill_area_legado --area DPC --dry-run
    python manage.py backfill_area_legado --area DPC
"""

from __future__ import annotations

from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.db import transaction


# (app_label, model_name) com campo ``area`` nullable herdado do legado.
_MODELOS = (
    ("cadastros", "Unidade"),
    ("cadastros", "Cargo"),
    ("cadastros", "Combustivel"),
    ("cadastros", "Servidor"),
    ("cadastros", "Viatura"),
    ("eventos", "Evento"),
    ("eventos", "TipoEvento"),
    ("eventos", "ModeloMotivoEvento"),
    ("oficios", "Oficio"),
    ("oficios", "ModeloMotivoOficio"),
    ("oficios", "OficioNumeroLacuna"),
    ("roteiros", "Roteiro"),
    ("termos", "TermoAutorizacao"),
    ("ordens_servico", "OrdemServico"),
    ("planos_trabalho", "PlanoTrabalho"),
    ("documentos", "DocumentoArtefato"),
    ("prestacoes_contas", "PrestacaoContas"),
)


class Command(BaseCommand):
    help = "Preenche area nula em registros legados com a area informada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--area",
            required=True,
            help="Sigla da AreaTrabalho que recebera os registros sem area.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Apenas conta quantos registros seriam atualizados.",
        )

    def handle(self, *args, **options):
        from usuarios.models import AreaTrabalho

        sigla = (options["area"] or "").strip()
        area = AreaTrabalho.objects.filter(sigla__iexact=sigla).first()
        if area is None:
            raise CommandError(f"Area com sigla '{sigla}' nao encontrada.")

        dry_run = options["dry_run"]
        total = 0
        atualizados = 0
        conflitos = 0

        for app_label, model_name in _MODELOS:
            model = apps.get_model(app_label, model_name)
            if not hasattr(model, "area"):
                continue
            qs = model.objects.filter(area__isnull=True)
            count = qs.count()
            if not count:
                continue
            total += count
            self.stdout.write(f"{app_label}.{model_name}: {count}")
            if dry_run:
                continue

            ok, skipped = self._atualizar_modelo(model, qs, area)
            atualizados += ok
            conflitos += skipped
            if skipped:
                self.stdout.write(
                    self.style.WARNING(
                        f"  {skipped} registro(s) ignorados por conflito de unicidade."
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Dry-run: {total} registro(s) seriam atualizados.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Atualizados {atualizados} registro(s) para area {area.sigla}."
            )
        )
        if conflitos:
            self.stdout.write(
                self.style.WARNING(
                    f"{conflitos} registro(s) permaneceram sem area "
                    "(ja existia equivalente na area destino)."
                )
            )

    def _atualizar_modelo(self, model, qs, area) -> tuple[int, int]:
        """Atualiza em lote; se houver unicidade, cai para registro a registro."""
        try:
            with transaction.atomic():
                updated = qs.update(area=area)
            return updated, 0
        except IntegrityError:
            pass

        ok = 0
        skipped = 0
        for pk in list(qs.values_list("pk", flat=True)):
            try:
                with transaction.atomic():
                    updated = model.objects.filter(pk=pk, area__isnull=True).update(area=area)
                if updated:
                    ok += 1
                else:
                    skipped += 1
            except IntegrityError:
                skipped += 1
        return ok, skipped
