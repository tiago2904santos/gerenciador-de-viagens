from __future__ import annotations

import datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from core.errors import capture
from core.middleware import get_current_request

AUDITED_APP_LABELS = {
    "cadastros",
    "roteiros",
    "eventos",
    "documentos",
    "oficios",
    "termos",
    "justificativas",
    "planos_trabalho",
    "ordens_servico",
    "prestacoes_contas",
    "google_drive",
}
SENSITIVE_NAMES = {
    "password",
    "access_token",
    "refresh_token",
    "link_token",
    "client_secret",
    "assinatura_png",
}


def _audited(sender) -> bool:
    return (
        sender._meta.app_label in AUDITED_APP_LABELS
        and sender._meta.label_lower != "core.auditevent"
        and not _historico_de_migracao(sender)
    )


def _historico_de_migracao(sender) -> bool:
    """Identifica os modelos históricos que as migrações de dados usam.

    ``apps.get_model()`` dentro de uma migração devolve uma classe recriada no
    módulo ``__fake__``. Sem esta guarda, toda migração de dados escreve na
    trilha de auditoria eventos sem ator e sem requisição — descrevendo o
    deploy, não uma ação de usuário.
    """
    return sender.__module__ == "__fake__"


def _json_value(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if hasattr(value, "name"):
        return value.name
    if hasattr(value, "pk"):
        return value.pk
    return str(value)


def _repr_seguro(instance) -> str:
    """Rótulo do objeto para a trilha, tolerante a `__str__` mal-comportado (BE-07).

    Os sinais estão conectados globalmente a 11 apps, então esta função roda para
    todo modelo auditado — e um `__str__` que devolve `None` fazia o próprio
    `str()` levantar `TypeError`, derrubando a operação que a auditoria só deveria
    observar. Foi o que acontecia ao excluir anexo de prestação com
    `nome_original` vazio: 500, e a linha ficava órfã no banco.

    Perder o rótulo legível é aceitável; perder o rastro do objeto não — daí o
    fallback carregar o rótulo do modelo e a pk.
    """
    try:
        rotulo = str(instance)
    except Exception as exc:
        capture(
            exc,
            "core.audit.instance_label",
            model=instance._meta.label,
            object_id=instance.pk,
        )
        rotulo = None
    if isinstance(rotulo, str) and rotulo:
        return rotulo[:255]
    return f"{instance._meta.label}#{instance.pk}"[:255]


def _snapshot(instance):
    values = {}
    for field in instance._meta.concrete_fields:
        if field.name in SENSITIVE_NAMES:
            continue
        try:
            values[field.name] = _json_value(field.value_from_object(instance))
        except Exception as exc:
            capture(
                exc,
                "core.audit.snapshot_instance",
                model=instance._meta.label,
                field=field.name,
            )
            continue
    return values


def capture_before_save(sender, instance, raw=False, **kwargs):
    if raw or not _audited(sender) or not instance.pk:
        return
    old = sender._default_manager.filter(pk=instance.pk).first()
    instance._audit_old = _snapshot(old) if old is not None else {}


def _context(instance):
    request = get_current_request()
    user = getattr(request, "user", None)
    actor_id = user.pk if user and user.is_authenticated else None
    area_id = getattr(instance, "area_id", None) or getattr(
        getattr(request, "area", None),
        "pk",
        None,
    )
    return {
        "actor_id": actor_id,
        "area_id": area_id,
        "request_path": getattr(request, "path", "")[:500],
        "request_id": getattr(request, "request_id", ""),
    }


def _write_event(payload):
    from core.models import AuditEvent

    AuditEvent.objects.create(**payload)


def capture_after_save(sender, instance, created=False, raw=False, **kwargs):
    if raw or not _audited(sender):
        return
    new = _snapshot(instance)
    old = getattr(instance, "_audit_old", {})
    if created:
        changes = {"new": new}
        action = "CREATE"
    else:
        delta = {
            name: {"old": old.get(name), "new": value}
            for name, value in new.items()
            if old.get(name) != value
        }
        if not delta:
            return
        changes = delta
        action = "UPDATE"
    payload = {
        **_context(instance),
        "action": action,
        "model_label": instance._meta.label,
        "object_id": str(instance.pk),
        "object_repr": _repr_seguro(instance),
        "changes": changes,
    }
    transaction.on_commit(lambda payload=payload: _write_event(payload))


def capture_before_delete(sender, instance, **kwargs):
    if not _audited(sender):
        return
    payload = {
        **_context(instance),
        "action": "DELETE",
        "model_label": instance._meta.label,
        "object_id": str(instance.pk),
        "object_repr": _repr_seguro(instance),
        "changes": {"old": _snapshot(instance)},
    }
    transaction.on_commit(lambda payload=payload: _write_event(payload))


def connect_audit_signals():
    from django.db.models.signals import post_save
    from django.db.models.signals import pre_delete
    from django.db.models.signals import pre_save

    pre_save.connect(capture_before_save, dispatch_uid="core.audit.pre_save")
    post_save.connect(capture_after_save, dispatch_uid="core.audit.post_save")
    pre_delete.connect(capture_before_delete, dispatch_uid="core.audit.pre_delete")
