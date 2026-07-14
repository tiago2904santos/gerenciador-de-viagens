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


def listar_pendencias_detalhadas(limite: int = 20):
    """Pendências prontas para exibição: nome legível + motivo em linguagem simples.

    Cada item é um dict com: ``titulo`` (nome do documento), ``tipo_label``
    (categoria), ``contexto`` (ofício/evento de origem), ``tentativas``,
    ``atualizado_em``, ``motivo``/``acao`` (explicação amigável) e ``detalhe``
    (erro técnico cru, para o expansível).
    """
    itens = []
    for pendencia in listar_pendencias(limite=limite):
        origem = pendencia.origem  # resolve o GenericForeignKey (1 query por item)
        motivo, acao = _motivo_amigavel(pendencia.ultimo_erro)
        itens.append(
            {
                "titulo": _titulo_pendencia(origem, pendencia.content_type),
                "tipo_label": _tipo_label(pendencia.content_type),
                "contexto": _contexto_pendencia(origem),
                "tentativas": pendencia.tentativas,
                "atualizado_em": pendencia.atualizado_em,
                "motivo": motivo,
                "acao": acao,
                "detalhe": (pendencia.ultimo_erro or "").strip(),
            }
        )
    return itens
