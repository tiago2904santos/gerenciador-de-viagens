"""DB-13: composicao consultavel sem reinterpretar dinheiro historico.

Validacao obrigatoria antes do deploy (somente leitura):

    SELECT COUNT(*) AS roteiros_com_resumo,
           COUNT(*) FILTER (WHERE quantidade_diarias ~* '\\d+\\s*x\\s*(15|30|100)\\s*%')
             AS resumos_estruturaveis
      FROM roteiros_roteiro
     WHERE quantidade_diarias <> '';

Backup: incluir ``roteiros_roteiro`` no backup logico normal; para um recorte
dedicado, ``pg_dump --table=roteiros_roteiro --data-only <banco> > db13.sql``.
O backfill extrai apenas quantidade e percentual de resumos inequivocos. Nao
atribui tabela, faixa, valor ou subtotal e nunca recalcula o total persistido.
"""

import re

import django.db.models.deletion
from django.db import migrations, models


COMPONENTE_RE = re.compile(r"(\d+)\s*x\s*(100|15|30)\s*%", re.IGNORECASE)


def estruturar_resumos_legados(apps, schema_editor):
    Roteiro = apps.get_model("roteiros", "Roteiro")
    Componente = apps.get_model("roteiros", "RoteiroDiariaComponente")
    buffer = []
    for roteiro_id, resumo in (
        Roteiro.all_objects.exclude(quantidade_diarias="")
        .values_list("pk", "quantidade_diarias")
        .iterator(chunk_size=1000)
    ):
        for ordem, match in enumerate(COMPONENTE_RE.finditer(resumo or "")):
            quantidade = int(match.group(1))
            if quantidade <= 0:
                continue
            buffer.append(
                Componente(
                    roteiro_id=roteiro_id,
                    ordem=ordem,
                    origem="LEGADO",
                    percentual=int(match.group(2)),
                    quantidade=quantidade,
                )
            )
        if len(buffer) >= 1000:
            Componente.objects.bulk_create(buffer)
            buffer.clear()
    if buffer:
        Componente.objects.bulk_create(buffer)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('cadastros', '0028_tabela_diaria_derivados_positivos'),
        ('roteiros', '0015_db09_indice_da_ordenacao_da_lista'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoteiroDiariaComponente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveIntegerField(default=0)),
                ('origem', models.CharField(choices=[('CALCULO', 'Calculo estruturado'), ('LEGADO', 'Resumo legado')], max_length=12)),
                ('faixa', models.CharField(blank=True, choices=[('INTERIOR', 'Interior'), ('CAPITAL', 'Capital'), ('BRASILIA', 'Brasilia')], default='', max_length=20)),
                ('percentual', models.PositiveSmallIntegerField(choices=[(15, '15%'), (30, '30%'), (100, '100%')])),
                ('quantidade', models.PositiveIntegerField()),
                ('valor_unitario', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('subtotal', models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ('tabela_vigencia_inicio', models.DateField(blank=True, null=True)),
                ('periodo_inicio', models.DateTimeField(blank=True, null=True)),
                ('periodo_fim', models.DateTimeField(blank=True, null=True)),
                ('roteiro', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='componentes_diarias', to='roteiros.roteiro')),
                ('tabela_diaria', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to='cadastros.tabeladiaria')),
            ],
            options={
                'ordering': ['ordem'],
                'indexes': [models.Index(fields=['percentual', 'periodo_inicio'], name='roteiro_diaria_pct_periodo_idx')],
                'constraints': [models.UniqueConstraint(fields=('roteiro', 'ordem'), name='uniq_roteiro_diaria_componente_ordem'), models.CheckConstraint(condition=models.Q(('quantidade__gt', 0)), name='roteiro_diaria_componente_qtd_positiva'), models.CheckConstraint(condition=models.Q(('percentual__in', (15, 30, 100))), name='roteiro_diaria_componente_pct_valido'), models.CheckConstraint(condition=models.Q(('valor_unitario__gte', 0)), name='roteiro_diaria_componente_unit_nao_negativo'), models.CheckConstraint(condition=models.Q(('subtotal__gte', 0)), name='roteiro_diaria_componente_subtotal_nao_negativo'), models.CheckConstraint(condition=models.Q(('periodo_fim__gte', models.F('periodo_inicio'))), name='roteiro_diaria_componente_periodo_ordenado')],
            },
        ),
        migrations.RunPython(estruturar_resumos_legados, noop),
    ]
