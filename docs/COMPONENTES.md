# Catálogo canônico de componentes

Este catálogo descreve a árvore ativa em `templates/components/`. Um componente é nomeado pela responsabilidade que exerce; nomes de página, módulo ou UI Lab não são aceitos em APIs globais.

## Organização

| Área | Responsabilidade | Componentes principais |
| --- | --- | --- |
| `ui/buttons` | ações e controles | `button`, `icon_button`, `field_manage_button`, `floating_action`, `footer_action` |
| `ui/forms` | campos e grupos de formulário | `field`, `form_block`, `date_picker`, `document_number_field`, `card_toggle`, `file_picker`, `select`, `multiselect` |
| `ui/headers` | cabeçalhos globais | `page_header`, `filter_page_header` |
| `ui/feedback` | estados e validação | `alert`, `empty_state`, `field_error`, `form_errors`, `pendencias_card` |
| `ui/badges` | chips e estados | `chip`, `status_badge` |
| `ui/layouts` | seções e rodapés de cards | `form_section`, `collection_header`, `card_footer_section`, `card_footer_actions` |
| `ui/lists` | primitivas de listas e cards | `entity_card*`, `file_list`, `pagination`, `list_card_actions` |
| `ui/modals` | diálogos com comportamento real | `confirm_action_modal`, `confirm_delete`, `delete_confirm_modal`, `attach_signed_modal`, `cancel_reason_modal` |
| `lists` | composições completas de listagem | `list_page_standard`, `list_page_cards`, `list_page_quick_add`, `main_list_card`, `simple_list*` |
| `travel` | conceitos compartilhados de viagem | destinos, trechos e cálculo de diárias |
| `cards`, `documents`, `feedback`, `layout`, `perfil` | composições globais já consumidas por páginas | cards documentais, assinatura/PDF, mensagens Django, sidebar e integração Drive |

## Contratos centrais

### Cabeçalho de página

`components/ui/headers/page_header.html` é o único markup de cabeçalho comum. Suporta:

- faixa de título e status;
- descrição e marcador de módulo;
- ação de retorno ou ação primária;
- stepper por `stepper_template`;
- variante `band_only=True` sem a faixa inferior.

Listagens com busca, filtros, ordenação e período usam `filter_page_header.html`. A estrutura visual histórica foi preservada; a consolidação alterou apenas nomes, includes e responsabilidades.

### Campos

`components/ui/forms/field.html` renderiza o `BoundField` Django e suas mensagens. Variações legítimas têm componentes próprios quando existe comportamento adicional:

- `date_picker.html`: data única ou intervalo, com `cv-date-picker.js`;
- `document_number_field.html`: número e ano sincronizados com campo oculto;
- `card_toggle.html`: booleano apresentado como card;
- `file_picker.html` e `multiselect.html`: controles compostos.

IDs, nomes de campos, validações e valores submetidos continuam definidos pelo backend. Hooks `data-*` globais descrevem comportamento; hooks de módulo só permanecem quando fazem parte do contrato do formulário daquela página.

### Listagens

- `list_page_standard.html`: lista compacta;
- `list_page_cards.html`: cards e filtros avançados;
- `list_page_quick_add.html`: lista com inclusão rápida;
- `list_empty.html`: composição de empty state para listas;
- `ui/lists/pagination.html`: paginação única.

### Botões, status e feedback

- botão base: `ui/buttons/button.html`;
- status semântico: `ui/badges/status_badge.html`, que delega a aparência ao `chip.html`;
- empty state base: `ui/feedback/empty_state.html`;
- mensagens Django: `feedback/alerts.html`;
- exclusão: `feedback/confirm_delete_block.html` ou modal canônico, conforme o fluxo.

## Regras de manutenção

1. Antes de criar um componente, procurar responsabilidade equivalente nesta árvore.
2. Repetição real deve virar parâmetro ou variante legítima do componente canônico.
3. Não criar wrappers que apenas encaminham contexto para outro include.
4. Não manter aliases de compatibilidade sem consumidor e prazo de remoção explícito.
5. CSS de demonstração pertence a `static/css/dev/`; produção não usa seletores `ui-lab-*`.
6. JavaScript global expõe API por responsabilidade (`CV.destinations`), não pelo módulo que a originou.
7. Templates de módulo podem compor componentes globais, mas não duplicar seu markup interno.

Os componentes de viagem e seus parâmetros estão detalhados em `docs/COMPONENTES_DOMINIO.md`.
