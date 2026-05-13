from django.apps import AppConfig


class OficiosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "oficios"
    verbose_name = "Oficios"

    def ready(self):
        # Registra checagens de URLconf do wizard (oficios/checks.py).
        from . import checks  # noqa: F401
