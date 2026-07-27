from django.db import migrations

import core.db_fields


def reencrypt_tokens(apps, schema_editor):
    DriveCredenciais = apps.get_model("google_drive", "DriveCredenciais")
    for credencial in DriveCredenciais.objects.all().iterator():
        credencial.save(update_fields=["access_token", "refresh_token"])


class Migration(migrations.Migration):
    dependencies = [
        ("google_drive", "0010_drivereorganizacaojob_area_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="drivecredenciais",
            name="access_token",
            field=core.db_fields.EncryptedTextField(),
        ),
        migrations.AlterField(
            model_name="drivecredenciais",
            name="refresh_token",
            field=core.db_fields.EncryptedTextField(),
        ),
        migrations.RunPython(reencrypt_tokens, migrations.RunPython.noop),
    ]
