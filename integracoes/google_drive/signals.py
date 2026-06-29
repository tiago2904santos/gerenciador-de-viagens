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


def _upload_artefato(sender, instance, created: bool, **kwargs) -> None:
    if not created or _drive_desligado():
        return
    try:
        from integracoes.google_drive import organizer

        organizer.organizar_artefato(instance)
    except Exception as exc:
        logger.error("[Drive] erro no signal de artefato %s: %s", instance.pk, exc, exc_info=True)


def _organizar_prestacao(sender, instance, **kwargs) -> None:
    if _drive_desligado():
        return
    try:
        from integracoes.google_drive import organizer

        organizer.organizar_prestacao(instance)
    except Exception as exc:
        logger.error("[Drive] erro no signal de prestação %s: %s", instance.pk, exc, exc_info=True)


def _organizar_prestacao_filho(sender, instance, **kwargs) -> None:
    """Anexo/assinatura de prestação: reorganiza a prestação inteira (idempotente)."""
    if _drive_desligado():
        return
    prestacao = getattr(instance, "prestacao", None)
    if prestacao is None:
        return
    try:
        from integracoes.google_drive import organizer

        organizer.organizar_prestacao(prestacao)
    except Exception as exc:
        logger.error("[Drive] erro no signal de filho de prestação %s: %s", instance.pk, exc, exc_info=True)


def _organizar_evento_anexo(sender, instance, **kwargs) -> None:
    if _drive_desligado():
        return
    try:
        from integracoes.google_drive import organizer

        organizer.organizar_evento_anexo(instance)
    except Exception as exc:
        logger.error("[Drive] erro no signal de anexo de evento %s: %s", instance.pk, exc, exc_info=True)


def _organizar_solicitacao(sender, instance, **kwargs) -> None:
    if _drive_desligado():
        return
    try:
        from integracoes.google_drive import organizer

        organizer.organizar_solicitacao_evento(instance)
    except Exception as exc:
        logger.error("[Drive] erro no signal de solicitação %s: %s", instance.pk, exc, exc_info=True)
