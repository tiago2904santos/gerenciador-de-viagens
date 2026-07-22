# Relatório de Paridade UI Lab × Sistema Real

**Data:** 2026-05-20  
**Branch:** `audit/ui-lab-paridade-global`  
**Base:** `main` (commit `9bd49fc` — feat unidade em Viatura + componentes relacionados)  
**Escopo:** Auditoria read-mostly; microcorreções seguras apenas onde indicado.

---

## 1. Resumo executivo

### Estado geral da paridade

| Área | Paridade estimada | Observação |
|------|-------------------|------------|
| Background / app shell | **Alta** | `app-shell` + `theme.css`/`tokens.css` unificam o fundo; UI Lab usa `app-shell--ui-lab` apenas como variante de demo |
| Headers (band/stack/rail) | **Alta em cadastros e listas** | Components em `templates/components/ui/headers/` adotados na maior parte dos CRUDs e listas |
| Structures (page-shell) | **Média-alta** | Cadastros e listas usam `page-shell--*`; wizards de ofício/roteiro ainda usam `app-page` / `app-page-shell` legado |
| Buttons (`cv-btn`) | **Média** | Design system novo em components; ofícios, assinaturas, roteiros editor e wizards ainda usam `btn btn-*` em massa |
| Listas / cards | **Alta em roteiros/ofícios** | `main_list_card.html` + `header_stack_filters`; cadastros simples usam `simple_list` via `list_page_standard` |
| Inputs / fields | **Média** | `form_field.html` → `field.html` no pipeline novo; UI Lab demonstra `cv-field-*` inline, não via includes |
| Selects / pickers | **Média-alta** | `cv-custom-select`, `cv-search-picker` globais; ofício transporte tem busca viatura custom (`oficio-viatura-busca`) |
| Toggles | **Média** | UI Lab: `cv-state-button`; produção: `field_action_button` (servidores/viaturas) + `app-card-toggle` (legado) |
| Chips / status | **Alta no component** | `chip.html` usado no UI Lab status; list cards usam badges via presenters |
| CSS / tokens | **Média** | `tokens.css` + `theme.css` existem; vários CSS de módulo (`oficios*.css`, `roteiros*.css`, `assinaturas`) com cores hardcoded |
| UI Lab como fonte | **Parcial** | Lab espelha visual aprovado mas **maioria do markup é inline**; poucos includes globais |

### Principais riscos

1. **Duas gramáticas de página:** `page-shell--*` (novo) vs `app-page` / `app-page-shell` (legado) — refatorar wizards quebra CSS acoplado em `oficios.css` / `app-page.css`.
2. **Botões legados (`btn`)** convivem com `cv-btn` — migração em `wizard_actions.html` afeta dezenas de testes e fluxos documentais.
3. **`_cv_icon.html` no dev/ui_lab** é dependência de `components/ui/buttons/button.html` — ícones do design system não estão em `static/`.
4. **Rota `/dev/ui-lab/cards/`** renderiza `lists.html`, não `cards.html` — documentação e links podem enganar.
5. **`js/dev/ui-lab-navigation.js`** referenciado em `dev/ui_lab/base.html` mas **arquivo ausente** — 404 silencioso em dev.
6. **Testes:** 6 failures + 8 errors na suite completa (principalmente cadastros unidade/cidade e wizard) — **pré-existentes** nesta branch, não causados pela auditoria.

### Principais divergências

- Wizard de ofícios: header próprio (`travel-document-wizard__header`), não `header_stack_stepper` / `page-shell--wizard`.
- Páginas placeholder (`planos_trabalho`, `ordens_servico`, etc.): `app-page` sem `page-shell`.
- `termos/index.html`: título manual + botão legado (corrigido nesta auditoria).
- `oficios-assinaturas-central.css`: dezenas de cores `#hex` e `rgba` fixos (fora de tokens).
- UI Lab fields/buttons: demos inline; sistema real usa `form_field` / `action_button` legado em vários pontos.
- Toggle RG/motorista: implementação nova com `field_action_button`, alinhada ao UI Lab “Field Attached”, mas **sem** `cv-state-button` semântico.

