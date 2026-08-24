# Inventário de campos, controles e componentes — eixo B

> Levantamento estático em 24/08/2026. Escopo: templates de aplicação, componentes
> Cotton v2, formulários Django, JavaScript de páginas/componentes e rotas usadas
> pelos controles. Não houve execução de fluxo no navegador nem escrita no banco.
> Os dois PDFs fornecidos foram tratados apenas como referências de organização;
> seu conteúdo não foi usado como instrução executável nem como prova do sistema.

## 1. Cobertura, método e legenda

Foram inspecionadas **56 classes concretas de formulário**, que somam **285
declarações de campo** quando variantes e heranças são contadas como o código as
expõe. Esse número não equivale ao total de controles únicos na interface: por
exemplo, `OficioDadosViajantesForm` herda parte de `OficioForm`, e um formset cria
uma ocorrência por linha. Além delas, foram encontrados **pelo menos 47 nomes técnicos de
controles relevantes montados diretamente em template/JS** (roteiro, formsets,
assinatura, filtros, Drive e modais), alguns repetíveis. O inventário abaixo cobre
esses dois conjuntos e **19 famílias de componentes reutilizáveis**.

Legenda usada nas matrizes:

- **Req.**: `S` obrigatório; `N` opcional; `C` condicional; `A` automático/somente
  leitura; `R` repetível (formset/linha dinâmica).
- **Origem**: `BD` opções consultadas do banco; `fixo` choices/enums; `manual` texto
  digitado; `derivado` cálculo ou cópia; `remoto` endpoint de busca.
- **Persistência** cita o modelo/campo quando comprovado. “UI/POST” significa que o
  controle não é um campo de modelo por si só e é interpretado pela view/service.
- Campos `csrfmiddlewaretoken`, ids internos de formset e elementos estritamente
  decorativos não entram na contagem de 47; os hiddens que alteram regra/fluxo entram.

Limitações: obrigatoriedade HTML e obrigatoriedade efetiva do backend nem sempre são
iguais; aqui prevalece `required`/`clean()` do formulário. Opções cujos rótulos vêm de
enums de modelo são descritas pela fonte, sem inventar valores não lidos. Itens cujo
efeito depende de presenter/estado são marcados como condicionais. A vitrine de
desenvolvimento `core/main_preview` não é funcional e foi excluída do inventário de
páginas operacionais, mas seus componentes reais foram auditados nos consumidores.

## 2. Controles globais e componentes reutilizáveis

Fontes principais: `templates/cotton/v2/*.html`, `static/js/components/*.js`,
`static/js/core/app.js`, `static/js/components/overlay.js` e `base.html`.

| Família | Controles e comportamento comprovado | Dados/efeito |
|---|---|---|
| `input`, `select`, `form_field`, `field` | Invólucros de input/select, rótulo, ajuda, erro e ação contextual. | Preservam `name`, `id`, valor e validação do `BoundField`; não persistem por conta própria. |
| `picker` | Autocomplete single/multi sobre `<select data-entity-picker>`; busca local, cartão selecionado, limpar/remover; variantes pessoa/viatura e definição de motorista. | Submete os valores do select; opções e metadados vêm dos querysets/widgets. `picker.js`. |
| `related_picker` | Busca visível de documentos inteiros, candidatos em cartões, seleção single/multi; páginas podem usar fonte remota. | O select oculto é o valor persistido; scripts de Termo/OS/Evento/Roteiro filtram e preenchem. |
| `destinations` + `destination_row` | Linhas repetíveis Estado → Cidade; adicionar abaixo, remover, reordenar por arraste; cidade desabilitada até haver estado. | Nomes `destino_estado[_N]` e `destino_cidade[_N]`; `location-rows.js` consulta API de cidades e o form normaliza/persiste. |
| `date_picker` | Calendário `single`, `range` ou `multi`; inputs visíveis são somente leitura e hiddens recebem ISO. Pode aplicar várias datas a trechos. | Datas chegam nos campos/hiddens correspondentes. `date-picker.js`; limites/opções dependem do consumidor. |
| `time_stepper` | Campo HH:MM + botões −/+ (padrão 15 min). | Valor em minutos é escrito em hidden do roteiro pelo editor. |
| `number_stepper` | Campo numérico + botões −/+ com passo fornecido pelo chamador. | Usado no efetivo; mantém mínimo aplicado pelo JS/form. |
| `toggle` | Variante navegação (links/contadores/`aria-current`) e variante de estado (botões). | Navega entre abas ou delega valor ao JS do domínio. |
| `state_toggle` | Botão liga/desliga seção e escreve `true`/`false` em hidden. | Usado no bate-volta diário e estados binários. `state-toggle.js`. |
| `choice_grid`/`choice_card` | Radios ou checkboxes apresentados como cartões. | Mantém o input nativo; usado em motorista/viatura, tipo de OS, atividades/presets. |
| `file_picker` | File input com `accept`, single/multiple, lista, abrir/remover seleção, drag-and-drop; submit nasce desabilitado e é habilitado com arquivo. | Upload multipart; nomes originais preservados nos anexos. `file-picker.js`. |
| `download_picker` | Modal carregado sob demanda com lista de documentos e três grupos radio: `<id>-origem` (Original do sistema/Documento assinado, quando aplicável), `<id>-formato` (PDF/DOCX) e `<id>-saida` (Separados/Um arquivo). | A confirmação enfileira as gerações/downloads indicados pela resposta do endpoint; Fechar cancela somente a interação visível. `download-picker.js`. |
| `attach_signed_button` + modal | Abre modal global, escolhe tipo quando há mais de um, envia PDF, mostra arquivo atual, abre ou remove via AJAX. | URL de anexar/remover vem do gatilho; substitui cópia exibida/Drive conforme contexto. `attach-signed-modal.js`. |
| `delete_modal` | Confirma exclusão permanente; recebe URL/rótulo do gatilho. | POST para endpoint de exclusão; vínculo pode bloquear no backend. |
| `cancel_modal` | Textarea `motivo` obrigatória + confirmação destrutiva. | POST para cancelar; motivo enviado ao endpoint. |
| `confirm_modal` | Confirma ação não destrutiva (reativar, finalizar/desarquivar conforme gatilho). | POST para URL do gatilho; rótulo variável. |
| `menu`/`menu_item`/`menu_button` | Dropdown de ações por registro; itens link, download, desabilitado ou destrutivo; menus podem ser carregados sob demanda. | Navegação/POST/download dependem do item/presenter. |
| `wizard_page` + `stepper` | Cabeçalho de etapas; voltar, salvar/avançar, salvar rascunho e finalizar conforme página. | `wizard_action` controla a view; formulários com `data-autosave` também enviam ao endpoint próprio. |
| `chip`, `badge`, `state_toggle`, `rail`, `pagination` | Chips/badges comunicam estado/tipo/contagem; rail contém busca/filtros; paginação envia `page`. | Chips em geral são informativos; botões/chips selecionáveis são identificados nos domínios abaixo. |

Controles globais adicionais: abrir/fechar sidebar móvel, alternar tema, links de
módulo e conta, Perfil e Sair. O botão de tema altera preferência visual; não foi
confirmada persistência em modelo. A paginação é comum às listas paginadas.

## 3. Acesso, início, perfil e Google Drive

### Login — `core:login` / `templates/core/login.html`

| Seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação e persistência |
|---|---|---|---|---|
| Acesso | `username` | Usuário | texto, S, manual | `LoginForm`; `autocomplete=username`, autofocus. Autenticação Django e limitação de tentativas em `core.login_throttle`; não persiste edição. |
| Acesso | `password` | Senha | password, S, manual | `autocomplete=current-password`; validado pelo backend de autenticação; não é exibido nem persistido em claro. |
| Fluxo | `next` | — | hidden, N, derivado | Mantém destino solicitado após login; redirecionamento, não campo de modelo. |
| Ação | Entrar | Entrar | submit | POST `core:login`; sucesso autentica/redireciona; falha reapresenta erros e pode retornar 429. |

O dashboard (`core:dashboard`) não tem campos. Seus cartões abrem Ofícios, Termos,
Justificativas, Roteiros e demais módulos fornecidos pelo contexto/sidebar.

### Perfil — `core:perfil` / `templates/core/perfil.html`

| Seção | Nome técnico | Label | Tipo / Req. | Validação, dependência e persistência |
|---|---|---|---|---|
| Dados pessoais | `perfil-nome_completo` | Nome completo | texto, N | `PerfilUsuarioForm`; divide no primeiro espaço e salva `User.first_name`/`last_name`. |
| Dados pessoais | `perfil-username` | Nome de usuário | texto, S | Validadores do modelo User; salva `User.username`. |
| Dados pessoais | `perfil-email` | E-mail institucional | email, N | Validação de e-mail; salva `User.email`. |
| Ação | `action=atualizar_perfil` | Salvar alterações | submit | POST na própria `core:perfil`; valida/salva o bloco pessoal. |
| Senha | `senha-old_password` | Senha antiga | password, S | `PasswordChangeForm`; confere senha atual. |
| Senha | `senha-new_password1` | Nova senha | password, S | Política Django configurada (ajuda visível informa mínimo 12, similaridade, senha comum e não inteiramente numérica). |
| Senha | `senha-new_password2` | Confirmação | password, S | Deve coincidir com a nova senha. |
| Ação | `action=alterar_senha` | Alterar senha | submit | Salva hash novo e preserva a sessão atual; a tela informa encerramento das demais sessões. |
| Sessão | Sair do sistema | — | submit | POST `core:logout`. |

