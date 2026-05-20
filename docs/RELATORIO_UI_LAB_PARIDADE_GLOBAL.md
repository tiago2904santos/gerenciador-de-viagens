# Relatório de Paridade UI Lab × Sistema Real

## 1. Resumo executivo

### Estado geral da paridade

O UI Lab já contém uma gramática visual ampla para o Central de Viagens: shell, background, headers, estruturas de página, botões, listas, campos, selects, dropdowns, multiselects, toggles e chips. O sistema real usa parte desse padrão, principalmente em Cadastros e em algumas listas de Roteiros/Ofícios, mas ainda mantém uma camada paralela de templates e CSS legados baseada em `app-page-*`, `btn btn-*`, `form-control`, `form-select`, `oficio-wizard__*`, `roteiro-editor__*`, `motivo-card__*` e cards de domínio.

### Principais riscos

- O UI Lab não é apenas documentação: ele contém CSS/JS funcional, mas algumas páginas reais ainda não usam os componentes globais correspondentes.
- Existem duas gerações de UI convivendo: `components/ui/*` e wrappers/legados em `components/forms`, `components/lists`, `components/feedback` e templates de domínio.
- A camada de wizards de Ofícios/Roteiros concentra o maior risco visual e estrutural por usar headers, steppers, actions, cards e selects próprios.
- Existem tokens e classes documentadas/consumidas no UI Lab que estão ausentes, mortos ou divergentes no CSS real.
- Há componentes globais já prontos (`cv-search-picker`, `cv-custom-select`, `cv-dropdown`) ainda não aplicados em fluxos importantes.

### Principais divergências

- `templates/dev/ui_lab/base.html` referencia `static/js/dev/ui-lab-navigation.js`, mas o arquivo não existe.
- `static/css/dev/ui-lab-cv-buttons.css` existe, é grande e duplicado, mas não é carregado.
- `--surface-panel` é usado em CSS do UI Lab e não foi definido nos tokens globais.
- Feedback, overlays, documents, tables e signature têm templates no UI Lab, mas vários estilos de suas classes não existem.
- Inputs `cv-field__control` são completos no UI Lab, mas produção ainda usa majoritariamente `form-control`/`form-select`.
- Há três gramáticas concorrentes de ação lateral em campo: `cv-field-action`, `cv-field-side-action` e `cv-field-control__*`.
- Listas de Roteiros/Ofícios usam cards próprios em vez de consolidar em `components/ui/lists`.
- Wizards de Ofícios usam `oficio-wizard__*`, `btn btn-*`, partial de stepper próprio e selects nativos.
- O editor de Roteiros usa `roteiro-editor__*`, `form-control`, `form-select` e scripts próprios, com picker buscável referenciado mas ausente.
- Chips têm múltiplas famílias: `cv-chip`, `page-header-status-chip`, `header-applied-chip`, `ui-lab-status-pill`, `ui-lab-demo-chip`.

### O que foi corrigido

Nesta fase não foram aplicadas microcorreções em templates/CSS de produção além da criação deste relatório. A auditoria encontrou divergências relevantes demais para correções pontuais seguras sem risco de misturar fases. A recomendação é tratar as correções em fases pequenas, começando por itens sem impacto de negócio: tokens ausentes, arquivos órfãos, includes globais e remoção de dependência do UI Lab em componentes de produção.

### O que ficou pendente

- Componentizar wizards de Ofícios com `wizard_page`, `header_stack_stepper`, `footer_actions` e botões `cv-btn`.
- Migrar editor de Roteiros para `components/ui/forms` e `components/ui/buttons`.
- Consolidar `cv-field__control` em produção.
- Consolidar ações laterais de campo.
- Unificar chips e status.
- Resolver assets mortos/ausentes do UI Lab.
- Integrar dropdowns de filtro do UI Lab com listas reais.

## 2. Inventário do UI Lab

### 2.1 Shell, background e infraestrutura

| Modelo | Origem | CSS relacionado | JS relacionado | Tokens/classes | Estado |
|---|---|---|---|---|---|
| UI Lab shell | `templates/dev/ui_lab/base.html` | `static/css/dev/ui-lab.css` | `theme-init.js`, `theme-toggle.js` | `app-shell--ui-lab`, `ui-lab-page` | Aprovado, mas específico do Lab |
| Background claro/escuro | `ui-lab.css` | `ui-lab.css` | Tema global | gradientes em pseudo-elementos | Divergente do app real |
| Navegação do Lab | `_lab_nav.html` | `ui-lab-navigation.css` | `ui-lab-navigation.js` referenciado | `ui-lab-nav`, `ui-lab-status-pill` | Parcial: JS ausente |
| Hero de documentação | `_lab_page_title.html` | `ui-lab-pages.css` | nenhum | `ui-lab-hero` | Aprovado |

### 2.2 Headers

