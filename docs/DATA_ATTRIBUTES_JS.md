# Contrato de data attributes — JavaScript

Referência mínima para motores globais da Central de Viagens. Não altera regra de negócio.

## HTTP (`window.CV.http`)

Carregado em `base.html` via `static/js/core/http.js`.

| API | Uso |
|-----|-----|
| `getCsrfToken(form?)` | Token do input CSRF no form ou cookie `csrftoken` |
| `readJsonResponse(response)` | `{ ok, status, data }` com fallback para JSON inválido |
| `fetchJson(url, options)` | `fetch` com `credentials: same-origin`, headers padrão |

`options`: `method`, `body` (objeto → JSON, FormData, string), `form`, `headers`, `signal`, `rawResponse`.

## Quick Add (`core/app.js`)

| Atributo | Elemento | Comportamento |
|----------|----------|---------------|
| `data-quick-add-toggle` | botão | ID do painel (ou use `aria-controls`) |
| `aria-controls` | botão | ID alternativo do painel |
| `data-quick-add-close` | botão no painel | Fecha o painel |
| `data-quick-edit` | botão lista | Abre painel em modo edição (`data-edit-url`, `data-edit-fields`) |

Painel: `#id` com classe `quick-add-panel` (ou equivalente com transição `is-open`).

## Filtros em tempo real (`realtime-filters.js` / `CV.filters`)

| Atributo | Elemento | Obrigatório |
|----------|----------|-------------|
| `data-cv-realtime-filter-scope` | container da lista/cards | sim (escopo) |
| `data-cv-filter="search"` | `input` texto/busca | opcional |
| `data-cv-filter="status"` | `select` status | opcional |
| `data-cv-filter-item` | linha, card, item da lista | sim (por item) |
| `data-search-text` | texto indexado (preferencial) | recomendado |
| `data-status-value` | valor do status do item | se filtrar status |
| `data-cv-empty-state` | bloco empty (fica `hidden` quando há itens) | opcional |
| `data-cv-results-count` | elemento do contador | opcional |
| `data-cv-results-count-template` | template do contador (`{{visible}}`, `{{total}}`) | opcional |
| `data-cv-filter-clear` | botão limpar | opcional |
| `data-cv-filter-bound` | escopo (interno) | idempotência |

API oficial:

| API | Uso |
|-----|-----|
| `window.CV.filters.init(root?)` | Inicializa filtros em `document` ou subárvore |
| `window.CV.filters.update(scope)` | Recalcula visibilidade de um escopo |
| `window.CV.filters.clear(scope)` | Limpa busca/status e reaplica |
| `window.CV.filters.getState(scope)` | Último estado `{ scope, total, visible, hidden, state }` |

Compatibilidade: `window.CVRealtimeFilters` delega para `CV.filters` (`init`, `applyFilters`, `update`, `clear`, `getState`, `normalizeText`, `matchesFilter`).

Evento: `cv:filters:updated` — `detail`: `{ scope, total, visible, hidden, state }`.

Busca: case-insensitive, sem acento (`normalize('NFD')`), trim, várias palavras com **AND** (todas devem aparecer em `data-search-text` ou `textContent`).

Status: compara `data-status-value` normalizado com o valor do `select`; vazio = todos.

Limpar: `data-cv-filter-clear` zera inputs do escopo, não submete form, não altera querystring nesta fase.

Inicialização global em `DOMContentLoaded`. **Não** é chamado por `CV.fields.init` (motores separados para evitar ordem/duplicação em painéis dinâmicos).

Exemplo após DOM dinâmico:

```javascript
window.CV.filters.init(panelElement);
```

## Máscaras (`masks.js` / `MaskEngine`)

| Atributo | Elemento | Valores |
|----------|----------|---------|
| `data-mask` | `input`, `textarea` | `upper`, `cpf`, `rg`, `placa`, `cep`, `telefone`, `protocolo` |
| `data-mask-bound` | campo (interno) | `true` após bind — evita listeners duplicados |

API:

| Método | Uso |
|--------|-----|
| `MaskEngine.scan(root?)` | Inicializa campos em `document` ou subárvore |
| `MaskEngine.apply(input)` | Aplica máscara ao valor atual |
| `MaskEngine.format(value, mask)` | Formata string sem DOM |

Aliases: `window.CV.masks` = `window.MaskEngine`.

Exemplo após DOM dinâmico (Quick Add):

```javascript
window.MaskEngine.scan(panelElement);
```

