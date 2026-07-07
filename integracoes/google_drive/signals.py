from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def conectar() -> None:
    from django.db.models.signals import post_save

    from documentos.models import DocumentoArtefato
    from eventos.models import Evento, EventoAnexo, EventoDocumentoSolicitacao
    from oficios.models import Oficio
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
    post_save.connect(
        _organizar_oficio_ao_salvar, sender=Oficio, dispatch_uid="gdrive_oficio_salvo"
    )
    post_save.connect(
        _organizar_evento_ao_salvar, sender=Evento, dispatch_uid="gdrive_evento_salvo"
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


def _organizar_oficio_ao_salvar(sender, instance, **kwargs) -> None:
    """Assim que o ofício deixa de ser rascunho, gera e sobe ao Drive tudo que
    ainda faltar (ofício, justificativa, termos, ordem de serviço) — sem
    depender de alguém abrir/baixar o documento manualmente.

    Roda em segundo plano (thread) porque envolve GERAR PDFs de verdade (não é
    só subir um arquivo já pronto) — fazer isso de forma síncrona deixaria o
    salvamento do ofício lento. As funções de backfill (``_garantir_*``) só
    geram o que ainda não existe, então salvar o ofício várias vezes não
    duplica nem reprocessa à toa.
    """
    if _drive_desligado():
        return
    if instance.status == instance.STATUS_RASCUNHO:
        return
    import threading

    threading.Thread(
        target=_organizar_oficio_em_thread, args=(instance.pk,), daemon=True
    ).start()


def _organizar_oficio_em_thread(oficio_id: int) -> None:
    from django.db import connection

    from . import organizer

    try:
        from oficios.models import Oficio

        oficio = Oficio.objects.filter(pk=oficio_id).first()
        if oficio is None:
            return
        try:
            from . import status

            status.executar_e_rastrear(organizer.organizar_oficio, oficio)
        except Exception:
            logger.error(
                "[Drive] falha ao gerar/organizar ofício #%s em segundo plano",
                oficio_id, exc_info=True,
            )
    finally:
        connection.close()


def _organizar_evento_ao_salvar(sender, instance, **kwargs) -> None:
    """Mesma ideia de ``_organizar_oficio_ao_salvar``, para o que depende do
    evento (plano de trabalho) — dispara assim que o evento sai do rascunho.
    Também roda em segundo plano pelo mesmo motivo (geração real de PDF).

    NÃO pula mais eventos cancelados: é o cancelamento que dispara mover a
    pasta pra "Eventos cancelados/", gravar o motivo e re-sincronizar os
    documentos com o sufixo "(cancelado)" (ver organizer.organizar_evento).
    """
    if _drive_desligado():
        return
    if instance.status == instance.STATUS_RASCUNHO:
        return
    import threading

    threading.Thread(
        target=_organizar_evento_em_thread, args=(instance.pk,), daemon=True
    ).start()


def _organizar_evento_em_thread(evento_id: int) -> None:
    from django.db import connection

    from . import organizer

    try:
        from eventos.models import Evento

        evento = Evento.objects.filter(pk=evento_id).first()
        if evento is None:
            return
        try:
            from . import status

            status.executar_e_rastrear(organizer.organizar_evento, evento)
        except Exception:
            logger.error(
                "[Drive] falha ao gerar/organizar evento #%s em segundo plano",
                evento_id, exc_info=True,
            )
    finally:
        connection.close()
