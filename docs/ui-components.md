# Componentes UI — Central de Viagens 3.0

## Regra fundamental

**UI Lab aprovado → componente reutilizável → `{% include %}` nas páginas reais.**

Não copiar HTML do UI Lab manualmente. Não criar variações por página.
Se o padrão existe no UI Lab, ele vira componente e é chamado via `{% include %}`.

---

## CSS

Os estilos de botões (`cv-btn`, `cv-icon-btn`, `cv-footer-action`, `cv-field-side-action`)
estão em `static/css/cv-buttons.css`, carregado globalmente via `templates/base.html`.

Os estilos de headers (`page-header-stack`, `page-header-band`, `page-header-rail`) e
estruturas de página (`page-shell`, `form-section`, `field-grid`, `footer-actions`) estão
em `static/css/page-shell.css`, também carregado globalmente.

---

## 1. Headers

### Standard Simple / Standard
```django
{% include "components/ui/headers/header_stack_simple.html" with
   eyebrow="CADASTROS"
   title=page_title
   description=page_description
   icon_label="SV"
   module_label="Servidores"
   only
%}
```

### Wizard / Back Action
```django
{% include "components/ui/headers/header_stack_back_action.html" with
   eyebrow="ROTEIROS"
   title=page_title
   description=page_description
   icon_label="RT"
   module_label="Roteiros"
   back_label="Voltar para lista"
   back_url=list_url
   only
%}
```
Quando há CTA primário ao invés de retorno (ex: "Finalizar documento"):
```django
{% include "components/ui/headers/header_stack_back_action.html" with
   ...
   primary_action_label="Finalizar documento"
   primary_action_url=finalize_url
   only
%}
```

### Lista com filtros
```django
{% include "components/ui/headers/header_stack_filters.html" with
   eyebrow="ROTEIROS"
   title=page_title
   icon_label="RT"
   form_action=request.path
   search_name="q"
   search_value=q
   search_placeholder="Buscar por sede, destino ou observações"
   search_clear_url=search_clear_url
   only
%}
```
> `form_action` ativa o `<form method="get">` no componente. Sem ele, renderiza `<div>`.

### Band com status (detalhe/documento)
```django
{% include "components/ui/headers/header_band_status.html" with
   eyebrow="ROTEIROS"
   title=page_title
   status_label="Rascunho"
   status_variant="draft"
   only
%}
```
Variantes de status: `draft` | `active` | `pending`.

---

## 2. Estruturas de página

### Estrutura padrão de formulário
```html
<div class="page-shell page-shell--standard">
    {% include "components/ui/headers/header_stack_simple.html" with ... only %}

    <form class="main-form-panel" method="post" novalidate>
        {% csrf_token %}
        {% include "components/ui/layouts/form_section.html" with title="Seção" description="..." section_id="minha-secao" only %}
        <div class="field-grid">
            <!-- campos aqui -->
        </div>
        </section>
        {% include "components/ui/layouts/footer_actions.html" with primary_label="Salvar" secondary_label="Voltar" secondary_url=back_url only %}
    </form>
</div>
```

Variantes de `page-shell`: `--standard-simple` | `--standard` | `--wizard` | `--list`.

### form_section
```django
{% include "components/ui/layouts/form_section.html" with
   title="Identificação"
   description="Nome, cargo e CPF são obrigatórios."
   section_id="id-unico"
   only
%}
<div class="field-grid">
    <!-- campos -->
</div>
</section>
```
> O componente abre `<section>` e `<header>`. Feche com `</section>` após os campos.

### footer_actions
```django
{% include "components/ui/layouts/footer_actions.html" with
   primary_label="Salvar"
   primary_variant="primary"
   primary_icon="check"
   secondary_label="Voltar"
   secondary_url=back_url
   only
%}
```

---

## 3. Botões pill