| Modelo | Origem UI Lab | CSS | JS | Estado |
|---|---|---|---|---|
| Header Band | `headers.html` | `page-shell.css` | nenhum | Aprovado |
| Header Band com status | `headers.html` | `page-shell.css` | nenhum | Aprovado |
| Header Stack Rail Simple | `headers.html` | `page-shell.css` | nenhum | Aprovado |
| Header Stack Rail Back Action | `headers.html` | `page-shell.css` | nenhum | Aprovado; ainda usa `btn` no demo |
| Header Stack Rail Filters | `headers.html` | `page-shell.css` | `realtime-filters.js` em produção | Aprovado |
| Header Stack Rail Advanced Filters | `headers.html` | `page-shell.css` + overrides Lab | `realtime-filters.js` parcial | Aprovado visual; integração filtro avançado pendente |
| Header Stack Filters + Quick Add | `headers.html`, `lists.html`, `structures.html` | `page-shell.css`, `ui-lab-pages.css` | `ui-lab.js` no Lab, `app.js` no real | Em revisão por duplicação |
| Header Stack Stepper | `headers.html` | `page-shell.css` | nenhum | Aprovado, mas pouco usado |

### 2.3 Structures

| Modelo | Origem | CSS | Component real esperado | Estado |
|---|---|---|---|---|
| Standard Simple | `structures.html` | `page-shell.css` | `components/ui/layouts/standard_simple_page.html` | Aprovado |
| Standard | `structures.html` | `page-shell.css` | `components/ui/layouts/standard_page.html` | Aprovado |
| Wizard | `structures.html` | `page-shell.css` | `components/ui/layouts/wizard_page.html` | Aprovado |
| List / Filters | `lists.html` | `page-shell.css` | `components/lists/list_page_standard.html` ou UI equivalente | Aprovado parcial |
| Quick Add | `headers.html`, `lists.html`, `structures.html` | `page-shell.css`, `ui-lab-pages.css` | `components/ui/layouts/quick_add.html` + header global | Duplicado |
| Footer actions | `structures.html` | `cv-buttons.css`, `page-shell.css` | `components/ui/layouts/footer_actions.html` | Aprovado |
| Floating action | `structures.html`, Cadastros | `page-shell.css`, `cv-buttons.css` | `components/ui/buttons/floating_primary_action.html` | Aprovado |

### 2.4 Buttons

| Modelo | Origem | CSS | Component real | Estado |
|---|---|---|---|---|
| Primário | `buttons.html` | `cv-buttons.css` | `components/ui/buttons/button.html` | Aprovado |
| Secundário | `buttons.html` | `cv-buttons.css` | `button.html` | Aprovado |
| Voltar | `buttons.html` | `cv-buttons.css` | `footer_actions.html`/`button.html` | Aprovado |
| Voltar para lista | `buttons.html` | `cv-buttons.css` | `button.html` | Aprovado |
| Excluir/destrutivo | `buttons.html` | `cv-buttons.css` | `button.html`, `icon_button.html` | Aprovado |
| PDF/DOCX | `buttons.html` | `cv-buttons.css` | `icon_button.html` ou variação documental | Aprovado no Lab; pouco aplicado |
| Preview/editar/assinar | `buttons.html` | `cv-buttons.css` | `icon_button.html`, `button.html` | Aprovado |
| Ação em lista | `buttons.html`, `lists.html` | `cv-buttons.css`, `page-shell.css` | `components/ui/lists/list_card_actions.html` | Parcial |
| Gerenciar campo | `fields.html`, `selects_filters.html` | `ui-lab-fields.css`, `cv-select.css`, `cv-buttons.css` | ainda divergente | Duplicado |

### 2.5 Lists e cards

| Modelo | Origem | CSS | JS | Estado |
|---|---|---|---|---|
| Simple list | `lists.html` | `page-shell.css` | `realtime-filters.js` | Aprovado |
| Simple list + quick add | `lists.html` | `page-shell.css` | `app.js` no real, `ui-lab.js` no Lab | Em revisão |
| Card list Roteiros/Ofícios | `lists.html` | `page-shell.css`, `roteiros-list.css` | `realtime-filters.js` | Divergente por card de domínio |
| `cards.html` | `cards.html` | parcial | nenhum | Órfão/duplicado |

### 2.6 Inputs e forms

| Modelo | Origem | CSS | JS | Estado |
|---|---|---|---|---|
| Text input | `fields.html` | `ui-lab-fields.css` | `masks.js` quando aplicável | Aprovado no Lab; não globalizado |
| Textarea | `fields.html` | `ui-lab-fields.css` | nenhum | Aprovado no Lab; produção parcial |
| Date/time/number/money | `fields.html` | `ui-lab-fields.css` | `masks.js` parcial | Aprovado no Lab; produção divergente |
| Error/success/disabled/readonly | `fields.html` | `ui-lab-fields.css` | nenhum | Aprovado no Lab; produção parcial |
| Field grid/group | `fields.html` | `ui-lab-fields.css`, `page-shell.css` | nenhum | Duplicado entre Lab e produção |
| Card toggle | `buttons.html`, Cadastros | `cv-buttons.css`, `forms.css` | `card-toggle.js` | Parcial |

