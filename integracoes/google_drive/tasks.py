"""Tarefas Celery de retry em segundo plano para uploads ao Drive.

Disparadas por ``signals.py`` quando a tentativa síncrona (a que roda dentro
do próprio request, ao salvar o objeto) falha. Cada tarefa é idempotente
(delega para as mesmas funções de ``organizer`` usadas no caminho síncrono) e
tenta de novo automaticamente, com backoff exponencial, até ``_RETRY_MAX``
vezes — depois disso, o objeto continua marcado como pendência (ver
``status.py``) até um reenvio manual (botão "Tentar novamente" ou os comandos
``gdrive_upload_pendentes``/"Reorganizar tudo").
"""

from __future__ import annotations

try:
    from celery import shared_task
except ModuleNotFoundError:
    # Celery não instalado (ex.: dev local sem broker). Fornecemos um decorator
    # equivalente cujo ``.delay()`` levanta erro — capturado em ``signals.py``,
    # que então registra o objeto como pendência para reenvio manual.
    def shared_task(*dargs, **dkwargs):
        def decorator(func):
            def _sem_celery(*args, **kwargs):
                raise RuntimeError("Celery não está instalado; retry indisponível")

            func.delay = _sem_celery
            func.apply_async = _sem_celery
            return func

        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return decorator(dargs[0])
        return decorator

from . import organizer, status

_RETRY_MAX = 8
_RETRY_BACKOFF_MAX = 3600  # tempo máximo entre tentativas: 1h

_TASK_KWARGS = dict(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=_RETRY_BACKOFF_MAX,
    retry_jitter=True,
    max_retries=_RETRY_MAX,
)


@shared_task(**_TASK_KWARGS)
def processar_artefato(self, artefato_id: int) -> None:
    from documentos.models import DocumentoArtefato

    art = DocumentoArtefato.objects.filter(pk=artefato_id).first()
    if art is None:
        status.limpar_pendencia_orfa(DocumentoArtefato, artefato_id)
        return
    status.executar_e_rastrear(organizer.organizar_artefato, art)


@shared_task(**_TASK_KWARGS)
def processar_prestacao(self, prestacao_id: int) -> None:
    from prestacoes_contas.models import PrestacaoContas

    prestacao = PrestacaoContas.objects.filter(pk=prestacao_id).first()
    if prestacao is None:
        status.limpar_pendencia_orfa(PrestacaoContas, prestacao_id)
        return
    status.executar_e_rastrear(organizer.organizar_prestacao, prestacao)


@shared_task(**_TASK_KWARGS)
def processar_evento_anexo(self, anexo_id: int) -> None:
    from eventos.models import EventoAnexo

    anexo = EventoAnexo.objects.filter(pk=anexo_id).first()
    if anexo is None:
        status.limpar_pendencia_orfa(EventoAnexo, anexo_id)
        return
    status.executar_e_rastrear(organizer.organizar_evento_anexo, anexo)


@shared_task(**_TASK_KWARGS)
def processar_solicitacao_evento(self, solicitacao_id: int) -> None:
    from eventos.models import EventoDocumentoSolicitacao

    doc = EventoDocumentoSolicitacao.objects.filter(pk=solicitacao_id).first()
    if doc is None:
        status.limpar_pendencia_orfa(EventoDocumentoSolicitacao, solicitacao_id)
        return
    status.executar_e_rastrear(organizer.organizar_solicitacao_evento, doc)


@shared_task(**_TASK_KWARGS)
def processar_sincronizar_pasta_evento(self, evento_id: int) -> None:
    from eventos.models import Evento

    evento = Evento.objects.filter(pk=evento_id).first()
    if evento is None:
        return
    status.executar_e_rastrear(organizer.sincronizar_pasta_evento, evento)
