"""O catálogo de tipos de evento (`P-02`).

O mais simples dos onze: sem "definir padrão", sem paginação, sem rótulo de volta
variável. Carrega o `?next=` porque a tela é aberta de dentro do cadastro do
evento e precisa voltar para lá.

Ao contrário de ofícios e justificativas, este não tem service próprio para
gravar — a view salvava na mão, atribuindo a área de trabalho. É exatamente o que
o caminho padrão de `core.catalog._salvar` faz.
"""

from __future__ import annotations

from core.catalog import CatalogConfig
from core.catalog import CatalogMessages
from core.catalog import delete_view
from core.catalog import edit_view
from core.catalog import index_view

from .forms import TipoEventoForm
from .presenters import apresentar_linha_lista_simples_tipo_evento
from .selectors import get_tipo_evento_by_id
from .selectors import listar_tipos_evento


TIPOS_EVENTO = CatalogConfig(
    listar=listar_tipos_evento,
    get_by_id=get_tipo_evento_by_id,
    form_class=TipoEventoForm,
    row_presenter=apresentar_linha_lista_simples_tipo_evento,
    url_index="eventos:tipos_index",
    url_editar="eventos:tipo_update",
    url_excluir="eventos:tipo_delete",
    template_index="eventos/tipos/index.html",
    template_confirm_delete="eventos/tipos/confirm_delete.html",
    contexto={
        "page_title": "Tipos de evento",
        "page_description": (
            "Cadastre os tipos que podem ser selecionados (mais de um por evento)."
        ),
    },
    mensagens=CatalogMessages(
        criado="Tipo de evento criado com sucesso.",
        atualizado="Tipo de evento atualizado com sucesso.",
        excluido="Tipo de evento excluído com sucesso.",
        erro_ao_salvar="Não foi possível salvar o tipo. Verifique os dados informados.",
    ),
    url_fallback_next="eventos:index",
    # As URLs de editar/excluir da linha são nuas, como na view antiga.
    urls_de_linha_com_next=False,
)


tipos_index = index_view(TIPOS_EVENTO)
tipo_editar = edit_view(TIPOS_EVENTO)
tipo_excluir = delete_view(TIPOS_EVENTO)
