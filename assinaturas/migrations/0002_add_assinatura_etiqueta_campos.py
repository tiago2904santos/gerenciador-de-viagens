# Generated manually for etiqueta de assinatura (CV 3.0)

import secrets

from django.db import migrations, models
from django.utils import timezone


def _preencher_codigos_verificacao(apps, schema_editor):
    AssinaturaDigital = apps.get_model("assinaturas", "AssinaturaDigital")
    ano = timezone.now().year
    for row in AssinaturaDigital.objects.filter(codigo_verificacao__isnull=True):
        while True:
            codigo = f"CV-{ano}-{secrets.token_hex(3).upper()}-{secrets.token_hex(2).upper()}"
            if not AssinaturaDigital.objects.filter(codigo_verificacao=codigo).exists():
                row.codigo_verificacao = codigo
                row.save(update_fields=["codigo_verificacao"])
                break


class Migration(migrations.Migration):

    dependencies = [
        ("assinaturas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="assinaturadigital",
            name="codigo_verificacao",
            field=models.CharField(db_index=True, max_length=32, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="nome_assinante",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="cpf_assinante",
            field=models.CharField(blank=True, default="", max_length=14),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="email_assinante",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="metodo_autenticacao",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="ip_assinatura",
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="user_agent",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="posicao_carimbo_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="pagina_carimbo",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="assinaturadigital",
            name="url_validacao",
            field=models.URLField(blank=True, default="", max_length=600),
        ),
        migrations.RunPython(_preencher_codigos_verificacao, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="assinaturadigital",
            name="codigo_verificacao",
            field=models.CharField(db_index=True, max_length=32, unique=True),
        ),
    ]
