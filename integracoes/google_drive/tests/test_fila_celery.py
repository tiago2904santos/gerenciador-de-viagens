"""O Drive tem fila própria.

Enquanto tudo dividia a fila padrão, o job de geração documental que o usuário
acabou de pedir esperava atrás das tarefas do Drive — que geram PDF de verdade
(`organizar_oficio` → ofício, justificativa, OS e um termo por servidor) no
mesmo worker e no mesmo unoserver.
"""

from django.conf import settings
from django.test import SimpleTestCase

from config.celery import app
from integracoes.google_drive import tasks as drive_tasks

_PREFIXO_DRIVE = "integracoes.google_drive.tasks."


def _nomes_das_tarefas_do_drive() -> list[str]:
    """Lê do módulo, não de `app.tasks`: o autodiscover é preguiçoso."""
    nomes = set()
    for atributo in vars(drive_tasks).values():
        nome = getattr(atributo, "name", None)
        if isinstance(nome, str) and nome.startswith(_PREFIXO_DRIVE):
            nomes.add(nome)
    return sorted(nomes)


def _fila(nome_da_tarefa: str) -> str:
    destino = app.amqp.router.route({}, nome_da_tarefa).get("queue")
    return getattr(destino, "name", destino)


class RoteamentoDeFilaTests(SimpleTestCase):
    def test_toda_tarefa_do_drive_vai_para_a_fila_do_drive(self):
        tarefas = _nomes_das_tarefas_do_drive()
        self.assertTrue(tarefas, "nenhuma tarefa Celery encontrada no módulo do Drive")
        for nome in tarefas:
            with self.subTest(tarefa=nome):
                self.assertEqual(_fila(nome), settings.CELERY_DRIVE_QUEUE)

    def test_geracao_documental_fica_na_fila_padrao(self):
        for nome in (
            "documentos.tasks.gerar_documento_assincrono",
            "documentos.tasks.gerar_pdf_oficio_cache",
            "documentos.tasks.manter_geracoes_documentais",
        ):
            with self.subTest(tarefa=nome):
                self.assertEqual(_fila(nome), settings.CELERY_TASK_DEFAULT_QUEUE)

    def test_filas_sao_distintas(self):
        self.assertNotEqual(settings.CELERY_DRIVE_QUEUE, settings.CELERY_TASK_DEFAULT_QUEUE)
