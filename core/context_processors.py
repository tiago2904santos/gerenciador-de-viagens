from django.conf import settings

from usuarios.models import VinculoUsuarioArea

from core.permissions import has_area_role
from .navigation import build_navigation


def navigation(request):
    cached = getattr(request, "_cv_navigation_context", None)
    if cached is None:
        # django-cotton cria um contexto por componente e volta a executar os
        # processadores. A navegação depende apenas desta requisição: montá-la
        # uma vez evita dezenas de reverse() por página sem cache entre usuários.
        cached = {"navigation_items": build_navigation(request)}
        request._cv_navigation_context = cached
    return cached


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
        return {"can_edit_area": open_edit}
    return {
        "can_edit_area": has_area_role(request, VinculoUsuarioArea.PAPEL_EDITOR),
    }