### O que foi corrigido nesta auditoria

| Arquivo | Correção |
|---------|----------|
| `templates/oficios/wizard_assinaturas.html` | Removido `style="padding: 0 1.15rem"` → classe `assinaturas-document-card__error` |
| `static/css/oficios-assinaturas-central.css` | Regra `.assinaturas-document-card__error` com `var(--space-card-x)` |
| `templates/termos/index.html` | `btn btn-primary` → `components/ui/buttons/button.html` (`cv-btn--primary`) |

### O que ficou pendente (fases futuras)

- Migrar wizard ofícios para `page-shell--wizard` + `header_stack_stepper`.
- Substituir `btn btn-*` em `wizard_actions.html`, `wizard_documentos.html`, assinaturas públicas.
- Tokenizar `oficios-assinaturas-central.css`, `roteiros-list.css`, trechos de `oficios.css`.
- Promover demos inline do UI Lab para includes em `components/ui/*`.
- Corrigir `ui_lab_cards` view / remover `cards.html` legado.
- Criar `ui-lab-navigation.js` ou remover referência.
- Mover `_cv_icon.html` para `templates/components/icons/`.
- Unificar `form_field` vs uso direto de `field.html` em todos os forms.
- HTML estrutural em `cadastros/configuracao/form.html` (`</section>` extras).

### Git / checkpoint

- **Início da sessão (instrução do usuário):** `main` com working tree **sujo** (cadastros, oficios, static, templates).
- **Ao criar branch:** working tree já **limpo** — alterações incorporadas em `9bd49fc` antes do checkpoint.
- **Checkpoint** `git add -A && git commit -m "checkpoint: ..."`: **não executado** (nothing to commit).
- **Branch criada:** `audit/ui-lab-paridade-global`.

---

## 2. Inventário do UI Lab

Rotas: apenas com `DEBUG=True` (`core/urls.py`). Namespace `core:ui_lab_*`.

### 2.1 Páginas e modelos

| Página | Template | Status metadata | Modelos / seções | CSS dev | JS |
|--------|----------|-----------------|------------------|---------|-----|
| Index | `index.html` | done | Overview cards por área | `ui-lab.css`, `ui-lab-navigation.css` | `ui-lab.js`, **`ui-lab-navigation.js` (ausente)** |
| Structures | `structures.html` | done | Quick Add Inline; Standard Simple; Standard; Wizard + stepper | + `ui-lab-pages.css` | — |
| Headers | `headers.html` | done | Band; Band+status; Rail Simple; Back Action; Filters; Advanced Filters; Filters+Quick Add; Stepper | + `ui-lab-pages.css` | — |
| Lists | `lists.html` | done | Lista standard; Lista+quick add; Lista cards roteiros | + `ui-lab-pages.css` | `realtime-filters` (global) |
| Buttons | `buttons.html` | build | Pill primary/secondary; Documental; PDF/DOCX; Circular; Operacional; Destructive; Field attached; Footer; States; State toggles | + `ui-lab-cv-buttons.css` (**não linkado**) | — |
| Fields | `fields.html` | planned* | 15+ painéis `cv-field-panel` (input, textarea, masks, grid, groups, side-action…) | + `ui-lab-fields.css` | masks, cv-select (global) |
| Selects/Filters | `selects_filters.html` | build | custom-select; search-picker; action-dropdown; filter-dropdown | + `ui-lab-fields.css` | cv-custom-select, cv-search-picker, cv-floating-dropdown |
| Status | `status.html` | planned* | Chips documentais, operacionais, entidade, filtros aplicados, variações | `ui-lab.css` | — |
| Feedback | `feedback.html` | planned | Placeholder + 4 callouts estáticos | `ui-lab.css` | — |
| Cards | `cards.html` | — | **Não servido** (view usa `lists.html`) | — | — |
| Overlays | `overlays.html` | planned | Placeholder + frames modal/drawer/popover | `ui-lab.css` | — |
| Tables | `tables.html` | planned | Tabela demo + pagination-shell | `ui-lab.css` | — |
| Documents | `documents.html` | planned | Viewer mock PDF | `ui-lab.css` | — |
| Signature | `signature.html` | planned | 3 cards assinatura | `ui-lab.css` | — |

