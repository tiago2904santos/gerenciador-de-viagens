# Auditoria visual completa — tema escuro

**Escopo:** 100% das páginas de produção, componente por componente, apenas tema escuro (`html[data-theme="dark"]`).
**Objetivo:** listar toda inconsistência visual e estrutural, propor renomeação funcional de todos os componentes, definir o conjunto de componentes globais e o plano de tokenização para reconstruir o CSS do zero.
**Data do levantamento:** 27/07/2026
**Este documento não altera código.** É o mapa para a reconstrução.

---

## Índice

1. [Método e números do sistema](#1-método-e-números-do-sistema)
2. [O padrão de referência (destilado das 4 páginas aprovadas)](#2-o-padrão-de-referência)
3. [Diagnóstico estrutural — a arquitetura de CSS](#3-diagnóstico-estrutural)
4. [Catálogo de defeitos — tema escuro](#4-catálogo-de-defeitos--tema-escuro)
5. [Auditoria página a página](#5-auditoria-página-a-página)
6. [Auditoria componente a componente](#6-auditoria-componente-a-componente)
7. [Dicionário de renomeação — de nome-de-página para nome-de-função](#7-dicionário-de-renomeação)
8. [Catálogo dos componentes globais propostos](#8-catálogo-dos-componentes-globais-propostos)
9. [Plano de tokenização — nenhum valor hardcoded](#9-plano-de-tokenização)
10. [Ordem de execução sugerida](#10-ordem-de-execução-sugerida)

---

## 1. Método e números do sistema

### 1.1 Como foi feito

- Inventário automático de **76 páginas** de produção (excluídos UI Lab, `ui_lab2`, templates de PDF).
- Inventário de **369 templates** e **62 arquivos CSS** (40.135 linhas; 36.771 fora do UI Lab).
- Extração de: shell de página, componente de cabeçalho, quantidade de section-cards, quantidade de `form_block`, níveis de heading, CSS carregado por página.
- Cruzamento de **982 tokens definidos** × **845 tokens usados** para achar órfãos e indefinidos.
- Cruzamento de **1.429 classes usadas em templates** × todas as classes definidas em CSS, para achar classes sem estilo.
- Análise de propriedade: quais arquivos estilizam a mesma classe (detecção de conflito).
- Varredura de cores hardcoded fora de `:root` e fora de blocos `data-theme`.

### 1.2 Números que definem o problema

| Métrica | Valor | Leitura |
|---|---|---|
| Linhas de CSS (produção) | **36.771** | Insustentável para a superfície real do sistema |
| Arquivos CSS | 62 | Sem fronteira clara entre global e módulo |
| Tokens definidos | 982 | 4 camadas concorrentes de token |
| Tokens usados | 845 | ~137 tokens definidos e nunca usados |
| **Tokens usados e nunca definidos** | **18** | Declarações inválidas → bugs visuais reais |
| Regras `!important` | 165 | 109 só em `dark-redesign.css` |
| Cores hardcoded fora de `:root`/tema | **318 regras** | O oposto de tokenizado |
| Seletores de tema mortos | **1.100+ linhas** | `dark-dark`, `light-dark`, `dark-light`, `light-light` |
| Classes usadas em template sem CSS | **~120** | Inclui componentes globais inteiros |
| Classes estilizadas em 3+ arquivos | **146** | `.cv-btn` em 16 arquivos, `.cv-field__control` em 11 |
| Estilos inline (`style="..."`) em templates | **0** | ✅ único ponto totalmente limpo |

---

## 2. O padrão de referência

Destilado de: **Ofícios etapa 1** (`wizard_dados_viajantes.html`), **Ofícios etapa 2** (`wizard_transporte.html`), **Termos** (`termos/form.html`), **Ordens de Serviço** (`ordens_servico/form.html`), e das listas de **Ofícios** e **Eventos**.

### 2.1 Anatomia da página de formulário aprovada

```
page-shell page-shell--wizard
├── page_header.html            → .page-header-stack
│   ├── .page-header-band       (faixa escura: eyebrow + h1 + status chip)
│   └── .page-header-rail       (marcador + módulo + descrição + ação de voltar)
├── page_stepper.html           → .page-stepper           [só wizard]
└── .main-form-panel.main-form-panel--stack
    └── .cv-form-section-stack.cv-form-section-stack--comfortable
        └── <form>
            └── section.cv-form-section-card.cv-form-card.cv-form-section-card--described
                ├── header.cv-form-section-header
                │   └── .cv-form-section-header__copy
                │       ├── h2/h3.cv-form-section-title
                │       └── p.cv-form-section-subtitle
                ├── .cv-form-section-body
                │   └── N × form_block.html   → .cv-form-block[--split|--resource]
                │       ├── header.cv-form-block__header
                │       │   ├── .cv-form-block__copy (title + description)
                │       │   └── .cv-form-block__actions
                │       └── .cv-form-block__body
                └── .cv-form-card__footer
                    └── card_footer_section.html → .cv-card-footer-section
```

**Regras implícitas do padrão:**

1. Uma página = **um** card mestre. Todo o conteúdo vive em `form_block` dentro dele.
2. O card mestre tem sempre título + subtítulo (`--described`).
3. Ações finais só no `cv-form-card__footer`, via `card_footer_section.html`.
4. O cabeçalho da página nunca contém botão de submit (só "Voltar à lista").
5. `form_block` tem 3 variantes: padrão (empilhado), `split` (copy à esquerda, campos à direita), `resource` (picker de entidade com botão "Novo X" no header). Subseções internas usam `cv-form-subsection` (e `--split` quando o copy e os campos cabem na mesma linha).
6. Campos sempre via `field.html` dentro de `.field-grid` com `field-size-1..4`.

### 2.2 Anatomia da lista aprovada

```
page-shell page-shell--list page-shell--cards
├── filter_page_header.html (advanced=True)  → .list-header.cv-filter-header
│   ├── .list-header__band  (faixa escura: eyebrow + h1)
│   └── .list-header__rail  (busca + selects + date picker + limpar)
├── list_tabs.html                            → .cv-list-tabs
└── .list-panel
    ├── pagination.html                       → .pagination-shell
    └── .cv-card-grid
        └── N × entity_card.html              → .cv-entity-card
            ├── entity_card_header.html
            ├── <body_template do módulo>
            └── entity_card_footer.html
└── floating_action.html (FAB "Novo X")
```

### 2.3 Desvios já presentes DENTRO das próprias páginas de referência

Mesmo o padrão aprovado não é internamente coerente:

| # | Desvio | Onde |
|---|---|---|
| R-01 | Ofícios usa `page-shell--wizard`; Termos e OS usam `page-shell--standard` para composição idêntica | `termos/form.html:15`, `ordens_servico/form.html:16` |
| R-02 | Título do card mestre é `<h2>` em Ofícios e `<h3>` em Termos/OS — mesma classe `.cv-form-section-title` | `wizard_dados_viajantes.html:14` vs `termos/form.html:40` |
| R-03 | Termos e OS carregam `travel-document-wizard` e `app-wizard` sem serem wizard | `termos/form.html:15` |
| R-04 | O mesmo bloco recebe 2–5 aliases de classe: `travel-document-block document-form-block os-block` | `ordens_servico/form.html:41-49` |
| R-05 | Termos carrega 4 CSS de outros módulos: `roteiros.css`, `oficios-documentos-inline.css`, `prestacoes_contas.css` | `termos/form.html:7-10` |
| R-06 | Lista de Ofícios carrega `roteiros-list.css` (599 linhas) para renderizar cards de ofício | `oficios/index.html:7` |
| R-07 | `entity_card.html` — componente **global** — emite classes `oficio-lc__*` em todos os módulos | `components/ui/lists/entity_card.html:5` |

---

## 3. Diagnóstico estrutural

### 3.1 Quatro camadas de token concorrentes

Ordem de carregamento real (de `base.html`):

```
1. style.css  →  @import tokens.css         (:root — escala + valores claros)
                 @import theme.css          (:root + [dark] + [light] — semânticos)
                 @import ... oficios.css (4.495 linhas, GLOBAL)
                 @import auth.css (282 linhas, só usado no login — GLOBAL)
2. utilities.css
3. page-shell.css                            (:root + [dark] + [light] — --surface-*/--border-*/--stepper-*)
4. cv-buttons.css                            (:root + [dark] — --cv-btn-*)
5. components/*.css                          (estrutura, quase sem cor)
6. dark-redesign.css                         (5.297 linhas — REDEFINE tudo de novo no dark)
7. components/list-header.css
```

**Consequência:** o mesmo token é definido até 4 vezes com valores diferentes. Exemplos verificados:

| Token | `tokens.css` | `theme.css` [dark] | `page-shell.css` [dark] | `dark-redesign.css` [dark] | Vencedor |
|---|---|---|---|---|---|
| `--color-surface-muted` | `#f8fafd` | `#172638` | — | `#131f2e` | dark-redesign |
| `--cv-form-section-bg` | `var(--surface-form-section)` | — | `var(--color-surface)` | `var(--cv-card-family-bg)` | dark-redesign |
| `--cv-btn-height` | `36px` | — | — | (via `cv-buttons.css` = `44px`) | cv-buttons |
| `--shadow-card` | `var(--shadow-md)` | `0 14px 34px rgba(0,0,0,.38)` | — | `0 1px 0 …inset, 0 14px 34px rgba(0,0,0,.42)` | dark-redesign |
| `--color-muted` | `#52657a` | **não define** | — | `#aebfd4` | dark-redesign |

A linha `--color-muted` é a mais grave: se `dark-redesign.css` for removido, o tema escuro herda cinza-claro do tema claro. **`dark-redesign.css` não é uma camada de ajuste — é o tema escuro inteiro.**

### 3.2 Seletores de tema mortos (~1.100 linhas de peso zero)

`static/js/core/theme-shared.js` normaliza qualquer valor para **`"dark"` ou `"light"`**:

```js
var VALID_THEMES = ["dark", "light"];
// LEGACY_THEMES mapeia dark-dark/light-dark/dark-light/light-light → dark|light
```

`theme-init.js` e `theme-toggle.js` só escrevem o valor normalizado em `data-theme`. Portanto:

| Seletor | Ocorrências | Status |
|---|---|---|
| `html[data-theme="dark"]` | 801 | ✅ vivo |
| `html[data-theme="light"]` | 26 | ✅ vivo |
| `html[data-theme="dark-dark"]` | 860 | ❌ **morto** |
| `html[data-theme="light-dark"]` | 860 | ❌ **morto** |
| `html[data-theme="light-light"]` | 15 | ❌ **morto** |
| `html[data-theme="dark-light"]` | 15 | ❌ **morto** |

`dark-redesign.css` repete o trio de seletores **655 vezes**. Só ali são ~737 linhas de seletor sem efeito.

Pior: há uma **contradição silenciosa** — `theme.css:408` coloca `dark-light` no bloco **claro**, enquanto `theme-shared.js` mapeia `"dark-light" → "dark"`. Se qualquer valor legado sobrevivesse, a página ficaria clara com JS achando que é escura.

### 3.3 Tokens usados e nunca definidos (18) — cada um é um bug visual

| Token | Consumido em | Efeito no tema escuro |
|---|---|---|
| `--theme-card-bg` | `components/document-download-loading.css:22` | **Toast global "Gerando documento…" sem fundo** |
| `--theme-shadow-card` | `components/document-download-loading.css:24` | Mesmo toast sem sombra |
| `--color-text-strong` | `planos-trabalho-eventos.css:86,135` | **`#0f172a` (quase preto) sobre card escuro — texto invisível** |
| `--color-info-strong` | `planos-trabalho-eventos.css:17` | `#1d4ed8` sobre banner escuro — ilegível |
| `--color-warning-border` | `planos-trabalho-eventos.css:171` | Borda âmbar fora da paleta do sistema |
| `--font-size-base` | `dark-redesign.css`, `page-shell.css`, `planos-trabalho-eventos.css:85` | Declaração inválida → tamanho herdado imprevisível |
| `--color-focus-ring` | `utilities.css:470` (sem fallback) | **`.cv-data-table-shell` sem anel de foco** |
| `--motion-fast` | `dark-redesign.css` | Transição inválida → sem animação |
| `--color-on-accent` | `dark-redesign.css`, `oficios.css`, `ordens-servico.css`, `planos-trabalho-atividades.css` | Cai no fallback `#081522` (funciona, mas é hardcode) |
| `--color-surface-raised` | `prestacoes_contas.css` | Fallback `#101828` — fora da paleta |
| `--cv-form-field-bg` | `prestacoes_contas.css` | Idem |
| `--surface-card` | `oficios.css` | Fundo indefinido |
| `--surface-panel` | `dev/*` | Só UI Lab |
| `--theme-text` | `page-shell.css` | Cor indefinida |
| `--border-filter-chip` / `--surface-filter-chip` | `page-shell.css` | Chips de filtro sem superfície própria |
| `--cv-chip-shadow-hover` | `utilities.css` | Sem sombra no hover do chip |

### 3.4 CSS morto em produção

Confirmado por varredura de `class="..."` em todos os templates fora de `dev/` e `ui_lab2/`:

| Arquivo | Linhas | Status |
|---|---|---|
| `app-page.css` | **625** | ❌ 0 usos de `.app-page__*` / `.app-page-hero*` em produção — **importado globalmente** |
| `buttons.css` | **140** | ❌ 0 usos de `.btn-primary/.btn-secondary/.btn-danger/.app-btn` |
| `buttons-functional.css` | **496** | ❌ 0 usos de `.btn--document-*`, `.btn--danger-strong`, `.btn--remove-chip` |
| `forms.css` (blocos `.app-form-shell`/`.form-shell`) | ~400 de 1.486 | ❌ 0 usos |
| `auth.css` | 282 | ⚠️ usado só no login, mas **importado globalmente** por `style.css:3` |
| `components/filter-header.css` | 18 | ⚠️ "compat residual" — 3 regras |
| `components/lists/main_list_card.html` | — | ❌ **template morto** (só citado em texto do UI Lab) |
| `roteiros/partials/roteiro_list_card.html` | — | ❌ morto em produção (só UI Lab + 1 teste) |
| `roteiros-list.css` → `.app-page-hero--roteiros-list` | ~25 | ❌ morto, mas o arquivo é carregado por 5 listas |

**Total de CSS provavelmente morto: ~1.900 linhas**, das quais ~1.260 são carregadas em **todas** as páginas.

### 3.5 Acoplamento cruzado entre módulos

| Página | CSS de outros módulos que carrega |
|---|---|
| `oficios/index.html` | `roteiros-list.css`, `oficios-documentos-inline.css` |
| `eventos/index.html` | `roteiros-list.css` |
| `eventos/detalhe.html` | `roteiros-list.css`, `roteiros.css`, `termos.css`, `planos-trabalho-eventos.css`, `prestacoes_contas.css` |
| `ordens_servico/index.html` | `roteiros-list.css` |
| `ordens_servico/form.html` | `roteiros.css`, `termos.css` |
| `planos_trabalho/index.html` | `roteiros-list.css` |
| `planos_trabalho/wizard_*.html` | `roteiros.css`, `termos.css`, `oficios-documentos-inline.css` |
| `termos/form.html` | `roteiros.css`, `oficios-documentos-inline.css`, `prestacoes_contas.css` |
| `termos/index.html` | `prestacoes_contas.css` |
| `prestacoes_contas/index.html` | `roteiros-list.css`, `oficios-list-header.css` |
| `prestacoes_contas/*_form.html` | `roteiros.css`, `oficios-documentos-inline.css` |
| **Global (`style.css`)** | `oficios.css` (4.495 linhas) e `auth.css` em **todas** as páginas |

Nenhum módulo tem CSS próprio de verdade. O acoplamento é total.

### 3.6 Uma classe, muitos donos

Classes estilizadas em 3+ arquivos diferentes: **146**. Top:

| Classe | Arquivos | Regras | Onde |
|---|---|---|---|
| `.cv-btn` | **16** | 54 | action-system, content-cards, cv-buttons, cv-date-picker, dark-redesign, dialog, document-viewer, form-sections, oficios, page-shell, planos-trabalho-atividades, planos-trabalho-eventos, roteiros-list, roteiros, utilities, workspace-admin |
| `.cv-field__control` | 11 | **96** | cv-select, dark-redesign, forms, justificativas, list-header, oficios, ordens-servico, page-shell, planos-trabalho-eventos, prestacoes_contas, roteiros |
| `.form-control` | 11 | 83 | app-page, dark-redesign, form-sections, forms, justificativas, list-header, oficios, ordens-servico, prestacoes_contas, roteiros, workspace-admin |
| `.cv-custom-select__trigger` | 10 | 47 | cv-select, dark-redesign, forms, justificativas, list-header, ordens-servico, planos-trabalho-atividades, planos-trabalho-eventos, prestacoes_contas, roteiros |
| `.cv-search-picker__control` | 7 | 39 | cv-search-picker, dark-redesign, forms, list-header, ordens-servico, planos-trabalho-eventos, roteiros |
| `.is-active` | 12 | 34 | — (estado sem dono) |
| `.cv-search-picker__selected-card` | 5 | 47 | cv-search-picker, dark-redesign, oficios, ordens-servico, termos |

**É por isso que mexer em um campo quebra três telas.** Um input tem 96 regras espalhadas por 11 arquivos, resolvidas por ordem de carregamento e `!important`.

### 3.7 Estrutura invertida: componentes globais sem aparência

Vários arquivos em `components/` são **puramente estruturais** e toda a pintura vive em `dark-redesign.css`:

| Arquivo | Regras de cor próprias | Consequência |
|---|---|---|
| `components/dialog.css` | **0** | `.cv-dialog__panel` **não tem `background`, `border` nem `box-shadow` em lugar nenhum além do bloco dark**. Todo diálogo global é transparente no tema claro. |
| `components/content-cards.css` | **0** | `.cv-summary-tile` e `.cv-document-card` **não têm fundo em tema nenhum** |
| `components/form-panel.css` | 0 | Painel sem superfície própria |
| `components/filter-header.css` | 0 | — |

Isso confirma a decisão do usuário: **o dark é o único tema completo**. Ele deve virar a base, não a exceção.

---

## 4. Catálogo de defeitos — tema escuro

Numerados para rastreio. Severidade: 🔴 crítico (quebra a leitura) · 🟠 alto (fere o padrão) · 🟡 médio (ruído/dívida).

### 4.1 Componentes globais quebrados no dark

| # | Sev | Defeito | Local |
|---|---|---|---|
| D-01 | 🔴 | **Toast "Gerando documento…" sem fundo e sem sombra** — usa `--theme-card-bg` e `--theme-shadow-card`, ambos indefinidos. Aparece em toda a aplicação (está em `base.html:55`). | `components/document-download-loading.css:22,24` |
| D-02 | 🔴 | **`.cv-dialog--danger/--warning/--success/--document` não existem no CSS.** Excluir, cancelar, confirmar e anexar-assinado têm exatamente a mesma aparência — nenhum sinal semântico. | `page-shell.css` / `dark-redesign.css` (ausentes); usados em `modals/*.html` |
| D-03 | 🔴 | **`.summary-items` sem nenhum estilo.** O bloco "Viagens próximas" do Dashboard é um `<ul>` cru. O arquivo `components/summary-items.css` define `cv-summary-*`, nome que ninguém usa ali. | `core/dashboard.html:47` |
| D-04 | 🔴 | **`variant="muted"` de botão não existe.** Os botões PDF/DOCX de `document_card.html` caem em `.cv-btn` sem variante. | `components/cards/document_card.html:47-48` |
| D-05 | 🟠 | `.cv-summary-tile` e `.cv-document-card` sem `background`/`border` em qualquer arquivo — dependem de herança do contêiner. | `components/content-cards.css` |
| D-06 | 🟠 | `.cv-data-table-shell:focus-visible` usa `var(--color-focus-ring)` indefinido → **sem anel de foco**. | `utilities.css:470` |
| D-07 | 🟠 | `--focus-ring` só existe como `none` (em `dark-redesign.css:102` e `roteiros.css:3095`). O `file-picker` usa `var(--cv-field-focus-ring, var(--focus-ring))` → **sem foco visível em nenhum tema**. | `components/file-picker.css:52,68,206` |
| D-08 | 🟠 | `.alert__title` e `.alert__message` (emitidos por `ui/feedback/alert.html`) não têm CSS. | `components/ui/feedback/alert.html:4-5` |
| D-09 | 🟠 | `.empty-state__actions` sem CSS — o botão do estado vazio não tem espaçamento próprio. | `components/ui/feedback/empty_state.html:6` |
| D-10 | 🟡 | `alert.html` emite `alert-{{v}}` **e** `alert--{{v}}` para o mesmo elemento; `.alert--*` só é estilizado no dark. | `components/ui/feedback/alert.html:2` |
| D-11 | 🟡 | `.cv-dialog` usa `z-index: var(--z-modal, 1000)` mas `--z-modal` vale `100`. Fallback contradiz o token. | `components/dialog.css:10` |
| D-12 | 🟡 | `.cv-chip__label` sem CSS (a tipografia mora só no `.cv-chip`). | `components/ui/badges/chip.html` |

### 4.2 Ilhas visuais que ignoram o tema escuro

| # | Sev | Defeito | Local |
|---|---|---|---|
| D-20 | 🔴 | **`.pte-card` (cards de evento do Plano de Trabalho) não tem nenhuma regra de tema escuro** e usa paleta Tailwind por fallback: `#0f172a`, `#64748b`, `#2563eb`, `#f8fafc`, `#e2e8f0`. Com `--color-text-strong` indefinido, **título e valores ficam quase pretos sobre card escuro**. | `planos-trabalho-eventos.css:38-180` |
| D-21 | 🔴 | `.pte-card__value--valor` usa `--color-primary-strong` = `#0b3a66` no dark — azul-marinho sobre superfície escura, contraste ≈ 1.5:1. | `planos-trabalho-eventos.css:147` |
| D-22 | 🔴 | **`.app-card-toggle` é deliberadamente claro em todos os temas** (`#fff7f7`, `#fee2e2`, `#f7c8c8`, `#f0fdf4`, `#dcfce7`, `#bbf7d0`). Um cartão pastel branco no meio do tema escuro. A "correção" força `#071a33`/`#52657a` no texto — hardcode sobre hardcode. O comentário no código admite o problema. | `forms.css:517-660` |
| D-23 | 🟠 | `.oficio-lc__action-menu-heading-icon` / `__item-icon` usam `rgba(69,105,143,.1)` + `color:#426b91` **sem override dark** — ícone azul-escuro sobre menu escuro. Idem `--wa`, `--business`, `--pdf`, `--route`, `--package`, `--copy`. | `oficios-list-header.css:128-200` |
| D-24 | 🟠 | Login (`auth.css`) é uma ilha de 282 linhas com paleta própria `--auth-*`, **zero `data-theme`**, e mesmo assim é importado globalmente. | `auth.css`, `style.css:3` |
| D-25 | 🟠 | Páginas públicas de assinatura (`prestacoes-assinatura.css`, prefixo `asgn-`) — segunda ilha, 354 linhas, zero token do sistema, zero `data-theme`. | `prestacoes_contas/assinatura/base_publico.html` |
| D-26 | 🟠 | `diario-troca.css` usa fallbacks de tema claro em 13 regras (`#52657a`, `#e3eaf2`, `#9fb2c8`) e um `--color-primary, #2f8bd8` que **não é** o primary do sistema (`#12507f` no dark). | `diario-troca.css:1-182` |
| D-27 | 🟡 | `oficios-documentos-inline.css` repete fallbacks claros (`#fff`, `#071a33`, `#e3eaf2`, `#52657a`) em ~20 regras. Se o token existir funciona; a intenção declarada é clara. | `oficios-documentos-inline.css:477-1000` |

### 4.3 Ruptura de escala e ritmo

| # | Sev | Defeito | Local |
|---|---|---|---|
| D-30 | 🟠 | **Alturas de controle divergentes:** `tokens.css` diz `--cv-btn-height: 36px`; `cv-buttons.css` redefine para `var(--control-height-md)` = **44px**. O token em `tokens.css` é letra morta e engana. Mesma duplicação em `--cv-btn-padding-x`, `--cv-btn-gap`, `--cv-btn-icon-size`, `--cv-btn-radius`, `--cv-btn-shadow`. | `tokens.css:140-144` vs `cv-buttons.css:14-22` |
| D-31 | 🟠 | **z-index fora da escala:** o sistema define `--z-sidebar:20`, `--z-dropdown:50`, `--z-modal:100`, `--z-toast:120`, `--z-sticky-stepper:1100`. Na prática há literais `10050`, `500`, `200`, `100`, `50`, `45`, `40`, `25`. | vários |
| D-32 | 🟠 | **Raio inconsistente no mesmo nível hierárquico:** `.oficio-lc__action-menu` usa `border-radius: 16px` literal; `.oficio-lc__action-menu-item` usa `11px`; o sistema tem `--radius-sm:8 / md:14 / card:16 / panel:18 / lg:20`. Nenhum literal corresponde a token. | `oficios-list-header.css:88,151` |
| D-33 | 🟡 | Tipografia em unidades misturadas: `rem` (`0.86rem`, `0.72rem`, `0.68rem`, `1.05rem`), `px` (`11px`, `13px`, `15px`) e `clamp()` convivem sem escala. Os tokens `--font-size-2xs..2xl` existem e são pouco usados. | `cv-buttons.css`, `oficios-list-header.css`, `planos-trabalho-eventos.css`, `forms.css` |
| D-34 | 🟡 | Duas escalas de transição: `--transition-fast/base/slow` (tokens) e `--duration-fast/normal/slow` + `--ease-standard` (page-shell). `dark-redesign` sobrescreve `--transition-*` com `cubic-bezier` diferente. | `tokens.css:167`, `page-shell.css:163`, `dark-redesign.css:103` |

### 4.4 Semântica e acessibilidade

| # | Sev | Defeito | Local |
|---|---|---|---|
| D-40 | 🟠 | **Níveis de heading arbitrários:** a mesma classe `.cv-form-section-title` aparece como `<h1>` (1×), `<h2>` (13×) e `<h3>` (21×). Dentro do módulo Prestações: `documentos_form` usa h3, `consolidado` usa h2. | vários |
| D-41 | 🟠 | `field.html` gera contratos diferentes por tipo de widget: `select` recebe `field app-form-field cv-field` + label `app-form-label cv-field__label`; input de texto recebe `field app-form-field` + label `app-form-label`. Estilizar "todo campo" é impossível. | `components/ui/forms/field.html:4,24,57` |
| D-42 | 🟠 | Três nomes para erro de campo: `.field-error`, `.app-form-error` (emitidos juntos) e `.form-error` (usado em `file_picker.html` e quick-adds, **sem CSS**). | `ui/feedback/field_error.html:1`, `ui/forms/file_picker.html` |
| D-43 | 🟡 | Classes utilitárias Bootstrap residuais sem CSS: `.py-2`, `.mb-2`, `.text-muted`, `.text-danger`, `.text-warning-emphasis`, `.small`. | `_roteiro_editor.html:40`, `roteiros/partials/roteiro/_diarias_body.html`, `_retorno_body.html` |
| D-44 | 🟡 | `action-system.css:79` e `:529` usam apenas `html[data-theme="dark"]`, sem o trio; `cv-select.css`, `cv-buttons.css`, `oficios-list-header.css`, `page-shell.css` idem. Coexistem dois padrões de escrita de seletor de tema. | vários |

### 4.5 Duplicação de sistemas

| # | Sev | Sistema duplicado | Instâncias |
|---|---|---|---|
| D-50 | 🟠 | **Botões** | `.cv-btn` (vivo) · `.btn`/`.btn-primary`/`.btn-*` (morto) · `.app-btn`/`.app-btn--*` (morto) · `.btn--document-*` (morto) · `.cv-icon-btn` (vivo) |
| D-51 | 🟠 | **Alertas/banners** | `.alert`/`.alert-*` (utilities) · `.cv-alert`/`.cv-alert--*` (page-shell) · `.diario-diaria-alert` (RT) · `.pte-events__banner` (PT) |
| D-52 | 🟠 | **Cards de lista** | `.cv-entity-card` + `.oficio-lc__*` (vivo, 6 módulos) · `.roteiro-list-card__*` (599 linhas, morto em produção) · `.evento-lc__*` (2 regras) · `.cv-document-card` (sem cor) |
| D-53 | 🟠 | **Cabeçalho de lista** | `filter_page_header.html` (canônico) · markup inline duplicado em `list_page_quick_add.html:3-11` |
| D-54 | 🟠 | **Confirmação de exclusão** | modal JS `delete_confirm_modal.html` (listas de cards) · página inteira `confirm_delete.html` (12 páginas de catálogo) — e a página usa `.cv-confirm-page*`, **sem CSS**, caindo em `.form-section`/`.section-header` legados |
| D-55 | 🟡 | **Resumo/estatística** | `cv-summary-item/-label/-value` (summary-items.css) · `cv-summary-tile` (content-cards.css) · `pt-resumo-box` (dentro de content-cards.css!) · `admin-overview__stats` com `<dl>` (usuarios) |
| D-56 | 🟡 | **Grid de campos** | `.field-grid` + `.field-size-1..4` (padrão) · `.field-grid--cols-2/3/4` (segundo padrão) · `.field-grid-rows` (terceiro) |
| NOVO-19 | 🟡 | **Sede do roteiro ofício espelhava Destinos** — card interno (`.oficio-roteiro-sede-row`) + badge dourado `SEDE` + título empilhado: três camadas de chrome para um par UF/cidade. **Corrigido:** `cv-form-subsection--split` (copy à esquerda, campos à direita), sem badge/card. | `_fonte_body.html` · `form-sections.css` |

---

## 5. Auditoria página a página

Legenda: **✅ conforme** · **⚠️ desvio** · **❌ fora do padrão**

### 5.1 Documentos — Ofícios (referência)

| Página | Template | Situação |
|---|---|---|
| Lista de Ofícios | `oficios/index.html` | ✅ **Referência de lista.** ⚠️ carrega `roteiros-list.css` (599 linhas, das quais só ~10 usadas) e `oficios-documentos-inline.css`. ⚠️ não carrega `oficios-list-header.css`, que só é carregado por Prestações — logo o menu de ações do card de ofício herda estilo de outro módulo por acaso. |
| Etapa 1 — Dados/Viajantes | `wizard_dados_viajantes.html` | ✅ **Referência.** ⚠️ `<h2>` no card mestre (Termos/OS usam `<h3>`). ⚠️ classes `travel-document-*` nomeadas por página. |
| Etapa 2 — Transporte | `wizard_transporte.html` | ✅ **Referência.** ⚠️ `<h3>` — diverge da etapa 1 da própria página. ⚠️ `section-cards=1, form_blocks=0` — monta campos direto no body, sem `form_block`. |
| Etapa 3 — Roteiro | `wizard_roteiro.html` | ⚠️ delega a `_roteiro_editor.html`. Recebe o card canônico **só** porque `roteiro_editor_oficio` é verdadeiro. Carrega Leaflet de **CDN externa** (`unpkg.com`) — risco de FOUC/offline e de política de CSP. Carrega `domain.css` + `roteiros.css` (3.215 linhas). |
| Etapa 4 — Justificativa | `wizard_justificativa.html` | ✅ conforme. ⚠️ `<h3>`. |
| Etapa 5 — Documentos | `wizard_documentos.html` | ⚠️ `<h2>`. ⚠️ carrega `roteiros.css` + `oficios-documentos-inline.css` + `prestacoes_contas.css`. Usa 5 aliases de classe por bloco (`oficio-documentos-block oficio-documentos-preview-section document-inline-stack …`). |
| Modelos de motivo | `oficios/modelos_motivo/index.html` | ⚠️ família Quick Add — cabeçalho duplicado (D-53). |
| Excluir modelo | `oficios/modelos_motivo/confirm_delete.html` | ❌ página de confirmação com `.cv-confirm-page*` sem CSS (D-54). |

### 5.2 Documentos — Termos (referência)

| Página | Template | Situação |
|---|---|---|
| Lista de Termos | `termos/index.html` | ❌ **usa `list_page_standard` (linhas), não `list_page_cards`.** Diverge do padrão aprovado de Ofícios/Eventos. Carrega `prestacoes_contas.css` sem motivo aparente. |
| Cadastro de Termo | `termos/form.html` | ✅ **Referência.** ⚠️ `page-shell--standard` (Ofícios usa `--wizard`). ⚠️ 4 CSS de outros módulos. ⚠️ `travel-document-wizard`/`app-wizard` sem ser wizard. |
| Preview de termo do ofício | `termos/preview.html` | ⚠️ `page-shell--standard-simple` — quarto modificador de shell para a mesma família. |
| Preview de termo avulso | `termos/preview_cadastro.html` | ⚠️ idem; classes `termo-*` (`termo-cabecalho`, `termo-secao`, `termo-tabela`, `termo-titulo`, `termo-texto`, `termo-assinaturas`) **sem CSS** no bundle da aplicação. |

### 5.3 Documentos — Ordens de Serviço (referência)

| Página | Template | Situação |
|---|---|---|
| Lista de OS | `ordens_servico/index.html` | ✅ `list_page_cards`. ⚠️ carrega `roteiros-list.css`. |
| Cadastro de OS | `ordens_servico/form.html` | ✅ **Referência.** ⚠️ `page-shell--standard`. ⚠️ shell com 6 classes: `page-shell page-shell--standard travel-document-wizard app-wizard document-form-page os-page`. ⚠️ blocos com 3 aliases: `travel-document-block document-form-block os-block`. ⚠️ `os-block`, `os-form-body`, `os-submit-btn`, `os-lc` **sem CSS**. ⚠️ 23 `!important` em `ordens-servico.css`. |

### 5.4 Eventos

| Página | Template | Situação |
|---|---|---|
| Lista de Eventos | `eventos/index.html` | ✅ **Referência de lista.** ⚠️ `eventos-list.css` tem 11 regras, 8 delas re-escopando `.oficio-lc__*` dentro de `.evento-lc` — patch sobre patch. |
| Painel do Evento (guiado) | `eventos/detalhe.html` | ❌ **maior acúmulo do sistema:** carrega **5 CSS de outros módulos** (`roteiros-list`, `roteiros`, `termos`, `planos-trabalho-eventos`, `prestacoes_contas`). Usa `.cv-alert--danger --action` (sistema de alerta nº 2). `.evento-step1-card` e `.evento-doc-picker` sem CSS. Renderiza `.pte-card` (D-20/D-21) e `.roteiro-*`. |
| Cadastro de Evento | `eventos/form.html` | ❌ **não usa `form_block`** (0 blocos). ❌ **footer escrito à mão** em vez de `card_footer_section.html`. ❌ card sem `--described` e sem subtítulo. `<h2>`. |
| Tipos de Evento | `eventos/tipos/index.html` | ⚠️ família Quick Add. |
| Excluir tipo | `eventos/tipos/confirm_delete.html` | ❌ D-54. |

### 5.5 Roteiros

| Página | Template | Situação |
|---|---|---|
| Lista de Roteiros | `roteiros/index.html` | ❌ **usa `list_page_standard` (linhas)**, enquanto o padrão aprovado é card. Existe um `roteiro_list_card.html` + 599 linhas de `.roteiro-list-card__*` construídos e **nunca usados em produção**. |
| Roteiro avulso | `roteiros/roteiro_form_page.html` | ❌ **o editor não recebe o card canônico quando é avulso.** O mesmo `_roteiro_editor.html` só monta `cv-form-section-card` + footer se `roteiro_editor_oficio` for verdadeiro (`_roteiro_editor.html:47-70`). Resultado: a página avulsa é visualmente órfã. Leaflet de CDN externa. `roteiros.css` = 3.215 linhas, 22 `!important`, 237 linhas de seletor de tema morto. |
| Excluir roteiro | `roteiros/confirm_delete.html` | ❌ D-54. |

**Componentes internos do roteiro** (`roteiro-editor__*`, `roteiro-trecho-card`, `roteiro-mapa__*`, `route-segment-card`, `roteiro-sequencia__order`): sistema paralelo completo de seções, cards e campos, com tokens próprios `--route-*` (49 tokens em `theme.css`). `.roteiro-mapa__error`, `.roteiro-mapa__stale-hint`, `.roteiro-wizard__form`, `.roteiro-trechos-date-picker-park` **sem CSS**.

### 5.6 Planos de Trabalho

| Página | Template | Situação |
|---|---|---|
| Lista de Planos | `planos_trabalho/index.html` | ✅ `list_page_cards`. ⚠️ o body do card usa `oficio-lc__transport-card--valor` para renderizar "valor médio" e `oficio-lc__valor-medio` — vocabulário de ofício em conteúdo de plano. |
| Etapa 1 — Identificação | `wizard_identificacao.html` | ⚠️ ✅ estrutura conforme, mas renderiza `.pte-card` (🔴 D-20/D-21) e `.pte-events__banner` (sistema de alerta nº 4). `.cv-card__hint`, `.pt-form-card`, `.pt-add-evento` sem CSS. Carrega `roteiros.css` + `termos.css`. |
| Etapa 2 — Efetivo/Diárias | `wizard_efetivo_diarias.html` | ⚠️ `.pt-efetivo-rows`, `.pt-efetivo-section` sem CSS. Carrega `roteiros.css` + `termos.css`. |
| Etapa 3 — Atividades | `wizard_atividades.html` | ⚠️ `.pt-preset-activities-field`, `.pt-activity` parcialmente sem CSS. `planos-trabalho-atividades.css` usa `--color-accent, #d9a40f` — **fallback diferente do accent real** `#d8a21b`. |
| Etapa 4 — Documentos | `wizard_documentos.html` | ⚠️ carrega `oficios-documentos-inline.css`. Renderiza `.pte-card` de novo. |
| Programas / Horários / Atividades / Presets | `*/index.html` | ⚠️ 4 listas Quick Add. |
| 4 páginas de exclusão | `*/confirm_delete.html` | ❌ D-54 ×4. |

### 5.7 Prestações de Contas

| Página | Template | Situação |
|---|---|---|
| Lista de Prestações | `prestacoes_contas/index.html` | ✅ `list_page_cards`. ⚠️ único consumidor de `oficios-list-header.css` — que estiliza `.oficio-lc__*` usado também por Ofícios e Eventos (D-23). Carrega 3 CSS. |
| Etapa 1 — Relatório Técnico | `relatorio_tecnico_form.html` | ✅ estrutura conforme (`<h3>`). ⚠️ `.diario-diaria-alert` = sistema de alerta nº 3. `.rt-custeios-block` sem CSS. 3 CSS de outros módulos. |
| Etapa 2 — Diário de Bordo | `diario_bordo_form.html` | ⚠️ 4 CSS de outros módulos (`roteiros`, `prestacoes_contas`, `oficios-documentos-inline`, `prestacoes-documento-preview`). |
| Etapa 3 — Troca de motorista | `diario_motorista_form.html` | ❌ **composição diferente das irmãs:** usa `form_block shell="card"` soltos, **sem card mestre e sem `cv-form-card__footer`**. `.dmv-form` sem CSS. `diario-troca.css` com fallbacks claros (D-26). |
| Etapa 4 — Documentos | `documentos_form.html` | ✅ conforme (`<h3>`). ⚠️ blocos com 5 aliases. |
| Etapa 5 — PDF Final | `consolidado.html` | ⚠️ **`<h2>`** — diverge das 4 etapas irmãs que usam `<h3>`. |
| Modelos de texto (lista) | `modelos_texto/index.html` | ❌ **sexta variante de lista:** `page-shell--list` + `filter_page_header` montados à mão, sem `list_page_*`. |
| Modelos de texto (form) | `modelos_texto/form.html` | ⚠️ `page-shell--standard-simple`, sem card mestre. |
| Excluir modelo | `modelos_texto/confirm_delete.html` | ❌ D-54. |
| **Assinatura pública** (5 páginas) | `assinatura/*.html` | ❌ **ilha completa** (D-25): `base_publico.html` não estende `base.html`, tem `<html>` próprio, CSS próprio (`asgn-*`), sem tokens, sem tema, sem componentes globais. `.assinaturas-central-*` (9 classes) sem CSS. |

### 5.8 Cadastros

| Página | Template | Situação |
|---|---|---|
| Hub de Cadastros | `cadastros/index.html` | ❌ `page-shell` **sem modificador**. ❌ usa `dashboard-page__section-heading`, `dashboard-page__eyebrow`, `dashboard-page__module-grid` — **classes do Dashboard em outra página**. `.cadastros-hub` sem CSS. |
| Servidores (lista) | `cadastros/servidores/index.html` | ⚠️ `list_page_standard` (linhas) — coerente para cadastro, mas é a 3ª família de lista. |
| Servidor (form) | `cadastros/servidores/form.html` | ⚠️ `page-shell--standard-simple`; a irmã Viaturas usa `--standard`. Sem subtítulo no card. |
| Viaturas (lista) | `cadastros/viaturas/index.html` | ⚠️ `list_page_standard`. |
| Viatura (form) | `cadastros/viaturas/form.html` | ⚠️ `page-shell--standard` — diverge de Servidores (D-31 de shell). |
| Configurações do sistema | `cadastros/configuracao/form.html` | ⚠️ usa `form_block shell="card"` (sem card mestre) e **dois `<form>` irmãos** com footers independentes — composição única no sistema. |
| Estados / Cidades / Unidades / Cargos / Combustíveis | `*/index.html` | ⚠️ 5 listas Quick Add com cabeçalho duplicado (D-53). |
| Excluir estado / servidor / viatura | `*/confirm_delete.html` | ❌ D-54 ×3. |

### 5.9 Justificativas

| Página | Template | Situação |
|---|---|---|
| Justificativas (lista) | `justificativas/index.html` | ⚠️ Quick Add. `justificativas.css` tem **4 blocos `html[data-theme="dark"]` sem o trio de seletores** e reestiliza `.quick-add-footer-button` global. |
| Modelos (lista) | `justificativas/modelos/index.html` | ⚠️ Quick Add. |
| Excluir modelo | `modelos/confirm_delete.html` | ❌ D-54. |

### 5.10 Núcleo / Conta / Administração

| Página | Template | Situação |
|---|---|---|
| Dashboard | `core/dashboard.html` | ❌ `page-shell` sem modificador. ❌ `.summary-items` sem CSS (D-03). ⚠️ mistura `cv-entity-card` (card de lista) com conteúdo editorial. `dashboard-page__*` = vocabulário local. |
| Login | `core/login.html` | ❌ ilha (D-24): não estende `base.html`, sem tokens do sistema, sem tema. |
| Perfil | `core/perfil.html` | ⚠️ usa `cv-form-section-card` **sem** `cv-form-card` (único no sistema). ❌ **footer escrito à mão ×3** em vez de `card_footer_section.html`. `<h2>`. Carrega `gdrive-config.css` (892 linhas) com vocabulário `gdrive-*` inteiramente próprio. |
| Administração / Usuários | `usuarios/index.html` | ❌ `.admin-overview` + `<dl class="admin-overview__stats">` — **quinto** sistema de estatística (D-55). `workspace-admin.css` com vocabulário `admin-*`. |
| Documentos (placeholder) | `documentos/index.html` | ⚠️ `module_placeholder.html`; `.module-placeholder-card__header` e `__status` sem CSS. |
| Diário de Bordo (placeholder) | `diario_bordo/index.html` | ⚠️ idem. |
| Visualizador de PDF | `documentos/pdf_viewer.html` | ⚠️ `doc-pdf-toolbar`, `doc-pdf-toolbar__btn`, `doc-section`, `doc-title`, `doc-meta`, `doc-muted`, `doc-orgao`, `doc-unidade` — 8 classes sem CSS no bundle. |

### 5.11 Resumo dos desvios por família

| Família | Páginas | Conformes | Desvios |
|---|---|---|---|
| Formulário/wizard canônico | 22 | 14 | 8 |
| Lista em cards (`list_page_cards`) | 5 | 5 | 0 (só acoplamento de CSS) |
| Lista em linhas (`list_page_standard`) | 4 | — | **4** (Roteiros e Termos deveriam ser cards) |
| Lista Quick Add | 13 | — | 13 (cabeçalho duplicado) |
| Página de confirmação de exclusão | 12 | 0 | **12** (sem CSS) |
| Ilhas (login + assinatura pública) | 6 | 0 | **6** |
| Hubs / placeholders / perfil / admin | 7 | 0 | 7 |
| Preview de documento | 3 | 0 | 3 |
| **Total** | **72** *(+4 bases)* | **19** | **53** |

---

## 6. Auditoria componente a componente

### 6.1 Shell e navegação

| Componente | Arquivo | Problemas |
|---|---|---|
| `app-shell` | `components/app-shell.css` (133) | ✅ ok. `--sidebar-width` definido em 3 lugares com valores diferentes (`15%` em tokens, `clamp(238px,17.5vw,276px)` em dark-redesign). |
| `sidebar` | `sidebar.css` (391) | ✅ ok no dark. 30 tokens `--sidebar-*` duplicados em `theme.css` e `dark-redesign.css` com valores divergentes. `.sidebar-link-text`, `.sidebar-item-text`, `.sidebar-link--root` sem CSS. |
| `page-shell` | `page-shell.css` (3.699) | ❌ arquivo-monólito: contém shell, header, stepper, field-grid, quick-add, paginação, modal de exclusão, action-menu, alerta e 237 definições de token. Precisa ser fatiado. |
| `page_header` | `ui/headers/page_header.html` | ✅ **componente canônico**. ⚠️ o CSS vive em `page-shell.css` (`.page-header-band`, `.page-header-rail`) **e** em `dark-redesign.css`. Bloco `.page-header--clean` (linhas 447-500 de page-shell) é morto. |
| `page_stepper` | `ui/navigation/page_stepper.html` | ✅ ok. ⚠️ existe um `.oficio-stepper__*` paralelo em `oficios.css:937-1030` com rgba hardcoded, morto. `.page-stepper--horizontal` sem CSS. |

### 6.2 Cabeçalhos de lista e filtros

| Componente | Arquivo | Problemas |
|---|---|---|
| `filter_page_header` | `ui/headers/filter_page_header.html` | ✅ canônico. ⚠️ dois ramos (`advanced` / simples) que produzem markups diferentes para o mesmo papel. |
| `list-header` (CSS) | `components/list-header.css` (762) | ⚠️ contém também o `filter-pill` do date picker e o Quick Add inteiro — três responsabilidades. Consome `--cv-card-family-bg`, definido só em `dark-redesign.css:126`. |
| `list_tabs` | `components/lists/list_tabs.html` | ✅ ok. `.cv-list-tab__label` sem CSS. |
| `filter-header.css` | `components/filter-header.css` (18) | ❌ "compat residual", 3 regras — absorver e apagar. |
| Quick Add | `list_page_quick_add.html` | ❌ duplica o markup do `filter_page_header` (linhas 3-11) em vez de incluí-lo (D-53). |

### 6.3 Cards de lista

| Componente | Arquivo | Problemas |
|---|---|---|
| `entity_card` | `ui/lists/entity_card.html` | 🔴 **componente global que emite classes `oficio-lc`** (`entity_card.html:5`). Usado por Ofícios, Roteiros, OS, PT, Eventos e Prestações. |
| `entity_card_header/_footer/_menu` | `ui/lists/*` | ⚠️ idem — `.oficio-lc__footer-actions-main`, `__footer-actions-danger`. |
| CSS de `oficio-lc` | 7 arquivos | 🔴 `oficios.css` (169 regras), `dark-redesign.css` (30), `oficios-list-header.css` (49), `eventos-list.css` (8), `roteiros-list.css` (3), `planos-trabalho-eventos.css` (3), `list-header.css` (2). |
| `main_list_card` | `components/lists/main_list_card.html` | ❌ **template morto**. |
| `roteiro_list_card` | `roteiros/partials/` | ❌ **morto em produção** (599 linhas de CSS associado). |
| `simple_list` / `simple_list_row` | `components/lists/` | ⚠️ terceira gramática de linha (`.cv-record-row` em `record-list.css` é a quarta). |
| `cv-document-card` | `cards/document_card.html` | ❌ sem `background`/`border` (D-05); botões com `variant="muted"` inexistente (D-04). |
| `module_card` | `cards/module_card.html` | ✅ ok (`cards.css`). `.module-placeholder-card` com gradiente hardcoded. |
| `summary_card` | `cards/summary_card.html` | ❌ emite `cv-summary-tile summary-card`; `summary-card` sem CSS, `cv-summary-tile` sem cor. |

### 6.4 Formulário

| Componente | Arquivo | Problemas |
|---|---|---|
| `form_block` | `ui/forms/form_block.html` | ✅ **componente canônico**, bem documentado. ⚠️ shell `card` usa `<h3>` fixo, shell `block` usa `heading_level` — inconsistente. |
| `form-sections.css` | `components/` (222) | ✅ estrutura limpa. ⚠️ contém `.cv-travel-schedule*` — vocabulário de domínio dentro de arquivo global. |
| `field` | `ui/forms/field.html` | 🔴 três contratos de classe diferentes por tipo de widget (D-41). |
| `field-grid` | `page-shell.css:1302+` | ⚠️ dois sistemas: `field-size-N` e `--cols-N` (D-56). |
| `card_toggle` | `ui/forms/card_toggle.html` | 🔴 pastel claro em tema escuro (D-22). |
| `select` / `multiselect` | `ui/forms/` + `cv-select.css` (953) | ⚠️ `.cv-custom-select__trigger` estilizado em 10 arquivos (47 regras). |
| `cv-search-picker` | `cv-search-picker.css` (954) | ⚠️ `.cv-search-picker__control` em 7 arquivos; `__selected-card` em 5 com 47 regras. |
| `date_picker` | `components/cv-date-picker.css` (651) | ⚠️ 8 `!important`; 52 linhas de seletor de tema morto; `--filter-pill` vive em `list-header.css`. |
| `file_picker` | `components/file-picker.css` (347) | ⚠️ sem anel de foco (D-07); `.cv-file-field` sem CSS; nome `prestacao-file-widget__*` (módulo) dentro de componente global. |
| `card_footer_section` | `ui/layouts/` | ✅ canônico — mas **ignorado** por `eventos/form.html` e `core/perfil.html` (footer à mão). |

### 6.5 Ações

| Componente | Arquivo | Problemas |
|---|---|---|
| `button.html` | `ui/buttons/button.html` | ✅ canônico. ⚠️ 27 variantes `.cv-btn--*` definidas, ~8 realmente usadas. `variant="muted"` usado e inexistente (D-04). |
| `cv-buttons.css` | 1.207 linhas | ⚠️ redefine 6 tokens já em `tokens.css` (D-30); 31 regras com cor hardcoded. |
| `icon_button` | `ui/buttons/icon_button.html` | ✅ ok. ⚠️ 20+ variantes `.cv-icon-btn--*` com gradientes hardcoded. |
| `action-system.css` | `components/` (1.018) | ⚠️ 110 tokens locais; blocos dark sem o trio de seletores; 108 cores hardcoded. |
| `floating_action` | `ui/buttons/floating_action.html` | ⚠️ `.cv-floating-action--back` sem CSS (só `--stacked` existe). |
| `action_menu` | `components/action-menu.js` + 3 CSS | ⚠️ `.cv-action-menu` estilizado em `page-shell.css`, `action-system.css` e `oficios-list-header.css`. Menus reanexados ao `<body>` obrigam escopo por classe. |
| Botões legados | `buttons.css`, `buttons-functional.css`, `.app-btn` | ❌ **636 linhas mortas** carregadas globalmente. |

### 6.6 Feedback e overlays

| Componente | Arquivo | Problemas |
|---|---|---|
| `dialog` | `components/dialog.css` (107) | 🔴 zero cor própria; 4 modificadores de tom sem CSS (D-02); fallback de z-index errado (D-11). |
| `delete_confirm_modal` / `cancel_reason_modal` / `confirm_action_modal` / `attach_signed_modal` | `ui/modals/` | ⚠️ 4 modais visualmente idênticos. `.delete-confirm-modal__body`, `.attach-signed-modal__cancel` sem CSS. |
| `confirm_delete` (página) | `ui/modals/confirm_delete.html` | 🔴 `.cv-confirm-page*` sem CSS; usa `.form-section`/`.section-header` legados (D-54). |
| `alert` | `ui/feedback/alert.html` | ⚠️ dupla classe; `__title`/`__message` sem CSS (D-08, D-10). |
| `alerts` (mensagens Django) | `feedback/alerts.html` | ⚠️ emite `alert-{{tags}}`; `debug` não tem estilo. |
| `empty_state` | `ui/feedback/empty_state.html` | ⚠️ `.empty-state__actions` sem CSS; `lists.css:96` usa `html[data-theme="dark"]` sem trio. |
| `pendencias_card` | `components/pendencias.css` (99) | ✅ ok. |
| `field_error` | `ui/feedback/field_error.html` | ⚠️ três nomes para o mesmo erro (D-42). |
| `document-download-loading` | `components/` (90) | 🔴 sem fundo nem sombra (D-01). |
| `document-viewer` | `components/document-viewer.css` (169) | ⚠️ `.cv-document-viewer__body` sem CSS. |

### 6.7 Componentes de domínio que já são globais de fato

Estes já são usados por 3+ módulos e devem virar componentes globais nomeados por função:

| Vocabulário atual | Módulos que usam | Função real |
|---|---|---|
| `oficio-lc__traveller*` | Ofícios, OS, PT, Eventos, Prestações | **Linha de pessoa com avatar, nome, meta e ações** |
| `oficio-lc__transport-card` | Ofícios, Roteiros, PT, Eventos, Prestações | **Bloco de fato rotulado (label + valor)** |
| `oficio-lc__trecho*` | Ofícios, Roteiros, PT, Eventos | **Item de itinerário (rota + horários)** |
| `oficio-lc__section` | todos | **Faixa interna de card** |
| `oficio-documentos-*` | Ofícios, Termos, PT, Prestações | **Grade de documentos com preview e ações** |
| `document-inline-*` | Ofícios, Termos, Prestações | **Cartão de documento com viewer embutido** |
| `travel-document-*` | Ofícios, Termos, OS, PT, Prestações, Eventos | **Página de documento (shell + card + bloco)** |
| `termo-block__body` | Termos, OS, PT | **Corpo de bloco com espaçamento denso** |
| `route-section-block` | Roteiros, Prestações | **Seção de trecho** |
| `cv-summary-*` / `pt-resumo-box` | Roteiros, Ofícios, PT, Prestações | **Ladrilho de métrica** |
| `prestacao-file-widget__*` | Prestações, componentes globais de arquivo | **Item de arquivo anexado** |

---

## 7. Dicionário de renomeação

Princípio: **o nome descreve o que o componente faz, nunca onde ele nasceu.** Prefixo único `cv-` para tudo que é global; sem prefixo de módulo em componentes globais; nomes em inglês, coerentes com o vocabulário já existente (`cv-form-*`, `cv-btn`, `cv-field`).

### 7.1 Shell e página

| Hoje | Proposto | Observação |
|---|---|---|
| `page-shell` | `cv-page` | — |
| `page-shell--wizard` / `--standard` / `--standard-simple` | `cv-page--flow` / `cv-page--form` / `cv-page--narrow` | Reduzir de 4 modificadores para 3 com semântica clara |
| `page-shell--list` / `--cards` | `cv-page--collection` / `cv-page--collection-cards` | — |
| `travel-document-wizard`, `app-wizard`, `document-form-page`, `os-page`, `evento-guided-page`, `pt-form-card` | **excluir** — absorvidos por `cv-page--flow` | 6 aliases → 0 |
| `main-form-panel` | `cv-page__panel` | — |
| `page-header-stack` / `-band` / `-rail` | `cv-page-header` / `__banner` / `__rail` | — |
| `page-stepper`, `oficio-stepper` | `cv-stepper` | Apagar `oficio-stepper` (morto) |
| `dashboard-page__section-heading` / `__eyebrow` / `__module-grid` | `cv-section-heading` / `cv-eyebrow` / `cv-module-grid` | Usados fora do Dashboard hoje |
| `cadastros-hub`, `eventos-list-page` | **excluir** | Sem CSS |

### 7.2 Coleções e cards de lista

| Hoje | Proposto |
|---|---|
| `list-header` | `cv-collection-header` |
| `list-header__band` / `__rail` / `__filters` / `__search` / `__select` | `cv-collection-header__banner` / `__toolbar` / `__filters` / `__search` / `__select` |
| `cv-filter-header`, `cv-filter-bar__*`, `header-filter-input`, `header-filter-select` | **excluir** — absorvidos |
| `list-panel` | `cv-collection` |
| `cv-card-grid` | `cv-collection__grid` |
| `cv-list-tabs` | `cv-collection-tabs` |
| `pagination-shell` | `cv-pagination` |
| `quick-add-panel` / `quick-add-inline__*` / `quick-add-footer-button` | `cv-inline-create__panel` / `__body` / `__toggle` |
| `cv-entity-card` + `oficio-lc` | **`cv-record-card`** (fim do `oficio-lc`) |
| `oficio-lc__layout` | `cv-record-card__layout` |
| `oficio-lc__section` | `cv-record-card__band` |
| `oficio-lc__travellers` | `cv-person-list` |
| `oficio-lc__traveller` | `cv-person-row` |
| `oficio-lc__traveller-avatar` / `-name` / `-meta` / `-badge` / `-actions` | `cv-person-row__avatar` / `__name` / `__meta` / `__badge` / `__actions` |
| `oficio-lc__traveller--motorista` | `cv-person-row--highlight` |
| `oficio-lc__traveller--justificativa` | (usar `cv-fact-row`, ver abaixo) |
| `oficio-lc__transport-row` | `cv-fact-grid` |
| `oficio-lc__transport-card` | `cv-fact-block` |
| `oficio-lc__transport-label` | `cv-fact-block__label` |
| `oficio-lc__transport-placa` / `-modelo` / `-driver` / `-hint` | `cv-fact-block__value` / `__value--secondary` / `__value` / `__hint` |
| `oficio-lc__valor-total` / `-extenso` / `-medio` | `cv-fact-block__value--strong` / `--long` / `--average` |
| `oficio-lc__trechos-list` | `cv-itinerary` |
| `oficio-lc__trecho` | `cv-itinerary__leg` |
| `oficio-lc__trecho-rota` / `-times` | `cv-itinerary__route` / `__time` |
| `oficio-lc__empty-hint`, `oficio-lc__text--empty` | `cv-empty-hint` |
| `oficio-lc__action-menu*` | `cv-action-menu*` (unificar com o global existente) |
| `oficio-lc__document-menu-trigger` | `cv-icon-btn--documents` |
| `oficio-lc__wa-trigger` / `__wa-menu` | `cv-icon-btn--whatsapp` / `cv-action-menu--whatsapp` |
| `oficio-lc__footer-actions-*` | `cv-record-card__footer-actions--*` |
| `oficio-lc__solicitacao-form/-input`, `__saque-range-picker` | `cv-record-card__inline-form` / `__inline-input` / `__inline-range` |
| `evento-lc__items-grid` / `__documentos-card` | `cv-fact-grid--dense` / `cv-fact-block--documents` |
| `roteiro-list-card__*` | **excluir** (morto) — o que sobreviver vira `cv-record-card` |
| `os-lc`, `main_list_card` | **excluir** |
| `simple-list-item`, `cv-record-row` | `cv-record-row` (um só) |

### 7.3 Formulário

| Hoje | Proposto |
|---|---|
| `cv-form-section-card` + `cv-form-card` | `cv-form-card` (uma classe só) |
| `cv-form-section-card--described` | **excluir** — subtítulo é opcional, não variante |
| `cv-form-section-header/-title/-subtitle/-body` | `cv-form-card__header` / `__title` / `__subtitle` / `__body` |
| `cv-form-card__footer` | `cv-form-card__footer` ✅ |
| `cv-form-section-stack` | `cv-form-stack` |
| `cv-form-block` | `cv-form-block` ✅ |
| `travel-document-block`, `document-form-block`, `os-block`, `termo-block__body`, `rt-topic-block`, `rt-custeios-block`, `docs-attach-block`, `pt-*-block` | **excluir** — todos viram `cv-form-block` + variante |
| `travel-document-body`, `os-form-body`, `rt-wizard-body`, `docs-wizard-body`, `consolidado-wizard-body`, `oficio-roteiro-body` | **excluir** — `cv-form-card__body` |
| `travel-document-card`, `os-form-card`, `rt-wizard-card`, `docs-wizard-card`, `consolidado-wizard-card`, `evento-step1-card` | **excluir** — `cv-form-card` |
| `field` + `app-form-field` + `cv-field` | `cv-field` (uma classe, todos os widgets) |
| `app-form-label` + `cv-field__label` | `cv-field__label` |
| `field-help` + `app-form-help` | `cv-field__help` |
| `field-error` + `app-form-error` + `form-error` | `cv-field__error` |
| `field-grid` + `field-size-N` | `cv-field-grid` + `cv-field-grid__item--span-N` |
| `field-grid--cols-N`, `field-grid-rows` | **excluir** — usar spans |
| `app-card-toggle` | `cv-switch-card` |
| `cv-composite-field__*` | `cv-field--composite` |
| `cv-ordered-field-row` | `cv-field-row` |
| `cv-travel-schedule*` | `cv-period-fields` (é layout, não domínio) |
| `cv-resource-picker*` | `cv-picker*` |
| `travel-document-identification-grid`, `travel-document-resource-card` | `cv-field-grid`, `cv-picker__card` |
| `oficio-equipe-picker`, `oficio-viajante-card`, `oficio-viatura-*`, `oficio-motorista-*`, `oficio-motivo-field` | `cv-picker--people`, `cv-picker__card`, `cv-picker--vehicle`, `cv-picker--driver`, `cv-field--template` |

### 7.4 Documentos

| Hoje | Proposto |
|---|---|
| `oficio-documentos-block` / `-preview-section` / `-card` / `-facts` / `-fact` | `cv-document-panel` / `__preview` / `cv-document-card` / `cv-fact-grid` / `cv-fact-block` |
| `oficio-documentos-traveller-tile` | `cv-person-tile` |
| `oficio-documentos-route-card` | `cv-itinerary-card` |
| `document-inline-card` / `-viewer` / `-stack` / `-empty` / `-actions` | `cv-document-card` / `__viewer` / `cv-document-list` / `cv-empty-hint` / `cv-document-card__actions` |
| `prestacao-file-widget__*`, `cv-file-widget__*` | `cv-file-item__*` |
| `doc-pdf-toolbar*`, `doc-section`, `doc-title`, `doc-meta`, `doc-muted` | `cv-pdf-toolbar*`, `cv-doc-section`, `cv-doc-title`, `cv-doc-meta`, `cv-doc-muted` (e criar o CSS) |
| `termo-cabecalho/-secao/-tabela/-titulo/-texto/-assinaturas` | `cv-doc-header` / `cv-doc-section` / `cv-doc-table` / `cv-doc-title` / `cv-doc-body` / `cv-doc-signatures` |
| `assinaturas-central-*`, `oficio-assinatura-*`, `asgn-*` | `cv-signature-*` |
| `cv-signature-card` | ✅ manter |

### 7.5 Domínio: roteiro e diárias

| Hoje | Proposto |
|---|---|
| `roteiro-editor` / `__section` / `__oficio-card` | `cv-itinerary-editor` / `__section` (usar `cv-form-card`) |
| `roteiro-trecho-card`, `route-segment-card` | `cv-leg-card` |
| `roteiro-mapa*` | `cv-map-panel*` |
| `roteiro-sequencia__order` | `cv-leg-card__order` |
| `route-section-block` | `cv-form-block--leg` |
| `roteiro-list-card__diarias-*` | `cv-allowance-*` |
| `pt-resumo-box`, `cv-summary-item`, `cv-summary-tile` | **`cv-metric`** (`__label`, `__value`, `__description`) |
| `cv-summary-grid` | `cv-metric-grid` |
| `summary-items` | `cv-linked-list` (e criar o CSS) |
| `admin-overview__stats` | `cv-metric-grid` |
| `pte-card*` | `cv-record-card` + `cv-fact-grid` |
| `pt-activity*`, `pt-live-col`, `pt-efetivo-*` | `cv-checklist-card*`, `cv-side-column`, `cv-roster-*` |
| `dmv-option`, `dmv-group`, `dmv-prefill`, `dmv-lede` | `cv-choice-card`, `cv-conditional-group`, `cv-prefill-card`, `cv-lede` |
| `gdrive-*` (block, card, pend, meta, stat) | `cv-integration-*` |
| `admin-subcard`, `admin-list-card` | `cv-form-card--nested`, `cv-record-card` |
| `os-model-card`, `oficio-transporte-card` | `cv-choice-card`, `cv-picker__card` |

### 7.6 Feedback

| Hoje | Proposto |
|---|---|
| `alert` + `alert-*` + `cv-alert` + `cv-alert--*` + `diario-diaria-alert` + `pte-events__banner` | **`cv-notice`** + `cv-notice--info/success/warning/danger` |
| `alerts` (contêiner) | `cv-notice-stack` |
| `empty-state` + `app-empty-state` | `cv-empty-state` |
| `cv-confirm-page*` | `cv-confirm-panel*` (e criar o CSS) |
| `cv-dialog--danger/warning/success/document` | manter os nomes, **criar o CSS** |
| `cv-pendencias*` | `cv-todo-card*` |

---

## 8. Catálogo dos componentes globais propostos

Alvo: **~40 componentes globais**, cada um com um único arquivo CSS, um único dono e cobertura total de tema.

### 8.1 Camada 0 — fundação (sem componentes)

| Arquivo | Conteúdo |
|---|---|
| `01-reset.css` | Reset + `box-sizing` + `:focus-visible` global |
| `02-tokens.css` | **Toda** a escala primitiva (cor, espaço, raio, sombra, tipografia, z, motion) |
| `03-theme-dark.css` | Mapeamento semântico do tema escuro (base) |
| `04-theme-light.css` | Mapeamento semântico do tema claro |

### 8.2 Camada 1 — layout

| Componente | Classe raiz | Substitui |
|---|---|---|
| App shell | `cv-app` | `app-shell`, `layout.css` |
| Sidebar | `cv-sidebar` | `sidebar.css` |
| Página | `cv-page` (`--form`, `--flow`, `--narrow`, `--collection`) | `page-shell` + 6 aliases |
| Cabeçalho de página | `cv-page-header` | `page-header-stack`, `page-header--clean`, `app-page-hero` |
| Stepper | `cv-stepper` | `page-stepper`, `oficio-stepper` |
| Painel de conteúdo | `cv-page__panel` | `main-form-panel`, `app-form-shell`, `form-shell` |

### 8.3 Camada 2 — primitivas

| Componente | Classe raiz | Substitui |
|---|---|---|
| Botão | `cv-btn` | `cv-btn`, `btn`, `app-btn`, `btn--document-*` |
| Botão de ícone | `cv-icon-btn` | ✅ manter |
| Chip / badge | `cv-chip` | `cv-chip`, `status-chip`, `page-header-status-chip` |
| Ícone | `cv-icon` | ✅ manter |
| Aviso | `cv-notice` | 4 sistemas de alerta |
| Métrica | `cv-metric` + `cv-metric-grid` | 5 sistemas de resumo |
| Estado vazio | `cv-empty-state` | `empty-state`, `app-empty-state`, `list_empty` |
| Dica vazia | `cv-empty-hint` | `oficio-lc__empty-hint`, `text--empty` |
| Tooltip | `cv-tooltip` | `cv-global-tooltip`, `[data-tooltip]::after` |

### 8.4 Camada 3 — formulário

| Componente | Classe raiz | Substitui |
|---|---|---|
| Card de formulário | `cv-form-card` | `cv-form-section-card` + 8 aliases de módulo |
| Pilha de cards | `cv-form-stack` | `cv-form-section-stack` |
| Bloco de formulário | `cv-form-block` (`--split`, `--resource`, `--leg`) | `cv-form-block` + 8 aliases |
| Subseção de formulário | `cv-form-subsection` (`--split`) | `cv-form-subsection`, `wizard-inner-section` |
| Grade de campos | `cv-field-grid` | `field-grid` + `--cols-N` + `field-grid-rows` |
| Campo | `cv-field` | `field` + `app-form-field` + `cv-field` |
| Select customizado | `cv-select` | `cv-custom-select`, `form-select` |
| Picker de busca | `cv-picker` | `cv-search-picker`, `cv-resource-picker`, `oficio-*-picker` |
| Date picker | `cv-date-picker` | ✅ manter (+ absorver `travel-period-filter`) |
| File picker | `cv-file-picker` + `cv-file-item` | `file-picker` + `prestacao-file-widget` |
| Switch em card | `cv-switch-card` | `app-card-toggle` |
| Toggle segmentado | `cv-segment-toggle` | ✅ manter |
| Rodapé de card | `cv-form-card__footer` + `cv-card-footer` | ✅ manter (obrigar uso) |

### 8.5 Camada 4 — coleções

| Componente | Classe raiz | Substitui |
|---|---|---|
| Cabeçalho de coleção | `cv-collection-header` | `list-header`, `cv-filter-header`, markup inline do Quick Add |
| Abas | `cv-collection-tabs` | `cv-list-tabs` |
| Coleção | `cv-collection` + `__grid` | `list-panel`, `cv-card-grid` |
| Paginação | `cv-pagination` | `pagination-shell` |
| Criação inline | `cv-inline-create` | `quick-add-*` |
| Card de registro | `cv-record-card` | `cv-entity-card` + `oficio-lc` + `roteiro-list-card` + `pte-card` + `os-lc` |
| Linha de registro | `cv-record-row` | `simple-list-item`, `cv-record-row` |
| Card de módulo | `cv-module-card` | ✅ manter |

### 8.6 Camada 5 — blocos de conteúdo reutilizáveis

Estes são a maior oportunidade de reuso — hoje existem sob nome de módulo em 5–6 lugares:

| Componente | Classe raiz | Uso hoje |
|---|---|---|
| **Bloco de fato** | `cv-fact-block` + `cv-fact-grid` | Ofícios, Roteiros, PT, Eventos, Prestações, OS |
| **Linha de pessoa** | `cv-person-row` + `cv-person-list` | Ofícios, OS, PT, Eventos, Prestações |
| **Ladrilho de pessoa** | `cv-person-tile` | Ofícios (docs), Prestações |
| **Itinerário** | `cv-itinerary` + `__leg` | Ofícios, Roteiros, PT, Eventos, Prestações |
| **Card de itinerário** | `cv-itinerary-card` | Ofícios (docs), Prestações |
| **Painel de documentos** | `cv-document-panel` | Ofícios, Termos, PT, Prestações |
| **Card de documento** | `cv-document-card` | Ofícios, Termos, PT, Prestações, Eventos |
| **Visualizador PDF** | `cv-pdf-viewer` + `cv-pdf-toolbar` | Ofícios, Termos, PT, Prestações |
| **Card de assinatura** | `cv-signature-card` | Ofícios, Prestações |
| **Card de escolha** | `cv-choice-card` | OS (modelos), Prestações (troca motorista), PT (presets) |
| **Card de checklist** | `cv-checklist-card` | PT (atividades), Eventos (documentos) |
| **Card de integração** | `cv-integration-card` | Perfil (Drive), Eventos (Drive) |
| **Card de pendências** | `cv-todo-card` | Ofícios, PT, Prestações |
| **Painel de mapa** | `cv-map-panel` | Ofícios (etapa 3), Roteiros |

### 8.7 Camada 6 — overlays

| Componente | Classe raiz | Substitui |
|---|---|---|
| Diálogo | `cv-dialog` (`--danger`, `--warning`, `--success`, `--document`) | `cv-dialog` + 4 modais |
| Painel de confirmação | `cv-confirm-panel` | `cv-confirm-page` + 12 páginas |
| Menu de ações | `cv-action-menu` | `cv-action-menu` + `oficio-lc__action-menu` |
| Dropdown flutuante | `cv-floating-dropdown` | ✅ manter |
| Toast de progresso | `cv-progress-toast` | `cv-document-loading` |
| Ação flutuante (FAB) | `cv-fab` | `cv-floating-action` |

---

## 9. Plano de tokenização

### 9.1 Regra única

> Nenhuma regra CSS fora de `02-tokens.css`, `03-theme-dark.css` e `04-theme-light.css` pode conter um literal de cor, sombra, raio, espaço, duração ou z-index.

Hoje isso é violado em **318 regras**. A varredura que gerou esse número deve virar teste de CI (`core/tests/test_css_tokens.py`).

### 9.2 Escala proposta (primitivas em `02-tokens.css`)

**Cor — rampas neutras e semânticas, sem valor solto**

```
--gray-950 … --gray-50            (11 degraus)
--navy-950 … --navy-100           (marca)
--gold-900 … --gold-100           (accent)
--red / --amber / --green / --blue  (4 rampas semânticas, 9 degraus cada)
```

**Espaço** — manter `--space-1..12` (já existe, coerente). **Excluir** `--cv-page-gap`, `--cv-grid-gap`, `--cv-shell-padding`, `--space-card-x/y`, `--space-section-x/y`, `--space-field-gap`, `--space-form-gap` (aliases redundantes).

**Raio** — reduzir de 12 tokens (`sm, md, lg, xl, 2xl, control, control-lg, card, panel, section, shell, pill` + 4 `cv-*`) para **5**: `--radius-xs/sm/md/lg/pill`.

**Sombra** — reduzir de 14 tokens (`xs, sm, md, lg, inner, soft, card, panel, section, elevated, strong, inner-light` + glows) para **4**: `--shadow-1/2/3/4` + `--shadow-inset`.

**Tipografia** — usar só `--font-size-2xs..2xl` já definidos. Eliminar `rem` e `px` soltos (hoje 40+ ocorrências). Criar `--font-size-base` (usado e inexistente).

**Motion** — uma escala: `--motion-fast/base/slow` + `--ease-standard/--ease-emphasis`. Excluir `--transition-*` e `--duration-*` duplicados.

**Z-index** — uma escala usada de verdade:
```
--z-base:0 --z-raised:10 --z-sticky:100 --z-dropdown:200
--z-overlay:300 --z-modal:400 --z-toast:500
```
Hoje há `10050`, `1100`, `500`, `200`, `100`, `50`, `45`, `40`, `25` fora da escala.

### 9.3 Camada semântica (em `03-theme-dark.css`)

Nomear por **papel**, não por cor nem por componente:

```
--surface-page          --surface-card         --surface-card-header
--surface-raised        --surface-sunken       --surface-overlay
--border-subtle         --border-default       --border-strong    --border-focus
--text-primary          --text-secondary       --text-muted       --text-inverse
--text-on-accent
--accent                --accent-soft          --accent-contrast
--state-info/-success/-warning/-danger  (+ -soft, -border, -text)
--elevation-card        --elevation-overlay    --elevation-popover
```

**Excluir por completo** as famílias redundantes: `--theme-*` (49 tokens), `--route-*` (49), `--cv-card-family-*` (9), `--surface-form-*`/`--border-form-*`/`--surface-list-*` (page-shell, ~60), `--cv-btn-*` de cor (30), `--auth-*` (20). Total: **~215 tokens eliminados**.

### 9.4 Tokens de componente (permitidos, escopados)

Cada componente pode declarar tokens **no próprio bloco** (não em `:root`), sempre derivados da camada semântica:

```css
.cv-record-card {
  --record-card-bg: var(--surface-card);
  --record-card-border: var(--border-subtle);
  --record-card-band-bg: var(--surface-sunken);
}
```

Isso substitui os 110 tokens de `action-system.css`, 161 de `cv-buttons.css`, 128 de `cv-select.css`, 237 de `page-shell.css` — todos hoje em `:root` global.

### 9.5 Ordem final de carregamento proposta

```
01-reset · 02-tokens · 03-theme-dark · 04-theme-light
10-layout/* (app, sidebar, page, page-header, stepper)
20-primitives/* (btn, icon-btn, chip, icon, notice, metric, empty-state, tooltip)
30-form/* (form-card, form-block, field-grid, field, select, picker, date, file, switch, segment, footer)
40-collection/* (collection-header, tabs, collection, pagination, inline-create, record-card, record-row)
50-content/* (fact, person, itinerary, document, pdf, signature, choice, checklist, integration, todo, map)
60-overlay/* (dialog, confirm, action-menu, dropdown, toast, fab)
90-print/* (documentos PDF)
```

Sem `dark-redesign.css`. Sem CSS por módulo. Sem `extra_css` nas páginas — só o bundle.

---

## 10. Ordem de execução sugerida

Cada fase é independente e verificável.

| Fase | Ação | Ganho |
|---|---|---|
| **0** | Apagar os 4 aliases mortos de tema (`dark-dark`, `light-dark`, `dark-light`, `light-light`) | −1.100 linhas, zero risco visual |
| **1** | Apagar CSS morto: `app-page.css`, `buttons.css`, `buttons-functional.css`, blocos `.app-form-shell`/`.form-shell`, `main_list_card.html`, `roteiro_list_card.html`, `.app-page-hero--roteiros-list`, `.oficio-stepper__*`, `.page-header--clean` | −1.900 linhas |
| **2** | Corrigir os 18 tokens indefinidos (D-01, D-03, D-06, D-20, D-21) | Bugs visíveis resolvidos |
| **3** | Criar o CSS faltante dos componentes globais: `cv-dialog--*`, `cv-confirm-panel`, `cv-notice`, `summary-items`, `cv-btn--muted`, `empty-state__actions` | D-02, D-04, D-54 |
| **4** | Remover `auth.css` e `oficios.css` do `@import` global; mover `oficios.css` para as páginas de ofício | −4.777 linhas por página |
| **5** | Consolidar a escala: tokens de raio, sombra, motion, z-index, tipografia | Base para o resto |
| **6** | Inverter a arquitetura de tema: `dark-redesign.css` vira `03-theme-dark.css` (só tokens); a aparência volta para os componentes | O tema deixa de ser patch |
| **7** | Renomear `oficio-lc` → `cv-record-card` + extrair `cv-fact-block`, `cv-person-row`, `cv-itinerary` | Fim do maior vazamento de nome |
| **8** | Unificar `field.html` num contrato único de classe (D-41) | Um input, uma regra |
| **9** | Unificar shells: `cv-page--form/flow/narrow/collection`; apagar os 6 aliases | Fim do class soup |
| **10** | Migrar Roteiros e Termos para `list_page_cards` | Padrão de lista único |
| **11** | Fazer o `_roteiro_editor.html` sempre montar o card canônico | Roteiro avulso entra no padrão |
| **12** | Trazer login e assinatura pública para o bundle e para os tokens | Fim das ilhas |
| **13** | Substituir os 4 sistemas de alerta por `cv-notice`; os 5 de métrica por `cv-metric` | −4 sistemas |
| **14** | Teste de CI: proibir literal de cor fora dos arquivos de token; proibir classe de template sem CSS | Trava a regressão |

---

## Anexo A — Tokens definidos e nunca usados (amostra)

`--cv-btn-shadow`, `--cv-field-gap`, `--cv-list-card-gap`, `--cv-list-card-accent`, `--cv-status-draft-bg/-color`, `--cv-status-success-bg`, `--cv-status-warning-bg`, `--cv-status-danger-bg`, `--space-9`, `--space-card-x/y`, `--space-section-x/y`, `--radius-map`, `--radius-full`, `--shadow-strong`, `--shadow-inner-light`, `--glow-primary`, `--text-area-height-justificativa`, `--layout-quick-create-*`, `--filter-search-min-width`, `--filter-field-min-width`, `--z-background`, `--z-page-shell`, `--z-stepper`, `--z-footer-actions-fixed` — entre ~137 no total.

## Anexo B — Classes usadas em template sem nenhuma regra CSS (120)

`admin-password-grid`, `alert__message`, `assinaturas-central-*` (9), `attach-signed-modal__cancel`, `cadastros-hub`, `cv-action-dropdown__chevron`, `cv-card__hint`, `cv-chip-list`, `cv-chip__label`, `cv-confirm-page*` (3), `cv-dialog--danger/-document/-success/-warning`, `cv-document-viewer__body`, `cv-field-row`, `cv-field__hint`, `cv-file-field`, `cv-floating-action--back`, `cv-form-section-header__meta`, `cv-list-tab__label`, `cv-pendencias__body`, `cv-record-row__badges`, `cv-signature-card__status`, `delete-confirm-modal__body`, `destino-cidade`, `destino-estado`, `dmv-form`, `doc-*` (8), `document-inline-card--lazy`, `document-meta-item`, `document-number-field`, `empty-state__actions`, `evento-doc-picker`, `evento-lc__documentos-card`, `evento-step1-card`, `eventos-list-page`, `form-error`, `gdrive-card`, `gdrive-disabled-hint`, `mb-2`, `modelos-grupo`, `module-placeholder-card__header/-status`, `oficio-assinatura-etiqueta-links*`, `oficio-documentos-*` (6), `oficio-justificativa-card__wide-field`, `oficio-lc__action-menu-item--wa`, `oficio-lc__section--justificativas`, `oficio-lc__transport-row--roteiro`, `oficio-lc__wa-menu`, `oficio-motivo-field`, `oficio-motorista-*` (4), `oficio-transporte-card`, `oficio-transporte-root`, `os-block`, `os-form-body`, `os-lc`, `os-submit-btn`, `page-stepper--horizontal`, `pt-add-evento*`, `pt-efetivo-rows`, `pt-efetivo-section`, `pt-form-card`, `pt-preset-activities-field`, `py-2`, `roteiro-list-card__diarias-subblock--composicao`, `roteiro-mapa__error`, `roteiro-mapa__stale-hint`, `roteiro-trechos-date-picker-park`, `roteiro-wizard__form`, `rt-custeios-block`, `sidebar-item-text`, `sidebar-link--root`, `sidebar-link-text`, `small`, `summary-items`, `termo-*` (18), `text-danger`, `text-muted`, `text-warning-emphasis`, `travel-document-identification-grid`, `travel-document-resource-card*`, `trecho-tempo-adicional-hhmm`, `trecho-tempo-total`.

## Anexo C — Arquivos CSS por destino na reconstrução

| Arquivo hoje | Linhas | Destino |
|---|---|---|
| `dark-redesign.css` | 5.297 | **Dissolver** → `03-theme-dark.css` (tokens) + aparência nos componentes |
| `oficios.css` | 4.495 | **Dissolver** → `50-content/*` + `40-collection/record-card` |
| `page-shell.css` | 3.699 | **Fatiar** → `10-layout/*`, `30-form/field-grid`, `40-collection/*`, `60-overlay/*` |
| `roteiros.css` | 3.215 | **Dissolver** → `50-content/itinerary`, `50-content/map`, `30-form/*` |
| `forms.css` | 1.486 | **Fatiar** → `30-form/*`; apagar `.app-form-shell`/`.form-shell` |
| `cv-buttons.css` | 1.207 | → `20-primitives/btn` + `20-primitives/icon-btn` |
| `action-system.css` | 1.018 | → `60-overlay/action-menu` + `20-primitives/icon-btn` |
| `oficios-documentos-inline.css` | 1.004 | → `50-content/document` |
| `prestacoes_contas.css` | 999 | **Dissolver** → `50-content/*` |
| `cv-search-picker.css` | 954 | → `30-form/picker` |
| `cv-select.css` | 953 | → `30-form/select` |
| `gdrive-config.css` | 892 | → `50-content/integration` |
| `list-header.css` | 762 | **Fatiar** → `40-collection/header` + `40-collection/inline-create` + `30-form/date` |
| `planos-trabalho-eventos.css` | 705 | **Dissolver** → `40-collection/record-card` + `50-content/fact` |
| `cv-date-picker.css` | 651 | → `30-form/date` |
| `app-page.css` | 625 | ❌ **apagar** (morto) |
| `roteiros-list.css` | 599 | ❌ **apagar** (morto) |
| `theme.css` | 596 | **Dissolver** → `03/04-theme-*` |
| `utilities.css` | 583 | **Fatiar** → `20-primitives/notice` + `20-primitives/chip` + utilitários reais |
| `buttons-functional.css` | 496 | ❌ **apagar** (morto) |
| `ordens-servico.css` | 469 | **Dissolver** (23 `!important`) |
| `workspace-admin.css` | 457 | → `50-content/*` |
| `planos-trabalho-atividades.css` | 411 | → `50-content/checklist` |
| `sidebar.css` | 391 | → `10-layout/sidebar` |
| `prestacoes-assinatura.css` | 354 | → `50-content/signature` (com tokens) |
| `file-picker.css` | 347 | → `30-form/file` |
| `lists.css` | 306 | **Dissolver** → `40-collection/*` |
| `auth.css` | 282 | → `10-layout/auth` (com tokens), fora do bundle global |
| `cards.css` | 265 | → `40-collection/module-card` |
| `oficios-list-header.css` | 246 | **Dissolver** → `40-collection/record-card` + `60-overlay/action-menu` |
| `content-cards.css` | 239 | → `20-primitives/metric` + `50-content/document` |
| `form-sections.css` | 222 | → `30-form/form-block` |
| `tokens.css` | 218 | → `02-tokens.css` |
| `justificativas.css` | 209 | **Dissolver** → `40-collection/inline-create` |
| `diario-troca.css` | 193 | → `50-content/choice` |
| `document-viewer.css` | 169 | → `50-content/pdf` |
| `record-list.css` | 155 | → `40-collection/record-row` |
| `buttons.css` | 140 | ❌ **apagar** (morto) |
| `app-shell.css` | 133 | → `10-layout/app` |
| `list-tabs.css` | 121 | → `40-collection/tabs` |
| `prestacoes-documento-preview.css` | 110 | → `50-content/document` |
| `dialog.css` | 107 | → `60-overlay/dialog` |
| `base.css` | 102 | → `01-reset.css` |
| `dashboard.css` | 100 | → `10-layout/page` + `20-primitives/metric` |
| `pendencias.css` | 99 | → `50-content/todo` |
| `document-download-loading.css` | 90 | → `60-overlay/toast` |
| `domain.css` | 88 | **Dissolver** |
| `app-ui.css` | 79 | ❌ **apagar** (`app-page-hero` morto) |
| `termos.css` | 76 | **Dissolver** |
| `form-panel.css` | 73 | → `10-layout/page` |
| `layout.css` | 69 | → `10-layout/app` |
| `eventos-list.css` | 68 | ❌ **apagar** (patches sobre `oficio-lc`) |
| `stages.css` | 64 | **Dissolver** |
| `summary-items.css` | 34 | → `20-primitives/metric` |
| `style.css` | 19 | ❌ **apagar** (cadeia de `@import`) |
| `filter-header.css` | 18 | ❌ **apagar** (compat residual) |
| `documents.css` | 12 | ❌ **apagar** |

**Estimativa:** de 36.771 linhas para **~12.000–14.000**, com cobertura total dos dois temas e zero valor hardcoded.
