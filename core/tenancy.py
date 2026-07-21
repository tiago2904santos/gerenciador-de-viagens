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
    """Aplica isolamento por area quando ha area atual resolvida.

    Registros legados com ``area`` nula continuam visíveis para a área ativa.
    Sem isso, cadastros/documentos criados antes do multi-tenant somem das
    listagens e quebram fluxos (ex.: novo ofício no evento, anexar termo).
    """
    from django.db.models import Q

    area = get_current_area() if area is None else area
    if area is None:
        return queryset.filter(area__isnull=True)
    return queryset.filter(Q(area=area) | Q(area__isnull=True))