\* *Metadata “planned” contradiz implementação HTML extensa — tratar como **aprovado visualmente, pendente componentização**.*

### 2.2 Includes globais usados no UI Lab

| Component | Onde |
|-----------|------|
| `components/ui/buttons/button.html` | structures, lists (Limpar filtros) |
| `components/ui/layouts/footer_actions.html` | structures |
| `components/lists/simple_list_row.html` | lists |
| `components/ui/badges/chip.html` | status |
| `roteiros/partials/roteiro_list_card.html` | lists (cards demo) |

**Todo o restante é markup inline** espelhando `components/ui/headers/*`, `cv-btn`, `cv-field`, etc.

### 2.3 Tokens principais (`static/css/tokens.css`)

- Cores estruturais: `--color-bg`, `--color-surface`, `--color-text`, `--color-primary*`, semânticas danger/success/warning/info
- Espaço: `--space-1`…`--space-10`, `--space-card-x/y`, `--cv-page-gap`, `--cv-shell-padding`
- Raios: `--radius-*`, `--cv-btn-radius`, `--cv-field-radius`, `--cv-card-radius`
- Controles: `--control-height-*`, `--cv-btn-height`, `--cv-field-height`, focus rings
- Sombras, tipografia, z-index, motion

Tema claro/escuro: **`theme.css`** (313 ocorrências de overrides); UI Lab herda `base.html` + `app-shell--ui-lab` (gradiente sutil em `ui-lab.css`).

### 2.4 Estado por modelo (resumo)

| Modelo | Estado |
|--------|--------|
| Background / shell | Aprovado; variante lab isolada |
| Headers (todos os rails) | Aprovado visual; **precisa virar component** (partials existem, lab não usa) |
| page-shell variants | Aprovado |
| cv-btn grammar | Aprovado; parcialmente em `cv-buttons.css` |
| cv-field grammar | Aprovado em lab; **duplicado** com `forms.css` + `ui-lab-fields.css` |
| cv-custom-select / search-picker | Aprovado + JS global |
| chip.html | Aprovado component global |
| Feedback / overlays / tables / documents | Incompleto no lab (placeholder) |
| `_cv_icon` em dev/ | **Divergente** — deveria ser component/static global |

---

## 3. Background

### UI Lab

- `templates/dev/ui_lab/base.html` → `{% block shell_class %}app-shell--ui-lab{% endblock %}`
- CSS: `static/css/dev/ui-lab.css` — fundo em camadas, compatível com tokens de superfície

### Páginas reais

- `templates/base.html`: `app-shell` padrão, `style.css` (bundle), `theme.css` via imports
- Sem inline style de background nos templates de produção (exceto PDF `oficio.html` — escopo documento impresso)

### Divergências

- UI Lab carrega CSS dev extra; produção não — **esperado**
- `page-shell.css` linkado **duas vezes** (`style.css` import + `base.html` link) — redundância, não divergência visual
- Módulos com `app-page` podem não herdar padding/gap do `page-shell` — listas card usam `app-page--main-card-list` **junto** com `page-shell--list` (ofícios/roteiros) — híbrido aceitável mas documentar

### Correções aplicadas

- Nenhuma no background global.

### Pendências

- Documentar contrato único: quando usar só `page-shell` vs `app-page` + `page-shell`
- Revisar dark mode em `roteiros-list.css` e `oficios-assinaturas-central.css` (cores fixas claras)

