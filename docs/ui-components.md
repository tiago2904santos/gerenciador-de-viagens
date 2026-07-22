# Uso dos componentes UI

O catálogo e as regras oficiais estão em [COMPONENTES.md](COMPONENTES.md). Este arquivo mantém exemplos mínimos de inclusão.

```django
{% include "components/ui/headers/page_header.html" with eyebrow="CADASTROS" title=page_title description=page_description icon_label="SV" module_label="Servidores" only %}
{% include "components/ui/headers/filter_page_header.html" with eyebrow="CADASTROS" title=page_title form_action=request.path search_value=q search_placeholder="Buscar" only %}
{% include "components/ui/buttons/button.html" with label="Salvar" variant="primary" icon="check" type="submit" only %}
{% include "components/ui/forms/field.html" with field=form.nome only %}
{% include "components/ui/forms/form_block.html" with title="Identificação" body_template="app/partials/_identificacao_body.html" %}
{% include "components/ui/badges/status_badge.html" with label="Ativo" variant="active" only %}
{% include "components/ui/lists/pagination.html" %}
{% include "components/ui/feedback/empty_state.html" with message=empty_message action_label="Novo" action_url=create_url only %}
```

JavaScript progressivo registra inicializadores idempotentes em `CV.registerEnhancer`. Conteúdo dinâmico deve passar pelo mesmo mecanismo; páginas não repetem o boot global.

Diálogos usam `CV.dialogs`, os hooks `cv-dialog-*` e `components/ui/modals/dialog_header.html`. Campos de destino usam `CV.destinations` e os componentes em `components/travel/`.

É proibido criar wrappers que apenas encaminham contexto, copiar markup canônico para uma página ou colocar seletores de demonstração `ui-lab-*` em CSS de produção.
