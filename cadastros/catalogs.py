"""Os quatro CRUDs de catálogo de ``cadastros`` (`P-02`).

Cidade continua fora: sua tela é lista + criação + exportação, sem o fluxo
completo de editar/excluir que caracteriza um catálogo administrável.
"""

from __future__ import annotations

from core.catalog import CatalogConfig
from core.catalog import CatalogMessages
from core.catalog import delete_view
from core.catalog import edit_view
from core.catalog import index_view
from core.catalog import set_default_view

from .forms import CargoForm
from .forms import CombustivelForm
from .forms import EstadoForm
from .forms import UnidadeForm
from .presenters import apresentar_linha_lista_simples_cargo
from .presenters import apresentar_linha_lista_simples_combustivel
from .presenters import apresentar_linha_lista_simples_estado
from .presenters import apresentar_linha_lista_simples_unidade
from .selectors import get_cargo_by_id
from .selectors import get_combustivel_by_id
from .selectors import get_estado_by_id
from .selectors import get_unidade_by_id
from .selectors import listar_cargos
from .selectors import listar_combustiveis
from .selectors import listar_estados
from .selectors import listar_unidades
from .services import CadastroVinculadoError
from .services import atualizar_cargo
from .services import atualizar_combustivel
from .services import atualizar_estado
from .services import atualizar_unidade
from .services import criar_cargo
from .services import criar_combustivel
from .services import criar_estado
from .services import criar_unidade
from .services import definir_cargo_padrao
from .services import definir_combustivel_padrao
from .services import excluir_cargo
from .services import excluir_combustivel
from .services import excluir_estado
from .services import excluir_unidade


CADASTROS_PER_PAGE = 15
_MENSAGEM_VINCULO = (
    "Não foi possível excluir este cadastro porque ele está vinculado a outros registros."
)


def _avisar_vinculo(request) -> None:
    from django.contrib import messages

    messages.error(request, _MENSAGEM_VINCULO)


def _contexto_next(back_label: str):
    def montar(_request, next_url: str) -> dict:
        return {
            "back_url": next_url or None,
            "back_label": back_label,
            "next_url": next_url,
        }

    return montar


def _contexto_cargos(_request, next_url: str) -> dict:
    retorno_ao_servidor = next_url.startswith("/cadastros/servidores/")
    return {
        "back_url": next_url or None,
        "back_label": "Voltar ao servidor" if retorno_ao_servidor else "Voltar ao formulário",
        "next_url": next_url,
    }


ESTADOS = CatalogConfig(
    listar=listar_estados,
    get_by_id=get_estado_by_id,
    form_class=EstadoForm,
    row_presenter=apresentar_linha_lista_simples_estado,
    url_index="cadastros:estados_index",
    url_editar="cadastros:estado_update",
    url_excluir="cadastros:estado_delete",
    template_index="cadastros/estados/index.html",
    template_confirm_delete="cadastros/estados/confirm_delete.html",
    contexto={
        "page_title": "Estados",
        "page_description": "Base administrativa interna de unidades federativas (UF).",
        "page_eyebrow": "Cadastros internos",
    },
    contexto_delete={
        "page_title": "Excluir estado",
        "page_description": "Não é possível excluir se existirem cidades vinculadas.",
    },
    mensagens=CatalogMessages(
        criado="Estado criado com sucesso.",
        atualizado="Estado atualizado com sucesso.",
        excluido="Estado excluído com sucesso.",
        erro_ao_salvar="Não foi possível salvar o estado. Verifique os dados informados.",
    ),
    paginar_por=CADASTROS_PER_PAGE,
    criar=criar_estado,
    atualizar=atualizar_estado,
    excluir=excluir_estado,
    erro_vinculo=CadastroVinculadoError,
    tratar_erro_vinculo=_avisar_vinculo,
)


UNIDADES = CatalogConfig(
    listar=listar_unidades,
    get_by_id=get_unidade_by_id,
    form_class=UnidadeForm,
    row_presenter=apresentar_linha_lista_simples_unidade,
    url_index="cadastros:unidades_index",
    url_editar="cadastros:unidade_update",
    url_excluir="cadastros:unidade_delete",
    template_index="cadastros/unidades/index.html",
    contexto={
        "page_title": "Unidades",
        "page_description": "Unidades administrativas reutilizadas nos fluxos.",
    },
    mensagens=CatalogMessages(
        criado="Unidade criada com sucesso.",
        atualizado="Unidade atualizada com sucesso.",
        excluido="Unidade excluída com sucesso.",
        erro_ao_salvar="Não foi possível salvar a unidade. Verifique os dados informados.",
    ),
    paginar_por=CADASTROS_PER_PAGE,
    aceitar_next=True,
    url_editar_com_next=False,
    confirmar_exclusao_em_get=False,
    criar=criar_unidade,
    atualizar=atualizar_unidade,
    excluir=excluir_unidade,
    erro_vinculo=CadastroVinculadoError,
    tratar_erro_vinculo=_avisar_vinculo,
)


