from django.conf import settings

from usuarios.models import VinculoUsuarioArea

from core.permissions import has_area_role
from .navigation import build_navigation


def navigation(request):
    return {
        "navigation_items": build_navigation(request),
    }


def _login_enforced() -> bool:
    return any(
        m.endswith("AjaxAwareLoginRequiredMiddleware")
        or m.endswith("LoginRequiredMiddleware")
        for m in settings.MIDDLEWARE
    )


def area_permissions(request):
    if not getattr(getattr(request, "user", None), "is_authenticated", False):
        # Com LOGIN_ENFORCED=false (dev), a UI de edição precisa aparecer —
        # senão o Quick Add some enquanto o POST ainda é aceito.
        open_edit = not _login_enforced()
        return {"can_edit_area": open_edit, "can_admin_area": open_edit}
    return {
        "can_edit_area": has_area_role(request, VinculoUsuarioArea.PAPEL_EDITOR),
        "can_admin_area": has_area_role(request, VinculoUsuarioArea.PAPEL_ADMIN),
    }
