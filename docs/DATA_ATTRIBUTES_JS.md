# Contrato de data attributes — JavaScript

Referência dos **motores compartilhados** da Central de Viagens: o que cada um procura no DOM e o
que ele publica em `window.CV`. Não altera regra de negócio.

## O que está aqui, e o que não está

Este documento cobre `static/js/core/`, `static/js/components/` e os motores de raiz — o código que
qualquer tela pode acionar. **Não** indexa os atributos de uma página só (`static/js/pages/`): são
**142** deles, cada um com um único consumidor, e a documentação certa para esses é o próprio
módulo da página.

A regra que decide: se o atributo aparece num motor compartilhado, ele está aqui. Isso é verificado
por `core/tests/test_contrato_data_attributes.py` nos dois sentidos — atributo citado aqui tem de
existir no código, e atributo de motor compartilhado tem de estar citado aqui. Não existe mais a
possibilidade de este arquivo apontar para o passado sem a suíte reclamar.

> **`HT-13`, corrigido em 07/08/2026.** A versão anterior citava **4 arquivos JS que não existem**
> (`cv-custom-select.js`, `cv-search-picker.js`, `app-multiselect.js`, `filterable-multiselect.js`)
> e **7 atributos com zero ocorrência no repositório** (`data-quick-add-toggle`,
> `data-quick-add-close`, `quick-add-panel`, `data-cv-select`, `data-cv-search-picker`,
> `data-app-multiselect`, `data-filterable-multiselect-input`). O enunciado do defeito dizia 3; a
> medição achou 7. E a cobertura era de **19%** — 57 atributos citados para 298 em uso.

Nomes de classe CSS **não** são contrato de JS. Desde o `JS-06`, comportamento se pendura em
`data-*`; classe é estilo e vai ser renomeada na reconstrução do CSS.

---

## `window.CV.http` — `core/http.js`

Carregado em `base.html`. Sem atributos: é API.

| API | Uso |
|-----|-----|
| `getCsrfToken(form?)` | Token do input CSRF no form ou do cookie `csrftoken` |
| `readJsonResponse(response)` | `{ ok, status, data }`, com fallback para JSON inválido |
| `fetchJson(url, options)` | `fetch` com `credentials: same-origin` e headers padrão |

`options`: `method`, `body` (objeto → JSON, `FormData`, string), `form`, `headers`, `signal`,
`rawResponse`.

## Registro de componentes — `core/app.js`

Coordenador dos inicializadores idempotentes. `CV.registerEnhancer(nome, init, destroy?)`; o
registry chama `destroy(root)` quando o nó sai do DOM (`JS-02`).

| Atributo | Elemento | Comportamento |
|---|---|---|
| `data-inline-create-toggle` | botão | Abre/fecha o painel de cadastro rápido (alvo por `aria-controls`) |
| `data-inline-create-close` | botão no painel | Fecha o painel |
| `data-quick-edit` | botão da lista | Abre o painel em modo edição (`data-edit-url`, `data-edit-fields`) |
| `data-confirm-submit` | form | Pede confirmação antes de submeter |
| `data-cv-feedback-accept` | botão | Confirma o diálogo de feedback |
| `data-cv-feedback-cancel` | botão | Cancela o diálogo de feedback |

O painel é o elemento apontado por `aria-controls`, com a transição `.is-open`.

## Carregamento progressivo — `core/component-loader.js`

O script do shell em `base.html` fornece URLs resolvidas pelo storage de estáticos. O loader pede
cada componente somente quando encontra seu marcador no DOM inicial ou em conteúdo inserido por
AJAX.

| Atributo | Elemento | Uso |
|---|---|---|
| `data-cv-lazy-components` | script do shell | Declara a configuração única do loader |
| `data-cv-lazy-form-components-src` | script do shell | URL de `form-components.bundle.js` |
| `data-cv-lazy-card-toggle-src` | script do shell | URL de `card-toggle.js` |
| `data-cv-lazy-segment-nav-src` | script do shell | URL de `segment-nav.js` |
| `data-cv-lazy-file-picker-src` | script do shell | URL de `file-picker.js` |
| `data-cv-lazy-attach-signed-modal-src` | script do shell | URL de `attach-signed-modal.js` |
| `data-cv-lazy-signature-actions-src` | script do shell | URL de `signature-actions.js` |
| `data-cv-lazy-extra-download-src` | script do shell | URL de `extra-download.js` |
| `data-cv-lazy-wizard-sticky-header-src` | script do shell | URL de `wizard-sticky-header.js` |
| `data-cv-component-bundle="forms"` | script opcional da página | Informa que o bundle de formulários já foi declarado antes do shell |

