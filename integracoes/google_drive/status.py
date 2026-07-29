"""Rastreamento de pendências de sincronização com o Drive.

Uma linha em ``DriveSyncStatus`` só existe enquanto o objeto de origem
(``DocumentoArtefato``, ``PrestacaoContas``, ``EventoAnexo``,
``EventoDocumentoSolicitacao``) estiver com a última tentativa de envio
malsucedida. Isso alimenta o retry em segundo plano (Celery, ver ``tasks.py``)
e o painel de pendências da tela de configuração (ver ``views.py``).
"""

from __future__ import annotations

from core.errors import capture

_LIMITE_ERRO = 2000  # trunca mensagens de exceção muito longas antes de persistir.


_UNSET = object()


def _resolve_usuario(usuario=None):
    if usuario is not None:
        return usuario
    try:
        from core.middleware import get_current_request

        request = get_current_request()
        user = getattr(request, "user", None) if request is not None else None
        if user is not None and getattr(user, "is_authenticated", False):
            return user
    except Exception as exc:
        capture(exc, "drive.status._resolve_usuario")  # pragma: no cover
        pass
    try:
        from .organizer import get_usuario_contexto

        return get_usuario_contexto()
    except Exception as exc:
        capture(exc, "drive.status._resolve_usuario")  # pragma: no cover
        return None


def _resolve_area(area=_UNSET):
    if area is not _UNSET:
        return area
    try:
        from core.tenancy import get_current_area

        return get_current_area()
    except Exception as exc:
        capture(exc, "drive.status._resolve_area")  # pragma: no cover
        return None


def _area_origem(origem):
    if origem is None:
        return None
    area = getattr(origem, "area", None)
    if area is not None:
        return area
    oficio = getattr(origem, "oficio", None)
    if oficio is not None:
        return getattr(oficio, "area", None)
    evento = getattr(origem, "evento", None)
    if evento is not None:
        return getattr(evento, "area", None)
    prestacao = getattr(origem, "prestacao", None)
    if prestacao is not None:
        return getattr(prestacao, "area", None)
    return None


def _mesma_area(origem, area) -> bool:
    origem_area = _area_origem(origem)
    origem_area_id = getattr(origem_area, "pk", origem_area)
    area_id = getattr(area, "pk", area)
    return origem_area_id == area_id


def registrar_falha(obj, exc: Exception, usuario=None) -> None:
    from django.contrib.contenttypes.models import ContentType

    from .models import DriveSyncStatus

    ct = ContentType.objects.get_for_model(obj.__class__)
    pendencia, criada = DriveSyncStatus.objects.get_or_create(
        content_type=ct,
        object_id=str(obj.pk),
        defaults={
            "usuario": _resolve_usuario(usuario),
            "ultimo_erro": str(exc)[:_LIMITE_ERRO],
        },
    )
    if not criada:
        usuario = _resolve_usuario(usuario)
        if usuario is not None:
            pendencia.usuario = usuario
        pendencia.tentativas += 1
        pendencia.ultimo_erro = str(exc)[:_LIMITE_ERRO]
        pendencia.save(update_fields=["usuario", "tentativas", "ultimo_erro", "atualizado_em"])


def registrar_sucesso(obj) -> None:
    from django.contrib.contenttypes.models import ContentType

    from .models import DriveSyncStatus

    ct = ContentType.objects.get_for_model(obj.__class__)
    DriveSyncStatus.objects.filter(content_type=ct, object_id=str(obj.pk)).delete()


def limpar_pendencia_orfa(model_cls, object_id) -> None:
    """Remove a pendência de um objeto de origem que não existe mais.

    As tasks de retry (``tasks.py``) buscam o objeto pelo id antes de
    reenviar; se ele foi excluído do sistema, não há mais o que sincronizar
    — sem isso a pendência ficava "zumbi", nunca resolvida por nenhum retry.
    """
    from django.contrib.contenttypes.models import ContentType

    from .models import DriveSyncStatus

    ct = ContentType.objects.get_for_model(model_cls)
    DriveSyncStatus.objects.filter(content_type=ct, object_id=str(object_id)).delete()


def executar_e_rastrear(fn, obj, usuario=None) -> None:
    """Roda ``fn(obj)``; registra sucesso/falha em ``DriveSyncStatus``.

    Repropaga a exceção em caso de falha para permitir que quem chamou decida
    o que fazer (ex.: Celery aplicar retry automático).
    """
    try:
        fn(obj)
    except Exception as exc:
        capture(exc, "drive.status.executar_e_rastrear")  # pragma: no cover
        registrar_falha(obj, exc, usuario=usuario)
        raise
    else:
        registrar_sucesso(obj)


def _pendencias_queryset(usuario=_UNSET):
    from .models import DriveSyncStatus

    qs = (
        DriveSyncStatus.objects
        .select_related("content_type", "usuario")
        .prefetch_related("origem")
        .order_by("-atualizado_em")
    )
    if usuario is not _UNSET:
        qs = qs.filter(usuario=usuario)
    return qs


def _filtrar_pendencias(qs, area=_UNSET, limite: int | None = None):
    area = _resolve_area(area)
    itens = []
    for pendencia in qs:
        if _mesma_area(pendencia.origem, area):
            itens.append(pendencia)
            if limite is not None and len(itens) >= limite:
                break
    return itens


def contagem_pendencias(usuario=_UNSET, area=_UNSET) -> int:
    return len(_filtrar_pendencias(_pendencias_queryset(usuario=usuario), area=area, limite=None))


