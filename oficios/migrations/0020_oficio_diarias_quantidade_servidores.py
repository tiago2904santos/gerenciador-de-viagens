from django.db import migrations, models
from django.db.models import Count


def congelar_efetivo_atual(apps, schema_editor):
    Oficio = apps.get_model("oficios", "Oficio")
    for oficio in Oficio.all_objects.annotate(
        total_servidores=Count("servidores"),
    ).iterator():
        Oficio.all_objects.filter(pk=oficio.pk).update(
            diarias_quantidade_servidores=max(oficio.total_servidores, 1),
        )


def liberar_snapshot(apps, schema_editor):
    Oficio = apps.get_model("oficios", "Oficio")
    Oficio.all_objects.update(diarias_quantidade_servidores=None)


class Migration(migrations.Migration):
    dependencies = [
        ("oficios", "0019_area_obrigatoria"),
    ]

    operations = [
        migrations.AddField(
            model_name="oficio",
            name="diarias_quantidade_servidores",
            field=models.PositiveIntegerField(
                blank=True,
                editable=False,
                help_text=(
                    "Snapshot do efetivo usado no total de diárias; não muda quando "
                    "um servidor é excluído posteriormente do cadastro."
                ),
                null=True,
                verbose_name="Quantidade de servidores considerada nas diárias",
            ),
        ),
        migrations.RunPython(congelar_efetivo_atual, liberar_snapshot),
    ]
