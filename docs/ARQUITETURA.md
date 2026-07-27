# Arquitetura

## Visao geral

Central de Viagens 3 e um projeto Django por apps de dominio, com arquitetura document-centric e migracao controlada do legado.

A pasta `legacy/` existe apenas para consulta historica e nao pode ser dependencia de runtime.

O projeto novo pode consultar `legacy/` como referencia visual, mas nao pode importar ou depender tecnicamente de templates, CSS ou JS antigos.

## App cadastros

`cadastros` e o modulo de dados-base reutilizados, com CRUD publico para:

- `Unidade`
- `Cargo`
- `Combustivel`
- `Servidor`
- `Viatura`

e tela de **Configuracao do sistema** (`ConfiguracaoSistema` singleton + linhas `AssinaturaConfiguracao` por tipo de documento).

`Estado` e `Cidade` existem como **base geografica interna** (roteiros e FKs); nao fazem parte do hub publico de cadastros nem do submenu lateral nesta fase.

Regras estruturais aplicadas:

- nao existe cadastro de `Motorista`;
- `Servidor` nao possui matricula;
- `Servidor.nome` e unico e em maiusculo; CPF obrigatorio e validado; RG/telefone com regras de unicidade quando informados;
- `Servidor.cargo` referencia `Cargo` via `PROTECT` (nullable no model por compatibilidade; obrigatorio no form);
- `Cargo`/`Combustivel` podem ter `is_padrao` (um padrao ativo por vez);
- `Viatura` nao possui `marca` nem `unidade`;
- `Viatura.combustivel` referencia `Combustivel` via `PROTECT`;
- busca simples usa `q` nos selectors;
- exclusao e fisica e bloqueada quando houver vinculos;
- mascaras e normalizacoes centralizadas em `core/utils/masks.py`.

## App roteiros

`roteiros` guarda roteiros reutilizaveis e avulsos para deslocamentos. Nesta base inicial, o app possui:

- `Roteiro`: entidade principal, independente de Evento, Oficio, Plano de Trabalho, Ordem de Servico ou qualquer outro documento.
- `TrechoRoteiro`: trecho pertencente a um roteiro, removido em cascata quando o roteiro for excluido.

Origem e destino de `Roteiro` e `TrechoRoteiro` apontam para `cadastros.Cidade`; cada cidade pertence a um `Estado`. As relacoes com cidades usam `PROTECT`, porque uma cidade em uso nao deve ser removida.

O app segue a arquitetura ja validada em `cadastros`: views chamam selectors, presenters formatam dados para listagem, templates usam components globais e consultas nao ficam no template.

Padrao interno do app (**modulo referencia** para os demais):

- `views.py` apenas orquestra request/response e mensagens.
- `services/` concentra calculos legacy (`diarias`, estimativa, etc.), `services/roteiro_editor.py` (persistencia e fluxo do editor avulso) e `services/routing/` (provedor OpenRouteService, assinatura/cache da rota consolidada, montagem de pontos a partir de `Cidade` com lat/lon no cadastro).
- `selectors.py` concentra consultas e querysets.
- `presenters.py` prepara dados de tela sem HTML.
- `templates/components/travel/` contem blocos de dominio reutilizaveis; ver `docs/COMPONENTES_DOMINIO.md` e `docs/ROTEIROS_ARQUITETURA.md`.

A interface publica em `/roteiros/` inclui listagem (busca `q`), criacao, edicao, detalhe, exclusao com confirmacao, wizard de trechos/destinos e endpoints de apoio (cidades, diarias, estimativa de trecho, **calculo de rota no mapa** via `POST /roteiros/api/calcular-rota/` que chama OpenRouteService no servidor — chave `OPENROUTESERVICE_API_KEY` apenas no `.env`), sem alterar regras do legado ja portadas.

**Mapa:** Leaflet + tiles OpenStreetMap no formulario (`static/js/roteiros-map.js`, estilos em `static/css/roteiros.css`). Variaveis: `ROUTE_PROVIDER`, `ROUTE_CACHE_ENABLED`, `ROUTE_REQUEST_TIMEOUT_SECONDS` (ver `.env.example`). Testes: `python manage.py test roteiros`.

