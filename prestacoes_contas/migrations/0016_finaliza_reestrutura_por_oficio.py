# Parte destrutiva da reestruturação "uma prestação por ofício".
#
# Roda em migração separada da 0015 (que fez a migração de dados) porque o
# Postgres recusa ALTER TABLE na mesma transação de um RunPython que alterou
# linhas da tabela ("pending trigger events").

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('oficios', '0013_oficionumerolacuna'),
        ('prestacoes_contas', '0015_reestrutura_por_oficio'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='prestacaocontas',
            name='unique_prestacao_por_servidor_oficio',
        ),
        migrations.RemoveField(
            model_name='prestacaocontas',
            name='comprovante_saque_transferencia',
        ),
        migrations.RemoveField(
            model_name='prestacaocontas',
            name='numero_solicitacao',
        ),
        migrations.RemoveField(
            model_name='prestacaocontas',
            name='servidor',
        ),
        migrations.AlterField(
            model_name='prestacaocontas',
            name='oficio',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='prestacao_contas', to='oficios.oficio'),
        ),
        migrations.AddConstraint(
            model_name='assinaturadocumento',
            constraint=models.UniqueConstraint(condition=models.Q(('servidor_prestacao__isnull', True)), fields=('prestacao', 'tipo'), name='uniq_assinatura_prestacao_tipo'),
        ),
        migrations.AddConstraint(
            model_name='assinaturadocumento',
            constraint=models.UniqueConstraint(condition=models.Q(('servidor_prestacao__isnull', False)), fields=('servidor_prestacao', 'tipo'), name='uniq_assinatura_servidor_tipo'),
        ),
    ]