API: `CV.lazyComponents.scan(root?)`, para uma varredura explícita, e `destroy()`, usado em testes.

O bundle de formulários agrupa `picker-parts`, os dois renderers de picker, `location-rows`,
`document-source`, `document-search` e `date-picker`. Páginas cujo JavaScript chama essas APIs
diretamente incluem `includes/form_components_js.html` no bloco `component_js`, depois do shell e
antes dos scripts de página;
nas demais, o loader usa `[data-entity-picker]`, `[data-location-rows]` ou
`[data-cv-date-picker]` como marcador. O inventário automatizado em
`core/tests/test_shell_bundles.py` obriga todo consumidor direto novo a declarar a dependência.

## Coleções — `components/collection.js` / `CV.collection`

Cada lista declara exatamente um modo. `client` filtra o que já está renderizado; `server` manda os
filtros por GET, troca só `.list-panel` e atualiza a URL.

| Atributo | Elemento | Obrigatório |
|---|---|---|
| `data-collection` | container da lista/cards | sim |
| `data-collection-mode="client\|server"` | container | sim |
| `data-collection-form` | `form` GET | no modo `server` |
| `data-collection-filter="search\|status\|select\|date"` | controle | sim, por filtro |
| `data-collection-item` | linha, card, item | no modo `client` |
| `data-search-text` | item | recomendado no modo `client` |
| `data-status-value` | item | se filtrar status no cliente |
| `data-collection-container` | container dos itens | opcional |
| `data-collection-empty` | estado vazio | opcional |
| `data-collection-count` | contador | opcional |
| `data-collection-count-template` | template `{{visible}}`/`{{total}}` | opcional |
| `data-collection-clear` | botão de limpar | opcional |
| `data-collection-bound` | container (interno) | idempotência |

API: `CV.collection.init(root?)`, `apply(collection)`, `clear(collection)`, `getState(collection)`,
`matches(item, filters)`, `normalize(value)`.

Evento no modo cliente: `cv:collection:updated` — `{ collection, filters, total, visible, hidden }`.

A busca cliente ignora caixa e acentos e combina palavras com AND. No modo servidor o backend
continua dono da semântica de busca e paginação.

## Pickers — `components/picker.js`, `components/picker-select.js`, `components/picker-parts.js`

O `<select>` fonte declara o componente; a `<div>` que o motor renderiza declara **o que ela é**.
Quem consome o picker de fora nunca deve procurá-lo pela classe CSS.

| Atributo | Onde | Para quê |
|---|---|---|
| `data-entity-picker` | `<select>` fonte | Declara o campo como picker |
| `data-entity-picker-mode` | `<select>` | `single` \| `multi` |
| `data-entity-picker-renderer="select"` | `<select>` | Escolhe o renderer alternativo (`picker-select.js`) |
| `data-entity-picker-ready` | `<select>` | Marcador de idempotência |
| `data-picker-v2` | `<select>` fonte | Declara que este picker é do sistema v2 |
| **`data-entity-picker-v2`** | dropdown **renderizado** | Cópia da marca acima no dropdown, que é portado para o `body` e perde os ancestrais. É por ela que o CSS e o próprio motor distinguem a lista v2 da legada — nunca pela classe |
| **`data-entity-picker-root`** | raiz **renderizada** | É por aqui que se acha o picker no DOM |
| **`data-entity-picker-part="…"`** | partes renderizadas | `field`, `control`, `input`, `clear`, `dropdown`, `list`, `empty`, `option`, `remove`, `selected-panel`, `selected-card`, `selected-title-row`, `term-control`, `driver-toggle`, `driver-surface`, `driver-text` |

```js
CV.picker.rootFor(select)        // raiz renderizada (serve para os dois renderers)
CV.picker.part(escopo, nome)     // uma parte
CV.picker.parts(escopo, nome)    // todas as partes
CV.picker.closestPart(no, nome)  // subindo a partir de um nó
```