Regras transversais: sem `href="#"`, sem CSS/JS inline nos blocos de dominio, sem exibir "Atualizado em" como metadado de lista; JS de pagina em `static/js/` (ex.: `roteiros.js`) e tokens de dominio em `static/css/domain.css`.

### Congelamento provisorio (referencia para outros apps)

Ate nova decisao de arquitetura, **Roteiros** e o modulo **referencia provisorio** para blocos de:

- destinos;
- trechos;
- retorno;
- calculadora (diarias no fluxo de roteiro);
- resumo de rota.

Os proximos modulos devem seguir o mesmo desenho (views magras, `selectors`, `services`, `presenters`, components em `templates/components/travel/`, `static/css/domain.css`). Quando um segundo modulo **passar a usar** o mesmo bloco em producao, pode ser necessaria **extração adicional** de HTML/CSS a partir dos partials atuais de Roteiros; isso e esperado e nao descaracteriza este aceite.

## Padrao tecnico

Views orquestram `forms + selectors + services + presenters + messages`.
Templates usam apenas components globais. CSS/JS por pagina seguem proibidos.

## Contrato arquitetural global definitivo

### Camadas obrigatorias

- `models.py`: estrutura de dados, relacoes, constraints e metodos simples de dominio.
- `forms.py`: validacao, normalizacao e widgets/classes de campos.
- `selectors.py`: consultas reutilizaveis, `get_object_or_404`, filtros por `q`, `select_related`/`prefetch_related`.
- `services.py` ou `services/`: criacao, atualizacao, exclusao, transacoes e regras funcionais.
- `presenters.py`: dados para tela (titulo, subtitulo, meta, badges, actions) sem HTML.
- `views.py`: orquestracao de request/form/selectors/services/presenters/messages/redirect/render.

### Reuso global recém padronizado

- Normalização de strings/dígitos/placa/acento em `core/normalizers.py`.
- Exclusão protegida em `core/deletion.py`.
- Builders de presenter em `core/presenters/actions.py`, `core/presenters/badges.py`, `core/presenters/meta.py`.
- Auditorias automáticas:
  - `python scripts/audit_frontend_standards.py --max-warnings 465`
    mantém a dívida histórica inventariada e bloqueia qualquer aumento na CI.
  - `python scripts/audit_django_architecture.py`

### Regras negativas (proibicoes)

- Nao colocar regra funcional pesada em `forms.py`.
- Nao colocar HTML em `services.py` ou `presenters.py`.
- Nao colocar query relevante em templates.
- Nao usar `href="#"` como acao.
- Nao usar CSS inline/JS inline em templates.
- Nao importar `legacy/` em runtime.

### Frontend global

- `templates/` com composicao por components e includes.
- `static/css/` com tokens + base + layout + sidebar + forms + buttons + cards + lists + domain + auth + themes.
- `static/js/` com `core`, `components` e `pages` (sem script inline no template).

### Preservacao obrigatoria de Roteiros

- O visual de `/roteiros/novo/` e referencia congelada.
- Evolucoes arquiteturais podem reorganizar includes, services, selectors e presenters.
- Nao alterar layout percebido, cores, espacamentos ou comportamento visual do wizard.

### Preservacao obrigatoria de Cadastros

- Manter regras atuais de CRUD, validacoes e bloqueio por `ProtectedError`.
- Manter exclusao fisica e sem ativo/inativo publico.
- Manter mascaras via `data-mask` e padrao de components.

## Configuracoes do sistema

A tela de configuracao segue o mesmo padrao arquitetural dos cadastros:

- view orquestra singleton, form, messages e redirect;
- `cadastros.services.salvar_configuracao_sistema()` persiste configuracao, resolve cidade sede e grava assinaturas por `update_or_create`;
- `cadastros.services.resolver_cidade_sede_por_endereco()` concentra a comparacao tolerante a acentos;
- `cadastros.selectors.build_configuracao_context()` prepara um contexto reutilizavel para documentos;
- API interna `/cadastros/api/cep/<cep>/` encapsula ViaCEP;
- JS da pagina fica em `static/js/pages/configuracoes.js`, enquanto mascaras globais permanecem em `static/js/components/masks.js`.

O app novo nao importa codigo do legacy em runtime; a tela apenas adapta as regras documentadas e auditadas do legacy.

## App documentos (núcleo base)

`documentos` deixa de ser placeholder puro e passa a expor um **núcleo documental reutilizável** em `documentos/services/`, com contrato para:

