# Roteiros Arquitetura

## Pendencias controladas

Itens conhecidos que **nao bloqueiam** o uso de Roteiros como referencia arquitetural, enquanto o fluxo em producao estiver correto:

1. **`roteiros/services/editor_state_builder.py`** (antigo `roteiro_logic.py`, renomeado no `BE-13` fatia 3) concentra 1.337 linhas de montagem e validação do estado do editor. Depois das três fatias do `BE-13` ele tem **uma responsabilidade só** — parsing de request, contexto e persistência saíram —, mas continua grande; reduzir o volume é trabalho de outra etapa.
2. **Components de dominio** ainda sao wrappers finos sobre `roteiros/partials/roteiro/` em varios blocos. Evolucao: extrair HTML compartilhado quando o **segundo** modulo (ex.: Oficios) reutilizar o mesmo bloco.
3. **`roteiros.css`** mantem o visual denso e especifico do wizard avulso (`roteiro-editor__*`, temas). **`domain.css`** cobre tokens semanticos; migracao em massa de regras nao e obrigatoria antes do aceite.
4. **Extração adicional** so deve ser feita quando Oficios/Planos/OS forem efetivamente reutilizar os mesmos blocos — evitar refatoracao antecipada.

Outras observacoes de validacao:

- **`bate_volta.html`** usa `form-check-input` / switch nativo para `bate_volta_diario_ativo`. O design system prefere **card-toggle** para booleanos visiveis; padronizar em etapa futura se quiser aderencia 100% ao DS sem mudar regra POST.

## Revisao critica pos-refatoracao

### 1. O que ficou bom

- Separacao clara: `selectors.py` para consultas, `services/roteiro_editor.py` para fluxo de persistencia e validacao de POST, `presenters.py` para dados de tela, views apenas orquestrando.
- Componentes de dominio em `templates/components/travel/` centralizam includes do wizard sem duplicar o HTML dos partials em `roteiros/partials/roteiro/`.
- `get_roteiro_by_id` com `select_related` / `prefetch_related` evita N+1 em detalhe e edicao.
- API `api_cidades_por_estado` usa selector com filtro opcional `q`.
- Exclusao com `ProtectedError` tratada no service `excluir_roteiro`.
- Scripts do formulario carregados via `extra_js` na pagina, nao embutidos no meio do partial (exceto `json_script` necessario ao lado dos dados).

### 2. O que ainda ficou acoplado

- `_build_roteiro_form_context` saiu do módulo no `BE-13` fatia 2 e hoje é privada de `roteiros/presenters.py`, atrás da fachada `montar_contexto_editor_roteiro`. O que sobrou em `editor_state_builder.py` são as 33 funções privadas de montagem/validação de estado.
- Partials em `roteiros/partials/roteiro/` continuam com HTML e classes `roteiro-editor__*` especificas do fluxo legacy; os components de dominio sao wrappers finos ate outro modulo precisar dos mesmos blocos.

### 3. O que ainda e especifico demais de Roteiros

- Nomes de campos, `fase_roteiro`, rotas `roteiros:*` e textos do wizard sao do modulo Roteiros.
- `roteiros.css` permanece grande porque o visual do editor avulso e denso; `domain.css` traz tokens e aliases semanticos para blocos reutilizaveis.

### 4. O que ainda esta duplicado

- `_build_roteiro_diarias_from_request` reparsing interno do POST (ja era assim na logica legacy); nao foi alterado para nao mudar comportamento.

### 5. O que ainda nao e reutilizavel sem trabalho extra

- `trecho_card.html` usa labels e formato de datas do modelo `RoteiroTrecho`; outro modulo precisaria de presenter ou partial alternativo se o modelo diferir.
- `destinos.html` / `trechos.html` apenas incluem partials de Roteiros: contrato reutilizavel documentado, implementacao ainda amarrada aos partials.

### 6. O que foi corrigido nesta etapa

- Conflito `roteiros/services.py` vs pacote `roteiros/services/`: orquestracao movida para `services/roteiro_editor.py` e reexportada em `services/__init__.py`.
- `views.py` integrada aos services e presenters (sem duplicar persistencia nem initial da config).
- `retorno.html` (domain) incluia o partial duas vezes; corrigido.
- Consultas de cidade/estado no setup do form e no mapa de roteiros avulsos passam por `selectors` onde aplicavel.
- `api_cidades_por_estado` aceita `?q=` via selector.
- `trechos_estimar` usa `obter_cidades_origem_destino_estimativa`.
- Detalhe: destinos renderizados a partir de `destinos_detalhe` no presenter (sem loop ORM no template).
- Card de listagem: uma unica avaliacao de `destinos` para preview e contagem.
- Removidos JS vazios `static/js/components/destinos.js`, `trechos.js`, `calculadora-rota.js` (sem referencias).
- Encoding do fallback "Parana (PR)" corrigido em `roteiro_logic`.
- Paginas de roteiro carregam `domain.css` onde usam components de dominio.

