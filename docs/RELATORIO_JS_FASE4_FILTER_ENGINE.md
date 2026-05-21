# Relatório JS Fase 4 — Filter Engine

**Branch:** `refactor/js-filters-fase4`  
**Base:** `refactor/js-fields-init-fase3`  
**Data:** 2026-05-20

## 1. Resumo executivo

### O que foi feito

- Consolidação de `static/js/components/realtime-filters.js` como API oficial `window.CV.filters` com `init(root)`, `update(scope)`, `clear(scope)`, `getState(scope)`.
- Idempotência por escopo via `data-cv-filter-bound="true"`.
- Busca com normalização sem acento, trim e múltiplos termos em **AND**.
- Evento `cv:filters:updated` com `{ scope, total, visible, hidden, state }`.
- Compatibilidade mantida com `window.CVRealtimeFilters` (delegação para `CV.filters`).
- Contador opcional com `data-cv-results-count-template` (`{{visible}}`, `{{total}}`).
- `simple_list.html`: contador + empty state client-side (já existia empty state; contador adicionado).
- UI Lab `lists.html`: três demos com escopo, busca, limpar, empty state, contador; demo cards com `data-cv-filter="status"` alinhado a `rascunho`.
- `docs/DATA_ATTRIBUTES_JS.md` atualizado na seção de filtros.

### O que não foi mexido

- `pages/roteiros/editor/index.js`, `roteiros-map.js`, motor de rotas/trechos.
- Models, migrations, endpoints, payloads.
- CSS visual novo.
- Inline JS/CSS.
- Integração de `CV.filters` dentro de `CV.fields.init` (motores independentes).
- Filtros server-side (GET `q`, `status`, paginação Django).

### Riscos preservados

- Listas com paginação server-side: filtro client-side atua só sobre itens já renderizados na página atual.
- Ofícios/roteiros: status no header continua podendo submeter via GET; filtro em tempo real é camada adicional nos cards da página.
- Botão “Limpar” com `href` + `data-cv-filter-clear`: `preventDefault` evita navegação ao limpar no cliente.

## 2. Inventário de filtros

| Página / componente | Scope? | Search? | Status? | Items? | Empty state? | Counter? | Clear? | Observação |
|----------------------|--------|---------|---------|--------|--------------|----------|--------|------------|
| `list_page_standard.html` | sim | via `header_stack_filters` | se `status_options` | `simple_list_row` | `simple_list.html` | `simple_list.html` | via header | Cadastros: servidores, viaturas, cidades, estados |
| `list_page_quick_add.html` | sim | sim | não | `simple_list_row` | `simple_list.html` | `simple_list.html` | sim | Cargos, unidades, combustíveis |
| `list_page.html` | sim | herdado | — | herdado | herdado | herdado | — | Legado |
| `header_stack_filters.html` | — | sim | opcional | — | — | — | opcional | GET preservado |
| `simple_list_row.html` | — | — | — | sim + `data-search-text` | — | — | — | |
| `main_list_card.html` | — | — | `data-status-value` | sim + search | — | — | — | Ofícios/roteiros |
| `oficios/index.html` | sim | header | header (server) | cards | sim | não | header | Paginação server |
| `roteiros/index.html` | sim | header | header (server) | cards | sim | não | header | Paginação server |
| `dev/ui_lab/lists.html` | 3× sim | sim | demo cards | rows/cards | sim | sim | sim | Referência Fase 4 |
| `dev/ui_lab/headers.html` | não | visual | visual | — | — | — | — | Sem motor lista |
| `dev/ui_lab/structures.html` | não | — | — | — | — | — | — | Estruturas estáticas |
| Termos / justificativas / modelos | parcial | se usam list_page | — | — | — | — | — | Via componentes |
| `selects_filters.html` | não | — | — | — | — | — | — | `data-cv-filter-dropdown` = outro motor |

## 3. API CV.filters

