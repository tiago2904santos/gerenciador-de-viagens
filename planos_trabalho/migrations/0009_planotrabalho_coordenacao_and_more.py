from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("planos_trabalho", "0008_seed_atividades_plano_trabalho"),
    ]

    operations = [
        migrations.AddField(
            model_name="planotrabalho",
            name="coordenacao",
            field=models.TextField(blank=True, default="", verbose_name="Coordenador do evento"),
        ),
        migrations.AddField(
            model_name="planotrabalho",
            name="coordenacao_auto",
            field=models.BooleanField(default=True),
        ),
    ]
