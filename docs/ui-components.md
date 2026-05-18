# Componentes UI - Central de Viagens 3.0

## Regra máxima

UI Lab aprovado vira componente obrigatório. O fluxo correto é:

`UI Lab aprovado -> componente reutilizável -> token CSS -> include/partial -> página real`.

Páginas reais não devem criar botão, card, filtro, input, header, sombra, raio, cor, espaçamento ou estrutura própria quando já existir equivalente em `templates/components/ui/`.

## Includes oficiais

Headers:

```django
{% include "components/ui/headers/header_stack_simple.html" with eyebrow="CADASTROS" title=page_title description=page_description icon_label="SV" module_label="Servidores" only %}
{% include "components/ui/headers/header_stack_back_action.html" with eyebrow="ROTEIROS" title=page_title back_url=list_url back_label="Voltar" only %}
{% include "components/ui/headers/header_stack_filters.html" with eyebrow="CADASTROS" title=page_title form_action=request.path search_value=q search_placeholder="Buscar" primary_action_label="Novo" primary_action_url=create_url only %}
{% include "components/ui/headers/header_stack_stepper.html" with eyebrow="OFÍCIOS" title=page_title status_label="Rascunho" only %}
```

Buttons:

```django
{% include "components/ui/buttons/button.html" with label="Salvar" variant="primary" icon="check" type="submit" only %}
{% include "components/ui/buttons/icon_button.html" with action="delete" href=delete_url aria_label="Excluir" only %}
{% include "components/ui/buttons/field_action_button.html" with label="Gerenciar cargo" icon="settings" href=cargos_url only %}
{% include "components/ui/buttons/footer_action.html" with label="Adicionar destino" icon="plus" href=add_url only %}
{% include "components/ui/buttons/floating_action.html" with label="Salvar" icon="check" type="submit" only %}
```

Forms:

```django
{% include "components/ui/forms/field.html" with field=form.nome size_class="field-size-3" only %}
{% include "components/ui/forms/field.html" with field=form.cargo action_url=cargos_url action_label="Gerenciar cargos" action_icon="settings" only %}
{% include "components/ui/forms/field_grid.html" with fields=form.visible_fields only %}
{% include "components/ui/forms/form_section.html" with title="Identificação" description="Dados principais." section_id="identificacao" only %}
{% include "components/ui/forms/footer_actions.html" with primary_label="Salvar" secondary_label="Voltar" secondary_url=back_url only %}
```

Lists, filters and status:

```django
{% include "components/ui/lists/list_toolbar.html" with q=q search_placeholder="Buscar registros" action_label="Novo" action_url=create_url only %}
{% include "components/ui/lists/list_card.html" with title=card.title subtitle=card.subtitle meta=card.meta actions=card.actions only %}
{% include "components/ui/lists/status_pill.html" with label="Ativo" variant="active" only %}
{% include "components/ui/lists/pagination.html" %}
{% include "components/ui/filters/filter_bar.html" with q=q search_placeholder="Buscar" clear_url=search_clear_url only %}
```

Feedback and deletion:

```django
{% include "components/ui/feedback/form_errors.html" with form=form only %}
{% include "components/ui/feedback/field_error.html" with errors=field.errors only %}
{% include "components/ui/feedback/empty_state.html" with message=empty_message action_label="Novo" action_url=create_url only %}
{% include "components/ui/modals/confirm_delete.html" with object_label=object.nome primary_label="Excluir" back_url=back_url only %}
```

## Proibido

- HTML de botão, card, filtro, input, header ou confirmação criado diretamente na página.
- Bootstrap cru (`btn-primary`, `form-control`, `form-select`) quando houver componente CV.
- CSS inline, JS inline e scripts de documentação renderizados na tela.
- `box-shadow`, `border-radius`, `background`, `color`, `padding`, `margin`, `gap`, `font-size` ou `font-weight` hardcoded em CSS de página.
- Classes visuais específicas por módulo, como `oficio-card`, `servidor-card`, `cargo-card`, `custom-card`.

Classes específicas só são aceitas quando forem semânticas ou hooks JS sem estilo visual próprio, por exemplo `js-mask-cpf` ou `data-role`.

## Tokens

Tokens públicos obrigatórios ficam em `static/css/tokens.css`: `--cv-btn-*`, `--cv-field-*`, `--cv-card-*`, `--cv-list-card-*`, `--cv-page-gap`, `--cv-grid-gap`, `--cv-shell-padding`, `--cv-footer-height` e `--cv-status-*`.

Novas variações devem nascer primeiro no UI Lab, depois virar token/componente, e só então serem usadas nas páginas reais.

## Checklist para novas telas

- Header vem de `components/ui/headers/`.
- Ações vêm de `button`, `icon_button`, `field_action_button`, `footer_action` ou `floating_action`.
- Campos vêm de `components/ui/forms/field.html`.
- Listas, status e paginação vêm de `components/ui/lists/`.
- Filtros vêm de `components/ui/filters/`.
- Exclusão vem de `components/ui/modals/confirm_delete.html`.
- Nenhum CSS/JS inline foi adicionado.
- `python scripts/audit_ui_patterns.py` foi executado e as reincidências foram avaliadas.
