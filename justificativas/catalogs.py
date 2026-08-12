"""O catálogo de modelos de justificativa (`P-02`).

Gêmeo do de modelos de motivo: tem "definir padrão" e rótulo de volta que muda
conforme a tela de origem. A diferença está no presenter — o de justificativas
recebe o `next_url` e compõe o link de "definir padrão" com ele, enquanto o de
ofícios monta a URL nua.

As frases de sucesso são as do código antigo, incluindo as sem acento
("Modelo definido como padrao.", "excluido com sucesso."). Corrigir a grafia é
mudança de microcopy — território do `N-11`, na Etapa 8, não deste PR.
"""

from __future__ import annotations

from django.urls import reverse

from core.catalog import CatalogConfig
from core.catalog import CatalogMessages
from core.catalog import delete_view
from core.catalog import edit_view
from core.catalog import index_view
from core.catalog import set_default_view

from .forms import ModeloJustificativaForm
from .presenters import apresentar_linha_lista_simples_modelo_justificativa
from .selectors import get_modelo_justificativa_by_id
from .selectors import listar_modelos_justificativa_busca
from .services import atualizar_modelo_justificativa
from .services import criar_modelo_justificativa
from .services import excluir_modelo_justificativa


MODELOS_JUSTIFICATIVA = CatalogConfig(
    listar=listar_modelos_justificativa_busca,
    get_by_id=get_modelo_justificativa_by_id,
    form_class=ModeloJustificativaForm,
    row_presenter=apresentar_linha_lista_simples_modelo_justificativa,
    url_index="justificativas:modelos_index",
    url_editar="justificativas:modelo_update",
    url_excluir="justificativas:modelo_delete",
    url_definir_padrao="justificativas:modelo_definir_padrao",
    template_index="justificativas/modelos/index.html",
    template_confirm_delete="justificativas/modelos/confirm_delete.html",
    contexto={
        "page_title": "Modelos de justificativa",
        "page_description": (
            "Cadastre textos reutilizaveis para preencher rapidamente a "
            "justificativa dos oficios."
        ),
    },
    mensagens=CatalogMessages(
        criado="Modelo de justificativa criado com sucesso.",
        atualizado="Modelo de justificativa atualizado com sucesso.",
        excluido="Modelo de justificativa excluido com sucesso.",
        erro_ao_salvar="Não foi possível salvar o modelo. Verifique os dados informados.",
        padrao_definido="Modelo definido como padrao.",
    ),
    url_fallback_next="justificativas:index",
    # O presenter monta o `set_default_url` e precisa do `next_url` para isso.
    presenter_recebe_set_default=False,
    presenter_recebe_next_url=True,
    criar=criar_modelo_justificativa,
    atualizar=atualizar_modelo_justificativa,
    excluir=excluir_modelo_justificativa,
)


def _contexto_de_retorno(request, next_url: str) -> dict:
    if next_url.startswith(reverse("oficios:index")):
        return {
            "back_to_url": next_url,
            "back_label": "Voltar para o ofício",
            "back_aria_label": "Voltar para o cadastro de ofício",
        }
    return {
        "back_to_url": next_url,
        "back_label": "Voltar para as justificativas",
        "back_aria_label": "Voltar para a lista de justificativas",
    }


modelos_index = index_view(MODELOS_JUSTIFICATIVA, contexto_extra=_contexto_de_retorno)
modelo_editar = edit_view(MODELOS_JUSTIFICATIVA)
modelo_excluir = delete_view(MODELOS_JUSTIFICATIVA)
modelo_definir_padrao = set_default_view(MODELOS_JUSTIFICATIVA)
