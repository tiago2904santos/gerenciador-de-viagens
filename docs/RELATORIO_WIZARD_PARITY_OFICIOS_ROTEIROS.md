# Relatório Wizard Parity — Ofícios e Roteiros

## 1. Resumo executivo

- **Migrado:** shell visual dos wizards de Ofícios e Roteiros para o modelo **UI Lab → Structures → Wizard** (`page-shell--wizard`, `header_stack_back_action`, `page-stepper`, `main-form-panel--stack`, `cv-wizard-section-stack`, `footer-actions`).
- **Não migrado:** lógica de rotas/trechos, JS funcional (`roteiros/editor/index.js`, `roteiros-map.js`), endpoints, models, validações, ordem de steps.
- **Riscos preservados:** `#roteiro-editor-form`, todos `data-api-*`, autosave, `OficioWizard` / `CV.fields`, submits (`name`/`value` de `action`), formulário embutido na etapa roteiro (sem form aninhado inválido).
- **Fase 5 funcional:** **B — Liberado com ressalvas** (paridade estrutural concluída; smoke visual manual e screenshots dedicados pendentes se o servidor não estiver ativo).

---

## 2. Modelo UI Lab Wizard

| Elemento Wizard UI Lab | Arquivo/component | Classe | Token | Ofício? | Roteiro? |
|------------------------|-------------------|--------|-------|---------|----------|
| Shell | `page-shell.css` | `page-shell page-shell--wizard` | `--surface-page-shell` | Sim | Sim |
| Header band + rail | `header_stack_back_action.html` | `page-header-stack`, `page-header-band`, `page-header-rail` | chips, radius shell | Sim | Sim |
| Status chip | header include | `page-header-status-chip--draft/active` | tema claro/escuro | Sim | Não (avulso) |
| Stepper | `page_stepper.html` | `page-stepper page-stepper--horizontal` | `--surface-stepper`, `--border-stepper` | Sim | Não (roteiro avulso) |
| Painel principal | `page-shell.css` | `main-form-panel main-form-panel--stack` | transparente, `--cv-wizard-section-stack-gap` | Sim | Sim |
| Stack de cards | `page-shell.css` | `cv-wizard-section-stack` | `--cv-wizard-section-stack-gap` | Sim | Sim |
| Card de seção | `page-shell.css` / bridge | `cv-wizard-section-card` | `--cv-wizard-section-*` | Bridge CSS | Bridge CSS |
| Footer | `footer_actions` pattern | `footer-actions`, `footer-actions__secondary/primary` | `--surface-footer-actions` | Sim | Sim |
| Campos | `forms.css` | `field-grid`, `field-size-*` | `--field-grid-gap` | Sim | Sim |

**Components globais criados/ajustados**

- `templates/components/ui/navigation/page_stepper.html` (novo)
- `templates/components/ui/layouts/wizard_section_card.html` (novo, reutilizável)
- `templates/components/ui/layouts/wizard_page.html` (ampliado com stepper opcional)
- UI Lab `structures.html` passou a incluir `page_stepper.html`

---

## 3. Roteiros

| Template | Antes | Depois | Components | Legado preservado | Risco | Status |
|----------|-------|--------|------------|-------------------|-------|--------|
| `roteiro_form_page.html` | `page-shell--wizard` + `app-form-shell` solto | `main-form-panel--stack` + `cv-wizard-section-stack` | header_stack_back_action | `app-page-shell--wizard` no editor | Baixo | OK |
| `_roteiro_editor.html` | `card`/`card-section` wrapper | form direto no stack; intro como card wizard | — | `app-page-shell`, `roteiro-editor`, todos `data-*` | Baixo | OK |
| `partials/roteiro/actions.html` | `div.roteiro-editor__actions` | `footer.footer-actions` + grupos | footer-actions | classes `roteiro-editor__actions`, submits | Baixo | OK |

---

## 4. Ofícios

| Template/step | Antes | Depois | Components | Legado preservado | Risco | Status |
|---------------|-------|--------|------------|-------------------|-------|--------|
| `wizard_base.html` | `app-page oficio-wizard`, header legado, `oficio-stepper` | `page-shell--wizard` + header global + `page-stepper` | header_stack, page_stepper, stack | `oficio-wizard`, `app-wizard`, `oficio-wizard__*` | Baixo | OK |
| `wizard_roteiro.html` | shell duplicado | `extends wizard_base`, `wizard_use_outer_form=False` | mesmo shell | `#roteiro-editor-form` único | Médio | OK |
| `wizard_assinaturas.html` | shell legado | `extends wizard_base` | header + stepper | centralizadora intacta | Baixo | OK |
| `partials/wizard_actions.html` | `div.form-actions` | `footer.footer-actions` + cv-btn bridge | footer-actions | `name`/`value` submits, links DOCX/PDF | Baixo | OK |
| Steps 1–6 conteúdo | `form-section` | bridge CSS → aparência `cv-wizard-section-card` | — | markup interno inalterado | Baixo | OK |