Duas armadilhas medidas no navegador: o **dropdown é portado para `document.body`** pelo overlay
quando aberto, então `part(root, "dropdown")` devolve `null` nesse estado — use `closestPart` a
partir do alvo do evento. Os pickers de relacionamento escritos pelo servidor usam
`ui/forms/related_picker.html`; sua raiz semântica é `data-related-picker-root` e a apresentação
(`card` ou `compact`) fica em `data-related-picker-presentation`. A estrutura criada por JS vem de
`CV.pickerParts`, sem reconstruir classes BEM nos módulos de página (`NOVO-16`).

## Máscaras — `components/masks.js` / `CV.masks`

| Atributo | Elemento | Valores |
|---|---|---|
| `data-mask` | `input`, `textarea` | `upper`, `cpf`, `rg`, `placa`, `cep`, `telefone`, `protocolo` |
| `data-mask-bound` | campo (interno) | `true` após bind — evita listener duplicado |

API: `CV.masks.scan(root?)`, `CV.masks.apply(input)`, `CV.masks.format(value, mask)`.

## State toggle — `components/state-toggle.js` / `CV.stateToggle`

| Atributo | Elemento | Uso |
|---|---|---|
| `data-cv-state-toggle` | container (ex.: `form`) | Escopo do toggle |
| `data-cv-state-binary` | container | Modo botão único + checkbox |
| `data-cv-state-option` | botão | Opção em grupo (com `data-value`) |
| `data-value` | opção | Valor aplicado ao input |
| `data-cv-state-input` | input / seletor | Campo sincronizado (padrão: primeiro checkbox) |
| `data-cv-state-trigger` | botão | Gatilho binário |
| `data-active-label`, `data-inactive-label` | botão/container | Rótulo por estado |
| `data-cv-state-bound` | container (interno) | Idempotência |

API: `CV.stateToggle.init(root?)`, `CV.stateToggle.update(group, value)`.
Evento: `cv:state-toggle:change` — `{ value, input, toggle, fromUser? }`.

## Card toggle — `components/card-toggle.js`

Checkbox renderizado como cartão clicável (`components/ui/forms/card_toggle.html`).

| Atributo | Elemento |
|---|---|
| `data-card-toggle` | `<label>` do cartão |
| `data-card-toggle-state` | span que mostra LIGADA/DESLIGADA |
| `data-servidor-sem-rg-form` | form que esconde o RG quando o toggle liga |
| `data-rg-field-wrap` | bloco do campo de RG |

## Overlay e modais — `components/overlay.js`

| Atributo | Elemento |
|---|---|
| `data-overlay-trigger` | botão que abre |
| `data-overlay-target` | id do overlay alvo |
| `data-overlay-kind` | tipo do overlay |
| `data-overlay-close` | botão que fecha |
| `data-delete-confirm-modal`, `data-delete-confirm-form`, `data-delete-confirm-label` | modal de exclusão |
| `data-confirm-action-modal`, `data-confirm-action-form`, `data-confirm-action-label` | modal de confirmação genérica |
| `data-cancel-reason-modal`, `data-cancel-reason-form`, `data-cancel-reason-label` | modal de cancelamento com motivo |
| `data-vincular-usuario-modal`, `data-vincular-usuario-form`, `data-vincular-usuario-label` | modal de vínculo de usuário |

## Date picker — `components/date-picker.js`

Raiz: `data-cv-date-picker`. Idempotência e ciclo de vida por `registerEnhancer` (`JS-02`).

| Grupo | Atributos |
|---|---|
| Estrutura | `data-cv-date-picker-panel`, `data-cv-date-picker-trigger`, `data-cv-date-picker-days`, `data-cv-date-picker-month`, `data-cv-date-picker-weekdays`, `data-cv-date-picker-summary` |
| Navegação | `data-cv-date-picker-prev`, `data-cv-date-picker-next`, `data-cv-date-picker-today`, `data-cv-date-picker-clear`, `data-cv-date-picker-confirm`, `data-cv-date-picker-undo` |
| Valor único | `data-cv-date-picker-value`, `data-cv-date-picker-display`, `data-cv-date-picker-display-text` |
| Intervalo | `data-cv-date-picker-start-value`, `data-cv-date-picker-start-display`, `data-cv-date-picker-start-label`, `data-cv-date-picker-end-value`, `data-cv-date-picker-end-display`, `data-cv-date-picker-end-label` |
| Contexto | `data-cv-date-picker-context`, `data-cv-date-picker-context-route`, `data-cv-date-picker-context-step` |

