import django.conf
import django.db.models.deletion
from django.db import migrations
from django.db import models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_unaccent_extension"),
        ("usuarios", "0001_initial"),
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=12)),
                ("model_label", models.CharField(db_index=True, max_length=120)),
                ("object_id", models.CharField(db_index=True, max_length=120)),
                ("object_repr", models.CharField(blank=True, default="", max_length=255)),
                ("changes", models.JSONField(default=dict)),
                ("request_path", models.CharField(blank=True, default="", max_length=500)),
                ("request_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="domain_audit_events",
                        to=django.conf.settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "area",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to="usuarios.areatrabalho",
                    ),
                ),
            ],
            options={"ordering": ["-created_at", "-pk"]},
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=["model_label", "object_id", "-created_at"],
                name="core_audit_object_idx",
            ),
        ),
    ]
