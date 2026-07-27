from __future__ import annotations

AREA_SESSION_KEY = "area_trabalho_id"


def get_area_from_request(request):
    return getattr(request, "area", None)


def get_current_area():
    from core.middleware import get_current_request

    request = get_current_request()
    if request is None:
        return None
    return get_area_from_request(request)


def resolve_area_for_request(request):
    """Resolve a area ativa do usuario autenticado sem bloquear fluxos antigos."""

    request.area = None
    request.vinculo_area = None

    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return None

    from usuarios.models import VinculoUsuarioArea

    vinculos = (
        VinculoUsuarioArea.objects.select_related("area")
        .filter(usuario=user, ativo=True, area__ativa=True)
        .order_by("-area_padrao", "area__sigla")
    )

    session_area_id = request.session.get(AREA_SESSION_KEY)
    if session_area_id:
        vinculo = vinculos.filter(area_id=session_area_id).first()
        if vinculo:
            request.area = vinculo.area
            request.vinculo_area = vinculo
            return vinculo.area
        request.session.pop(AREA_SESSION_KEY, None)

    vinculo = vinculos.first()
    if not vinculo:
        return None

    request.area = vinculo.area
    request.vinculo_area = vinculo
    request.session[AREA_SESSION_KEY] = vinculo.area_id
    return vinculo.area


def filter_queryset_by_area(queryset, area=None):
    """Aplica isolamento estrito pela área de trabalho resolvida.

    Registros legados sem área devem ser tratados pelo comando explícito de
    saneamento; eles nunca são compartilhados implicitamente entre áreas.
    """
    area = get_current_area() if area is None else area
    if area is None:
        return queryset.filter(area__isnull=True)
    return queryset.filter(area=area)


def validate_cross_area_foreign_keys(sender, instance, raw=False, **kwargs):
    if raw or not hasattr(instance, "area_id") or instance.area_id is None:
        return
    from django.core.exceptions import ValidationError

    for field in instance._meta.concrete_fields:
        if not field.is_relation or not field.many_to_one or not field.name:
            continue
        try:
            related = getattr(instance, field.name, None)
        except Exception:
            continue
        related_area_id = getattr(related, "area_id", None)
        if related_area_id is not None and related_area_id != instance.area_id:
            raise ValidationError(
                {
                    field.name: (
                        f"{field.verbose_name} pertence a outra área de trabalho."
                    ),
                },
            )


def validate_cross_area_many_to_many(
    sender,
    instance,
    action,
    reverse,
    model,
    pk_set,
    **kwargs,
):
    if action != "pre_add" or not pk_set:
        return
    instance_area_id = getattr(instance, "area_id", None)
    if instance_area_id is None:
        return
    try:
        model._meta.get_field("area")
    except Exception:
        return
    if model._default_manager.filter(pk__in=pk_set).exclude(area_id=instance_area_id).exists():
        from django.core.exceptions import ValidationError

        raise ValidationError("Não é permitido relacionar registros de áreas diferentes.")


def connect_area_integrity_signals():
    from django.db.models.signals import m2m_changed
    from django.db.models.signals import pre_save

    pre_save.connect(
        validate_cross_area_foreign_keys,
        dispatch_uid="core.tenancy.validate_fk",
    )
    m2m_changed.connect(
        validate_cross_area_many_to_many,
        dispatch_uid="core.tenancy.validate_m2m",
    )
