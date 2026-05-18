# ESTADO ATUAL - CENTRAL DE VIAGENS 3.0

## 1. Resumo executivo

O projeto esta em estado **hibrido e controlado**: a base arquitetural principal ja esta definida e operacional, com `cadastros` e `roteiros` como modulos referencia, enquanto o conjunto documental (oficios/termos/justificativas/planos/OS/prestacoes/diario) ainda esta em fase de consolidacao por etapas.

Os modulos mais maduros hoje sao:
- `cadastros` (CRUD consolidado, validacoes e regras de exclusao documentadas);
- `roteiros` (CRUD publico completo, selectors/services/presenters, components de dominio, mapa e calculos com divida controlada).

Modulos ainda em construcao:
- camada documental de negocio integrada (`documentos` + apps de dominio documental);
- convergencia plena das camadas arquiteturais em todos os apps;
- cobertura de testes ampla fora dos modulos referencia.

O padrao arquitetural atual e **Django modular por dominio, document-centric**, com contrato de camadas:
`models -> forms -> selectors -> services -> presenters -> views -> templates/components`.

O risco principal de continuar refatorando sem ordem e **quebrar convergencia arquitetural**: criar retrabalho entre apps documentais ainda incompletos, acoplar regras em views/templates e perder o alinhamento com o alvo document-centric ja assumido.

## 2. Apps existentes

| App | Funcao esperada | Estado atual | Models | Forms | Selectors | Services | Presenters | Views | URLs | Templates | Testes | Classificacao |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `core` | shell do sistema, autenticacao, navegacao e base transversal | base funcional, sem maturidade total de camadas | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Parcial |
| `usuarios` | ciclo de vida de usuarios/perfil do dominio | estrutura minima | Sim | Nao | Nao | Nao | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `cadastros` | dados-base (unidade, cargo, combustivel, servidor, viatura, configuracao) | consolidado e referencia | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Maduro |
| `roteiros` | roteiros avulsos/reutilizaveis, trechos, mapa, calculos | consolidado e referencia | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Maduro |
| `eventos` | agrupador opcional de documentos e fluxos por evento | app em preparacao, com rotas/telas base | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Sim | Placeholder |
| `documentos` | nucleo de renderizacao/geracao documental | preparacao de nucleo, sem cadeia fim a fim consolidada | Sim | Nao | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `oficios` | dominio principal de documento de viagem | preparacao de fluxo documental, ainda sem maturidade de referencia | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Sim | Nao | Placeholder |
| `termos` | termos de autorizacao e variacoes por fluxo | preparacao com estrutura inicial | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `justificativas` | regras de justificativa e modelos | preparacao com estrutura inicial | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `planos_trabalho` | planejamento operacional e derivacoes documentais | preparacao com estrutura inicial | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `ordens_servico` | ordens vinculadas a oficios/eventos | preparacao com estrutura inicial | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `prestacoes_contas` | prestacao, RT, comprovacoes e dossie | preparacao com estrutura inicial | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `diario_bordo` | diario operacional e exportacoes | preparacao com estrutura inicial | Sim | Sim | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `assinaturas` | trilha de assinatura e validacao | preparacao com base tecnica, sem consolidacao funcional | Sim | Nao | Nao | Sim | Nao | Sim | Sim | Sim | Nao | Placeholder |
| `integracoes` | conectores externos (ex.: Drive) | namespace/subapp ainda inicial | Parcial | Nao | Nao | Parcial | Nao | Parcial | Parcial | Sim | Nao | Placeholder |

## 3. Padroes oficiais atuais

### Backend

- **models:** regras de dominio, relacoes e constraints; normalizacao simples permitida; `TimeStampedModel` central ainda pendente.
- **forms:** validacao e normalizacao de entrada; mascaras via `data-mask`; sem regra funcional pesada.
- **selectors:** consultas reutilizaveis, filtro por `q`, `select_related/prefetch_related`.
- **services:** regra funcional, persistencia e transacao; exclusao protegida padronizada (`core/deletion.py`).
- **presenters:** payload de tela sem HTML (`title/subtitle/meta/actions/badges`).
- **views:** orquestracao HTTP magra (`form + selector + service + presenter + messages`).
- **urls:** convencao orientada a CRUD, mas com nomenclaturas mistas entre apps.
- **exclusao:** fisica, bloqueada por vinculo com mensagem padrao unica.
- **autenticacao:** sessao Django, login/logout, sem cadastro publico, protecao por middleware.
- **normalizadores:** `core/normalizers.py` e mascaras em `core/utils/masks.py`.
- **auditorias:** scripts dedicados de auditoria frontend e arquitetura Django.

