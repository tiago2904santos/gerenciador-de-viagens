from django.contrib.auth.views import LoginView as DjangoLoginView
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from .forms import LoginForm


UI_LAB_PAGE_DEFINITIONS = [
    {
        "slug": "index",
        "label": "Overview / Index",
        "mark": "UI",
        "title": "UI Lab",
        "subtitle": (
            "Laboratorio visual do design system. Cada area tem sua propria pagina "
            "e pode evoluir de forma incremental."
        ),
        "summary": "Pagina inicial com atalhos, contexto e status de cada area.",
        "status_label": "Pronto",
        "status_modifier": "done",
        "route_name": "core:ui_lab",
    },
    {
        "slug": "structures",
        "label": "Page Structures",
        "mark": "PS",
        "title": "Page Structures",
        "subtitle": "Layouts de shell, listas, formularios e wizards em nivel de pagina.",
        "summary": "Standard Simple, Standard, Wizard e variacoes de list/filter shell.",
        "status_label": "Pronto",
        "status_modifier": "done",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "headers",
        "label": "Headers",
        "mark": "HD",
        "title": "Headers",
        "subtitle": "Composicao do sistema de cabecalhos com band, rail, filtros e stepper.",
        "summary": "Header Band, Header Stack, filtros no rail e quick add separado.",
        "status_label": "Pronto",
        "status_modifier": "done",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "buttons",
        "label": "Buttons",
        "mark": "BT",
        "title": "Buttons",
        "subtitle": "Padroes de acao primaria, secundaria e estados visuais de botao.",
        "summary": "Base para botoes primarios, secundarios, icone, loading e disabled.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "fields",
        "label": "Fields / Inputs",
        "mark": "FD",
        "title": "Fields / Inputs",
        "subtitle": "Campos base do design system, agrupamentos e variacoes de estado.",
        "summary": "Inputs, textareas, checkboxes, radios, switches e layouts de campo.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "selects",
        "label": "Selects / Filters",
        "mark": "SF",
        "title": "Selects / Dropdowns / Filters",
        "subtitle": "Selecao, dropdowns, filtros e quick add em uma pagina dedicada.",
        "summary": "Selects, filtros simples, filtros avancados e quick add aberto.",
        "status_label": "Em construcao",
        "status_modifier": "build",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "status",
        "label": "Badges / Status",
        "mark": "ST",
        "title": "Badges / Chips / Status",
        "subtitle": "Estados, chips e etiquetas para ciclos documentais e entidades.",
        "summary": "Status de ciclo, chips de pessoa, viajante, destino e filtros aplicados.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "feedback",
        "label": "Feedback / Validation",
        "mark": "FB",
        "title": "Feedback / Validation",
        "subtitle": "Mensagens, alertas, estados vazios e validacao de formulario.",
        "summary": "Erros, avisos, sucesso, loading, skeleton e estados discretos.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "cards",
        "label": "Cards / List Items",
        "mark": "CD",
        "title": "Cards / List Items",
        "subtitle": "Cards e linhas de lista para entidades, documentos e acoes.",
        "summary": "Card documental, list row, acoes, status e empty list.",
        "status_label": "Pronto",
        "status_modifier": "done",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "overlays",
        "label": "Modals / Overlays",
        "mark": "OV",
        "title": "Modals / Drawers / Popovers",
        "subtitle": "Camadas de interface que aparecem acima do conteudo principal.",
        "summary": "Modal, drawer lateral, popover, tooltip e menus de acao.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "tables",
        "label": "Tables / Pagination",
        "mark": "TB",
        "title": "Tables / Pagination",
        "subtitle": "Tabelas, selecao, paginacao e estados vazios em um so lugar.",
        "summary": "Tabela simples, densa, responsiva, com acoes e paginacao.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "documents",
        "label": "Document Viewer",
        "mark": "DV",
        "title": "Document Viewer / PDF Preview",
        "subtitle": "Superficie documental para pre-visualizacao, metadados e acoes.",
        "summary": "Preview de PDF, toolbar, info lateral e arquivos vinculados.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
    {
        "slug": "signature",
        "label": "Signature",
        "mark": "SG",
        "title": "Signature / Document Actions",
        "subtitle": "Acoes de assinatura e distribuicao documental em um shell separado.",
        "summary": "Solicitacao, download, copia de link e estados de assinatura.",
        "status_label": "Planejado",
        "status_modifier": "planned",
        "route_name": "core:ui_lab_section",
    },
]

UI_LAB_STATUS_EXAMPLES = [
    {"label": "Rascunho", "modifier": "draft"},
    {"label": "Finalizado", "modifier": "done"},
    {"label": "Pendente", "modifier": "pending"},
    {"label": "Assinado", "modifier": "signed"},
    {"label": "Cancelado", "modifier": "cancelled"},
    {"label": "Ativo", "modifier": "active"},
    {"label": "Inativo", "modifier": "inactive"},
    {"label": "Bloqueado", "modifier": "locked"},
    {"label": "Retificado", "modifier": "corrected"},
    {"label": "Com pendencia", "modifier": "issue"},
    {"label": "Sem RG", "modifier": "missing"},
    {"label": "Ligado", "modifier": "on"},
    {"label": "Desligado", "modifier": "off"},
]

UI_LAB_PLAN_ITEMS = {
    "buttons": [
        "Primary Button",
        "Secondary Button",
        "Ghost / Outline Button",
        "Danger, Success e Warning states",
        "Icon Button e Compact Button",
        "Loading, Disabled e Dropdown Action Button",
    ],
    "fields": [
        "Input text, obrigatorio e opcional",
        "Textarea, checkbox, radio e switch",
        "Field Group, Field Grid e Field Row",
        "Input com hint, erro, readonly e mascara",
        "Field addon com botao acoplado",
    ],
    "selects": [
        "Select simples, com busca e com botao auxiliar",
        "Multi-select premium e combobox",
        "Filter bar simples e advanced filters",
        "Applied filter chips e quick create inline",
        "Quick add aberto, separado do Header Lab",
    ],
    "status": [
        "Status de ciclo documental e estados operacionais",
        "Chips de pessoa, servidor, viajante e viatura",
        "Chips de destino, trecho e filtro aplicado",
        "Chip removivel e chip compacto",
    ],
    "feedback": [
        "Field error, form error e callout",
        "Alert info, warning, success e danger",
        "Empty state, loading state e skeleton",
        "Autosave discreto e pendencias de etapa",
    ],
    "overlays": [
        "Modal pequeno, medio e grande",
        "Confirm dialog e drawer lateral",
        "Popover, tooltip e dropdown menu",
        "Command menu se a demanda evoluir",
    ],
    "tables": [
        "Tabela simples, densa e com acoes",
        "Tabela com selecao e status",
        "Tabela responsiva e empty table",
        "Paginacao padrao e compacta",
    ],
    "documents": [
        "Document Viewer Shell e PDF Preview Area",
        "Viewer Toolbar com zoom e download",
        "Side info panel e document status",
        "Linked documents e generated files panel",
    ],
    "signature": [
        "Signature label, status e action card",
        "Pending signer chip e document action bar",
        "Download PDF/DOCX, preview e copy link",
        "Expired signature state",
    ],
}

UI_LAB_HEADER_STATUS_VARIANTS = [
    {"label": "Rascunho", "modifier": "draft"},
    {"label": "Ativo", "modifier": "active"},
    {"label": "Pendente", "modifier": "pending"},
]

UI_LAB_STEPS = [
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
        "state_class": "is-pending",
        "step_label": "Etapa 4",
        "title": "Justificativa",
        "status": "Aguardando",
        "marker": "4",
        "marker_aria_hidden": False,
    },
    {
        "state_class": "is-pending",
        "step_label": "Etapa 5",
        "title": "Documentos",
        "status": "Aguardando",
        "marker": "5",
        "marker_aria_hidden": False,
    },
    {
        "state_class": "is-disabled",
        "step_label": "Etapa 6",
        "title": "Central de assinaturas",
        "status": "Bloqueada",
        "marker": "6",
        "marker_aria_hidden": True,
    },
]

