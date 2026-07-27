"""Jobs órfãos são recuperados pelo Celery Beat, nunca no startup do Django."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from integracoes.google_drive.models import DriveReorganizacaoJob
from integracoes.google_drive.tasks import marcar_reorganizacoes_orfas


class MarcarJobsOrfaosTests(TestCase):
    def test_marca_job_antigo_em_andamento_como_erro(self):
        job = DriveReorganizacaoJob.objects.create(
            status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO,
            total_eventos=7,
        )
        DriveReorganizacaoJob.objects.filter(pk=job.pk).update(
            iniciado_em=timezone.now() - timedelta(hours=1),
        )

        self.assertEqual(marcar_reorganizacoes_orfas(max_age_minutes=30), 1)

        job.refresh_from_db()
        self.assertEqual(job.status, DriveReorganizacaoJob.STATUS_ERRO)
        self.assertIsNotNone(job.finalizado_em)

    def test_nao_mexe_em_job_recente_ou_concluido(self):
        recente = DriveReorganizacaoJob.objects.create(
            status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO,
        )
        concluido = DriveReorganizacaoJob.objects.create(
            status=DriveReorganizacaoJob.STATUS_CONCLUIDA,
        )

        self.assertEqual(marcar_reorganizacoes_orfas(max_age_minutes=30), 0)
        recente.refresh_from_db()
        concluido.refresh_from_db()
        self.assertEqual(recente.status, DriveReorganizacaoJob.STATUS_EM_ANDAMENTO)
        self.assertEqual(concluido.status, DriveReorganizacaoJob.STATUS_CONCLUIDA)
