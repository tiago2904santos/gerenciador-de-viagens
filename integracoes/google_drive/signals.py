from __future__ import annotations

import logging

from core.errors import capture

logger = logging.getLogger(__name__)


def _agendar_apos_commit(task, *args) -> None:
    from django.db import transaction

    def enviar():
        try:
            task.delay(*args)
        except Exception as exc:
            capture(exc, "drive.signals.enviar")  # pragma: no cover
            logger.exception("[Drive] não foi possível agendar tarefa assíncrona")

    transaction.on_commit(enviar)


def conectar() -> None:
    from django.db.models.signals import post_save, pre_delete

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
    post_save.connect(
        _sincronizar_pasta_evento_ao_salvar, sender=Evento, dispatch_uid="gdrive_evento_pasta_sync"
    )

    pre_delete.connect(
        _limpar_drive_artefato, sender=DocumentoArtefato, dispatch_uid="gdrive_excluir_artefato"
    )
    for model, dispatch_uid in (
        (PrestacaoContas, "gdrive_excluir_prestacao"),
        (PrestacaoDocumentoAnexo, "gdrive_excluir_prestacao_anexo"),
        (AssinaturaDocumento, "gdrive_excluir_prestacao_assinatura"),
        (EventoAnexo, "gdrive_excluir_evento_anexo"),
        (EventoDocumentoSolicitacao, "gdrive_excluir_evento_solicitacao"),
        (Evento, "gdrive_excluir_evento_nota"),
    ):
        pre_delete.connect(_limpar_drive_externo, sender=model, dispatch_uid=dispatch_uid)

    pre_delete.connect(
        _limpar_pasta_evento, sender=Evento, dispatch_uid="gdrive_excluir_evento_pasta"
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
    except Exception as exc:
        # Sem MessageMiddleware ativo (ex.: comando de management, shell) — ignora.
        capture(exc, "drive.signals._avisar_usuario")  # pragma: no cover
        pass


def _usuario_atual():
    from core.middleware import get_current_request

    request = get_current_request()
    user = getattr(request, "user", None) if request is not None else None
    return user if user is not None and getattr(user, "is_authenticated", False) else None


def _usuario_por_id(usuario_id):
    if not usuario_id:
        return None
    from django.contrib.auth import get_user_model

    return get_user_model().objects.filter(pk=usuario_id).first()


def _processar_com_retry(fn, obj, task) -> None:
    """Agenda a sincronização somente depois do commit.

    ``fn`` permanece no contrato para documentar qual operação a tarefa
    representa, mas rede/Drive nunca executa dentro do request que salvou o
    objeto. Isso evita que anexos pareçam travados após o arquivo já estar
    persistido localmente.
    """
    _ = fn
    usuario = _usuario_atual()
    usuario_id = getattr(usuario, "pk", None)

    def enviar():
        from . import status

        try:
            task.delay(obj.pk, usuario_id=usuario_id)
        except Exception as exc:
            capture(exc, "drive.signals.enviar")  # pragma: no cover
            status.registrar_falha(obj, exc, usuario=usuario)
            logger.warning(
                "[Drive] fila indisponível (%s); %s #%s fica pendente até reenvio manual",
                exc,
                obj.__class__.__name__,
                obj.pk,
            )
            _avisar_usuario(
                f'O arquivo "{_descrever(obj)}" foi salvo, mas o envio ao '
                "Google Drive ficou pendente."
            )

    from django.db import transaction

    transaction.on_commit(enviar)


def _upload_artefato(sender, instance, created: bool, **kwargs) -> None:
    if not created or _drive_desligado():
        return
    from . import organizer, tasks

    _processar_com_retry(
        organizer.organizar_artefato,
        instance,
        tasks.processar_artefato,
    )


# Campos que não afetam os documentos da prestação no Drive: arquivar/finalizar
# são apenas estado de listagem, não devem disparar reorganização de arquivos.
_PRESTACAO_CAMPOS_SEM_DRIVE = {
    "arquivada", "arquivada_em", "finalizada", "finalizada_em", "atualizado_em",
}


def _organizar_prestacao(sender, instance, update_fields=None, **kwargs) -> None:
    if _drive_desligado():
        return
    # Save que mexeu só em flags de listagem (arquivar/finalizar) não muda nada
    # no Drive — evita reorganização desnecessária.
    if update_fields is not None and set(update_fields) <= _PRESTACAO_CAMPOS_SEM_DRIVE:
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

    Roda em segundo plano (Celery) porque envolve GERAR PDFs de verdade (não é
    só subir um arquivo já pronto) — fazer isso de forma síncrona deixaria o
    salvamento do ofício lento. As funções de backfill (``_garantir_*``) só
    geram o que ainda não existe, então salvar o ofício várias vezes não
    duplica nem reprocessa à toa.
    """
    if _drive_desligado():
        return
    if instance.status == instance.STATUS_RASCUNHO:
        return
    from .tasks import organizar_oficio

    _agendar_apos_commit(
        organizar_oficio,
        instance.pk,
        getattr(_usuario_atual(), "pk", None),
    )


def _organizar_oficio_em_thread(oficio_id: int, usuario_id=None) -> None:
    from django.db import connection

    from . import organizer

    try:
        from oficios.models import Oficio

        oficio = Oficio.objects.filter(pk=oficio_id).first()
        if oficio is None:
            return
        try:
            from . import status

            usuario = _usuario_por_id(usuario_id)
            with organizer.usar_usuario(usuario):
                status.executar_e_rastrear(organizer.organizar_oficio, oficio, usuario=usuario)
        except Exception as exc:
            capture(exc, "drive.signals._organizar_oficio_em_thread")  # pragma: no cover
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
    from .tasks import organizar_evento

    _agendar_apos_commit(
        organizar_evento,
        instance.pk,
        getattr(_usuario_atual(), "pk", None),
    )


def _sincronizar_pasta_evento_ao_salvar(sender, instance, **kwargs) -> None:
    """Cria (na primeira vez com dados suficientes) ou renomeia a pasta do
    evento no Drive sempre que ele é salvo — inclusive antes de sair do
    rascunho — para refletir qualquer alteração de tipo/cidade/data.

    Diferente de ``_organizar_evento_ao_salvar`` (que só roda quando o evento
    sai do rascunho, pois organiza documentos e gera PDFs reais em segundo
    plano), aqui sincronizamos a pasta em uma tarefa assíncrona curta
    (mesmo padrão de ``_organizar_evento_anexo``/``_organizar_solicitacao``).
    A função chamada (``organizer.sincronizar_pasta_evento``) não faz nada
    enquanto a Etapa 1 ainda não tiver dados suficientes.
    """
    if _drive_desligado():
        return
    from . import organizer, tasks

    _processar_com_retry(
        organizer.sincronizar_pasta_evento, instance, tasks.processar_sincronizar_pasta_evento
    )


def _excluir_no_drive(client, reg) -> None:
    """Move para a lixeira o arquivo canônico e o atalho (se houver) de um registro."""
    if reg.file_id:
        try:
            client.mover_para_lixeira(reg.file_id)
        except Exception as exc:
            capture(exc, "drive.signals._excluir_no_drive")  # pragma: no cover
            logger.error("[Drive] falha ao mover file_id=%s para a lixeira", reg.file_id, exc_info=True)
    if getattr(reg, "atalho_id", ""):
        try:
            client.mover_para_lixeira(reg.atalho_id)
        except Exception as exc:
            capture(exc, "drive.signals._excluir_no_drive")  # pragma: no cover
            logger.error("[Drive] falha ao mover atalho_id=%s para a lixeira", reg.atalho_id, exc_info=True)


def _limpar_drive_artefato(sender, instance, **kwargs) -> None:
    """Ao excluir um ``DocumentoArtefato``, move seu arquivo (e atalho) no Drive
    para a lixeira antes que o ``DriveArquivo`` seja cascateado do banco."""
    if _drive_desligado():
        return
    reg = getattr(instance, "drive_arquivo", None)
    if reg is None:
        return
    from .services import get_client

    try:
        client = get_client()
    except Exception as exc:
        capture(exc, "drive.signals._limpar_drive_artefato")  # pragma: no cover
        logger.error(
            "[Drive] falha ao obter client para excluir artefato %s", instance.pk, exc_info=True
        )
        return
    _excluir_no_drive(client, reg)


def _limpar_drive_externo(sender, instance, **kwargs) -> None:
    """Ao excluir qualquer origem rastreada em ``DriveArquivoExterno`` (prestação,
    anexo de prestação, assinatura, anexo de evento, solicitação, nota de
    cancelamento), move os arquivos correspondentes no Drive para a lixeira.

    Roda em ``pre_delete`` porque ``DriveArquivoExterno`` usa ``GenericForeignKey``
    (sem FK de verdade) — não cascateia sozinho e ficaria órfão no banco.
    """
    if _drive_desligado():
        return
    from django.contrib.contenttypes.models import ContentType

    from .models import DriveArquivoExterno

    ct = ContentType.objects.get_for_model(instance.__class__)
    regs = list(DriveArquivoExterno.objects.filter(content_type=ct, object_id=instance.pk))
    if not regs:
        return
    from .services import get_client

    try:
        client = get_client()
    except Exception as exc:
        capture(exc, "drive.signals._limpar_drive_externo")  # pragma: no cover
        logger.error(
            "[Drive] falha ao obter client para excluir arquivos de %s #%s",
            instance.__class__.__name__, instance.pk, exc_info=True,
        )
        return
    for reg in regs:
        _excluir_no_drive(client, reg)
    DriveArquivoExterno.objects.filter(pk__in=[reg.pk for reg in regs]).delete()


def _limpar_pasta_evento(sender, instance, **kwargs) -> None:
    """Ao excluir um Evento, move a pasta inteira do evento no Drive para a lixeira.

    Roda em ``pre_delete`` depois que os documentos do evento já foram excluídos
    (Django deleta dependentes antes do próprio evento), quando seus arquivos
    canônicos e atalhos já foram movidos para a lixeira individualmente por
    ``_limpar_drive_artefato``/``_limpar_drive_externo``. Esta função cuida do que
    sobra: a pasta do evento em si (que ficaria vazia, mas visível, no Drive).
    """
    if _drive_desligado():
        return
    from . import organizer
    from .services import get_client

    pasta_id = instance.drive_folder_id or None
    if not pasta_id:
        from eventos.services import _evento_dados_completos

        if not _evento_dados_completos(instance):
            # Nunca teve dados suficientes (Etapa 1) para ganhar uma pasta própria.
            return

    try:
        client = get_client()
    except Exception as exc:
        capture(exc, "drive.signals._limpar_pasta_evento")  # pragma: no cover
        logger.error(
            "[Drive] falha ao obter client para excluir pasta do evento #%s", instance.pk, exc_info=True
        )
        return
    if pasta_id is None:
        try:
            pasta_id = organizer._pasta_evento_folder(client, instance)
        except Exception as exc:
            capture(exc, "drive.signals._limpar_pasta_evento")  # pragma: no cover
            logger.error(
                "[Drive] falha ao localizar pasta do evento #%s", instance.pk, exc_info=True
            )
            return
    try:
        client.mover_para_lixeira(pasta_id)
    except Exception as exc:
        capture(exc, "drive.signals._limpar_pasta_evento")  # pragma: no cover
        logger.error(
            "[Drive] falha ao mover pasta do evento #%s para a lixeira", instance.pk, exc_info=True
        )
        return

    from django.contrib.contenttypes.models import ContentType

    from .models import DriveArquivoExterno

    ct = ContentType.objects.get_for_model(instance.__class__)
    DriveArquivoExterno.objects.filter(
        content_type=ct, object_id=instance.pk, campo="pasta_evento"
    ).delete()


def _organizar_evento_em_thread(evento_id: int, usuario_id=None) -> None:
    from django.db import connection

    from . import organizer

    try:
        from eventos.models import Evento

        evento = Evento.objects.filter(pk=evento_id).first()
        if evento is None:
            return
        try:
            from . import status

            usuario = _usuario_por_id(usuario_id)
            with organizer.usar_usuario(usuario):
                status.executar_e_rastrear(organizer.organizar_evento, evento, usuario=usuario)
        except Exception as exc:
            capture(exc, "drive.signals._organizar_evento_em_thread")  # pragma: no cover
            logger.error(
                "[Drive] falha ao gerar/organizar evento #%s em segundo plano",
                evento_id, exc_info=True,
            )
    finally:
        connection.close()