Chamado automaticamente em `core/app.js` ao abrir painel Quick Add / quick edit.

## State Toggle (`state-toggle.js`)

| Atributo | Elemento | Uso |
|----------|----------|-----|
| `data-cv-state-toggle` | container (ex.: `form`) | Escopo do toggle |
| `data-cv-state-binary` | container | Modo botão único + checkbox |
| `data-cv-state-option` | botão | Opção em grupo (com `data-value`) |
| `data-value` | opção | Valor aplicado ao input |
| `data-cv-state-input` | input / seletor | Campo sincronizado (opcional; padrão: primeiro checkbox) |
| `data-cv-state-trigger` | botão | Gatilho binário (alternativa a `data-rg-toggle`) |
| `data-active-label` | botão/container | Label quando ativo |
| `data-inactive-label` | botão/container | Label quando inativo |
| `data-rg-toggle` | botão | Legado — RG servidor (binário) |
| `data-motorista-fixo-toggle` | botão | Legado — motorista viatura (binário) |
| `data-cv-state-bound` | container (interno) | Idempotência |

Classes visuais: `is-active`, `is-inactive`, `cv-field-side-action--success`, `cv-field-side-action--danger`.

API: `window.CV.stateToggle.init(root?)`, `window.CV.stateToggle.update(group, value)`.

Evento: `cv:state-toggle:change` — `detail`: `{ value, input, toggle, fromUser? }`.

## Autosave (`autosave.js`)

| Atributo | Form |
|----------|------|
| `data-autosave="true"` | ativa motor |
| `data-autosave-model` | chave snapshots/validators |
| `data-autosave-url` / `data-autosave-create-url` | endpoints |

Hooks: `window.AppAutosaveSnapshots[model]`, `window.AppAutosaveValidators[model]`.

## Fields Init (`fields-init.js`)

Orquestrador carregado após os motores em `base.html`.

| API | Uso |
|-----|-----|
| `window.CV.fields.init(root?)` | Inicializa máscaras, toggles, selects, pickers e dropdowns na subárvore |
| `window.CV.initFields` | Alias de `CV.fields.init` |
| `window.CV.fields.initSelects(root?)` | Apenas `cv-custom-select` |
| `window.CV.fields.initSearchPickers(root?)` | Apenas search picker |
| `window.CV.fields.initDropdowns(root?)` | Apenas `cv-select` |
| `window.CV.fields.initMultiselects(root?)` | Apenas `app-multiselect` (se script carregado) |

Evento: `cv:fields:init` — `detail.initialized`: `{ masks, stateToggles, selects, searchPickers, dropdowns, multiselects, filterableMultiselects }`.

Ordem interna: masks → stateToggle → customSelect → searchPicker → dropdowns → multiselect → filterableMultiselect.

Exemplo após DOM dinâmico:

```javascript
window.CV.fields.init(panelElement);
```

Quick Add chama `CV.fields.init(panel)` automaticamente em `core/app.js`.  
`OficioWizard.refreshSelectPickers(root)` delega para `CV.fields.init(root)`.

## Selects / dropdowns (motores individuais)

| Motor | Seletor | API |
|-------|---------|-----|
| `cv-custom-select.js` | `[data-cv-select]` (wrapper) | `CV.customSelect.init(root)` |
| `cv-search-picker.js` | `select[data-cv-search-picker]` | `CV.searchPicker.init(root)` |
| `cv-select.js` | `[data-cv-dropdown]`, `[data-cv-filter-dropdown]` | `CV.dropdowns.init(root)` |
| `app-multiselect.js` | `select[data-app-multiselect]` | `CV.multiselect.init(root)` |
| `filterable-multiselect.js` | `input[data-filterable-multiselect-input]` | `CV.filterableMultiselect.init(root)` (se carregado) |

Marcadores de idempotência: `_cvSelect`, `data-cv-search-picker-ready`, `_cvDropdownReady`, `data-app-multiselect-ready`, `data-cv-select-bound`.

## Configurações CEP

| Atributo | Uso |
|----------|-----|
| `data-configuracoes-form` | form root |
| `data-cep-lookup-url-template` | URL com `00000000` |

## Roteiro / mapa (domínio — não unificar nesta fase)

Atributos no `#roteiro-editor-form`: `data-api-calcular-rota-url`, `data-api-calcular-rota-preview-url`, `data-url-trechos-estimar`, `data-api-cidades-url`, `data-api-diarias-url`.

Bridge: `window.RoteirosEditor`, `window.RoteirosMap`.
