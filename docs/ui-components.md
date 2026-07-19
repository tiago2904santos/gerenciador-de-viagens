# Componentes UI - Central de Viagens 3.0

## Regra máxima

UI Lab aprovado vira componente obrigatório. O fluxo correto é:

`UI Lab aprovado -> componente reutilizável -> token CSS -> include/partial -> página real`.

Páginas reais não devem criar botão, card, filtro, input, header, sombra, raio, cor, espaçamento ou estrutura própria quando já existir equivalente em `templates/components/ui/`.

## Includes oficiais

Headers:

```django
{# Os wrappers abaixo compartilham o markup único de page_header.html. #}
{% include "components/ui/headers/header_stack_simple.html" with eyebrow="CADASTROS" title=page_title description=page_description icon_label="SV" module_label="Servidores" only %}
{% include "components/ui/headers/header_stack_back_action.html" with eyebrow="ROTEIROS" title=page_title back_url=list_url back_label="Voltar" only %}
{% include "components/ui/headers/header_stack_filters.html" with eyebrow="CADASTROS" title=page_title form_action=request.path search_value=q search_placeholder="Buscar" primary_action_label="Novo" primary_action_url=create_url only %}
{% include "components/ui/headers/header_stack_stepper.html" with eyebrow="OFÍCIOS" title=page_title status_label="Rascunho" only %}
```

`components/ui/headers/page_header.html` é a fonte única de markup para as
variantes `simple`, `back_action` e `stepper`. Páginas consumidoras devem usar
os wrappers públicos acima; não devem incluir `page_header.html` diretamente.

Buttons:

```django
{% include "components/ui/buttons/button.html" with label="Salvar" variant="primary" icon="check" type="submit" only %}
{% include "components/ui/buttons/button.html" with label="Salvando" variant="primary" loading=True only %}
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
{% include "components/ui/forms/form_block.html" with title="Identificação" description="Dados principais." section_id="identificacao" body_template="app/partials/_identificacao_body.html" %}
{% include "components/ui/forms/form_block.html" with shell="card" title="Dados do registro" description="Card de seção standalone." section_id="registro-title" body_template="app/partials/_registro_body.html" footer_template="app/partials/_registro_footer.html" %}
{% include "components/ui/forms/footer_actions.html" with primary_label="Salvar" secondary_label="Voltar" secondary_url=back_url only %}
{% include "components/ui/forms/file_picker.html" with field_id="id_anexos" field_name="anexos" label="Documentos" help_text="PDF ou imagem." only %}
```

`components/forms/form_field.html` é somente um ponto de compatibilidade para
consumidores existentes; toda a renderização vive em
`components/ui/forms/field.html`. Novos componentes devem usar o caminho `ui`.

O seletor de arquivos usa o contrato global `cv-file-*`; sua estrutura fica em
`components/ui/forms/file_picker.html` e sua aparÃªncia em
`static/css/components/file-picker.css`. Os aliases `prestacao-file-*` existem
apenas durante a migraÃ§Ã£o dos consumidores antigos e nÃ£o devem ser usados em
novos templates.

Inicialização progressiva: componentes JavaScript registram seus inicializadores
idempotentes em `CV.registerEnhancer`. Conteúdo adicionado dinamicamente é
aprimorado automaticamente; páginas não devem repetir o boot global.

Diálogos abrem e fecham por `CV.dialogs`, que centraliza Escape, contenção de
foco com Tab/Shift+Tab e devolução do foco ao acionador.

Exclusão, cancelamento e confirmação usam a estrutura `cv-dialog-*`, o cabeçalho
compartilhado `components/ui/modals/dialog_header.html` e os hooks `data-*`
específicos de cada fluxo. Novos modais não devem copiar o markup
`delete-confirm-modal`; devem compor o contrato canônico e registrar o
comportamento em `CV.dialogs`.

Lists, filters and status:

```django
{% include "components/ui/lists/list_toolbar.html" with q=q search_placeholder="Buscar registros" action_label="Novo" action_url=create_url only %}
{% include "components/ui/lists/list_card.html" with title=card.title subtitle=card.subtitle meta=card.meta actions=card.actions only %}
{% include "components/ui/lists/status_pill.html" with label="Ativo" variant="active" only %}
{% include "components/ui/lists/pagination.html" %}
{% include "components/ui/filters/filter_bar.html" with q=q search_placeholder="Buscar" clear_url=search_clear_url only %}
```

Summary and document cards:

```django
{% include "components/cards/summary_card.html" with label="Total" value=total description="Registros ativos" only %}
{% include "components/cards/document_card.html" with card=document_card only %}
```

Resumos compostos usam `cv-summary-card`, `cv-summary-grid` e
`cv-summary-grid--2|3|4`. Itens internos conservam os dados e ações do domínio,
mas não criam novas superfícies, bordas ou grids em CSS de página.

Cards documentais usam `cv-document-card-*`; PDF, DOCX, visualização e exclusão
continuam sendo ações semânticas do botão canônico.

Cards ricos de Ofícios, Eventos, Planos de Trabalho, Ordens de Serviço,
Prestações de Contas e Roteiros compartilham `cv-entity-card` com as regiões
`__header`, `__body` e `__footer`. O conteúdo e os comportamentos de cada domínio
continuam específicos, mas superfície, interação e responsividade são globais.

Viewer e assinatura documental:

```django
{% include "components/documents/pdf_viewer.html" with pdf_url=pdf_url worker_src=worker_src filename=filename share_url=share_url only %}
{% include "components/documents/signature_card.html" with signature=assinatura next_url=request.get_full_path only %}
```

O viewer preserva o contrato do PDF.js (`doc-pdf-*`) dentro do shell global
`cv-document-viewer`. O card `cv-signature-card` usa `signature-actions.js` para
copiar links e abrir WhatsApp; não deve conter JavaScript inline em consumidores.

O shell global fornece `#main-content`, skip link e drawer móvel. A sidebar é
controlada por `data-sidebar-drawer-*`; páginas não devem criar menus móveis
ou alterar o foco diretamente.

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
