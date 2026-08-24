# Inventário estático de páginas e navegação

> Eixo A da apresentação do sistema. Levantamento feito por leitura estática em
> 24/08/2026, sem navegador, sem acessar banco e sem executar views. Os IDs `PG-*`
> abaixo são identificadores provisórios deste inventário; não são IDs do catálogo
> de defeitos.

## 1. Escopo, método e números

- Roteador raiz: `config/urls.py:10-31`.
- 14 namespaces de aplicação: `core`, `usuarios`, `cadastros`, `roteiros`,
  `eventos`, `documentos`, `oficios`, `termos`, `justificativas`,
  `planos_trabalho`, `ordens_servico`, `protocolos`, `prestacoes_contas` e
  `google_drive` (`config/urls.py:17-30`).
- 268 chamadas `path()` declaradas nos 14 roteadores de aplicação (266 ficam
  ativas fora de `DEBUG`). O roteador raiz
  acrescenta `/admin/login/`, `/admin/` e os 14 `include()`; em `DEBUG`, o `core`
  acrescenta duas rotas do UI Lab e o projeto serve `MEDIA_URL`
  (`config/urls.py:33-34`; `core/urls.py:18-25`).
- Distribuição dos 268 padrões: core 8; cadastros 32; documentos 8; eventos 20;
  Google Drive 12; justificativas 12; ofícios 31; ordens de serviço 9; planos de
  trabalho 33; prestações de contas 52; protocolos 6; roteiros 11; termos 23;
  usuários 11.
- 357 templates HTML em `templates/`, dos quais 214 pontos usam `{% include %}`;
  há 1.572 invocações de componentes Cotton `c-v2`.
- 32 controladores JS de página e 30 componentes JS de produção em
  `static/js/pages/` e `static/js/components/` (testes excluídos da contagem).
- 67 classes declaradas nos `models.py` auditados (inclui 2 abstratas e managers)
  e 77 classes nos módulos de formulários (inclui widgets/mixins).

Limite de interpretação: “página” abaixo significa uma rota que renderiza HTML ou
um estado visual alcançável por redirecionamento. APIs JSON, downloads, conteúdo
binário, POSTs de ação e fragmentos de menu aparecem também, pois são parte do
grafo funcional da página, mas não são contados como telas independentes.

## 2. Regras transversais de acesso e composição

### PG-001 — autenticação, área e papel

Com o padrão `LOGIN_ENFORCED=true`, toda view exige login pelo
`AjaxAwareLoginRequiredMiddleware`; o ambiente de desenvolvimento pode desligar
esse portão, e páginas deliberadamente anônimas declaram `login_not_required`
(`config/settings/base.py:100-107`). Uma sessão expirada vira redirect
em páginas e JSON 401 em AJAX (`core/middleware.py:176-219`). A área ativa é
resolvida antes da view (`core/middleware.py:222-230`). Um vínculo `LEITOR` pode
usar GET/HEAD/OPTIONS, mas recebe 403 em mutações, salvo logout e perfil
(`core/middleware.py:233-269`). A hierarquia de papel é LEITOR < EDITOR < ADMIN e
superusuário sempre satisfaz o papel (`core/permissions.py:7-22`).

Exceções públicas comprovadas:

- `/health/`, `/metrics/` e as duas páginas do UI Lab quando `DEBUG`
  (`core/views.py:28-43`, `core/views.py:233-256`);
- `/login/`, naturalmente controlada pela própria `LoginView`
  (`core/views.py:73-75`);
- `/admin/login/`, com limitação de tentativas (`config/urls.py:10-16` e
  `core/admin_login.py:25-35`);
- conteúdo PDF por token temporário em
  `/documentos/artefatos/conteudo-publico/?t=...`
  (`documentos/views.py:70-84`);
- fluxo de assinatura por token em cinco URLs `prestacoes_contas:assinatura_*`
  (`prestacoes_contas/urls.py:118-123`; `prestacoes_contas/assinatura_views.py:125-290`).

