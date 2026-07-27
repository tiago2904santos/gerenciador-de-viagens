from __future__ import annotations

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.db import transaction

from usuarios.models import AreaTrabalho


class Command(BaseCommand):
    help = "Atribui registros legados com area=NULL a uma área explícita."

    def add_arguments(self, parser):
        parser.add_argument("--area", required=True, help="Sigla da área de destino.")
        parser.add_argument(
            "--commit",
            action="store_true",
            help="Aplica as alterações; sem esta opção apenas exibe o plano.",
        )

    def handle(self, *args, **options):
        try:
            area = AreaTrabalho.objects.get(
                sigla=options["area"].strip().upper(),
                ativa=True,
            )
        except AreaTrabalho.DoesNotExist as exc:
            raise CommandError("Área ativa não encontrada.") from exc

        planned = []
        skipped = []
        for model in apps.get_models():
            field = next(
                (field for field in model._meta.concrete_fields if field.name == "area"),
                None,
            )
            if field is None or not field.null:
                continue
            queryset = model._default_manager.filter(area__isnull=True)
            try:
                count = queryset.count()
            except Exception:
                # Permite executar o comando durante uma implantação em que
                # uma tabela nova ainda não exista.
                continue
            if not count:
                continue
            if field.one_to_one and model._default_manager.filter(area=area).exists():
                skipped.append((model._meta.label, count, "conflito OneToOne"))
                continue
            safe_ids = []
            for instance in queryset.order_by(model._meta.pk.name).iterator():
                instance.area = area
                try:
                    instance.validate_unique()
                    instance.validate_constraints()
                except ValidationError:
                    skipped.append(
                        (model._meta.label, 1, f"conflito de unicidade no id={instance.pk}"),
                    )
                    continue
                safe_ids.append(instance.pk)
            if safe_ids:
                planned.append((model, safe_ids))

        for model, ids in planned:
            self.stdout.write(f"{model._meta.label}: {len(ids)}")
        for label, count, reason in skipped:
            self.stdout.write(self.style.WARNING(f"{label}: {count} ignorado(s), {reason}"))

        if not options["commit"]:
            self.stdout.write(self.style.WARNING("Simulação: use --commit para aplicar."))
            return

        with transaction.atomic():
            for model, ids in planned:
                for instance in model._default_manager.filter(pk__in=ids):
                    instance.area = area
                    try:
                        with transaction.atomic():
                            instance.save(update_fields=["area"])
                    except (IntegrityError, ValidationError):
                        self.stdout.write(
                            self.style.WARNING(
                                f"{model._meta.label}: id={instance.pk} ignorado por conflito.",
                            ),
                        )
        self.stdout.write(self.style.SUCCESS("Backfill de áreas concluído."))