---

## 4. Headers

| Modelo UI Lab | Component global | Uso em produção | Gap |
|---------------|------------------|-----------------|-----|
| Header Band | (inline no lab) | Espelhado em structures demo | Band isolada rara em produção |
| Header Band + status | `header_band_status.html` | Pouco usado diretamente | — |
| Rail Simple | `header_stack_simple.html` | Cadastros forms, confirm_delete, configuração | OK |
| Rail Back Action | `header_stack_back_action.html` | `wizard_page.html` (parcial) | Ofício wizard **não usa** |
| Rail Filters | `header_stack_filters.html` | `list_page_standard`, ofícios/roteiros index | OK |
| Advanced Filters + chips | `advanced_filters.html` / inline lab | Roteiros/ofícios (status no header_stack_filters) | Chips aplicados nem sempre via `filter_chip.html` |
| Filters + Quick Add | `list_page_quick_add.html` | cargos, unidades, combustíveis index | OK |
| Rail Stepper | `header_stack_stepper.html` | `roteiro_form_page.html` (parcial) | Ofício wizard usa `wizard_stepper` próprio |

### Arquivos reais por tipo

- **header_stack_simple:** todos `cadastros/*/form.html`, `confirm_delete`, `configuracao/form.html`
- **header_stack_filters:** `components/lists/list_page_standard.html`, `oficios/index.html`, `roteiros/index.html`
- **Legado wizard:** `oficios/wizard_base.html` (`travel-document-wizard__header`), `roteiros/includes/_roteiro_editor.html` (`app-page-shell--wizard`)

### Hardcoded

- `headers.html` (lab): usa `btn btn-primary` em demos — não é produção
- Produção: hardcoded principalmente em CSS de módulo, não nos partials de header

### Correções aplicadas

- Nenhuma (headers aprovados; regra do escopo).

### Pendências

- Migrar `oficios/wizard_base.html` para `header_stack_stepper` + status chip
- Avaliar `roteiro_form_page` vs UI Lab wizard structure

---

## 5. Structures

| Estrutura UI Lab | Layout component | Produção |
|------------------|------------------|----------|
| Standard Simple | `standard_simple_page.html` / manual shell | Cadastros CRUD simples |
| Standard | `standard_page.html` | `roteiros/detail`, `configuracao` |
| Wizard | `wizard_page.html` | Ofício wizard (**legado**), roteiro form (misto) |
| List / Filters | `list_page_standard.html` | Cadastros listas simples |
| List + Quick Add | `list_page_quick_add.html` | cargos, unidades |
| Cards list | inline lab / `main_list_card` | ofícios, roteiros index |
| Form sections | `form_section.html` | Cadastros, config |
| Footer actions | `footer_actions.html` | Forms cadastros |
| Floating actions | `floating_action.html` / `floating_primary_action.html` | Listas e forms combustíveis/unidades |

### Páginas com `app-page` (sem `page-shell`)

`planos_trabalho/index`, `ordens_servico/index`, `prestacoes_contas`, `diario_bordo`, `documentos/index`, `eventos`, `assinaturas/index`, `termos/index` (parcial), vários placeholders.

### Correções aplicadas

- Nenhuma estrutural.

### Pendências

- Padronizar placeholders com `page-shell--standard-simple` + `header_stack_simple`
- Extrair `list_page` legado (`components/lists/list_page.html`) se ainda referenciado

---

## 6. Buttons

Mapeamento função → component ideal (`components/ui/buttons/`):

