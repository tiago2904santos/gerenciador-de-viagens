# Relatório de Consistência JavaScript

**Data:** 2026-05-20  
**Branch:** `audit/js-consistencia-global`  
**Escopo:** Auditoria read-only + microcorreções apenas se seguras (nenhuma aplicada nesta fase além do relatório).

---

## 1. Resumo executivo

### Estado geral do JS

O projeto possui **~46 arquivos JS** em `static/js/`, com arquitetura **híbrida**: parte moderna (ES modules, `data-*`, motores em `components/`) e parte legada (IIFEs monolíticos, IDs fixos, `window.*` globais). Não há `<script>` inline em templates de produção (validado por testes em `oficios/tests/test_wizard_dados_viajantes.py`), o que é positivo.

A carga global em `base.html` é alta: tema, sidebar, máscaras, toggles RG, filtros em tempo real, três famílias de select/picker, dropdowns e `cv-select.js` — com **duplicação de carregamento** no UI Lab (`cv-custom-select`, `cv-search-picker`, `cv-select` repetidos).

### Principais duplicações

| Área | Duplicação | Gravidade |
|------|------------|-----------|
| **Rotas/trechos** | `roteiros-map.js` (647 linhas) + lógica equivalente embutida em `pages/roteiros/editor/index.js` (~1390 linhas) | **Crítica** |
| **Quick Add** | `core/app.js` vs `dev/ui-lab.js` (`data-ui-lab-toggle` paralelo) | Média |
| **CSRF / fetch** | `getCookie` em mapa; `csrfFromForm` em autosave; `querySelector` em editor | Média |
| **Select UI** | `cv-custom-select`, `cv-search-picker`, `cv-select`, `filterable-multiselect`, `app-multiselect` | Alta |
| **Wizard glance** | `roteiros_wizard.js` (protocolo + resumo sticky) só em ofícios | Baixa |
| **Módulos ES vazios** | `trechos.js`, `mapa.js`, `destinos.js` etc. exportam stub; lógica real no `index.js` | Média (dívida técnica) |

### Principais riscos

1. **Dois motores de rota** podem divergir em payload, preenchimento de trechos e tratamento de erro (mapa vs preview API).
2. **`pages/roteiros/editor/index.js` monolítico** — qualquer correção exige alto risco de regressão; difícil testar isoladamente.
3. **Autosave** com validadores por modelo em `window` — risco de payload vazio se validator retornar true cedo demais (mitigado por `AppAutosaveValidators.roteiro`).
4. **Máscaras** só em `input[data-mask]` no load — campos injetados dinamicamente (quick add, trechos HTML) podem ficar sem máscara até reload.
5. **Globals `window.OficioWizard` / `RoteirosEditor`** acoplam páginas sem contrato formal de módulos.

### Áreas críticas

1. Roteiros × Ofício (roteiro wizard) — mesmo stack de scripts, implementações sobrepostas.
2. Editor de roteiro (`index.js`) — coração do domínio viagem.
3. Ofício transporte + motorista + viatura busca — três JS de página + pickers globais.
4. Autosave (`autosave.js` + hooks por formulário).

### O que pode ser corrigido rápido (Fase 1)

- Unificar Quick Add do UI Lab para usar só `data-quick-add-toggle` (remover `ui-lab.js` duplicado).
- Remover scripts duplicados em `dev/ui_lab/base.html` (já carregados em `base.html`).
- Documentar contrato `data-*` em `docs/ui-components.md` (se existir) ou README interno.
- Garantir `data-cv-filter-item` em todos os itens de listas (já em `simple_list_row`, `main_list_card`).

### O que exige refatoração planejada

- Extrair motor de trechos/rotas de `index.js` para `modules/routes.js`.
- Unificar cálculo de rota mapa + preview sob um serviço HTTP com CSRF centralizado.
- Quebrar `index.js` em módulos reais (destinos, trechos, diárias, mapa bridge).
- Consolidar pickers/selects atrás de um `initAllCvFields(root)`.

---

## 2. Inventário de arquivos JS

