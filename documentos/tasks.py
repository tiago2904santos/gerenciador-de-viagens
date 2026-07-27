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