Áreas de trabalho são lista informativa no perfil. O painel Google Drive possui
ações condicionais: **Conectar conta Google**, **Trocar conta**, **Desconectar**,
**Ver no Drive**, navegar pastas/voltar, **Criar nova pasta aqui**, **Criar pasta**,
**Usar esta pasta como destino**, **Ver prévia**, **Reorganizar tudo no Drive** e
**Tentar novamente agora**. `gdrive-nova-pasta-nome` é texto opcional na abertura
do painel, com rótulo/placeholder “Nome da nova pasta” e `maxlength=255`; o botão
Criar envia o nome para `google_drive:api_criar_pasta` no diretório corrente. Os
hiddens `pasta_raiz_id` e `pasta_raiz_nome` guardam a seleção da árvore e são
submetidos a `google_drive:salvar_pasta_raiz`; `gdrive-config.js`/
`configuracoes.js` controlam a UI e as demais URLs chegam do contexto. A
persistência exata das credenciais/pasta deve ser descrita pelo eixo de regras;
neste eixo apenas se comprovaram os endpoints, o campo e os hiddens.

## 4. Cadastros e configuração

### Listas de catálogo

`Unidades`, `Cargos`, `Combustíveis`, `Cidades`, `Estados`, `Tipos de evento`,
`Modelos de motivo`, `Modelos de justificativa`, `Programas`, `Horários`,
`Atividades`, `Presets`, `Usuários` e `Áreas` usam `c-v2.catalog_page`: busca `q`,
abrir/fechar inclusão rápida, salvar, editar, definir padrão quando previsto,
excluir por modal/página de confirmação, limpar busca e paginação. Usuários/Áreas
têm também filtro de navegação entre as duas administrações. `Cidades` oferece
exportação CSV pela rota `cadastros:cidades_export_csv`.

### Unidades — `cadastros:unidades_index`, create/update

| Nome técnico | Label | Tipo / Req. / origem | Validação, dependências e persistência |
|---|---|---|---|
| `nome` | Nome | texto, S, manual | Sem duplicata na área; salva `Unidade.nome`. |
| `sigla` | Sigla | texto, N, manual | `strip().upper()`; salva `Unidade.sigla`. |
| `servidores` | Servidores | autocomplete multi, N, BD | Busca nome/cargo/CPF/RG; ao salvar sincroniza `Servidor.unidade`, vinculando escolhidos e desvinculando removidos dentro da área. |

### Estados e cidades

| Página | Nome técnico | Label | Tipo / Req. / origem | Validação e persistência |
|---|---|---|---|---|
| Estados | `nome` | Nome | texto, S | `strip`; `Estado.nome`. |
| Estados | `sigla` | Sigla | texto, S | maiúsculas, exatamente 2 caracteres; `Estado.sigla`. |
| Estados | `codigo_ibge` | Código IBGE | número, N | inteiro/modelo; `Estado.codigo_ibge`. |
| Cidades | `nome` | Nome | texto, S | `strip`; `Cidade.nome`. |
| Cidades | `estado` | Estado | select, S, BD | estados ordenados; `Cidade.estado`. |
| Cidades | `capital` | Capital | checkbox/toggle, N | booleano `Cidade.capital`. |
| Cidades | `codigo_ibge` | Código IBGE | número, N | `Cidade.codigo_ibge`. |
| Cidades | `latitude` / `longitude` | Latitude / Longitude | decimal, N | campos decimais `Cidade.*`. |

### Cargos e combustíveis

Ambos possuem `nome` obrigatório, normalizado para maiúsculas e único na área, e
`is_padrao`/“Cargo padrão” ou “Combustível padrão”, toggle opcional. As listas
oferecem ação explícita **Definir como padrão** (`*_set_default`) e excluir. Salvos
em `Cargo`/`Combustivel`.

### Servidores — lista e formulário

Filtros da lista: `q` (nome/identificação conforme selector) e cargo (`cargo`,
mantido em hidden enquanto busca); ações: Novo, editar, excluir e limpar.

| Nome técnico | Label | Tipo / Req. / origem | Validação, automação e persistência |
|---|---|---|---|
| `nome` | Nome | texto, S, manual | Normalizado em maiúsculas; único na área; `Servidor.nome`. |
| `cargo` | Cargo | select, N, BD | Filtrado por área; criação inicia no cargo padrão quando existe; `Servidor.cargo`. Ação Gerenciar cargos. |
| `cpf` | CPF | texto mascarado, N | 11 dígitos, dígitos verificadores válidos e único na área; armazena somente dígitos em `Servidor.cpf`. |
| `rg` | RG | texto mascarado, N | Alfanumérico normalizado; vazio vira valor canônico “não possui”; único na área; atualiza `sem_rg`; `Servidor.rg`. |
| `telefone` | Telefone | texto mascarado, N | 10 ou 11 dígitos e único na área; salva dígitos em `Servidor.telefone`. |
| `unidade` | Unidade | autocomplete single, N, BD | Filtrada por área; `Servidor.unidade`. Ação Gerenciar unidades. |
| Fluxo | `next` | — | hidden, N | Retorno seguro ao fluxo que abriu “Novo viajante”. |
| Ações | Voltar / Salvar | — | link/submit | Create/update; exclusão por modal/página própria. |

### Viaturas — lista e formulário

Filtros: `q`, unidade/combustível (URL escolhida no select; valores preservados em
hiddens). Ações: Nova, editar, excluir, limpar.

| Nome técnico | Label | Tipo / Req. / origem | Validação, automação e persistência |
|---|---|---|---|
| `placa` | Placa | texto mascarado, S | Normaliza e aceita padrão antigo ou Mercosul com 7 caracteres; única por área; `Viatura.placa`. |
| `modelo` | Modelo | texto, N | maiúsculas; `Viatura.modelo`. |
| `tipo` | Tipo | select, N, fixo | `Viatura.TIPO_CHOICES`; novo inicia descaracterizada; `Viatura.tipo`. |
| `combustivel` | Combustível | select, N, BD | Filtrado por área; inicia padrão; `Viatura.combustivel`. Ação Gerenciar combustíveis. |
| `unidade` | Unidade (opcional) | autocomplete, N, BD | `Viatura.unidade`; ação Gerenciar unidades. |
| `motoristas` | Motoristas | autocomplete multi, N, BD | Busca servidores da área e apresenta cargo/unidade/CPF; relação M2M `Viatura.motoristas`. Ação Gerenciar servidores. |
| Fluxo/ações | `next`, Voltar, Salvar | hidden/link/submit | Mantém retorno; create/update e delete. |

### Configuração do sistema — instituição, ofício e diárias

A navegação é um toggle de abas. Cada POST leva `form_id` (`instituicao`, `oficio`
ou `diarias`) e tem Voltar/Salvar.

| Aba/seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação e persistência |
|---|---|---|---|---|
| Instituição | `unidade` | Unidade | autocomplete, N, BD | Busca sigla/nome; `ConfiguracaoSistema.unidade`. |
| Endereço | `cep` | CEP | texto mascarado, N | 8 dígitos; consulta `cadastros:api_consulta_cep`; pode preencher endereço/UF. `ConfiguracaoSistema.cep`. |
| Endereço | `logradouro`, `numero`, `bairro` | Logradouro/Número/Bairro | texto, N | logradouro/bairro em maiúsculas; campos homônimos do singleton por área. |
| Endereço | `cidade_endereco` | Cidade | texto, N | espaços normalizados e maiúsculas. |
| Endereço | `uf` | — | hidden, N, derivado | 2 letras; preenchido pela consulta de CEP; `ConfiguracaoSistema.uf`. |
| Endereço | `uf_nome` | UF | texto readonly, A | Exibição do nome do estado; não é campo do modelo. |
| Contato | `telefone` | Telefone | máscara, N | 10/11 dígitos; `ConfiguracaoSistema.telefone`. |
| Contato | `ramal` | Ramal (opcional) | texto, N | `strip`; `ConfiguracaoSistema.ramal`. |
| Contato | `email` | E-mail | email, N | validação de e-mail; `ConfiguracaoSistema.email`. |
| Assinantes | `assinante_oficio`, `assinante_justificativa`, `assinante_plano_trabalho`, `assinante_ordem_servico` | Assinante padrão – … | autocomplete single, N, BD | Quatro campos dinâmicos; salvam/atualizam `AssinaturaConfiguracao` ordem 1; vazio remove a configuração do tipo. |
| Destinatário | `destinatario_oficio` | Nome | autocomplete + texto livre, N, BD/manual | Ao escolher servidor preenche nome/cargo/unidade se vazios. `ConfiguracaoSistema.destinatario_oficio`. |
| Destinatário | `destinatario_oficio_nome` | — | hidden, N | Cópia do nome ou texto livre; campo homônimo. |
| Destinatário | `destinatario_oficio_cargo`, `destinatario_oficio_unidade` | Cargo / Unidade lotada | texto, N | Autopreenchidos pelo servidor, mas editáveis; campos homônimos. |
| Diárias | `faixa` | Faixa | select, S, fixo | `TabelaDiaria.faixa`. |
| Diárias | `vigencia_inicio` | Vigente a partir de | date picker/hidden, S | Não permite mesma faixa+data repetida; `TabelaDiaria.vigencia_inicio`. |
| Diárias | `valor_24h` | Diária de 24 horas | decimal, S | `> 0`; `TabelaDiaria.valor_24h`. |
| Diárias | `diaria-calc-15`, `diaria-calc-30` | 15% / 30% | readonly, A | Derivados no frontend para prévia; o modelo deriva os percentuais, não são entrada persistida. |

## 5. Ofícios e justificativas

### Lista de ofícios