- tipos e formatos de documento;
- registro central de tipos suportados;
- validações por contrato;
- nomenclatura de arquivo;
- renderização via interface base (DOCX/PDF) com wrappers seguros.

Nesta etapa, o núcleo é infra de baixo acoplamento: sem CRUD completo de domínio e sem dependência obrigatória de conversor externo em runtime. Os apps de `oficios`, `termos`, `planos_trabalho` e `ordens_servico` devem consumir esse núcleo quando seus fluxos forem implementados.

### API técnica pública do núcleo documental v1

`documentos/services` expõe contratos estáveis para:

- exceções padronizadas (`DocumentError` e especializações por tipo, formato, template, renderer e placeholders);
- registro de tipos (`DocumentoRegistry` e `default_document_registry`) com proteção contra duplicidade;
- validação (`ensure_required_fields` e `DocumentValidatorRegistry`);
- templates (`DocumentTemplateRegistry` e `default_template_registry`);
- placeholders (`extract_placeholders`, `ensure_required_placeholders`, `ensure_no_unresolved_placeholders`);
- renderização controlada (`DocumentRenderRequest`, `DocumentRenderResult`, `DocumentRenderer`, `NoopDocumentRenderer`, `render_document`);
- resposta de download (`build_download_response`) sem acoplamento a view específica.

### Hardening V1.1 do núcleo documental

O núcleo documental V1.1 reforça contratos sem ampliar escopo funcional:

- `DocumentoRegistry` continua definindo formatos aceitos conceitualmente por tipo (DOCX/PDF);
- `DocumentTemplateRegistry` passa a validar duplicidade de `(tipo, formato)` e explicita ausência de template;
- `render_document` aplica ordem previsível de validação (tipo -> formato -> template -> placeholders -> renderer);
- PDF permanece como formato de contrato, sem promessa de conversão final de produção nesta etapa.

## App oficios (CRUD mínimo real)

`oficios` passa a ter uma implementação mínima funcional e document-centric:

- model `Oficio` com número/ano/protocolo/status/custeio e vínculos opcionais com roteiro, unidade, servidores, viatura e motorista;
- CRUD básico (`index`, `novo`, `detalhe`, `editar`, `excluir`) com views magras;
- camadas separadas por contrato (`forms`, `selectors`, `services`, `presenters`);
- sem geração DOCX/PDF final nesta fase, apenas preparação de payload por `build_oficio_document_payload`.

O app é o primeiro consumidor de referência para a evolução dos próximos módulos documentais.

## Fase 12.1 - Auditoria funcional do legado de Ofícios

A auditoria funcional do legado 2.0 consolidou que o fluxo de Ofícios antigo era composto por:

- wizard próprio de ofício (dados, transporte, roteiro/diárias e resumo);
- integração forte com evento e roteiro;
- documentos derivados (justificativa, termo, plano de trabalho, ordem de serviço);
- renderização DOCX/PDF com validações de prontidão e placeholders.

No 3.0, essa base é tratada como insumo de migração faseada, mantendo as decisões arquiteturais:

- sem import runtime de `legacy/`;
- regras de negócio em `services` e validações, não em templates;
- núcleo documental (`documentos/services`) como contrato transversal para tipos, formatos, templates, placeholders e renderização.

## Navegacao lateral

A navegacao principal e declarada em `core/navigation.py` e suporta hierarquia. O grupo `Cadastros` organiza:

- `Servidores`
  - `Cargos`
- `Viaturas`
  - `Combustiveis`
- `Unidades`
- `Configuracoes`

O estado ativo/aberto e preparado antes da renderizacao e o comportamento de abrir/fechar fica em JS centralizado. `Motoristas` nao e cadastro independente e nao deve aparecer no menu lateral. Estados/Cidades **nao** aparecem no menu; permanecem como base interna e importacao conforme `docs/IMPORTACAO_BASE_GEOGRAFICA.md`.

## Autenticacao

Fluxo documentado em `docs/AUTENTICACAO.md`: login e logout em `/login/` e `/logout/` (`core:login`, `core:logout`), sessao padrao do Django, sem cadastro publico. Paginas internas sao protegidas por `LoginRequiredMiddleware`; usuarios sao criados pelo admin ate haver modulo proprio.
