"""Fachada pública das views de Ofícios (P-06)."""

from .api_views import api_viatura_por_placa
from .card_menu_views import card_menus
from .catalogs import (
    modelo_motivo_definir_padrao,
    modelo_motivo_editar,
    modelo_motivo_excluir,
    modelos_motivo_index,
)
from .document_views import (
    baixar_documento,
    baixar_justificativa_documento,
    baixar_ordem_servico_documento,
    justificativa_pdf_inline,
    oficio_pdf_inline,
    ordem_servico_pdf_inline,
)
from .lifecycle_views import cancelar, excluir, marcar_complementar, retificar
from .list_views import OFICIOS_POR_PAGINA, detalhe, editar, index, novo
from .route_views import (
    _resolver_roteiro_rascunho_autosave,
    wizard_roteiro,
    wizard_roteiro_autosave_criar,
)
from .services import validar_oficio_para_documento
from .traveler_views import (
    dados_viajantes,
    dados_viajantes_autosave,
    transporte,
    transporte_autosave,
)
from .view_helpers import _wizard_normalizar_acao
from .wizard_document_views import (
    justificativa_autosave,
    wizard_documentos,
    wizard_justificativa,
    wizard_resumo,
)

# QA-07 — a superfície pública da fachada, escrita. Ver o mesmo bloco em
# `planos_trabalho/views.py`: sem `__all__`, re-export e import morto são a
# mesma coisa aos olhos do `F401`.
__all__ = [
    "OFICIOS_POR_PAGINA",
    "_resolver_roteiro_rascunho_autosave",
    "_wizard_normalizar_acao",
    "api_viatura_por_placa",
    "baixar_documento",
    "baixar_justificativa_documento",
    "baixar_ordem_servico_documento",
    "cancelar",
    "card_menus",
    "dados_viajantes",
    "dados_viajantes_autosave",
    "detalhe",
    "editar",
    "excluir",
    "index",
    "justificativa_autosave",
    "justificativa_pdf_inline",
    "marcar_complementar",
    "modelo_motivo_definir_padrao",
    "modelo_motivo_editar",
    "modelo_motivo_excluir",
    "modelos_motivo_index",
    "novo",
    "oficio_pdf_inline",
    "ordem_servico_pdf_inline",
    "retificar",
    "transporte",
    "transporte_autosave",
    "validar_oficio_para_documento",
    "wizard_documentos",
    "wizard_justificativa",
    "wizard_resumo",
    "wizard_roteiro",
    "wizard_roteiro_autosave_criar",
]