def listar_pendencias(limite: int = 20, usuario=_UNSET, area=_UNSET):
    return _filtrar_pendencias(_pendencias_queryset(usuario=usuario), area=area, limite=limite)


# Rótulo amigável por modelo de origem (fallback: verbose_name do ContentType).
_TIPO_LABELS = {
    "documentoartefato": "Documento",
    "prestacaocontas": "Prestação de contas",
    "eventoanexo": "Anexo do evento",
    "eventodocumentosolicitacao": "Documento de solicitação",
    "oficio": "Ofício",
    "evento": "Evento",
}

# (palavras-chave no erro cru) → (motivo em linguagem simples, ação sugerida).
_MOTIVOS = (
    (
        ("pasta raiz", "pasta de destino", "root folder", "sem pasta"),
        "Nenhuma pasta de destino configurada no Drive.",
        "Escolha a pasta no bloco “Diretório de destino”, acima.",
    ),
    (
        ("invalid_scope", "escopo", "scope", "permiss"),
        "A autorização não tem todas as permissões necessárias.",
        "Use “Trocar conta” para reautorizar com as permissões pedidas.",
    ),
    (
        ("credencial", "credential", "token", "unauthor", "desconect", "não conectad"),
        "Conta Google desconectada ou sem autorização válida.",
        "Reconecte a conta no bloco “Conta Google”, acima.",
    ),
    (
        ("quota", "rate limit", "ratelimit", "too many", "userratelimit"),
        "Limite temporário da API do Google foi atingido.",
        "Aguarde alguns minutos — o reenvio é automático.",
    ),
    (
        ("has no attribute", "traceback", "nonetype", "keyerror", "typeerror", "attributeerror"),
        "Erro interno ao preparar o arquivo para envio.",
        "A falha foi registrada; tente de novo ou avise o suporte se persistir.",
    ),
    (
        ("timeout", "timed out", "connection", "network", "temporarily"),
        "Falha de conexão com o Google ao enviar.",
        "Normalmente passa sozinho — o reenvio é automático.",
    ),
)


def _tipo_label(content_type) -> str:
    return _TIPO_LABELS.get(content_type.model, (content_type.name or "Documento").capitalize())


def _titulo_pendencia(origem, content_type) -> str:
    """Nome legível do documento por trás da pendência (evita 'Artefato #uuid')."""
    if origem is None:
        return f"{_tipo_label(content_type)} removido do sistema"
    # DocumentoArtefato guarda um nome 'bonito' calculado na geração.
    nome_drive = (getattr(origem, "nome_drive", "") or "").strip()
    if nome_drive:
        return nome_drive
    # Fallback do DocumentoArtefato: o __str__ inclui o hash (ruído). Monta um
    # rótulo limpo a partir do tipo/formato quando disponível.
    tipo = getattr(origem, "tipo", "")
    if tipo and hasattr(origem, "formato"):
        rotulo = tipo.replace("_", " ").strip().capitalize()
        formato = (getattr(origem, "formato", "") or "").upper()
        return f"{rotulo} ({formato})" if formato else rotulo
    texto = str(origem).strip()
    return texto or _tipo_label(content_type)


def _contexto_pendencia(origem) -> str:
    """Linha de contexto: a qual ofício/evento o documento pertence."""
    if origem is None:
        return ""
    oficio = getattr(origem, "oficio", None)
    if oficio is not None:
        numero = getattr(oficio, "numero", None) or oficio.pk
        return f"Ofício nº {numero}"
    evento = getattr(origem, "evento", None)
    if evento is not None:
        return str(evento)
    return ""


def _motivo_amigavel(erro: str):
    texto = (erro or "").lower()
    for chaves, motivo, acao in _MOTIVOS:
        if any(chave in texto for chave in chaves):
            return motivo, acao
    return (
        "Falha temporária ao enviar para o Drive.",
        "O sistema tenta reenviar sozinho em segundo plano.",
    )


def listar_pendencias_detalhadas(limite: int = 20, usuario=_UNSET, area=_UNSET):
    """Pendências prontas para exibição: nome legível + motivo em linguagem simples.

    Cada item é um dict com: ``titulo`` (nome do documento), ``tipo_label``
    (categoria), ``contexto`` (ofício/evento de origem), ``tentativas``,
    ``atualizado_em``, ``motivo``/``acao`` (explicação amigável) e ``detalhe``
    (erro técnico cru, para o expansível).
    """
    return [
        _detalhar_pendencia(pendencia)
        for pendencia in listar_pendencias(limite=limite, usuario=usuario, area=area)
    ]


def _detalhar_pendencia(pendencia):
    origem = pendencia.origem
    motivo, acao = _motivo_amigavel(pendencia.ultimo_erro)
    return {
        "titulo": _titulo_pendencia(origem, pendencia.content_type),
        "tipo_label": _tipo_label(pendencia.content_type),
        "contexto": _contexto_pendencia(origem),
        "tentativas": pendencia.tentativas,
        "atualizado_em": pendencia.atualizado_em,
        "motivo": motivo,
        "acao": acao,
        "detalhe": (pendencia.ultimo_erro or "").strip(),
    }


def resumo_pendencias(limite: int = 20, usuario=_UNSET, area=_UNSET):
    """Carrega uma vez, agrupa GenericFK por tipo e devolve total + detalhes."""
    pendencias = _filtrar_pendencias(
        _pendencias_queryset(usuario=usuario),
        area=area,
        limite=None,
    )
    return {
        "total": len(pendencias),
        "itens": [_detalhar_pendencia(item) for item in pendencias[:limite]],
    }
