from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("oficios", "0009_oficiosolicitacaoanexo"),
    ]

    operations = [
        migrations.DeleteModel(
            name="OficioSolicitacaoAnexo",
        ),
    ]
