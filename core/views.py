from django.contrib.auth.views import LoginView as DjangoLoginView
from django.http import Http404
from django.shortcuts import render
from django.urls import reverse

from eventos.forms import EventoForm
from eventos.models import Evento

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
        "subtitle": "Layouts de shell, formularios e wizards em nivel de pagina.",
        "summary": "Quick Add Inline, Standard Simple, Standard e Wizard.",
        "status_label": "Pronto",
        "status_modifier": "done",
        "route_name": "core:ui_lab_structures",
    },
    {
        "slug": "eventos-cadastro",
        "label": "Eventos / Cadastro",
        "mark": "EV",
        "title": "Cadastro de Evento",
        "subtitle": "Laboratorio visual do formulario de Eventos usando padroes existentes.",
        "summary": "Header, cards, grid, campos, chips e rodape clonados dos cadastros maduros.",
        "status_label": "Em revisao",
        "status_modifier": "review",
        "route_name": "core:ui_lab_eventos_cadastro",
    },
    {
        "slug": "eventos-lista",
        "label": "Eventos / Lista",
        "mark": "EV",
        "title": "Lista & Painel de Eventos",
        "subtitle": "Laboratorio da lista e do card de eventos clonando Roteiros e Oficios.",
        "summary": "Lista de eventos em cards, filtro em tempo real, chips de status e estado vazio.",
        "status_label": "Em revisao",
        "status_modifier": "review",
        "route_name": "core:ui_lab_eventos_lista",
    },
    {
        "slug": "lists",
        "label": "Lists",
        "mark": "LS",
        "title": "Lists",
        "subtitle": "Lista standard, quick add e cards em uma página dedicada.",
        "summary": "Lista standard, quick add e cards com paginação.",
        "status_label": "Pronto",
        "status_modifier": "done",
        "route_name": "core:ui_lab_lists",
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
        "route_name": "core:ui_lab_headers",
    },
    {
        "slug": "buttons",
        "label": "Buttons",
        "mark": "BT",
        "title": "Buttons",
        "subtitle": "Taxonomia funcional de botoes: form, navegacao, wizard, documento e destrutivos.",
        "summary": "Hierarquia, document actions com identidade propria, Excluir vs Remover, estados e icon buttons.",
        "status_label": "Em construcao",
        "status_modifier": "build",
        "route_name": "core:ui_lab_buttons",
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
        "route_name": "core:ui_lab_fields",
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
        "route_name": "core:ui_lab_selects_filters",
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
        "route_name": "core:ui_lab_status",
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
        "route_name": "core:ui_lab_feedback",
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
        "route_name": "core:ui_lab_overlays",
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
        "route_name": "core:ui_lab_tables",
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
        "route_name": "core:ui_lab_documents",
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
        "route_name": "core:ui_lab_signature",
    },
]

UI_LAB_STATUS_EXAMPLES = [
    {"label": "Rascunho", "tone": "warning"},
    {"label": "Finalizado", "tone": "success"},
    {"label": "Pendente", "tone": "pending"},
    {"label": "Assinado", "tone": "success"},
    {"label": "Cancelado", "tone": "danger"},
    {"label": "Ativo", "tone": "success"},
    {"label": "Inativo", "tone": "muted"},
    {"label": "Bloqueado", "tone": "danger"},
    {"label": "Retificado", "tone": "info"},
    {"label": "Com pendência", "tone": "warning"},
    {"label": "Sem RG", "tone": "neutral"},
    {"label": "Ligado", "tone": "success"},
    {"label": "Desligado", "tone": "muted"},
]

