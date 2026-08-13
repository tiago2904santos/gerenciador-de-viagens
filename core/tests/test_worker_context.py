from unittest import mock

from django.test import TestCase

from core import middleware
from core.testing import area_de_teste
from core.testing import com_request
from documentos import tasks as documentos_tasks
from integracoes.google_drive import tasks as drive_tasks
from oficios.models import Oficio


TASKS_DOCUMENTOS = (
    documentos_tasks.gerar_pdf_oficio_cache,
    documentos_tasks.gerar_documento_assincrono,
    documentos_tasks.manter_geracoes_documentais,
)

TASKS_DRIVE = (
    drive_tasks.processar_artefato,
    drive_tasks.sincronizar_assinatura_manual,
    drive_tasks.processar_prestacao,
    drive_tasks.processar_evento_anexo,
    drive_tasks.processar_solicitacao_evento,
    drive_tasks.processar_sincronizar_pasta_evento,
    drive_tasks.organizar_oficio,
    drive_tasks.organizar_evento,
    drive_tasks.reorganizar_drive,
    drive_tasks.reprocessar_pendencias,
    drive_tasks.marcar_reorganizacoes_orfas,
)


class WorkerContextContractTests(TestCase):
    def test_toda_task_de_dados_declara_contexto_de_worker(self):
        for task in (*TASKS_DOCUMENTOS, *TASKS_DRIVE):
            with self.subTest(task=task.name):
                self.assertTrue(
                    getattr(task.run, "executa_sem_request", False),
                    msg=f"{task.name} pode herdar o request em modo eager",
                )

    def test_task_documental_enxerga_objeto_de_outra_area_e_restaura_request(self):
        area_request = area_de_teste(sigla="WRK-A", nome="Worker A")
        area_objeto = area_de_teste(sigla="WRK-B", nome="Worker B")
        oficio = Oficio.objects.create(area=area_objeto, numero=20, ano=2026)

        with mock.patch(
            "oficios.services.validar_oficio_para_documento",
            return_value={"pendencias": []},
        ), mock.patch("oficios.services.gerar_resposta_documento_oficio") as gerar:
            with com_request(area_request) as request:
                documentos_tasks.gerar_pdf_oficio_cache(oficio.pk)
                self.assertIs(middleware.get_current_request(), request)

        gerar.assert_called_once()

    def test_task_drive_enxerga_objeto_de_outra_area_e_restaura_request(self):
        area_request = area_de_teste(sigla="DRV-A", nome="Drive A")
        area_objeto = area_de_teste(sigla="DRV-B", nome="Drive B")
        oficio = Oficio.objects.create(area=area_objeto, numero=21, ano=2026)

        with mock.patch("integracoes.google_drive.status.executar_e_rastrear") as executar:
            with com_request(area_request) as request:
                drive_tasks.organizar_oficio(oficio.pk)
                self.assertIs(middleware.get_current_request(), request)

        executar.assert_called_once()
