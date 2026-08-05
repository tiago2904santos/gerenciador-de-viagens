# Relatório Baseline Pré-Fase 5 — Rotas/Trechos

**Branch:** `stabilization/js-ui-baseline-pre-routes`  
**Base:** `refactor/js-filters-fase4` (`b8df43b`)  
**Data:** 2026-05-20

## 1. Resumo executivo

Após as Fases 1–4 (HTTP, máscaras/toggles, fields, filters), o estado geral é **estável para iniciar a Fase 5**, com ressalvas documentadas.

| Item | Resultado |
|------|-----------|
| Contrato `DATA_ATTRIBUTES_JS.md` | Coerente com código; divergências menores (ver §2) |
| `manage.py check` | OK |
| Suite Django | **428** testes, **6 failures, 8 errors, 1 skipped** — mesmo baseline pré-existente |
| Regressão JS Fases 1–4 | Não identificada nos testes nem no smoke Playwright |
| Screenshots | 9 rotas capturadas em `screenshots/baseline-pre-routes/` |
| Smoke interativo parcial | `CV.filters` (busca/empty/limpar) validado via Playwright |

**Bloqueios para Fase 5:** nenhum bloqueio técnico nos motores globais UI. Testes quebrados de cadastros (unidade/cidade/CEP) e wizard ofício permanecem **fora do escopo** desta fase.

**Riscos antes de mexer em rotas:** domínio `RoteirosEditor` / `RoteirosMap` / autosave não foi refatorado; qualquer mudança em `pages/roteiros/editor/index.js` ou `roteiros-map.js` exige reteste manual de mapa, cálculo de rota e trechos.

## 2. Contrato JS validado

| Motor | API documentada | Arquivo | Status | Observação |
|-------|-----------------|---------|--------|------------|
| HTTP | `CV.http.getCsrfToken`, `readJsonResponse`, `fetchJson` | `static/js/core/http.js` | OK | Doc não lista `getCookie` (existe no código) |
| Quick Add | `data-quick-add-toggle`, `data-quick-edit`, … | `static/js/core/app.js` | OK | Painel chama `CV.fields.init(panel)` |
| CV.filters | `init`, `update`, `clear`, `getState` | `static/js/components/realtime-filters.js` | OK | `data-cv-filter-bound`, evento `cv:filters:updated` |
| MaskEngine | `scan`, `apply`, `format` | `static/js/components/masks.js` | OK | `data-mask-bound`; alias `CV.masks` |
| CV.stateToggle | `init`, `update` | `static/js/components/state-toggle.js` | OK | `data-cv-state-bound`; legado RG/motorista |
| CV.fields | `init`, `initSelects`, … | `static/js/components/fields-init.js` | OK | Ordem documentada confere; evento `cv:fields:init` |
| customSelect | `CV.customSelect.init` | `static/js/components/cv-custom-select.js` | OK | `_cvSelect` / bound |
| searchPicker | `CV.searchPicker.init` | `static/js/components/cv-search-picker.js` | OK | `data-cv-search-picker-ready` |
| dropdowns | `CV.dropdowns.init` | `static/js/cv-select.js` | OK | `[data-cv-dropdown]`, `[data-cv-filter-dropdown]` |
| multiselect | `CV.multiselect.init` | `static/js/components/app-multiselect.js` | OK | Sob demanda em páginas wizard |
| filterableMultiselect | `CV.filterableMultiselect.init` | `static/js/components/filterable-multiselect.js` | OK | Opcional |
| Configurações CEP | `data-configuracoes-form`, `data-cep-lookup-url-template` | `templates/cadastros/configuracao/form.html`, `pages/configuracoes.js` | OK | Usa `CV.http.fetchJson` |
| Roteiro/mapa | `RoteirosEditor`, `RoteirosMap`, data-* no form | `roteiros-map.js`, editor (não unificado) | Documentado | **Não alterado nesta fase** |

**Divergências menores (doc vs código):**

1. Exemplo Quick Add em `DATA_ATTRIBUTES_JS.md` cita `MaskEngine.scan(panel)`; produção usa **`CV.fields.init(panel)`** em `core/app.js` (equivalente funcional).
2. `CV.http` expõe também `getCookie` — omitido na tabela do doc (não quebra contrato).

Nenhuma alteração de contrato foi necessária.

## 3. Testes automatizados

| Comando | Resultado | Falhas | Pré-existente? | Observações |
|---------|-----------|--------|----------------|-------------|
| `python manage.py check` | OK (0 issues) | — | — | — |
| `python manage.py test` | FAILED | 6 / 8 / 1 skip | **Sim** | 428 testes, ~43s |