| Arquivo | Linhas (aprox.) | Finalidade | Páginas / uso | Dependências | Problemas | Status |
|---------|----------------|------------|---------------|--------------|-----------|--------|
| `core/theme-shared.js` | pequeno | Preferências de tema (localStorage) | Todas | — | OK | Manter |
| `core/theme-init.js` | pequeno | Aplica tema no load | Todas | theme-shared | OK | Manter |
| `core/app.js` | 115 | Quick Add + quick edit global | cargos, unidades, combustíveis | — | Duplica lab | Manter / fundir lab |
| `theme-toggle.js` | pequeno | Toggle tema UI | base | theme-shared | OK | Manter |
| `components/sidebar.js` | — | Sidebar accordion | base | — | OK | Manter |
| `components/masks.js` | 80 | Máscaras `data-mask` | base (global) | — | Sem re-scan DOM | Refatorar (observer) |
| `components/card-toggle.js` | 124 | Card toggle + RG servidor (par) | base | — | OK pós Fase 3 | Manter |
| `components/viatura-motorista-fixo.js` | 94 | Toggle motorista fixo (par) | viaturas/form | card-toggle pattern | Duplica sync | Fundir em toggles.js |
| `components/realtime-filters.js` | 199 | Filtro lista `data-cv-*` | listas com scope | — | Bom motor | Manter / estender |
| `components/cv-custom-select.js` | 367 | Select custom premium | base + forms | cv-select? | Overlap cv-select | Manter / unificar |
| `components/cv-search-picker.js` | 545 | Search picker multiselect | base, ofícios, forms | — | Complexo | Manter |
| `components/cv-floating-dropdown.js` | — | (verificar) | base | — | Investigar | Manter |
| `cv-select.js` | 278 | Action + filter dropdown | base | — | OK global | Manter |
| `components/filterable-multiselect.js` | — | Multiselect filtrável legado? | pouco uso | — | Investigar remoção | Investigar |
| `components/app-multiselect.js` | 244 | Multiselect custom equipe | wizard dados viajantes | — | Paralelo search-picker | Fundir ou deprecar |
| `components/app-motorista-picker.js` | 237 | Picker motorista ofício | wizard transporte | — | Específico domínio | Manter até motor unificado |
| `components/oficio-motorista-suffix.js` | — | Sufixo nº ofício motorista | transporte | — | Específico | Manter |
| `autosave.js` | 249 | Autosave genérico | roteiro form, outros | AppAutosaveSnapshots | Globals | Manter / core/http |
| `roteiros-map.js` | 647 | Mapa Leaflet + POST rota | roteiro form, ofício roteiro | RoteirosEditor, L | IDs fixos, getCookie | Refatorar → routes-map |
| `roteiros.js` | 13 | Boot editor ES module | roteiro/ofício roteiro | editor/index | Stub modules | Refatorar |
| `pages/roteiros/editor/index.js` | **1390** | Editor completo roteiro | roteiro form, ofício roteiro | map, autosave, OficioWizard | Monolito | **Refatorar crítico** |
| `pages/roteiros/editor/trechos.js` | 3 | Stub módulo | — | — | Vazio | Remover ou implementar |
| `pages/roteiros/editor/mapa.js` | 3 | Stub módulo | — | — | Vazio | Remover ou implementar |
| `pages/roteiros/editor/destinos.js` | stub | Destinos (real no index) | — | — | — | Fundir |
| `pages/roteiros/editor/diarias.js` | stub | Diárias | — | — | — | Fundir |
| `pages/roteiros/editor/retorno.js` | stub | Retorno | — | — | — | Fundir |
| `pages/roteiros/editor/state.js` | stub | Estado | — | — | — | Fundir |
| `pages/roteiros/editor/utils.js` | stub | Utils | — | — | — | Fundir |
| `roteiros_wizard.js` | 355 | Protocolo + glance ofício | wizard dados | — | IDs ofício | Extrair wizard-glance |
| `roteiros-map.js` | ver acima | Mapa | roteiro pages | Leaflet | ver §5 | Refatorar |
| `pages/oficios-transporte.js` | 385 | Viatura busca, motorista | transporte | fetch API | IDs ofício | Refatorar |
| `pages/oficios-dados-viajantes.js` | — | Custeio, motivo, multiselect | dados viajantes | — | — | Manter |
| `oficios_termos_selector.js` | 93 | Termos por viajante | dados viajantes | cv-search-picker | — | Manter |
| `pages/configuracoes.js` | 124 | CEP lookup | configuração | fetch | — | Manter |
| `pages/oficios-justificativa-wizard.js` | — | Justificativa | wizard | — | — | Manter |
| `pages/oficios-documentos-inline.js` | — | Docs inline | wizard docs | fetch | — | Manter |
| `pages/oficios-assinaturas-wizard.js` | 84 | Assinaturas | wizard | — | — | Manter |
| `pages/assinaturas-central.js` | — | Central assinaturas | assinaturas | — | — | Manter |
| `pages/assinatura-pdf.js` | 280 | PDF assinatura | público | pdf.js | — | Manter |
| `pages/signature-public.js` | — | Assinatura pública | público | — | — | Manter |
| `pages/documentos-pdf-viewer.js` | 184 | Viewer PDF | documentos | pdf.js | — | Manter |
| `dev/ui-lab.js` | 114 | Quick add + demos lab | UI Lab | duplica app.js | — | Fundir |
| `dev/ui-lab-navigation.js` | stub | Placeholder 404 | UI Lab | — | OK | Manter |