Usuários e áreas têm um segundo portão: todas as 11 views usam
`@somente_administrador`, que aceita apenas `is_staff`/`is_superuser`
(`usuarios/views.py:31-42`, `usuarios/views.py:68-356`). Configuração de valores de
diária é editável somente por superusuário; os demais veem o conteúdo somente para
leitura e uma tentativa de POST gera `PermissionDenied`
(`cadastros/views.py:625-732`, em especial `:653-655`).

### PG-002 — shell, includes e modais

`base.html` monta o shell e carrega os componentes globais/lazy de card, arquivo,
anexo assinado, assinatura, download extra e cabeçalho de wizard
(`templates/base.html:47-56`). A composição de telas usa 214 includes; os núcleos
mais importantes são:

- formulários compartilhados: `templates/includes/form_components_css.html` e
  `templates/includes/form_components_js.html`;
- editor de roteiro: `templates/roteiros/includes/_roteiro_editor_v2.html:60-69`;
- wizard de evento: `templates/eventos/includes/_evento_form_sections.html:9-22`;
- shell de ofício: `templates/oficios/wizard_base.html`;
- shell de plano: `templates/planos_trabalho/wizard_base.html:32-59`;
- shell de prestação: `templates/prestacoes_contas/flow_base.html`, estendido por
  documentos, RT, diário, troca de motorista e consolidado;
- cartões de lista e menus sob demanda: `*/partials/*_list_card.html` e
  `*/partials/_card_menus.html`.

Há quatro famílias de diálogo reutilizável — exclusão, cancelamento com motivo,
confirmação e anexação de assinado — sobre `<dialog>` nativo
(`templates/cotton/v2/modal.html:31`; `delete_modal.html:30-62`;
`cancel_modal.html:27-63`; `confirm_modal.html:26-56`;
`attach_signed_modal.html:46-119`). O motor é
`static/js/components/overlay.js:25-56`. Há ainda download picker
(`templates/cotton/v2/download_picker.html:38-132`) e os modais específicos de
vincular usuário (`templates/usuarios/partials/_vincular_usuario_modal.html:1-22`
e `_vincular_na_area_modal.html:2-24`). Menus de card são fragmentos GET carregados
somente no primeiro clique para eventos, ofícios, OS, planos e prestações
(`*/card_menu_views.py:19-25`).

## 3. Menu principal e páginas fora dele

### PG-003 — o que aparece no menu

O menu declarado em `core/navigation.py:8-100` expõe:

1. Dashboard.
2. Planejamento: Eventos, Roteiros, Planos de Trabalho, Ordens de Serviço.
3. Documentos: Ofícios, Termos, Justificativas, Protocolos.
4. Execução e prestação: Prestações de Contas.
5. UI Lab, apenas em `DEBUG` (`core/navigation.py:48-70`, `:147-159`).
6. Administração: Servidores, Cargos, Viaturas, Combustíveis, Unidades,
   Configurações; Usuários e Áreas aparecem apenas para staff/superusuário
   (`core/navigation.py:72-99`, `:147-159`).

### PG-004 — páginas alcançáveis fora do menu

As seguintes páginas existem por URL direta, redirect, botão contextual ou link de
perfil, mas não são itens próprios do menu:

- `/admin/`, `/login/`, `/logout/`, `/perfil/`, health e metrics;
- hub `/cadastros/`, Estados, Cidades, Tipos de Evento, Modelos de Motivo de
  Ofício, Modelos de Justificativa, Programas, Horários, Atividades, Presets e
  Modelos de texto do RT;
- `/documentos/` (painel técnico do núcleo documental), viewer de PDF e telas de
  espera de geração;
- todos os wizards/detalhes/edições/exclusões, páginas de preview e downloads;
- integração Google Drive, incorporada ao Perfil, sem página principal própria
  (`templates/core/perfil.html:47-62`);
- fluxo público de assinatura por token;
- aliases legados de Justificativas e Evento;
- criação/edição administrativa do usuário, realizadas por redirect/modais, não
  por uma tela separada para todos os nomes de rota.

## 4. Inventário por namespace

