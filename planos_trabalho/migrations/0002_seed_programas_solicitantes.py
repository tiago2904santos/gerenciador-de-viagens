from django.db import migrations

PROGRAMAS = [
    ("PROGRAMA PARANÁ EM AÇÃO", 10),
    ("PROGRAMA JUSTIÇA NO BAIRRO", 20),
    ("PCPR NA COMUNIDADE", 30),
]


def seed_programas(apps, schema_editor):
    ProgramaSolicitante = apps.get_model("planos_trabalho", "ProgramaSolicitante")
    for nome, ordem in PROGRAMAS:
        ProgramaSolicitante.objects.get_or_create(nome=nome, defaults={"ordem": ordem, "ativo": True})


def unseed_programas(apps, schema_editor):
    ProgramaSolicitante = apps.get_model("planos_trabalho", "ProgramaSolicitante")
    ProgramaSolicitante.objects.filter(nome__in=[nome for nome, _ in PROGRAMAS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("planos_trabalho", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_programas, unseed_programas),
    ]