### Frontend

- **CSS:** centralizado em `static/css/` com arquivos globais por responsabilidade.
- **tokens:** `tokens.css` + `theme.css`; politica de reduzir hardcode.
- **theme:** `data-theme` em `html`, persistencia em `localStorage`, init antecipado em JS dedicado.
- **componentes globais:** `templates/components/` (layout, forms, lists, cards, feedback, buttons).
- **componentes de dominio:** `templates/components/domain/` com Roteiros como referencia congelada provisoria.
- **templates:** composicao por components/includes, sem logica pesada de negocio.
- **JS:** centralizado em `static/js/core`, `static/js/components`, `static/js/pages`.
- **proibicoes:** sem inline CSS/JS, sem `href="#"`, sem dependencia runtime de `legacy/`.

### Regras de nao regressao

- proibido `href="#"`;
- proibido CSS inline;
- proibido JS inline;
- proibido exibir `updated_at`/`Atualizado em` como metadado padrao de lista;
- proibido `border-radius` hardcoded tipo `999px` (usar token);
- proibido cor hardcoded quando existir token semantico equivalente;
- proibido regra de negocio em template;
- proibido query relevante em view/template quando deve ir para selector;
- proibido presenter retornando HTML;
- proibido service depender de template/request sem excecao documentada;
- proibido uso runtime de `legacy/`.

## 4. Estado por modulo

### Cadastros

Estado atual: **consolidado e estavel** como modulo de base.

Consolidacao verificada para:
- Unidade;
- Cargo;
- Combustivel;
- Servidor;
- Viatura;
- Configuracao do sistema;
- Cidade como cadastro operacional visivel.
- Estado como base interna/administrativa (rota mantida sem destaque em navegacao principal).

Regras confirmadas na documentacao oficial:
- sem ativo/inativo para os cadastros operacionais;
- exclusao fisica com bloqueio por vinculo;
- Motorista nao e cadastro proprio (usa Servidor);
- Cargo e Combustivel com possibilidade de padrao;
- mascaras via `data-mask`;
- sem uso de "Atualizado em" como metadado de lista.

### Roteiros

Estado atual: **modulo referencia arquitetural** com dividas controladas.

Consolidacao confirmada:
- CRUD publico (listagem/novo/editar/detalhe/excluir);
- selectors dedicados;
- services com foco em `services/roteiro_editor`;
- presenters sem HTML;
- components de dominio;
- CSS com tokenizacao em progresso e contrato de preservacao visual;
- theme integrado;
- mapa e rota via backend;
- bloco de trechos/retorno/calculadora;
- documentacao explicita de divida controlada (`roteiro_logic`, extracao futura).

### Documentos

Estado atual: **intermediario** (nao placeholder puro, nem nucleo final pronto).

Mapeamento:
- registry/tipos e validadores: documentados no legacy map e parcialmente refletidos;
- renderer: existe pipeline legado robusto mapeado para migracao;
- placeholders: estrategia mapeada no legado;
- validators: mapeados como componente obrigatorio do nucleo;
- downloads/filenames/backends: mapeados e com direcao arquitetural;
- templates DOCX e conversao PDF: claramente documentados como nucleo futuro;
- relacao com Oficios/Termos/PT/OS: prevista, ainda parcial.

Com a fase "Nucleo Documental V1", o app passa a ter contratos técnicos testáveis para:

- exceções documentais padronizadas;
- registro e validação segura de tipo/formato;
- validação de placeholders e detecção de placeholders não resolvidos;
- registry de templates por tipo e formato;
- renderização controlada com renderer inicial seguro (sem dependência obrigatória de DOCX/PDF externo);
- helper de resposta de download com content type e filename centralizados.

Com a fase "Nucleo Documental V1.1 (hardening)", os contratos são reforçados com validação previsível de erros (tipo, formato, template, placeholders e renderer) e cobertura de testes ampliada. O núcleo segue sem geração DOCX/PDF final de produção nesta etapa.

### Oficios

