"""Relata conflitos que impedem o backfill de ``area=NULL``.

Uso:
    python scripts/inspect_area_conflicts.py DPC

O script é somente leitura. Ele compara cada registro legado conflitante com
o registro já existente na área e lista relações reversas que precisariam ser
reapontadas antes de uma eventual consolidação.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django

django.setup()

from cadastros.models import Cargo
from cadastros.models import Combustivel
from cadastros.models import ConfiguracaoSistema
from cadastros.models import Servidor
from cadastros.models import Unidade
from oficios.models import ModeloMotivoOficio
from oficios.models import Oficio
from planos_trabalho.models import PlanoTrabalho
from usuarios.models import AreaTrabalho


IGNORED_FIELDS = {
    "area",
    "created_at",
    "updated_at",
    "criado_em",
    "atualizado_em",
}


def _field_differences(old, new):
    differences = []
    for field in old._meta.concrete_fields:
        if field.primary_key or field.name in IGNORED_FIELDS:
            continue
        old_value = getattr(old, field.attname)
        new_value = getattr(new, field.attname)
        if old_value != new_value:
            differences.append((field.name, repr(old_value), repr(new_value)))
    return differences


def _reverse_references(instance):
    references = []
    for relation in instance._meta.related_objects:
        accessor = relation.get_accessor_name()
        try:
            related = getattr(instance, accessor)
            count = related.count() if relation.one_to_many or relation.many_to_many else 1
        except relation.related_model.DoesNotExist:
            count = 0
        if count:
            references.append(
                (relation.related_model._meta.label, relation.field.name, count),
            )
    return references


def _pairs(area):
    for model in (Unidade, Cargo, Combustivel, Servidor, ModeloMotivoOficio):
        for old in model.objects.filter(area__isnull=True):
            yield old, model.objects.filter(area=area, nome=old.nome).first()
    for old in ConfiguracaoSistema.objects.filter(area__isnull=True):
        yield old, ConfiguracaoSistema.objects.filter(area=area).first()
    for old in Oficio.objects.filter(area__isnull=True):
        yield old, Oficio.objects.filter(
            area=area,
            ano=old.ano,
            numero=old.numero,
        ).first()
    for old in PlanoTrabalho.objects.filter(area__isnull=True):
        yield old, PlanoTrabalho.objects.filter(
            area=area,
            ano=old.ano,
            numero=old.numero,
        ).first()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Informe a sigla da área: python scripts/inspect_area_conflicts.py DPC")
    area = AreaTrabalho.objects.get(sigla=sys.argv[1].strip().upper(), ativa=True)
    for old, new in _pairs(area):
        print(f"\n{old._meta.label} {old.pk} -> {getattr(new, 'pk', None)}")
        if new is None:
            print("  sem conflito correspondente")
            continue
        differences = _field_differences(old, new)
        references = _reverse_references(old)
        print(f"  diferenças: {differences or 'nenhuma'}")
        print(f"  referências: {references or 'nenhuma'}")


if __name__ == "__main__":
    main()