| Função | Component ideal | Variações encontradas | Páginas afetadas |
|--------|-----------------|----------------------|------------------|
| Criar/Novo | `floating_action` / header CTA | `cv-btn--primary`, `btn-primary` | listas, ofícios index |
| Salvar | `footer_actions` + `cv-btn--primary` | `btn-primary`, submit nativo | cadastros, wizard |
| Cancelar/Voltar | `cv-btn--secondary` / `back` | `btn-secondary` | wizard_actions, transporte |
| Voltar lista | `cv-btn--back-list` | `btn-secondary` + label manual | wizard_actions |
| Excluir | `cv-btn--danger` | `btn-danger`, links POST | confirm_delete |
| Remover item | `cv-icon-btn--delete` | inline | listas domínio |
| PDF/DOCX/Preview | `cv-icon-btn--pdf/docx/preview` | `btn-secondary` links | wizard_actions, documentos |
| Assinar | `cv-btn--sign` | `btn` custom assinaturas | wizard_assinaturas, público |
| Gerenciar campo | `field_manage_button` | `action_button` legado | servidores, viaturas |
| Toggle possui/não | `field_action_button` + state classes | `cv-state-button` (lab), `app-card-toggle` | servidores RG, viaturas motorista |
| Filtros | `button.html` variant secondary | `btn` | lists lab |

### Correções aplicadas

- `termos/index.html` → `button.html` primary

### Pendências

- **Grande:** `oficios/partials/wizard_actions.html` (~10 `btn` por etapa)
- **Grande:** `wizard_documentos.html`, `assinatura_central_documento.html`
- **Média:** `components/buttons/action_button.html` → deprecar em favor de `ui/buttons/button.html`
- Mover ícones de `dev/ui_lab/partials/_cv_icon.html`

---

## 7. Listas e cards

### Modelo correto (UI Lab lists — variante cards)

- Header: `header_stack_filters` (avançado com status)
- Container: `page-shell--list` + `list-panel`
- Grid: `list-grid--roteiros` / `card-list--roteiros`
- Item: `components/lists/main_list_card.html` (wrapper de domínio)

### Produção alinhada

- `oficios/index.html`, `roteiros/index.html` — **paridade alta** com UI Lab variante 3
- `list_page_standard.html` — lista simples (variante 1 UI Lab) — servidores, viaturas, cidades, estados
- `list_page_quick_add.html` — variante 2 UI Lab

### Divergências

- `dev/ui_lab/partials/_list_card.html` — demo local, diferente de `main_list_card`
- Status badges: presenters + CSS `roteiros-list.css` vs chips `chip.html` em filtros
- CTA clusters: `list_card_actions` vs botões inline em partials antigos

### Correções aplicadas

- Nenhuma.

### Pendências

- Unificar demo `_list_card` com `main_list_card` ou remover `cards.html`
- Revisar chips de filtro aplicado no header avançado (usar `components/ui/filters/filter_chip.html`)

---

## 8. Inputs / forms

### UI Lab

- Gramática `cv-field`, `cv-field-grid`, máscaras, estados — em `fields.html` + `ui-lab-fields.css`

### Produção

- Pipeline: `form_field.html` → `components/ui/forms/field.html` (select → `select.html` / `multiselect.html`)
- Classes legadas coexistem: `field`, `app-form-field`, `form-grid`

### Divergências

| Tópico | Lab | Real |
|--------|-----|------|
| Altura controle | `--cv-field-height` | OK em forms.css |
| Toggle RG | `cv-state-button` demo | `field_action_button` com `cv-field-side-action--state` |
| Checkbox | card toggle demo | `card_toggle.html` / `app-card-toggle` |
| Wizard ofício | — | `.field`, `.oficio-data-grid` custom |

### Correções aplicadas

- Nenhuma.

### Pendências

- Migrar toggles de cadastro para component único (`cv-state-button` ou formalizar `field_action_button` no design system)
- Reduzir duplicação `ui-lab-fields.css` vs `forms.css`

---

## 9. Selects, dropdowns e multiselects

### Modelo UI Lab (`selects_filters.html`)

- `cv-custom-select` + `data-cv-select`
- `cv-search-picker` + `data-cv-search-picker`
- `cv-action-dropdown`, `cv-filter-dropdown`