Estado atual: **CRUD mínimo inicial com wizard em implantação**. O app já possui model real, forms, selectors, services, presenters, views, URLs e templates; o cadastro de Ofícios iniciou fluxo por etapas com a Etapa 1 "Dados e viajantes" implementada.

Mapeamento:
- models/forms/selectors/services/presenters/views/urls: existentes;
- wizard por etapas: Etapa 1 "Dados e viajantes" implementada com header "Cadastro de ofício", stepper visual acoplado ao cabeçalho e estados `not_started`, `current`, `incomplete`, `complete` e `locked`; etapas 2 a 5 aparecem como futuras/bloqueadas;
- layout do cadastro: segue estrutura `background > section > div interna`, sem resumo lateral;
- listagem: cards de Ofícios foram aproximados do padrão visual de Roteiros, com destaque para "N° do Ofício", status, protocolo, data, roteiro, solicitante, viajantes e ações;
- numeração: `numero` e `ano` não são preenchidos pelo usuário no wizard; o service reserva automaticamente o menor número disponível no ano, reaproveitando lacunas após exclusão, com exibição em dois dígitos (`01/2026`);
- fluxos documentais avançados: direção definida, maturação pendente;
- vinculo opcional com Roteiro/Evento: esperado e documentado como alvo;
- transporte, roteiro, trechos e diárias: alvo funcional claro, fora do escopo desta fase;
- documentos/justificativa/termos: alvo funcional claro, fora do escopo desta fase;
- geração DOCX/PDF final: ainda fora do escopo, dependente das próximas fases documentais.

### Termos, Justificativas, Planos e OS

**Termos**
- model proprio: Sim.
- CRUD proprio: parcial.
- dependencia de Oficio: prevista em fluxos.
- dependencia de Evento: prevista/legada.
- geracao documental: prevista, parcial.
- placeholder: nao puro, mas incompleto.
- migracao do legacy: necessaria e documentada.

**Justificativas**
- model proprio: Sim.
- CRUD proprio: parcial.
- dependencia de Oficio: estrutural no legado.
- dependencia de Evento: indireta por vinculos.
- geracao documental: prevista.
- placeholder: nao puro, mas incompleto.
- migracao do legacy: necessaria e documentada.

**Planos de Trabalho**
- model proprio: Sim.
- CRUD proprio: parcial.
- dependencia de Oficio: frequente no legado.
- dependencia de Evento: frequente no legado.
- geracao documental: prevista.
- placeholder: parcial.
- migracao do legacy: necessaria e extensa.

**Ordens de Servico**
- model proprio: Sim.
- CRUD proprio: parcial.
- dependencia de Oficio: frequente no legado.
- dependencia de Evento: frequente no legado.
- geracao documental: prevista.
- placeholder: parcial.
- migracao do legacy: necessaria.

## 5. Dividas tecnicas documentadas

- **CRITICA:** apps documentais ainda sem convergencia plena de arquitetura e fluxo funcional fim a fim.
- **ALTA:** nucleo documental (render/placeholder/validacao/download/conversao) ainda nao consolidado no novo projeto.
- **ALTA:** dependencia de referencia funcional do legacy para varios modulos documentais.
- **ALTA:** cobertura de testes desigual fora de `cadastros` e `roteiros`.
- **MEDIA:** `roteiro_logic` ainda concentra contexto pesado (divida controlada).
- **MEDIA:** components de dominio ainda muito ancorados nos partials de Roteiros (divida controlada).
- **MEDIA:** nomenclatura de URLs com convencoes mistas entre apps.
- **MEDIA:** auditorias automaticas existem, mas ainda sem integracao de enforcement no fluxo completo.
- **MEDIA:** `TimeStampedModel` ainda nao centralizado em `core`.
- **BAIXA/CONTROLADA:** hardcodes CSS remanescentes autorizados por contrato visual do wizard de Roteiros.
- **CONTROLADA:** contraste/theme com checklist ainda em aberto para fechamento 100%.

## 6. Conflitos ou documentacao desatualizada

