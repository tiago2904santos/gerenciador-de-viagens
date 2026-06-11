import django.db.models.deletion
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0013_remove_assinatura_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssinaturaConfiguracao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, editable=False)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('tipo', models.CharField(choices=[('OFICIO', 'Ofício'), ('JUSTIFICATIVA', 'Justificativa'), ('PLANO_TRABALHO', 'Plano de Trabalho'), ('ORDEM_SERVICO', 'Ordem de Serviço')], max_length=30)),
                ('ordem', models.PositiveSmallIntegerField(default=1)),
                ('ativo', models.BooleanField(default=True)),
                ('configuracao', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assinaturas', to='cadastros.configuracaosistema')),
                ('servidor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='cadastros.servidor', verbose_name='Servidor')),
            ],
            options={
                'verbose_name': 'Assinatura (configuração)',
                'verbose_name_plural': 'Assinaturas (configuração)',
            },
        ),
        migrations.AddConstraint(
            model_name='assinaturaconfiguracao',
            constraint=models.UniqueConstraint(fields=('configuracao', 'tipo', 'ordem'), name='uniq_assinatura_cfg_tipo_ordem_v2'),
        ),
    ]
