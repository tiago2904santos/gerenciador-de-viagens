from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.core.exceptions import PermissionDenied

from usuarios.models import VinculoUsuarioArea

ROLE_ORDER = {
    VinculoUsuarioArea.PAPEL_LEITOR: 10,
    VinculoUsuarioArea.PAPEL_EDITOR: 20,
    VinculoUsuarioArea.PAPEL_ADMIN: 30,
}


def has_area_role(request, minimum_role: str) -> bool:
    vinculo = getattr(request, "vinculo_area", None)
    if getattr(request.user, "is_superuser", False):
        return True
    if vinculo is None:
        return not getattr(settings, "AREA_RBAC_REQUIRE_MEMBERSHIP", True)
    if not vinculo.ativo:
        return False
    return ROLE_ORDER.get(vinculo.papel, 0) >= ROLE_ORDER[minimum_role]


def require_area_role(minimum_role: str):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not has_area_role(request, minimum_role):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
