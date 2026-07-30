# Auditoria estrutural completa — HTML + JavaScript

**Escopo:** 100% das páginas de produção, componente por componente. Estrutura de templates (composição, semântica, contratos, acessibilidade) e camada JavaScript (motores, ciclo de vida, contratos `data-*`, duplicação).
**Objetivo:** listar toda inconsistência estrutural e propor um conjunto de **motores globais** que funcionem em qualquer página, com contrato único de `data-*` e ciclo de vida idempotente.
**Companheiro de:** [`AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md`](AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md) (CSS/tema escuro).
**Este documento não altera código.**

---

## Índice

1. [Método e números](#1-método-e-números)
2. [O padrão de referência — HTML e JS](#2-o-padrão-de-referência--html-e-js)
3. [Diagnóstico estrutural — HTML](#3-diagnóstico-estrutural--html)
4. [Diagnóstico estrutural — JavaScript](#4-diagnóstico-estrutural--javascript)
5. [Catálogo de defeitos — HTML](#5-catálogo-de-defeitos--html)
6. [Catálogo de defeitos — JavaScript](#6-catálogo-de-defeitos--javascript)
7. [Auditoria página a página](#7-auditoria-página-a-página)
8. [Auditoria componente a componente](#8-auditoria-componente-a-componente)
9. [Dicionário de renomeação — templates, hooks e namespaces](#9-dicionário-de-renomeação)
10. [Catálogo dos motores globais propostos](#10-catálogo-dos-motores-globais-propostos)
11. [Contrato único de `data-*`](#11-contrato-único-de-data-)
12. [Ordem de execução sugerida](#12-ordem-de-execução-sugerida)

---

## 1. Método e números

### 1.1 Como foi feito

- Parse de **369 templates** (76 páginas de produção + 80 componentes + partials).
- Parse de **71 arquivos JS** (63 de produção, 18.301 linhas).
- Cruzamento de **380 atributos `data-*` lidos pelo JS** × **392 emitidos pelos templates**.
- Detecção de: includes sem `only`, elementos com 5+ classes, `<button>` sem `type`, `aria-expanded` sem `aria-controls`, `<label>` sem `for`, IDs estáticos repetidos, URLs hardcoded, blocos de template mortos.
- Classificação do padrão de inicialização de cada arquivo JS (enhancer / DOMContentLoaded / IIFE / ESM) e mapeamento de listeners globais.
- Rastreio de motores duplicados (cascata estado→cidade, pickers, prefill, debounce, CSRF).

### 1.2 Números que definem o problema

| Métrica | Valor | Leitura |
|---|---|---|
| Templates | 369 | 80 em `components/`, 213 em partials de módulo |
| Páginas de produção | 76 | — |
| Linhas de JS (produção) | **18.301** | 63 arquivos |
| JS carregado em **toda** página (`base.html`) | **28 arquivos** | Sem bundling, sem code-splitting |
| **Arquivos JS órfãos** (nunca carregados) | **9** (989 linhas) | Removidos em J-06 |
| Namespaces globais em `window` | **22** | `CV` + 21 outros |
| Listeners em `document`/`window` | **116** | — |
| Arquivos que registram no motor de enhancers | **12 de 63** | O registry existe e quase ninguém usa |
| `fetch()` direto ignorando `CV.http` | **13 arquivos** | CSRF reimplementado em 11 |
| Implementações de "cascata estado→cidade" | **6** | 1 global + 5 cópias por módulo |
| Includes **sem** `only` | **190 de 863** | Vazamento de contexto |
| Elementos com 5+ classes | 29 | Máximo: 8 classes num `<select>` |
| `<div>` × `<section>`+`<article>` | **1.540 × 209** | Div soup |
| `aria-expanded` sem `aria-controls` | **29** | — |
| Tokens `?v=` distintos, mantidos à mão | **88** | 11 arquivos servidos com `?v=` divergentes |
| `alert()` / `confirm()` nativos | **13** | Num sistema com 4 modais próprios |
| Estilos inline em template | 0 | ✅ |
| `<button>` sem `type` | 0 | ✅ |
| `<img>` sem `alt` / `target=_blank` sem `rel` | 0 / 0 | ✅ |
| URLs hardcoded em `href`/`action` | 0 | ✅ (5 em `default:` de include) |

---

## 2. O padrão de referência — HTML e JS

### 2.1 Composição de template aprovada

Ofícios etapa 1/2, Termos e OS convergem para:

```
base.html
└── {% block content %}
    └── página (page-shell)
        ├── include page_header.html          … only ✅
        ├── include page_stepper.html         … only ✅
        └── main-form-panel > cv-form-section-stack
            └── <form>
                └── section.cv-form-section-card
                    ├── header (escrito à mão na página) ⚠️
                    ├── cv-form-section-body
                    │   └── N × include form_block.html   … SEM only ⚠️
                    │       └── body_template (partial do módulo)
                    │           └── N × include field.html  … only ✅
                    └── cv-form-card__footer
                        └── include card_footer_section.html … only ✅
```

**Contratos implícitos que funcionam bem:**

1. Cada `form_block` recebe um `body_template` — o componente é a casca, o módulo entrega o miolo.
2. Campos sempre via `field.html`, nunca `{{ form.x }}` cru.
3. Hooks de comportamento entram por `data-*` (via `extra_class` ou `data_hook`), nunca por classe de estilo.
4. Nenhum `<script>` inline. Nenhum `style=` inline.
5. Ações de navegação carregam `data-autosave-link="1"` para o autosave descarregar antes de sair.

### 2.2 Motor JS de referência: `CV.registerEnhancer`

`static/js/core/app.js:7-77` já define exatamente o motor global que o sistema precisa:

```js
CV.registerEnhancer(nome, init)   // init(root) idempotente
```

- Roda `init(document)` no boot.
- Um `MutationObserver` em `document.documentElement` reexecuta todos os enhancers em qualquer subárvore inserida (AJAX, template clonado, lista filtrada).
- Erros são isolados por `try/catch` e emitidos como `cv:enhancer-error`.
- Agenda em microtask com deduplicação de raízes.

**Este é o padrão certo. O problema é que só 12 de 63 arquivos o usam.**

### 2.3 Desvios já presentes DENTRO das páginas de referência

| # | Desvio | Onde |
|---|---|---|
| RH-01 | O `<header>` do card mestre é escrito à mão em **todas** as páginas, apesar de `form_block shell="card"` já produzir exatamente esse markup | `wizard_dados_viajantes.html:12-17`, `termos/form.html:38-43`, `ordens_servico/form.html:33-38` |
| RH-02 | `form_block.html` é incluído **sem `only`** em 50 lugares — o contexto inteiro da página vaza para o componente | todas as páginas de formulário |
| RH-03 | Ofícios etapa 2 monta os campos direto no `cv-form-section-body`, sem `form_block` | `wizard_transporte.html` |
| RH-04 | O mesmo `<select>` de estado existe em 5 variantes com contratos incompatíveis (`pk` vs `sigla`) | ver §3.3 |
| RJ-01 | Ofícios etapa 1 carrega **4 scripts de página** (`oficios-dados-viajantes`, `oficios-transporte`, `oficios-wizard-driver-state`, `oficios-viatura-sugestoes`) — nenhum registrado como enhancer | `wizard_dados_viajantes.html:40-43` |
| RJ-02 | `oficios-transporte.js` (634 linhas) é carregado tanto na etapa 1 quanto na etapa 2 | `wizard_dados_viajantes.html:41`, `wizard_transporte.html` |
| RJ-03 | Termos e OS reimplementam prefill-a-partir-de-ofício de forma independente | `termos-form.js:465+`, `ordens-servico-form.js:913+` |

---

## 3. Diagnóstico estrutural — HTML

### 3.1 A árvore de templates não tem fronteira

| Pasta | Arquivos | Papel declarado | Papel real |
|---|---|---|---|
| `templates/components/ui/` | 51 | Componentes globais | ✅ na maior parte |
| `templates/components/lists/` | 10 | Composição de lista | ⚠️ inclui `main_list_card.html` morto |
| `templates/components/travel/` | 11 | Componentes de domínio | ⚠️ misturado com global |
| `templates/components/cards/`, `documents/`, `feedback/`, `layout/`, `perfil/` | 8 | Global | ⚠️ `perfil/gdrive_card.html` é de módulo |
| `templates/<modulo>/partials/` | 213 | Miolos de módulo | ❌ contém 6 cópias de componentes globais |

**Consequência:** não existe regra para saber se um partial é reutilizável. `components/perfil/gdrive_card.html` é global por localização e local por conteúdo; `eventos/partials/_destino_primary_state.html` é local por localização e global por conteúdo.

### 3.2 Vazamento de contexto: 190 includes sem `only`

| Componente | Includes sem `only` | Efeito |
|---|---|---|
| `components/ui/forms/form_block.html` | **~50** | Recebe todo o contexto da view. Impossível saber quais variáveis o componente realmente consome. |
| `components/ui/forms/_date_picker_icon.html` | 11 | — |
| `eventos/partials/_documento_panel.html` | 5 | — |
| `prestacoes_contas/partials/_docs_attach_card.html` | 5 | — |
| `components/travel/destination_row.html` | 4 | — |

`form_block.html` é o caso central: ele **precisa** do contexto porque o `body_template` incluído dentro dele consome variáveis da view. É um componente que não consegue selar sua interface — o motivo estrutural pelo qual o sistema não consegue ser componentizado de verdade.

**Correção estrutural:** `form_block` deve receber um `context` explícito (dict montado pelo presenter) e incluir o body com `only`. Isso torna cada bloco testável isoladamente.

### 3.3 O caso do destino: um conceito, seis implementações

**Corrigido (H-01/J-08):** `CV.locationRows` e os hooks `data-location-*`
passaram a ser o único contrato vivo. Planos, Termos, OS, Eventos e Roteiros
não contêm mais fallback de cascata, criação de linha ou drag-and-drop. Os seis
partials de select exclusivos de Eventos foram removidos; seus controles agora
também usam `estado.pk`, convertendo para a sigla/nome exigidos pelo modelo
legado somente na serialização. O corte removeu 1.158 linhas.

O inventário abaixo registra a linha de base histórica que motivou a correção:

| # | Implementação | Templates | JS | Contrato de valor |
|---|---|---|---|---|
| 1 | **Global** `components/travel/destinations/*` | 5 arquivos | `destination-section.js` (508 l.) | `estado.pk` |
| 2 | Eventos | `_destino_primary_state/-city`, `_destino_extra_state/-city`, `_destino_extra_*_saved`, `_destino_extra_template`, `_destinos_rows_novo/-detalhe` (9 arquivos) | `eventos-detalhe.js` (490 l.) | **`estado.sigla`** |
| 3 | Roteiros | `_destino_template_state/-city` | `roteiros/editor/index.js` (2.042 l.) | `estado.pk` |
| 4 | Ordens de Serviço | `_evento_destinos_section.html` | `ordens-servico-form.js` (1.111 l.) | `estado.pk` |
| 5 | Termos | `_evento_destinos_section.html` | `termos-form.js` (621 l.) | `estado.pk` |
| 6 | Planos de Trabalho | `_identificacao_evento_destinos.html` | `planos-trabalho-wizard.js` (1.113 l.) | `estado.pk` |

Os cinco `<select>` de estado diferem apenas em `name`, hook e tipo de valor:

```html
<!-- global -->      data-{{ prefix }}-destino-state   name="destino_estado_{{ i }}"   value="{{ estado.pk }}"
<!-- eventos -->     data-destino-uf-extra             name="destino_uf"               value="{{ estado.sigla }}"
<!-- roteiros -->    class="destino-estado"            name="destino_estado___index__" value="{{ estado.pk }}"
<!-- OS -->          data-os-destino-state             …                               value="{{ estado.pk }}"
<!-- termos -->      data-termo-destino-state          …                               value="{{ estado.pk }}"
<!-- PT -->          data-pt-destino-state             …                               value="{{ estado.pk }}"
```

E os IDs são estáticos com prefixo de módulo, não gerados pelo componente:
`btn-adicionar-destino` (3 arquivos), `os-destinos-list`, `pt-destinos-list`, `termo-destinos-list`, `os-evento-destinos`, `pt-evento-destinos`, `termo-evento-destinos`.

**Custo estimado da duplicação:** ~20 templates + ~1.200 linhas de JS que colapsam em 1 componente + 1 motor.

### 3.4 Class soup: até 8 classes num elemento

| Distribuição | Elementos |
|---|---|
| 1 classe | 1.870 |
| 2 classes | 565 |
| 3 classes | 149 |
| 4 classes | 55 |
| **5+ classes** | **29** |

Piores casos:

```html
<!-- 8 classes -->
<select class="cv-search-picker cv-search-picker--single cv-search-picker--detailed
               cv-search-picker--people cv-search-picker--roster related-route-picker
               termo-oficio-picker os-oficio-picker">          <!-- _oficios_body.html:1 -->

<!-- 7 classes -->
<div class="field field-size-4 app-form-field cv-field oficio-motivo-field
            oficio-reveal-panel is-open">                      <!-- _motivo_texto_body.html:8 -->

<!-- 6 classes no shell -->
<div class="page-shell page-shell--standard travel-document-wizard app-wizard
            document-form-page os-page">                        <!-- ordens_servico/form.html:16 -->
```

O padrão é sempre o mesmo: **um alias por módulo empilhado no mesmo elemento**, porque nenhum módulo confiou que o nome global cobriria seu caso.

### 3.5 Semântica: div soup

| Tag | Ocorrências |
|---|---|
| `<div>` | **1.540** |
| `<section>` | 141 |
| `<article>` | 68 |
| `<header>` | 77 |
| `<footer>` | 15 |
| `<nav>` | **7** |
| `<main>` | 8 |
| `<aside>` | 4 |
| `<table>` | 7 |
| `<ul>` | 23 |
| `<dl>` | 11 |

- Só **7 `<nav>`** num sistema com sidebar, stepper, abas de lista, paginação e breadcrumb implícito. As abas (`cv-list-tabs`) e o stepper não são `<nav>`.
- **15 `<footer>`** para 24+ rodapés de card (`cv-card-footer` é `<div>` em boa parte).
- Listas de dados renderizadas como `<div>` empilhadas em vez de `<ul>`/`<table>` — `oficio-lc__travellers`, `oficio-lc__trechos-list`, `cv-card-grid`.

### 3.6 Blocos de template mortos

| Bloco | Definido | Sobrescrito por |
|---|---|---|
| `{% block extra_css_after_theme %}` | `base.html:32` | **ninguém** |
| `{% block shell_class %}` | `base.html:36` | apenas `dev/ui_lab/base.html` e `ui_lab2/base.html` |

### 3.7 Herança: 3 níveis, sem contrato de wizard

```
base.html
├── oficios/wizard_base.html      → 5 etapas
├── planos_trabalho/wizard_base.html → 4 etapas
├── prestacoes_contas/assinatura/base_publico.html → 5 páginas (NÃO estende base.html)
└── 60 páginas diretas
```

**Prestações tem 5 etapas de wizard e nenhum `wizard_base`** — cada uma (`relatorio_tecnico_form`, `diario_bordo_form`, `diario_motorista_form`, `documentos_form`, `consolidado`) repete o mesmo bloco de 25 linhas (page-shell + header + stepper + panel + form + card). Mesma coisa em `eventos/detalhe.html`, `termos/form.html`, `ordens_servico/form.html`, `roteiros/roteiro_form_page.html`.

**~180 linhas de estrutura duplicada** que um `document_flow_base.html` eliminaria.

---

## 4. Diagnóstico estrutural — JavaScript

### 4.1 O motor global existe e é ignorado

`core/app.js` fornece `CV.registerEnhancer` + `MutationObserver`. Quem usa:

| Registram (12) | Não registram (51) |
|---|---|
| `attach-signed-modal`, `cancel-reason-modal`, `confirm-action-modal`, `delete-confirm-modal`, `cv-custom-select`, `cv-date-picker`, `cv-search-picker`, `file-picker`, `live-search-submit`, `realtime-filters`, `eventos-detalhe`, `prestacoes-contas-documentos`* | `masks`, `state-toggle`, `card-toggle`, `cv-select`, `fields-init`, `autosave`, `destination-section`, `document-number-field`, `app-motorista-picker`, `sidebar`, `theme-toggle`, e **todos os 20 scripts de página** |

\* `prestacoes-contas-documentos.js` é **órfão** — registra um enhancer que nunca é carregado.

**Padrão de inicialização por arquivo:**

| Padrão | Arquivos | Sobrevive a swap de DOM? |
|---|---|---|
| `registerEnhancer` | 12 | ✅ sim |
| Delegação em `document` | 8 | ✅ sim |
| `DOMContentLoaded` + `boot(document)` | **31** | ❌ **não** |
| ESM (`type="module"`) | 7 | ❌ não |
| IIFE imediato | 5 | depende |

### 4.2 O buraco: `live-search-submit` troca o DOM e ninguém reinicializa

`components/live-search-submit.js:46-54`:

```js
function swapListPanel(htmlText) {
  var nextPanel = nextDoc.querySelector('.list-panel');
  var currentPanel = document.querySelector('.list-panel');
  currentPanel.replaceWith(nextPanel);          // ← troca o painel inteiro
}
```

O `MutationObserver` do `app.js` reexecuta os **12** enhancers registrados na nova subárvore. Tudo o mais que vivia dentro do `.list-panel` perde os handlers:

| Componente dentro do `.list-panel` | Init | Após filtro |
|---|---|---|
| `masks.js` | DOMContentLoaded | ❌ máscaras param de funcionar em campos inline do card |
| `state-toggle.js` | DOMContentLoaded | ❌ |
| `card-toggle.js` | DOMContentLoaded | ❌ |
| `cv-select.js` (dropdowns) | DOMContentLoaded | ❌ |
| `fields-init.js` | DOMContentLoaded | ❌ |
| `autosave.js` | DOMContentLoaded | ❌ forms inline do card deixam de salvar |
| Quick Add (`app.js:201`) | DOMContentLoaded | ❌ botão "Cadastrar item" morre |
| `action-menu.js` | delegação | ✅ mas ver §4.3 |
| `icon-tooltips.js`, `signature-actions.js`, `extra-download.js`, `prestacoes-diaria-wa.js` | delegação | ✅ |

O código já tem cicatrizes disso: `core/app.js:321-325` comenta explicitamente que o Quick Edit precisou virar delegação **porque o painel é trocado via AJAX**, e `prestacoes-diaria-wa.js:1-3` diz "delegação no document (sobrevive ao swap do live-search)". A solução foi aplicada caso a caso em vez de virar regra.

### 4.3 `action-menu.js`: vazamento de nós e ID duplicado

`components/action-menu.js:36`:

```js
if (menu.parentNode !== document.body) document.body.appendChild(menu);
```

O menu é **movido** para `<body>` ao abrir e nunca volta nem é removido. Consequências:

1. Depois de um filtro (`replaceWith` do `.list-panel`), o menu antigo continua em `<body>` — nó órfão permanente.
2. O painel novo traz um menu com **o mesmo `id`** (`termo-action-menu-{{oficio_pk}}-{{servidor_pk}}`). `document.getElementById` devolve o **primeiro** → o menu obsoleto, apontando para URLs de um card que pode nem estar mais na lista.
3. `closeAll()` percorre `.cv-action-menu--open` no documento inteiro, incluindo os órfãos.

`prestacoes-diaria-wa.js:11-20` documenta o efeito colateral e implementa um workaround (voltar ao gatilho pelo `id` do menu) em vez de corrigir a causa.

### 4.4 Dois motores de filtro na mesma lista

| Motor | Arquivo | Contrato | Lado |
|---|---|---|---|
| Filtro em tempo real | `realtime-filters.js` (277 l.) | `[data-cv-realtime-filter-scope]` + `[data-cv-filter]` + `[data-cv-filter-item]` | **cliente** |
| Submit ao vivo | `live-search-submit.js` (171 l.) | `[data-cv-live-submit-form]` + `[data-cv-filter]` | **servidor** |

Os dois escutam **o mesmo seletor** `[data-cv-filter]`. Em `list_page_cards.html`:

```html
<div class="page-shell … " data-cv-realtime-filter-scope>      <!-- motor cliente -->
  {% include "…/filter_page_header.html" with advanced=True form_action=request.path … %}
                                        <!-- ↳ <form data-cv-live-submit-form> : motor servidor -->
  <div class="list-panel"> … </div>
```

Ao digitar na busca das listas de **Ofícios, Eventos, OS, Planos de Trabalho e Prestações**, os dois disparam: o cliente esconde itens na hora, o servidor troca o painel 300 ms depois. Resultado observável: a lista "pisca" e o resultado final pode divergir do filtro exibido durante a digitação (o cliente casa por `data-search-text`, o servidor por queryset).

`roteiros/index.html` e `justificativas/index.html` passam `disable_realtime_filter=True` — a válvula de escape existe mas não é usada pelas 5 listas em card.

### 4.5 Motores duplicados

| Capacidade | Implementações | Onde |
|---|---|---|
| **Cascata estado→cidade** | **6** | `destination-section.js`, `eventos-detalhe.js`, `ordens-servico-form.js`, `planos-trabalho-wizard.js`, `roteiros/editor/index.js`, `termos-form.js` |
| **CSRF** | **11** | `CV.http` + reimplementação em `autosave`, `attach-signed-modal`, `gdrive_config`, `ordens-servico-form`, `planos-trabalho-wizard`, `prestacoes-contas-documentos`, `roteiros/editor/index`, `servidores-form`, `termos-form`, `viaturas-form`, `roteiros-map` |
| **`fetch` sem `CV.http`** | **13 arquivos** | sem tratamento padronizado de 401/403/HTML-em-vez-de-JSON |
| **`debounce`** | **5** | `live-search-submit`, `realtime-filters`, `oficios-transporte`, `ordens-servico-form`, `prestacoes-assinatura` |
| **Prefill a partir de ofício** | **3** | `termos-form.js`, `ordens-servico-form.js`, `diario-motorista.js` — cada um com seu `json_script` e sua rotina |
| **Picker de entidade** | **1** | **Corrigido:** `CV.picker` possui um enhancer e renderers de busca/select sob o contrato `data-entity-picker`; sugestões de viatura e coordenadores operam sobre o mesmo select canônico |
| **Feedback ao usuário** | **3** | `cv-document-loading` (toast de progresso), 4 modais `cv-dialog`, e **13 `window.alert`/`confirm`** |

### 4.6 Namespaces globais: 22

```
window.CV  (24 sub-APIs)      ← o certo
window.AppAutosave            window.AppAutosaveSnapshots   window.AppAutosaveValidators
window.AppMultiselect         window.AppMotoristaPicker     window.MaskEngine
window.CvSelect               window.CvSearchPicker         window.CvCustomSelect
window.CvDatePicker           window.CvFloatingDropdown     window.CvFilterableMultiselect
window.CVRealtimeFilters      window.RoteirosEditor         window.RoteirosEditorModules
window.RoteirosMap            window.RoteirosMapBoot        window.OficioWizard
window.OSFocusDestino         window.__prestDiariaWaBound   window.DEBUG_AUTOSAVE
```

Vários são **duplicatas** de uma entrada em `CV`: `MaskEngine` ≡ `CV.masks`, `CvSelect` ≡ `CV.dropdowns`, `AppAutosave` ≡ `CV.autosave`, `CVRealtimeFilters` ≡ `CV.filters`.

### 4.7 Cache-busting manual: 88 tokens, 11 arquivos incoerentes

O mesmo arquivo é servido com `?v=` diferentes conforme a página:

| Arquivo | Tokens divergentes |
|---|---|
| `js/roteiros.js` | `20260720-date-picker-header` (ofício) × `20260717-load-saved-route-map` (avulso) |
| `js/components/masks.js` | `20260620-milhar` (base) × `20260711` (diário motorista) |
| `js/pages/oficios-documentos-inline.js` | 4 tokens diferentes em 5 páginas |
| `js/pages/planos-trabalho-wizard.js` | 2 tokens |
| `js/pages/oficios-dados-viajantes.js` | 2 tokens |
| `css/roteiros.css`, `css/termos.css`, `css/prestacoes_contas.css`, `css/planos-trabalho-eventos.css`, `css/oficios-documentos-inline.css`, `css/prestacoes-documento-preview.css` | 2–5 tokens cada |

**Efeito:** o navegador guarda N cópias do mesmo arquivo. Uma correção publicada com token novo em uma página continua sendo servida da cache antiga em outra.

Pior no ESM (`roteiros.js`):

```js
// roteiros.js  (?v= vem do template)
import { initRoteirosEditor } from './pages/roteiros/editor/index.js?v=20260720-date-picker-header';
// index.js
import { … } from './trechos.js?v=20260720-date-picker-header';
import { createEditorState } from './state.js';        // ← SEM ?v=
import { createRetornoModule } from './retorno.js';    // ← SEM ?v=
import { createDiariasModule } from './diarias.js';    // ← SEM ?v=
import { createMapaModule } from './mapa.js';          // ← SEM ?v=
```

O `?v=` do `<script>` não busta os imports internos. A cadeia é mantida à mão em 3 níveis e 4 dos 6 módulos ficam de fora.

### 4.8 Código JS morto

| Arquivo | Linhas | Hooks que ficam sem dono |
|---|---|---|
| `components/app-multiselect.js` | 278 | `data-app-multiselect` |
| `components/app-motorista-picker.js`* | 264 | `data-app-motorista-picker` |
| `components/filterable-multiselect.js` | 45 | `data-filterable-multiselect-input` |
| `components/oficio-collapse.js` | 19 | `data-oficio-glance-*`, `data-oficio-sticky-header`, `data-oficio-toggle` |
| `components/viatura-motorista-fixo.js` | 52 | `data-viatura-motorista-form`, `data-viatura-motoristas-panel` |
| `oficios_termos_selector.js` | 113 | `data-oficio-termos-selector` |
| `pages/assinaturas-central.js` | 14 | — |
| `pages/prestacoes-contas-documentos.js` | 195 | registra enhancer `prestacaoDocumentos` que nunca carrega |
| `pages/roteiros/editor/utils.js` | 9 | — |

\* `app-motorista-picker.js` **é** carregado em `wizard_transporte.html`, mas nenhum template emite `data-app-motorista-picker`.

**Total: ~989 linhas mortas** + ~15 hooks `data-*` sem consumidor vivo.

### 4.9 Um recurso global que só funciona numa página

`components/extra-download.js` (27 l.) implementa o download secundário disparado por `data-extra-download-url`. Esse atributo é emitido pelo **componente global** `components/ui/menus/rich_menu_link.html:7`, usado em Ofícios, Eventos, Termos, PT e Prestações.

O script é carregado **apenas** em `eventos/index.html:7`.

Em todas as outras páginas o atributo existe no DOM e não faz nada — o segundo arquivo simplesmente não baixa, sem erro nem aviso.

---

## 5. Catálogo de defeitos — HTML

Severidade: 🔴 crítico · 🟠 alto · 🟡 médio.

| # | Sev | Defeito | Local |
|---|---|---|---|
| H-01 | ✅ | **Corrigido:** um componente global e contrato `data-location-*`; Eventos também usa `estado.pk` e converte apenas na fronteira do modelo legado | §3.3, `location-rows.js` |
| H-02 | 🔴 | **Prestações não tem `wizard_base`** — 5 páginas repetem 25 linhas de shell cada | `prestacoes_contas/*_form.html`, `consolidado.html` |
| H-03 | 🔴 | `_docs_attach_kinds_attrs.html` passa uma **lista** como 30 atributos com ordinais latinos (`primary`…`quinary`); o JS tem `KINDS` fixo de 5 | `prestacoes_contas/partials/_docs_attach_kinds_attrs.html`, `attach-signed-modal.js:7` |
| H-04 | 🟠 | 190 includes **sem `only`**; `form_block.html` sozinho em ~50 | §3.2 |
| H-05 | 🟠 | O `<header>` do card mestre é escrito à mão em 20+ páginas, apesar de `form_block shell="card"` já produzi-lo | §2.3 RH-01 |
| H-06 | 🟠 | **29 `aria-expanded` sem `aria-controls`** — menus de ação, date pickers, file picker, dropdowns | ver lista abaixo |
| H-07 | 🟠 | **IDs estáticos com prefixo de módulo** em componentes que deveriam gerá-los: `btn-adicionar-destino` (3 arquivos), `os-/pt-/termo-destinos-list`, `retorno-card` (3), `sec-retorno`, `trechos-gerados-container` | §3.3 |
| H-08 | 🟠 | **Div soup**: 1.540 `<div>` × 209 `<section>`/`<article>`; só 7 `<nav>` (abas e stepper não são nav); listas de dados como `<div>` empilhadas | §3.5 |
| H-09 | 🟠 | Elementos com 5–8 classes, sempre por empilhamento de alias de módulo | §3.4 |
| H-10 | 🟡 | 14 `<label>` sem `for` (o campo é irmão, não filho) | `_diario_trecho_body.html` (6), `card_toggle.html` (2), `_dmv_*_body.html` (2), `_motivo_body.html`, `_atividades_body.html`, `pdf_viewer.html`, `identidade.html` |
| H-11 | 🟡 | `{% block extra_css_after_theme %}` e `{% block shell_class %}` mortos em produção | `base.html:32,36` |
| H-12 | 🟡 | 5 URLs hardcoded em `default:` (`"/prestacoes-contas/"`) | `consolidado.html:18`, `diario_bordo_form.html:19`, `documentos_form.html:13`, `relatorio_tecnico_form.html:19`, `_rt_downloads_footer.html:5` |
| H-13 | 🟡 | `components/perfil/gdrive_card.html` em pasta global mas conteúdo de módulo; `components/travel/*` idem | §3.1 |
| H-14 | 🟡 | 4 padrões de submissão: `<form method=post>`, `formaction` em botão dentro do form do wizard, `data-autosave-link`, `fetch` manual | `evento_card.html:11`, `resumo_evento_card.html:27`, `wizard_documentos.html:58` |
| H-15 | 🟡 | `pdf_viewer.html:27-28` usa `href="#"` em botões de ação | `components/documents/pdf_viewer.html` |

**Lista completa de `aria-expanded` sem `aria-controls`:**
`simple_list_row.html:38` · `date_picker.html:65,90,101,113,124,150,173,202,212` · `dropdown.html:15` · `file_picker.html:26` · `entity_card_menu.html:3` · `_evento_card_body.html:22,79,141` · `_oficio_card_body.html:22,158` · `_conferencia_body.html:8,49,90,126` · `_prestacao_card_body.html:47,146` · `_bate_volta_date_controls.html:10` (+4 similares).

---

## 6. Catálogo de defeitos — JavaScript

| # | Sev | Defeito | Local |
|---|---|---|---|
| J-01 | ✅ | **Corrigido no conjunto sensível a swap:** os 8 componentes da fase 4 registram enhancers idempotentes e aceitam `root` | §4.1, fase 4 |
| J-02 | ✅ | **Corrigido:** `CV.registry.destroy(root)` executa os destruidores antes do swap; `action-menu.js` devolve ao dono qualquer menu movido para `<body>` | `core/app.js`, `collection.js`, `action-menu.js` |
| J-03 | ✅ | **Corrigido:** `CV.collection` escolhe exatamente um modo `client|server`; os dois motores e hooks antigos foram removidos | `collection.js`, componentes `list_page_*` |
| J-04 | ✅ | **Corrigido:** `CV.inlineCreate` e `CV.autosave` reinicializam conteúdo inserido e impedem listeners duplicados | `core/app.js`, `autosave.js` |
| J-05 | 🔴 | `extra-download.js` carregado só em Eventos, mas o hook é emitido pelo componente global `rich_menu_link.html` → **recurso silenciosamente morto em 4 módulos** | §4.9 |
| J-06 | ✅ | **989 linhas de JS órfão removidas** em 9 arquivos; 6 emissões remanescentes de hooks sem consumidor removidas | §4.8 |
| J-07 | 🟠 | **CSRF reimplementado em 11 arquivos**; 13 arquivos usam `fetch()` sem `CV.http` (sem tratamento de 401/HTML-em-vez-de-JSON) | §4.5 |
| J-08 | ✅ | **Corrigido:** `CV.locationRows` é a única cascata estado→cidade; fallbacks por página removidos | §3.3, `location-rows.js` |
| J-09 | 🟠 | **22 namespaces globais**, vários duplicando `CV.*` | §4.6 |
| J-10 | 🟠 | `autosave.js` registra **um `beforeunload` e um listener de captura em `document` por formulário**, nunca removidos | `autosave.js:250,283` |
| J-11 | 🟠 | `app.js:394-412` — `data-confirm-submit` escuta **click e submit**; num `<form data-confirm-submit>` com botão submit dentro, o `confirm()` aparece **duas vezes** | `app.js`, disparado por `eventos/detalhe.html:24` |
| J-12 | 🟠 | **13 `window.alert`/`confirm` nativos** num sistema com 4 modais próprios e um toast | `app.js`, `gdrive_config.js`, `oficios-documentos-inline.js`, `planos-trabalho-wizard.js`, `prestacoes-diaria-wa.js` |
| J-13 | 🟠 | **88 tokens `?v=` manuais**; 11 arquivos servidos com tokens divergentes; cadeia ESM bustada à mão em 3 níveis com 4 módulos de fora | §4.7 |
| J-14 | 🟠 | `masks.js` é carregado **duas vezes** em `diario_motorista_form.html` (base + página) | `diario_motorista_form.html:11` |
| J-15 | ✅ | **Corrigido:** `CV.documentSource` lê, seleciona, agrega e aplica campos de documento-fonte; Termos, OS e Diário-motorista usam o mesmo motor e contrato `data-source-document` | `document-source.js`, `termos-form.js`, `ordens-servico-form.js`, `diario-motorista.js` |
| J-16 | 🟡 | `debounce` redefinido em 5 arquivos; `escapeHtml` em 2 | §4.5 |
| J-17 | 🟡 | `eventos/detalhe.html` carrega `pages/oficios-dados-viajantes.js` — script de outro módulo | `eventos/detalhe.html` |
| J-18 | 🟡 | `oficios-transporte.js` (634 l.) carregado nas etapas 1 **e** 2 do ofício | `wizard_dados_viajantes.html:41` |
| J-19 | 🟡 | `console.error`/`warn`/`debug` em 4 arquivos sem canal de log centralizado | `autosave.js`, `fields-init.js`, `prestacoes-contas-documentos.js` |
| J-20 | 🟡 | `window.__prestDiariaWaBound` — guard de bind com flag global ad-hoc | `prestacoes-diaria-wa.js:7` |
| J-21 | 🟡 | 28 `<script>` em `base.html`, sem `type=module`, sem bundling; ordem importa e não é declarada | `base.html:62-87` |
| J-22 | 🟡 | Leaflet carregado de **CDN externa** (`unpkg.com`) em 2 páginas | `wizard_roteiro.html:6`, `roteiro_form_page.html:7` |

---

## 7. Auditoria página a página

Legenda: **✅** conforme · **⚠️** desvio · **❌** fora do padrão

### 7.1 Ofícios

| Página | HTML | JS |
|---|---|---|
| Lista | ⚠️ `list_page_cards` ✅; **J-03** dois motores de filtro; **J-02** menus de ação órfãos após filtro | ⚠️ `extra-download.js` **não** carregado apesar de `rich_menu_link` emitir o hook (**J-05**) |
| Etapa 1 | ✅ referência. ⚠️ header do card à mão (**H-05**); `form_block` sem `only` ×4 | ❌ 4 scripts de página, **nenhum** enhancer; `oficios-transporte.js` (634 l.) carregado aqui e na etapa 2 |
| Etapa 2 | ⚠️ campos direto no body, sem `form_block` (**RH-03**) | ⚠️ `app-motorista-picker.js` (264 l.) carregado; **nenhum template emite `data-app-motorista-picker`** → morto |
| Etapa 3 | ⚠️ delega a `_roteiro_editor.html`; card canônico condicional | ❌ ESM com cache-bust manual em 3 níveis (**J-13**); Leaflet de CDN (**J-22**); `roteiros_wizard.js` + `roteiros.js` + `roteiros-map.js` = 3 entradas |
| Etapa 4 | ✅ | ⚠️ `oficios-justificativa-wizard.js` — DOMContentLoaded |
| Etapa 5 | ⚠️ blocos com 5 aliases | ⚠️ `oficios-documentos-inline.js` com 4 tokens `?v=` diferentes entre páginas (**J-13**); 3 `window.alert` (**J-12**) |
| Modelos de motivo | ⚠️ Quick Add | ❌ Quick Add morre após filtro (**J-04**) |

### 7.2 Termos

| Página | HTML | JS |
|---|---|---|
| Lista | ❌ `list_page_standard` (linhas) | ⚠️ — |
| Cadastro | ✅ referência. ⚠️ `<header>` à mão; `form_block` sem `only` ×5; `<select>` com 7 classes (**H-09**) | ❌ `termos-form.js` (621 l.) reimplementa: cascata estado→cidade (**J-08**), prefill de ofício (**J-15**), CSRF (**J-07**), destinos com IDs `termo-*` (**H-07**) |
| Previews | ⚠️ `page-shell--standard-simple`; 18 classes `termo-*` sem CSS | — |

### 7.3 Ordens de Serviço

| Página | HTML | JS |
|---|---|---|
| Lista | ✅ `list_page_cards` | ⚠️ **J-03** |
| Cadastro | ✅ referência. ❌ shell com 6 classes; `<select>` com **8 classes** (recorde); `form_block` sem `only` ×5 | ❌ `ordens-servico-form.js` (**1.111 linhas**) — reimplementa cascata, prefill, CSRF, `debounce`, destinos `os-*`; expõe `window.OSFocusDestino` |

### 7.4 Eventos

| Página | HTML | JS |
|---|---|---|
| Lista | ✅ `list_page_cards` | ✅ único lugar com `extra-download.js` |
| **Painel guiado** | ❌ **30 includes** (recorde do sistema); 5 CSS de outros módulos; sem `wizard_base` | ❌ `eventos-detalhe.js` (490 l.) — **única** implementação que usa `estado.sigla` em vez de `pk` (**H-01**); carrega `pages/oficios-dados-viajantes.js` de outro módulo (**J-17**); `data-confirm-submit` dispara `confirm()` duplo (**J-11**) |
| Cadastro | ❌ não usa `form_block`; footer à mão | ⚠️ — |
| Tipos | ⚠️ Quick Add | ❌ **J-04** |

### 7.5 Roteiros

| Página | HTML | JS |
|---|---|---|
| Lista | ❌ `list_page_standard` | ⚠️ — |
| Roteiro avulso | ❌ editor sem card canônico quando avulso; `retorno-card`/`sec-retorno` com ID repetido (**H-07**) | ❌ `roteiros/editor/index.js` = **2.042 linhas**, o maior arquivo; 9 usos de `innerHTML`; CSRF manual; cascata própria; ESM mal bustado; `roteiros-map.js` (814 l.) com CSRF manual; 4 namespaces globais (`RoteirosEditor`, `RoteirosEditorModules`, `RoteirosMap`, `RoteirosMapBoot`) |
| Excluir | ⚠️ página de confirmação | — |

### 7.6 Planos de Trabalho

| Página | HTML | JS |
|---|---|---|
| Lista | ✅ `list_page_cards` | ⚠️ **J-03** |
| Etapas 1–4 | ⚠️ `wizard_base` ✅; card com 5–6 classes; `pt-*` IDs estáticos | ❌ `planos-trabalho-wizard.js` (**1.113 linhas**) carregado nas 3 primeiras etapas — cascata própria, CSRF via `getCookie` local, `window.confirm` (**J-12**), 7 `innerHTML` |
| Catálogos (4 listas) | ⚠️ Quick Add ×4 | ❌ **J-04** ×4 |
| Exclusões (4 páginas) | ❌ ×4 | — |

### 7.7 Prestações de Contas

| Página | HTML | JS |
|---|---|---|
| Lista | ✅ `list_page_cards` | ⚠️ **J-03**; `prestacoes-diaria-wa.js` com guard global ad-hoc (**J-20**) e 5 `window.alert` (**J-12**) |
| Etapa 1 — RT | ❌ **H-02** sem `wizard_base` | ⚠️ `prestacoes-contas-rt.js` (58 l.) DOMContentLoaded |
| Etapa 2 — Diário | ❌ **H-02** | ⚠️ 10 includes; `oficios-documentos-inline.js` de outro módulo |
| Etapa 3 — Troca motorista | ❌ **H-02**; composição sem card mestre | ❌ `masks.js` carregado **2×** (**J-14**); `diario-motorista.js` reimplementa prefill (**J-15**) |
| Etapa 4 — Documentos | ❌ **H-02**; **H-03** 30 atributos ordinais | ❌ `prestacoes-contas-documentos.js` (195 l.) é **órfão** — registra enhancer nunca carregado (**J-06**); os anexos dependem do `attach-signed-modal.js` global |
| Etapa 5 — PDF Final | ❌ **H-02** | ⚠️ — |
| Modelos de texto | ❌ 6ª variante de lista, montada à mão | — |
| **Assinatura pública** (5) | ❌ base própria fora de `base.html`; sem nenhum componente global | ❌ `prestacoes-assinatura.js` (427 l.) — `debounce` próprio, 6 listeners globais, zero reuso |

### 7.8 Cadastros

| Página | HTML | JS |
|---|---|---|
| Hub | ❌ usa classes do Dashboard | — |
| Servidores / Viaturas (form) | ✅ estrutura; ⚠️ shells divergentes | ⚠️ `servidores-form.js` e `viaturas-form.js` repetem o mesmo padrão de "criar registro sem sair da tela" com CSRF manual |
| Configurações | ⚠️ dois `<form>` irmãos, `form_block shell="card"` | ⚠️ `configuracoes.js` (180 l.) — `fetch` direto sem `CV.http` |
| 5 listas de catálogo | ⚠️ Quick Add | ❌ **J-04** ×5 |
| 3 exclusões | ❌ | — |

### 7.9 Núcleo / Conta / Admin

| Página | HTML | JS |
|---|---|---|
| Dashboard | ❌ classes locais; `<ul class="summary-items">` sem CSS | ✅ sem JS de página |
| Login | ❌ fora de `base.html`; **nenhum** script (nem tema) | ❌ o tema não é aplicado — a página é fixa |
| Perfil | ⚠️ **19 includes**; 3 footers à mão | ❌ `gdrive_config.js` (491 l.) — `escapeHtml` próprio, 6 `innerHTML`, CSRF manual, `alert()` |
| Administração | ❌ `admin-overview` com `<dl>` | — |
| Visualizador PDF | ⚠️ 8 classes sem CSS | ⚠️ `documentos-pdf-viewer.js` (200 l.) — pdf.js com `data-worker-src` |
| Placeholders (2) | ⚠️ `module_placeholder` | — |

---

## 8. Auditoria componente a componente

### 8.1 Componentes de template globais (`components/ui/`)

| Componente | HTML | JS que o serve | Problema |
|---|---|---|---|
| `page_header.html` | ✅ selado (`only`) | — | ✅ |
| `page_stepper.html` | ⚠️ não é `<nav>` | — | **H-08** |
| `filter_page_header.html` | ⚠️ dois ramos de markup para o mesmo papel | `realtime-filters` + `live-search-submit` | **J-03** |
| `form_block.html` | ⚠️ incluído sem `only` ×50 | — | **H-04**; não consegue selar interface |
| `field.html` | ⚠️ 16 includes internos; 3 contratos de classe | `fields-init.js` | ver auditoria CSS D-41 |
| `select.html` / `multiselect.html` | ✅ | `cv-custom-select.js` (enhancer ✅), `app-multiselect.js` (**órfão**) | **J-06** |
| `date_picker.html` | ⚠️ 13 includes; 9 `aria-expanded` sem `aria-controls` | `cv-date-picker.js` (902 l., enhancer ✅) | **H-06** |
| `file_picker.html` | ⚠️ `aria-expanded` sem `aria-controls`; `<label>` sem `for` | `file-picker.js` (enhancer ✅) | **H-06**, **H-10** |
| `card_toggle.html` | ⚠️ 2 `<label>` sem `for` | `card-toggle.js` (**sem enhancer**) | **J-01**, **H-10** |
| `dropdown.html` | ⚠️ `aria-expanded` sem `aria-controls` | `cv-floating-dropdown.js` | **H-06** |
| `document_number_field.html` | ✅ | `document-number-field.js` (**sem enhancer**) | **J-01** |
| `button.html` / `icon_button.html` | ✅ | — | ✅ |
| `chip.html` / `status_badge.html` | ✅ | — | ✅ |
| `alert.html` / `empty_state.html` / `field_error.html` | ⚠️ classes duplicadas | — | ver auditoria CSS |
| `pendencias_card.html` | ✅ | — | ✅ |
| 4 modais (`delete/cancel/confirm/attach_signed`) | ⚠️ markup quase idêntico | 4 arquivos JS (~520 l.) quase idênticos, **todos enhancers ✅** | candidatos a 1 componente + 1 motor |
| `confirm_delete.html` (página) | ❌ classes sem CSS | — | 5º padrão de confirmação |
| `dialog_header.html` | ✅ | `CV.dialogs` (`app.js`) ✅ | ✅ focus trap correto |
| `entity_card*.html` (4) | ⚠️ emitem `oficio-lc__*` | `action-menu.js` | **J-02** |
| `rich_menu_link.html` | ⚠️ emite `data-extra-download-url` | `extra-download.js` só em 1 página | **J-05** |
| `pagination.html` | ⚠️ não é `<nav>` | — | **H-08** |
| `data_table.html` | ⚠️ único `<table>` global; 7 no sistema | — | `--color-focus-ring` indefinido (CSS D-06) |
| `page_stepper` / `list_tabs` | ⚠️ nenhum é `<nav>` | — | **H-08** |

### 8.2 Componentes de domínio (`components/travel/`)

| Componente | Problema |
|---|---|
| `destination_section.html` + `destination_row.html` + `destinations/*` (5) | ✅ é o componente global correto — **mas só Eventos-novo e Roteiros-fonte o usam**; 4 módulos mantêm cópia (**H-01**) |
| `period_destinations_section.html` | ⚠️ composição de período + destino; sobrepõe `cv-travel-schedule` |
| `route_segments.html` | ⚠️ acoplado ao editor de roteiro |
| `travel_allowance_calculator.html` | ⚠️ idem |

### 8.3 Motores JS globais existentes

| Motor | Arquivo | Linhas | Ciclo de vida | Estado |
|---|---|---|---|---|
| **Registro de enhancers** | `core/app.js` | 77 | — | ✅ **correto, subutilizado (12/63)** |
| **Diálogos + focus trap** | `core/app.js` | 100 | delegação | ✅ correto |
| **HTTP/CSRF** | `core/http.js` | 99 | — | ✅ correto, **ignorado por 13 arquivos** |
| **Tema** | `core/theme-shared/-init` + `theme-toggle` | 124 | síncrono no `<head>` | ✅ correto |
| **Autosave** | `autosave.js` | 377 | DOMContentLoaded | ⚠️ sólido, mas sem enhancer e com listeners por form (**J-10**) |
| **Máscaras** | `components/masks.js` | 161 | DOMContentLoaded | ❌ **J-01** |
| **Campos (orquestrador)** | `components/fields-init.js` | 171 | DOMContentLoaded | ❌ **J-01** — é justamente o que deveria ser enhancer |
| **Select customizado** | `components/cv-custom-select.js` | 466 | enhancer | ✅ |
| **Picker de busca** | `components/cv-search-picker.js` | 872 | enhancer | ✅ |
| **Date picker** | `components/cv-date-picker.js` | 902 | enhancer | ✅ |
| **File picker** | `components/file-picker.js` | 274 | enhancer | ✅ |
| **Dropdown flutuante** | `components/cv-floating-dropdown.js` | 79 | IIFE | ⚠️ |
| **Dropdowns legados** | `cv-select.js` | 336 | DOMContentLoaded | ❌ **J-01**; sobrepõe `cv-custom-select` |
| **Coleções cliente/servidor** | `components/collection.js` | único | enhancer | ✅ **J-03** |
| **Menu de ações** | `components/action-menu.js` | 59 | delegação | ❌ **J-02** vazamento |
| **Tooltips** | `components/icon-tooltips.js` | 101 | delegação | ✅ |
| **Toggle de estado** | `components/state-toggle.js` | 256 | DOMContentLoaded | ❌ **J-01** |
| **Card toggle** | `components/card-toggle.js` | 94 | DOMContentLoaded | ❌ **J-01** |
| **Download de documento** | `components/document-download.js` | 214 | delegação | ✅ |
| **Download extra** | `components/extra-download.js` | 27 | delegação | ❌ **J-05** carregado em 1 página |
| **Assinatura (copiar/WhatsApp)** | `components/signature-actions.js` | 59 | delegação | ✅ |
| **Sidebar** | `components/sidebar.js` | 194 | DOMContentLoaded | ⚠️ aceitável (fora de área AJAX) |
| **Seção de destinos** | `components/destination-section.js` | 508 | IIFE | ❌ **J-01**; concorre com 5 cópias |
| **4 modais** | `delete/cancel/confirm/attach-signed` | 521 | enhancer | ✅ mas 4× o mesmo código |

### 8.4 Scripts de página (20 arquivos, 6.885 linhas)

| Arquivo | Linhas | O que reimplementa |
|---|---|---|
| `roteiros/editor/index.js` | 2.042 | cascata, CSRF, `escapeHtml`, picker, autosave próprio |
| `planos-trabalho-wizard.js` | 1.113 | cascata, CSRF, picker de coordenador, `confirm()` |
| `ordens-servico-form.js` | 1.111 | cascata, prefill, CSRF, `debounce`, picker |
| `roteiros-map.js` | 814 | CSRF |
| `oficios-transporte.js` | 634 | `debounce`, picker de viatura |
| `termos-form.js` | 621 | cascata, prefill, CSRF |
| `gdrive_config.js` | 491 | `escapeHtml`, CSRF, `alert()` |
| `eventos-detalhe.js` | 490 | cascata (com `sigla`), clonagem de template |
| `prestacoes-assinatura.js` | 427 | `debounce`, 6 listeners globais |
| `roteiros_wizard.js` | 398 | CSRF |
| `oficios-viatura-sugestoes.js` | 279 | picker |
| `oficios-wizard-driver-state.js` | 270 | estado de motorista |
| `documentos-pdf-viewer.js` | 200 | — |
| `prestacoes-contas-documentos.js` | 195 | **órfão** |
| `configuracoes.js` | 180 | `fetch` sem `CV.http` |
| `oficios-documentos-inline.js` | 156 | `alert()` |
| `prestacoes-diaria-wa.js` | 148 | `alert()`, guard global |
| `viaturas-form.js` | 139 | criar-sem-sair |
| `servidores-form.js` | 119 | criar-sem-sair |
| `diario-motorista.js` | 108 | prefill |

**~40% dessas linhas são reimplementação de capacidades que já existem como motor global.**

---

## 9. Dicionário de renomeação

Princípio (o mesmo da auditoria de CSS): **o nome descreve a função, nunca a página**. Aqui vale para três eixos: caminho de template, hook `data-*` e namespace JS.

### 9.1 Templates — reorganização por função

| Hoje | Proposto |
|---|---|
| `components/ui/headers/page_header.html` | `components/page/header.html` |
| `components/ui/headers/filter_page_header.html` | `components/collection/header.html` |
| `components/ui/navigation/page_stepper.html` | `components/page/stepper.html` |
| `components/lists/list_page_standard.html` | `components/collection/page_rows.html` |
| `components/lists/list_page_cards.html` | `components/collection/page_cards.html` |
| `components/lists/list_page_quick_add.html` | `components/collection/page_inline_create.html` |
| `components/lists/list_tabs.html` | `components/collection/tabs.html` |
| `components/lists/simple_list.html` / `simple_list_row.html` | `components/collection/row_list.html` / `row.html` |
| `components/lists/main_list_card.html` | ❌ **apagar** (morto) |
| `components/ui/lists/entity_card*.html` | `components/collection/record_card*.html` |
| `components/ui/lists/pagination.html` | `components/collection/pagination.html` |
| `components/ui/lists/file_list.html` | `components/file/list.html` |
| `components/ui/forms/form_block.html` | `components/form/block.html` |
| `components/ui/forms/field.html` | `components/form/field.html` |
| `components/ui/forms/*` (select, multiselect, date_picker, file_picker, card_toggle, dropdown, document_number_field) | `components/form/*` |
| `components/ui/layouts/card_footer_section.html` / `card_footer_actions.html` | `components/form/card_footer.html` (um só) |
| `components/ui/modals/*` (5) | `components/overlay/dialog_*.html` |
| `components/ui/feedback/*` | `components/feedback/*` (unificar com a pasta existente) |
| `components/ui/badges/chip.html` / `status_badge.html` | `components/primitives/chip.html` / `status.html` |
| `components/ui/buttons/*` (7) | `components/primitives/button*.html` |
| `components/ui/icons/icon.html` | `components/primitives/icon.html` |
| `components/ui/menus/rich_menu_*.html` | `components/overlay/menu_*.html` |
| `components/ui/tables/data_table.html` | `components/collection/table.html` |
| `components/travel/destination*` + `destinations/*` | `components/form/location_rows*.html` |
| `components/travel/period_destinations_section.html` | `components/form/period_and_locations.html` |
| `components/travel/route_segments.html` | `components/itinerary/segments.html` |
| `components/travel/travel_allowance_calculator.html` | `components/itinerary/allowance.html` |
| `components/cards/summary_card.html` | `components/primitives/metric.html` |
| `components/cards/document_card.html` | `components/document/card.html` |
| `components/cards/module_card.html` | `components/collection/module_card.html` |
| `components/documents/pdf_viewer.html` / `signature_card.html` | `components/document/pdf_viewer.html` / `signature.html` |
| `components/perfil/gdrive_card.html` | `components/integration/drive_card.html` |
| `components/create_draft.html` | `components/form/draft_create.html` |
| **novo** | `components/page/flow_base.html` — base de wizard única (resolve **H-02**) |
| **novo** | `components/form/card.html` — card mestre com header (resolve **H-05**) |

### 9.2 Hooks `data-*` — de nome-de-módulo para nome-de-função

| Hoje (N variantes) | Proposto (1) |
|---|---|
| `data-os-destination-row`, `data-pt-destination-row`, `data-termo-destination-row`, `data-destination-row`, `data-destino-uf-extra`, `class="destino-estado"` | **`data-location-row`** |
| `data-os-destino-state/-city`, `data-pt-destino-state/-city`, `data-termo-destino-state/-city`, `data-{{prefix}}-destino-state/-city` | **`data-location-state`** / **`data-location-city`** |
| `data-os-destino-template`, `data-pt-destino-template`, `data-termo-destino-template`, `data-destino-extra-template` | **`data-location-template`** |
| `data-os-remove-destino`, `data-pt-remove-destino`, `data-termo-remove-destino` | **`data-location-remove`** |
| `data-evento-add-destino`, `data-termo-add-destino`, `data-destination-add`, `#btn-adicionar-destino` | **`data-location-add`** |
| `data-oficio-viatura-*` (13 atributos), `data-oficio-vehicle-picker`, `data-app-motorista-picker`, `data-pt-coordenador-picker`, `data-dmv-picker`, `data-oficio-equipe-picker` | **`data-entity-picker`** + `data-entity-picker-kind="vehicle\|person\|program"` |
| `data-termo-oficio-summary/-destino/-periodo/-servidores/-viatura`, `data-oficios` (OS), `data-oficios` (DMV) | **`data-source-document`** + `data-source-document-fields` |
| `data-attach-signed-{primary…quinary}-*` (30 atributos) | **`data-attach-signed`** com JSON: `[{url, label, currentName, viewUrl, removeUrl}]` |
| `data-travel-document-wizard-shell/-form/-step1/-rt/-documentos/-consolidado/-diario/-roteiro`, `data-os-wizard-shell/-form`, `data-pt-wizard-shell`, `data-termo-wizard-shell/-form` | **`data-flow`** + `data-flow-step="<slug>"` |
| `data-quick-add-toggle/-close/-submit-when-open/-save-label`, `data-quick-edit`, `data-edit-url`, `data-edit-fields` | **`data-inline-create-*`** / **`data-inline-edit-*`** |
| `data-cv-realtime-filter-scope` + `data-cv-live-submit-form` | ✅ **`data-collection`** + `data-collection-mode="client\|server"` |
| `data-cv-filter`, `data-cv-filter-item`, `data-cv-filter-clear` | ✅ `data-collection-filter`, `data-collection-item`, `data-collection-clear` |
| `data-oficio-glance-*`, `data-oficio-sticky-header`, `data-oficio-toggle`, `data-oficio-termos-selector`, `data-app-multiselect`, `data-filterable-multiselect-input`, `data-viatura-motorista-form/-panel` | ❌ **apagar** (JS órfão) |
| `data-wa-*` (8 atributos) | **`data-share-whatsapp`** com JSON |
| `data-rt-*` (6), `data-modelo-justificativa-select`, `data-modelo-motivo-select`, `data-texto-modelo` | **`data-text-template-*`** |
| `data-pt-activity*`, `data-pt-diarias-*`, `data-pt-efetivo-*` | **`data-checklist-*`**, **`data-allowance-*`**, **`data-roster-*`** |

### 9.3 Namespaces JS — colapsar 22 em 1

| Hoje | Proposto |
|---|---|
| `window.MaskEngine` | `CV.masks` (já existe — remover o alias) |
| `window.CvSelect` | `CV.dropdowns` (idem) |
| `window.AppAutosave` | `CV.autosave` (idem) |
| `window.CVRealtimeFilters` | `CV.filters` (idem) |
| `window.CvCustomSelect` / `CvSearchPicker` / `CvDatePicker` / `CvFloatingDropdown` | `CV.fields.select` / `.picker` / `.datePicker` / `.dropdown` |
| `window.AppMultiselect` / `AppMotoristaPicker` / `CvFilterableMultiselect` | ❌ apagar (órfãos) |
| `window.AppAutosaveSnapshots` / `AppAutosaveValidators` | `CV.autosave.snapshots` / `.validators` |
| `window.RoteirosEditor` / `RoteirosEditorModules` / `RoteirosMap` / `RoteirosMapBoot` | `CV.itinerary.editor` / `.map` |
| `window.OficioWizard` / `OSFocusDestino` | `CV.flow.*` |
| `window.__prestDiariaWaBound` | ❌ substituir pelo guard padrão do enhancer |
| `window.DEBUG_AUTOSAVE` | `CV.debug.autosave` |

---

## 10. Catálogo dos motores globais propostos

Alvo: **16 motores globais**, todos registrados via `CV.registerEnhancer`, todos com `init(root)` idempotente, todos com contrato `data-*` funcional. Nenhum script de página com mais de ~150 linhas.

### 10.1 Núcleo (sempre carregado)

| # | Motor | Substitui | Responsabilidade |
|---|---|---|---|
| 1 | **`CV.registry`** | `core/app.js` (parte 1) | Registro + `MutationObserver` + isolamento de erro. **Único ponto de inicialização do sistema.** Adicionar: `destroy(root)` para limpeza de nós removidos (resolve **J-02**) |
| 2 | **`CV.http`** | `core/http.js` | `fetch` com CSRF, 401/403, JSON vs HTML. **Proibir `fetch()` cru** (resolve **J-07**) |
| 3 | **`CV.theme`** | `theme-shared` + `theme-init` + `theme-toggle` | ✅ já correto — só consolidar em um arquivo |
| 4 | **`CV.util`** | `debounce` ×5, `escapeHtml` ×2, `normalize` ×10 | Utilitários únicos (resolve **J-16**) |
| 5 | **`CV.feedback`** | 13 `alert`/`confirm` + `cv-document-loading` + 4 modais | Toast, confirmação e progresso. **Proibir `window.alert`/`confirm`** (resolve **J-12**) |

### 10.2 Formulário

| # | Motor | Substitui | Contrato |
|---|---|---|---|
| 6 | **`CV.fields`** | `fields-init` + `masks` + `state-toggle` + `card-toggle` + `cv-select` + `document-number-field` | Enhancer único que varre `root` e inicializa todo controle. Resolve **J-01** para 6 arquivos |
| 7 | **`CV.picker`** | ✅ substituiu `cv-search-picker` + `cv-custom-select`; motores órfãos já removidos; comportamentos de domínio operam sobre o select canônico | `data-entity-picker` + `data-entity-picker-mode="single\|multi"` |
| 8 | **`CV.datePicker`** | `cv-date-picker` | ✅ já enhancer — só padronizar `aria-controls` (**H-06**) |
| 9 | **`CV.filePicker`** | `file-picker` | ✅ já enhancer |
| 10 | **`CV.autosave`** | `autosave.js` | Virar enhancer; **um** listener global de `beforeunload`/click em vez de um por form (resolve **J-10**) |
| 11 | **`CV.locationRows`** | ✅ substituiu `destination-section` + 5 cópias por módulo | `data-location-row/-state/-city/-add/-remove/-template`. Cascata estado→cidade **única**, contrato de valor **único** (`pk`). **H-01/J-08 resolvidos** |
| 12 | **`CV.documentSource`** | prefill em `termos-form` + `ordens-servico-form` + `diario-motorista` | `data-source-document` + JSON de campos. Resolve **J-15** |

### 10.3 Coleções

| # | Motor | Substitui | Contrato |
|---|---|---|---|
| 13 | **`CV.collection`** | `realtime-filters` + `live-search-submit` | **Um** motor, modo declarado: `data-collection-mode="client\|server"`. Nunca os dois na mesma lista. Após `replaceWith`, chamar `CV.registry.destroy(old)` + `enhance(new)`. Resolve **J-03**/**J-04** |
| 14 | **`CV.inlineCreate`** | Quick Add + Quick Edit (`app.js:183-425`) | Virar enhancer com delegação; sobrevive ao swap. Resolve **J-04** |

### 10.4 Overlays e ações

| # | Motor | Substitui | Contrato |
|---|---|---|---|
| 15 | **`CV.overlay`** | `action-menu` + `cv-floating-dropdown` + 4 modais + `CV.dialogs` | Portal com **registro de nós movidos** e limpeza no `destroy` (resolve **J-02**). Um único `openDialog(config)` para os 4 modais (~520 linhas → ~180) |
| 16 | **`CV.actions`** | `document-download` + `extra-download` + `signature-actions` + `icon-tooltips` + `prestacoes-diaria-wa` | Delegação global de ações declarativas: download (com extras), copiar, compartilhar, tooltip. Carregado sempre. Resolve **J-05** |

### 10.5 O que sobra como script de página

Depois dos 16 motores, cada módulo mantém apenas regra de negócio:

| Página | Hoje | Depois (estimativa) |
|---|---|---|
| Editor de roteiro | 2.042 + 814 + 398 = **3.254** | ~700 (cálculo de trechos/diárias + integração de mapa) |
| Plano de Trabalho | 1.113 | ~200 (multi-evento) |
| Ordens de Serviço | 1.111 | ~150 (funções de servidor) |
| Termos | 621 | ~80 |
| Ofícios (4 scripts) | 1.279 | ~250 (estado de motorista) |
| Eventos | 490 | ~120 |
| Google Drive | 491 | ~200 |
| Assinatura pública | 427 | ~250 (canvas de assinatura) |
| Demais | ~1.100 | ~300 |
| **Total de scripts de página** | **~9.800** | **~2.250** |

Somando os motores (~4.500 linhas), a projeção é de **18.301 → ~7.000 linhas**.

---

## 11. Contrato único de `data-*`

Regra: um hook tem **exatamente um** motor dono; o nome descreve a função; valores complexos vão em JSON, nunca em ordinais.

### 11.1 Gramática

```
data-<motor>                       → ativa o motor no elemento
data-<motor>-<opção>               → configuração escalar
data-<motor>-config='{"…":"…"}'    → configuração complexa (JSON)
data-<motor>-<papel>               → papel de um filho (trigger, panel, item…)
```

### 11.2 Tabela canônica

| Motor | Ativação | Papéis | Config |
|---|---|---|---|
| `CV.collection` | `data-collection` | `data-collection-filter`, `-item`, `-clear`, `-container`, `-empty` | `data-collection-mode`, `-debounce` |
| `CV.inlineCreate` | `data-inline-create` | `-toggle`, `-panel`, `-close`, `-submit` | `-mode="create\|edit"`, `-labels` |
| `CV.locationRows` | `data-location-rows` | `-row`, `-state`, `-city`, `-add`, `-remove`, `-template` | `-api-url`, `-max`, `-value-kind="pk"` |
| `CV.picker` | `data-entity-picker` | `-input`, `-menu`, `-option`, `-selected`, `-clear` | `-kind`, `-mode="single\|multi"`, `-url` |
| `CV.datePicker` | `data-date-picker` | `-trigger`, `-panel`, `-input` | `-mode="single\|range\|multi"`, `-variant` |
| `CV.filePicker` | `data-file-picker` | `-input`, `-list`, `-item`, `-remove` | `-accept`, `-autosave-url` |
| `CV.autosave` | `data-autosave` | — | `-model`, `-step`, `-url`, `-create-url`, `-object-id` |
| `CV.overlay` | `data-overlay-trigger` | `-target`, `-close`, `-panel` | `-kind="menu\|dialog\|dropdown"`, `-tone` |
| `CV.actions` | `data-action` | — | `-download`, `-download-extra`, `-copy`, `-share`, `-tooltip`, `-confirm` |
| `CV.documentSource` | `data-source-document` | — | `-fields` (JSON), `-summary-id` |
| `CV.fields` | (implícito no `root`) | — | — |
| `CV.flow` | `data-flow` | `-step`, `-next`, `-prev` | `-model` |

### 11.3 Exemplo do maior ganho — anexo de documento assinado

**Hoje** (30 atributos, arity fixa em 5):
```html
<button data-attach-signed-trigger
        data-attach-signed-url="…"           data-attach-signed-doc-label="…"
        data-attach-signed-secondary-url="…" data-attach-signed-secondary-doc-label="…"
        data-attach-signed-tertiary-url="…"  … (×5)>
```

**Proposto** (1 atributo, arity livre):
```html
<button data-overlay-trigger data-overlay-kind="dialog" data-overlay-target="attach-signed"
        data-attach-signed='[
          {"url":"…","label":"Ofício","currentName":"…","viewUrl":"…","removeUrl":"…"},
          {"url":"…","label":"Despacho"}
        ]'>
```

---

## 12. Ordem de execução sugerida

Cada fase é independente, verificável e não depende da reconstrução do CSS.

| Fase | Ação | Resolve | Ganho |
|---|---|---|---|
| **0** | ✅ Apagar os 9 arquivos JS órfãos e os hooks `data-*` sem dono ainda emitidos | J-06 | −989 linhas |
| **1** | Carregar `extra-download.js` no bundle base; remover `masks.js` duplicado de `diario_motorista_form.html` | J-05, J-14 | Recurso morto volta a funcionar em 4 módulos |
| **2** | Corrigir `data-confirm-submit` (escutar só `submit`) | J-11 | Fim do `confirm()` duplo |
| **3** | ✅ Adicionar `CV.registry.destroy(root)` e chamá-lo antes de `replaceWith` em `live-search-submit`; `action-menu` devolve o menu ao dono no `destroy` | J-02 | Fim dos nós órfãos e IDs duplicados |
| **4** | ✅ Registrar como enhancer: `fields-init`, `masks`, `state-toggle`, `card-toggle`, `cv-select`, `document-number-field`, `destination-section`, `autosave` | J-01, J-04 | 8 componentes passam a sobreviver ao AJAX |
| **5** | ✅ Quick Add/Quick Edit pertencem ao enhancer idempotente `CV.inlineCreate` | J-04 | Quick Add volta a funcionar após filtro |
| **6** | ✅ Escolher **um** motor de filtro por lista (`data-collection-mode`) | J-03 | Fim do duplo filtro nas 5 listas em card |
| **7** | Proibir `fetch()` cru: migrar os 13 arquivos para `CV.http`; apagar as 11 cópias de CSRF | J-07 | Tratamento único de erro/sessão |
| **8** | Criar `CV.util` (debounce, escapeHtml, normalize) e remover as 17 cópias | J-16 | — |
| **9** | Criar `CV.feedback`; substituir os 13 `alert`/`confirm` | J-12 | Feedback consistente com o design system |
| **10** | Criar `components/page/flow_base.html` e migrar Prestações (5), Termos, OS, Eventos-detalhe, Roteiro-avulso | H-02 | −180 linhas de estrutura duplicada |
| **11** | Criar `components/form/card.html` (card mestre com header) e migrar as 20+ páginas | H-05 | Fim do header à mão |
| **12** | Criar `CV.locationRows` + `components/form/location_rows.html`; migrar os 6 módulos; unificar contrato em `estado.pk` | H-01, J-08 | −20 templates, −950 linhas de JS |
| **13** | ✅ Criar `CV.documentSource`; migrar Termos, OS e Diário-motorista | J-15 | −3 implementações |
| **14** | ✅ Criar `CV.picker`; unificar hooks, namespace, enhancer e renderers vivos | — | Um contrato de seleção |
| **15** | Criar `CV.overlay`; fundir os 4 modais e o action-menu | J-02 | −340 linhas |
| **16** | Colapsar os 22 namespaces em `CV.*` | J-09 | — |
| **17** | Trocar os 88 `?v=` manuais por `ManifestStaticFilesStorage` (hash automático); remover os `?v=` dos `import` ESM | J-13 | Fim da cache incoerente |
| **18** | Refatorar `form_block.html` para receber `context` explícito e incluir o body com `only` | H-04 | Componentes seláveis e testáveis |
| **19** | Semântica: `<nav>` em stepper/abas/paginação; `<ul>`/`<table>` nas listas de dados; `<footer>` nos rodapés de card | H-08 | — |
| **20** | Adicionar `aria-controls` nos 29 `aria-expanded`; `for`/`id` nos 14 `<label>` | H-06, H-10 | — |
| **21** | Renomear hooks e templates conforme §9 | — | — |
| **22** | Bundling: um `app.js` para o núcleo + chunks por módulo; hospedar Leaflet localmente | J-21, J-22 | 28 requisições → 2–3 |
| **23** | Testes de CI: (a) todo `data-*` emitido tem motor; (b) todo JS de componente registra enhancer; (c) nenhum `fetch(`/`window.alert`/`window.confirm` fora do núcleo; (d) nenhum include de componente sem `only` | — | Trava a regressão |

---

## Anexo A — Arquivos JS órfãos (apagar na Fase 0)

| Arquivo | Linhas | Hooks que morrem junto |
|---|---|---|
| `components/app-multiselect.js` | 278 | `data-app-multiselect` |
| `components/app-motorista-picker.js` | 264 | `data-app-motorista-picker` (carregado, mas sem hook emitido) |
| `pages/prestacoes-contas-documentos.js` | 195 | enhancer `prestacaoDocumentos` |
| `oficios_termos_selector.js` | 113 | `data-oficio-termos-selector` |
| `components/viatura-motorista-fixo.js` | 52 | `data-viatura-motorista-form`, `data-viatura-motoristas-panel` |
| `components/filterable-multiselect.js` | 45 | `data-filterable-multiselect-input` |
| `components/oficio-collapse.js` | 19 | `data-oficio-glance-panel/-toggle/-toggle-label`, `data-oficio-sticky-header`, `data-oficio-toggle` |
| `pages/assinaturas-central.js` | 14 | — |
| `pages/roteiros/editor/utils.js` | 9 | — |
| **Total** | **989** | **~11 hooks** |

## Anexo B — Templates duplicados a colapsar

| Grupo | Arquivos hoje | Depois |
|---|---|---|
| Selects de estado/cidade do destino | 11 (`components/travel/destinations/*` + 6 de Eventos + 2 de Roteiros) | 2 |
| Linhas/seções de destino | 9 (`_destinos_rows_*`, `_evento_destinos_section` ×2, `_identificacao_evento_destinos`, `destination_row/_section`, `rows.html`, `row_template.html`) | 2 |
| Base de wizard | 2 (`oficios/wizard_base`, `planos_trabalho/wizard_base`) + 8 páginas com estrutura repetida | 1 |
| Header de card mestre | 20+ cópias inline | 1 (`components/form/card.html`) |
| Header de lista | `filter_page_header.html` + cópia inline em `list_page_quick_add.html:3-11` | 1 |
| Modais | 5 templates + 4 JS | 1 template + 1 motor |
| Card de lista | `entity_card*` (4) + `main_list_card` (morto) + `roteiro_list_card` (morto) | 4 |
| Cards de anexo assinado | `_docs_attach_card`, `_docs_attach_trigger`, `_docs_attach_kinds_attrs` | 1 |

## Anexo C — Matriz motor × página (estado atual)

| Motor | Ofícios | Termos | OS | Eventos | Roteiros | PT | Prestações | Cadastros |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Filtro cliente | ✓ | – | ✓ | ✓ | – | ✓ | ✓ | – |
| Filtro servidor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| **Conflito dos dois** | ⚠️ | – | ⚠️ | ⚠️ | – | ⚠️ | ⚠️ | – |
| Autosave | ✓ | – | – | ✓ | ✓ | ✓ | ✓ | – |
| Cascata destino | próprio | próprio | próprio | **próprio (sigla)** | próprio | próprio | – | – |
| Prefill de ofício | – | próprio | próprio | – | – | – | próprio | – |
| Picker de entidade | global+próprio | global | global | global | global | global+próprio | global | global |
| Menu de ações | ✓ | ✓ | ✓ | ✓ | – | ✓ | ✓ | ✓ |
| Download extra | ✗ hook sem motor | ✗ | ✗ | ✓ | – | ✗ | ✗ | – |
| Anexar assinado | ✓ | ✓ | – | ✓ | – | – | ✓ | – |
| Quick Add | ✓ catálogos | – | – | ✓ tipos | – | ✓ catálogos | ✓ modelos | ✓ 5 listas |