## Auditoria antes da refatoracao

- View com regra funcional acoplada ao fluxo de fase_roteiro (validacao e persistencia).
- Consulta direta de cidades em endpoint de API fora de selector.
- Template de formulario com composicao misturada entre blocos de dominio e parciais de pagina.
- CSS extenso e especifico de Roteiros sem camada de dominio reutilizavel explicita.
- Componentes de dominio inexistentes em `templates/components/travel/`.

## Contrato de arquitetura

- Roteiro e avulso e reutilizavel; nao depende de Evento nem de Oficio.
- Trecho pertence a um roteiro, com ordem, origem e destino.
- Destinos, trechos, retorno e calculadora devem ser blocos de dominio reutilizaveis.
- Views ficam magras: orquestram form/selectors/services/presenters.
- Sem `href="#"`, sem CSS inline, sem JS inline, sem exibir "Atualizado em".

## Camada de services (roteiro_editor)

| Funcao | Papel |
|--------|--------|
| `obter_initial_roteiro` | Le singleton de configuracao para sede padrao (somente dados iniciais). |
| `preparar_querysets_formulario_roteiro` | Preenche querysets do form (sem template). |
| `carregar_opcoes_rotas_avulsas_salvas` | Opcoes de duplicacao + mapa de estado (delega `editor_state_builder`). |
| `preparar_estado_editor_roteiro_para_get` | Destinos/trechos/fase_roteiro para GET. |
| `normalizar_destinos_e_trechos_apos_erro_post` | Reexibe form apos POST invalido. |
| `validar_submissao_editor_roteiro` | Parse fase_roteiro + validacao + diarias (sem HTTP). |
| `calcular_diarias_roteiro_request` | Façade para cálculo de diárias mantendo contrato do endpoint. |
| `criar_roteiro` / `atualizar_roteiro` / `excluir_roteiro` | Transacao e persistencia. |

## Serviços internos do editor

- `roteiros/services/editor_parser.py`: parse de `fase_roteiro`/POST/state (inteiros, datas/horas, decimal, destinos, trechos).
- `roteiros/services/editor_context.py`: helpers puros de localidade e equivalência (`cidade/UF`) usados no wizard.
- `roteiros/services/editor_state.py`: estado de bate-volta e dedupe de retorno final sem dependência de view.
- `roteiros/services/map_defaults.py`: defaults de mapa e resolução de UF por CEP para bootstrap do editor.
- `roteiros/services/editor_state_builder.py`: monta e valida o estado do editor a partir do POST e dos trechos gravados (o antigo `roteiro_logic.py`). Não confundir com o `editor_state.py` acima, que só tem os helpers de bate-volta e dedupe.
- `roteiros/services/editor_persistence.py`: grava roteiro, destinos e trechos sob `@transaction.atomic`, e atualiza as datas do cabeçalho depois. Único módulo do editor que escreve no banco.
- `roteiros/services/editor_flow.py`: fluxo de submissão do editor (`novo` e `editar` compartilham).

## JavaScript do editor (modular)

- Entrypoint: `static/js/pages/roteiros.js` (arquivo enxuto de bootstrap).
- Núcleo do editor: `static/js/pages/roteiros/editor/index.js`.
- Módulos por responsabilidade:
  - `state.js`
  - `destinos.js`
  - `trechos.js`
  - `retorno.js`
  - `diarias.js`
  - `mapa.js`
  - `utils.js`
- Carregamento em `templates/roteiros/roteiro_form_page.html` com `type="module"`, sem bundler e sem retorno de JS inline para template.

## View `calcular_diarias` e `request`

**Corrigido no `BE-13` fatia 1.** A view repassava o `request` inteiro ao módulo de estado, contra `docs/PADRAO_SERVICES.md:20`, e a exceção estava documentada aqui. Hoje ela chama `calcular_diarias_roteiro_request(request.POST)`: quem sai da view é o `QueryDict`, e nenhum service do editor recebe `request`.

## Decisoes de refatoracao

- Extraida orquestracao de fluxo de criacao/edicao para `roteiros/services/roteiro_editor.py`.
- Centralizada consulta de cidades/estados relevantes em `roteiros/selectors.py`.
- Mantida regra funcional existente via reutilizacao de `roteiro_logic`.
- Criada camada de componentes de dominio em `templates/components/travel/`.
