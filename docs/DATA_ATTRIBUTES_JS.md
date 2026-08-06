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

## Coleções (`collection.js` / `CV.collection`)

Cada lista declara exatamente um modo. `client` filtra os itens já renderizados;
`server` envia os filtros por GET, troca apenas `.list-panel` e atualiza a URL.

| Atributo | Elemento | Obrigatório |
|----------|----------|-------------|
| `data-collection` | container da lista/cards | sim |
| `data-collection-mode="client|server"` | container | sim |
| `data-collection-form` | `form` GET | no modo `server` |
| `data-collection-filter="search|status|select|date"` | controle | sim por filtro |
| `data-collection-item` | linha, card, item | no modo `client` |
| `data-search-text` | item | recomendado no modo `client` |
| `data-status-value` | item | se filtrar status no cliente |
| `data-collection-container` | container dos itens | opcional |
| `data-collection-empty` | estado vazio | opcional |
| `data-collection-count` | contador | opcional |
| `data-collection-count-template` | template `{{visible}}`/`{{total}}` | opcional |
| `data-collection-clear` | botão de limpar | opcional |
| `data-collection-bound` | container (interno) | idempotência |

API oficial: `CV.collection.init(root?)`, `apply(collection)`,
`clear(collection)`, `getState(collection)`, `matches(item, filters)` e
`normalize(value)`.

Evento no modo cliente: `cv:collection:updated`, com
`{ collection, filters, total, visible, hidden }`.

A busca cliente ignora caixa e acentos e combina palavras com AND. No modo
servidor, o backend continua sendo o dono da semântica de busca e paginação.

## Máscaras (`masks.js` / `CV.masks`)

| Atributo | Elemento | Valores |
|----------|----------|---------|
| `data-mask` | `input`, `textarea` | `upper`, `cpf`, `rg`, `placa`, `cep`, `telefone`, `protocolo` |
| `data-mask-bound` | campo (interno) | `true` após bind — evita listeners duplicados |

API:

| Método | Uso |
|--------|-----|
| `CV.masks.scan(root?)` | Inicializa campos em `document` ou subárvore |
| `CV.masks.apply(input)` | Aplica máscara ao valor atual |
| `CV.masks.format(value, mask)` | Formata string sem DOM |

API pública: `window.CV.masks`.

Exemplo após DOM dinâmico (Quick Add):

```javascript
window.CV.masks.scan(panelElement);
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

Hooks: `window.CV.autosaveSnapshots[model]`, `window.CV.autosaveValidators[model]`.

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

Quick Add e o wizard de ofícios chamam `CV.fields.init(root)` para inicializar
campos inseridos dinamicamente.

## Picker de entidade (contrato vigente)

O `<select>` fonte declara o componente; a `<div>` que o motor renderiza declara **o que ela é**.
Quem consome o picker de fora nunca deve procurá-lo pela classe CSS — a classe é estilo e vai ser
renomeada na reconstrução do CSS (`JS-06`).

| Atributo | Onde | Para quê |
|---|---|---|
| `data-entity-picker` | no `<select>` fonte | declara o campo como picker |
| `data-entity-picker-mode` | no `<select>` | `single` \| `multi` |
| `data-entity-picker-renderer="select"` | no `<select>` | escolhe o renderer alternativo (`picker-select.js`) |
| `data-entity-picker-ready` | no `<select>` | marcador de idempotência |
| **`data-entity-picker-root`** | na raiz **renderizada** | é por aqui que se acha o picker no DOM |
| **`data-entity-picker-part="…"`** | nas partes renderizadas | `field`, `control`, `input`, `clear`, `dropdown`, `list`, `empty`, `option`, `remove`, `selected-panel`, `selected-card`, `selected-title-row`, `term-control`, `driver-toggle`, `driver-surface`, `driver-text` |

API pública, em `window.CV.picker`:

```js
CV.picker.rootFor(select)        // raiz renderizada (serve para os dois renderers)
CV.picker.part(escopo, nome)     // uma parte
CV.picker.parts(escopo, nome)    // todas as partes
CV.picker.closestPart(no, nome)  // subindo a partir de um nó
```

Duas armadilhas medidas no navegador: o **dropdown é portado para `document.body`** pelo overlay
quando aberto, então `part(root, "dropdown")` devolve `null` nesse estado — use `closest` a partir
do alvo do evento; e existe markup que **imita** o picker sem ser um (três templates o escrevem à
mão, `NOVO-16`), que tem as classes mas não os atributos.

> **O resto deste documento está desatualizado** — `HT-13`: descreve 4 arquivos JS que não existem
> mais e 9 atributos com zero ocorrência no repositório. A correção é da etapa F3 do plano de
> front; até lá, confie na tabela acima e no código, não no que vem abaixo.

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

APIs públicas: `window.CV.roteiros.editor` e `window.CV.roteiros.map`.