---

## 3. Scripts inline encontrados

| Template | Código inline? | Finalidade | Risco | Destino global sugerido |
|----------|----------------|------------|-------|------------------------|
| Templates produção (wizard, cadastros, listas) | **Não** (regra de teste) | — | Baixo | — |
| `assinaturas/assinatura_token.html` | Apenas `<script src=...>` | PDF + assinatura | Baixo | OK |
| `documentos/pdf_viewer.html` | `<script src=vendor pdf.js>` | PDF.js | Baixo | OK |
| `roteiros/roteiro_form_page.html` | Leaflet CDN + scripts estáticos | Mapa externo | Médio (CDN) | Self-host Leaflet |
| `oficios/wizard_roteiro.html` | Mesmo stack roteiro | Editor embed | Médio | shared bundle |

**json_script (dados, não lógica):** `roteiro-editor-state-data`, `roteiro-editor-routes-data`, `roteiro-editor-diarias-data`, `roteiro-mapa-inicial`, `initialTrechosData` — padrão correto Django.

---

## 4. Mapa por funcionalidade

### Rotas / trechos

| Onde | Arquivos | Duplicações | Riscos | Unificação proposta |
|------|----------|-------------|--------|---------------------|
| Mapa + geometria | `roteiros-map.js` | Paralelo a preview em `index.js` | Endpoints/payload diferentes unificados via `RoteirosEditor` bridge | `modules/route-map.js` + `modules/route-calculator.js` |
| Trechos UI | `pages/roteiros/editor/index.js` | `urlTrechosEstimar`, `renderTrechos`, `buildTrechoCard` | Monolito | `modules/trechos-ui.js` |
| Estimar par | `index.js` `runAutoEstimarTrechos` | Similar a preview legs | `route-calculator.estimateSegment` |
| Preview rota | `index.js` `applyRoutePreviewResult` | Usado por `roteiros-map.js` | API única |
| Diárias | `index.js` `calculateDiarias` | Só editor | `modules/diarias.js` |

### Filtros simples

| Onde | Arquivos | Duplicações | Riscos | Unificação |
|------|----------|-------------|--------|------------|
| Listas cadastro | `realtime-filters.js` | Nenhuma outra implementação ativa encontrada | Cards em `main_list_card` precisam `data-cv-filter-item` | **Já é o motor** — estender para tabelas |
| UI Lab | Mesmos `data-cv-*` nas demos | — | Documentar |

**Páginas com `data-cv-realtime-filter-scope`:** `list_page_standard`, `list_page`, `list_page_cards`, `list_page_quick_add` (busca no header), ofícios/roteiros index.

**Páginas só server-side filter (sem motor JS):** podem existir em CRUDs sem scope — verificar ao migrar.

### Quick Add

| Onde | Arquivos | Divergências | Unificação |
|------|----------|--------------|------------|
| Produção | `core/app.js` | `data-quick-add-toggle`, `data-quick-add-close`, `data-quick-edit` | Manter |
| UI Lab | `dev/ui-lab.js` | `data-ui-lab-toggle` + `data-ui-lab-close` | Remover lab JS; usar atributos globais |

