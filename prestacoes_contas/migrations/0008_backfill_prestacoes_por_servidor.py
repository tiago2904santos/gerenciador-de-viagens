from django.db import migrations


def criar_prestacoes_faltantes(apps, schema_editor):
    Oficio = apps.get_model("oficios", "Oficio")
    PrestacaoContas = apps.get_model("prestacoes_contas", "PrestacaoContas")

    for oficio in Oficio.objects.all().prefetch_related("servidores"):
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