### PG-010 — `core` (`core/urls.py:7-25`)

Rotas: `health`, `metrics`, `login`, `logout`, `perfil`, `dashboard` e, em DEBUG,
`main_preview`/`main_preview_secao`. Templates: `core/login.html`,
`core/login_bloqueado.html`, `core/dashboard.html`, `core/perfil.html` e
`core/main_preview.html` + nove seções em `core/main_preview/`
(`core/views.py:73-117`, `:234-265`, `:504-563`). Forms:
`LoginForm`, `PerfilUsuarioForm`, `AlterarSenhaForm`
(`core/forms/__init__.py:12-86`). Modelos próprios: abstratos `TimeStampedModel`,
`CancelavelModel` e `AuditEvent` (`core/models.py:8-37`); dashboard lê `Evento`
(`core/views.py:17-20`). Serviços/integrações: cartões de entidades, throttle de
login, cache, Google Drive e dados dos vínculos de área. JS específico do perfil:
`gdrive-config.js`; o UI Lab carrega `download-queue.js` e `font-try.js`.

### PG-011 — `cadastros` (`cadastros/urls.py:5-44`)

32 padrões:

- hub `index`; configuração geral e por aba (`configuracao`,
  `configuracao_aba`); API CEP (`api_consulta_cep`);
- Estados: `estados_index`, `estado_update`, `estado_delete`;
- Unidades: `unidades_index`, alias de criação `unidade_create`, update/delete;
- Cargos e Combustíveis: index, alias de criação, update, definir padrão, delete;
- Cidades: index/alias de criação e exportação CSV;
- Servidores e Viaturas: index/create/update/delete.

Views diretas estão em `cadastros/views.py:121-760`; os CRUDs de catálogo são
gerados por `core.catalog` a partir de `cadastros/catalogs.py:81-190`. Templates:
hub, configuração, cinco catálogos e formulários/confirm-delete de servidor e
viatura. Forms: `UnidadeForm`, `EstadoForm`, `CidadeForm`, `CargoForm`,
`CombustivelForm`, `ServidorForm`, `ViaturaForm`, três forms de configuração e
`TabelaDiariaForm` (`cadastros/forms.py:152-830`). Modelos: Unidade, Estado,
Cidade, Cargo, Combustível, Servidor, Viatura, Configuração, configuração de
assinatura e Tabela de Diária (`cadastros/models.py:16-737`). Services: CRUD,
proteção de vínculo, sede, CEP e importação geográfica
(`cadastros/services.py:38-328`; `services_importacao.py:171-632`). JS:
`configuracoes.js` -> API CEP; `servidores-form.js`; `viaturas-form.js`;
`diaria-derivados.js`. Rascunhos de Servidor/Viatura são preservados e a listagem
filtra por cargo/unidade/combustível (`cadastros/views.py:300-620`).

### PG-012 — `documentos` (`documentos/urls.py:6-25`)

8 padrões: `index`; status/resultado de geração; visualizar/conteúdo do artefato;
conteúdo público por token; anexar/remover versão assinada. Views e templates em
`documentos/views.py:34-160`: `documentos/index.html` e `pdf_viewer.html`; as
telas `geracao_aguarde.html`/`geracao_aguarde_embedded.html` são escolhidas pelo
serviço assíncrono (`documentos/services/async_generation.py:329-333`). Modelos:
`DocumentoArtefato`, `DocumentoGeracao`, `DocumentoAssinaturaVersao`
(`documentos/models.py:9-192`). O domínio não tem forms.py; upload assinado é
tratado pelo serviço de persistência. JS: `document-generation-wait.js` consulta
status/resultado; `documentos-pdf-viewer.js` + PDF.js exibem e copiam link
temporário (`templates/documentos/pdf_viewer.html:19-86`).

### PG-013 — `eventos` (`eventos/urls.py:7-46`)

