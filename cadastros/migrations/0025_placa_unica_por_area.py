"""`DB-05`: a placa de viatura passa a ser única por área, não pelo sistema.

**Validação dos dados antes de migrar** (`AGENTS.md`, limite 4), rodada contra
PostgreSQL:

    viaturas ................................. 1
    com area NULL ............................ 0
    placas repetidas DENTRO da mesma area .... []
    placas repetidas entre as globais ........ []

E o resultado não depende do banco em que se rode: a constraint nova é
**estritamente mais permissiva** que a que sai. Hoje `placa` é `unique` global,
então duas linhas com a mesma placa não existem — nem dentro de uma área, nem
entre as globais. Nenhum dado existente pode violar `viatura_placa_global_unique`
nem `viatura_area_placa_unique`. Esta migração não tem como falhar por dado.

**Backup:** o `deploy.yml` roda `scripts/backup_production.sh` antes do
checkout, e o `scripts/deploy_rollback.sh` (`QA-03`) desfaz esta migração pelo
`migrate cadastros 0024` se o deploy abortar depois dela.

**A volta é segura no dia do deploy e deixa de ser depois.** Isto foi medido, não
suposto — drill contra PostgreSQL com duas áreas usando a mesma placa:

    IntegrityError: could not create unique index
      "cadastros_viatura_placa_af1b9674_uniq"
    DETAIL: Key (placa)=(DRL0A00) is duplicated.

É inerente à mudança: não dá para reapertar uma unicidade que os dados já
usaram alargada. No dia do deploy a volta funciona, porque nenhuma duplicata
existe ainda — é exatamente a janela em que o `QA-03` age. Depois que a primeira
área cadastrar uma placa que outra já tinha, a volta exige decidir **qual das
duas viaturas some**, e isso é decisão de gente, não de script.

Quem precisar reverter mais tarde: a query que lista o que impede é

    select placa, count(*) from cadastros_viatura
    group by placa having count(*) > 1;

Nenhuma reversão automática vai adivinhar qual linha apagar.

A ordem importa: o `AlterField` solta o índice único global **antes** de as
condicionais entrarem. Invertido, o Postgres recusaria a segunda por
sobreposição com a primeira.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0024_tabeladiaria"),
        ("usuarios", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="viatura",
            name="placa",
            field=models.CharField(max_length=7),
        ),
        migrations.AddConstraint(
            model_name="viatura",
            constraint=models.UniqueConstraint(
                condition=models.Q(("area__isnull", True)),
                fields=("placa",),
                name="viatura_placa_global_unique",
            ),
        ),
        migrations.AddConstraint(
            model_name="viatura",
            constraint=models.UniqueConstraint(
                condition=models.Q(("area__isnull", False)),
                fields=("area", "placa"),
                name="viatura_area_placa_unique",
            ),
        ),
    ]