UI_LAB_FIELDS = {
    "quick_add_header": [
        {"label": "Input exemplo 1", "size_class": "field-size-3"},
        {"label": "Input exemplo 2", "size_class": "field-size-1"},
    ],
    "quick_add_structure": [
        {"label": "Input exemplo 1", "size_class": "field-size-3"},
        {"label": "Input exemplo 2", "size_class": "field-size-1"},
    ],
    "standard_simple": [
        {"label": "Input exemplo 1", "size_class": "field-size-2"},
        {"label": "Input exemplo 2", "size_class": "field-size-2"},
        {"label": "Input exemplo 3", "size_class": "field-size-2"},
        {"label": "Input exemplo 4", "size_class": "field-size-2"},
    ],
    "standard_primary": [
        {"label": "Input exemplo 1", "size_class": "field-size-3"},
        {"label": "Input exemplo 2", "size_class": "field-size-1"},
        {"label": "Input exemplo 3", "size_class": "field-size-2"},
        {"label": "Input exemplo 4", "size_class": "field-size-2"},
        {"label": "Input exemplo 5", "size_class": "field-size-4"},
    ],
    "standard_secondary": [
        {"label": "Input exemplo 6", "size_class": "field-size-2"},
        {"label": "Input exemplo 7", "size_class": "field-size-2"},
        {"label": "Input exemplo 8", "size_class": "field-size-1"},
        {"label": "Input exemplo 9", "size_class": "field-size-1"},
        {"label": "Input exemplo 10", "size_class": "field-size-2"},
    ],
    "wizard_primary": [
        {"label": "Input exemplo 1", "size_class": "field-size-2"},
        {"label": "Input exemplo 2", "size_class": "field-size-1"},
        {"label": "Input exemplo 3", "size_class": "field-size-1"},
    ],
    "wizard_secondary": [
        {"label": "Input exemplo 4", "size_class": "field-size-4"},
        {"label": "Input exemplo 5", "size_class": "field-size-2"},
        {"label": "Input exemplo 6", "size_class": "field-size-2"},
    ],
}

