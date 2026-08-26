from django.conf import settings

from usuarios.models import VinculoUsuarioArea

from core.permissions import has_area_role
from .navigation import build_navigation


SHELL_CSS_PROFILE_BY_VIEW = {
    # NOVO-70: o login não tem shell (não estende base.html), mas tem perfil de
    # componentes — por isso entra aqui e é filtrado em shell_css_profile().
    "core:login": "login",
    "core:dashboard": "dashboard",
    "oficios:index": "entity-lists",
    "roteiros:index": "entity-lists",
    "prestacoes_contas:index": "entity-lists",
    "termos:index": "entity-lists",
    "planos_trabalho:index": "entity-lists",
    "ordens_servico:index": "entity-lists",
    "eventos:index": "eventos-list",
    "justificativas:index": "justificativas-list",
    "oficios:modelos_motivo_index": "catalog-lists",
    "cadastros:servidores_index": "catalog-lists",
    "cadastros:viaturas_index": "catalog-lists",
    "cadastros:unidades_index": "catalog-lists",
    "cadastros:cargos_index": "catalog-lists",
    "cadastros:combustiveis_index": "catalog-lists",
    "oficios:novo": "oficio-new",
    "termos:preview_termo_oficio": "termo-preview",
    "oficios:modelo_motivo_create": "model-forms",
    "oficios:modelo_motivo_update": "model-forms",
    "justificativas:legacy_modelo_create": "model-forms",
    "justificativas:legacy_modelo_update": "model-forms",
    "justificativas:modelos_index": "model-forms",
    "justificativas:modelo_create": "model-forms",
    "justificativas:modelo_update": "model-forms",
    "cadastros:unidade_create": "model-forms",
    "cadastros:unidade_update": "model-forms",
    "cadastros:cargo_create": "model-forms",
    "cadastros:cargo_update": "model-forms",
    "cadastros:combustivel_create": "model-forms",
    "cadastros:combustivel_update": "model-forms",
    "oficios:detalhe": "oficio-core",
    "oficios:editar": "oficio-core",
    "oficios:dados_viajantes": "oficio-core",
    "oficios:transporte": "oficio-transport",
    "oficios:wizard_roteiro": "oficio-route",
    "oficios:wizard_justificativa": "oficio-justification",
    "oficios:wizard_resumo": "oficio-documents",
    "oficios:wizard_documentos": "oficio-documents",
    "roteiros:novo": "roteiro-form",
    "roteiros:editar": "roteiro-form",
    "cadastros:configuracao": "admin-form",
    "cadastros:servidor_create": "admin-form",
    "cadastros:servidor_update": "admin-form",
    "cadastros:viatura_create": "admin-form",
    "cadastros:viatura_update": "admin-form",
}


# NOVO-70: o login é a única rota sem casca. `build_css_profiles.py` não gera
# `login.css` para ela; só `login.ui.css`. Sem esta lista, o `base.html` pediria
# um arquivo que não existe.
PERFIS_SEM_SHELL = frozenset({"login"})


def shell_css_profile(request):
    if not settings.CSS_ROUTE_PROFILES_ENABLED:
        return {"shell_css_profile_path": None, "ui_css_profile_path": None}
    match = getattr(request, "resolver_match", None)
    profile = SHELL_CSS_PROFILE_BY_VIEW.get(getattr(match, "view_name", None))
    if not profile:
        return {"shell_css_profile_path": None, "ui_css_profile_path": None}
    tem_shell = profile not in PERFIS_SEM_SHELL
    return {
        "shell_css_profile_path": f"css/profiles/{profile}.css" if tem_shell else None,
        # NOVO-70: o par do shell. O `ui.bundle.css` inteiro entregava 552 KB em
        # toda rota a 9% de uso; o perfil poda pelas classes que a família usa.
        "ui_css_profile_path": f"css/profiles/{profile}.ui.css",
    }


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
