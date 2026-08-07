from __future__ import annotations

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.db import transaction
from django.db.models import Max
from django.db.models import Q

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
        parser.add_argument(
            "--resolve-conflicts",
            action="store_true",
            help=(
                "Preserva e resolve conflitos conhecidos: consolida cadastros "
                "inequívocos e renumera documentos antes do backfill."
            ),
        )

    def _merge_reverse_relations(self, source, target) -> None:
        """Reaponta FKs/M2M reversas antes de remover uma duplicata inequívoca."""
        # Relações com ``related_name='+'`` não aparecem em
        # ``source._meta.related_objects``. A varredura de campos concretos
        # garante que nenhuma FK oculta continue apontando para o legado.
        for model in apps.get_models():
            for field in model._meta.concrete_fields:
                if (
                    field.remote_field is not None
                    and field.remote_field.model is source.__class__
                ):
                    model._default_manager.filter(
                        **{field.attname: source.pk},
                    ).update(**{field.attname: target.pk})

        for relation in source._meta.related_objects:
            accessor = relation.get_accessor_name()
            try:
                related = getattr(source, accessor)
            except relation.related_model.DoesNotExist:
                continue
            if relation.one_to_many:
                related.update(**{relation.field.name: target})
                continue
            if relation.many_to_many:
                for owner in related.all():
                    manager = getattr(owner, relation.field.name)
                    manager.add(target)
                    manager.remove(source)
                continue
            setattr(related, relation.field.name, target)
            related.save(update_fields=[relation.field.name])

    def _merge_configuracao(self, source, target) -> None:
        """Completa a configuração da área sem sobrescrever valores já definidos."""
        changed = []
        for field in source._meta.concrete_fields:
            if field.primary_key or field.name in {
                "area",
                "created_at",
                "updated_at",
                "criado_em",
                "atualizado_em",
            }:
                continue
            source_value = getattr(source, field.attname)
            target_value = getattr(target, field.attname)
            if target_value in (None, "") and source_value not in (None, ""):
                setattr(target, field.attname, source_value)
                changed.append(field.name)
        if changed:
            target.save(update_fields=changed)
        self._merge_reverse_relations(source, target)
        source.delete()

    def _servidor_identity_target(self, source, area):
        from cadastros.models import Servidor

        identity = Q()
        if source.cpf:
            identity |= Q(cpf=source.cpf)
        if source.rg and source.rg != "NAO POSSUI RG":
            identity |= Q(rg=source.rg)
        if source.telefone:
            identity |= Q(telefone=source.telefone)
        if not identity:
            return None
        matches = list(Servidor.objects.filter(identity, area=area).distinct()[:2])
        return matches[0] if len(matches) == 1 else None

    def _next_number(self, model, area, year, reserved) -> int:
        key = (model._meta.label, year)
        if key not in reserved:
            reserved[key] = (
                model._default_manager.filter(area=area, ano=year)
                .aggregate(value=Max("numero"))["value"]
                or 0
            )
        reserved[key] += 1
        return reserved[key]

    def _conflict_actions(self, area):
        from cadastros.models import ConfiguracaoSistema
        from cadastros.models import Servidor
        from cadastros.models import Unidade
        from oficios.models import Oficio
        from planos_trabalho.models import PlanoTrabalho

        actions = []
        # A configuração pode referenciar uma unidade legada por uma FK
        # oculta. Consolide-a primeiro; a consolidação da unidade, logo
        # depois, reaponta também a configuração de destino.
        target_config = ConfiguracaoSistema.objects.filter(area=area).first()
        if target_config is not None:
            for source in ConfiguracaoSistema.objects.filter(area__isnull=True):
                actions.append(("config", source, target_config))

        for source in Unidade.objects.filter(area__isnull=True):
            target = Unidade.objects.filter(area=area, nome=source.nome).first()
            if target is not None:
                actions.append(("merge", source, target))

        for source in Servidor.objects.filter(area__isnull=True):
            target = self._servidor_identity_target(source, area)
            if target is not None:
                actions.append(("merge", source, target))

        for model in (Oficio, PlanoTrabalho):
            for source in model.objects.filter(
                area__isnull=True,
                ano__isnull=False,
                numero__isnull=False,
            ).order_by("ano", "numero", model._meta.pk.name):
                if model.objects.filter(
                    area=area,
                    ano=source.ano,
                    numero=source.numero,
                ).exists():
                    actions.append(("renumber", source, None))
        return actions

    def _resolve_conflicts(self, area, *, commit: bool) -> None:
        actions = self._conflict_actions(area)
        reserved = {}
        for action, source, target in actions:
            if action == "merge":
                self.stdout.write(
                    f"CONSOLIDAR {source._meta.label} id={source.pk} -> id={target.pk}",
                )
                if commit:
                    self._merge_reverse_relations(source, target)
                    source.delete()
            elif action == "config":
                self.stdout.write(
                    f"CONSOLIDAR {source._meta.label} id={source.pk} -> id={target.pk}",
                )
                if commit:
                    self._merge_configuracao(source, target)
            elif action == "renumber":
                number = self._next_number(
                    source.__class__,
                    area,
                    source.ano,
                    reserved,
                )
                self.stdout.write(
                    f"RENUMERAR {source._meta.label} id={source.pk}: "
                    f"{source.numero}/{source.ano} -> {number}/{source.ano}",
                )
                if commit:
                    source.__class__._default_manager.filter(pk=source.pk).update(
                        numero=number,
                    )

        # Conflitos restantes causados apenas por dois itens marcados como
        # padrão são resolvidos preservando o legado como item não padrão.
        for label in (
            "cadastros.Cargo",
            "cadastros.Combustivel",
            "oficios.ModeloMotivoOficio",
        ):
            model = apps.get_model(label)
            if not model._default_manager.filter(area=area, is_padrao=True).exists():
                continue
            for source in model._default_manager.filter(
                area__isnull=True,
                is_padrao=True,
            ):
                self.stdout.write(
                    f"DESMARCAR PADRÃO {label} id={source.pk}",
                )
                if commit:
                    model._default_manager.filter(pk=source.pk).update(
                        is_padrao=False,
                    )

    def handle(self, *args, **options):
        try:
            area = AreaTrabalho.objects.get(
                sigla=options["area"].strip().upper(),
                ativa=True,
            )
        except AreaTrabalho.DoesNotExist as exc:
            raise CommandError("Área ativa não encontrada.") from exc

        if options["resolve_conflicts"]:
            with transaction.atomic():
                # A trava serializa saneamentos concorrentes da mesma área.
                area = AreaTrabalho.objects.select_for_update().get(pk=area.pk)
                self._resolve_conflicts(area, commit=options["commit"])

        planned = []
        skipped = []
        for model in apps.get_models():
            field = next(
                (field for field in model._meta.concrete_fields if field.name == "area"),
                None,
            )
            # Só `field is None`, nunca `not field.null`: com o NOT NULL do
            # `DB-02` no modelo, o critério de nulidade em memória pularia
            # exatamente os modelos operacionais que este comando existe para
            # sanear — ele roda com o código novo sobre o banco PRÉ-migração,
            # onde o órfão ainda existe. Num banco já migrado a consulta
            # `area__isnull=True` volta vazia e o modelo é pulado adiante.
            if field is None:
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
                    try:
                        with transaction.atomic():
                            # QuerySet.update também permite sanear modelos
                            # append-only, como AuditEvent, sem violar a
                            # imutabilidade de conteúdo definida em save().
                            model._default_manager.filter(pk=instance.pk).update(
                                area=area,
                            )
                    except (IntegrityError, ValidationError):
                        self.stdout.write(
                            self.style.WARNING(
                                f"{model._meta.label}: id={instance.pk} ignorado por conflito.",
                            ),
                        )
        self.stdout.write(self.style.SUCCESS("Backfill de áreas concluído."))
