"""Fachada pública das views de Ofícios (P-06)."""

from .api_views import api_viatura_por_placa
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
