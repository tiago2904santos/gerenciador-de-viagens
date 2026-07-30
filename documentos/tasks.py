"""Tarefas pesadas do núcleo documental."""

from __future__ import annotations

try:
    from celery import shared_task
except ModuleNotFoundError:
    def shared_task(*dargs, **dkwargs):
        def decorator(func):
            def _sem_celery(*args, **kwargs):
                raise RuntimeError("Celery não está instalado")

            func.delay = _sem_celery
            return func

        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return decorator(dargs[0])
        return decorator


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def gerar_pdf_oficio_cache(oficio_id: int) -> None:
    from documentos.services.types import DocumentoFormato
    from oficios.models import Oficio
    from oficios.services import gerar_resposta_documento_oficio
    from oficios.services import validar_oficio_para_documento

    oficio = Oficio.objects.filter(pk=oficio_id).first()
    if oficio is None:
        return
    if validar_oficio_para_documento(oficio).get("pendencias"):
        return
    gerar_resposta_documento_oficio(oficio, DocumentoFormato.PDF)


@shared_task
def gerar_documento_assincrono(job_id: str) -> None:
    from django.utils import timezone

    from documentos.models import DocumentoGeracao
    from documentos.services.async_generation import concluir_job
    from documentos.services.async_generation import falhar_job
    from documentos.services.async_generation import gerar_resposta_do_job

    job = DocumentoGeracao.objects.filter(pk=job_id).first()
    if job is None or job.status == DocumentoGeracao.STATUS_CONCLUIDO:
        return
    job.status = DocumentoGeracao.STATUS_PROCESSANDO
    job.iniciado_em = timezone.now()
    job.erro = ""
    job.save(update_fields=["status", "iniciado_em", "erro"])
    try:
        response = gerar_resposta_do_job(job)
        concluir_job(job, response)
    except Exception as exc:
        falhar_job(job, exc)


@shared_task
def manter_geracoes_documentais(
    *,
    max_age_minutes: int = 30,
    retention_hours: int = 24,
) -> dict[str, int]:
    from datetime import timedelta

    from django.utils import timezone

    from documentos.models import DocumentoGeracao

    now = timezone.now()
    limite_orfas = now - timedelta(minutes=max(1, max_age_minutes))
    orfas = DocumentoGeracao.objects.filter(
        status__in=(
            DocumentoGeracao.STATUS_NA_FILA,
            DocumentoGeracao.STATUS_PROCESSANDO,
        ),
        criado_em__lt=limite_orfas,
    ).update(
        status=DocumentoGeracao.STATUS_ERRO,
        erro="A geração foi interrompida antes da conclusão.",
        concluido_em=now,
    )

    removidas = 0
    limite_retencao = now - timedelta(hours=max(1, retention_hours))
    jobs = DocumentoGeracao.objects.filter(
        status__in=(
            DocumentoGeracao.STATUS_CONCLUIDO,
            DocumentoGeracao.STATUS_ERRO,
        ),
        concluido_em__lt=limite_retencao,
    )
    for job in jobs.iterator():
        if job.arquivo:
            job.arquivo.delete(save=False)
        job.delete()
        removidas += 1
    return {"orfas": orfas, "removidas": removidas}