Filtros GET comprovados: `q`; `aba` (situação); `sort`; intervalos `viagem_de` /
`viagem_ate` e `criacao_de` / `criacao_ate` via date picker; limpar; paginação.
Cada cartão exibe chip de situação, viajantes/documentos com badges, e menus/ações
condicionais fornecidos pelo presenter: abrir/detalhar, editar/continuar wizard,
documentos e downloads, anexar/gerenciar assinado, retificar, marcar complementar,
cancelar com motivo e excluir. Endpoints incluem `oficios:detalhe`, `editar`, etapas
do wizard, `baixar_documento`, `retificar`, `complementar`, `cancelar`, `excluir` e
rotas de anexos/menus. A disponibilidade por status não foi reconstituída só deste
eixo e deve ser cruzada com o inventário de regras.

### Wizard do ofício — etapa Dados dos viajantes

Template principal `wizard_dados_viajantes.html`; form `OficioDadosViajantesForm`;
autosave `oficios:dados_viajantes_autosave`.

| Seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação e persistência |
|---|---|---|---|---|
| Identificação | `numero` | Nº do Ofício | número, N | Em branco mantém/reserva automático; se informado, >0 e único por ano+área; `Oficio.numero`. Ano é sufixo informativo. |
| Identificação | `protocolo` | Protocolo | texto máscara, C | Normaliza para dígitos; na validação final, se preenchido exige 9 dígitos; `Oficio.protocolo`. |
| Custeio | `custeio` | Custeio | select, N nesta etapa, fixo | `Oficio.custeio`; escolher `OUTRA_INSTITUICAO` revela Nome da Instituição. |
| Custeio | `custeio_observacao` | Nome da Instituição | texto, C | Visível apenas para outra instituição; espaços normalizados; `Oficio.custeio_observacao`. |
| Finalidade | `modelo_motivo` | Modelo de motivo | select, N, BD | Modelos ativos da área. Ao mudar, JS copia `ModeloMotivoOficio.texto` para `motivo`; novo ofício usa modelo padrão. Não persiste o FK. Ação Gerenciar modelos com autosave. |
| Finalidade | `motivo` | Descrição | textarea, N | Texto copiado continua editável; espaços normalizados; `Oficio.motivo`. |
| Equipe | `servidores` | Servidores | autocomplete multi, N, BD | Relação `Oficio.servidores`; cada selecionado permite marcar motorista e necessidade de termo. Novo viajante preserva autosave. |
| Equipe | `servidores_termo_autorizacao` | — | multiselect oculto, N | Deve ser subconjunto da equipe; se a marca de presença não vier, backend assume toda a equipe. Relação M2M homônima. |
| Equipe | `servidores_termo_autorizacao_present` | — | hidden, A | Distingue lista vazia enviada de campo ausente. |
| Transporte rápido | `viatura` | Viatura | autocomplete single, N, BD | `Oficio.viatura`; sugestões podem ser ordenadas por unidade/motoristas da equipe em JS. |
| Fluxo | `transporte_embed=1` | — | hidden | Diz à view que o transporte está embutido nesta etapa. |

Ações: Voltar/Avançar (`wizard_action=wizard_back|wizard_next`), atalhos Novo
viajante/Gerenciar modelos e ações do picker. O wizard preserva rascunho por autosave.

### Wizard do ofício — Transporte

Form `OficioTransporteForm`; autosave `oficios:transporte_autosave`; busca de placa
em `oficios:api_viatura_por_placa`.

| Nome técnico | Label | Tipo / Req. / origem | Dependências, validação e persistência |
|---|---|---|---|
| `transporte_busca_ui` | Buscar viatura | search/autocomplete, N, remoto/manual | Busca placa/unidade/combustível/tipo. Seleção do BD preenche id, placa, modelo, combustível e tipo e bloqueia painel manual; texto de placa não encontrada mantém modo manual. UI, não modelo. |
| `viatura` | — | hidden FK, N | `Oficio.viatura`; preenchido por resultado. |
| `transporte_placa_manual` | — | hidden, N | Normaliza placa; se não há viatura e houver valor, exige 7 caracteres. `Oficio.transporte_placa_manual`. |
| `transporte_modelo_manual` | Modelo | texto, N | Preenchido/readonly visualmente quando cadastro escolhido; `Oficio.transporte_modelo_manual`. |
| `transporte_combustivel_manual` | Combustível | select, N, BD | Catálogo da área; `Oficio.transporte_combustivel_manual`. |
| `transporte_tipo_manual` | Tipo | select, N, fixo | Default descaracterizada; `Oficio.transporte_tipo_manual`. |
| `porte_transporte_armas` | Porte/transporte de armas | select Sim/Não, N | Default Sim; coage booleano; `Oficio.porte_transporte_armas`. |
| `motorista_modo` | — | hidden/toggle, C | `SERVIDOR` ou `MANUAL`; controla qual painel aparece e limpa a alternativa; `Oficio.motorista_modo`. |
| `motorista` | Motorista servidor | autocomplete single, C, BD | Desabilitado no modo manual; se membro da equipe, limpa referências externas; `Oficio.motorista`. |
| `motorista_manual_nome` | Nome do motorista | texto, C | Visível no modo manual; ao usar servidor é limpo; `Oficio.motorista_manual_nome`. |
| `motorista_oficio_referencia` | Nº do ofício do motorista | document number/hidden, C | Formata `número/ano`, limita ao max_length; exibido para motorista externo/manual; campo homônimo. |
| `motorista_protocolo_ref` | Protocolo do motorista | texto máscara, C | Normaliza protocolo; campo homônimo. |

Ações: limpar/trocar viatura, alternar motorista servidor/manual, criar/editar
servidor ou viatura, Voltar e Avançar.

### Etapa Roteiro

Embute o editor completo descrito na seção 8. O retorno ao wizard é controlado por
`wizard_action`; autosave usa `oficios:roteiro_autosave` e o objeto `Roteiro`
vinculado ao ofício.

### Etapa Justificativa

| Nome técnico | Label | Tipo / Req. | Comportamento/persistência |
|---|---|---|---|
| `modelo` | Modelo | select, N, BD | Modelos ativos da área; mudança copia texto para a justificativa; ação Gerenciar modelos com autosave. Não salva o modelo no documento. |
| `texto` | Justificativa | textarea, C | `JustificativaOficio.texto`; `obrigatoria=True` na instância do form torna o campo exigido. Texto normalizado. |

Botões Voltar/Avançar. Em contextos de inclusão rápida, `oficios` é multiselect
obrigatório, `modelo` opcional e `texto` obrigatório; endpoint principal
`justificativas:index`, com busca remota `justificativas:api_buscar_oficios`.

### Etapa Documentos

Não possui campo editorial principal. Ações comprovadas: Voltar; Salvar rascunho e
voltar à lista; Finalizar Ofício; abrir/fechar prévias; validar artefatos; abrir todos
os termos; visualizar/baixar formatos; anexar/gerenciar documentos assinados. Rotas
`oficio_pdf_inline`, previews de termo/justificativa/OS e `baixar_documento`.

### Catálogos de texto

`ModeloMotivoOficioForm` e `ModeloJustificativaForm`: `nome` (texto, S, nome curto),
`texto` (textarea, S, copiado mas editável no documento) e `is_padrao` (toggle, N).
Ambos oferecem busca, criar/editar, definir padrão e excluir. Justificativas rápidas:
`oficios` (document picker multi, S), `modelo` (N) e `texto` (S).

## 6. Eventos

### Lista

Filtros GET: `q` e `aba`/status; limpar e paginação. Chips mostram situação e
tipos/contagens fornecidos pelo presenter. Ações condicionais dos cartões incluem
abrir painel, editar, criar documentos relacionados, anexar assinado, cancelar,
reativar, excluir e menus sob demanda (`eventos:card_menus`). Modais globais:
exclusão, cancelamento com motivo, confirmação de reativação e anexo assinado.

### Cadastro/edição administrativa — `EventoForm`, `eventos/form.html`

| Seção | Nome técnico | Label | Tipo / Req. / origem | Validação, dependência e persistência |
|---|---|---|---|---|
| Dados principais | `titulo` | Título | texto, N | `Evento.titulo`. |
| Dados principais | `descricao` | Descrição/objetivo | textarea, N | `Evento.descricao`. |
| Dados principais | `status` | Status | select, S, enum | `Evento.status`. |
| Dados principais | `unidade_responsavel` | Unidade responsável | select, N, BD área | `Evento.unidade_responsavel`. |
| Dados principais | `responsavel` | Responsável | select, N, BD área | `Evento.responsavel`. |
| Destino | `destino_uf` | UF do destino | texto, N | Maiúsculas; se preenchido exige 2 caracteres; `Evento.destino_uf`. |
| Destino | `destino_cidade` | Cidade do destino | texto, N | `Evento.destino_cidade`. |
| Período | `data_inicio`, `data_fim` | Período do evento | date range/hidden, N | Fim não pode preceder início; `Evento.data_*`. |
| Período | `horario_inicio`, `horario_fim` | Horário inicial/final | time, N | `Evento.horario_*`. |
| Drive | `drive_folder_url` | URL da pasta no Drive | URL, N | Validador de URL; `Evento.drive_folder_url`. |

“Organização documental” mostra chips informativos (Ofícios, Justificativas,
Termos, Plano de trabalho, Ordem de serviço, Roteiro, Anexos); não são inputs nessa
tela. Ações: Cancelar, Abrir painel (na edição), Salvar evento; ações de Drive vêm
do partial e são condicionais ao estado da integração.

### Cadastro guiado/painel — `EventoNovoCadastroForm`, `eventos/detalhe.html`