### Selects / dropdowns / multiselects

| Motor | Arquivo | Ativação |
|-------|---------|----------|
| Custom select | `cv-custom-select.js` | `select[data-cv-select]` (ver implementação) |
| Search picker | `cv-search-picker.js` | `select[data-cv-search-picker]` |
| Native enhance | `cv-select.js` | `data-cv-select` |
| Floating dropdown | `cv-floating-dropdown.js` | wrappers |
| App multiselect | `app-multiselect.js` | `data-app-multiselect` |
| Filterable multiselect | `filterable-multiselect.js` | `data-filterable-multiselect-input` |
| Oficio picker refresh | `roteiros_wizard.js` → `OficioWizard.refreshSelectPickers` | classes `data-oficio-picker-search` |

**Risco:** cinco superfícies diferentes; comportamento e acessibilidade podem divergir.

### Toggles

| Onde | Arquivo | Padrão |
|------|---------|--------|
| RG servidor | `card-toggle.js` + `field_state_toggle` template | Par `data-rg-value` |
| Motorista fixo | `viatura-motorista-fixo.js` | Par `data-mf-value` |
| Card genérico | `card-toggle.js` | `data-card-toggle` |
| Termos motorista | `cv-search-picker.js` | classes em picker |

### Chips

| Onde | JS | Nota |
|------|-----|------|
| Filtros aplicados header | Nenhum motor dedicado | HTML server-side + `filter_chip.html` |
| Chips interativos | `cv-search-picker` (driver chip, term controls) | Lógica no picker, não chip global |

### Máscaras

| Onde | Arquivo | Cobertura |
|------|---------|-----------|
| Global | `masks.js` | `input[data-mask]` no DOMContentLoaded |
| Protocolo wizard | `roteiros_wizard.js` | `#id_protocolo` hardcoded + `data-mask` implícito via classe? (só protocolo) |

**Gap:** trechos gerados dinamicamente, quick add fields após open — **não re-aplicam máscara** sem `MutationObserver` ou `initMasks(container)`.

### Wizards

| Peça | Arquivo | Função |
|------|---------|--------|
| Autosave | `autosave.js` | PATCH-like POST com snapshots |
| Glance/resumo | `roteiros_wizard.js` | Sticky header ofício etapa 1 |
| Transporte | `oficios-transporte.js` | Viatura/motorista |
| Justificativa | `oficios-justificativa-wizard.js` | — |
| Documentos | `oficios-documentos-inline.js` | Fetch status docs |
| Stepper | HTML only | Sem JS de steps |

**Risco autosave:** `shouldCreate` / validators por modelo; campos vazios não devem criar objeto (validator roteiro implementado).

### Autosave

- `window.AppAutosave`, `AppAutosaveSnapshots`, `AppAutosaveValidators`
- Modelos: `roteiro` (em `index.js`)
- Evento `autosave:created` para redirect novo → editar

### Botões / ações

- Documentais: `wizard_form_actions` + `cv-btn` (template)
- Step tempo trecho: botões ±15 min no `index.js` (delegação click)

### Modais

- Quick add panel (não modal overlay)
- PDF viewers: `assinatura-pdf.js`, `documentos-pdf-viewer.js`

### Outros

- `configuracoes.js` — ViaCEP fetch
- `theme-*` — tema global

---

## 5. Roteiros × Ofícios — relatório específico

### JS usado em Roteiros (formulário avulso)

`roteiro_form_page.html` carrega:

- Leaflet (CDN)
- `roteiros_wizard.js`
- `autosave.js`
- `roteiros.js` → `pages/roteiros/editor/index.js`
- `roteiros-map.js`

### JS usado em Rotas dentro do Ofício

`oficios/wizard_roteiro.html` carrega **o mesmo stack**:

- Mesmos 5 scripts acima
- Template embed `_roteiro_editor.html` + `mapa_rota.html`
- `initialTrechosData` via json_script (ofício)

### Diferenças encontradas

