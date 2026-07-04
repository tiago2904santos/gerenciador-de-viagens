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

from celery import shared_task

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
        return
    status.executar_e_rastrear(organizer.organizar_artefato, art)


@shared_task(**_TASK_KWARGS)
def processar_prestacao(self, prestacao_id: int) -> None:
    from prestacoes_contas.models import PrestacaoContas

    prestacao = PrestacaoContas.objects.filter(pk=prestacao_id).first()
    if prestacao is None:
        return
    status.executar_e_rastrear(organizer.organizar_prestacao, prestacao)


@shared_task(**_TASK_KWARGS)
def processar_evento_anexo(self, anexo_id: int) -> None:
    from eventos.models import EventoAnexo

    anexo = EventoAnexo.objects.filter(pk=anexo_id).first()
    if anexo is None:
        return
    status.executar_e_rastrear(organizer.organizar_evento_anexo, anexo)


@shared_task(**_TASK_KWARGS)
def processar_solicitacao_evento(self, solicitacao_id: int) -> None:
    from eventos.models import EventoDocumentoSolicitacao

    doc = EventoDocumentoSolicitacao.objects.filter(pk=solicitacao_id).first()
    if doc is None:
        return
    status.executar_e_rastrear(organizer.organizar_solicitacao_evento, doc)