| Etapa/seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação e persistência |
|---|---|---|---|---|
| Identificação | `tipos` | Tipo do evento | multiselect, N, BD | Tipos ativos da área; relação de tipos do Evento. |
| Identificação | `modelo_motivo` | Modelo de motivo | select, N, BD | Modelo ativo da área; seleção copia texto para `motivo`; não persiste FK. |
| Identificação | `motivo` | Motivo | textarea, N | Texto livre ou copiado, `Evento.motivo`. |
| Período | `data_inicio`, `data_fim` | Período do evento | date range, N | Fim >= início. Essas datas também pré-filtram documentos vinculáveis com tolerância fornecida pelo contexto. |
| Destinos | `destinos_json` | — | hidden JSON, A/R | JS serializa todas as linhas `{uf,cidade}`. A persistência da lista é tratada pela view/service; o primeiro também alimenta os hiddens abaixo. |
| Destinos | `destino_uf`, `destino_cidade` | Estado / Cidade do destino | hidden + linhas autocomplete, N/R, BD | UF começa pela configuração da área quando possível. Estado altera cidades via `eventos:api_cidades_por_uf`/motor global. Primeiro destino vai aos campos do Evento; adicionar/remover/reordenar ocorre na UI. |
| Documentos | `oficios_vinculados` | Ofícios já existentes | related picker multi, N, BD | Apenas área atual; documento cancelado só permanece se já vinculado. Relação Evento↔Ofício. |
| Documentos | `roteiros_vinculados` | Roteiros já existentes | related picker multi, N, BD | Filtrado por área e período na UI; relação Evento↔Roteiro. |
| Documentos | `planos_trabalho_vinculados` | Planos de trabalho já existentes | related picker multi, N, BD | Área/período; relação Evento↔Plano. |
| Documentos | `ordens_servico_vinculadas` | Ordens de serviço já existentes | related picker multi, N, BD | Área/período; relação Evento↔OS. |
| Documentos | `termos_vinculados` | Termos de autorização já existentes | related picker multi, N, BD | Área/período; relação Evento↔Termo. |

O alternador de documentos troca cinco painéis; cada painel tem busca própria,
limpar busca, cartões selecionáveis e vazio por período. Ações do fluxo guiado:
Voltar à lista, Salvar e avançar, Reativar evento (quando cancelado), criar novo
Roteiro/Ofício/OS/Plano/Termo conforme etapa e abrir/editar/remover documentos já
vinculados. Endpoints `eventos:guiado_etapa`, `guiado_termos`, create-associate de
documentos, `cancelar`, `reativar`, `editar`, `excluir`.

## 7. Termos de autorização

### Lista

Filtros `q` e `aba`; limpar/paginação. Cartões exibem situação e período/destino;
ações: editar, prévia/downloads, anexar/gerenciar assinado e excluir. Modais de
exclusão e anexo assinado.

### Cadastro/edição — `TermoAutorizacaoForm`

| Seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação, automação e persistência |
|---|---|---|---|---|
| Fonte | `oficio` | Ofício vinculado | related picker single, N, remoto | Busca `termos:api_buscar_oficios`; ao selecionar, `termos-form.js` pode copiar destino, período, servidores e viatura. Salva `TermoAutorizacao.oficio`. |
| Período | `data_evento_inicio`, `data_evento_fim` | Data de ida/volta | date range, C | Opcionais isoladamente, mas deve haver período informado ou herdável do ofício. Se só início, fim = início; fim >= início. Campos do Termo. |
| Destino | `destino_estado` | Estado | autocomplete, C, BD | Sede da configuração pode iniciar estado. Cidade selecionada corrige estado. `TermoAutorizacao.destino_estado`. |
| Destino | `destino_cidade` | Cidade | autocomplete dependente, C, BD | Desabilitada sem estado. Exigida se estado informado; se não houver cidade, ofício precisa fornecer destino. `TermoAutorizacao.destino_cidade`. |
| Destinos extras | `destino_estado_N`, `destino_cidade_N` | Estado/Cidade | linhas R, C, BD | Linha parcial gera erro; cidade válida. Persistidos como JSON normalizado em `TermoAutorizacao.destinos_extras`. |
| Equipe | `servidores` | Servidores | autocomplete multi, N, BD | Se vazio, pode usar servidores do termo no ofício; relação M2M. Com vários, a saída gera um termo por servidor. |
| Transporte | `viatura` | Viatura | autocomplete single, N, BD | Se vazio, pode herdar do ofício; `TermoAutorizacao.viatura`. |

Ações: Novo viajante, Nova viatura, adicionar/remover/reordenar destino, Voltar,
Salvar termo; na edição, visualizar PDF inline e baixar PDF/DOCX/individual/lote
conforme rotas de `termos:downloads` e previews. A origem do ofício é um select
oculto validado pelo queryset da área, apesar da busca remota.

## 8. Roteiros

### Lista

Filtros `q` e `aba`/status; limpar/paginação. Ações: novo, editar e excluir. O
editor também aparece embutido no wizard de ofício.

### Editor — campos de modelo

| Nome técnico | Label | Tipo / Req. | Validação/persistência |
|---|---|---|---|
| `origem_estado` | Estado sede | autocomplete, N | Deve corresponder à cidade; `Roteiro.origem_estado`. |
| `origem_cidade` | Cidade sede | autocomplete dependente, N | Cidade deve pertencer ao estado; `Roteiro.origem_cidade`. |
| `saida_dt` | Data/hora saída | datetime-local, N | Aceita datetime/data nos formatos do form; `Roteiro.saida_dt`. |
| `retorno_saida_dt` | Retorno – saída | datetime-local, N | `Roteiro.retorno_saida_dt`; a tela atual usa controles de retorno mais granulares descritos abaixo. |
| `observacoes` | Observações | textarea, N | `strip().upper()`; `Roteiro.observacoes`. |
| `rota_distancia_manual_km` | Distância ajustada manualmente (km) | decimal >=0, N | Se preenchida, justificativa é obrigatória; campo homônimo. |
| `rota_duracao_manual_min` | Duração ajustada manualmente (min) | inteiro >=0, N | Mesma condição; campo homônimo. |
| `rota_ajuste_justificativa` | Justificativa do ajuste manual | textarea, C | Obrigatória quando distância ou duração manual existe; campo homônimo. |

### Editor — controles compostos/template/JS

| Bloco | Nome técnico | Label/controle | Req. | Comportamento e destino do dado |
|---|---|---|---|---|
| Fonte | `roteiro_modo` | Usar roteiro salvo / Roteiro próprio | radio oculto + toggle, C | `EVENTO_EXISTENTE` mostra busca e desabilita edição própria; `ROTEIRO_PROPRIO` mostra sede/destinos. UI/POST interpretado pelo parser. |
| Fonte | `roteiro_id` | Roteiro salvo | hidden + related search, C | Habilitado somente no modo existente; seleção de rota prévia. |
| Destinos | `destino_estado_N`, `destino_cidade_N` | Estado/Cidade | autocomplete R, C | Cascata, inserir, remover, arrastar/reordenar. Recalcula trechos, mapa e diárias. Parser `roteiros/services/editor_parser.py`. |
| Bate-volta | `bate_volta_diario_ativo` | Com/Sem bate-volta diário | state toggle/hidden, N | Mostra/esconde bloco; booleano no POST. |
| Bate-volta | `bate_volta_data_inicio`, `bate_volta_data_fim` | Período do bate-volta | date range, C | Usado para repetir ida/volta diariamente. |
| Bate-volta | `bate_volta_ida_saida_hora`, `bate_volta_volta_saida_hora` | Saída da ida/volta | hora mascarada, C | HH:MM; parser do editor. |
| Bate-volta | `bate_volta_ida_tempo_min`, `bate_volta_volta_tempo_min` | Tempo da ida/volta | hidden, C | Inputs visíveis HH:MM são convertidos para minutos. |
| Trechos | `trecho_<N>_saida_data/hora`, `...chegada_data/hora` | Datas/horas do trecho | date/time R, C | Linhas são geradas pelo editor; calendário multi pode aplicar datas em sequência. |
| Trechos | `trecho_<N>_tempo_cru_estimado_min`, `...tempo_adicional_min`, `...distancia_km`, `...duracao_estimada_min`, `...rota_fonte` | Métricas do trecho | hidden R, A | Recebem cálculo de rota; tempo adicional é editável via HH:MM/stepper; total é readonly. |
| Retorno | `retorno_saida_data/hora` | Data/Hora de saída | date + hora, C | Cidade de saída é readonly e vem do último destino. |
| Retorno | `retorno_chegada_data/hora` | Data/Hora de chegada | date + hora, C | Cidade de chegada é readonly e volta à sede. |
| Retorno | `retorno_tempo_cru_estimado_min` | Tempo de viagem | hidden + HH:MM, A/editável conforme editor | Estimativa de rota. |
| Retorno | `retorno_tempo_adicional_min` | Tempo adicional | hidden + stepper, N | Ajuste de 15 min; total visível readonly soma estimado+adicional. |
| Retorno | `retorno_distancia_km`, `retorno_duracao_estimada_min`, `retorno_rota_fonte` | Métricas | hidden, A | Resultado da API de rota/estimativa. |
| Autosave | `autosave_obj_id` | — | hidden, A | Identifica rascunho para `roteiro-autosave-create`/`roteiro-autosave`. |
| Diárias | `quantidade_servidores` | — | hidden, A | Alimenta cálculo das diárias; no editor geral começa no contexto. |
| Diárias | `tipo_destino`, `quantidade_diarias`, `valor_diarias`, `valor_diarias_extenso` | Resultado | hidden, A | Derivados pelo motor/endpoint `roteiros:calcular_diarias`. |
| Mapa | `map_route_geometry_json`, `map_route_points_json`, `map_route_distance_km`, `map_route_duration_minutes`, `map_route_provider`, `map_route_calculated_at` | Resultado da rota | hidden, A | Preenchidos por `api/calcular-rota`/preview e usados ao salvar/cachear rota. |

