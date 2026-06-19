from django.apps import AppConfig


class PrestacoesContasConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prestacoes_contas"
    verbose_name = "Prestações de Contas"

    def ready(self):
        from .signals import connect_signals
        connect_signals()