20 padrões: index/novo; API de cidades por UF; catálogo Tipos; detalhe; fragmento
`menus`; três variantes do fluxo guiado (`guiado`, `guiado_etapa`, alias legacy e
`guiado_termos`); editar/excluir/cancelar/reativar; conteúdo de anexo; anexar,
ver e excluir solicitação. A mesma view `detalhe` atende painel e etapas 1–5
(`eventos/views.py:287-418`); `novo` redireciona à etapa 1
(`eventos/views.py:249-269`). Templates: index, form, detalhe de cinco etapas,
catálogo de tipos e fragmentos/cards. Forms: `EventoNovoCadastroForm`,
`EventoForm`, `TipoEventoForm` (`eventos/forms.py:111-365`). Modelos: Evento,
Tipo, ModeloMotivoEvento, DocumentoSolicitação e Anexo
(`eventos/models.py:14-317`). Services: salvar identificação, anexos, termo
automático, exclusão, seeds de documentos e contexto guiado
(`eventos/services.py:57-453`). JS: `eventos-detalhe.js` e
`oficios-dados-viajantes.js`; dependências de cidades usam
`roteiros:api_cidades_por_estado`. Estado: cancelado mostra alerta e botão de
reativar; cancelamento propaga aos documentos, e reativação só desfaz os
cancelamentos em cascata (`eventos/views.py:488-515`;
`templates/eventos/detalhe.html:44-52`).

### PG-014 — `google_drive` (`integracoes/google_drive/urls.py:5-32`)

12 padrões sem tela autônoma: OAuth iniciar/callback/revogar; listar pastas,
drives compartilhados e “compartilhados comigo”; criar pasta/salvar raiz;
reorganizar, prévia e polling de status; reprocessar pendências. Todas as views
têm `login_required` e mutações declaram POST
(`integracoes/google_drive/views.py:66-463`). A interface vive no Perfil
(`templates/core/partials/_gdrive_card_body.html`) e usa
`gdrive-config.js` -> seis endpoints via `CV.http.fetchJson`
(`static/js/pages/gdrive-config.js:16-19`, `:179-296`, `:337-463`). Modelos:
credenciais, job, arquivo interno/externo e status de sync
(`integracoes/google_drive/models.py:9-174`). Services abstraem cliente
mock/real, autorização, upload e sincronização (`services.py:43-592`). A ação de
reorganizar só aparece quando `drive_pode_reorganizar`
(`templates/core/partials/_gdrive_diretorio_body.html:20`, `:98-115`).

### PG-015 — `justificativas` (`justificativas/urls.py:6-21`)

12 padrões: index, API de busca de ofícios, excluir justificativa; CRUD/definir
padrão de modelos; quatro aliases legados (`novo`, editar, padrão, excluir) que
apenas redirecionam ao índice de modelos (`justificativas/views.py:171-172`). A
criação/edição de justificativa ocorre na própria lista/quick-add, não em páginas
dedicadas (`justificativas/views.py:86-168`). Templates: index e catálogo de
modelos. Forms: `JustificativaOficioForm`, `JustificativaQuickAddForm`,
`ModeloJustificativaForm` (`justificativas/forms.py:31-134`). Modelos: Modelo e
Justificativa (`justificativas/models.py:10-95`). Services decidem antecedência,
obrigatoriedade, completude e persistência (`services.py:22-329`). JS:
`justificativas-index.js`; o picker consulta `api_buscar_oficios`. Estados:
rascunho/finalizada e aplicabilidade obrigatória/opcional/não aplicável são
derivados pelo service, não pelo template.

### PG-016 — `oficios` (`oficios/urls.py:6-64`)

31 padrões:

- index/novo; catálogo Modelos de Motivo (index/create/update/default/delete);
- detalhe, menus e editar (redirects ao wizard);
- etapas `dados_viajantes`, `transporte`, `roteiro`, `justificativa`, `resumo`
  (alias da etapa documental) e `documentos`;
- quatro autosaves: viajantes, transporte, criar roteiro e justificativa;
- API de viatura por placa;
- previews PDF inline de ofício/justificativa/OS;
- downloads por formato do ofício, justificativa e OS;
- excluir, cancelar, retificar e marcar complementar.

