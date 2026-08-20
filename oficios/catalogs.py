"""O catálogo de modelos de motivo (`P-02`).

Substitui `catalog_views.py`. As frases e o rótulo de retorno são os mesmos;
`core/tests/test_catalogos_a2_caracterizacao.py` compara cada um literalmente.

O rótulo de volta muda conforme a tela de origem — vindo da Ordem de Serviço ele
diz outra coisa. Por isso o contexto de retorno é resolvido por função e passado
via `contexto_extra`, e não por constante como nos catálogos do Plano de Trabalho.
"""

from __future__ import annotations

from core.catalog import CatalogConfig
from core.catalog import CatalogMessages
from core.catalog import delete_view
from core.catalog import edit_view
from core.catalog import index_view
from core.catalog import rotulo_de_retorno
from core.catalog import set_default_view

from .forms import ModeloMotivoOficioForm
from .presenters import apresentar_linha_lista_simples_modelo_motivo
from .selectors import get_modelo_motivo_by_id
from .selectors import listar_modelos_motivo
from .services import atualizar_modelo_motivo
from .services import criar_modelo_motivo
from .services import excluir_modelo_motivo


def _listar(q=None):
    return listar_modelos_motivo(q=q, incluir_inativos=True)


MODELOS_MOTIVO = CatalogConfig(
    listar=_listar,
    get_by_id=get_modelo_motivo_by_id,
    form_class=ModeloMotivoOficioForm,
    row_presenter=apresentar_linha_lista_simples_modelo_motivo,
    url_index="oficios:modelos_motivo_index",
    url_editar="oficios:modelo_motivo_update",
    url_excluir="oficios:modelo_motivo_delete",
    url_definir_padrao="oficios:modelo_motivo_definir_padrao",
    template_index="oficios/modelos_motivo/index.html",
    template_confirm_delete="oficios/modelos_motivo/confirm_delete.html",
    contexto={
        "page_title": "Modelos de motivo",
        "page_description": (
            "Cadastre textos reutilizáveis para preencher rapidamente "
            "o motivo dos ofícios."
        ),
    },
    mensagens=CatalogMessages(
        criado="Modelo de motivo criado com sucesso.",
        atualizado="Modelo de motivo atualizado com sucesso.",
        excluido="Modelo de motivo excluído com sucesso.",
        erro_ao_salvar="Não foi possível salvar o modelo. Verifique os dados informados.",
        padrao_definido="Modelo definido como padrão.",
    ),
    paginar_por=20,
    url_fallback_next="oficios:novo",
    back_label_com_next="Voltar ao ofício",
    back_label_sem_next="Voltar ao ofício",
    # O presenter monta o `set_default_url` por dentro e as URLs da linha são
    # nuas — comportamento preservado da view antiga.
    presenter_recebe_set_default=False,
    urls_de_linha_com_next=False,
    criar=criar_modelo_motivo,
    atualizar=atualizar_modelo_motivo,
    excluir=excluir_modelo_motivo,
)


def _contexto_de_retorno(request, next_url: str) -> dict:
    """Rótulo de volta conforme a tela de onde o usuário veio.

    O rótulo sai de `core.catalog.rotulo_de_retorno`, que o lê do DESTINO. Aqui
    havia duas frases fixas — ofício e Ordem de Serviço —, e este catálogo é
    aberto também do evento e do termo: quem vinha de um evento lia "Voltar para
    o ofício" e ia parar no evento (2026-08-19).
    """
    rotulo = rotulo_de_retorno(next_url)
    return {
        "back_to_oficio_url": next_url,
        "back_label": rotulo,
        "back_aria_label": rotulo,
    }


modelos_motivo_index = index_view(MODELOS_MOTIVO, contexto_extra=_contexto_de_retorno)
modelo_motivo_editar = edit_view(MODELOS_MOTIVO)
modelo_motivo_excluir = delete_view(MODELOS_MOTIVO)
modelo_motivo_definir_padrao = set_default_view(MODELOS_MOTIVO)