**Presenter:** `apresentar_oficio_wizard_page_steps()` adapta steps para `page_stepper`; header com `description` (Etapa N de 6) e `status_label` no chip.

---

## 5. Components globais alterados

| Component | Alteração | Motivo | Páginas |
|-----------|-----------|--------|---------|
| `page_stepper.html` | Novo | Paridade UI Lab + links nas etapas | Ofícios, UI Lab |
| `wizard_section_card.html` | Novo | Card genérico de seção | Futuro / includes |
| `wizard_page.html` | Stepper + painel opcional | Shell reutilizável | Lab / futuras telas |
| `wizard_stepper.html` (ofício) | Delega a `page_stepper` | Compatibilidade | — |

---

## 6. CSS/tokens

| Arquivo | Alteração |
|---------|-----------|
| `static/css/page-shell.css` | Footer no form do stack; bridge `.form-section.app-form-section` e `.roteiro-editor__section` → tokens `cv-wizard-section-*` |

**Compatibilidades temporárias (documentadas):** `oficio-wizard`, `app-page`, `app-page-shell--wizard`, `oficio-wizard__actions`, `btn btn-*` junto com `cv-btn` e `footer-actions`.

---

## 7. Contrato DOM/JS preservado

| ID / data-attribute / container | Uso | Preservado? |
|---------------------------------|-----|-------------|
| `#roteiro-editor-form` | RoteirosEditor, autosave | Sim |
| `data-api-calcular-rota-url` | Mapa / cálculo | Sim |
| `data-api-calcular-rota-preview-url` | Preview | Sim |
| `data-url-trechos-estimar` | Trechos | Sim |
| `data-api-cidades-url` / `data-api-diarias-url` | APIs | Sim |
| `data-autosave-*` | Autosave | Sim |
| `name="action"` nos botões wizard | Navegação POST | Sim |
| `data-app-multiselect`, `CV.fields` | Ofício step 1 | Sim |
| Containers destinos/trechos/mapa | Domain partials | Sim |

---

## 8. Botões/actions

- **Migrados:** rodapés com `footer-actions` + classes `cv-btn` em paralelo aos `btn btn-*`.
- **Mantidos legados:** `btn`, `app-btn`, `name`/`value`/`type`/`href` inalterados.
- **Pendência visual:** substituir totalmente `btn` por `components/ui/buttons/button.html` quando testes/smoke confirmarem paridade.

---

## 9. Screenshots

Pasta prevista: `screenshots/wizard-parity-oficios-roteiros/`

**Não gerados nesta sessão** (exige `runserver` + Playwright com dados de demo). Comandos de referência:

```bash
python manage.py runserver
python screenshots/auditoria-telas/_capturar.py
# Copiar: 07–13 (ofício), 18–20 (roteiro), 45 (ui-lab structures)
```

Checklist manual: comparar com `/dev/ui-lab/structures/` em 1440×900, tema claro e escuro.

---

## 10. Testes

| Comando | Resultado |
|---------|-----------|
| `python manage.py check` | OK (0 issues) |
| `python manage.py test oficios roteiros` | 190 testes, **OK** (após ajuste de asserts de stepper/status) |
| Testes wizard ofício direcionados | OK |

**Smoke manual (obrigatório antes de release):** criar/editar roteiro, wizard ofício steps 1–6, mapa, autosave, console limpo — ver seção 9.

---

## 11. Pendências

**Antes da Fase 5 funcional**

- Smoke visual + screenshots na pasta dedicada.
- Remover bridge CSS quando steps usarem `wizard_section_card.html` explicitamente.

**Depois**

- Migrar botões 100% para `button.html` sem classes `btn`.
- UI Lab `headers.html` ainda tem stepper inline (opcional unificar).

---

## 12. Decisão

**B — Liberado com ressalvas**

A estrutura dos wizards está alinhada ao UI Lab sem alterar motor de rotas/trechos. Liberar Fase 5B (fachada `route-calculator`) após smoke visual manual e captura de screenshots.
