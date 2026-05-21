# Relatório JS Fase 3 — Fields Init

**Data:** 2026-05-20  
**Branch:** `refactor/js-fields-init-fase3`  
**Base:** `refactor/js-masks-toggles-fase2`

---

## 1. Resumo executivo

### O que foi feito

- Criado `static/js/components/fields-init.js` — orquestrador `window.CV.fields`.
- Motores existentes ganharam `init(root)` com escopo em subárvore (mudança mínima).
- `base.html` carrega `fields-init.js` após `cv-select.js`.
- Quick Add usa `CV.fields.init(panel)` em vez de só máscaras.
- `OficioWizard.refreshSelectPickers` delega para `CV.fields.init`.
- `filterable-multiselect.js` ganhou idempotência e API `init(root)`.
- Documentação em `docs/DATA_ATTRIBUTES_JS.md`.

### O que não foi mexido

- `pages/roteiros/editor/index.js`, `roteiros-map.js`.
- Motor de rotas/trechos.
- CSS/visual dos selects.
- Remoção de motores legados.
- `app-motorista-picker.js`, `oficios-transporte.js` (sem alteração comprovada segura).

### Riscos preservados

- Idempotência mantida nos motores (marcadores existentes + `data-cv-select-bound`).
- Falha em um motor não quebra a página (`try/catch` discreto).
- Scripts de página (`app-multiselect` em `extra_js`) continuam com boot próprio.

---

## 2. Inventário de motores existentes

| Motor | Arquivo | Seletor | API anterior | API nova/adaptada | Idempotência | Status |
|-------|---------|---------|--------------|-------------------|--------------|--------|
| Custom Select | `cv-custom-select.js` | `[data-cv-select]` | `CvCustomSelect.init()` doc only | `init(root)`, `CV.customSelect` | `_cvSelect` + `data-cv-select-bound` | Adaptado |
| Search Picker | `cv-search-picker.js` | `select[data-cv-search-picker]` | `boot()` | `init(root)`, `CV.searchPicker` | `data-cv-search-picker-ready` | Adaptado |
| Dropdowns | `cv-select.js` | `[data-cv-dropdown]`, `[data-cv-filter-dropdown]` | `CvSelect.init()` | `init(root)`, `CV.dropdowns` | `_cvDropdownReady` | Adaptado |
| App Multiselect | `app-multiselect.js` | `select[data-app-multiselect]` | `boot()` | `init(root)`, `CV.multiselect` | `data-app-multiselect-ready` | Adaptado |
| Filterable MS | `filterable-multiselect.js` | `input[data-filterable-multiselect-input]` | `boot()` só document | `init(root)`, `CV.filterableMultiselect` | `data-filterable-multiselect-bound` | Adaptado |
| Floating dropdown | `cv-floating-dropdown.js` | — | `CvFloatingDropdown.attach` | Sem `init` (usado pelo picker) | N/A | Inalterado |
| Masks | `masks.js` | `input[data-mask]` | `MaskEngine.scan` | Via `CV.fields` | `data-mask-bound` | Integrado |
| State toggle | `state-toggle.js` | `data-cv-state-toggle` | `CV.stateToggle.init` | Via `CV.fields` | `data-cv-state-bound` | Integrado |

**OficioSelectPicker:** referenciado em `roteiros_wizard.js` mas **não existe** no repositório — `refreshSelectPickers` agora usa `CV.fields.init`.

**Roteiro editor:** selects nativos com `data-oficio-picker-search` — não são `data-cv-search-picker`; comportamento inalterado.

---

## 3. Fields Init

| Item | Detalhe |
|------|---------|
| Arquivo | `static/js/components/fields-init.js` |
| API | `CV.fields.init`, `initSelects`, `initSearchPickers`, `initDropdowns`, `initMultiselects` |
| Alias | `window.CV.initFields` |
| Ordem | masks → stateToggle → customSelect → searchPicker → dropdowns → multiselect → filterableMultiselect |
| Evento | `cv:fields:init` |
| Debug | `window.DEBUG_CV_FIELDS = true` para warnings no console |
| Boot | `DOMContentLoaded` → `init(document)` (passagem idempotente pós-motores) |

---

## 4. Integrações feitas

| Local | Antes | Depois | Risco | Status |
|-------|-------|--------|-------|--------|
| `base.html` | sem fields-init | `fields-init.js` após cv-select | Baixo | OK |
| `core/app.js` | `MaskEngine.scan(panel)` | `CV.fields.init(panel)` | Baixo | OK |
| `roteiros_wizard.js` | `OficioSelectPicker.refresh` | `CV.fields.init` + fallbacks | Baixo | OK |
| Motores | `init` só em document | `init(root)` escopado | Baixo | OK |

---

## 5. Integrações não feitas

| Local | Motivo | Fase |
|-------|--------|------|
| `oficios-transporte.js` | Lógica viatura/motorista específica; sem API clara de re-init | Auditar Fase 4 |
| `app-motorista-picker.js` | Script de página isolado | Fase 4 |
| `oficios-dados-viajantes.js` | Multiselect já boot em `extra_js` | OK como está |
| `filterable-multiselect` em base | Não carregado globalmente (legado) | Remover ou incluir se voltar |
| Roteiro `data-oficio-picker-search` | Não é search-picker CV | Unificação futura |

---

## 6. UI Lab

| Tela | Verificação |
|------|-------------|
| `/dev/ui-lab/fields/` | Custom selects `[data-cv-select]` — init idempotente |
| `/dev/ui-lab/selects-filters/` | Selects, pickers, dropdowns — sem dup em reload |
| structures/lists/headers | Quick Add + `CV.fields.init(panel)` |

**Risco de duplicação:** baixo — marcadores por motor. Smoke manual recomendado no console.

---

## 7. Testes

| Comando | Resultado |
|---------|-----------|
| `python manage.py check` | **OK** — 0 issues |
| `python manage.py test` | **428 testes** — **6 failures, 8 errors, 1 skipped** (pré-existentes; cadastros/wizard) |

Nenhuma falha referenciou `fields-init.js` ou motores de select.

---

## 8. Arquivos alterados

- `static/js/components/fields-init.js` (novo)
- `static/js/components/cv-custom-select.js`
- `static/js/components/cv-search-picker.js`
- `static/js/cv-select.js`
- `static/js/components/app-multiselect.js`
- `static/js/components/filterable-multiselect.js`
- `static/js/core/app.js`
- `static/js/roteiros_wizard.js`
- `templates/base.html`
- `docs/DATA_ATTRIBUTES_JS.md`
- `docs/RELATORIO_JS_FASE3_FIELDS_INIT.md`

---

## 9. Pendências

- Incluir `filterable-multiselect.js` em `base.html` apenas se voltar a ser usado.
- Unificar `data-oficio-picker-search` com search-picker (domínio roteiro).
- Fase 4: estender `realtime-filters` / filter-engine global.
- Fase 5: motor rotas/trechos.

---

*Fim do relatório.*
