"""Rastreamento de pendências de sincronização com o Drive.

Uma linha em ``DriveSyncStatus`` só existe enquanto o objeto de origem
(``DocumentoArtefato``, ``PrestacaoContas``, ``EventoAnexo``,
``EventoDocumentoSolicitacao``) estiver com a última tentativa de envio
malsucedida. Isso alimenta o retry em segundo plano (Celery, ver ``tasks.py``)
e o painel de pendências da tela de configuração (ver ``views.py``).
"""

from __future__ import annotations

_LIMITE_ERRO = 2000  # trunca mensagens de exceção muito longas antes de persistir.


def registrar_falha(obj, exc: Exception) -> None:
    from django.contrib.contenttypes.models import ContentType

    from .models import DriveSyncStatus

    ct = ContentType.objects.get_for_model(obj.__class__)
    pendencia, criada = DriveSyncStatus.objects.get_or_create(
        content_type=ct, object_id=str(obj.pk), defaults={"ultimo_erro": str(exc)[:_LIMITE_ERRO]}
    )
    if not criada:
        pendencia.tentativas += 1
        pendencia.ultimo_erro = str(exc)[:_LIMITE_ERRO]
        pendencia.save(update_fields=["tentativas", "ultimo_erro", "atualizado_em"])


def registrar_sucesso(obj) -> None:
    from django.contrib.contenttypes.models import ContentType

    from .models import DriveSyncStatus

    ct = ContentType.objects.get_for_model(obj.__class__)
    DriveSyncStatus.objects.filter(content_type=ct, object_id=str(obj.pk)).delete()


def executar_e_rastrear(fn, obj) -> None:
    """Roda ``fn(obj)``; registra sucesso/falha em ``DriveSyncStatus``.

    Repropaga a exceção em caso de falha para permitir que quem chamou decida
    o que fazer (ex.: Celery aplicar retry automático).
    """
    try:
        fn(obj)
    except Exception as exc:
        registrar_falha(obj, exc)
        raise
    else:
        registrar_sucesso(obj)


def contagem_pendencias() -> int:
    from .models import DriveSyncStatus

    return DriveSyncStatus.objects.count()


def listar_pendencias(limite: int = 20):
    from .models import DriveSyncStatus

    return list(
        DriveSyncStatus.objects.select_related("content_type").order_by("-atualizado_em")[:limite]
    )
