import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("documentos", "0010_documento_assinatura_versionada"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentoGeracao",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("tipo", models.CharField(max_length=64)),
                ("parametros", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Na fila"),
                            ("processing", "Processando"),
                            ("complete", "Concluído"),
                            ("error", "Erro"),
                        ],
                        db_index=True,
                        default="queued",
                        max_length=16,
                    ),
                ),
                ("dedupe_key", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("disposicao", models.CharField(default="attachment", max_length=16)),
                ("nome_arquivo", models.CharField(blank=True, default="", max_length=255)),
                ("content_type", models.CharField(blank=True, default="", max_length=128)),
                ("hash_sha256", models.CharField(blank=True, default="", max_length=64)),
                ("arquivo", models.FileField(blank=True, upload_to="documentos/jobs/%Y/%m/")),
                ("erro", models.CharField(blank=True, default="", max_length=500)),
                ("criado_em", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("iniciado_em", models.DateTimeField(blank=True, null=True)),
                ("concluido_em", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "area",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documentos_geracoes",
                        to="usuarios.areatrabalho",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="documentos_geracoes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Geração documental",
                "verbose_name_plural": "Gerações documentais",
                "ordering": ["-criado_em"],
            },
        ),
    ]