UI_LAB_CHIP_GROUPS = [
    {
        "title": "Status documentais",
        "description": "Ciclo de vida de documentos e decisões formais.",
        "items": [
            ("Rascunho", "warning"), ("Em preenchimento", "info"), ("Pendente", "pending"),
            ("Em análise", "info"), ("Aguardando validação", "pending"), ("Aguardando assinatura", "pending"),
            ("Assinado", "success"), ("Finalizado", "success"), ("Cancelado", "danger"),
            ("Indeferido", "danger"), ("Deferido", "success"), ("Retificado", "info"),
            ("Com pendência", "warning"), ("Expirado", "danger"), ("Arquivado", "muted"),
        ],
    },
    {
        "title": "Status operacionais",
        "description": "Disponibilidade e estado operacional de recursos.",
        "items": [
            ("Ativo", "success"), ("Inativo", "muted"), ("Bloqueado", "danger"),
            ("Suspenso", "warning"), ("Ligado", "success"), ("Desligado", "muted"),
            ("Disponível", "success"), ("Indisponível", "danger"), ("Ocupado", "warning"),
            ("Em uso", "info"), ("Reservado", "pending"), ("Manutenção", "warning"),
        ],
    },
    {
        "title": "Cadastro e integridade",
        "description": "Completude, verificação e pendências estruturais.",
        "items": [
            ("Completo", "success"), ("Incompleto", "warning"), ("Verificado", "success"),
            ("Não verificado", "pending"), ("Com erro", "danger"), ("Sem erro", "success"),
            ("Sem RG", "neutral"), ("Com RG", "info"), ("Sem assinatura", "warning"),
            ("Assinatura pendente", "pending"),
        ],
    },
    {
        "title": "Chips de entidade",
        "description": "Identificação rápida de objetos recorrentes no domínio.",
        "family": "entity",
        "items": [
            ("Servidor", "entity"), ("Viajante", "entity"), ("Viatura", "entity"),
            ("Motorista", "entity"), ("Destino", "entity"), ("Trecho", "entity"),
            ("Unidade", "entity"), ("Evento", "entity"), ("Documento", "entity"),
            ("Roteiro", "entity"),
        ],
    },
    {
        "title": "Filtros aplicados",
        "description": "Chips removíveis usados em barras de filtro e buscas.",
        "family": "filter",
        "removable": True,
        "items": [
            ("Curitiba", "filter"), ("Últimos 30 dias", "filter"), ("Ativos", "filter"),
            ("Com pendência", "filter"), ("Tipo: Ofício", "filter"), ("Ordenação: recentes", "filter"),
        ],
    },
]

