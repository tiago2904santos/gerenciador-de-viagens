import hashlib

from django.db import migrations
from django.db import models

import core.db_fields


def proteger_tokens(apps, schema_editor):
    AssinaturaDocumento = apps.get_model("prestacoes_contas", "AssinaturaDocumento")
    for documento in AssinaturaDocumento.objects.exclude(link_token="").iterator():
        documento.link_token_hash = hashlib.sha256(
            documento.link_token.encode("utf-8"),
        ).hexdigest()
        documento.save(update_fields=["link_token", "link_token_hash"])


class Migration(migrations.Migration):
    dependencies = [
        ("prestacoes_contas", "0026_prestacaoservidor_estado_individual"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assinaturadocumento",
            name="link_token",
            field=core.db_fields.EncryptedTextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="assinaturadocumento",
            name="link_token_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.RunPython(proteger_tokens, migrations.RunPython.noop),
    ]