Ações do editor: escolher rota salva, adicionar/remover/reordenar destinos, calcular
rota, ajustar tempos −/+, aplicar/desfazer datas, alternar bate-volta, Voltar,
Avançar (quando embutido) e Salvar roteiro. APIs: cidades por estado, estimar
trechos, calcular rota/preview e calcular diárias. Os campos de cidade readonly e
totais não são submetidos como fonte autoritativa quando não têm `name`.

## 9. Ordens de serviço

### Lista

Filtros GET: `q`, `aba`, `sort`, `viagem_de`/`viagem_ate`; limpar/paginação.
Ações: Nova OS, editar, menu de downloads (DOCX/PDF/visualização), anexar/gerenciar
assinado e excluir. Endpoints `nova`, `editar`, `baixar_docx`, `pdf_inline`,
`baixar_pdf`, `excluir`, `card_menus`.

### Cadastro/edição — `OrdemServicoForm`

| Seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação e persistência |
|---|---|---|---|---|
| Fonte | `oficios` | Ofícios vinculados | related picker multi, N, remoto | Busca `ordens_servico:api_buscar_oficios`; cancelados não entram em nova seleção, mas já vinculados permanecem. Pode preencher destino, período, equipe e motivo. Relação M2M. |
| Necessidade | `tipo_necessidade` | Tipo de necessidade | radio/cards, S, enum | `OrdemServico.tipo_necessidade`; controla papéis/funções disponíveis. |
| Motivo | `modelo_motivo` | Modelo de motivo | select, N, BD área | Copia texto para `motivo`; não persiste modelo. Ação Gerenciar modelos. |
| Motivo | `motivo` | Motivo | textarea, N | Livre ou copiado; `OrdemServico.motivo`. |
| Período | `data_evento_inicio`, `data_evento_fim` | Data de ida/volta | date range, N | Campos homônimos. A validação temporal específica não aparece no `clean()` deste form; não assumir. |
| Destinos | `destino_estado`, `destino_cidade` | Estado/Cidade | autocomplete, N/C | Cidade desabilitada sem estado; estado sem cidade gera erro. Cidade principal persiste na relação `destinos`. |
| Destinos extras | `destino_estado_N`, `destino_cidade_N` | Estado/Cidade | R, C | Linha parcial/inválida gera erro; todas as cidades válidas são gravadas em `OrdemServico.destinos`. |
| Equipe | `servidores` | Servidores | autocomplete multi, N, BD | Se vazio e houver ofícios, pode reutilizar equipes. Relação M2M. |
| Funções | `motorista_equipe`, `tecnico_equipe`, `apoio_montagem`, `apoio_escolta`, `coordenador_cerimonial`, `apoio_cerimonial`, `apoio_preparacao` | Papéis correspondentes | autocomplete single, N, BD | Campos FK/modelo correspondentes; a apresentação/visibilidade varia com `tipo_necessidade`. |
| Funções por servidor | `funcao_servidor_<id>` | Função na equipe | select/toggle dinâmico, C/R, fixo | Somente para caminhão, micro-ônibus ou cerimonial antecipado; servidor deve estar na equipe e função em `FUNCOES_SERVIDOR_VALIDAS`; persiste JSON `OrdemServico.funcoes_servidores`. |

Ações: escolher/remover ofícios, tipo de necessidade, destinos e equipe; marcar
funções; Novo viajante; Voltar; Salvar/Gerar conforme `submit_label`. O JS usa os
resumos dos ofícios para preencher campos, mas os querysets/backend validam os ids.

## 10. Planos de trabalho

### Lista e catálogos auxiliares

Lista principal: `q`, `aba`, `sort`, período `viagem_de`/`viagem_ate`, limpar e
paginação. Ações: Novo plano, editar/continuar etapas, abrir menu/documentos,
downloads/preview, excluir. Catálogos:

- Programas: `nome` (texto, S), `ativo` (toggle, N), `ordem` (inteiro, S).
- Horários: `horario_inicio` e `horario_fim` (time, S); o hidden `faixa` é montado
  como `HH:MM até HH:MM` e persiste em `HorarioAtendimento.faixa`.
- Atividades (edição completa): `codigo` (S, normalizado via slug para maiúsculas
  com `_`, único na área), `nome` (S), `meta` (textarea, S),
  `recurso_necessario` (textarea, N), `ordem` (inteiro, S) e `ativo` (toggle, N).
- Atividade rápida: `nome`/Atividade (S), `meta`/Metas (S),
  `recurso_necessario`/Recursos necessários (N); código único é gerado do nome.
- Preset: `nome` (S, maiúsculas, único na área) e `atividades` (checkbox cards
  multi, S, ao menos uma atividade ativa). Ação Definir padrão.

### Wizard — etapa 1, Identificação (`PlanoIdentificacaoForm`)

Autosave: `planos_trabalho:identificacao_autosave`.

| Seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação, automação e persistência |
|---|---|---|---|---|
| Programa | `programa` | Programa | select, N, BD + “Outro” | Programas ativos da área; escolha persiste FK `PlanoTrabalho.programa`. `__outro__` mostra o campo manual. |
| Programa | `programa_outros` | Outro programa | texto, C | Habilitado e obrigatório somente em Outro; caso contrário é limpo. `PlanoTrabalho.programa_outros`. |
| Período | `data_evento_inicio`, `data_evento_fim` | Período do evento | date range, N | Se só início, fim = início; fim não pode preceder início. Campos homônimos. |
| Período | `horario_atendimento` | Horário de atendimento | select, N, BD | Faixas ativas do catálogo; preserva valor histórico fora da lista; string no Plano. Ação Gerenciar horários. |
| Destinos | `destino_estado`, `destino_cidade` | Estado/Cidade | autocomplete dependente, N/C | Estado inicia na sede configurada; estado sem cidade gera erro; cidade corrige estado. Campos principais do Plano. |
| Destinos extras | `destino_estado_N`, `destino_cidade_N` | Estado/Cidade | R, C | Linhas válidas viram `PlanoDestino` do rascunho; linha parcial/inválida gera erro. |
| Coord. adm. | `coordenador_adm` | Nome | autocomplete + texto livre, N, BD/manual | Escolher servidor define modo SERVIDOR e limpa manual; texto livre define MANUAL. FK no Plano. |
| Coord. adm. | `coordenador_adm_modo`, `coordenador_adm_nome_manual` | — | hiddens, A/C | Guardam origem/nome manual; nome normalizado em maiúsculas; campos homônimos. |
| Coord. adm. | `coordenador_adm_cargo_manual` | Cargo | select, N, BD | Preenchido pelo servidor ou selecionável no manual; campo homônimo. Ação Gerenciar cargos. |
| Coord. adm. | `coordenador_adm_genero` | Gênero | select, N, fixo | Default masculino se vazio; usado na geração do texto; campo homônimo. |
| Coord. op. | `coordenador_op`, `coordenador_op_modo`, `coordenador_op_nome_manual`, `coordenador_op_cargo_manual`, `coordenador_op_genero` | Nome/Cargo/Gênero | mesmos tipos, N | Mesmo comportamento; coordenador operacional é apresentado como opcional. |
| Textos | `contextualizacao` | Breve contextualização | textarea, N | Gerada de programa+destino enquanto flag auto=1; primeira edição manual bloqueia futuras substituições; `PlanoTrabalho.contextualizacao`. |
| Textos | `coordenacao` | Coordenação do evento | textarea, N | Gerada dos coordenadores enquanto automática; campo homônimo. |
| Textos | `consideracao_final` | Considerações finais | textarea, N | Gerada do destino enquanto automática; campo homônimo. |
| Estado auto | `contextualizacao_auto`, `coordenacao_auto`, `consideracao_auto` | — | hidden flags, A | UI/POST, indicam se JS ainda pode recalcular o texto. Persistência direta não confirmada neste eixo. |

Ações: gerenciar programas/cargos/horários (links com autosave), adicionar/remover/
ordenar destinos, Voltar à lista salvando rascunho e Salvar e avançar.

### Wizard — etapa 2, Efetivo e diárias

Autosave `efetivo_diarias_autosave`; cálculo `api_calcular_diarias`.

| Bloco | Nome técnico | Label | Tipo / Req. | Validação e persistência |
|---|---|---|---|---|
| Efetivo R | `efetivo-<N>-unidade` | Unidade | autocomplete, N | `EfetivoPlano.unidade`; vazio permitido. |
| Efetivo R | `efetivo-<N>-cargo` | Cargo | select, C | Linha vazia é ignorada; em linha parcial, cargo obrigatório. `EfetivoPlano.cargo`. |
| Efetivo R | `efetivo-<N>-quantidade` | Quantidade | number stepper, C | Mínimo visual 1; em linha parcial, obrigatório. `EfetivoPlano.quantidade`. |
| Efetivo R | `efetivo-<N>-DELETE`, `id`, `TOTAL_FORMS` | — | hiddens, A | Formset; remover marca DELETE ou elimina linha nova; adicionar incrementa total. |
| Deslocamento | `saida_sede_data`, `saida_sede_hora` | Data/Hora de saída da sede | date + time, N | Campos do Plano. |
| Deslocamento | `chegada_sede_data`, `chegada_sede_hora` | Data/Hora de chegada à sede | date + time, N | Se os quatro existem, chegada deve ser posterior à saída. |

Qualquer mudança no efetivo/deslocamento consulta o cálculo e atualiza fatos
readonly: Valor total do plano, Valor por servidor, Quantidade/composição de
diárias, Efetivo total e valores por extenso. Ações: adicionar/remover efetivo,
−/+, datas/horas, Voltar e Salvar e avançar.

### Wizard — etapa 3, Atividades