- `README.md` ainda e mais operacional (setup) e pouco explicita o estado real por modulo e maturidade.
- `LEGACY_MODELS_MAP.md` contem pontos historicos que ja mudaram no novo (ex.: cita ausencia de `ConfiguracaoSistema` e `is_padrao` que hoje ja constam no projeto/documentacao atual), exigindo revisao de consistencia.
- mapas legacy (`LEGACY_*_MAP.md`) foram gerados em momentos diferentes e trazem niveis de atualizacao distintos; precisam consolidacao editorial.
- existe documentacao de transicao (`autosave.md`) sem vinculo explicito ao roadmap por modulo, podendo gerar expectativa de cobertura maior que a atual.
- parte dos relatorios de auditoria mistura "corrigido" com "pendencia controlada" sem matriz temporal unica.

## 7. Proxima fase recomendada

**Recomendacao principal: 5) iniciar nucleo documental.**

Justificativa:
- **menor risco arquitetural:** usa contratos ja definidos (selectors/services/presenters + configuracao institucional + regras document-centric);
- **maior impacto funcional:** destrava oficios/termos/justificativas/planos/OS e reduz dependencia do legado;
- **dependencias atendidas:** Cadastros e Roteiros ja estao maduros para servir de base;
- **aderencia ao alvo:** consolida o eixo document-centric assumido em toda a documentacao;
- **controle de escopo:** permite evolucao incremental com validadores, renderer e downloads padronizados antes de expandir todos os CRUDs documentais.

## 8. Matriz de prioridade

| Prioridade | Fase | Motivo | Risco | Impacto | Pre-requisito |
|---|---|---|---|---|---|
| 1 | Iniciar nucleo documental | destrava cadeia documental inteira e reduz acoplamento ao legacy | Medio | Muito alto | padroes backend/frontend ja definidos |
| 2 | Iniciar Oficios | principal consumidor do nucleo documental e maior valor funcional imediato | Medio | Alto | nucleo documental minimo (renderer/validators/downloads) |
| 3 | Migrar Termos/Justificativas | dependem de oficios/eventos e completam ciclo documental basico | Medio | Alto | oficios estabilizado + contratos de contexto |
| 4 | Migrar Planos/OS | fluxos mais densos com maior complexidade de regra | Alto | Alto | termos/justificativas estabilizados e padrao de services maduro |
| 5 | Criar auditorias automaticas (enforcement) | evita regressao de padrao durante expansao dos apps | Baixo | Medio/alto | scripts atuais consolidados em pipeline |
| 6 | Finalizar theme/contraste | fechamento de qualidade visual e acessibilidade | Baixo | Medio | sem bloquear backend documental |
| 7 | Estabilizar Prestacao/Diario | etapas dependentes de documentos e vinculos anteriores | Alto | Alto | cadeia documental principal operacional |

## 9. Fase 12.1 concluída (auditoria funcional)

Foi concluída a auditoria funcional do Ofício no legado 2.0, com quatro entregáveis documentais:

- `docs/OFICIOS_LEGACY_MAP.md`
- `docs/OFICIOS_MIGRATION_BACKLOG.md`
- `docs/OFICIOS_REGRAS_NEGOCIO.md`
- `docs/OFICIOS_COMPARATIVO_2_0_3_0.md`

Resultado prático da fase:

- mapeamento técnico dos artefatos legacy (models, forms, views, urls, services, templates, JS e templates DOCX);
- extração e priorização de regras de negócio para migração controlada;
- backlog faseado de implementação (Fase 13 a Fase 23) alinhado ao padrão document-centric;
- diagnóstico de lacunas entre o CRUD mínimo atual e o comportamento funcional legado completo.

## 10. Atualização mais recente em Ofícios (Etapa 1)

- Etapa 1 mantida como **Dados e viajantes**, sem bloco de assunto manual e sem contexto operacional.
- `data_criacao` passou a ser automática no backend e informativa no wizard.
- `protocolo` passou a aceitar entrada com ou sem máscara, persistindo em dígitos e exibindo formatado.
- `status` passou a ser automático, com base em completude da etapa e ação de salvamento.
- `ModeloMotivoOficio` foi adicionado para gerenciamento de modelos de motivo ativos/inativos.
- seleção de viajantes recebeu filtro progressivo em frontend, preservando submissão via `<select multiple>`.
- no GET de `/oficios/novo/`, os informativos de N° do Ofício, Data criação e Status agora aparecem imediatamente antes de salvar.
- `custeio_observacao` passou a ter exibição condicional quando `custeio=Outra instituição`, mantendo validação obrigatória no backend.
- gerenciador de modelos de motivo foi exposto no fluxo da Etapa 1 com botão "Gerenciar modelos" e CRUD dedicado.
