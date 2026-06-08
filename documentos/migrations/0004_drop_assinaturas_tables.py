"""
Remove tabelas do app 'assinaturas' (app removido do projeto).
A assinatura digital passou a ser feita diretamente no e-protocolo.
"""

from django.db import migrations


_ASSINATURAS_TABLES = [
    "assinaturas_eventoassinatura",
    "assinaturas_pedidoassinaturadocumento",
    "assinaturas_assinaturadigital",
    "assinaturas_configuracaochaveassinatura",
]

_DROP_SQL = "\n".join(f"DROP TABLE IF EXISTS {t};" for t in _ASSINATURAS_TABLES)
_CLEAN_MIGRATIONS_SQL = "DELETE FROM django_migrations WHERE app = 'assinaturas';"


class Migration(migrations.Migration):
    dependencies = [
        ("documentos", "0003_remove_assinatura_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql=_DROP_SQL + "\n" + _CLEAN_MIGRATIONS_SQL,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
