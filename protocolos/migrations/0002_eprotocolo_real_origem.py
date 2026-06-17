from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("protocolos", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="protocolo",
            name="origem_tipo",
            field=models.CharField(
                choices=[
                    ("interna", "Documento interno"),
                    ("manual", "Externo / manual"),
                    ("eprotocolo_real", "eProtocolo real"),
                ],
                default="interna",
                max_length=20,
            ),
        ),
    ]
