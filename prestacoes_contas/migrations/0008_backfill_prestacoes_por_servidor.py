from django.db import migrations


def criar_prestacoes_faltantes(apps, schema_editor):
    Oficio = apps.get_model("oficios", "Oficio")
    PrestacaoContas = apps.get_model("prestacoes_contas", "PrestacaoContas")

    # `BE-09`: `all_objects`, e não `objects`. O modelo histórico de migração só
    # conserva managers que sejam `_default_manager`, `_base_manager` ou
    # `use_in_migrations` (`db/migrations/state.py:905`). Como `objects` virou o
    # manager que recorta por área — e nenhum dos três —, ele deixa de existir
    # aqui. `all_objects` é o `_default_manager`, então sobrevive como `Manager`
    # puro: mesmo comportamento que `objects` tinha antes desta migração ser
    # escrita.
    for oficio in Oficio.all_objects.all().prefetch_related("servidores"):
        for servidor in oficio.servidores.all():
            PrestacaoContas.objects.get_or_create(
                oficio_id=oficio.pk,
                servidor_id=servidor.pk,
                defaults={"status": "pendente"},
            )


class Migration(migrations.Migration):
    dependencies = [
        ("prestacoes_contas", "0007_alter_modelotextorelatoriotecnico_campo"),
    ]

    operations = [
        migrations.RunPython(criar_prestacoes_faltantes, migrations.RunPython.noop),
    ]