## File picker — `components/file-picker.js`

Raiz: `data-file-picker`, com o `<input type=file>` nativo em `data-file-native`.

| Grupo | Atributos |
|---|---|
| Estado | `data-file-picker-name`, `data-file-picker-status`, `data-file-inline-actions` |
| Seleção | `data-file-selection-list`, `data-file-selection-index`, `data-file-selection-name`, `data-file-selection-size`, `data-file-selection-summary`, `data-file-selection-template` |
| Menu | `data-file-selection-menu`, `data-file-selection-toggle`, `data-file-selection-dropdown` |
| Ações | `data-file-preview-selection`, `data-file-remove-selection`, `data-file-clear-selection` |

## Anexar documento assinado — `components/attach-signed-modal.js`

Raiz: `data-attach-signed-modal`, aberto por `data-attach-signed-trigger`.

| Grupo | Atributos |
|---|---|
| Fluxo | `data-attach-signed-form`, `data-attach-signed-next`, `data-attach-signed-cancel`, `data-attach-signed-error`, `data-attach-signed-reopen-key` |
| Tipo | `data-attach-signed-kind`, `data-attach-signed-kind-selector`, `data-attach-signed-kind-options`, `data-attach-signed-label` |
| Arquivo atual | `data-attach-signed-current`, `data-attach-signed-current-name`, `data-attach-signed-current-open`, `data-attach-signed-remove` |
| Upload | `data-attach-signed-file-description`, `data-attach-signed-file-help`, `data-file-upload-button`, `data-file-picker-action-label` |

## Linhas de localidade — `components/location-rows.js`

Raiz: `data-location-rows`; a lista é `data-location-list` e o molde `data-location-template`.

| Atributo | Uso |
|---|---|
| `data-location-row` | Uma linha |
| `data-location-state` / `data-location-city` | Selects de UF e cidade |
| `data-location-add` / `data-location-remove` | Botões |
| `data-location-drag-handle` | Alça do arraste. Só ela inicia a reordenação: o motor bloqueia o gesto sobre botões e pickers, e numa linha cheia de controles não sobra outro ponto |
| `data-location-managed` | Na raiz: a seção se liga sozinha, sem script de página chamando `initManagedRows` |
| `data-location-order` | Campo de ordem |
| `data-route-destinos-trechos` / `data-route-destinos-subtitle` | Resumo do roteiro |

## Documentos — `components/document-*.js`, `components/extra-download.js`

| Atributo | Motor | Uso |
|---|---|---|
| `data-document-loading`, `data-document-loading-title`, `data-document-loading-detail` | `document-download.js` | Estado de carregamento do download |
| `data-document-download-bypass` | `document-download.js` | Link que ignora o estado de carregamento |
| `data-document-generation-wait`, `data-document-generation-message` | `document-generation-wait.js` | Espera da geração assíncrona |
| `data-document-number-field`, `data-document-number-input`, `data-document-number-value` | `document-number-field.js` | Campo composto número/ano |
| `data-extra-download-url` | `extra-download.js` | Enfileira um segundo download junto do principal |

## Autosave — `autosave.js`

| Atributo | Elemento |
|---|---|
| `data-autosave="true"` | form — ativa o motor |
| `data-autosave-model` | form — chave de snapshots/validators |
| `data-autosave-url`, `data-autosave-create-url` | form — endpoints |
| `data-autosave-link` | link que salva antes de navegar |

Hooks: `window.CV.autosaveSnapshots[model]`, `window.CV.autosaveValidators[model]`.

## Casca da página — `components/sidebar.js`, `theme-toggle.js`, `components/wizard-sticky-header.js`, `components/icon-tooltips.js`

| Atributo | Motor |
|---|---|
| `data-sidebar`, `data-sidebar-toggle`, `data-sidebar-drawer-toggle`, `data-sidebar-drawer-close`, `data-sidebar-root-link`, `data-sidebar-panel-link` | `sidebar.js` |
| `data-theme-mode` | `theme-toggle.js` |
| `data-wizard-sticky-header`, `data-wizard-sticky-band`, `data-wizard-sticky-stepper`, `data-wizard-sticky-sentinel` | `wizard-sticky-header.js` |
| `data-tooltip` | `icon-tooltips.js` |

