# Relatório JS Fase 2 — Máscaras e Toggles

**Data:** 2026-05-20  
**Branch:** `refactor/js-masks-toggles-fase2`  
**Base:** `audit/ui-lab-js-consistencia` (Fase 1 concluída)

---

## 1. Resumo executivo

### O que foi feito

- `MaskEngine` com `scan`, `apply`, `format` e bind idempotente (`data-mask-bound`).
- `MaskEngine.scan(panel)` integrado ao Quick Add em `core/app.js`.
- Motor global `CV.stateToggle` com modos grupo de opções e binário (checkbox + botão).
- Migração controlada: servidores (RG) e viaturas (motorista fixo) usam `data-cv-state-toggle` + adaptadores de domínio.
- `state-toggle.js` incluído em `base.html` (antes de `card-toggle.js`).
- Documentação atualizada em `docs/DATA_ATTRIBUTES_JS.md`.

### O que não foi mexido

- `pages/roteiros/editor/index.js`, `roteiros-map.js` (rotas/trechos).
- Endpoints, payloads, models, migrations.
- UI/CSS novos.
- Unificação de selects/pickers (Fase 3).
- Remoção de `card-toggle` para `[data-card-toggle]` genérico.

### Riscos preservados

- Lógica de negócio RG (travar campo, limpar valor) permanece em `card-toggle.js`.
- Painel motoristas viatura permanece em `viatura-motorista-fixo.js`.
- Fallback: motores não quebram se API ausente.

---

## 2. Máscaras

| Item | Detalhe |
|------|---------|
| Arquivo | `static/js/components/masks.js` |
| API | `window.MaskEngine`, `window.CV.masks` |
| Máscaras | `upper`, `cpf`, `rg`, `placa`, `cep`, `telefone`, `protocolo` |
| Re-scan | `scan(root)` — `input[data-mask]`, `textarea[data-mask]` |
| Idempotência | `data-mask-bound="true"` |
| Disabled/readonly | Ignorados em `apply`/`bind` |
| DOMContentLoaded | `scan(document)` mantido |

Compatibilidade: mesmas funções de formatação; valor existente reformatado ao bind (não duplica caracteres de máscara).

---

## 3. Quick Add

| Onde | Comportamento |
|------|---------------|
| `core/app.js` → `openPanel()` | `scanPanelMasks(panel)` após `is-open` |
| `core/app.js` → quick edit | `scanPanelMasks(panel)` ao preencher campos |

Telas afetadas (quando painel tiver `data-mask`): cargos, unidades, combustíveis (`list_page_quick_add`). Demais listas sem máscara no painel: scan é no-op.

---

## 4. State Toggle

| Item | Detalhe |
|------|---------|
| Arquivo | `static/js/components/state-toggle.js` (novo) |
| API | `window.CV.stateToggle.init(root)`, `.update(group, value)` |
| Evento | `cv:state-toggle:change` |
| Modo binário | `data-cv-state-binary` + checkbox + `data-rg-toggle` / `data-motorista-fixo-toggle` |
| Modo opções | `[data-cv-state-option]` + `data-value` |
| Idempotência | `data-cv-state-bound` no container |

---

## 5. Migrações feitas

| Tela | Arquivo | Antes | Depois | Risco | Status |
|------|---------|-------|--------|-------|--------|
| Servidores RG | `servidores/form.html` | `data-servidor-sem-rg-form` | + `data-cv-state-toggle data-cv-state-binary` | Médio | OK |
| Servidores RG | `card-toggle.js` | click delegado `data-rg-toggle` | `stateToggle` + `applyServidorSemRgUi` | Médio | OK |
| Viaturas motorista | `viaturas/form.html` | `data-viatura-motorista-form` | + `data-cv-state-toggle data-cv-state-binary` | Médio | OK |
| Viaturas motorista | `viatura-motorista-fixo.js` | UI botão + painel | `stateToggle` + painel/clear | Médio | OK |
| Quick Add | `core/app.js` | sem máscara dinâmica | `MaskEngine.scan(panel)` | Baixo | OK |
| Global | `base.html` | masks + card-toggle | + `state-toggle.js` | Baixo | OK |

---

## 6. Migrações NÃO feitas

| Tela / item | Motivo | Fase |
|-------------|--------|------|
| `field_state_toggle` (par UI Lab) | Não existe na branch; RG usa botão único | UI + Fase 3 |
| `[data-card-toggle]` genérico | Ainda usado; sem duplicação removida | Documentar |
| Configurações CEP | `configuracoes.js` mantém máscara local + API | Opcional unificar Fase 2b |
| Ofícios / roteiro | Fora de escopo | 5–6 |
| Grupo dois botões RG (`nao`/`possui`) | Template não migrado para `data-cv-state-option` | UI Lab paridade |

---

## 7. Testes

| Comando | Resultado |
|---------|-----------|
| `python manage.py check` | **OK** — 0 issues |
| `python manage.py test` | **428 testes** — **6 failures, 8 errors, 1 skipped** (pré-existentes; cadastros unidade/cidade/CEP mock, wizard ofício) |

Nenhuma falha referenciou `masks.js`, `state-toggle.js`, `card-toggle.js` ou `viatura-motorista-fixo.js`.

### Smoke manual (checklist)

- [ ] Servidores: CPF/RG/telefone mascarados; alternar RG; reabrir edição.
- [ ] Viaturas: motorista fixo visual; painel motoristas; submit.
- [ ] Quick Add cargos/unidades/combustíveis com campo mascarado.
- [ ] Configurações: CEP.
- [ ] UI Lab Fields / Quick Add sem erro console.

---

## 8. Arquivos alterados

- `static/js/components/masks.js`
- `static/js/components/state-toggle.js` (novo)
- `static/js/components/card-toggle.js`
- `static/js/components/viatura-motorista-fixo.js`
- `static/js/core/app.js`
- `templates/base.html`
- `templates/cadastros/servidores/form.html`
- `templates/cadastros/viaturas/form.html`
- `docs/DATA_ATTRIBUTES_JS.md`
- `docs/RELATORIO_JS_FASE2_MASKS_TOGGLES.md` (este arquivo)

---

## 9. Pendências

- Migrar templates para par `data-cv-state-option` (UI Lab / servidores) quando shell estável.
- `MaskEngine.scan` após outros partials AJAX (se houver).
- Unificar CEP configurações com `MaskEngine` (opcional).
- Fase 3: `fields-init.js` para selects.

---

*Fim do relatório.*
