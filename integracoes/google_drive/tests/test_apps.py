"""Regressão: job de reorganização "em andamento" órfão (processo reiniciado
no meio) trava o spinner da tela de Configurações pra sempre, porque o JS só
para de repetir o polling quando o job deixa de estar "em_andamento"."""

from __future__ import annotations

from unittest import mock

from django.apps import apps
from django.test import TestCase

from integracoes.google_drive.models import DriveReorganizacaoJob


class MarcarJobsOrfaosTests(TestCase):
    def setUp(self):
        self.app_config = apps.get_app_config("google_drive")

    def _marcar(self):
        with mock.patch("sys.argv", ["manage.py", "runserver"]):
            self.app_config._marcar_jobs_orfaos()

    def test_marca_job_em_andamento_como_erro(self):
        job = DriveReorganizacaoJob.objects.create(
            status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO, total_eventos=7
        )
        self._marcar()
        job.refresh_from_db()
        self.assertEqual(job.status, DriveReorganizacaoJob.STATUS_ERRO)
        self.assertIsNotNone(job.finalizado_em)

    def test_nao_mexe_em_job_ja_concluido(self):
        job = DriveReorganizacaoJob.objects.create(
            status=DriveReorganizacaoJob.STATUS_CONCLUIDA, total_eventos=3
        )
        self._marcar()
        job.refresh_from_db()
        self.assertEqual(job.status, DriveReorganizacaoJob.STATUS_CONCLUIDA)

    def test_pula_durante_comando_test(self):
        """Chamado durante manage.py test, não deve tocar em nada (evita
        mexer no banco de teste durante o boot da suíte)."""
        job = DriveReorganizacaoJob.objects.create(
            status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO, total_eventos=1
        )
        with mock.patch("sys.argv", ["manage.py", "test"]):
            self.app_config._marcar_jobs_orfaos()
        job.refresh_from_db()
        self.assertEqual(job.status, DriveReorganizacaoJob.STATUS_EM_ANDAMENTO)
