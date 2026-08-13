"""Tarefas Celery em segundo plano para uploads ao Drive.

Os signals agendam estas tarefas somente depois do commit: a API do Google
Drive nunca participa do tempo de resposta que salva ou anexa um arquivo.
Cada tarefa é idempotente e tenta novamente com backoff exponencial até
``_RETRY_MAX`` vezes. Depois disso, o objeto permanece marcado como pendente
para reenvio manual.
"""

from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from core.middleware import executar_sem_request

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


def _usuario_por_id(usuario_id):
    if not usuario_id:
        return None
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(pk=usuario_id).first()


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def processar_artefato(self, artefato_id: int, usuario_id=None) -> None:
    from documentos.models import DocumentoArtefato

    art = DocumentoArtefato.objects.filter(pk=artefato_id).first()
    if art is None:
        status.limpar_pendencia_orfa(DocumentoArtefato, artefato_id)
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(organizer.organizar_artefato, art, usuario=usuario)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def sincronizar_assinatura_manual(self, artefato_id: int, usuario_id=None) -> None:
    from documentos.models import DocumentoArtefato

    artefato = DocumentoArtefato.objects.filter(pk=artefato_id).first()
    if artefato is None:
        status.limpar_pendencia_orfa(DocumentoArtefato, artefato_id)
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(
            organizer.sincronizar_conteudo_assinado,
            artefato,
            usuario=usuario,
        )


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def processar_prestacao(self, prestacao_id: int, usuario_id=None) -> None:
    from prestacoes_contas.models import PrestacaoContas

    prestacao = PrestacaoContas.objects.filter(pk=prestacao_id).first()
    if prestacao is None:
        status.limpar_pendencia_orfa(PrestacaoContas, prestacao_id)
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(organizer.organizar_prestacao, prestacao, usuario=usuario)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def processar_evento_anexo(self, anexo_id: int, usuario_id=None) -> None:
    from eventos.models import EventoAnexo

    anexo = EventoAnexo.objects.filter(pk=anexo_id).first()
    if anexo is None:
        status.limpar_pendencia_orfa(EventoAnexo, anexo_id)
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(organizer.organizar_evento_anexo, anexo, usuario=usuario)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def processar_solicitacao_evento(self, solicitacao_id: int, usuario_id=None) -> None:
    from eventos.models import EventoDocumentoSolicitacao

    doc = EventoDocumentoSolicitacao.objects.filter(pk=solicitacao_id).first()
    if doc is None:
        status.limpar_pendencia_orfa(EventoDocumentoSolicitacao, solicitacao_id)
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(organizer.organizar_solicitacao_evento, doc, usuario=usuario)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def processar_sincronizar_pasta_evento(self, evento_id: int, usuario_id=None) -> None:
    from eventos.models import Evento

    evento = Evento.objects.filter(pk=evento_id).first()
    if evento is None:
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(organizer.sincronizar_pasta_evento, evento, usuario=usuario)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def organizar_oficio(self, oficio_id: int, usuario_id=None) -> None:
    from oficios.models import Oficio

    oficio = Oficio.objects.filter(pk=oficio_id).first()
    if oficio is None:
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(organizer.organizar_oficio, oficio, usuario=usuario)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def organizar_evento(self, evento_id: int, usuario_id=None) -> None:
    from eventos.models import Evento

    evento = Evento.objects.filter(pk=evento_id).first()
    if evento is None:
        return
    usuario = _usuario_por_id(usuario_id)
    with organizer.usar_usuario(usuario):
        status.executar_e_rastrear(organizer.organizar_evento, evento, usuario=usuario)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def reorganizar_drive(self, job_id: int, usuario_id=None, area_id=None) -> None:
    from usuarios.models import AreaTrabalho
    from .views import _executar_reorganizacao

    usuario = _usuario_por_id(usuario_id)
    area = AreaTrabalho.objects.filter(pk=area_id).first() if area_id else None
    _executar_reorganizacao(job_id, usuario, area)


@shared_task(**_TASK_KWARGS)
@executar_sem_request
def reprocessar_pendencias(self, usuario_id=None, area_id=None) -> None:
    from usuarios.models import AreaTrabalho
    from .views import _reprocessar_pendencias_em_thread

    usuario = _usuario_por_id(usuario_id)
    area = AreaTrabalho.objects.filter(pk=area_id).first() if area_id else None
    _reprocessar_pendencias_em_thread(usuario, area)


@shared_task
@executar_sem_request
def marcar_reorganizacoes_orfas(max_age_minutes: int = 30) -> int:
    """Encerra jobs abandonados sem consultar o banco no startup do Django."""
    from .models import DriveReorganizacaoJob

    limite = timezone.now() - timedelta(minutes=max(1, max_age_minutes))
    return DriveReorganizacaoJob.objects.filter(
        status=DriveReorganizacaoJob.STATUS_EM_ANDAMENTO,
        iniciado_em__lt=limite,
    ).update(
        status=DriveReorganizacaoJob.STATUS_ERRO,
        finalizado_em=timezone.now(),
        mensagem="Processamento interrompido antes da conclusão.",
    )
