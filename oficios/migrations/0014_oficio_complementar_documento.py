from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("oficios", "0013_oficionumerolacuna"),
    ]

    operations = [
        migrations.AddField(
            model_name="oficio",
            name="complementar_documento",
            field=models.BooleanField(
                default=False,
                help_text="Quando verdadeiro, o documento usa o rótulo Complementar ao lado do número do ofício.",
                verbose_name="Emitir como complementar",
            ),
        ),
    ]
