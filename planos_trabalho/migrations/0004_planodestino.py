import django.db.models.deletion
import django.utils.timezone
from django.db import migrations
from django.db import models


def seed_destinos_from_primary_fields(apps, schema_editor):
    PlanoTrabalho = apps.get_model("planos_trabalho", "PlanoTrabalho")
    PlanoDestino = apps.get_model("planos_trabalho", "PlanoDestino")
    for plano in PlanoTrabalho.objects.exclude(destino_cidade_id__isnull=True):
        if PlanoDestino.objects.filter(plano_id=plano.pk).exists():
            continue
        PlanoDestino.objects.create(
            plano_id=plano.pk,
            estado_id=plano.destino_estado_id,
            cidade_id=plano.destino_cidade_id,
            ordem=1,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0015_configuracaosistema_pt_sufixo_numero"),
        ("planos_trabalho", "0003_horarioatendimento_and_seed"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlanoDestino",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ordem", models.PositiveIntegerField(default=1)),
                ("cidade", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="planos_trabalho_destinos", to="cadastros.cidade", verbose_name="Cidade do destino")),
                ("estado", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="+", to="cadastros.estado", verbose_name="UF do destino")),
                ("plano", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="destinos", to="planos_trabalho.planotrabalho", verbose_name="Plano de trabalho")),
            ],
            options={
                "verbose_name": "Destino do plano de trabalho",
                "verbose_name_plural": "Destinos do plano de trabalho",
                "ordering": ["ordem", "pk"],
            },
        ),
        migrations.RunPython(seed_destinos_from_primary_fields, migrations.RunPython.noop),
    ]
