from usuarios.models import VinculoUsuarioArea

from core.permissions import has_area_role
from .navigation import build_navigation


def navigation(request):
    return {
        "navigation_items": build_navigation(request),
    }


def area_permissions(request):
    if not getattr(getattr(request, "user", None), "is_authenticated", False):
        return {"can_edit_area": False, "can_admin_area": False}
    return {
        "can_edit_area": has_area_role(request, VinculoUsuarioArea.PAPEL_EDITOR),
        "can_admin_area": has_area_role(request, VinculoUsuarioArea.PAPEL_ADMIN),
    }
