import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("cadastros", "0013_remove_assinatura_fields"),
        ("oficios", "0007_oficio_servidores_termo_autorizacao"),
    ]

    operations = [
        migrations.CreateModel(
            name="TermoAutorizacao",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("data_evento_inicio", models.DateField(blank=True, null=True, verbose_name="Data inicial do evento")),
                ("data_evento_fim", models.DateField(blank=True, null=True, verbose_name="Data final do evento")),
                (
                    "destino_cidade",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="termos_autorizacao",
                        to="cadastros.cidade",
                        verbose_name="Cidade do destino",
                    ),
                ),
                (
                    "destino_estado",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="cadastros.estado",
                        verbose_name="UF do destino",
                    ),
                ),
                (
                    "oficio",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="termos_autorizacao",
                        to="oficios.oficio",
                        verbose_name="Oficio vinculado",
                    ),
                ),
                (
                    "viatura",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="termos_autorizacao",
                        to="cadastros.viatura",
                        verbose_name="Viatura",
                    ),
                ),
                (
                    "servidores",
                    models.ManyToManyField(
                        blank=True,
                        related_name="termos_autorizacao",
                        to="cadastros.servidor",
                        verbose_name="Servidores",
                    ),
                ),
            ],
            options={
                "verbose_name": "Termo de autorizacao",
                "verbose_name_plural": "Termos de autorizacao",
                "ordering": ["-created_at"],
            },
        ),
    ]