### 2.7 Selects, dropdowns e multiselects

| Modelo | Origem | CSS | JS | Estado |
|---|---|---|---|---|
| Custom select | `selects_filters.html` | `ui-lab-fields.css`, `cv-select.css` | `cv-custom-select.js` | Aprovado; aplicado em Cadastros |
| Select com botão lateral | `selects_filters.html`, `fields.html` | `cv-select.css`, `ui-lab-fields.css` | `cv-custom-select.js` | Aprovado; botão lateral ainda conflita |
| Search picker single | `selects_filters.html` | `cv-search-picker.css` | `cv-search-picker.js` | Aprovado |
| Multiselect | `selects_filters.html` | `cv-search-picker.css` | `cv-search-picker.js` | Aprovado; Ofícios ainda usam legado |
| Action dropdown | `selects_filters.html` | `cv-select.css` | `cv-select.js` | Aprovado; pouco usado no real |
| Filter dropdown | `selects_filters.html` | `cv-select.css` | `cv-select.js` | Aprovado; não integrado às listas reais |

### 2.8 Toggles

| Modelo | Origem | CSS | JS | Estado |
|---|---|---|---|---|
| Toggle possui/não possui | `buttons.html`, Servidores | `cv-buttons.css` | `card-toggle.js` | Aprovado parcial |
| Toggle de estado verde/vermelho | `buttons.html` | `cv-buttons.css` | `card-toggle.js` ou demo | Aprovado |
| Toggle termo por servidor | `selects_filters.html` | `cv-search-picker.css`, `cv-buttons.css` | `cv-search-picker.js` | Aprovado no Lab; não usado em Ofícios |
| Toggle quick add | `headers.html`, `lists.html` | `page-shell.css` | `app.js`, `ui-lab.js` | Duplicado |

### 2.9 Chips e status

| Modelo | Origem | CSS | Estado |
|---|---|---|---|
| `cv-chip` | `status.html`, `components/ui/badges/chip.html` | `utilities.css` | Aprovado |
| Status pill do header | `headers.html` | `page-shell.css` | Aprovado, mas paralelo |
| Applied filter chip | `headers.html` | `page-shell.css` | Divergente de `cv-chip` |
| UI Lab nav status | `_lab_nav.html` | `ui-lab-navigation.css` | Interno ao Lab |
| Demo chip | `lists.html` | `ui-lab-pages.css` | Duplicado |

## 3. Background

### Como está no UI Lab

O UI Lab usa `app-shell--ui-lab` com pseudo-elementos de fundo e gradientes próprios. O tema claro usa tons frios e acentos tipo cyan/lime; o tema escuro usa base azul/preta e blobs neon. Esse fundo vive em `static/css/dev/ui-lab.css`.

### Como está nas páginas reais

As páginas reais usam o shell base (`app-shell`, `app-main`, `content-wrap`) e tokens de tema em `theme.css`, `layout.css`, `base.css`, `sidebar.css`, `page-shell.css` e `app-page.css`. O background institucional real depende de `--app-body-bg`, `--app-featured-bg`, `--theme-*`, `--color-primary`, `--color-accent`.

### Divergências encontradas

- O UI Lab tem uma skin de fundo própria, não tokenizada pelo mesmo conjunto de tokens `--app-*` usado no app.
- Há cores hardcoded em `ui-lab.css`.
- O Lab consome tokens `--surface-*`/`--theme-*`, mas não a API pública `--app-*` documentada nos tokens.
- Páginas reais antigas usam `app-page`/`app-page__shell`, enquanto páginas alinhadas usam `page-shell--standard`, `page-shell--standard-simple`, `page-shell--list` e `page-shell--wizard`.

### Correções aplicadas

Nenhuma. Alterar background é risco visual alto e deve ser tratado como fase específica.

### Pendências

- Decidir se o background do UI Lab é apenas skin de desenvolvimento ou se deve representar o app real.
- Se for fonte da verdade, mover os tokens de background para `theme.css`/`tokens.css` e aplicar no shell real.
- Se não for fonte para o app shell, documentar explicitamente essa exceção.

## 4. Headers

### Header Band

- Modelo no UI Lab: `templates/dev/ui_lab/headers.html`.
- Onde aparece: demos do UI Lab e alguns headers simples via `components/ui/headers`.
- Onde deveria aparecer: páginas sem rail, dashboards ou páginas com contexto mínimo.
- Inconsistências: poucas páginas reais antigas ainda usam `app-page-hero`.
- Páginas afetadas: `cadastros/index.html`, `termos/index.html`, `assinaturas/*`, `oficios/modelos_motivo/*`, `justificativas/modelos/*`.
- Correções aplicadas: nenhuma.
- Pendência: migrar heróis legados para `header_stack_simple` ou `header_band_status`, conforme caso.

### Header Band com status

- Modelo no UI Lab: `page-header-status-chip`.
- Onde aparece: UI Lab e headers com status de fluxo.
- Divergência: status reais usam também `cv-chip`, `status_pill` e chips de domínio.
- Pendência: definir quando status de header deve usar `page-header-status-chip` versus `cv-chip`.

