from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("prestacoes_contas", "0005_alter_modelotextorelatoriotecnico_campo"),
    ]

    operations = [
        migrations.AddField(
            model_name="relatoriotecnico",
            name="combustivel",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