UI_LAB_CHIP_VARIATIONS = [
    {"label": "Simples", "tone": "info"},
    {"label": "Com ícone", "tone": "success", "icon": "✓"},
    {"label": "Selecionável", "tone": "entity", "family": "interactive", "selected": True},
    {"label": "Toggle", "tone": "warning", "family": "interactive", "icon": "●"},
    {"label": "Removível", "tone": "filter", "family": "removable", "removable": True},
    {"label": "Contagem", "tone": "info", "count": "12"},
    {"label": "Compacto", "tone": "neutral", "size": "compact"},
    {"label": "Desabilitado", "tone": "muted", "disabled": True},
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
    "lists": [
        "Lista simples com avatar, titulo e status",
        "Lista com cards, descricao e metadados",
        "Estado vazio com acao contextual",
        "Pagination shell com paginas anterior e proxima",
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
        "edit_url": "#",
        "delete_url": "#",
        "meta": "Descricao exemplo · Metadado exemplo",
        "status_label": "Status exemplo",
        "status_modifier": "done",
        "action_label": "Acao",
    },
    {
        "avatar": "A2",
        "title": "Item exemplo 2",
        "edit_url": "#",
        "delete_url": "#",
        "meta": "Descricao exemplo · Metadado exemplo",
        "status_label": "Status exemplo",
        "status_modifier": "draft",
        "action_label": "Acao",
    },
    {
        "avatar": "A3",
        "title": "Item exemplo 3",
        "edit_url": "#",
        "delete_url": "#",
        "meta": "Descricao exemplo · Metadado exemplo",
        "status_label": "Status exemplo",
        "status_modifier": "review",
        "action_label": "Acao",
    },
    {
        "avatar": "A4",
        "title": "Item exemplo 4",
        "edit_url": "#",
        "delete_url": "#",
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

UI_LAB_ROTEIROS_CARDS = [
    {
        "title": "CURITIBA/PR \u2192 LONDRINA/PR",
        "subtitle": "Roteiro reutiliz\u00e1vel para documentos",
        "status_chip_label": "RASCUNHO",
        "status_chip_class": "status-chip--draft",
        "status_variant": "rascunho",
        "trechos": [
            {
                "rota": "CURITIBA/PR \u2192 LONDRINA/PR",
                "saida": "27/05/2026 13:01",
                "chegada": "27/05/2026 18:01",
            },
            {
                "rota": "LONDRINA/PR \u2192 CURITIBA/PR",
                "saida": "29/05/2026 18:01",
                "chegada": "29/05/2026 23:01",
            },
        ],
        "trechos_count": 2,
        "diaria_moeda": "R$ 150,00",
        "diaria_composicao_linhas": ["2"],
        "actions": [
            {"href": "#", "label": "Abrir", "variant": "secondary"},
            {"href": "#", "label": "Editar", "variant": "secondary"},
            {"href": "#", "label": "Excluir", "variant": "danger"},
        ],
    },
    {
        "title": "CURITIBA/PR \u2192 LONDRINA/PR",
        "subtitle": "Roteiro reutiliz\u00e1vel para documentos",
        "status_chip_label": "RASCUNHO",
        "status_chip_class": "status-chip--draft",
        "status_variant": "rascunho",
        "trechos": [
            {
                "rota": "CURITIBA/PR \u2192 LONDRINA/PR",
                "saida": "26/05/2026 13:01",
                "chegada": "26/05/2026 18:01",
            },
            {
                "rota": "LONDRINA/PR \u2192 CURITIBA/PR",
                "saida": "28/05/2026 18:01",
                "chegada": "28/05/2026 23:01",
            },
        ],
        "trechos_count": 2,
        "diaria_moeda": "R$ 150,00",
        "diaria_composicao_linhas": ["2"],
        "actions": [
            {"href": "#", "label": "Abrir", "variant": "secondary"},
            {"href": "#", "label": "Editar", "variant": "secondary"},
            {"href": "#", "label": "Excluir", "variant": "danger"},
        ],
    },
    {
        "title": "CURITIBA/PR \u2192 LONDRINA/PR",
        "subtitle": "Roteiro reutiliz\u00e1vel para documentos",
        "status_chip_label": "RASCUNHO",
        "status_chip_class": "status-chip--draft",
        "status_variant": "rascunho",
        "trechos": [
            {
                "rota": "CURITIBA/PR \u2192 LONDRINA/PR",
                "saida": "25/05/2026 13:01",
                "chegada": "25/05/2026 18:01",
            },
            {
                "rota": "LONDRINA/PR \u2192 CURITIBA/PR",
                "saida": "27/05/2026 18:01",
                "chegada": "27/05/2026 23:01",
            },
        ],
        "trechos_count": 2,
        "diaria_moeda": "R$ 150,00",
        "diaria_composicao_linhas": ["2"],
        "actions": [
            {"href": "#", "label": "Abrir", "variant": "secondary"},
            {"href": "#", "label": "Editar", "variant": "secondary"},
            {"href": "#", "label": "Excluir", "variant": "danger"},
        ],
    },
]


UI_LAB_EVENTOS_STATUS_OPTIONS = [
    {"value": "", "label": "Todos os status"},
    {"value": "rascunho", "label": "Rascunho"},
    {"value": "em_preparacao", "label": "Em preparacao"},
    {"value": "documentos_gerados", "label": "Documentos gerados"},
    {"value": "em_execucao", "label": "Em execucao"},
    {"value": "prestacao_pendente", "label": "Prestacao pendente"},
    {"value": "finalizado", "label": "Finalizado"},
    {"value": "cancelado", "label": "Cancelado"},
]


def _ui_lab_evento_card(
    *,
    titulo,
    status_variant,
    status_label,
    status_tone,
    destino,
    periodo,
    responsavel,
    unidade,
    oficios,
    documentos,
    pendencias,
    drive,
    href="#",
):
    """Monta um card de evento no formato esperado por main_list_card.html.

    Mesmo contrato usado por Roteiros/Oficios: title, subtitle, status chip,
    meta (coluna esquerda), number/side_items (coluna direita) e actions.
    """

    return {
        "title": titulo,
        "subtitle": f"{destino} · {periodo}",
        "status_variant": status_variant,
        "status_chip_label": status_label,
        "status_chip_class": f"status-chip--{status_tone}",
        "meta": [
            {"label": "Destino", "value": destino},
            {"label": "Periodo", "value": periodo},
            {"label": "Responsavel", "value": responsavel},
            {"label": "Unidade", "value": unidade},
        ],
        "side_title": "Resumo",
        "number_label": "Documentos",
        "number": str(documentos),
        "side_items": [
            {"label": "Oficios", "value": str(oficios), "strong": True},
            {"label": "Pendencias", "value": str(pendencias)},
            {"label": "Drive", "value": drive},
        ],
        "actions": [
            {"label": "Abrir painel", "variant": "secondary", "href": href},
        ],
    }


UI_LAB_EVENTOS_CARDS = [
    _ui_lab_evento_card(
        titulo="Reuniao de planejamento regional",
        status_variant="rascunho",
        status_label="Rascunho",
        status_tone="warning",
        destino="Curitiba/PR",
        periodo="A definir",
        responsavel="Nao definido",
        unidade="DPC",
        oficios=0,
        documentos=0,
        pendencias=3,
        drive="Nao vinculado",
    ),
    _ui_lab_evento_card(
        titulo="Operacao Integrada Litoral",
        status_variant="em_preparacao",
        status_label="Em preparacao",
        status_tone="info",
        destino="Paranagua/PR",
        periodo="20/06 a 22/06/2026",
        responsavel="Del. Marina Alves",
        unidade="1a DRP",
        oficios=2,
        documentos=3,
        pendencias=2,
        drive="Vinculado",
    ),
    _ui_lab_evento_card(
        titulo="Capacitacao de Agentes",
        status_variant="documentos_gerados",
        status_label="Documentos gerados",
        status_tone="info",
        destino="Londrina/PR",
        periodo="01/07 a 03/07/2026",
        responsavel="Insp. Carlos Lima",
        unidade="Academia",
        oficios=4,
        documentos=6,
        pendencias=1,
        drive="Vinculado",
    ),
    _ui_lab_evento_card(
        titulo="Forca-Tarefa Fronteira",
        status_variant="em_execucao",
        status_label="Em execucao",
        status_tone="pending",
        destino="Foz do Iguacu/PR",
        periodo="12/06 a 16/06/2026",
        responsavel="Cap. Ana Souza",
        unidade="BPFRON",
        oficios=6,
        documentos=9,
        pendencias=0,
        drive="Vinculado",
    ),
    _ui_lab_evento_card(
        titulo="Seminario Estadual de Seguranca",
        status_variant="prestacao_pendente",
        status_label="Prestacao pendente",
        status_tone="warning",
        destino="Maringa/PR",
        periodo="02/05 a 04/05/2026",
        responsavel="Del. Paulo Reis",
        unidade="DRACO",
        oficios=3,
        documentos=5,
        pendencias=2,
        drive="Vinculado",
    ),
    _ui_lab_evento_card(
        titulo="Diligencia Externa - Operacao Aurora",
        status_variant="finalizado",
        status_label="Finalizado",
        status_tone="success",
        destino="Sao Paulo/SP",
        periodo="10/04 a 12/04/2026",
        responsavel="Esc. Julia Nunes",
        unidade="DENARC",
        oficios=5,
        documentos=8,
        pendencias=0,
        drive="Vinculado",
    ),
    _ui_lab_evento_card(
        titulo="Visita Tecnica Interinstitucional",
        status_variant="cancelado",
        status_label="Cancelado",
        status_tone="danger",
        destino="Cascavel/PR",
        periodo="18/03/2026",
        responsavel="Nao definido",
        unidade="DPC",
        oficios=1,
        documentos=1,
        pendencias=0,
        drive="Nao vinculado",
    ),
]


def _build_ui_lab_pages():
    pages = []
    for page in UI_LAB_PAGE_DEFINITIONS:
        item = page.copy()
        item["url"] = reverse(item["route_name"])
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
        "ui_lab_roteiros_cards": UI_LAB_ROTEIROS_CARDS,
        "ui_lab_status_examples": UI_LAB_STATUS_EXAMPLES,
        "ui_lab_chip_groups": UI_LAB_CHIP_GROUPS,
        "ui_lab_chip_variations": UI_LAB_CHIP_VARIATIONS,
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


def ui_lab_structures(request):
    return _render_ui_lab(request, "dev/ui_lab/structures.html", "structures")


def ui_lab_eventos_cadastro(request):
    create_form = EventoForm(
        initial={
            "titulo": "Operacao integrada de atendimento institucional",
            "descricao": "Evento com descricao longa para validar quebra de linha, responsividade e leitura em modo claro e escuro.",
            "destino_uf": "PR",
            "destino_cidade": "Curitiba",
            "data_inicio": "2026-06-17",
            "data_fim": "2026-06-18",
            "horario_inicio": "08:00",
            "horario_fim": "18:00",
            "status": Evento.STATUS_RASCUNHO,
            "drive_folder_url": "https://drive.google.com/drive/folders/exemplo",
        }
    )
    edit_evento = Evento(
        pk=999,
        titulo="Evento institucional em revisao",
        descricao="Estado de edicao com dados ja persistidos para validar CTA do painel e status.",
        destino_uf="PR",
        destino_cidade="Londrina",
        data_inicio="2026-07-02",
        data_fim="2026-07-04",
        horario_inicio="09:00",
        horario_fim="17:30",
        status=Evento.STATUS_EM_PREPARACAO,
        drive_folder_url="",
    )
    edit_form = EventoForm(instance=edit_evento)
    context = _build_ui_lab_context("eventos-cadastro")
    context.update(
        {
            "evento_create_form": create_form,
            "evento_edit_form": edit_form,
            "evento_edit_mock": edit_evento,
        }
    )
    return render(request, "dev/ui_lab/eventos_cadastro.html", context)


def ui_lab_eventos_lista(request):
    context = _build_ui_lab_context("eventos-lista")
    context.update(
        {
            "eventos_lab_cards": UI_LAB_EVENTOS_CARDS,
            "eventos_lab_status_options": UI_LAB_EVENTOS_STATUS_OPTIONS,
        }
    )
    return render(request, "dev/ui_lab/eventos_lista.html", context)


def ui_lab_headers(request):
    return _render_ui_lab(request, "dev/ui_lab/headers.html", "headers")


def ui_lab_buttons(request):
    return _render_ui_lab(request, "dev/ui_lab/buttons.html", "buttons")


def ui_lab_fields(request):
    return _render_ui_lab(request, "dev/ui_lab/fields.html", "fields")


def ui_lab_selects_filters(request):
    return _render_ui_lab(request, "dev/ui_lab/selects_filters.html", "selects")


def ui_lab_status(request):
    return _render_ui_lab(request, "dev/ui_lab/status.html", "status")


def ui_lab_feedback(request):
    return _render_ui_lab(request, "dev/ui_lab/feedback.html", "feedback")


def ui_lab_lists(request):
    return _render_ui_lab(request, "dev/ui_lab/lists.html", "lists")


def ui_lab_cards(request):
    return ui_lab_lists(request)


def ui_lab_overlays(request):
    return _render_ui_lab(request, "dev/ui_lab/overlays.html", "overlays")


def ui_lab_tables(request):
    return _render_ui_lab(request, "dev/ui_lab/tables.html", "tables")


def ui_lab_documents(request):
    return _render_ui_lab(request, "dev/ui_lab/documents.html", "documents")


def ui_lab_signature(request):
    return _render_ui_lab(request, "dev/ui_lab/signature.html", "signature")