### Components

- `select.html`, `multiselect.html`, `dropdown.html`
- JS: `cv-custom-select.js`, `cv-search-picker.js`, `cv-floating-dropdown.js`, `cv-select.js`

### Páginas divergentes

- `oficios/wizard_transporte.html`: dropdown viatura custom (HTML+JS página) — **não** usa search-picker
- Wizard viajantes: multiselect termos (`app-termos-selector`) — CSS/JS dedicado

### Hardcoded

- Demo inline em lab: `style="width:36px"` em um botão (lab only)
- `oficios.css`, `cv-select.css` — revisar hex isolados

### Correções aplicadas

- Nenhuma (JS fora de escopo).

### Pendências

- Avaliar viatura busca → `cv-search-picker`
- Componentizar filter dropdown do lab

---

## 10. Toggles

| Contexto | Implementação atual | UI Lab |
|----------|---------------------|--------|
| Servidor sem RG | `field_action_button` success/danger | Field attached state |
| Viatura motorista fixo | idem + JS `viatura-motorista-fixo.js` | idem |
| Termos ofício | `cv-state-button` em `oficios_termos_selector.js` | State buttons panel |
| Checkbox cadastro | `app-card-toggle` | card toggle demo |

### Correções aplicadas

- Nenhuma.

### Pendências

- Documentar padrão oficial: `field_action_button` vs `cv-state-button`
- Altura alinhada: verificar `--cv-field-height` nos toggles lado a lado

---

## 11. Chips

### Modelo correto

`templates/components/ui/badges/chip.html` — famílias: status, entity, filter (removível), variações em `status.html`

### Produção

- UI Lab status: **100% chip.html**
- Listas: badges via `status_badge` / presenters / CSS classes em cards
- Filtros header: `header-applied-chip` inline em lab; produção parcial

### Chip azul entidade / RETIFICADO

- Definidos em contexto UI Lab (`ui_lab_chip_groups`); verificar presenters de ofício/roteiro para paridade de tons

### Correções aplicadas

- Nenhuma.

### Pendências

- Usar `chip.html` em filtros aplicados das listas avançadas
- Auditar dark mode dos tons de chip em `app-ui.css` / badges

---

## 12. CSS

### Arquivos analisados

**Globais:** `tokens.css`, `theme.css`, `style.css`, `base.css`, `layout.css`, `forms.css`, `lists.css`, `cards.css`, `cv-buttons.css`, `page-shell.css`, `app-ui.css`, `utilities.css`

**Dev:** `dev/ui-lab*.css` (5 arquivos; `ui-lab-cv-buttons.css` órfão)

**Módulo:** `oficios.css`, `oficios-*.css`, `roteiros.css`, `roteiros-list.css`, `domain.css`, `assinaturas.css`, `documentos-viewer.css`, `dashboard.css`, `auth.css`

### Hardcoded (amostra por arquivo — ocorrências `#|rgb`)

| Arquivo | ~Count | Gravidade |
|---------|--------|-----------|
| `theme.css` | 313 | Esperado (definição tema) |
| `cv-buttons.css` | 86 | Média |
| `page-shell.css` | 62 | Média |
| `oficios-assinaturas-central.css` | 36+ | **Alta** (fundo claro fixo) |
| `roteiros-list.css` | 27 | Alta |
| `forms.css` | 28 | Média |
| `oficios.css` | 17+ | Alta |

### Duplicações

- `page-shell.css` no bundle e no `<link>` do base
- `cv-buttons.css` no bundle e link direto
- Pastas `components/lists` vs `components/ui/lists`
- `ui-lab-fields.css` vs `forms.css` para mesma gramática visual

### Classes mortas prováveis

- `ui-lab-*` fora do lab
- `app-btn` se migração `cv-btn` completar
- Variantes antigas em `buttons.css` vs `cv-buttons.css`