**Módulos com falha/erro (inalterados em relação à Fase 4):**

| Tipo | Testes |
|------|--------|
| ERROR | CEP API mock (`test_retorna_200_com_campos_esperados`, `test_retorna_404_para_cep_nao_encontrado`) |
| ERROR | Cidades CRUD (`test_get_*`, `test_post_*` cidades) |
| ERROR | `test_cadastros_exige_login_para_usuario_anonimo` |
| FAIL | Unidades CRUD (5 testes) |
| FAIL | `test_get_novo_renderiza_wizard` (ofícios) |

**Referência a arquivos Fases 1–4 nas falhas:** apenas menção incidental em HTML renderizado do wizard (scripts carregados em `base.html`). **Nenhuma stack trace apontando** para `http.js`, `masks.js`, `state-toggle.js`, `fields-init.js`, `realtime-filters.js`, `autosave.js` ou `roteiros-map.js` como causa.

**Teste UI Lab:** `core.tests.test_ui_lab.test_ui_lab_lists_page_contains_list_patterns` — **FAIL** pré-existente (espera strings `"List Shell"` / `"Empty State"` que não estão no template atual). Não é regressão do motor de filtros.

## 4. Smoke manual

Legenda: **A** = automatizado (Playwright carga ou `_smoke_interactions.py`); **M** = checklist manual pendente nesta sessão.

| Tela | Fluxo testado | Resultado | Erros console | Observações | Bloqueia Fase 5? |
|------|---------------|-----------|---------------|-------------|------------------|
| UI Lab Lists | Carga + busca sem match + limpar | **A OK** | Nenhum | APIs globais presentes; empty state após `zzznomatch` | não |
| UI Lab Lists | Status + sem acento + tema | M | — | Status não exercitado no script | não |
| UI Lab Fields | Carga | **A OK** | Nenhum | 3 selects bound | não |
| UI Lab Fields | Máscaras/toggles interativos | M | — | — | não |
| UI Lab Selects/Filters | Carga screenshot | **A OK** | Nenhum na carga | Abrir/fechar repetido | M | não |
| Quick Add (cargos/unidades/combustíveis) | Abrir/fechar/reabrir | M | — | Página carrega (screenshot cargos) | não |
| Servidores lista | Busca/contador/empty | M | — | Template com `data-cv-realtime-filter-scope` | não |
| Servidores form | Máscaras + toggle RG | M | — | — | não |
| Viaturas lista/form | Busca + motorista fixo | M | — | — | não |
| Configurações | CEP + máscaras | M | — | Screenshot OK; testes CEP com ERROR na suite | não* |
| Ofícios index | Busca/status/cards/ações | M parcial | Nenhum na carga | Screenshot OK | não |
| Roteiros index | Busca/status/cards | M parcial | Nenhum na carga | Screenshot OK | não |
| Roteiro editor | Mapa/rota/trechos/autosave | M | — | **Baseline obrigatório antes de editar código Fase 5** | não** |
| Ofício wizard | Viajantes/transporte/roteiro embutido | M | — | `test_get_novo_renderiza_wizard` já falha na suite | não** |
| Tema claro/escuro | 4 telas | M | — | — | não |

\* Falhas de teste CEP são de mock/backend, não de JS de máscara.  
\*\* Risco de domínio, não bloqueio dos motores globais.

## 5. Filtros/listas

| Verificação | Resultado |
|-------------|-----------|
| `CV.filters` exposto | OK |
| Busca sem resultado → empty state | OK (UI Lab, 4 itens → 0 visíveis) |
| Limpar filtros restaura itens | OK (4/4 visíveis) |
| `cv:filters:updated` | Implementado (não assertado no script) |
| Páginas com scope em produção | cargos, unidades, combustíveis, servidores, viaturas, cidades, estados, ofícios, roteiros |

**Pendências:** smoke de acento/status em cadastros e ofícios (manual); contador visível só após filtro em algumas telas.

## 6. Fields/selects/toggles/masks

| Motor | Smoke | Pendências |
|-------|-------|------------|
| `CV.fields` | Carga UI Lab fields OK | Repetir abertura Quick Add / wizard |
| `MaskEngine` | API presente na lista UI Lab | Form servidores/viaturas (manual) |
| `CV.stateToggle` | API presente | RG / motorista fixo (manual) |
| Selects/pickers | Screenshot selects-filters | Toggle repetido (manual) |

**Integração:** `CV.fields.init` **não** chama `CV.filters.init` (conforme doc) — evita duplicação.

## 7. Roteiros baseline