O agregador `oficios/views.py:3-34` reexporta views especializadas: lista
(`list_views.py:92-150`), viajantes/transporte (`traveler_views.py:221-310`),
roteiro (`route_views.py:51-244`), documentos/justificativa
(`wizard_document_views.py:72-179`), downloads (`document_views.py:42-110`) e
ciclo de vida (`lifecycle_views.py:43-105`). Templates: lista, wizard base + cinco
telas e catálogo. Forms: `OficioForm`, `OficioDadosViajantesForm`,
`OficioTransporteForm`, `ModeloMotivoOficioForm` (`oficios/forms.py:150-594`).
Modelos: Ofício, configuração/lacuna de numeração e modelo de motivo
(`oficios/models.py:25-407`). Services cobrem roteiro, persistência parcial,
numeração, avaliação das etapas, validação/geração documental e ciclo de vida
(`oficios/services.py:121-1163`). JS: controladores de viajantes, transporte,
motorista, sugestão de viatura, justificativa, documentos inline e o editor de
roteiro. Condicionais: ofício cancelado perde ação de edição e ganha nota/estado;
retificado e complementar geram chips próprios
(`oficios/presenters.py:423-481`). Documento incompleto redireciona à etapa que
precisa de correção (`oficios/document_views.py:16-31`).

### PG-017 — `ordens_servico` (`ordens_servico/urls.py:7-19`)

9 padrões: index, API de ofícios, nova, editar, menus, DOCX, PDF inline, download
PDF e excluir. Templates: index/form + cards/menus. `nova`/`editar` compartilham
`OrdemServicoForm` e `ordens_servico/form.html`
(`ordens_servico/views.py:483-524`); API/downloads estão em `:423-558`. Modelo:
`OrdemServico` + lacunas de numeração (`ordens_servico/models.py:24-326`).
Services: exclusão e geração/caching DOCX/PDF (`services.py:39-199`). JS:
`ordens-servico-form.js` usa picker de ofícios e alterna papéis; a lista carrega
menus sob demanda. O botão finaliza apenas quando o presenter considera a OS
completa; caso contrário salva rascunho
(`templates/ordens_servico/form.html:84`).

### PG-018 — `planos_trabalho` (`planos_trabalho/urls.py:6-42`)

33 padrões:

- index/novo;
- catálogos Programas, Horários, Atividades e Presets, com update/delete e default
  onde aplicável;
- editar, menus e quatro etapas: identificação, efetivo/diárias, atividades,
  documentos;
- autosave das três etapas editáveis e API de cálculo de diárias;
- adicionar/editar/remover subevento;
- PDF inline/download por formato e excluir.

O agregador `planos_trabalho/views.py:3-31` divide lista, identificação,
efetivo/diárias, atividades e documentos. Templates: index; wizard base + quatro
telas; quatro catálogos. Forms principais: `PlanoIdentificacaoForm`,
`PlanoDiariasForm`, formset de `EfetivoPlano`, `EventoPlanoForm`,
`EfetivoEventoForm` e forms de catálogo (`planos_trabalho/forms.py:50-874`).
Modelos: quatro catálogos; Plano, Destino, Efetivo, EventoPlano e EfetivoEvento
(`models.py:26-927`). Services: identificação, reconciliação do efetivo, cálculo e
snapshot de diárias, textos, atividades, metas e geração de documento
(`identificacao_services.py:36-62`; `efetivo_services.py:47-131`;
`services.py:393-1298`). JS: `planos-trabalho-wizard.js` controla três telas,
autosaves, linhas dinâmicas e `api_calcular_diarias`; documentos reutilizam
`oficios-documentos-inline.js`. Estado de cada etapa é apresentado como não
iniciada/incompleta/completa (`planos_trabalho/presenters.py:185-280`).

### PG-019 — `prestacoes_contas` (`prestacoes_contas/urls.py:8-128`)

52 padrões, organizados pelo identificador canônico `PrestacaoServidor`:

