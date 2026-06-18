"""UI Lab 2.0 — catalogo de componentes do sistema organizados por funcao.

Cada categoria e uma pagina. Cada componente aparece com: nome, preview clonado
(include do partial real quando existe; copia literal quando o padrao e inline)
e a lista "Usado em" com os arquivos onde ele aparece no sistema.

Escopo do catalogo (decidido com o usuario): site inteiro EXCETO paginas de
lista (`*/index.html`, `components/lists/**`) e EXCETO o app `protocolos`.
As listas de "Usado em" sao apuradas por grep e datadas em USAGE_AUDIT_DATE.
"""

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .forms import UiLab2DemoForm


USAGE_AUDIT_DATE = "2026-06-17"


# ── Categorias (componentes separados por funcao) ──────────────────────────
UI_LAB2_CATEGORIES = [
    {
        "slug": "shells",
        "label": "Shells & Layout",
        "mark": "SH",
        "title": "Shells & Layout de pagina",
        "subtitle": "Cascas de pagina, painel de formulario e pilha de secoes.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "headers",
        "label": "Headers",
        "mark": "HD",
        "title": "Headers de pagina",
        "subtitle": "Cabecalhos com voltar, status, stepper e variantes simples.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "steppers",
        "label": "Steppers & Etapas",
        "mark": "ST",
        "title": "Steppers & Navegacao de etapas",
        "subtitle": "Indicadores de progresso dos wizards.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "section-cards",
        "label": "Section Cards",
        "mark": "SC",
        "title": "Section Cards de formulario",
        "subtitle": "Cartoes de secao e subsecoes internas dos cadastros.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "fields",
        "label": "Campos & Inputs",
        "mark": "FD",
        "title": "Campos & Inputs",
        "subtitle": "Campos base, grid de campos, textarea e toggle.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "selects",
        "label": "Selects & Pickers",
        "mark": "SL",
        "title": "Selects & Pickers",
        "subtitle": "Select, multiselect, dropdown e search picker.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "calendars",
        "label": "Calendarios & Datas",
        "mark": "CD",
        "title": "Calendarios & Datas",
        "subtitle": "Calendario customizado cv-date-picker e inputs de data/hora.",
        "status_label": "Pronto",
        "status_modifier": "done",
    },
    {
        "slug": "buttons",
        "label": "Botoes",
        "mark": "BT",
        "title": "Botoes",
        "subtitle": "Familia cv-btn, botoes de campo, rodape, icone e flutuantes.",
        "status_label": "Pronto",
        "status_modifier": "done",
    },
    {
        "slug": "footers",
        "label": "Rodapes de acao",
        "mark": "FT",
        "title": "Rodapes de acao",
        "subtitle": "Barras de acao de formulario, card e wizard.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "badges",
        "label": "Badges & Status",
        "mark": "BG",
        "title": "Badges, Chips & Status",
        "subtitle": "Chips de entidade, status pill e status badge.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "feedback",
        "label": "Feedback",
        "mark": "FB",
        "title": "Feedback & Validacao",
        "subtitle": "Alertas, erros de campo/formulario e estados vazios.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "modals",
        "label": "Modais & Overlays",
        "mark": "MD",
        "title": "Modais & Overlays",
        "subtitle": "Modal shell e confirmacoes de exclusao.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "domain-cards",
        "label": "Cards de dominio",
        "mark": "DC",
        "title": "Cards de dominio",
        "subtitle": "Trecho, destinos, resumo de rota, evento e documento.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "signatures",
        "label": "Assinaturas",
        "mark": "SG",
        "title": "Assinaturas",
        "subtitle": "Central de assinatura e etiqueta de acoes do documento.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
    {
        "slug": "documents",
        "label": "Document Viewer & PDF",
        "mark": "DV",
        "title": "Document Viewer & PDF",
        "subtitle": "Viewer de PDF e templates documentais.",
        "status_label": "Planejado",
        "status_modifier": "planned",
    },
]

CATEGORY_BY_SLUG = {c["slug"]: c for c in UI_LAB2_CATEGORIES}


# ── "Usado em" — apurado por grep (datado em USAGE_AUDIT_DATE) ──────────────
# Exclui paginas de lista (*/index.html) e o app protocolos, por decisao do
# usuario. Tambem exclui base.html (infra) e dev/ui_lab/** (UI Lab 1.0).
COMPONENT_USAGE = {
    # Calendarios & Datas
    "cv_date_picker": [
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
        "templates/roteiros/partials/roteiro/trechos.html",
        "templates/roteiros/partials/roteiro/bate_volta.html",
        "templates/roteiros/partials/roteiro/retorno.html",
    ],
    "input_date_time": [
        "templates/eventos/includes/_evento_form_sections.html",
        "templates/termos/form.html",
        "templates/ordens_servico/form.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
    ],
    # Botoes
    "cv_btn": [
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/termos/preview_cadastro.html",
        "templates/eventos/detalhe.html",
        "templates/prestacoes/diario_form.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_atividades.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
        "templates/planos_trabalho/wizard_documentos.html",
        "templates/roteiros/partials/roteiro/trechos.html",
        "templates/roteiros/partials/roteiro/retorno.html",
        "templates/roteiros/partials/roteiro/source.html",
        "templates/roteiros/includes/mapa_rota.html",
        "templates/documentos/pdf_viewer.html",
        "templates/oficios/partials/assinatura_central_documento.html",
        "templates/oficios/partials/assinatura_etiqueta_actions.html",
    ],
    # button.html + action_button.html (wrapper compat) — usos fora de listas
    "button_component": [
        "templates/eventos/form.html",
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/termos/preview.html",
        "templates/prestacoes/diario_form.html",
        "templates/prestacoes/prestacao_form.html",
        "templates/prestacoes/registro_form.html",
        "templates/prestacoes/relatorio_form.html",
        "templates/oficios/wizard_dados_viajantes.html",
        "templates/oficios/wizard_transporte.html",
        "templates/oficios/wizard_justificativa.html",
        "templates/oficios/partials/wizard_dados_card_viatura.html",
        "templates/components/cards/document_card.html",
        "templates/components/cards/module_card.html",
        "templates/components/ui/feedback/empty_state.html",
        "templates/components/ui/layouts/card_footer_actions.html",
    ],
    "field_manage_button": [
        "templates/components/ui/forms/field.html",
    ],
    "field_action_button": [
        "templates/cadastros/servidores/form.html",
        "templates/cadastros/viaturas/form.html",
    ],
    "footer_action": [],
    "icon_button": [
        "templates/oficios/wizard_documentos.html",
        "templates/planos_trabalho/wizard_documentos.html",
    ],
    "floating_action": [],
    "floating_primary_action": [
        "templates/cadastros/cargos/form.html",
        "templates/cadastros/cidades/form.html",
        "templates/cadastros/combustiveis/form.html",
        "templates/cadastros/estados/form.html",
        "templates/cadastros/unidades/form.html",
    ],
    # Headers
    "header_stack_back_action": [
        "templates/eventos/form.html",
        "templates/eventos/detalhe.html",
        "templates/oficios/wizard_base.html",
        "templates/ordens_servico/form.html",
        "templates/planos_trabalho/wizard_base.html",
        "templates/roteiros/roteiro_form_page.html",
        "templates/roteiros/detail.html",
        "templates/termos/form.html",
        "templates/termos/preview.html",
        "templates/termos/preview_cadastro.html",
        "templates/prestacoes/diario_form.html",
        "templates/prestacoes/prestacao_form.html",
        "templates/prestacoes/registro_form.html",
        "templates/prestacoes/relatorio_form.html",
        "templates/components/ui/layouts/wizard_page.html",
    ],
    "header_stack_simple": [
        "templates/cadastros/servidores/form.html",
        "templates/cadastros/viaturas/form.html",
        "templates/cadastros/unidades/form.html",
        "templates/cadastros/cidades/form.html",
        "templates/cadastros/estados/form.html",
        "templates/cadastros/cargos/form.html",
        "templates/cadastros/combustiveis/form.html",
        "templates/cadastros/configuracao/form.html",
        "templates/justificativas/modelos/form.html",
        "templates/oficios/modelos_motivo/form.html",
        "templates/planos_trabalho/atividades/form.html",
        "templates/planos_trabalho/horarios/form.html",
        "templates/planos_trabalho/programas/form.html",
    ],
    "header_band_status": [],
    "header_stack_stepper": [],
    # Steppers
    "page_stepper": [
        "templates/oficios/wizard_base.html",
        "templates/planos_trabalho/wizard_base.html",
        "templates/roteiros/roteiro_form_page.html",
        "templates/components/ui/layouts/wizard_page.html",
        "templates/oficios/partials/wizard_stepper.html",
    ],
    # Badges / Status
    "chip": [
        "templates/eventos/includes/_evento_form_sections.html",
        "templates/oficios/wizard_documentos.html",
        "templates/oficios/partials/assinatura_central_documento.html",
        "templates/oficios/partials/assinatura_etiqueta_actions.html",
        "templates/planos_trabalho/wizard_atividades.html",
    ],
    "status_badge": [
        "templates/components/ui/modals/confirm_delete.html",
    ],
    "status_pill": [
        "templates/oficios/wizard_documentos.html",
        "templates/components/cards/document_card.html",
    ],
    "page_header_status_chip": [
        "templates/components/ui/headers/header_stack_back_action.html",
        "templates/components/ui/headers/header_stack_simple.html",
    ],
    # Feedback
    "alert": [
        "templates/termos/preview.html",
        "templates/oficios/modelos_motivo/confirm_delete.html",
        "templates/justificativas/modelos/confirm_delete.html",
        "templates/planos_trabalho/atividades/confirm_delete.html",
    ],
    "field_error": [
        "templates/eventos/includes/_evento_form_sections.html",
        "templates/oficios/wizard_dados_viajantes.html",
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
        "templates/prestacoes/diario_form.html",
        "templates/roteiros/partials/roteiro/source.html",
        "templates/cadastros/servidores/form.html",
        "templates/components/ui/forms/field.html",
    ],
    "form_errors": [],
    "empty_state": [
        "templates/roteiros/detail.html",
        "templates/components/lists/list_empty.html",
    ],
    "module_placeholder": [],
    # Shells & Layout
    "page_shell_wizard": [
        "templates/oficios/wizard_base.html",
        "templates/planos_trabalho/wizard_base.html",
        "templates/roteiros/roteiro_form_page.html",
        "templates/eventos/form.html",
        "templates/components/ui/layouts/wizard_page.html",
    ],
    "main_form_panel": [
        "templates/oficios/wizard_base.html",
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/eventos/form.html",
        "templates/prestacoes/diario_form.html",
        "templates/cadastros/servidores/form.html",
    ],
    # Section Cards
    "cv_wizard_section_card": [
        "templates/eventos/includes/_evento_form_sections.html",
        "templates/oficios/wizard_dados_viajantes.html",
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
    ],
    "wizard_section_card": [],
    "form_section": [
        "templates/cadastros/servidores/form.html",
        "templates/cadastros/viaturas/form.html",
        "templates/cadastros/cidades/form.html",
        "templates/justificativas/modelos/form.html",
        "templates/oficios/modelos_motivo/form.html",
        "templates/planos_trabalho/atividades/form.html",
        "templates/planos_trabalho/horarios/form.html",
        "templates/roteiros/detail.html",
        "templates/termos/preview.html",
    ],
    # Fields
    "form_field": [
        "templates/eventos/includes/_evento_form_sections.html",
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/oficios/wizard_dados_viajantes.html",
        "templates/oficios/wizard_transporte.html",
        "templates/oficios/wizard_justificativa.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
        "templates/prestacoes/diario_form.html",
        "templates/cadastros/servidores/form.html",
        "templates/cadastros/viaturas/form.html",
    ],
    "card_toggle": [
        "templates/cadastros/cidades/form.html",
        "templates/components/ui/forms/field.html",
    ],
    # Selects & Pickers
    "select": [
        "templates/components/ui/forms/field.html",
    ],
    "multiselect": [
        "templates/components/ui/forms/field.html",
    ],
    "dropdown": [],
    "cv_search_picker": [
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
        "templates/roteiros/partials/roteiro/source.html",
    ],
    "input_with_action": [
        "templates/ordens_servico/form.html",
        "templates/oficios/wizard_dados_viajantes.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
        "templates/cadastros/servidores/form.html",
        "templates/cadastros/viaturas/form.html",
    ],
    "oficio_motorista_split_field": [
        "templates/oficios/partials/wizard_dados_card_motorista_externo.html",
        "templates/oficios/wizard_transporte.html",
    ],
    # Footers
    "card_footer_actions": [
        "templates/cadastros/servidores/form.html",
        "templates/cadastros/viaturas/form.html",
        "templates/cadastros/configuracao/form.html",
        "templates/justificativas/modelos/form.html",
        "templates/oficios/modelos_motivo/form.html",
        "templates/planos_trabalho/atividades/form.html",
        "templates/planos_trabalho/horarios/form.html",
        "templates/planos_trabalho/programas/form.html",
    ],
    "card_footer_section": [
        "templates/oficios/wizard_documentos.html",
        "templates/oficios/wizard_justificativa.html",
        "templates/oficios/partials/wizard_dados_card_viatura.html",
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_atividades.html",
        "templates/planos_trabalho/wizard_efetivo_diarias.html",
        "templates/roteiros/partials/roteiro/actions.html",
    ],
    "termo_actions": [
        "templates/ordens_servico/form.html",
        "templates/termos/form.html",
    ],
    # Modais
    "confirm_delete_block": [
        "templates/cadastros/servidores/confirm_delete.html",
        "templates/cadastros/viaturas/confirm_delete.html",
        "templates/cadastros/cidades/confirm_delete.html",
        "templates/oficios/confirm_delete.html",
        "templates/planos_trabalho/confirm_delete.html",
        "templates/roteiros/confirm_delete.html",
    ],
    "modal_shell": [],
    # Cards de dominio
    "trecho_card": [
        "templates/roteiros/detail.html",
    ],
    "resumo_rota": [
        "templates/roteiros/detail.html",
    ],
    "calculadora_rota": [
        "templates/roteiros/includes/_roteiro_editor.html",
    ],
    "retorno": [
        "templates/roteiros/includes/_roteiro_editor.html",
    ],
    "resumo_evento_card": [
        "templates/planos_trabalho/wizard_identificacao.html",
        "templates/planos_trabalho/wizard_documentos.html",
    ],
    "document_card": [
        "templates/components/lists/list_grid.html",
    ],
    "summary_card": [],
    "module_card": [],
    "card": [],
    # Assinaturas
    "assinatura_central_documento": [
        "templates/oficios/wizard_documentos.html",
    ],
    "assinatura_etiqueta_actions": [
        "templates/oficios/wizard_documentos.html",
    ],
    # Document Viewer / PDF
    "pdf_viewer": [
        "templates/documentos/pdf_viewer.html",
    ],
    "pdf_templates": [
        "templates/documentos/pdf/oficio.html",
        "templates/documentos/pdf/justificativa.html",
        "templates/documentos/pdf/ordem_servico.html",
        "templates/documentos/pdf/plano_trabalho.html",
        "templates/documentos/pdf/termo_autorizacao.html",
    ],
}


# Steps de demonstracao para o page_stepper (mesmo contrato dos wizards reais)
UI_LAB2_DEMO_STEPS = [
    {
        "state_class": "is-complete",
        "step_label": "Etapa 1",
        "title": "Dados e viajantes",
        "status": "Concluida",
        "marker": "✓",
        "marker_aria_hidden": True,
    },
    {
        "state_class": "is-current",
        "step_label": "Etapa 2",
        "title": "Transporte",
        "status": "Em andamento",
        "marker": "2",
        "marker_aria_hidden": False,
        "aria_current": "step",
    },
    {
        "state_class": "is-pending",
        "step_label": "Etapa 3",
        "title": "Roteiro e diarias",
        "status": "Aguardando",
        "marker": "3",
        "marker_aria_hidden": False,
    },
    {
        "state_class": "is-disabled",
        "step_label": "Etapa 4",
        "title": "Documentos",
        "status": "Bloqueada",
        "marker": "4",
        "marker_aria_hidden": True,
    },
]


def _categories_with_urls():
    items = []
    for category in UI_LAB2_CATEGORIES:
        item = category.copy()
        item["url"] = reverse("ui_lab2:category", kwargs={"slug": category["slug"]})
        items.append(item)
    return items


def _base_context(active_slug):
    categories = _categories_with_urls()
    current = next((c for c in categories if c["slug"] == active_slug), None)
    return {
        "ui_lab2_categories": categories,
        "ui_lab2_current": current,
        "ui_lab2_index_url": reverse("ui_lab2:index"),
        "usage": COMPONENT_USAGE,
        "usage_audit_date": USAGE_AUDIT_DATE,
        "demo_form": UiLab2DemoForm(),
        "demo_form_bound": UiLab2DemoForm(data={"texto_obrigatorio": ""}),
        "demo_steps": UI_LAB2_DEMO_STEPS,
        "dropdown_items": [
            {"label": "Abrir", "href": "#"},
            {"label": "Editar", "href": "#"},
            {"label": "Baixar DOCX", "href": "#"},
            {"label": "Excluir", "href": "#", "danger": True, "separator_before": True},
        ],
    }


def index(request):
    context = _base_context(None)
    context["ui_lab2_overview"] = context["ui_lab2_categories"]
    return render(request, "ui_lab2/index.html", context)


def category(request, slug):
    if slug not in CATEGORY_BY_SLUG:
        raise Http404("Categoria do UI Lab 2.0 nao encontrada.")
    context = _base_context(slug)
    template = "ui_lab2/{}.html".format(slug.replace("-", "_"))
    return render(request, template, context)
