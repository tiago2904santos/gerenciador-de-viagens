from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase

import documentos.management.commands.documentos_setup_pdf as setup_mod


class DocumentosSetupPdfCommandTests(SimpleTestCase):
    @mock.patch.object(setup_mod.subprocess, "run")
    def test_sem_yes_nao_executa_subprocess(self, m_run):
        call_command("documentos_setup_pdf", "--python-only")
        m_run.assert_not_called()

    @mock.patch.object(setup_mod.subprocess, "run", return_value=mock.Mock(returncode=0))
    def test_dry_run_nao_executa(self, m_run):
        call_command("documentos_setup_pdf", "--dry-run", "--yes")
        m_run.assert_not_called()

    @mock.patch.object(setup_mod.shutil, "which", return_value=None)
    @mock.patch.object(setup_mod.subprocess, "run", return_value=mock.Mock(returncode=0))
    def test_yes_executa_pip(self, m_run, *_m):
        call_command("documentos_setup_pdf", "--yes", "--python-only")
        self.assertTrue(m_run.called)
        first = m_run.call_args[0][0]
        self.assertIn("-m", first)
        self.assertIn("pip", first)