UI_LAB_SIMPLE_ROWS = [
    {
        "avatar": "A1",
        "title": "Item exemplo 1",
        "meta": "Descricao exemplo · Metadado exemplo",
        "status_label": "Status exemplo",
        "status_modifier": "done",
        "action_label": "Acao",
    },
    {
        "avatar": "A2",
        "title": "Item exemplo 2",
        "meta": "Descricao exemplo · Metadado exemplo",
        "status_label": "Status exemplo",
        "status_modifier": "draft",
        "action_label": "Acao",
    },
    {
        "avatar": "A3",
        "title": "Item exemplo 3",
        "meta": "Descricao exemplo · Metadado exemplo",
        "status_label": "Status exemplo",
        "status_modifier": "review",
        "action_label": "Acao",
    },
    {
        "avatar": "A4",
        "title": "Item exemplo 4",
        "meta": "Descricao exemplo · Metadado exemplo",
        "status_label": "Status exemplo",
        "status_modifier": "done",
        "action_label": "Acao",
    },
]

UI_LAB_CARDS = [
    {
        "title": "Card exemplo 1",
        "status_label": "Status exemplo",
        "status_modifier": "draft",
        "meta_items": ["Metadado exemplo", "Metadado exemplo"],
        "description": "Descricao generica do conteudo deste card. Texto de exemplo sem dados reais.",
        "secondary_action": "Acao exemplo",
        "primary_action": "Ver detalhes",
    },
    {
        "title": "Card exemplo 2",
        "status_label": "Status exemplo",
        "status_modifier": "done",
        "meta_items": ["Metadado exemplo", "Metadado exemplo"],
        "description": "Descricao generica do conteudo deste card. Texto de exemplo sem dados reais.",
        "secondary_action": "Acao exemplo",
        "primary_action": "Ver detalhes",
    },
    {
        "title": "Card exemplo 3",
        "status_label": "Status exemplo",
        "status_modifier": "review",
        "meta_items": ["Metadado exemplo", "Metadado exemplo"],
        "description": "Descricao generica do conteudo deste card. Texto de exemplo sem dados reais.",
        "secondary_action": "Acao exemplo",
        "primary_action": "Ver detalhes",
    },
]

UI_LAB_SECTION_TEMPLATES = {
    "structures": "dev/ui_lab/structures.html",
    "headers": "dev/ui_lab/headers.html",
    "buttons": "dev/ui_lab/buttons.html",
    "fields": "dev/ui_lab/fields.html",
    "selects": "dev/ui_lab/selects.html",
    "status": "dev/ui_lab/status.html",
    "feedback": "dev/ui_lab/feedback.html",
    "cards": "dev/ui_lab/cards.html",
    "overlays": "dev/ui_lab/overlays.html",
    "tables": "dev/ui_lab/tables.html",
    "documents": "dev/ui_lab/documents.html",
    "signature": "dev/ui_lab/signature.html",
}


def _build_ui_lab_pages():
    pages = []
    for page in UI_LAB_PAGE_DEFINITIONS:
        item = page.copy()
        route_name = item["route_name"]
        if route_name == "core:ui_lab_section":
            item["url"] = reverse(route_name, kwargs={"section": item["slug"]})
        else:
            item["url"] = reverse(route_name)
        pages.append(item)
    return pages


def _build_ui_lab_context(active_slug):
    pages = _build_ui_lab_pages()
    current_page = next((page for page in pages if page["slug"] == active_slug), None)

    if current_page is None:
        raise Http404

    return {
        "ui_lab_pages": pages,
        "ui_lab_nav_items": pages,
        "ui_lab_overview_cards": [page for page in pages if page["slug"] != "index"],
        "ui_lab_current_page": current_page,
        "ui_lab_page": current_page,
        "ui_lab_header_status_variants": UI_LAB_HEADER_STATUS_VARIANTS,
        "ui_lab_steps": UI_LAB_STEPS,
        "ui_lab_fields": UI_LAB_FIELDS,
        "ui_lab_simple_rows": UI_LAB_SIMPLE_ROWS,
        "ui_lab_cards": UI_LAB_CARDS,
        "ui_lab_status_examples": UI_LAB_STATUS_EXAMPLES,
        "ui_lab_plan_items": UI_LAB_PLAN_ITEMS.get(active_slug, []),
    }


def _render_ui_lab(request, template_name, active_slug):
    return render(request, template_name, _build_ui_lab_context(active_slug))


class LoginView(DjangoLoginView):
    template_name = "core/login.html"
    redirect_authenticated_user = True
    authentication_form = LoginForm


def dashboard(request):
    return render(
        request,
        "core/dashboard.html",
        {
            "page_title": "Central de Viagens 3",
            "page_section": "Dashboard",
            "page_description": "Fundacao visual para os fluxos documentais do sistema.",
        },
    )


def ui_lab(request):
    return ui_lab_index(request)


def ui_lab_index(request):
    return _render_ui_lab(request, "dev/ui_lab/index.html", "index")


def ui_lab_section(request, section):
    template_name = UI_LAB_SECTION_TEMPLATES.get(section)
    if template_name is None:
        raise Http404
    return _render_ui_lab(request, template_name, section)
