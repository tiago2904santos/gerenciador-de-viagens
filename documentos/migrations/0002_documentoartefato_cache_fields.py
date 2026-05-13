from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documentos", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="documentoartefato",
            name="cache_key",
            field=models.CharField(blank=True, db_index=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="documentoartefato",
            name="generator_version",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
        migrations.AddField(
            model_name="documentoartefato",
            name="engine",
            field=models.CharField(blank=True, default="", max_length=32),
        ),
    ]