| Aspecto | Roteiro avulso | Ofício wizard roteiro |
|---------|----------------|----------------------|
| Form id | `roteiro-editor-form` | Mesmo embed |
| API calcular (persistido) | `data-api-calcular-rota-url` | Igual (atributos no form) |
| API preview | `data-api-calcular-rota-preview-url` | Igual |
| Mapa inicial | `roteiro-mapa-inicial` json_script | + `initialTrechosData` no ofício |
| Autosave model | `roteiro` | `roteiro` (mesmo) |
| Glance ofício | Não | `roteiros_wizard.js` em outras etapas |
| Selector evento | `roteiros:route-state-changed` | Mesmo (mapa escuta) |

### Integração mapa ↔ editor

`roteiros-map.js` **delega** para `window.RoteirosEditor` quando existe:

- `buildRoutePreviewPayload()`
- `applyRoutePreviewResult()`
- `getPreviewEndpointUrl()`
- `canCalculateRoutePreview()`

Isso **reduz** divergência de resultado, mas mantém **duas implementações** de UI mapa (loading, errors, botões `btn-calcular-rota-mapa`).

### Endpoints (atributos data- no form)

- `data-api-calcular-rota-url` — rota persistida (POST JSON `{ roteiro_id, force }`)
- `data-api-calcular-rota-preview-url` — preview sem id (payload montado no cliente)
- `data-url-trechos-estimar` — estimativa por par origem/destino cidades

### Bugs prováveis

1. **Correção em um arquivo sem o outro** (só mapa ou só cards).
2. **Módulos ES vazios** induzem manutenção errada.
3. **IDs hardcoded** (`trechos-gerados-container`, `id_origem_cidade`, etc.) impedem reuso em outras telas.
4. **Loop diário** desativa mapa em ambos — lógica duplicada `isLoopModeActive` / `isDailyRoundTripActive`.

### Proposta de motor único

```
static/js/
  core/http.js          # fetchJson, csrf, readJsonResponse
  modules/routes/
    calculator.js       # preview + persist + estimate
    trechos-renderer.js # buildTrechoCard, recalcCard, state maps
    diarias.js          # calculateDiarias
  modules/route-map.js  # Leaflet layer only
```

**Bridge temporário:** `window.RoteirosEditor` vira fachada fina sobre `modules/routes/*`.

### Plano de migração por etapas

1. Extrair `core/http.js` + trocar fetchs em mapa, autosave, configuracoes.
2. Extrair `applyRoutePreviewResult` / `buildRoutePreviewPayload` para `calculator.js`; mapa só desenha.
3. Mover `renderTrechos` + estimar para `trechos-renderer.js`; `index.js` só orquestra listeners.
4. Testes manuais: roteiro avulso e ofício mesma ordem destinos — comparar km/tempos/trechos.
5. Remover duplicação de funções loop/bate-volta para um `loop-mode.js`.

---

## 6. Motor único de filtros simples

### Nome sugerido

`static/js/components/filter-engine.js` (evoluir `realtime-filters.js`).

### API por data attributes

| Atributo | Elemento | Comportamento |
|----------|----------|---------------|
| `data-cv-realtime-filter-scope` | Container raiz | Escopo de filtragem |
| `data-cv-filter="search"` | input text/search | Normaliza texto, debounce 250ms |
| `data-cv-filter="status"` | select | Match exato `data-status-value` no item |
| `data-cv-filter-item` | item filtrável | `hidden=true` quando não match |
| `data-search-text` | item | Texto indexado (preferível a textContent) |
| `data-status-value` | item | Valor para filtro status |
| `data-cv-empty-state` | bloco | Exibe quando 0 resultados |
| `data-cv-results-count` | span | Contador opcional |
| `data-cv-filter-clear` | botão/link | Limpa filtros (preventDefault) |

### HTML esperado (lista)

```html
<div data-cv-realtime-filter-scope>
  <input data-cv-filter="search" name="q" />
  <select data-cv-filter="status">...</select>
  <div data-cv-list>
    <article data-cv-filter-item data-search-text="..." data-status-value="ativo">...</article>
  </div>
  <div data-cv-empty-state hidden>Nenhum resultado</div>
</div>
```

### Comportamentos

- Idempotente: `init(scope)` re-scan opcional.
- Funciona com `hidden` em itens (nativo).
- Não depende de IDs de página.
- Extensível: `data-cv-filter="tags"` no futuro.

### Aplicação por página