CARGOS = CatalogConfig(
    listar=listar_cargos,
    get_by_id=get_cargo_by_id,
    form_class=CargoForm,
    row_presenter=apresentar_linha_lista_simples_cargo,
    url_index="cadastros:cargos_index",
    url_editar="cadastros:cargo_update",
    url_excluir="cadastros:cargo_delete",
    url_definir_padrao="cadastros:cargo_set_default",
    template_index="cadastros/cargos/index.html",
    contexto={
        "page_title": "Cargos",
        "page_description": "Cadastre os cargos utilizados em servidores.",
    },
    mensagens=CatalogMessages(
        criado="Cargo criado com sucesso.",
        atualizado="Cargo atualizado com sucesso.",
        excluido="Cargo excluído com sucesso.",
        erro_ao_salvar="Não foi possível salvar o cargo. Verifique os dados informados.",
        padrao_definido="Cargo definido como padrão com sucesso.",
    ),
    paginar_por=CADASTROS_PER_PAGE,
    aceitar_next=True,
    url_editar_com_next=False,
    confirmar_exclusao_em_get=False,
    criar=criar_cargo,
    atualizar=atualizar_cargo,
    excluir=excluir_cargo,
    definir_padrao=definir_cargo_padrao,
    erro_vinculo=CadastroVinculadoError,
    tratar_erro_vinculo=_avisar_vinculo,
    definir_padrao_get_redireciona=True,
)


COMBUSTIVEIS = CatalogConfig(
    listar=listar_combustiveis,
    get_by_id=get_combustivel_by_id,
    form_class=CombustivelForm,
    row_presenter=apresentar_linha_lista_simples_combustivel,
    url_index="cadastros:combustiveis_index",
    url_editar="cadastros:combustivel_update",
    url_excluir="cadastros:combustivel_delete",
    url_definir_padrao="cadastros:combustivel_set_default",
    template_index="cadastros/combustiveis/index.html",
    contexto={
        "page_title": "Combustíveis",
        "page_description": "Cadastre os combustíveis disponíveis para viaturas.",
    },
    mensagens=CatalogMessages(
        criado="Combustível criado com sucesso.",
        atualizado="Combustível atualizado com sucesso.",
        excluido="Combustível excluído com sucesso.",
        erro_ao_salvar=(
            "Não foi possível salvar o combustível. Verifique os dados informados."
        ),
        padrao_definido="Combustível definido como padrão com sucesso.",
    ),
    paginar_por=CADASTROS_PER_PAGE,
    aceitar_next=True,
    url_editar_com_next=False,
    confirmar_exclusao_em_get=False,
    criar=criar_combustivel,
    atualizar=atualizar_combustivel,
    excluir=excluir_combustivel,
    definir_padrao=definir_combustivel_padrao,
    erro_vinculo=CadastroVinculadoError,
    tratar_erro_vinculo=_avisar_vinculo,
    definir_padrao_get_redireciona=True,
)


estados_index = index_view(ESTADOS)
estado_update = edit_view(ESTADOS)
estado_delete = delete_view(ESTADOS)

unidades_index = index_view(
    UNIDADES, contexto_extra=_contexto_next("Voltar ao servidor")
)
unidade_update = edit_view(UNIDADES)
unidade_delete = delete_view(UNIDADES)

cargos_index = index_view(CARGOS, contexto_extra=_contexto_cargos)
cargo_update = edit_view(CARGOS)
cargo_delete = delete_view(CARGOS)
cargo_set_default = set_default_view(CARGOS)

combustiveis_index = index_view(
    COMBUSTIVEIS, contexto_extra=_contexto_next("Voltar à viatura")
)
combustivel_update = edit_view(COMBUSTIVEIS)
combustivel_delete = delete_view(COMBUSTIVEIS)
combustivel_set_default = set_default_view(COMBUSTIVEIS)
