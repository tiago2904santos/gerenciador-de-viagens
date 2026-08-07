"""`DB-02` grupo 2 — `TipoEvento` passa a ter dono, um por área.

As 5 linhas nascem sem área, criadas pelo seed de `0008`. Mesma medição do irmão
em `planos_trabalho/0023`: toda leitura passa por `filter_queryset_by_area`, que é
estrito (`eventos/selectors.py:189,196`, `eventos/forms.py:241`), e as 5 linhas são
vistas por **zero** usuários com área nas três áreas do banco de desenvolvimento.
Linha nova já nasce com área (`core/catalog.py:187-188`).

Decisão do usuário em 07/08/2026 (§8 do plano mestre): duplicar por área, seguindo
o `NOVO-09`.
"""

from django.db import migrations

#: **`_base_manager`, nunca `objects`.** Modelo histórico de migração não recebe o
#: manager customizado: com `default_manager_name` definido (o `AreaScopedManager`
#: do `BE-09`), `objects` simplesmente não existe ali. E o erro só aparece na
#: **volta**, porque a ida sai cedo quando não há área — foi assim que ele apareceu,
#: drilando o rollback num banco de teste.


def _liberar_gatilhos_pendentes(schema_editor):
    """Ver `planos_trabalho/0023`: sem isto a **volta** morre no PostgreSQL."""
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def duplicar_por_area(apps, schema_editor):
    """Uma cópia em cada área; a original fica com a primeira, não sobra global."""
    TipoEvento = apps.get_model("eventos", "TipoEvento")
    AreaTrabalho = apps.get_model("usuarios", "AreaTrabalho")

    areas = list(AreaTrabalho._base_manager.order_by("pk"))
    if not areas:
        return

    globais = list(TipoEvento._base_manager.filter(area__isnull=True).order_by("pk"))
    if not globais:
        return

    primeira, demais = areas[0], areas[1:]

    if demais:
        TipoEvento._base_manager.bulk_create(
            [
                TipoEvento(
                    area=area,
                    nome=tipo.nome,
                    ativo=tipo.ativo,
                    ordem=tipo.ordem,
                    created_at=tipo.created_at,
                    updated_at=tipo.updated_at,
                )
                for area in demais
                for tipo in globais
            ]
        )
    TipoEvento._base_manager.filter(pk__in=[t.pk for t in globais]).update(area=primeira)

    _liberar_gatilhos_pendentes(schema_editor)


def devolver_ao_global(apps, schema_editor):
    """Volta: uma linha por nome, sem área; as demais cópias saem."""
    TipoEvento = apps.get_model("eventos", "TipoEvento")
    if not apps.get_model("usuarios", "AreaTrabalho")._base_manager.exists():
        return

    vistos = set()
    for tipo in TipoEvento._base_manager.filter(area__isnull=False).order_by("pk"):
        if tipo.nome in vistos:
            tipo.delete()
        else:
            vistos.add(tipo.nome)
            TipoEvento._base_manager.filter(pk=tipo.pk).update(area=None)

    _liberar_gatilhos_pendentes(schema_editor)


class Migration(migrations.Migration):
    dependencies = [
        # O `#253` (`DB-02` grupo 1, sessão paralela) levou `0015_area_obrigatoria`
        # para a `main` depois deste ramo. `TipoEvento` não está entre os oito
        # modelos operacionais daquela migração, então as duas são independentes;
        # esta só encadeia depois.
        ("eventos", "0015_area_obrigatoria"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(duplicar_por_area, devolver_ao_global),
    ]
