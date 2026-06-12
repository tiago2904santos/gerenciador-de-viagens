import django.utils.timezone
from django.db import migrations
from django.db import models


HORARIOS = [
    ("09:00 até 17:00", 10),
    ("08:00 até 16:00", 20),
    ("10:00 até 18:00", 30),
]


def seed_horarios(apps, schema_editor):
    HorarioAtendimento = apps.get_model("planos_trabalho", "HorarioAtendimento")
    for faixa, ordem in HORARIOS:
        HorarioAtendimento.objects.get_or_create(faixa=faixa, defaults={"ordem": ordem, "ativo": True})


def unseed_horarios(apps, schema_editor):
    HorarioAtendimento = apps.get_model("planos_trabalho", "HorarioAtendimento")
    HorarioAtendimento.objects.filter(faixa__in=[faixa for faixa, _ in HORARIOS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("planos_trabalho", "0002_seed_programas_solicitantes"),
    ]

    operations = [
        migrations.CreateModel(
            name="HorarioAtendimento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("faixa", models.CharField(max_length=60, unique=True)),
                ("ativo", models.BooleanField(default=True)),
                ("ordem", models.PositiveIntegerField(default=100)),
            ],
            options={
                "verbose_name": "Horário de atendimento",
                "verbose_name_plural": "Horários de atendimento",
                "ordering": ["ordem", "faixa"],
            },
        ),
        migrations.RunPython(seed_horarios, unseed_horarios),
    ]
