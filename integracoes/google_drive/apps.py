from django.apps import AppConfig


class GoogleDriveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integracoes.google_drive"
    verbose_name = "Integração Google Drive"

    def ready(self) -> None:
        from integracoes.google_drive.signals import conectar

        conectar()
