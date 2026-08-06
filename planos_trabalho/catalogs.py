"""Os quatro catálogos administráveis do Plano de Trabalho (`P-02`).

Substitui `catalog_views.py` (430 linhas) por quatro declarações. O motor está em
`core/catalog.py`; aqui só mora o que cada catálogo tem de próprio — frases,
rótulos de retorno, presenter da linha e se tem busca ou "definir padrão".

As mensagens são as mesmas de antes, letra por letra. `test_catalogos_
caracterizacao.py` compara cada uma literalmente: trocar "Atividade cadastrada."
por "Atividade criada." seria uma regressão silenciosa numa tela de uso diário.
"""

from __future__ import annotations

import json

from core.catalog import CatalogConfig
from core.catalog import CatalogMessages
from core.catalog import delete_view
from core.catalog import edit_view
from core.catalog import index_view
from core.catalog import set_default_view

from .forms import AtividadePlanoTrabalhoQuickAddForm
from .forms import HorarioAtendimentoForm
from .forms import PresetAtividadesQuickAddForm
from .forms import ProgramaSolicitanteForm
from .presenters import apresentar_linha_lista_simples_atividade
from .presenters import apresentar_linha_lista_simples_horario
from .presenters import apresentar_linha_lista_simples_preset
from .presenters import apresentar_linha_lista_simples_programa
from .selectors import get_atividade_by_id
from .selectors import get_horario_by_id
from .selectors import get_preset_by_id
from .selectors import get_programa_by_id
from .selectors import listar_atividades
from .selectors import listar_horarios
from .selectors import listar_presets
from .selectors import listar_programas


_VOLTA_AO_WIZARD = "Voltar pra plano de trabalho"


def _campos_da_atividade(atividade) -> str:
    return json.dumps(
        {
            "nome": atividade.nome,
            "recurso_necessario": atividade.recurso_necessario,
            "meta": atividade.meta,
        },
        ensure_ascii=False,
    )


def _campos_do_preset(preset) -> str:
    return json.dumps(
        {
            "nome": preset.nome,
            "atividades": [str(pk) for pk in preset.atividades.values_list("pk", flat=True)],
        },
        ensure_ascii=False,
    )


def _campos_ordenaveis(campo: str):
    def montar(obj) -> str:
        return json.dumps(
            {campo: getattr(obj, campo), "ativo": obj.ativo, "ordem": obj.ordem},
            ensure_ascii=False,
        )

    return montar


ATIVIDADES = CatalogConfig(
    listar=listar_atividades,
    get_by_id=get_atividade_by_id,
    form_class=AtividadePlanoTrabalhoQuickAddForm,
    row_presenter=apresentar_linha_lista_simples_atividade,
    edit_fields_json=_campos_da_atividade,
    url_index="planos_trabalho:atividades_index",
    url_editar="planos_trabalho:atividade_update",
    url_excluir="planos_trabalho:atividade_delete",
    template_index="planos_trabalho/atividades/index.html",
    template_confirm_delete="planos_trabalho/atividades/confirm_delete.html",
    rows_context_key="linhas",
    contexto={
        "page_title": "Gerenciamento de atividades",
        "page_description": "Cadastre, edite e organize atividades com metas e recursos.",
    },
    mensagens=CatalogMessages(
        criado="Atividade cadastrada.",
        atualizado="Atividade atualizada.",
        excluido="Atividade “{}” excluída.",
    ),
    rotulo=lambda atividade: atividade.nome,
    url_fallback_next="planos_trabalho:index",
    back_label_com_next=_VOLTA_AO_WIZARD,
    back_label_sem_next="Voltar",
)


