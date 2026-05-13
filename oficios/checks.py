"""Checagens do Django para garantir que o URLconf do wizard de ofício está íntegro."""

from __future__ import annotations

from django.core.checks import Error, Tags, register
from django.urls import NoReverseMatch, reverse

_WIZARD_ROUTE_TESTS = (
    ("oficios:wizard_justificativa", [1]),
    ("oficios:wizard_documentos", [1]),
    ("oficios:wizard_assinaturas", [1]),
    ("oficios:wizard_resumo", [1]),
)


@register(Tags.urls)
def check_oficios_wizard_rotas(app_configs, **kwargs):
    """Falha em `manage.py check` se rotas do wizard não estiverem registradas."""
    errors = []
    for name, args in _WIZARD_ROUTE_TESTS:
        try:
            reverse(name, args=args)
        except NoReverseMatch as exc:
            errors.append(
                Error(
                    f"Rota '{name}' não resolve ({exc}).",
                    hint=(
                        "Confira oficios/urls.py e se o runserver foi iniciado a partir da "
                        "raiz do projeto (onde está este repositório)."
                    ),
                    id="oficios.urls.E001",
                ),
            )
    return errors
