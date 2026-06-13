from django.db import migrations
from django.db import models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0013_remove_assinatura_fields"),
        ("planos_trabalho", "0004_planodestino"),
    ]

    operations = [
        migrations.AddField(
            model_name="efetivoplano",
            name="unidade",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="efetivos_plano_trabalho",
                to="cadastros.unidade",
                verbose_name="Unidade",
            ),
        ),
        migrations.AlterModelOptions(
            name="efetivoplano",
            options={
                "ordering": ["plano", "unidade__nome", "cargo__nome"],
                "verbose_name": "Efetivo do plano de trabalho",
                "verbose_name_plural": "Efetivos do plano de trabalho",
            },
        ),
        migrations.RemoveConstraint(
            model_name="efetivoplano",
            name="planos_trabalho_efetivo_plano_cargo_unique",
        ),
        migrations.AddConstraint(
            model_name="efetivoplano",
            constraint=models.UniqueConstraint(
                fields=("plano", "unidade", "cargo"),
                name="planos_trabalho_efetivo_plano_unidade_cargo_unique",
            ),
        ),
    ]