| Página | Já usa? | Ação |
|--------|---------|------|
| servidores, viaturas | `list_page_standard` | OK |
| cargos, unidades, combustíveis | `list_page_quick_add` | OK (busca no header) |
| ofícios, roteiros cards | `list_page_cards` | Garantir `data-cv-filter-item` em cada card |
| termos, justificativas | verificar scope | Adicionar scope + items |

### Plano de migração

1. Renomear/exportar `CVFilterEngine` além de `CVRealtimeFilters`.
2. Auditar cards: `main_list_card.html` inclui atributos nos presenters.
3. Remover filtros server-only onde UX pedir instantâneo.
4. Teste: busca + status + limpar + empty state.

---

## 7. Motor único de rotas/trechos

### Responsabilidades

| Camada | Responsabilidade |
|--------|------------------|
| `route-calculator` | HTTP preview, persist, estimate; normalização erros |
| `trechos-ui` | Render cards, merge state, recalc times, signatures |
| `route-map` | Leaflet draw, fit bounds, stale hint |
| `loop-mode` | Bate-volta diário trechos sintéticos |

### Configurável por página (data-attributes no form)

- `data-api-calcular-rota-preview-url`
- `data-api-calcular-rota-url`
- `data-url-trechos-estimar`
- `data-api-cidades-url` (template com `__ID__`)
- `data-api-diarias-url`

### Payload

- Preview: `{ origem_cidade_id, destinos: [{uuid, cidade_id}], retorno_cidade_id, incluir_retorno, modo }`
- Persist: `{ roteiro_id, force_recalculate? }`
- Estimate: `{ origem_cidade_id, destino_cidade_id }`

### Tratamento de erro

- `readJsonResponse` padronizado (já em `index.js`).
- UI: `[data-route-error]`, `[data-route-loading]` por escopo.

### Loading

- Atributos `data-loading="true"` no form desabilitam calcular.

### Integração

- Ofício e roteiro compartilham mesmo módulo; diferença só em `roteiro_id` presente ou não.

---

## 8. Motor único de máscaras

### Campos cobertos hoje

`upper`, `cpf`, `rg`, `placa`, `cep`, `telefone`, `protocolo` via `data-mask`.

### API proposta

```html
<input data-mask="cpf" data-mask-on-input />
```

```js
MaskEngine.init(root = document);
MaskEngine.scan(root); // querySelectorAll input[data-mask]
```

### Reabrir / editar

- Chamar `scan(panel)` ao abrir quick add (`core/app.js` hook).
- `MutationObserver` opcional no form (baixo custo).

### Riscos

Máscara em valor salvo vs exibido (backend normaliza) — manter testes de submit.

---

## 9. Motor único de selects/dropdowns

### Hoje

| Componente | Inicialização |
|-----------|---------------|
| `cv-custom-select.js` | auto no load |
| `cv-search-picker.js` | auto no load |
| `cv-select.js` | dropdowns |
| `cv-floating-dropdown.js` | ? |
| `app-multiselect.js` | boot explícito página |
| `filterable-multiselect.js` | auto input específico |

### Deveria existir

```js
// components/fields-init.js
initAllFields(root) {
  initCustomSelects(root);
  initSearchPickers(root);
  initCvSelects(root);
  initAppMultiselects(root);
}
```

Chamado em `DOMContentLoaded` e após `quick-add` open / AJAX partial load.

### Plano de migração

1. Documentar matriz qual widget usar (`data-cv-search-picker` vs `data-cv-select`).
2. Deprecar `filterable-multiselect` se não usado.
3. Unificar `OficioWizard.refreshSelectPickers` com `initAllFields`.
4. UI Lab: remover scripts duplicados no `extra_js`.

---

## 10. Motor único de toggles/chips

### Toggles hoje

- `card-toggle.js` — RG + card toggle
- `viatura-motorista-fixo.js` — motorista
- `field_state_toggle.html` — par UI Lab

**Proposta:** `static/js/components/state-toggle.js`

```html
<div data-cv-state-toggle="rg" data-cv-state-field="sem_rg">
  <button data-cv-state-option value="nao" data-variant="danger">...</button>
  <button data-cv-state-option value="possui" data-variant="success">...</button>
</div>
```

Hidden input: `#id_sem_rg` / `#id_tem_motorista_fixo` — engine sincroniza checked + classes.

