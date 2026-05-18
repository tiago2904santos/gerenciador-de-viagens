from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("oficios", "0005_oficio_motorista_oficio_protocolo_ref"),
    ]

    operations = [
        migrations.AddField(
            model_name="oficio",
            name="retificado_documento",
            field=models.BooleanField(
                default=False,
                help_text="Quando verdadeiro e o ofício seria Autorização por datas, o documento usa o rótulo Retificado.",
                verbose_name="Emitir como retificado",
            ),
        ),
    ]