PRESETS = CatalogConfig(
    listar=listar_presets,
    get_by_id=get_preset_by_id,
    form_class=PresetAtividadesQuickAddForm,
    row_presenter=apresentar_linha_lista_simples_preset,
    edit_fields_json=_campos_do_preset,
    url_index="planos_trabalho:presets_index",
    url_editar="planos_trabalho:preset_update",
    url_excluir="planos_trabalho:preset_delete",
    url_definir_padrao="planos_trabalho:preset_definir_padrao",
    template_index="planos_trabalho/presets/index.html",
    template_confirm_delete="planos_trabalho/presets/confirm_delete.html",
    rows_context_key="linhas",
    contexto={
        "page_title": "Gerenciamento de presets",
        "page_description": "Monte conjuntos de atividades para aplicar de uma vez no wizard.",
    },
    mensagens=CatalogMessages(
        criado="Preset cadastrado.",
        atualizado="Preset atualizado.",
        excluido="Preset “{}” excluído.",
        padrao_definido="Preset “{}” definido como padrão.",
    ),
    rotulo=lambda preset: preset.nome,
    url_fallback_next="planos_trabalho:index",
    back_label_com_next=_VOLTA_AO_WIZARD,
    back_label_sem_next="Voltar",
)


PROGRAMAS = CatalogConfig(
    listar=listar_programas,
    get_by_id=get_programa_by_id,
    form_class=ProgramaSolicitanteForm,
    row_presenter=apresentar_linha_lista_simples_programa,
    edit_fields_json=_campos_ordenaveis("nome"),
    url_index="planos_trabalho:programas_index",
    url_editar="planos_trabalho:programa_update",
    url_excluir="planos_trabalho:programa_delete",
    template_index="planos_trabalho/programas/index.html",
    template_confirm_delete="planos_trabalho/programas/confirm_delete.html",
    rows_context_key="linhas",
    # Este catálogo não tem busca; o `q` vazio é o que o template espera.
    buscar=False,
    contexto={
        "page_title": "Programas solicitantes",
        "page_description": "Programas exibidos na etapa de identificação do plano de trabalho.",
    },
    mensagens=CatalogMessages(
        criado="Programa cadastrado.",
        atualizado="Programa atualizado.",
        excluido="Programa “{}” excluído.",
        erro_ao_salvar="Não foi possível salvar o programa. Verifique os dados informados.",
    ),
    rotulo=lambda programa: programa.nome,
    url_fallback_next="planos_trabalho:index",
    back_label_com_next="Voltar",
    back_label_sem_next="Voltar",
)


HORARIOS = CatalogConfig(
    listar=listar_horarios,
    get_by_id=get_horario_by_id,
    form_class=HorarioAtendimentoForm,
    row_presenter=apresentar_linha_lista_simples_horario,
    edit_fields_json=_campos_ordenaveis("faixa"),
    url_index="planos_trabalho:horarios_index",
    url_editar="planos_trabalho:horario_update",
    url_excluir="planos_trabalho:horario_delete",
    template_index="planos_trabalho/horarios/index.html",
    template_confirm_delete="planos_trabalho/horarios/confirm_delete.html",
    rows_context_key="linhas",
    buscar=False,
    contexto={
        "page_title": "Horários de atendimento",
        "page_description": (
            "Horários exibidos no select da etapa de identificação do plano de trabalho."
        ),
    },
    mensagens=CatalogMessages(
        criado="Horário cadastrado.",
        atualizado="Horário atualizado.",
        excluido="Horário “{}” excluído.",
        erro_ao_salvar="Não foi possível salvar o horário. Verifique os dados informados.",
    ),
    rotulo=lambda horario: horario.faixa,
)


atividades_index = index_view(ATIVIDADES)
atividade_editar = edit_view(ATIVIDADES)
atividade_excluir = delete_view(ATIVIDADES)

presets_index = index_view(PRESETS)
preset_editar = edit_view(PRESETS)
preset_excluir = delete_view(PRESETS)
preset_definir_padrao = set_default_view(PRESETS)

programas_index = index_view(PROGRAMAS)
programa_editar = edit_view(PROGRAMAS)
programa_excluir = delete_view(PROGRAMAS)

horarios_index = index_view(HORARIOS)
horario_editar = edit_view(HORARIOS)
horario_excluir = delete_view(HORARIOS)