- downloads: índice JSON, compilado e assinado por item/formato;
- por servidor: arquivar, finalizar, documentos, RT, diário, consolidado e menu;
- aliases por `PrestacaoContas` redirecionam ao primeiro servidor para arquivar,
  finalizar, documentos, RT, diário, troca de roteiro/motorista e consolidado;
- autosaves de despacho, solicitação, comprovante, RT e diário;
- anexar ofício/despacho/RT/DB assinados, remover/ver anexos; ajustar/ver PDF cru
  do carimbo;
- downloads de RT, diário e consolidado;
- gerar/cancelar links de assinatura de RT/DB;
- cinco rotas públicas de assinatura por token;
- catálogo de modelos de texto (index/update/delete).

Templates: index; `flow_base.html`; documentos; RT; diário; troca de motorista;
consolidado; carimbo; três telas do catálogo; cinco telas públicas de assinatura.
Views são divididas em `document_views.py`, `rt_views.py`, `diario_views.py`,
`download_views.py`, `signature_views.py`, `assinatura_views.py` e
`model_views.py`, reexportadas por `prestacoes_contas/views.py:19-165`. Forms:
trecho, motorista, despacho, documentos, solicitação, diária, relatório técnico e
modelo de texto (`prestacoes_contas/forms.py:34-728`). Modelos: Prestação,
PrestaçãoServidor, anexos, carimbo, RT, Diário/trecho, Assinatura e Modelo de texto
(`models.py:51-864`). Services especializados cobrem anexos, assinatura, carimbo,
diário, download, RT, solicitação e consolidação. JS: RT, diário motorista,
carimbo, assinatura/identidade, WhatsApp de diária/documentos,
documentos-inline e download queue. Estados de lista são não liberada, liberada,
finalizada e arquivada (`prestacoes_contas/views.py:87-94`, `:344-443`); leitor
não pode acionar os POSTs pelo portão transversal.

### PG-020 — `protocolos` (`protocolos/urls.py:6-20`)

6 padrões: index, criar, vincular manualmente, detalhe, atualizar/sincronizar e
enviar documento. Todas as views reafirmam `login_required`
(`protocolos/views.py:29`, `:63-257`). Templates: index, detalhe, formulário de
criação/vínculo e envio. Forms existentes: vínculo manual, anexar documento,
solicitar assinatura, tramitar e protocolar ofício (`protocolos/forms.py:16-146`).
Modelos: Protocolo, Documento, Assinatura, Pendência, Tramitação, Movimentação e
Log (`protocolos/models.py:31-587`). Services já implementam demo/real, criação,
vínculo, envio, conclusão, assinatura, tramitação e sincronização
(`protocolos/services.py:167-1041`). O detalhe mostra documentos, pendências,
assinaturas, tramitações e movimentações (`templates/protocolos/detalhe.html:35-102`).

### PG-021 — `roteiros` (`roteiros/urls.py:6-20`)

11 padrões: index/novo/editar/excluir; criar/autosalvar; API cidades; calcular
diárias; estimar trechos; calcular rota persistida e preview. Templates: index,
form page, editor compartilhado e confirmação de exclusão
(`roteiros/views.py:126-410`). Form: `RoteiroForm` (`roteiros/forms.py:8`).
Modelos: Roteiro, componente de diária, destino e trecho
(`roteiros/models.py:14-356`). Services: fluxo/persistência do editor, diárias,
estimativa local e provedores de rota (`roteiros/views.py:22-69`). JS:
`roteiros.js` importa o editor (`editor/index.js`, `mapa.js`, `trechos.js`), além
de `roteiros-wizard.js`, `roteiros-map.js` e source-toggle. O formulário publica
por `data-*` todos os endpoints de cidades, diárias, estimativa, rota, preview e
autosave (`templates/roteiros/includes/_roteiro_editor_v2.html:60-69`). Quando
vinculado a Evento, retorno/salvamento vão para a etapa 2 do evento
(`roteiros/views.py:76-84`, `:233-236`).

### PG-022 — `termos` (`termos/urls.py:6-86`)

23 padrões:

- index, busca de ofícios, novo/editar/excluir;
- JSON de downloads e previews/downloads genérico, por viatura e por servidor;
- anexar assinado genérico e por servidor;
- preview de termos do ofício, PDF inline/anexar assinado/download por servidor,
  PDF consolidado e lote ZIP.

Templates: index, form, preview de ofício e seus partials; o form inclui preview
inline e download picker. Form/modelo: `TermoAutorizacaoForm` e
`TermoAutorizacao` (`termos/forms.py:46`; `termos/models.py:16`). Services geram
artefatos avulsos/vinculados, resolvem variantes e assinados e fundem lotes
(`termos/services.py:44-710`). JS: `termos-form.js` -> API de busca de ofícios e
cidades; `oficios-documentos-inline.js`; `download-queue.js`. A ordem das rotas é
deliberada para literais `pdf-inline`/`assinado` não serem capturados por
`<str:formato>` (`termos/urls.py:38-59`). Termo vinculado a Evento retorna à etapa
5 (`termos/views.py:187-213`).

### PG-023 — `usuarios` (`usuarios/urls.py:6-20`)

11 padrões, todos administrativos: usuários index/create/update/delete; criar e
remover vínculo; áreas index/create/update/delete; vincular dentro de uma área.
Somente index, áreas index e área update renderizam páginas diretamente
(`usuarios/views.py:69-218`); create/update/delete de usuário e vínculo operam por
POST/redirect (`:231-356`). Templates: índices, área form, shell genérico de
usuário e dois modais de vínculo. Forms: criação/edição de área, criação/edição de
usuário e dois forms de vínculo (`usuarios/forms.py:56-254`). Modelos:
`AreaTrabalho` e `VinculoUsuarioArea` (`usuarios/models.py:7-30`). Services:
CRUD/vínculo e proteção contra autoexclusão (`usuarios/services.py:26-71`). JS:
`usuarios-admin.js` e `usuarios-area-form.js`; ações de editar/vincular são
passadas por `data-edit-url`/`data-vincular-url`.

## 5. Contratos JS -> endpoints

### PG-030 — matriz resumida

- Autosave global (`static/js/autosave.js:53-115`) usa `data-autosave-url`,
  `data-autosave-create-url` e template de URL; consumidores: Ofícios, Roteiros,
  Planos e Prestações.
- Localidades (`static/js/components/location-rows.js:116-129`) consomem
  `roteiros:api_cidades_por_estado`; Eventos também possui sua API por UF.
- Picker remoto (`static/js/components/document-search.js:55-72`) consome busca
  de ofícios de Justificativas, OS e Termos.
- Rotas/diárias (`static/js/pages/roteiros/editor/index.js:34-37`, `:844`,
  `:1442`; `roteiros-map.js:526-557`) consomem cinco endpoints de Roteiros.
- Plano (`planos-trabalho-wizard.js:549-558`) consome cálculo de diárias e os
  autosaves de etapa.
- Google Drive (`gdrive-config.js:16-19`, `:179-296`, `:337-463`) consome listar,
  criar, prévia e status.
- Geração (`document-generation-wait.js:6-10` e
  `document-download.js:141-238`) consome status/resultado e downloads.
- Anexo assinado (`attach-signed-modal.js:32-41`, `:354-501`) usa URLs fornecidas
  por cada card para anexar/remover/ver documento.
- Menus (`overlay.js`) fazem GET dos cinco fragmentos `:card_menus` e submetem
  ações delete/cancel/confirm/vincular por atributos de dados.

Não foi encontrado `fetch()` cru nesses contratos; a comunicação observada passa
por `CV.http.request`/`fetchJson`.

## 6. Lacunas e pontos de atenção comprováveis

### PG-100 — protocolo tem forms/services e métodos de URL sem rotas (lacuna real)