| Área | Estado nesta fase |
|------|-------------------|
| Editor | **Não testado automaticamente** — sem alteração de código |
| Mapa / calcular rota | Contrato `data-api-*` presente em `_roteiro_editor.html` |
| Trechos | Renderização server-side inalterada |
| Autosave | `autosave.js` + `CV.http` — suite `roteiros.tests.test_autosave` não listada nas falhas atuais |
| Console | Nenhum erro na carga das páginas index capturadas |

**Riscos:** alta complexidade e acoplamento DOM/API; Fase 5 deve manter snapshots e este baseline visual.

## 8. Ofício wizard baseline

| Etapa | Estado |
|-------|--------|
| Dados viajantes | Não exercitado no Playwright desta fase |
| Transporte | Idem |
| Roteiro embutido | Idem |
| Console | Scripts globais carregam no HTML de falha do teste wizard (sem erro JS reportado) |

**Risco:** `test_get_novo_renderiza_wizard` falha na suite — investigar separadamente; não bloqueia refatoração de rotas se escopo Fase 5 for só editor/mapa.

## 9. Screenshots

**Executado** com Playwright existente (`screenshots/baseline-pre-routes/_capturar_baseline.py`).

| Arquivo | Rota |
|---------|------|
| `ui-lab-lists.png` | `/dev/ui-lab/lists/` |
| `ui-lab-fields.png` | `/dev/ui-lab/fields/` |
| `ui-lab-selects-filters.png` | `/dev/ui-lab/selects-filters/` |
| `cadastros-cargos.png` | `/cadastros/cargos/` |
| `cadastros-servidores.png` | `/cadastros/servidores/` |
| `cadastros-viaturas.png` | `/cadastros/viaturas/` |
| `oficios-index.png` | `/oficios/` |
| `roteiros-index.png` | `/roteiros/` |
| `cadastros-configuracao.png` | `/cadastros/configuracao/` |

Relatórios JSON: `_baseline_report.json`, `_smoke_interactions.json`.

Tema escuro: **não** capturado automaticamente — ver README da pasta.

## 10. Decisão

**B. Liberado para Fase 5 com ressalvas**

Motivos:

- Motores globais (Fases 1–4) validados por contrato, check Django, smoke Playwright (APIs + filtros) e screenshots sem erros de console.
- Suite de regressão **não piorou** (mesmos 6F/8E/1S).
- Domínio roteiro/wizard exige baseline manual complementar **antes de cada entrega** na Fase 5, não bloqueia abertura da fase.

Não é **A** pleno porque smoke manual completo (12 itens) e tema escuro não foram 100% executados por humano. Não é **C** porque não há regressão nova nos JS refatorados.

## 11. Pendências antes da Fase 5

### Obrigatórias (antes de merge crítico em rotas)

1. Smoke manual do **editor de roteiro** (mapa, calcular rota, trechos, autosave).
2. Confirmar **ofício wizard** (transporte + roteiro embutido) após qualquer touch em JS compartilhado.

### Recomendadas

1. Completar checklist §4 (Quick Add, servidores/viaturas forms, tema escuro).
2. Capturar screenshots tema escuro em `screenshots/baseline-pre-routes/`.
3. Corrigir `test_ui_lab_lists_page_contains_list_patterns` (expectativas desatualizadas) — fase de testes separada.

### Podem ficar para depois

1. Corrigir suite unidades/cidades/CEP mock.
2. Contador de filtros visível por padrão em ofícios/roteiros.

## 12. Próxima prompt recomendada

```
Fase 5 — Refatorar motor de rotas/trechos (somente domínio):

- Escopo: static/js/pages/roteiros/editor/index.js e static/js/roteiros-map.js
- Manter: endpoints, payloads, data-api-* no #roteiro-editor-form
- Baseline: comparar com screenshots/baseline-pre-routes/ e RELATORIO_BASELINE_PRE_ROTAS.md
- Após cada passo: smoke mapa + calcular rota + trechos + autosave + wizard ofício (roteiro embutido)
- Não alterar CV.filters, CV.fields, masks, stateToggle salvo bug bloqueante
```

---

## Artefatos desta fase

| Path | Descrição |
|------|-----------|
| `docs/RELATORIO_BASELINE_PRE_ROTAS.md` | Este relatório |
| `screenshots/baseline-pre-routes/*.png` | Baseline visual |
| `screenshots/baseline-pre-routes/_capturar_baseline.py` | Captura PNG |
| `screenshots/baseline-pre-routes/_smoke_interactions.py` | Smoke CV.filters/APIs |
| `screenshots/baseline-pre-routes/README.md` | Instruções de captura |
