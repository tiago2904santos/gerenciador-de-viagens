from django.db import migrations
from django.db import models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("ordens_servico", "0008_ordemservico_funcoes_servidores"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="ordemservico",
            constraint=models.UniqueConstraint(
                fields=("area", "ano", "numero"),
                condition=Q(ano__isnull=False, numero__isnull=False),
                name="ordens_servico_area_ano_numero_unique",
            ),
        ),
    ]
