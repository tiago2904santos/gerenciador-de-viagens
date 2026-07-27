from copy import deepcopy

from django.conf import settings
from django.urls import NoReverseMatch
from django.urls import reverse


NAVIGATION_ITEMS = [
    {"id": "dashboard", "label": "Dashboard", "url_name": "core:dashboard", "icon": "DG"},
    {
        "id": "planejamento",
        "label": "Planejamento",
        "icon": "PL",
        "active_when": ["eventos:", "roteiros:", "planos_trabalho:", "ordens_servico:"],
        "children": [
            {"id": "eventos", "label": "Eventos", "url_name": "eventos:index", "active_when": ["eventos:"]},
            {"id": "roteiros", "label": "Roteiros", "url_name": "roteiros:index", "active_when": ["roteiros:"]},
            {"id": "planos", "label": "Planos de Trabalho", "url_name": "planos_trabalho:index", "active_when": ["planos_trabalho:"]},
            {"id": "ordens", "label": "Ordens de Serviço", "url_name": "ordens_servico:index", "active_when": ["ordens_servico:"]},
        ],
    },
    {
        "id": "documentos-operacionais",
        "label": "Documentos",
        "icon": "DC",
        "active_when": ["oficios:", "termos:", "justificativas:"],
        "children": [
            {"id": "oficios", "label": "Ofícios", "url_name": "oficios:index", "active_when": ["oficios:"]},
            {"id": "termos", "label": "Termos", "url_name": "termos:index", "active_when": ["termos:"]},
            {"id": "justificativas", "label": "Justificativas", "url_name": "justificativas:index", "active_when": ["justificativas:"]},
        ],
    },
    {
        "id": "execucao",
        "label": "Execução e prestação",
        "icon": "EX",
        "active_when": ["prestacoes_contas:"],
        "children": [
            {
                "id": "prestacoes",
                "label": "Prestações de Contas",
                "url_name": "prestacoes_contas:index",
                "active_when": ["prestacoes_contas:"],
            },
        ],
    },
    {
        "id": "administracao",
        "label": "Administração",
        "icon": "AD",
        "active_when": ["cadastros:", "usuarios:"],
        "children": [
            {"id": "servidores", "label": "Servidores", "url_name": "cadastros:servidores_index", "active_when": ["cadastros:servidor_", "cadastros:servidores_index"]},
            {"id": "cargos", "label": "Cargos", "url_name": "cadastros:cargos_index", "active_when": ["cadastros:cargo_", "cadastros:cargos_index"]},
            {"id": "viaturas", "label": "Viaturas", "url_name": "cadastros:viaturas_index", "active_when": ["cadastros:viatura_", "cadastros:viaturas_index"]},
            {"id": "combustiveis", "label": "Combustíveis", "url_name": "cadastros:combustiveis_index", "active_when": ["cadastros:combustivel_", "cadastros:combustiveis_index"]},
            {"id": "unidades", "label": "Unidades", "url_name": "cadastros:unidades_index", "active_when": ["cadastros:unidade_", "cadastros:unidades_index"]},
            {"id": "configuracao", "label": "Configurações", "url_name": "cadastros:configuracao", "active_when": ["cadastros:configuracao"]},
            {
                "id": "usuarios",
                "label": "Usuários e áreas",
                "url_name": "usuarios:index",
                "active_when": ["usuarios:"],
                "staff_only": True,
            },
        ],
    },
]

if settings.DEBUG:
    NAVIGATION_ITEMS.append(
        {
            "id": "ui-lab",
            "label": "UI Lab",
            "url_name": "core:ui_lab",
            "icon": "DV",
            "active_when": ["core:ui_lab"],
        }
    )


def build_navigation(request):
    current_view_name = ""
    if request.resolver_match:
        current_view_name = request.resolver_match.view_name or ""
    return [
        _build_item(item, current_view_name, request)
        for item in NAVIGATION_ITEMS
        if _is_visible_for_request(item, request)
    ]


def _build_item(item, current_view_name, request):
    built_item = deepcopy(item)
    built_item["url"] = _resolve_url(built_item.get("url_name"))
    children = [
        _build_item(child, current_view_name, request)
        for child in built_item.get("children", [])
        if _is_visible_for_request(child, request)
    ]
    built_item["children"] = children
    is_active = _matches_current_view(built_item, current_view_name)
    has_active_child = any(child["is_active"] or child["is_open"] for child in children)
    built_item["is_current"] = is_active
    built_item["is_active"] = is_active or has_active_child
    built_item["is_open"] = has_active_child
    built_item["has_children"] = bool(children)
    built_item["children_id"] = f"sidebar-children-{built_item['id']}"
    return built_item


def _resolve_url(url_name):
    if not url_name:
        return None
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return None


def _matches_current_view(item, current_view_name):
    url_name = item.get("url_name")
    if url_name and current_view_name == url_name:
        return True
    return any(current_view_name.startswith(prefix) for prefix in item.get("active_when", []))


def _is_visible_for_request(item, request):
    user = getattr(request, "user", None)
    if item.get("auth_only") and not (user and user.is_authenticated):
        return False
    if not item.get("staff_only"):
        return True
    return bool(user and user.is_authenticated and (user.is_staff or user.is_superuser))
