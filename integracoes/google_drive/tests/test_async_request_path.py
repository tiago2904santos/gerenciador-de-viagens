from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings

from documentos.models import DocumentoArtefato
from integracoes.google_drive import services
from integracoes.google_drive import signals
from core.testing import area_de_teste
class DriveSignalAsyncRequestPathTests(TestCase):
    def test_signal_nao_executa_drive_dentro_da_request(self):
        artefato = DocumentoArtefato.objects.create(area=area_de_teste(), 
            tipo="teste",
            formato="pdf",
            hash_sha256="b" * 64,
        )
        operation = mock.Mock()
        task = mock.Mock()

        with self.captureOnCommitCallbacks(execute=True):
            signals._processar_com_retry(operation, artefato, task)

        operation.assert_not_called()
        task.delay.assert_called_once_with(artefato.pk, usuario_id=None)


@override_settings(GOOGLE_DRIVE={"MODO": "real", "UPLOAD_EM_MOCK": False})
class ManualSignatureAsyncRequestPathTests(TestCase):
    def test_assinatura_e_agendada_depois_do_commit(self):
        user = get_user_model().objects.create_user(username="drive-async")
        with mock.patch(
            "integracoes.google_drive.tasks.processar_artefato.delay"
        ):
            artefato = DocumentoArtefato.objects.create(area=area_de_teste(), 
                tipo="oficio",
                formato="pdf",
                hash_sha256="a" * 64,
            )

        with mock.patch(
            "integracoes.google_drive.tasks.sincronizar_assinatura_manual.delay"
        ) as delay:
            with self.captureOnCommitCallbacks(execute=True):
                services.agendar_sincronizacao_assinatura_manual(
                    artefato,
                    usuario=user,
                )

        delay.assert_called_once_with(artefato.pk, usuario_id=user.pk)