### Header Stack — Rail Simple

- Modelo correto: `components/ui/headers/header_stack_simple.html`.
- Uso real positivo: Cadastros CRUD, Configuração.
- Divergência: vários módulos placeholder não usam `page-shell` + header, apenas card placeholder.
- Pendência: aplicar em Planos de Trabalho, Ordens de Serviço, Prestações, Diário de Bordo, Documentos e Assinaturas index.

### Header Stack — Rail Back Action

- Modelo correto: `components/ui/headers/header_stack_back_action.html`.
- Uso real positivo: `roteiros/roteiro_form_page.html`.
- Divergência: confirm deletes de Ofícios/Roteiros/Modelos ainda usam hero legado.
- Pendência: migrar confirm deletes e páginas de edição com retorno.

### Header Stack — Rail Filters

- Modelo correto: `components/ui/headers/header_stack_filters.html`.
- Uso real positivo: listas de Cadastros, Ofícios e Roteiros.
- Divergência: busca/status misturam GET server-side com filtro DOM client-side.
- Pendência: definir contrato único: filtro local, server-side ou híbrido com URL sincronizada.

### Header Stack — Rail Advanced Filters

- Modelo no UI Lab: filtros avançados com `header-filter-select`, `header-applied-filters`.
- Uso real: parcial em listas de Roteiros/Ofícios.
- Divergência: UI Lab também tem `cv-filter-dropdown`, criando dois padrões de filtro.
- Pendência: decidir se filtros avançados devem usar selects nativos estilizados ou `cv-filter-dropdown`.

### Header Stack — Rail Filters + Quick Add

- Uso real: listas de Cargos, Combustíveis e Unidades.
- Divergência: quick add é implementado inline em `components/lists/list_page_quick_add.html`; existe `components/ui/layouts/quick_add.html` e `_quick_add_inline.html` no UI Lab.
- Pendência: extrair include único e remover duplicações entre Lab/real.

### Header Stack — Rail Stepper

- Modelo correto: `components/ui/headers/header_stack_stepper.html`.
- Uso real: praticamente ausente; wizards de Ofícios usam `oficios/partials/wizard_stepper.html`.
- Pendência crítica: migrar wizards para stepper global.

## 5. Structures

### Standard Simple

- Modelo correto: `page-shell--standard-simple`, header simples, `main-form-panel`, seção, `field-grid`, footer/floating.
- Uso real positivo: Cadastros CRUD.
- Divergências: shell montado manualmente em cada template; layouts globais existem mas são pouco usados.
- Pendência: substituir montagem manual por `standard_simple_page.html` quando possível.

### Standard

- Modelo correto: `page-shell--standard` para páginas mais densas.
- Uso real positivo: Configuração.
- Divergências: Configuração usa marcação manual de seções e tem fechamentos `</section>` sobrando no template, embora renderize.
- Pendência: revisar estrutura sem alterar visual.

### Wizard

- Modelo correto: `page-shell--wizard`, `header_stack_stepper`, `cv-wizard-section-card`, `footer_actions`.
- Uso real divergente: Ofícios e partes de Roteiros usam `oficio-wizard__*`, `app-wizard__*`, partial de stepper próprio e botões Bootstrap.
- Pendência crítica: fase própria para wizards.

### List / Filters

- Modelo correto: `page-shell--list`, `header_stack_filters`, `list-panel`, lista/card componentizados.
- Uso real positivo: Cadastros.
- Divergência: Ofícios/Roteiros usam `main_list_card.html` e `list-grid--roteiros` com card de domínio.
- Pendência: compor card de domínio sobre `components/ui/lists/list_card.html` ou promover card rico como componente global.

### Quick Add

- Modelo correto: UI Lab mostra rail + painel + footer button.
- Uso real: `list_page_quick_add.html`.
- Divergência: lógica JS do Lab (`data-ui-lab-toggle`) e produção (`data-quick-add-toggle`) divergem.
- Pendência: unificar JS e template.

### Cards

- Modelo UI Lab: cards em listas, overview, placeholders.
- Divergência: `cards.html` é órfão; cards reais de domínio usam classes próprias.
- Pendência: mapear slots necessários para cards ricos.

### Footer actions

- Modelo correto: `components/ui/layouts/footer_actions.html`.
- Uso real positivo: Cadastros.
- Divergência: `components/forms/form_actions.html` legado ainda usado em modelos.
- Pendência: remover uso legado.

### Floating actions

- Modelo correto: `floating_primary_action.html`.
- Uso real: Cadastros quick add/form.
- Divergência: não crítica; alias existe.
- Pendência: consolidar alias em documentação.

## 6. Buttons

