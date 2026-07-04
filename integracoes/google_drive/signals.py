from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def conectar() -> None:
    from django.db.models.signals import post_save

    from documentos.models import DocumentoArtefato
    from eventos.models import EventoAnexo, EventoDocumentoSolicitacao
    from prestacoes_contas.models import (
        AssinaturaDocumento,
        PrestacaoContas,
        PrestacaoDocumentoAnexo,
    )

    post_save.connect(
        _upload_artefato, sender=DocumentoArtefato, dispatch_uid="gdrive_upload_artefato"
    )
    post_save.connect(
        _organizar_prestacao, sender=PrestacaoContas, dispatch_uid="gdrive_prestacao"
    )
    post_save.connect(
        _organizar_prestacao_filho,
        sender=PrestacaoDocumentoAnexo,
        dispatch_uid="gdrive_prestacao_anexo",
    )
    post_save.connect(
        _organizar_prestacao_filho,
        sender=AssinaturaDocumento,
        dispatch_uid="gdrive_prestacao_assinatura",
    )
    post_save.connect(
        _organizar_evento_anexo, sender=EventoAnexo, dispatch_uid="gdrive_evento_anexo"
    )
    post_save.connect(
        _organizar_solicitacao,
        sender=EventoDocumentoSolicitacao,
        dispatch_uid="gdrive_evento_solicitacao",
    )


def _drive_desligado() -> bool:
    """True quando não devemos tocar no Drive (mock sem upload habilitado)."""
    from django.conf import settings

    cfg = getattr(settings, "GOOGLE_DRIVE", {})
    modo = cfg.get("MODO", "mock").lower()
    upload_em_mock = cfg.get("UPLOAD_EM_MOCK", False)
    return modo == "mock" and not upload_em_mock


def _descrever(obj) -> str:
    nome = getattr(obj, "nome_drive", None) or getattr(obj, "titulo", None)
    if nome:
        return str(nome)
    return f"{obj._meta.verbose_name} #{obj.pk}"


def _avisar_usuario(mensagem: str) -> None:
    from django.contrib import messages

    from core.middleware import get_current_request

    request = get_current_request()
    if request is None:
        return
    try:
        messages.warning(request, mensagem)
    except Exception:
        # Sem MessageMiddleware ativo (ex.: comando de management, shell) — ignora.
        pass


def _processar_com_retry(fn, obj, task) -> None:
    """Tenta ``fn(obj)`` na hora (como sempre foi); se falhar, avisa o usuário
    e agenda um retry em segundo plano (Celery) com backoff.

    Nunca deixa a exceção do Drive subir e quebrar o ``save()`` que disparou
    o signal — no pior caso (fila também indisponível), o objeto fica
    registrado como pendência (``status.py``) para reenvio manual depois.
    """
    from . import status

    try:
        status.executar_e_rastrear(fn, obj)
    except Exception as exc:
        logger.error(
            "[Drive] falha ao sincronizar %s #%s: %s",
            obj.__class__.__name__,
            obj.pk,
            exc,
            exc_info=True,
        )
        _avisar_usuario(
            f'Não foi possível enviar "{_descrever(obj)}" ao Google Drive agora. '
            "O sistema vai tentar novamente automaticamente em segundo plano."
        )
        try:
            task.delay(obj.pk)
        except Exception as exc2:
            logger.warning(
                "[Drive] fila de retry indisponível (%s); %s #%s fica pendente até reenvio manual",
                exc2,
                obj.__class__.__name__,
                obj.pk,
            )


def _upload_artefato(sender, instance, created: bool, **kwargs) -> None:
    if not created or _drive_desligado():
        return
    from . import organizer, tasks

    _processar_com_retry(organizer.organizar_artefato, instance, tasks.processar_artefato)


def _organizar_prestacao(sender, instance, **kwargs) -> None:
    if _drive_desligado():
        return
    from . import organizer, tasks

    _processar_com_retry(organizer.organizar_prestacao, instance, tasks.processar_prestacao)


def _organizar_prestacao_filho(sender, instance, **kwargs) -> None:
    """Anexo/assinatura de prestação: reorganiza a prestação inteira (idempotente)."""
    if _drive_desligado():
        return
    prestacao = getattr(instance, "prestacao", None)
    if prestacao is None:
        return
    from . import organizer, tasks

    _processar_com_retry(organizer.organizar_prestacao, prestacao, tasks.processar_prestacao)


def _organizar_evento_anexo(sender, instance, **kwargs) -> None:
    if _drive_desligado():
        return
    from . import organizer, tasks

    _processar_com_retry(organizer.organizar_evento_anexo, instance, tasks.processar_evento_anexo)


def _organizar_solicitacao(sender, instance, **kwargs) -> None:
    if _drive_desligado():
        return
    from . import organizer, tasks

    _processar_com_retry(
        organizer.organizar_solicitacao_evento, instance, tasks.processar_solicitacao_evento
    )