## Formulários — `components/fields-init.js`

Orquestrador carregado depois dos motores em `base.html`.

| API | Uso |
|---|---|
| `CV.fields.init(root?)` | Inicializa tudo na subárvore |
| `CV.initFields` | Alias de `CV.fields.init` |
| `CV.fields.initSelects(root?)` | Só os selects customizados |
| `CV.fields.initSearchPickers(root?)` | Só o picker de busca |
| `CV.fields.initDatePickers(root?)` | Só os date pickers |
| `CV.fields.initMultiselects(root?)` | Só os multiselects |

| Atributo | Uso |
|---|---|
| `data-form-errors` | Resumo de erro de formulário (`HT-03`) — recebe o foco uma vez por carga de página |

Evento: `cv:fields:init` — `detail.initialized`:
`{ masks, stateToggles, segmentNav, selects, searchPickers, datePickers, multiselects, filterableMultiselects, resumoDeErros }`.

Ordem interna: masks → stateToggle → segmentNav → selects → searchPickers → datePickers →
multiselects → filterableMultiselects → resumo de erros.

Depois de inserir DOM dinamicamente:

```javascript
window.CV.fields.init(panelElement);
```

## Outros motores compartilhados

| Atributo | Motor | Uso |
|---|---|---|
| `data-diaria-base`, `data-diaria-derivado` | `components/diaria-derivados.js` | Espelha na tela a derivação de 15% e 30% que o modelo faz no `save()` — é pré-visualização, o servidor continua dono do valor |
| `data-cv-signature-card`, `data-cv-signature-link`, `data-cv-signature-copy`, `data-cv-signature-wa` | `components/signature-actions.js` | Cartão de assinatura: copiar link e enviar por WhatsApp |
| `data-cv-segment-nav-bound` | `components/segment-nav.js` | Navegação por segmentos — marcador de idempotência (o motor liga por classe, não por atributo) |
| `data-font-try`, `data-font-sample`, `data-font-try-current`, `data-font-weight-step`, `data-font-weight-current`, `data-font-try-reset` | `components/font-try.js` | Provador de fontes do UI Lab: reescreve `--font-sans` no `<html>` e a interface inteira troca de família, ao vivo. A pilha é lida da amostra vizinha (`data-font-sample`) por `getComputedStyle`, e não de um atributo do botão — gancho impresso com escape quebrava as aspas da pilha. Nada é gravado — recarregar volta ao padrão. Carregado só na galeria |
| `data-fit-text`, `data-fit-text-min`, `data-fit-text-max` | `components/fit-text.js` | Texto que encolhe até caber em UMA linha, e só o necessário: o CSS declara o corpo ideal, o JS desce dali. `-min` é o piso (padrão 11px); `-max` é gravado pelo próprio motor no primeiro ajuste, para o texto voltar a crescer quando o bloco alargar. Reage a mudança de largura por `ResizeObserver` |
| `data-download-picker`, `data-download-picker-trigger`, `data-download-picker-list`, `data-download-picker-item`, `data-download-picker-queue`, `data-download-picker-confirm`, `data-download-picker-error` | `components/download-queue.js` | Seletor de download do termo: o gatilho pergunta ao `data-src` o que existe (com um documento só, baixa direto), e a confirmação baixa em FILA, um arquivo de cada vez |
| `data-map-focus-lat`, `data-map-focus-lng` | `pages/roteiros-map.js` | Centro inicial do mapa |
| `data-oficio-glance-panel`, `data-oficio-glance-toggle`, `data-oficio-glance-toggle-label`, `data-oficio-sticky-header` | `pages/roteiros-wizard.js` | Painel de resumo do ofício no wizard de roteiro |

## Domínio de roteiro (no `#roteiro-editor-form`)

`data-api-calcular-rota-url`, `data-api-calcular-rota-preview-url`, `data-url-trechos-estimar`,
`data-api-cidades-url`, `data-api-diarias-url`.

APIs públicas: `window.CV.roteiros.editor` e `window.CV.roteiros.map`.

## Configurações — CEP

`data-configuracoes-form` no form raiz; `data-cep-lookup-url-template` com `00000000` no lugar do
CEP.