| Função | Component ideal | Variações encontradas | Páginas afetadas | Correção aplicada | Pendência |
|---|---|---|---|---|---|
| Criar/Novo | `components/ui/buttons/button.html` ou `floating_primary_action` | `btn btn-primary`, `cv-btn`, floating | Termos, Ofícios, Assinaturas, Cadastros | Não | Migrar legados |
| Salvar | `footer_actions.html` | `btn btn-primary`, `cv-btn`, floating | Ofícios, Roteiros, Modelos | Não | Fase forms/wizards |
| Cancelar | `footer_actions.html` | `btn btn-secondary`, links avulsos | Wizards e modelos | Não | Padronizar |
| Voltar | `button.html`/`footer_actions` | `btn btn-secondary`, `header_stack_back_action` | Roteiros, modelos | Não | Consolidar |
| Voltar para lista | `cv-btn--back-list` | `btn`, links textuais | Termos, documentos, assinaturas | Não | Consolidar |
| Excluir | `icon_button`, `button danger` | `btn btn-danger`, `cv-icon-btn--delete` | Confirm deletes, lists | Não | Migrar confirm deletes |
| Remover item | `cv-search-picker__remove` ou icon button | `oficio-viajante-card__remove`, `btn` | Ofícios, search pickers | Não | Migrar para picker global |
| Abrir | `button.html`/`icon_button` | `btn`, `cv-btn`, links | listas e docs | Não | Unificar |
| Editar | `icon_button` | `cv-icon-btn`, `btn` | Listas, documentos | Não | Aplicar global |
| Preview | `button/icon_button` | `btn btn-secondary`, `cv-icon-btn--preview` | Documentos, Ofícios | Não | Migrar PDF viewer |
| PDF | `cv-icon-btn--pdf` | `btn btn-secondary` | Documentos, Ofícios | Não | Migrar ações documentais |
| DOCX | `cv-icon-btn--docx` | `btn btn-secondary` | Documentos, Ofícios | Não | Migrar ações documentais |
| Assinar | `cv-btn--sign`, `icon_button` | `btn`, `cv-chip` em partials | Assinaturas, Ofícios | Não | Fase assinaturas |
| Gerenciar | `cv-field-action` ou `cv-field-side-action` único | ambas as APIs | Cadastros, UI Lab | Não | Escolher API |
| Filtros | `header_stack_filters` + futuro `cv-filter-dropdown` | select nativo, filter dropdown lab | Listas | Não | Integrar |
| Floating action | `floating_primary_action` | correto em Cadastros | Cadastros | Não | Documentar |

## 7. Listas e cards

### Modelo correto

O padrão atual aprovado combina `page-shell--list`, `header_stack_filters`, `list-panel`, `simple_list`/`simple_list_row` para listas simples e cards ricos para Roteiros/Ofícios.

### Modelos divergentes

- `components/lists/main_list_card.html` é card rico de domínio, não derivado de `components/ui/lists/list_card.html`.
- `templates/dev/ui_lab/cards.html` existe, mas não é rota ativa do UI Lab.
- `templates/dev/ui_lab/partials/_simple_list_item.html` e `_list_card.html` são demos paralelos.
- `list_page_quick_add.html` monta header/filtro/painel de quick add inline.

### Páginas afetadas

- Cadastros: aderência alta.
- Roteiros e Ofícios: aderência média no header, baixa/média no card.
- Termos: usa `app-page` simples com botão Bootstrap.
- Placeholders de módulos: usam `app-page__list-card--placeholder`, sem `page-shell`.

### Status badges, CTA clusters e filtros

- `cv-chip` está sólido, mas várias listas ainda usam outros pills.
- CTA clusters de cards ricos são específicos.
- Filtros avançados têm dois modelos concorrentes.

### Correções aplicadas

Nenhuma.

### Pendências

- Decidir se `main_list_card` vira componente UI global rico.
- Remover partials órfãos ou documentar como demos.
- Unificar empty state em `components/ui/feedback/empty_state.html`.

## 8. Inputs/forms

### Inputs padrão

O UI Lab define `cv-field`, `cv-field__label`, `cv-field__control` e estados. Produção ainda usa `form-control` e `form-select` em vários domínios, sobretudo Roteiros e Ofícios.

### Textarea

O UI Lab usa `cv-field__control--textarea`; produção usa `textarea.form-control` ou widgets Django renderizados diretamente.

### Date, number e masked fields

Máscaras globais existem em `masks.js` e são aplicadas via `data-mask`, mas a estrutura visual nem sempre usa `cv-field`.

### Disabled/readonly/error/focus

O UI Lab tem estados completos. Produção tem estados parciais em `forms.css`, com radius/sombra diferentes.

### Field grid e field group

Há `field-grid` no `page-shell.css`, `cv-field-grid` no UI Lab e `app-form-grid` em `forms.css`. A multiplicidade indica necessidade de consolidação.

### Correções aplicadas

Nenhuma.

### Pendências

- Promover `cv-field__control` completo para produção.
- Migrar partials de Roteiros/Ofícios.
- Consolidar `field-grid`, `cv-field-grid` e `app-form-grid`.

## 9. Selects, dropdowns e multiselects

### Modelo correto do UI Lab

