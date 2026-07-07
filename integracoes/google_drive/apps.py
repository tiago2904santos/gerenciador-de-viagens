from django.apps import AppConfig


class GoogleDriveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integracoes.google_drive"
    verbose_name = "Integração Google Drive"

    def ready(self) -> None:
        from integracoes.google_drive.signals import conectar
        conectar()
        self._marcar_jobs_orfaos()

    def _marcar_jobs_orfaos(self) -> None:
        """Jobs de reorganização "em andamento" não sobrevivem a um restart do
        processo (rodam numa thread daemon do próprio worker) — se o processo
        caiu ou reiniciou (deploy) no meio de um, a linha fica presa em
        "em_andamento" pra sempre. Isso mantém o spinner da tela de
        Configurações perguntando ao servidor a cada 3s sem nunca parar
        (``initStatusMassa`` em gdrive_config.js só para de repetir quando o
        job deixa de estar "em_andamento"). Ao subir o processo, qualquer job
        "em_andamento" encontrado já é garantidamente órfão.
        """
        import sys

        if any(cmd in sys.argv for cmd in ("migrate", "makemigrations", "test")):
            return
        try:
            from django.db import connection
            from integracoes.google_drive.models import DriveReorganizacaoJob

            if DriveReorganizacaoJob._meta.db_table not in connection.introspection.table_names():
                return
            from django.utils import timezone

            DriveReorganizacaoJob.objects.filter(
                status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO
            ).update(
                status=DriveReorganizacaoJob.STATUS_ERRO,
                mensagem="Interrompido por reinício do processo (deploy/restart).",
                finalizado_em=timezone.now(),
            )
        except Exception:
            pass