| Nome técnico | Label | Tipo / Req. / origem | Comportamento/persistência |
|---|---|---|---|
| `atividade_<codigo>` (checkboxes com `data-pt-activity-checkbox`) | Atividade | checkbox cards multi, N/R, BD | Seleção é serializada pelo autosave e salva atividades escolhidas no plano. Cada item traz meta/recurso do catálogo. |
| `data-pt-activity-search` | Filtrar atividades | search, N | Filtra cartões somente no cliente. |
| `data-pt-activity-select-all` | Selecionar todas | checkbox/botão, N | Marca atividades visíveis. |
| `data-pt-activity-preset` | Preset de atividades | select, N, BD | Ao mudar, pode pedir confirmação antes de substituir seleção; ação Gerenciar presets. |
| Limpar seleção | — | botão | Desmarca todas e limpa preset. |

Metas e recursos são listas readonly recalculadas da seleção. Ações: Gerenciar
atividades/presets com autosave, Voltar, Salvar e avançar.

### Etapa 4, Documentos; eventos internos

Documentos: Voltar, Salvar rascunho, Finalizar plano, visualizar PDF inline,
baixar PDF e DOCX. `EventoPlanoForm` aparece nos fluxos multi-evento: `ordem`
(hidden, S), `programa` (select N), `programa_outros` (texto N), datas início/fim
(hiddens N), `horario_atendimento` (texto N). Cada evento pode ter
`EfetivoEventoForm` (unidade N, cargo/quantidade condicionais como o efetivo do
plano), editar e remover via endpoints `evento_adicionar`, `evento_update`,
`evento_remover`.

## 11. Prestação de contas

### Lista operacional

Filtros GET: `q` e `aba` (situação/liberação); limpar e paginação. Cada prestação é
agrupada por ofício e servidor, com chips/status e ações condicionais para Relatório
Técnico, Diário de Bordo, Documentos, Consolidado, downloads, assinatura,
finalização e arquivamento. Menus são carregados por `prestacoes_contas:card_menus`.

Campos por servidor presentes nos cartões/documentos:

| Nome técnico | Label | Tipo / Req. | Validação, dependência e persistência |
|---|---|---|---|
| `ps-<id>-numero_solicitacao` | Número da solicitação | texto, N | Espaços normalizados; `PrestacaoServidor.numero_solicitacao`; autosave individual `prestacao_servidor_solicitacao_autosave` e salvamento em lote. Usado no carimbo do ofício. |
| `ps-<id>-data_liberacao_diarias` | Data de liberação | date picker/hidden, N | ISO validado pelo service; `PrestacaoServidor.data_liberacao_diarias`. |
| `ps-<id>-prazo_limite_saque` | Prazo limite de saque | date picker/hidden, N | ISO validado; constraint garante prazo >= liberação quando ambos existem; campo homônimo. |
| `ps-<id>-diaria_valor_override` | Diária recebida por este servidor | texto monetário, N | Parser separa valor/observação; nunca pode superar liberado e, no modelo, valor deve ser positivo. Salva `diaria_valor_override` + `_observacao`; vazio usa valor padrão. |

O botão/copiar mensagem de diária usa número de solicitação, liberação e prazo;
fica bloqueado por validações no JS quando faltam dados ou liberação é futura. A
mudança da aba de liberação depende de `data_liberacao_diarias`, não apenas de um
status visual.

### Relatório Técnico — `RelatorioTecnicoForm`

Autosave `rt_autosave`; página coletiva `rt_criar` e individual `rt_servidor`.

| Seção | Nome técnico | Label | Tipo / Req. / origem | Dependências, validação e persistência |
|---|---|---|---|---|
| Custeios | `diaria` | Diária | texto, N | Texto livre/default do contexto; `RelatorioTecnico.diaria`. O valor individual acima pode alterar apenas o RT daquele servidor. |
| Custeios | `translado` | Translado | select, N | “Não houve” ou Outro; default “Não houve”. `RelatorioTecnico.translado`. |
| Custeios | `translado_outro` | Informe translado | texto, C | Só habilitado em Outro; obrigatório nesse caso e copiado para `translado`; não é campo separado do modelo. |
| Custeios | `combustivel` | Combustível | select, N | “Cartão Prime” ou Outro; default Cartão Prime. Campo do RT. |
| Custeios | `combustivel_outro` | Informe combustível | texto, C | Mesma regra de Outro. |
| Custeios | `passagem` | Passagem | select, N | “Não houve” ou Outro; default Não houve. Campo do RT. |
| Custeios | `passagem_outro` | Informe passagem | texto, C | Mesma regra de Outro. |
| Tópicos | `modelo_motivo`, `modelo_atividade`, `modelo_conclusao`, `modelo_medidas`, `modelo_info_complementares` | Modelo | select, N, BD | Cinco campos dinâmicos filtrados por tópico/área; escolha copia texto para textarea alvo; não persiste FK. Ação Gerenciar modelos. |
| Tópicos | `motivo` | Descrição do evento | textarea, N | `RelatorioTecnico.motivo`. |
| Tópicos | `atividade` | Objetivo da participação | textarea, N | Campo homônimo. |
| Tópicos | `conclusao` | Conclusão | textarea, N | Campo homônimo. |
| Tópicos | `medidas` | Medidas a serem adotadas pelo órgão | textarea, N | Campo homônimo. |
| Tópicos | `info_complementares` | Informações complementares | textarea, N | Campo homônimo. |

Modelos de RT: `campo` (select, S, um dos cinco tópicos), `nome` (texto, S) e
`texto` (textarea, S). A lista agrupa por aba/tópico, busca `q`, cria/edita/exclui.
O RT oferece prévia/download por servidor, geração/cancelamento de solicitação de
assinatura e avanço ao Diário.

### Diário de bordo — trechos

| Ocorrência | Nome técnico | Label | Tipo / Req. | Validação/persistência |
|---|---|---|---|---|
| Por trecho R | `<prefix>-km_inicial` | KM inicial | texto numérico, N | Remove não dígitos e salva inteiro/None em `DiarioBordoTrecho.km_inicial`. |
| Por trecho R | `<prefix>-km_final` | KM final | texto numérico, N | Mesmo; `km_final`. A ordenação/relação entre KM deve ser confirmada no eixo de regras/service. |
| Por trecho R | `<prefix>-abastecimento` | Necessidade de abastecimento | select Sim/Não, N | Default Sim quando ainda vazio; salva booleano `abastecimento`. |
| Readonly | origem/destino/datas/horas | Rota e período | texto readonly, A | Vêm do roteiro; não são edição nessa tela. |

Ações: Trocar motorista, Editar trechos, definir roteiro se vazio, autosave
`diario_autosave`, visualizar PDF, baixar PDF/XLSX, voltar ao RT e avançar para
Documentos.

### Troca de motorista e viatura do diário — `DiarioMotoristaForm`

Essa alteração vale somente para o diário; o ofício original não é alterado.

| Grupo | Nome técnico | Label | Tipo / Req. / origem | Dependências/validação/persistência |
|---|---|---|---|---|
| Motorista | `motorista_modo` | Do ofício / Servidor / Outro ofício | radio cards, N/default Ofício | Controla painéis e limpeza dos overrides; `DiarioBordo.motorista_modo`. |
| Motorista servidor | `motorista_servidor` | Servidor deste ofício | select, C, BD | Exigido no modo SERVIDOR; opções somente equipe do ofício; campo homônimo. |
| Motorista externo | `motorista_manual_nome` | Nome do motorista | texto, C | Exigido no modo OUTRO; normaliza espaços; campo homônimo. |
| Motorista externo | `motorista_manual_cpf` | CPF | máscara, N | Mantém até 11 dígitos; campo homônimo. O form não chama verificador de CPF. |
| Motorista externo | `motorista_oficio_referencia` | Ofício do motorista | texto, N | Limite 16; campo homônimo. |
| Motorista externo | `motorista_protocolo_ref` | Protocolo do motorista | máscara, N | Normaliza protocolo; campo homônimo. |
| Prefill | `dmv-oficio-prefill` | Ofício de origem | select UI, N | `document-source.js` copia motorista, referência, protocolo e viatura; todos continuam editáveis. Não persiste por si. |
| Viatura | `viatura_modo` | Do ofício / Cadastro / Manual | radio cards, N/default Ofício | Controla painéis/limpa overrides; campo homônimo. |
| Viatura BD | `viatura` | Viatura do cadastro | select, C, BD | Exigida em BANCO; campo homônimo. |
| Viatura manual | `viatura_manual_modelo` | Modelo | texto, C | Exigido em MANUAL; normaliza espaços. |
| Viatura manual | `viatura_manual_placa` | Placa | máscara, N | Remove pontuação, maiúsculas, até 8; sem validação completa de formato neste form. |
| Viatura manual | `viatura_manual_tipo` | Tipo | select, N, fixo | `Viatura.TIPO_CHOICES`; campo homônimo. |
| Viatura manual | `viatura_manual_combustivel` | Combustível | texto, N | normaliza espaços; campo homônimo. |

Ações Cancelar e Salvar alterações; endpoint `diario_motorista`. JS alterna grupos
e aplica prefill do ofício.

### Documentos da prestação

Campos e uploads:

- `numero_solicitacao` por servidor, com autosave já descrito.
- `despacho_arquivos`: upload múltiplo opcional, despacho assinado compartilhado.
- `comprovante_arquivos`: upload múltiplo opcional por servidor.
- `rt_assinado_arquivos`: upload múltiplo opcional por servidor.
- `diario_assinado_arquivos`: upload múltiplo opcional e gravado somente para o
  motorista.
- Modal moderno usa `arquivo` (single/multiple conforme gatilho) e `next` hidden;
  aceita PDF para assinado e PDF/PNG/JPEG nos anexos comuns. Validador central
  `validate_private_document_upload` verifica a política de conteúdo; o nome
  original é preservado em `PrestacaoDocumentoAnexo.nome_original`.