### Chips

- Status/filtro: server-rendered `chip.html`.
- Picker chips: dentro `cv-search-picker.js`.
- **Sem** motor global de remoção de chip de filtro client-side (limpar filtros é reload ou `data-cv-filter-clear`).

---

## 11. Plano de refatoração JS por fases

### Fase 1 — Fundação (baixo risco)

| Tarefa | Arquivos | Páginas | Aceite | Testes |
|--------|----------|---------|--------|--------|
| `core/http.js` | novo | todos fetch | CSRF único | smoke fetch |
| Quick Add lab → global | remover dup ui-lab.js | UI Lab | toggle abre/fecha | manual |
| UI Lab scripts dedup | base.html | lab | sem 404 nav | network |
| Documentar `data-cv-*` filtros | docs | listas | — | busca listas |

### Fase 2 — Máscaras + toggles

| Tarefa | Arquivos | Aceite |
|--------|----------|--------|
| `MaskEngine.scan(root)` | masks.js | campos dinâmicos mascarados |
| `StateToggle` unificado | state-toggle.js, remover dup motorista JS | RG + viatura iguais |

### Fase 3 — Selects

| Tarefa | Arquivos | Aceite |
|--------|----------|--------|
| `fields-init.js` | novo | pickers após quick add |
| Deprecar multiselect legado | grep uso | menos JS |

### Fase 4 — Filtros

| Tarefa | Aceite |
|--------|--------|
| Estender filter-engine a cards ofícios/roteiros | filtro instantâneo em todas listas |
| Contador/empty padronizados | UX lista |

### Fase 5 — Rotas/trechos (alto risco)

| Tarefa | Arquivos | Aceite |
|--------|----------|--------|
| Extrair calculator | modules/routes/ | paridade km/tempo |
| Extrair trechos-ui | modules/routes/ | trechos iguais |
| Slim index.js | editor/index.js | < 200 linhas orquestração |
| Mapa thin | route-map.js | mapa igual |

**Testes manuais:** roteiro novo, ofício roteiro, bate-volta, retorno sede, recalcular mapa, autosave roteiro.

### Fase 6 — Wizard/autosave

| Tarefa | Aceite |
|--------|--------|
| Extrair glance ofício | wizard-glance.js |
| Autosave hooks tipados | menos window globals |
| Testes payload vazio | não cria rascunho vazio |

---

## 12. Checklist de problemas

| Item | Situação |
|------|----------|
| Inline JS | OK em produção |
| Duplicação | Crítica (rotas, quick add lab, CSRF, pickers) |
| IDs hardcoded | Crítica em editor + mapa + ofícios transporte |
| CSRF centralizado | Ausente |
| Fetch duplicado | Parcial (padrões similares) |
| Listeners duplicados | Possível se scripts carregados 2x no lab |
| Guarda null | Parcial (muitos early return) |
| Loading | Mapa + autosave; incompleto em fetchs página |
| Erro visual | Mapa sim; outras páginas variável |
| Empty state | Filtro sim (`data-cv-empty-state`) |
| Documentação JS | Fraca (comentários pontuais em realtime-filters, autosave) |

---

## 13. Recomendações finais

1. **Não refatorar `index.js` antes de `core/http.js` e testes de paridade** — ordem importa.
2. **Tratar `roteiros-map.js` + `RoteirosEditor` como um único produto** chamado "domínio rota".
3. **Manter `realtime-filters.js`** como base do filter-engine — já alinhado ao UI Lab.
4. **Congelar novos `window.*`** — usar módulos ES ou namespace `CV.*`.
5. **Quebrar stubs** `pages/roteiros/editor/*.js` — implementar ou apagar para não confundir.
6. **Próxima prompt recomendada:** Fase 1 + início Fase 5 (extrair `core/http.js` + `route-calculator.js` sem mover UI trechos ainda).

---

## 14. Verificações executadas

| Comando | Resultado |
|---------|-----------|
| `python manage.py check` | OK (0 issues) |
| `python manage.py test` | Não executado nesta fase (auditoria only) |

---

## 15. Microcorreções nesta fase

**Nenhuma alteração de código** — apenas este relatório, conforme escopo da auditoria.

---

*Fim do relatório.*
