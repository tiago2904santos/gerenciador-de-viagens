# Relatório — Padronização Visual Global
**Branch:** `refactor/padronizacao-visual-global`  
**Data:** 2026-06-03

---

## 1. Resumo do que foi padronizado

### Migração `app-page` → `page-shell`
Todas as páginas internas que usavam o padrão antigo (`app-page`, `app-page-hero`, `app-page__form-card`) foram migradas para a estrutura oficial `page-shell`.

| Página | Antes | Depois |
|--------|-------|--------|
| `roteiros/confirm_delete.html` | `app-page` + hero manual | `page-shell--standard-simple` + `page_header` |
| `oficios/confirm_delete.html` | `app-page` + hero manual | `page-shell--standard-simple` + `page_header` |
| `oficios/modelos_motivo/form.html` | `app-page` + `app-form-shell` + `form-grid` | `page-shell--standard-simple` + `field-grid` |
| `oficios/modelos_motivo/confirm_delete.html` | `app-page` + `app-form-shell` | `page-shell--standard-simple` + `footer_actions` |
| `justificativas/modelos/form.html` | `app-page` + `app-form-shell` + `form-grid` + `field-span-12` | `page-shell--standard-simple` + `field-grid` + `field-size-4` |
| `justificativas/modelos/confirm_delete.html` | `app-page` + `app-form-shell` | `page-shell--standard-simple` + `footer_actions` |
| `termos/index.html` | `app-page` + `h1` solto | `page-shell--standard-simple` + `page_header` + `form_section` |
| `termos/preview.html` | `app-page` + `h1` solto + link inline | `page-shell--standard-simple` + `page_header` |
| `roteiros/detail.html` | `page-shell--standard` + `page_header` + div duplo `form-section` | `page-shell--standard` + `page_header` + seções corretas |
| `planos_trabalho/index.html` | `app-page` + `module_placeholder` | `page-shell--standard-simple` + `page_header` |
| `ordens_servico/index.html` | `app-page` + `module_placeholder` | `page-shell--standard-simple` + `page_header` |
| `prestacoes_contas/index.html` | `app-page` + `module_placeholder` | `page-shell--standard-simple` + `page_header` |
| `diario_bordo/index.html` | `app-page` + `module_placeholder` | `page-shell--standard-simple` + `page_header` |
| `eventos/index.html` | `app-page` + `module_placeholder` | `page-shell--standard-simple` + `page_header` |
| `documentos/index.html` | `app-page` + `module_placeholder` | `page-shell--standard-simple` + `page_header` |
| `assinaturas/index.html` | `app-page` + `module_placeholder` | `page-shell--standard-simple` + `page_header` |

### Correções estruturais

- **`cadastros/configuracao/form.html`** — Removidas 3 tags `</section>` soltas e erroneamente posicionadas. Re-adicionadas corretamente como fechamento das seções abertas pelo `form_section.html` (o include abre `<section>` sem fechar; o template pai deve fechar). Agora cada uma das 3 seções (Dados da unidade, Endereço, Assinaturas) está devidamente encerrada antes da próxima começar.

### Componente corrigido

- **`components/feedback/module_placeholder.html`** — Substituído `components/ui/buttons/button.html` (caminho antigo) por `components/ui/buttons/button.html` (caminho correto). Resultado visual idêntico, mas agora usando o componente canônico.

### CSS limpo

- **`static/css/roteiros-list.css`**
  - Removidas todas as regras `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-muted` legadas (o HTML atual usa `cv-btn cv-btn--*`, não as classes antigas).
  - Substituídas cores hardcoded de borda lateral de status por tokens globais:
    - `#dc2626` → `var(--color-danger)`
    - `#d97706` → `var(--color-accent)`
    - `#2563eb` → `var(--color-info)`
    - `#16805a` → `var(--color-success)`
    - `#64748b` → `var(--color-subtle)`
    - `#7f9bbb` (hover) → `var(--color-border-strong)`
  - Removidos blocos de override para toolbar antiga (`.app-page__toolbar`, `.app-page__shell`) que não têm mais correspondência no HTML atual.

---

## 2. Arquivos alterados por esta refatoração

### Templates HTML
```
templates/components/feedback/module_placeholder.html
templates/assinaturas/index.html
templates/cadastros/configuracao/form.html
templates/diario_bordo/index.html
templates/documentos/index.html
templates/eventos/index.html
templates/justificativas/modelos/confirm_delete.html
templates/justificativas/modelos/form.html
templates/oficios/confirm_delete.html
templates/oficios/modelos_motivo/confirm_delete.html
templates/oficios/modelos_motivo/form.html
templates/ordens_servico/index.html
templates/planos_trabalho/index.html
templates/prestacoes_contas/index.html
templates/roteiros/confirm_delete.html
templates/roteiros/detail.html
templates/termos/index.html
templates/termos/preview.html
```

### CSS
```
static/css/roteiros-list.css
```

---

## 3. Componentes criados ou consolidados