- Select simples: `cv-custom-select` com `data-cv-select`.
- Select com botão lateral: `cv-field-with-action` + `cv-custom-select` + `cv-field-action`.
- Select com busca/multiselect: `cv-search-picker`.
- Dropdown de ação: `cv-action-dropdown`.
- Dropdown de filtro: `cv-filter-dropdown`.

### Páginas divergentes

- Ofícios: `wizard_justificativa.html`, `wizard_dados_viajantes.html`, `wizard_transporte.html`.
- Roteiros: `partials/roteiro/sede_destinos.html` e selects criados por JS.
- Wizards: equipe/motorista usam `app-multiselect`, `app-motorista-picker`, `oficios_termos_selector`.

### Classes duplicadas

- `data-app-multiselect` versus `data-cv-search-picker`.
- `data-oficio-picker-search` sem implementação global.
- `header-filter-select` versus `cv-filter-dropdown`.

### Hardcoded

- UI Lab ainda tem inline style em exemplo de dropdown de ação.
- Roteiros cria selects via string JS com classes `form-select`.

### Correções aplicadas

Nenhuma nesta fase.

### Pendências

- Migrar Ofícios para `cv-search-picker`.
- Implementar ou remover `OficioSelectPicker`.
- Conectar `cv-filter-dropdown` a listas reais.

## 10. Toggles

### Modelo correto

O modelo visual mais consistente está em `buttons.html`: `cv-field-side-action--toggle`, estado verde/vermelho e altura compatível com input.

### Páginas afetadas

- Servidores: toggle de RG.
- Cargos/Combustíveis/Cidades: card toggle boolean.
- Roteiros: switch Bootstrap em bate-volta.
- Ofícios: termo/motorista com componentes próprios.

### Divergências

- `card_toggle.html` vive fora de `components/ui`.
- `bate_volta.html` usa `form-check`.
- `cv-search-picker` já tem termo/motorista, mas Ofícios usam scripts e markup próprios.

### Correções aplicadas

Nenhuma.

### Pendências

- Criar/assumir componente UI global de toggle.
- Migrar switches de Roteiros.
- Reusar controles do `cv-search-picker` em Ofícios.

## 11. Chips

### Modelo correto

`components/ui/badges/chip.html` + `.cv-chip` em `utilities.css` deve ser o modelo padrão.

### Chips de status

Existem `page-header-status-chip`, `status_pill`, `cv-chip`, `ui-lab-status-pill`. Precisam de regra clara de uso.

### Chips de filtros

`header-applied-chip` e `filter_chip.html` coexistem. O chip azul padrão deveria ser o mesmo componente.

### Chips de entidade

`cv-chip` cobre entidade, contagem e removível, mas uso real é irregular.

### Chip azul padrão

Está presente em `utilities.css` como tom informativo/entidade, mas algumas páginas usam classes próprias.

### Divergências

- Pílulas do UI Lab para navegação/documentação não devem vazar para produção.
- Badges de cards/listas nem sempre usam `cv-chip`.

### Correções aplicadas

Nenhuma.

### Pendências

- Substituir chips aplicados por `cv-chip`.
- Definir `page-header-status-chip` como exceção de header ou reimplementar sobre `cv-chip`.

## 12. CSS

### Arquivos analisados

- Globais: `tokens.css`, `theme.css`, `base.css`, `layout.css`, `sidebar.css`, `buttons.css`, `buttons-functional.css`, `forms.css`, `lists.css`, `cards.css`, `cv-buttons.css`, `cv-select.css`, `cv-search-picker.css`, `page-shell.css`, `app-page.css`, `app-ui.css`, `dashboard.css`, `roteiros.css`, `roteiros-list.css`, `oficios.css`, `oficios-documentos-inline.css`, `oficios-assinaturas-central.css`, `documentos-viewer.css`, `assinaturas.css`, `signature-public.css`, `utilities.css`.
- Dev/UI Lab: `ui-lab.css`, `ui-lab-navigation.css`, `ui-lab-pages.css`, `ui-lab-fields.css`, `ui-lab-cv-buttons.css`.

### Hardcoded encontrado

- Gradientes/cores em `ui-lab.css`.
- `#ffffff` em canvas de chips do UI Lab sem override dark.
- Vários `rgba()` e px em CSS de domínio (`roteiros.css`, `oficios-documentos-inline.css`, `assinaturas.css`, etc.).
- Inline style em `oficios/wizard_assinaturas.html`, UI Lab selects demo e `documentos/pdf/oficio.html`.

### Duplicações

- `ui-lab-cv-buttons.css` versus `cv-buttons.css`.
- Quick add em `ui-lab-pages.css` versus `page-shell.css`.
- `cv-field-action` em `cv-select.css`, `cv-buttons.css`, `ui-lab-fields.css`.
- `cv-field__control` versus `cv-field-control__input`.
- `ui-lab-status-pill`, `ui-lab-demo-chip`, `cv-chip`, `header-applied-chip`.

### Classes mortas prováveis

- `static/css/dev/ui-lab-cv-buttons.css` inteiro.
- `ui-lab-preview-grid`.
- `ui-lab-placeholder__eyebrow`.
- `filterable-multiselect.js` relacionado a UI antiga.

