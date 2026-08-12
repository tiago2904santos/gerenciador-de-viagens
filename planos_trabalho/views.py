"""Fachada pública das views de Planos de Trabalho (P-06)."""

from .activity_views import atividades_autosave, wizard_atividades
from .card_menu_views import card_menus
from .catalogs import (
    atividade_editar,
    atividade_excluir,
    atividades_index,
    horario_editar,
    horario_excluir,
    horarios_index,
    preset_definir_padrao,
    preset_editar,
    preset_excluir,
    presets_index,
    programa_editar,
    programa_excluir,
    programas_index,
)
from .document_views import baixar_documento, pdf_inline, wizard_documentos
from .identification_views import identificacao_autosave, wizard_identificacao
from .list_views import editar, excluir, index, novo
from .per_diem_views import (
    api_calcular_diarias,
    efetivo_diarias_autosave,
    evento_adicionar,
    evento_editar,
    evento_remover,
    wizard_efetivo_diarias,
)
from .view_helpers import (
    _autosave_form_errors,
    _evento_etapa_url,
    _get_plano,
    _merge_payload_fields,
    _plano_autosave_version,
    _plano_lista_label,
    _plano_lista_url,
    _querydict_from_pairs,
    _redirect_plano_lista,
    _wizard_shell_ctx,
    _wizard_steps_ctx,
)

# QA-07 — a superfície pública da fachada, escrita.
#
# `urls.py` referencia tudo como `views.<nome>`; os nomes vêm dos módulos
# irmãos. Sem `__all__`, cada re-export era indistinguível de import morto
# para o ruff (`F401`) — e para quem lê. Com ele, `F401` volta a significar
# o que deve: import que ninguém usa.
__all__ = [
    "_autosave_form_errors",
    "_evento_etapa_url",
    "_get_plano",
    "_merge_payload_fields",
    "_plano_autosave_version",
    "_plano_lista_label",
    "_plano_lista_url",
    "_querydict_from_pairs",
    "_redirect_plano_lista",
    "_wizard_shell_ctx",
    "_wizard_steps_ctx",
    "api_calcular_diarias",
    "atividade_editar",
    "atividade_excluir",
    "atividades_autosave",
    "atividades_index",
    "card_menus",
    "baixar_documento",
    "editar",
    "efetivo_diarias_autosave",
    "evento_adicionar",
    "evento_editar",
    "evento_remover",
    "excluir",
    "horario_editar",
    "horario_excluir",
    "horarios_index",
    "identificacao_autosave",
    "index",
    "novo",
    "pdf_inline",
    "preset_definir_padrao",
    "preset_editar",
    "preset_excluir",
    "presets_index",
    "programa_editar",
    "programa_excluir",
    "programas_index",
    "wizard_atividades",
    "wizard_documentos",
    "wizard_efetivo_diarias",
    "wizard_identificacao",
]
