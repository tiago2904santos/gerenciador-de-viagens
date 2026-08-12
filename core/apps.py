from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _register_sqlite_unaccent(sender, connection, **kwargs):
    """Espelha a extensão Postgres `unaccent` no SQLite (usado nos testes).

    Sem isso, os lookups `__unaccent__icontains` usados nas barras de busca
    quebrariam a suíte de testes, que roda em SQLite in-memory.
    """
    if connection.vendor != "sqlite":
        return
    from .normalizers import remove_accents

    connection.connection.create_function("UNACCENT", 1, remove_accents)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core"

    def ready(self):
        connection_created.connect(_register_sqlite_unaccent)
        from . import checks  # noqa: F401
        from .audit import connect_audit_signals
        from .observability import initialize_error_tracking
        from .tenancy import connect_area_integrity_signals

        initialize_error_tracking()
        connect_audit_signals()
        connect_area_integrity_signals()