### Classes exclusivas que deveriam virar component

- `roteiro-editor__*`
- `oficio-wizard__*`
- `motivo-card__*`
- `document-inline-*`
- `assinaturas-*`
- `app-page-hero`

### Tokens ausentes

- `--surface-panel`.
- Tokens globais equivalentes para alguns campos do UI Lab.

### Correções aplicadas

Nenhuma.

### Pendências

- Definir `--surface-panel`.
- Remover CSS morto.
- Mover `cv-field__control` para produção.
- Reduzir CSS por página.

## 13. Templates

| Página | Tipo | Modelo correto esperado | Modelo atual encontrado | Divergência | Correção aplicada | Pendente |
|---|---|---|---|---|---|---|
| `cadastros/servidores/index.html` | Lista | List filters standard | Componente de lista | Baixa | Não | Manter |
| `cadastros/servidores/form.html` | Form | Standard Simple + field components | Quase aderente, bloco RG custom | Média | Não | Toggle global |
| `cadastros/viaturas/form.html` | Form | Standard Simple + selects/picker | Aderente alto | Baixa | Não | Revisar motoristas após unificação |
| `cadastros/cargos/index.html` | Lista quick add | Quick Add global | Aderente, quick add inline | Média | Não | Extrair quick add |
| `cadastros/combustiveis/index.html` | Lista quick add | Quick Add global | Aderente, quick add inline | Média | Não | Extrair quick add |
| `cadastros/unidades/form.html` | Form/multiselect | `cv-search-picker` | Aderente pós-selects | Baixa | Não | Validar CSS final |
| `cadastros/configuracao/form.html` | Form standard | Standard + field components | Aderente parcial | Média | Não | Revisar seções/fechamentos |
| `cadastros/index.html` | Hub | Header/simple page | `app-page-hero` | Alta | Não | Migrar hero |
| `roteiros/index.html` | Lista cards | Header filters + card global | Header ok, card domínio | Média | Não | Card global rico |
| `roteiros/roteiro_form_page.html` | Wizard/form | Wizard global | Header ok, editor custom | Alta | Não | Fase editor |
| `roteiros/includes/_roteiro_editor.html` | Editor | UI forms/cards | `roteiro-editor__*`, Bootstrap | Alta | Não | Fase média/grande |
| `roteiros/confirm_delete.html` | Confirm delete | Standard simple + confirm component | `app-page-hero` | Alta | Não | Migrar |
| `oficios/index.html` | Lista cards | Header filters + card global | Header ok, card domínio | Média | Não | Card global rico |
| `oficios/wizard_base.html` | Wizard | `wizard_page` + stepper global | `oficio-wizard__*` | Crítica | Não | Fase própria |
| `oficios/wizard_dados_viajantes.html` | Wizard step | `cv-search-picker` | `app-multiselect` legado | Alta | Não | Migrar picker |
| `oficios/wizard_transporte.html` | Wizard step | UI fields/selects | picker motorista próprio | Alta | Não | Migrar |
| `oficios/wizard_documentos.html` | Wizard step | Cards/actions globais | botões e cards próprios | Alta | Não | Migrar |
| `oficios/wizard_assinaturas.html` | Wizard step | Cards/actions globais | botões próprios + inline style | Alta | Não | Migrar/remover inline |
| `oficios/modelos_motivo/form.html` | CRUD form | Standard simple | `app-page-hero`, form_actions legado | Alta | Não | Migrar |
| `justificativas/modelos/form.html` | CRUD form | Standard simple | `app-page-hero`, form_actions legado | Alta | Não | Migrar |
| `termos/index.html` | Index/list | Header/page-shell | `app-page`, `btn` | Alta | Não | Migrar |
| `documentos/pdf_viewer.html` | Viewer | Document viewer component | toolbar custom Bootstrap | Alta | Não | Criar viewer global |
| `assinaturas/assinatura_token.html` | Fluxo público | Public flow component | hero/actions próprios | Média/Alta | Não | Fase pública |
| `planos_trabalho/index.html` | Placeholder | Page shell + header + empty state | `app-page__list-card--placeholder` | Média | Não | Migrar placeholder |
| `ordens_servico/index.html` | Placeholder | Page shell + header + empty state | `app-page__list-card--placeholder` | Média | Não | Migrar placeholder |
| `prestacoes_contas/index.html` | Placeholder | Page shell + header + empty state | `app-page__list-card--placeholder` | Média | Não | Migrar placeholder |
| `diario_bordo/index.html` | Placeholder | Page shell + header + empty state | `app-page__list-card--placeholder` | Média | Não | Migrar placeholder |

## 14. Riscos

### O que pode quebrar se for refatorado

- Wizards de Ofícios: dependem de fluxo, autosave, documentos, assinaturas, termos e dados persistidos.
- Editor de Roteiros: contém mapa, destinos dinâmicos, autosave, cálculo de diárias e campos gerados por JS.
- Listas de Ofícios/Roteiros: cards ricos carregam métricas, ações e filtros.
- Assinaturas públicas: fluxo sensível de token, PDF e assinatura.

