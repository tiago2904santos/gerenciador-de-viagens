from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prestacoes_contas", "0019_diariobordo_viatura_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="prestacaocontas",
            name="arquivada",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="prestacaocontas",
            name="arquivada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="prestacaocontas",
            name="finalizada",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="prestacaocontas",
            name="finalizada_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