Nenhum componente novo foi criado. Foram consolidados:
- `module_placeholder.html` corrigido para usar o caminho canônico do botão
- `roteiros/detail.html` consolidado para usar `page_header` + `footer_actions` padrão + `empty_state` global em vez de estrutura própria

---

## 4. CSS removido ou migrado

| Arquivo | O que foi feito |
|---------|----------------|
| `roteiros-list.css` | Removidas ~80 linhas de regras `.btn-*` legadas e overrides de toolbar antiga. Cores hardcoded substituídas por tokens. |

---

## 5. Páginas migradas para components

Todas as páginas listadas na tabela da seção 1 foram migradas para usar exclusivamente components e headers padrão do design system.

---

## 6. Pendências

### Baixa prioridade (não alteram experiência principal)
- **`assinaturas/verificar_codigo.html`** — usa `class="app-page"` em `<section>`. É uma página utilitária de verificação de integridade de assinaturas. Pode ser migrada para `page-shell--standard-simple` em sprint futuro.
- **`cadastros/index.html`** (hub de cadastros) — usa `app-page` com hero para a tela de hub de módulos. Visualmente distinto por design. Pode manter ou migrar para estrutura `page-shell--list` futuramente.

### Para próximo sprint (fora do escopo desta refatoração por risco)
- **`oficios/wizard_transporte.html`** — usa `form-grid`, `app-form-grid-panel`, `field-span-12`. Migração requer revisão cuidadosa com CSS do `oficios.css` e JS específico do wizard.
- **`oficios/wizard_justificativa.html`** — usa `motivo-card__body app-form-grid-panel`. Mesmo risco acima.
- **`static/css/assinaturas.css`** — ~50 hardcodes de cor (maioria com fallback `var()`). Ideal limpar para usar apenas tokens.
- **`static/css/app-page.css`** — gradientes hardcoded (`#0e5088`, `#0b3a66`). Pode substituir por `var(--color-primary-bright)` / `var(--color-primary)`.

---

## 7. Riscos e pontos de revisão visual

1. **`configuracao/form.html`** — Verificar que as 3 seções aparecem como cards separados (não aninhados). A estrutura de `</section>` após cada `field-grid` é essencial para isso.
2. **`roteiros/detail.html`** — O footer agora usa estrutura `<footer class="footer-actions">` inline (não via include), pois são dois botões primários (Editar + Excluir). Verificar layout visual.
3. **`termos/preview.html`** — A URL de volta usa `{% url 'oficios:dados_viajantes' oficio.pk %}`. Confirmar que esse nome de URL está correto para o projeto.
4. **Módulos placeholder** — `planos_trabalho`, `ordens_servico`, etc. — o `module_placeholder` aparece dentro de `main-form-panel`. Verificar espaçamento: o componente não tem margem superior própria, pode ficar colado ao rail.

---

## 8. Resultado dos comandos git

### `python manage.py check`
Não executado — o ambiente virtual é Windows e não pode ser ativado na sandbox Linux. O comando deve ser rodado manualmente no terminal do projeto.

### `git status`
O git index está bloqueado (`index.lock`) pelo processo Windows do Claude Code, impedindo staging/commit da sandbox. Rode os comandos abaixo **no seu terminal local**:

```bash
# Confirmar branch correta
git branch --show-current
# → deve mostrar: refactor/padronizacao-visual-global

# Ver o que foi alterado
git status

# Adicionar as alterações desta refatoração
git add \
  templates/components/feedback/module_placeholder.html \
  templates/assinaturas/index.html \
  templates/cadastros/configuracao/form.html \
  templates/diario_bordo/index.html \
  templates/documentos/index.html \
  templates/eventos/index.html \
  templates/justificativas/modelos/confirm_delete.html \
  templates/justificativas/modelos/form.html \
  templates/oficios/confirm_delete.html \
  templates/oficios/modelos_motivo/confirm_delete.html \
  templates/oficios/modelos_motivo/form.html \
  templates/ordens_servico/index.html \
  templates/planos_trabalho/index.html \
  templates/prestacoes_contas/index.html \
  templates/roteiros/confirm_delete.html \
  templates/roteiros/detail.html \
  templates/termos/index.html \
  templates/termos/preview.html \
  static/css/roteiros-list.css

# Verificar o que será commitado
git diff --stat --cached

# Commitar
git commit -m "refactor: padroniza componentes visuais globais

- Migra 17 páginas de app-page para page-shell (standard-simple/standard)
- Substitui hero manual por page_header/back_action nos formulários
- Migra form-grid/field-span-12 para field-grid/field-size-* nos módulos de ofícios
- Corrige seções duplicadas em configuracao/form.html
- Corrige module_placeholder para usar caminho canônico de button
- Limpa roteiros-list.css: remove .btn-* legados, substitui cores por tokens
- Módulos stub (planos, ordens, prestações, diário, eventos, documentos) migrados"

# Validar
python manage.py check
git status
```