### Classes exclusivas de página que deveriam ser component

- `travel-document-wizard__*`, `oficio-viatura-busca__*`, `assinaturas-document-card__*` (OK como módulo, mas tokenizar cores)

### Tokens ausentes

- Padding horizontal 1.15rem usado em assinaturas — não há token dedicado (usa-se `--space-card-x` na correção pontual)

### Correções aplicadas

- `.assinaturas-document-card__error` com token de espaçamento

### Pendências

- Passagem sistemática `docs/CSS_TOKENS_AUDITORIA.md` + este relatório
- Remover ou linkar `ui-lab-cv-buttons.css`

---

## 13. Templates — tabela de paridade

| Página | Tipo | Modelo esperado | Modelo atual | Divergência | Correção | Pendente |
|--------|------|-----------------|--------------|-------------|----------|----------|
| cadastros/servidores | List | list_page_standard | OK | — | — | — |
| cadastros/servidores/form | Form simple | standard-simple + field | OK + toggles custom | Toggle não cv-state-button | — | Padronizar toggle |
| cadastros/viaturas/form | Form simple | standard-simple | OK | motorista toggle | — | JS fora escopo |
| cadastros/unidades | List+QA | list_page_quick_add | OK | — | — | — |
| cadastros/cargos | List+QA | list_page_quick_add | OK | — | — | — |
| cadastros/combustíveis | Form | standard-simple | OK | — | — | — |
| cadastros/cidades/estados | List | list_page_standard | OK | — | — | — |
| cadastros/configuracao | Form standard | standard + sections | OK | `</section>` extras | — | Corrigir HTML |
| cadastros/index | Hub | cards módulo | module_card | — | — | — |
| roteiros/index | List cards | UI Lab lists v3 | OK | extra_css roteiros-list | — | — |
| roteiros/detail | Detail standard | standard | OK | — | — | — |
| roteiros/roteiro_form | Wizard | page-shell--wizard + stepper | Misto | Classes app-page | — | Migrar shell |
| oficios/index | List cards | UI Lab lists v3 | OK | — | — | — |
| oficios/wizard_* | Wizard | page-shell--wizard | app-page legado | Header/actions btn | — | **Grande** |
| oficios/wizard_transporte | Form section | form_section + cv-field | Custom viatura busca | — | — | search-picker |
| oficios/wizard_assinaturas | Form/docs | assinaturas module | OK | inline style | **Sim** | tokenizar CSS módulo |
| termos/index | Info | standard-simple | app-page legado | btn legado | **Sim** | Migrar shell |
| planos_trabalho/index | Placeholder | standard-simple | app-page placeholder | — | — | Ao implementar |
| ordens_servico/index | Placeholder | standard-simple | app-page | — | — | Ao implementar |
| justificativas/modelos | List simple | list_page_simple | OK | — | — | — |
| oficios/modelos_motivo | List simple | list_page_simple | OK | — | — | — |
| integracoes/google_drive | — | — | (não auditado linha a linha) | — | — | Fase 2 |
| usuarios/index | — | list ou placeholder | (verificar) | — | — | Fase 2 |
| documentos/pdf_viewer | Viewer | documents lab | btn legado | — | — | Média |
| assinaturas/* | Público | signature lab | btn + layout próprio | — | — | Grande |
| dev/ui-lab/* | Lab | — | inline demos | Poucos includes | — | Componentizar |

---

## 14. Riscos

| Risco | Detalhe |
|-------|---------|
| Refatorar wizard ofícios | Quebra CSS/JS acoplado; 428 testes, falhas já em wizard/cadastros |
| Remover `btn` globalmente | `buttons.css` ainda necessário para legado |
| Mover `_cv_icon` | Quebra todos `cv-btn` com ícone até atualizar includes |
| Unificar list_page.html legado | Pode haver views ainda apontando |
| Dark mode em assinaturas | Cores #fff/#0f172a fixas — contraste ruim em tema escuro |
| Dependência oculta | `field_manage_button.html` / `field_action_button.html` novos, não no UI Lab como partial nomeado |

---

## 15. Plano de próximas fases

### Correções rápidas (< 1h cada)

- Remover segundo `<link>` de `page-shell.css` se bundle cobrir
- Criar stub `ui-lab-navigation.js` vazio ou remover tag
- Corrigir view `ui_lab_cards` → `cards.html` ou redirecionar
- Corrigir `</section>` em `configuracao/form.html`
- Mais inline styles pontuais (busca `style=` em templates)

### Refatorações médias (1–3 dias)

- `wizard_actions.html` → `cv-btn` + icon buttons documentais
- Tokenizar `oficios-assinaturas-central.css` e `roteiros-list.css`
- Placeholders → `page-shell--standard-simple`
- Filtros aplicados com `chip.html`

### Refatorações grandes (sprint)

- Ofício wizard → `wizard_page.html` + `header_stack_stepper`
- Roteiro editor legado → `page-shell--wizard`
- UI Lab demos → includes globais (eliminar inline)
- Deprecar `components/buttons/` e `components/lists/` legado
- Ícones em `static/icons` + sprite

### JS (fase dedicada)

- Viatura busca vs search-picker
- Unificar toggles RG/motorista com component JS único
- Auditar duplicação scripts no `ui_lab/base.html`

### Testes visuais

- Screenshots em `screenshots/auditoria-telas/` vs estado atual
- Playwright/snapshot por rota UI Lab + páginas reais críticas

---

## 16. Checklist final

| Item | Resultado |
|------|-----------|
| `python manage.py check` | OK (0 issues) |
| `python manage.py test` | **FAIL** — 428 tests: 6 failures, 8 errors, 1 skipped (cadastros unidade/cidade, wizard; pré-existentes) |
| Páginas inspecionadas | UI Lab completo; cadastros; roteiros; ofícios; termos; planos/ordens placeholder; amostra assinaturas/wizard |
| Arquivos alterados | `wizard_assinaturas.html`, `oficios-assinaturas-central.css`, `termos/index.html` |
| Arquivos criados | `docs/RELATORIO_UI_LAB_PARIDADE_GLOBAL.md` |
| Branch | `audit/ui-lab-paridade-global` |
| Pendências registradas | Sim — seções acima |

---

## Apêndice A — Mapa de components globais (`templates/components/`)

**ui/buttons:** button, icon_button, floating_action, floating_primary_action, footer_action, field_action_button, field_manage_button  

**ui/headers:** header_stack_simple, header_stack_filters, header_stack_back_action, header_stack_stepper, header_band_status  

**ui/layouts:** page_shell, standard_page, standard_simple_page, wizard_page, main_panel, quick_add, form_section, footer_actions  

**ui/forms:** field, input, textarea, select, multiselect, dropdown, field_grid, field_group  

**ui/filters:** filter_bar, advanced_filters, search_input, filter_chip  

**ui/lists:** list_card, list_toolbar, pagination, card_metric, route_card, list_card_actions, status_pill  

**ui/badges:** chip, status_badge, status_pill  

**ui/feedback:** alert, empty_state, field_error, form_errors  

**lists/ (legado):** list_page*, simple_list*, pagination, main_list_card, …  

**forms/ (legado):** form_field, form_actions, card_toggle, input_with_action, …  

---

## Apêndice B — Inline styles em templates (produção)

| Arquivo | Linha | Nota |
|---------|-------|------|
| `oficios/wizard_assinaturas.html` | ~~80~~ | **Corrigido** |
| `documentos/pdf/oficio.html` | 9 | PDF impresso — exceção aceitável |
| `dev/ui_lab/selects_filters.html` | 517+ | Escopo dev apenas |

---

*Relatório gerado na auditoria de paridade UI Lab. Não altera regras de negócio, models ou migrations.*