Ações: escolher, pré-visualizar seleção, remover seleção, anexar; abrir/remover
arquivo já anexado; ajustar posição do carimbo quando houver ofício assinado;
finalizar/arquivar prestação; ir ao Consolidado. Endpoints de autosave/anexo/delete
estão em `prestacoes_contas/urls.py` (`prestacao_arquivo_autosave`,
`prestacao_servidor_arquivo_autosave`, `prestacao_documento_delete`, etc.).

### Ajuste de carimbo e consolidado

`carimbo_ajustar.html` repete por caixa os hiddens
`caixa-<ps>-pagina`, `-x`, `-y`, `-tamanho`; o usuário arrasta/redimensiona sobre
o PDF e salva posição. Ações “Ir para a caixa”, Salvar posição e Voltar. O texto
carimbado usa o número atual da solicitação. Consolidado é leitura/download: gera
pacotes por servidor e compilado, sem inputs editoriais; ações de download e volta.

### Assinatura pública

Fluxo por token: landing → identidade → assinar um ou mais documentos → concluído.

| Página | Nome técnico | Label | Tipo / Req. | Validação/efeito |
|---|---|---|---|---|
| Identidade | `confirma_nome` | Confirmo que sou … | checkbox card, C | Confirma nome readonly vindo do documento. `assinatura-identidade.js` participa da habilitação/validação. |
| Identidade | `cpf` | Seu CPF | texto mascarado, S | Até 14 caracteres; backend confere identidade/token; tentativas em excesso bloqueiam temporariamente. Não expor CPF na documentação. |
| Assinar | `asgn-name-input` | Nome que aparecerá na assinatura | texto UI, N | Preenche prévias de fontes; limite 60. |
| Assinar | fonte | Assinatura na fonte … | choice cards, C | Seleciona uma fonte para gerar imagem; alternativa é desenhar em canvas. |
| Assinar | canvas `asgn-draw` | Desenhar à mão | desenho, C | Gera PNG em memória; Limpar apaga. |
| Posicionamento | `assinatura_png` | — | hidden, S para envio | Imagem base64/PNG gerada; enviada no POST. |
| Posicionamento | `modo`, `fonte` | — | hiddens, C | Registram modo fonte/desenho e fonte escolhida. |
| Posicionamento | `pagina`, `pos_x`, `pos_y`, `largura`, `altura` | — | hiddens, S após posicionar | `pdf-place.js` atualiza ao arrastar/redimensionar; botão Enviar nasce desabilitado até assinatura válida/posição. |

Ações: Começar; Continuar para assinar; Criar assinatura; fonte/desenho; Limpar;
Cancelar/Usar assinatura; página anterior/próxima; arrastar/redimensionar; Enviar
assinatura. Os endpoints são `assinatura_landing`, `identidade`, `assinar`,
`pdf_origem` e `concluido`.

## 12. Central de Protocolos

### Lista e criação

Lista: `q` e `status`, limpar, paginação; ação Novo protocolo e abrir detalhe.
`protocolos/form.html` oferece dois POSTs separados:

| Caminho | Nome técnico | Label | Tipo / Req. / origem | Validação/efeito |
|---|---|---|---|---|
| Protocolar ofício | `oficio` | Ofício | select, S, BD | Só ofícios protocoláveis segundo selector (sem protocolo na Central). POST `protocolos:vincular`; cria/vincula protocolo. |
| Protocolar ofício | `content_type_id` | — | hidden, A | ContentType de Ofício para o vínculo. |
| Protocolar ofício | `enviar_documento=1` | — | hidden, A | Obriga envio do PDF do ofício nesse caminho. O campo booleano equivalente do form tem default marcado. |
| Vincular existente | `numero` | Número do protocolo | texto, N | `normalize_protocolo`; aceita vazio se ainda não houver número. |
| Vincular existente | `assunto` | Assunto | texto, N | Até 255. |
| Vincular existente | `descricao` | Descrição | textarea, N | Texto manual. |

Botões: Protocolar ofício e Cadastrar protocolo. Em modo demonstração, a tela
informa que não chama o eProtocolo real.

### Detalhe e envio de documento

Detalhe é leitura: fatos de número, status, situação externa, origem, órgão, local,
responsável e sincronização; listas de documentos, pendências, assinaturas,
tramitações e movimentações. Ações **Enviar documento** e **Sincronizar**.

| Nome técnico | Label | Tipo / Req. | Validação/efeito |
|---|---|---|---|
| `tipo_documento` | Tipo de documento | select, S | Anexo manual, Ofício, Termo, Justificativa, Plano ou OS. |
| `arquivo` | Arquivo PDF | file, C | Obrigatório se geração automática não marcada; extensão PDF ou MIME `application/pdf`. |
| `nome_arquivo` | Nome do arquivo | texto, N | Até 255; metadado do documento. |
| `usar_documento_principal` | Gerar e enviar o documento vinculado automaticamente | checkbox, N | Se marcado dispensa upload e usa documento principal vinculado. |

Ações Enviar documento e Voltar; endpoint `protocolos:enviar_documento`.

### Formulários existentes sem ligação ativa confirmada

`SolicitarAssinaturaForm` (`documento` N, `servidor` N, `cpf` C, `nome` N,
`observacao` N) exige servidor ou CPF; CPF deve ter 11 dígitos válidos e pode ser
preenchido do servidor. `TramitarForm` possui `cod_local_para` obrigatório,
`nome_local_para`, `cpf_destinatario`, `nome_destinatario` e `parecer` opcionais;
CPF, quando existe, é validado. As classes existem, mas não foi encontrada rota
ativa/template consumidor em `protocolos/urls.py` nesta passagem. Portanto **não
devem ser apresentadas como recurso operacional ativo sem confirmação adicional**.

## 13. Usuários e áreas de trabalho

### Usuários

Lista com busca por nome/usuário/e-mail/área, navegação Usuários/Áreas, inclusão
rápida, editar, excluir e modal Vincular usuário.

| Fluxo | Nome técnico | Label | Tipo / Req. / origem | Validação/persistência |
|---|---|---|---|---|
| Criar | `username` | Nome de usuário | texto, S | Validador Django (até 150 e caracteres permitidos); `User.username`. |
| Criar | `email` | E-mail institucional | email, N | `User.email`. |
| Criar | `nome_completo` | Nome completo | texto, S | Separado em nome/sobrenome pelo form/service de usuário. |
| Criar | `password1`, `password2` | Senha / Confirmação | password, S | Devem coincidir e passam pela política de senha. |
| Criar | `area` | Área de trabalho | select, S, BD | Cria vínculo inicial. |
| Criar | `papel` | Perfil na área | select, S, fixo | Choices de papel do vínculo; persiste `UsuarioArea.papel`/modelo equivalente. |
| Editar | `username`, `email`, `nome_completo` | mesmos | texto/email, S/N/S | Edita dados sem expor senha. |

### Vínculos e áreas

`AreaTrabalhoForm`: `nome` e `sigla`, ambos texto obrigatório, persistidos em
`AreaTrabalho`. Na edição há lista paginada dos usuários da área e ação **Vincular
usuário**. `VinculoNaAreaForm`: `usuario` (select S, usuários elegíveis), `area`
(hidden S, área atual), `papel` (select S). No sentido inverso,
`VinculoUsuarioAreaForm`: `usuario` hidden, `area` select e `papel` select, todos
obrigatórios. Ações Cancelar/Salvar vínculo e Remover acesso por modal; endpoints
`usuarios:vinculo_create`, `vinculo_create_na_area`, `vinculo_delete`.

## 14. Documentos e visualizador PDF

`documentos:index` é um hub/lista de gerações/artefatos; as ações concretas são
abrir resultado, aguardar/polling de geração e voltar. `geracao_status` é consultado
por `document-generation-wait.js`; `geracao_resultado` redireciona/entrega saída.

O visualizador PDF possui: Voltar, página Anterior/Seguinte, slider `doc-pdf-zoom`
(50–200%, default 100), Abrir PDF, Baixar, Imprimir e, quando fornecido, Copiar link
temporário. O slider/controles afetam apenas a visualização; conteúdo vem de
`artefato_pdf_conteudo`; compartilhamento usa rota temporária. Nenhum campo de
modelo é editado nesta página.

## 15. Busca, filtros, chips, badges e ações transversais

### Matriz de filtros das listas

| Página | Busca | Filtros/ordenação adicionais | Limpar |
|---|---|---|---|
| Ofícios | `q` | `aba`, `sort`, viagem de/até, criação de/até | `search_clear_url` |
| Eventos | `q` | `aba`/status | sim |
| Roteiros | `q` | `aba`/status | sim |
| Termos | `q` | `aba` | sim |
| Ordens de Serviço | `q` | `aba`, `sort`, viagem de/até | sim |
| Planos de Trabalho | `q` | `aba`, `sort`, viagem de/até | sim |
| Prestações | `q` | `aba` | sim |
| Protocolos | `q` | `status` | sim |
| Servidores | `q` | cargo | sim |
| Viaturas | `q` | unidade ou combustível | sim |
| Catálogos rápidos | `q` | em Usuários/Áreas, toggle administrativo; modelos RT, aba de tópico | conforme busca |

Todos usam filtro no servidor quando a lista é paginada (`filter_mode=none` na
coleção), evitando filtrar só a página atual. `server-filter.js` submete com debounce
ou navega para a URL do filtro. Os date pickers de filtro enviam hiddens ISO.

### Chips e badges com significado comprovado

- chips de situação/tom em Ofício, Evento, Termo, OS, Plano, Prestação e Protocolo
  são calculados pelos presenters e informativos; o clique não muda status;
- badges em pessoas/documentos mostram protocolo, número de ofício, tipo ou estado
  do artefato e não são controles por si;
