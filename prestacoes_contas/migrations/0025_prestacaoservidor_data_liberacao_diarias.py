from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prestacoes_contas", "0024_prestacaoservidor_prazo_limite_saque"),
    ]

    operations = [
        migrations.AddField(
            model_name="prestacaoservidor",
            name="data_liberacao_diarias",
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name="Data de liberação das diárias",
            ),
        ),
    ]