`Protocolo` expõe `get_solicitar_assinatura_url`, `get_tramitar_url`,
`get_concluir_url`, `get_movimentacoes_url` e `get_logs_url`, todos fazendo
`reverse()` para nomes ausentes (`protocolos/models.py:139-152`). Há forms e
services para assinatura, tramitação e conclusão (`protocolos/forms.py:80-146`;
`protocolos/services.py:683-806`), mas `protocolos/urls.py:13-20` registra apenas
seis rotas. O próprio comentário do roteador e o docstring das views dizem que
essas ações ficaram para a “fatia 2” (`protocolos/urls.py:8-12`;
`protocolos/views.py:1-11`). Consequência: chamar hoje qualquer um desses cinco
métodos de URL gera `NoReverseMatch`; a UI atual evita chamá-los.

### PG-101 — template de preview avulso sem produtor de produção

`templates/termos/preview_cadastro.html` existe e inclui
`_preview_cadastro_body.html`, mas nenhuma view, URL ou include de produção o
referencia. A busca de repositório encontrou apenas menção em auditoria histórica.
O fluxo ativo de termo avulso faz preview dentro de `termos/form.html`
(`termos/views.py:480-558`; `templates/termos/form.html:91`). Deve ser documentado
como template sem página ativa, não como tela apresentável.

### PG-102 — nomes de rota que são aliases, não páginas distintas

- `eventos:guiado`, `guiado_etapa`, `guiado_etapa_legacy` compartilham a mesma
  view/template (`eventos/urls.py:18-20`).
- `eventos:guiado_termos` só encaminha à etapa 5 (`eventos/views.py:470-471`).
- `oficios:detalhe` e `editar` encaminham ao wizard; `wizard_resumo` usa a tela de
  documentos (`oficios/list_views.py:141-150`; `oficios/urls.py:35-37`).
- aliases antigos de Justificativas ignoram o `pk` e redirecionam ao catálogo
  (`justificativas/views.py:171-172`).
- aliases por `PrestacaoContas` escolhem o primeiro `PrestacaoServidor`
  (`prestacoes_contas/view_common.py:183-188`).
- `unidade_create`, `cargo_create`, `combustivel_create` e `cidade_create`
  reutilizam as páginas index correspondentes (`cadastros/urls.py:16-34`).

Uma apresentação que trate cada nome de rota como uma tela inflará artificialmente
o total e repetirá imagens.

### PG-103 — páginas técnicas/condicionais não devem entrar no roteiro comum

`documentos:index` é diagnóstico do núcleo/registry, não catálogo de documentos
do usuário (`documentos/views.py:34-49`). UI Lab só existe em DEBUG. Health,
metrics, callbacks OAuth, APIs, conteúdo binário, polling, downloads, autosaves e
fragmentos de menu são superfícies técnicas. Devem aparecer no diagrama de
arquitetura/endpoints, não no tour de telas.

### PG-104 — visibilidade no menu não equivale a autorização completa

O menu só esconde Usuários/Áreas por `staff_only`; os outros itens administrativos
ficam visíveis para usuários autenticados (`core/navigation.py:72-99`). A escrita
é bloqueada transversalmente para LEITOR e a edição de diárias exige
superusuário. Portanto, capturas e manuais precisam distinguir “item visível”,
“página acessível em leitura” e “ação permitida”.

## 7. Sequência de telas recomendada para apresentação

Sem executar o sistema, o grafo estático sugere esta ordem sem duplicar aliases:

1. Login -> Dashboard -> Perfil/área/Drive.
2. Cadastros-base e configurações.
3. Evento guiado: identificação -> roteiro -> ofício -> solicitação ->
   plano/OS -> termos.
4. Ofício em detalhe: viajantes -> transporte -> roteiro -> justificativa ->
   documentos/assinados.
5. Plano: identificação -> efetivo/diárias -> atividades -> documentos.
6. Execução: prestação liberada -> documentos -> RT -> diário -> consolidado ->
   finalizar/arquivar.
7. Protocolo: criar/vincular -> detalhe -> sincronizar -> enviar documento,
   explicitando que assinatura/tramitação/conclusão ainda não têm rota/UI.
8. Fluxo público de assinatura por token.

Esse roteiro cobre as páginas funcionais, os estados e as integrações sem contar
como “tela nova” cada API, download, modal, alias ou fragmento sob demanda.