- contadores em toggles/abas navegam e aplicam o filtro correspondente;
- chips de sugestão de viatura no Ofício são botões selecionáveis (`aria-pressed`)
  e alteram `viatura`; chips de atividades/choice cards alteram checkboxes;
- o chip de progresso da assinatura (“N de total”) é apenas informativo.

### Ações de card/lista por família

- **Criar**: FAB/ação principal ou expansão de cadastro rápido.
- **Editar/continuar**: link direto ou etapa atual do wizard.
- **Visualizar**: detalhe, preview inline, PDF em nova aba.
- **Baixar**: PDF, DOCX, XLSX, compilado ou formato selecionado; itens podem nascer
  desabilitados quando documento ainda não existe.
- **Anexar/gerenciar assinado**: modal compartilhado, arquivo atual substituível ou
  removível.
- **Excluir**: modal/página de confirmação; o backend decide proteção por vínculo.
- **Cancelar/reativar/retificar/complementar/finalizar/arquivar**: aparecem conforme
  domínio/estado; efeito e transição exatos precisam ser cruzados com regras e
  presenters, pois o template recebe as ações já resolvidas.

## 16. Contagens consolidadas e pendências de confirmação

### Contagem

- 56 classes concretas de formulário auditadas.
- 285 declarações `base_fields` somadas nas classes (com herança/variantes).
- Pelo menos 47 nomes/famílias técnicas de controles relevantes adicionais encontrados em
  templates/JS; formsets e linhas de destino/trecho podem produzir ocorrências sem
  limite fixo.
- 19 famílias de componente compartilhado descritas.
- 15 grupos de listagem/filtro cobertos (7 operacionais centrais, Protocolos,
  Servidores, Viaturas e catálogos auxiliares).

### Não confirmado ou dependente de outro eixo

1. **Comportamento visual em navegador**: esta foi auditoria estática; não se
   confirmou foco, overlays, mensagens e estados de habilitação em execução.
2. **Protocolos – solicitar assinatura/tramitar**: classes de formulário existem,
   mas não há rota/template consumidor ativo encontrado; manter fora da apresentação
   operacional até prova de ligação.
3. **`EventoForm` versus fluxo guiado**: ambos têm rota ativa, porém a prevalência de
   cada tela por perfil/estado deve ser confirmada na navegação real.
4. **Ações condicionais dos menus de card**: labels/URLs são montados por presenters;
   a matriz completa status → ação pertence ao eixo de regras/permissões.
5. **Campos de roteiro por trecho**: nomes são produzidos dinamicamente pelo editor e
   parser; a ocorrência depende do número de destinos/trechos. Os prefixos descritos
   precisam ser validados em HTML renderizado para um roteiro com vários trechos.
6. **Persistência das flags `*_auto` do Plano**: comprovou-se seu uso no POST/JS, mas
   não um campo de modelo com o mesmo nome.
7. **Upload de protocolos**: a validação local aceita extensão `.pdf` ou MIME PDF;
   validação profunda de conteúdo, tamanho e integração externa deve ser verificada
   no service/eixo de segurança.
8. **Opções exatas de enums** (`tipo_necessidade`, papéis, custeio, status, gênero,
   tipos de viatura): a fonte foi identificada, mas os rótulos completos devem ser
   extraídos dos modelos para slides que listem cada opção.
9. **Campos de `data_liberacao_diarias`/`prazo_limite_saque`**: renderizados por
   template e salvos pelo service, não pertencem a `PrestacaoSolicitacaoForm`; foram
   inventariados como controles dinâmicos e não como fields Django.
10. **Dados pessoais**: opções de pickers contêm CPF/RG/telefone em metadados de
    busca. O manual e screenshots devem usar dados sintéticos e nunca reproduzir
    valores locais.

## 17. Arquivos-fonte principais para rastreio

- Formulários: `cadastros/forms.py`, `core/forms/__init__.py`, `eventos/forms.py`,
  `justificativas/forms.py`, `oficios/forms.py`, `ordens_servico/forms.py`,
  `planos_trabalho/forms.py`, `prestacoes_contas/forms.py`, `protocolos/forms.py`,
  `roteiros/forms.py`, `termos/forms.py`, `usuarios/forms.py`.
- Templates: `templates/<app>/` e componentes em `templates/cotton/v2/`.
- JS de domínio: `static/js/pages/`; motores compartilhados em
  `static/js/components/` (`picker`, `location-rows`, `date-picker`, `file-picker`,
  `document-source`, `overlay`, `state-toggle`, `pdf-place`).
- Endpoints: `*/urls.py`; autosaves e APIs citados nas seções correspondentes.

## 18. Cruzamento Form → página/template

Este índice explica a contagem de 56 classes e evita que uma classe existente seja
confundida com uma página ativa independente.

| Módulo | Form(s) | Consumidor comprovado / observação |
|---|---|---|
| Core | `LoginForm` | `templates/core/login.html`, `core:login`. |
| Core | `PerfilUsuarioForm`, `AlterarSenhaForm` | `templates/core/perfil.html`, `core:perfil`. |
| Cadastros | `UnidadeForm` | `templates/cadastros/unidades/index.html`, inclusão rápida/edição. |
| Cadastros | `EstadoForm` | `templates/cadastros/estados/index.html` e edição/confirmação. |
| Cadastros | `CidadeForm` | `templates/cadastros/cidades/index.html`, inclusão rápida. |
| Cadastros | `CargoForm` | `templates/cadastros/cargos/index.html`, inclusão/edição/padrão. |
| Cadastros | `CombustivelForm` | `templates/cadastros/combustiveis/index.html`, inclusão/edição/padrão. |
| Cadastros | `ServidorForm` | `templates/cadastros/servidores/form.html`. |
| Cadastros | `ViaturaForm` | `templates/cadastros/viaturas/form.html`. |
| Configuração | `ConfiguracaoSistemaForm`, `ConfiguracaoAssinaturasForm`, `ConfiguracaoDestinatarioForm`, `TabelaDiariaForm` | `templates/cadastros/configuracao/form.html` e partials das três abas. |
| Eventos | `EventoNovoCadastroForm` | `templates/eventos/detalhe.html`, fluxo guiado. |
| Eventos | `EventoForm` | `templates/eventos/form.html`, edição administrativa. |
| Eventos | `TipoEventoForm` | `templates/eventos/tipos/index.html`. |
| Justificativas | `JustificativaQuickAddForm` | `templates/justificativas/index.html`. |
| Justificativas | `JustificativaOficioForm` | etapa de justificativa do ofício, montada em `oficios/wizard_document_views.py`. |
| Justificativas | `ModeloJustificativaForm` | `templates/justificativas/modelos/index.html`. |
| Ofícios | `OficioDadosViajantesForm` | `templates/oficios/wizard_dados_viajantes.html`. |
| Ofícios | `OficioTransporteForm` | `templates/oficios/wizard_transporte.html` e transporte embutido. |
| Ofícios | `ModeloMotivoOficioForm` | `templates/oficios/modelos_motivo/index.html`. |
| Ofícios | `OficioForm` | Classe-base de `OficioDadosViajantesForm`; uso direto só encontrado em testes, não apresentar como formulário separado. |
| Roteiros | `RoteiroForm` | `templates/roteiros/roteiro_form_page.html` e editor embutido. |
| Termos | `TermoAutorizacaoForm` | `templates/termos/form.html`. |
| OS | `OrdemServicoForm` | `templates/ordens_servico/form.html`. |
| Planos | `PlanoIdentificacaoForm` | `templates/planos_trabalho/wizard_identificacao.html`. |
| Planos | `PlanoDiariasForm`, `EfetivoPlanoForm` | `wizard_efetivo_diarias.html`, formset de efetivo. |
| Planos | `AtividadePlanoTrabalhoForm`, `AtividadePlanoTrabalhoQuickAddForm` | catálogo `atividades/index.html`; edição e inclusão rápida. |
| Planos | `PresetAtividadesQuickAddForm` | `presets/index.html`. |
| Planos | `ProgramaSolicitanteForm` | `programas/index.html`. |
| Planos | `HorarioAtendimentoForm` | `horarios/index.html`. |
| Planos | `EventoPlanoForm`, `EfetivoEventoForm` | subfluxo de eventos internos do plano. |
| Prestação | `RelatorioTecnicoForm`, `PrestacaoServidorDiariaForm` | `relatorio_tecnico_form.html` e linhas individuais do RT. |
| Prestação | `DiarioBordoTrechoForm` | `diario_bordo_form.html`, formset por trecho. |
| Prestação | `DiarioMotoristaForm` | `diario_motorista_form.html`. |
| Prestação | `PrestacaoSolicitacaoForm` | cartões/lista e `documentos_form.html`, prefixado por servidor. |
| Prestação | `PrestacaoDespachoForm`, `PrestacaoServidorDocumentosForm` | endpoints/partials de anexos; a UI atual também usa o modal global de assinado. |
| Prestação | `ModeloTextoRelatorioTecnicoForm` | `modelos_texto/index.html` e `form.html`. |
| Protocolos | `ProtocolarOficioForm`, `VinculoManualForm` | `templates/protocolos/form.html`, dois POSTs. |
| Protocolos | `AnexarDocumentoForm` | `templates/protocolos/enviar_documento.html`. |
| Protocolos | `SolicitarAssinaturaForm`, `TramitarForm` | Sem rota/template ativo confirmado; inventariados como não confirmados. |
| Usuários | `UsuarioAreaCreationForm` | inclusão/criação de usuário. |
| Usuários | `UsuarioEditForm` | `templates/usuarios/form.html`, edição. |
| Usuários | `AreaTrabalhoForm`, `AreaTrabalhoEditForm` | lista/criação e `templates/usuarios/areas/form.html`. |
| Usuários | `VinculoUsuarioAreaForm`, `VinculoNaAreaForm` | modais de vínculo em usuário/área. |