```django
{% include "components/ui/buttons/button.html" with label="Salvar" variant="primary" icon="check" type="submit" only %}

{% include "components/ui/buttons/button.html" with label="Voltar" variant="back" icon="arrow-left" href=back_url only %}

{% include "components/ui/buttons/button.html" with label="Voltar para lista" variant="back-list" icon="list" href=list_url only %}

{% include "components/ui/buttons/button.html" with label="Cancelar" variant="cancel" icon="x" href=cancel_url only %}

{% include "components/ui/buttons/button.html" with label="Excluir" variant="danger" icon="trash" type="submit" only %}
```

Variantes: `primary` | `secondary` | `back` | `back-list` | `cancel` | `danger` |
`soft-danger` | `preview` | `pdf` | `docx` | `sign` | `neutral` | `tool`.

---

## 4. Botões circulares (icon-only)

Uso exclusivo em listas, cards e documentos. `aria_label` é **obrigatório**.

```django
{% include "components/ui/buttons/icon_button.html" with action="edit" href=edit_url aria_label="Editar" only %}

{% include "components/ui/buttons/icon_button.html" with action="delete" href=delete_url aria_label="Excluir" only %}

{% include "components/ui/buttons/icon_button.html" with action="preview" href=preview_url aria_label="Visualizar" only %}

{% include "components/ui/buttons/icon_button.html" with action="pdf" href=pdf_url aria_label="Baixar PDF" only %}

{% include "components/ui/buttons/icon_button.html" with action="docx" href=docx_url aria_label="Baixar DOCX" only %}

{% include "components/ui/buttons/icon_button.html" with action="sign" href=sign_url aria_label="Assinar" only %}
```

Agrupar com `.cv-icon-btn-group`:
```html
<div class="cv-icon-btn-group">
    {% include "components/ui/buttons/icon_button.html" with action="edit" href=edit_url aria_label="Editar" only %}
    {% include "components/ui/buttons/icon_button.html" with action="delete" href=delete_url aria_label="Excluir" only %}
</div>
```

---

## 5. Botão lateral acoplado a campo

Wrapper obrigatório: `.cv-field-row` + `.cv-field-control--grow` no campo.

```django
<div class="cv-field-row">
    <div class="cv-field-control cv-field-control--grow">
        {% include "components/forms/form_field.html" with field=form.cargo only %}
    </div>
    {% include "components/ui/buttons/field_action_button.html" with label="Gerenciar cargo" icon="settings" href=cargos_url only %}
</div>
```

Variantes: `secondary` | `neutral` | `manage` | `clear` | `primary`.

---

## 6. Footer action (rodapé de card)

O rodapé inteiro é o botão. Deve ser o último elemento dentro de um card com `overflow:hidden`.

```django
{% include "components/ui/buttons/footer_action.html" with label="Adicionar destino" icon="plus" href=add_destino_url only %}

{% include "components/ui/buttons/footer_action.html" with label="Cadastrar item" icon="plus" variant="primary" only %}

{% include "components/ui/buttons/footer_action.html" with label="Adicionar anexo" icon="plus" variant="neutral" only %}
```

Variantes: `add` (default) | `primary` | `neutral`.

---

## Localização dos arquivos

| Tipo | Caminho |
|------|---------|
| Headers | `templates/components/ui/headers/` |
| Layouts | `templates/components/ui/layouts/` |
| Botões | `templates/components/ui/buttons/` |
| Ícones | `templates/dev/ui_lab/partials/_cv_icon.html` |
| CSS botões | `static/css/cv-buttons.css` |
| CSS estrutura | `static/css/page-shell.css` |

---

## Pendências para a próxima fase

- Migrar `input_with_action.html` para usar `cv-field-side-action` em vez de `btn btn-secondary`
- Migrar `form_actions.html` para usar `cv-btn` em vez de `btn btn-primary`
- Aplicar os novos componentes no restante das telas do sistema
- Mover `_cv_icon.html` de `dev/ui_lab/partials/` para `components/ui/` (path de produção)
- Criar componente para o stepper (`page-stepper`) para wizards
