# Componentes compartilhados de viagem

Os conceitos reaproveitados por Eventos, Termos, Ordens de Serviço, Planos de Trabalho e Roteiros ficam em `templates/components/travel/`. Eles não consultam banco, não aplicam regra de negócio e não alteram os nomes enviados ao backend.

## Destinos

### `destination_section.html`

Compõe título, descrição, lista ordenável, botão de adição e template de nova linha.

Parâmetros principais:

- `prefix`: prefixo dos campos do formulário (`termo`, `os`, `pt`, `evento` etc.);
- `rows_template` e `row_template`: fontes das linhas existentes e da linha nova;
- `list_id`, `add_button_id`, `template_id`: IDs preservados quando o módulo depende deles;
- `add_hook`, `list_hook`, `section_hook`: hooks adicionais específicos do consumidor;
- `show_dates`, `show_remove`, `single`: variantes funcionais.

### `destination_row.html`

É a única estrutura HTML de uma linha de destino. Usa `cv-ordered-field-row` para layout e os hooks globais `data-destination-row` e `data-destination-order`.

Os subcomponentes em `travel/destinations/` isolam seleção de estado, seleção de cidade, erros, coleção de linhas e template vazio.

Comportamento global: `static/js/components/destination-section.js`, disponível como `window.CV.destinations`. O componente preserva os nomes e IDs Django recebidos; cada página apenas informa os seletores específicos necessários ao seu fluxo.

Consumidores em produção:

- Eventos: cadastro e detalhe;
- Termos: seção de evento;
- Ordens de Serviço: seção de evento;
- Planos de Trabalho: identificação do evento;
- Roteiros: fonte, sede e destinos.

## Trechos de rota

`route_segments.html` contém a coleção editável de trechos do roteiro. O hook global é `data-route-segments`; cards usam `route-segment-card` e blocos usam `route-section-block`.

O template continua recebendo o contexto já preparado pelo fluxo de Roteiros, inclusive JSON inicial e URLs presentes no formulário pai. Cálculo, persistência e validação continuam no backend e nos módulos JavaScript existentes.

## Cálculo de diárias

`travel_allowance_calculator.html` apresenta a seção de cálculo e os campos ocultos já definidos pelo formulário. O hook de integração é `data-travel-allowance-calculator`.

O componente não calcula valores por conta própria e não substitui endpoints ou regras de negócio.

## Limites

- HTML visual e comportamento genérico pertencem aos componentes desta pasta.
- Labels, nomes POST, permissões, regras e mensagens de negócio pertencem aos módulos Django.
- Uma diferença visual deve ser parâmetro/variante apenas quando representa estado real; diferenças cosméticas locais não justificam cópia.
- Novos consumidores devem incluir os componentes canônicos diretamente, sem aliases intermediários.