| Item | Detalhe |
|------|---------|
| Arquivo | `static/js/components/realtime-filters.js` |
| API pública | `CV.filters.init`, `update`, `clear`, `getState`, `applyFilters`, `normalizeText`, `matchesFilter` |
| Compatibilidade | `CVRealtimeFilters.*` → mesma implementação |
| Evento | `cv:filters:updated` (bubbles) |
| Idempotência | `data-cv-filter-bound="true"` no escopo; re-`init` não duplica listeners |
| `init(root)` | `undefined`/`document`/`HTMLElement`/subárvore; retorna quantidade de escopos ligados |

## 4. Components ajustados

| Component | Antes | Depois | Páginas afetadas | Risco |
|-----------|-------|--------|------------------|-------|
| `realtime-filters.js` | API legada, sem multi-termo, sem evento | `CV.filters` completo | Todas com scope | Baixo |
| `simple_list.html` | empty state only | + contador template | list_page_* cadastros | Baixo |
| `dev/ui_lab/lists.html` | demo sem contrato | scope + filtros + empty + count | UI Lab | Baixo |

## 5. Páginas migradas

| Página | Antes | Depois | Risco | Status |
|--------|-------|--------|-------|--------|
| Cargos, unidades, combustíveis | scope + search (quick add) | + contador/empty em `simple_list` | Baixo | Via component |
| Servidores, viaturas, cidades, estados | scope + header search GET | + contador/empty client | Médio (só página atual) | Via component |
| Ofícios / roteiros index | scope + cards | motor reforçado; sem mudança template | Médio | Compatível |
| UI Lab lists | sem motor | contrato completo | Baixo | Feito |

## 6. Páginas não migradas

| Página | Motivo | Fase recomendada |
|--------|--------|------------------|
| UI Lab headers / structures | referência estática, sem lista filtrável | — |
| Páginas só com filtro GET sem `data-cv-filter-item` | sem itens client-side | avaliar caso a caso |
| Wizard ofício / editor roteiro | fora de escopo | Fase 5+ (domínio) |
| `selects_filters.html` dropdowns | motor `cv-select`, não lista | — |

## 7. UI Lab

| Tela | Resultado |
|------|-----------|
| `/dev/ui-lab/lists/` | Busca, status (cards), limpar, empty state, contador — contrato aplicado |
| `/dev/ui-lab/headers/` | Não alterado (sem escopo lista) |
| `/dev/ui-lab/structures/` | Não alterado |

**Risco:** Quick Add no demo 2 permanece com `data-quick-add-toggle`; filtros não chamados em `CV.fields.init`.

## 8. Testes

### `python manage.py check`

OK — 0 issues.

### `python manage.py test`

- **Total:** 428
- **Failures:** 6
- **Errors:** 8
- **Skipped:** 1
- **Tempo:** ~42s

Falhas pré-existentes (cadastros unidade/cidade/CEP mock, wizard ofício/termos). Nenhuma referência a `realtime-filters` / `CV.filters` na saída.

### Smoke manual (checklist)

- [ ] UI Lab Lists: busca, status, limpar, empty, contador
- [ ] Cargos: busca + Quick Add
- [ ] Combustíveis: busca + limpar
- [ ] Unidades: busca + Quick Add
- [ ] Servidores: busca sem acento + contador/empty
- [ ] Viaturas: placa/modelo + contador/empty
- [ ] Roteiros index: busca + status
- [ ] Ofícios index: busca + status
- [ ] Tema claro/escuro

## 9. Arquivos alterados

- `static/js/components/realtime-filters.js`
- `templates/components/lists/simple_list.html`
- `templates/dev/ui_lab/lists.html`
- `docs/DATA_ATTRIBUTES_JS.md`
- `docs/RELATORIO_JS_FASE4_FILTER_ENGINE.md`

## 10. Pendências

- Smoke manual completo no navegador.
- Avaliar `data-cv-results-count` visível no header de ofícios/roteiros (sem redesign).
- Fase 5: motores de domínio (rotas/trechos) — não iniciar antes de validar filtros em produção.