### Dependência oculta

- Componentes de produção incluem `dev/ui_lab/partials/_cv_icon.html`.
- `data-oficio-picker-search` existe sem implementação aparente.
- `data-copy-value` depende de `assinaturas-central.js` carregado só em alguns contextos.
- `data-cv-filter-dropdown` existe, mas não tem listener de lista real.
- `realtime-filters.js` intercepta limpar filtros sem sincronizar URL.

### Duplicação perigosa

- `app-multiselect` versus `cv-search-picker`.
- `oficios-dados-viajantes.js` versus `oficios-justificativa-wizard.js`.
- `form_actions` legado versus `footer_actions`.
- `form_section` legado versus `ui/layouts/form_section`.
- `main_list_card` versus `ui/lists/list_card`.

### Inconsistência visual grave

- Ofícios/Roteiros wizards.
- Editor de Roteiros.
- Termos e Documentos.
- Modelos de motivo/justificativa.
- Placeholders de módulos.

## 15. Plano de próximas fases

### Correções rápidas

1. Definir ou substituir `--surface-panel`.
2. Remover referência a `ui-lab-navigation.js` ou criar script mínimo.
3. Marcar/remover `ui-lab-cv-buttons.css` como morto.
4. Remover inline style de `oficios/wizard_assinaturas.html`.
5. Trocar `form_actions` legado por `footer_actions` em modelos simples.
6. Migrar confirm deletes simples de Ofícios/Roteiros para o padrão de Cadastros.

### Refatorações médias

1. Migrar `oficios/modelos_motivo` e `justificativas/modelos` para `page-shell`.
2. Migrar placeholders de módulos para `header_stack_simple` + empty state global.
3. Consolidar `cv-field-action` e `cv-field-side-action`.
4. Extrair Quick Add único.
5. Migrar `termos/index.html` e previews simples.

### Refatorações grandes

1. Migrar wizard de Ofícios para `wizard_page`.
2. Migrar editor de Roteiros para fields/buttons globais.
3. Promover card rico de Roteiros/Ofícios para componente UI global.
4. Criar viewer/document actions global para Documentos/Ofícios.
5. Consolidar fluxo público de Assinaturas.

### JS

1. Migrar Ofícios de `app-multiselect` para `cv-search-picker`.
2. Remover `filterable-multiselect.js`.
3. Resolver `OficioSelectPicker`.
4. Extrair helper global para modelo → textarea.
5. Unificar quick add do UI Lab e produção.
6. Integrar `cv-filter-dropdown` com `realtime-filters.js`.

### Testes visuais

1. Criar roteiro visual para UI Lab × Cadastros.
2. Criar roteiro visual para UI Lab × Ofícios wizard.
3. Criar roteiro visual para UI Lab × Roteiros editor.
4. Validar dark/light com screenshots pareados.
5. Adicionar verificação de ausência de `btn btn-*` em templates migrados.

## 16. Checklist final

### `manage.py check`

- `.venv/bin/python manage.py check`: executado; falhou porque `config.settings.dev` exige `DB_NAME`, `DB_USER` e `DB_PASSWORD` no `.env` local.
- `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py check`: executado com sucesso, sem issues.

### Testes executados

- `DJANGO_SETTINGS_MODULE=config.settings.test .venv/bin/python manage.py test cadastros.tests.test_crud_cadastros_estrutura.ServidorCrudTests cadastros.tests.test_crud_cadastros_estrutura.ViaturaCrudTests cadastros.tests.test_crud_cadastros_estrutura.CargoCrudTests cadastros.tests.test_crud_cadastros_estrutura.CombustivelCrudTests`: executado com sucesso.
- A suíte completa não foi rodada porque a fase produziu relatório documental e já havia testes de cadastros antigos com falhas conhecidas/não relacionadas em execuções anteriores.

### Páginas inspecionadas

- UI Lab: headers, structures, buttons, lists, fields, selects_filters, status, feedback, overlays, tables, documents, signature, cards.
- Cadastros: servidores, viaturas, cargos, combustíveis, unidades, configuração, cidades/estados e hub.
- Roteiros: index, detail, form page, editor partials, confirm delete.
- Ofícios: index, wizard base, etapas principais, modelos de motivo, confirm delete.
- Termos: index e preview.
- Justificativas: modelos.
- Documentos: index e PDF viewer.
- Assinaturas: index e fluxo público.
- Placeholders: planos de trabalho, ordens de serviço, prestações de contas, diário de bordo.

### Arquivos alterados

- `docs/RELATORIO_UI_LAB_PARIDADE_GLOBAL.md`

### Arquivos criados

- `docs/RELATORIO_UI_LAB_PARIDADE_GLOBAL.md`

### Pendências

- Todas as correções visuais/estruturais listadas acima permanecem pendentes para fases próprias.
- Nenhum model, migration ou regra de banco foi alterado.
- Nenhum JS foi alterado nesta fase.
