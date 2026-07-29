# Plano de execução do refactor — como conduzir Claude, Cursor e Codex

**Origem:** as quatro auditorias de 27–28/07/2026 mais a auditoria de segurança.
**Função deste documento:** transformar 2.700 linhas de diagnóstico em uma fila de trabalho
com dono, ordem, gate e critério de pronto. É o único documento que muda durante o refactor —
as auditorias ficam congeladas como registro.

**Regras de conduta dos agentes:** [`AGENTS.md`](../AGENTS.md) (raiz) · **Prompts prontos:**
[`PROMPTS_REFATORACAO.md`](PROMPTS_REFATORACAO.md)

---

## 1. A resposta curta

**Comece pela Etapa 1 (correções críticas isoladas) e pela Etapa 2 (rede de segurança de
testes). Termine pela Etapa 7 (reconstrução do CSS) e Etapa 8 (higiene).**

O erro que destruiria o projeto é começar pelo CSS. A reconstrução do CSS é a etapa mais
visível, mais longa (35–45 dias-pessoa) e a mais tentadora — e é exatamente a que precisa de
todas as outras prontas antes:

- ela renomeia classes que **hoje são emitidas pelo Python** (`P-04`: 194 `attrs={...}` com
  classe CSS dentro de `forms.py`);
- ela mexe em telas cuja cobertura de teste é **0,04** (`T-01`, Prestações de Contas);
- ela reescreve componentes que ainda existem em 6 cópias divergentes (`H-01`, destinos).

Refatorar CSS nessas condições é reescrever a fachada de um prédio sem andaime.

## 2. A fila, do começo ao fim

| # | Etapa | Fonte | Dias | Risco | Por que aqui |
|---|---|---|---:|---|---|
| **1** | **Correções críticas isoladas** | Bloco 0 da AUDITORIA_FINAL | 8–12 | baixo | 16 defeitos 🔴 que não dependem de renomear nada. Se o calendário virar, você para aqui e o sistema já está apresentável. |
| **2** | **Rede de segurança** | Bloco 1 | 18–24 | baixo | Suíte de Prestações + *golden files* dos documentos + `coverage` no CI. É o andaime. Sem isto, toda etapa seguinte é aposta. |
| **3** | **Regra de negócio (diárias)** | Bloco 2 | 15–20 | **médio** | Dinheiro. Tabela de diárias sem vigência (`N-01`) é a pior resposta que a banca vai receber. Depende da Etapa 2. |
| **4** | **Backend de aderência** | Bloco 6 | 25–30 | baixo | Selectors, `core/catalog.py`, `core/errors.py` e **widget base com classes canônicas (`P-04`)** — este último é pré-requisito duro das Etapas 6 e 7. |
| **5** | **Motores JS** | Bloco 3 | 30–40 | médio | 16 motores globais, `CV.registry.destroy`, fim das 6 cópias de destinos. Independe do CSS; pode correr em paralelo com a Etapa 4. |
| **6** | **Estrutura HTML** | Bloco 5 | 20–25 | médio | `flow_base` de wizard, card mestre, `form_block` selado, semântica e ARIA. Fixa **quais classes existem** — a Etapa 7 estiliza o resultado. |
| **7** | **Reconstrução do CSS** | Bloco 4 | 35–45 | médio | 36.771 → ~13.000 linhas, 4 camadas de token → 1, `oficio-lc` → `cv-record-card`. A mais longa, a mais visível, a mais reversível (a suíte não depende de nome de classe). |
| **8** | **Higiene e polimento** | Bloco 7 | 10–14 | zero | Repositório, docs históricos, microcopy, ícones, rate limit, e-mail, CSP. Fecha a conta. |

**Total: 161–210 dias-pessoa.** Solo com alavancagem de IA: 2,5–3,5 meses.

### Paralelismo permitido

```
Etapa 1 ──► Etapa 2 ──┬──► Etapa 3 (diárias)          ──┐
                      └──► Etapa 4 (backend) ──► Etapa 6 (HTML) ──► Etapa 7 (CSS) ──► Etapa 8
                           Etapa 5 (JS) ─────────────────┘
```

Etapas 3, 4 e 5 podem correr ao mesmo tempo em branches separadas — são camadas disjuntas.
**Etapas 6 e 7 nunca correm juntas**: o HTML define o nome, o CSS pinta o nome.

## 3. O corte mínimo, se o prazo apertar

Se houver banca/entrega antes do refactor completo, o mínimo aceitável é **Etapas 1 + 2 + 3**
(41–56 dias-pessoa). É o conjunto exato que elimina as quatro respostas negativas previstas:

| Pergunta da banca | Antes | Hoje |
|---|---|---|
| "E quando o valor da diária mudar?" | exigia deploy e recalculava o histórico | tabela com vigência, editável na tela; roteiro anterior mantém o valor da época |
| "A conta bate com o sistema oficial?" | não se sabia — ninguém tinha comparado | **bate ao centavo** nos cinco demonstrativos, com os cinco travados por teste |
| "A lista aguenta 500 ofícios?" | 11 MB de HTML, sem paginação | paginada |
| "O documento gerado confere?" | nenhum teste abria o arquivo | *golden files* dos 11 documentos |
| "Qual a cobertura?" | assimétrica, Prestações a 0,04 | piso por app no CI |

A segunda linha não estava prevista. Ela apareceu quando comparamos o cálculo
com o sistema oficial de solicitação e achamos **dois defeitos que nenhuma
auditoria tinha visto** (`NOVO-11` e a faixa de 12h do `N-08`), ambos mexendo
em dinheiro, um deles pagando a menor em toda viagem acima de 12 horas.
É a evidência de que auditoria por leitura tem limite: a régua veio de fora.

## 4. Quem faz o quê

A regra é: **Claude decide, Cursor enxerga, Codex executa em massa.**

| Etapa | Dono principal | Apoio | Por quê |
|---|---|---|---|
| 1 — Críticos isolados | **Codex** (defeitos CSS/JS pontuais) | Cursor para os 3 pares de contraste (`N-03`) | Cada defeito tem local exato e verificação objetiva |
| 2 — Rede de segurança | **Claude Code** | — | Escrever suíte de 5 etapas + assinatura pública exige entender o fluxo inteiro |
| 3 — Diárias | **Claude Code** (plan mode obrigatório) | Humano revisa a regra | Regra financeira com duas implementações conflitantes (`N-05`) |
| 4 — Backend | **Claude Code** (selectors, `core/errors.py`) | **Codex** para os 13 catálogos e o widget base | Selectors exigem julgamento; catálogo é repetição |
| 5 — Motores JS | **Claude Code** (desenho dos motores) | **Codex** para as migrações mecânicas (`fetch`→`CV.http`, 17 cópias de util) | Desenho de contrato `data-*` é arquitetura; a migração é braçal |
| 6 — HTML | **Claude Code** (componentes) | **Cursor** para conferir cada página migrada no navegador | Regressão estrutural só aparece na tela |
| 7 — CSS | **Codex** (fases 0–5: apagar morto, tokens) | **Cursor** (fases 6–13: aparência) + Claude para o gate de CI | Metade é deleção verificável, metade é olho |
| 8 — Higiene | **Codex** | — | Puramente mecânico |

**Um dono por PR.** Duas ferramentas na mesma branch produzem conflito de estilo e
perda de rastreabilidade.

## 5. Como conduzir cada ferramenta

### 5.1 O prompt padrão (vale para as três)

Todo prompt tem cinco partes. Sem qualquer uma delas o agente inventa escopo:

```
1. ETAPA e ID:      "Etapa 1, defeitos D-01 e D-04."
2. FONTE:           "Leia docs/AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md §4.1 — só essa seção."
3. ESCOPO FECHADO:  "Altere apenas static/css/components/. Não renomeie classe nenhuma."
4. GATE:            "Suíte verde + audit_frontend_standards sem aumentar avisos."
5. ENTREGA:         "PR com o template do AGENTS.md §5 e a linha do plano marcada."
```

Modelos prontos por etapa: [`PROMPTS_REFATORACAO.md`](PROMPTS_REFATORACAO.md).

### 5.2 Claude Code

- Uma etapa por sessão; abra o PR e encerre.
- Peça **plan mode** antes de escrever nas Etapas 3, 5, 6 e 7.
- Ele roda a suíte de verdade — exija o número de testes e o tempo no corpo do PR.
- Use subagente só para varredura ("ache todas as cópias de X"), nunca para editar.

### 5.3 Cursor

- Ele lê `AGENTS.md` automaticamente; não repita as regras no chat.
- Trabalhe com o servidor rodando e a tela ao lado: as etapas visuais existem porque
  o defeito **só se vê** (`D-20`: título quase preto sobre card escuro).
- Peça diff pequeno: um componente por vez, print antes/depois nos dois temas.
- Não peça a ele varreduras de 60 arquivos — é onde ele fica caro e impreciso.

### 5.4 Codex

- Ele funciona melhor com tarefa fechada e verificação por comando. Sempre termine o prompt
  com o comando que prova o resultado:
  `"pronto = python scripts/audit_frontend_standards.py --max-warnings 461 sai com 0"`.
- Para deleção, exija a prova de `grep` no corpo do PR (regra 6 do `AGENTS.md`).
- Vários PRs pequenos e paralelos > um PR grande. É a ferramenta certa para as fases 0–2 da
  reconstrução CSS (−3.000 linhas de CSS morto, risco zero).

### 5.5 O que nunca delegar

Decisão de produto continua sendo sua: qual a tabela de diárias vigente, se `diario_bordo`
vive ou morre (`P-08`), qual motor de PDF é o canônico (`D-01` do backend). Os agentes
implementam a decisão; não a tomam.

### 5.6 A mecânica: branch, PR e merge

**Nada é feito no `main`.** O `main` só recebe merge de PR aprovado e com CI verde.

**Uma branch por PR, sempre a partir do `main` atualizado:**

```bash
git checkout main
git pull origin main            # SEMPRE antes de criar a branch
git checkout -b codex/etapa1-componentes-globais
# ... trabalho ...
git push -u origin codex/etapa1-componentes-globais
# abrir PR em draft; sair do draft quando o gate da etapa passar
```

**Convenção de nome:** `<ferramenta>/etapa<N>-<assunto>`. A ferramenta no prefixo faz o
histórico mostrar quem fez o quê sem abrir o PR — e deixa evidente se duas ferramentas
encostaram na mesma camada, o que a §4 proíbe.

```
codex/etapa1-componentes-globais       cursor/etapa1-contraste-wcag
claude/etapa2-suite-prestacoes         claude/etapa3-diarias-vigencia
codex/etapa7-css-morto                 cursor/etapa7-record-card
```

**Nunca empilhe branch sobre branch.** Se a Etapa 6 depende da 4.b, espere a 4.b entrar no
`main` e só então crie a branch da 6 a partir dele. Branch empilhada transforma um conflito
em três.

**Depois de cada merge**, atualize o `main` local antes da próxima branch. Quem pula esse
passo refaz trabalho já mergeado.

**Se o `main` andar enquanto seu PR está aberto:** traga o `main` para dentro da sua branch
(`git merge origin/main`), resolva na sua branch e empurre. Nunca o contrário.

---

## 6. Gates — o que trava a regressão

Cada etapa entrega, além do código, **um teste de CI que impede o defeito de voltar**. Sem
isso o refactor vira esteira: conserta na frente, quebra atrás.

| Etapa | Gate a adicionar em `.github/workflows/tests.yml` |
|---|---|
| 1 | Nenhum (correções pontuais já cobertas pela catraca existente) |
| 2 | `coverage` com **piso por app**; falha se algum app cair abaixo do piso |
| 3 | Teste de vigência de diária + teste de congelamento do valor no documento |
| 4 | Teste anti-ORM-em-view (`P-01`); `makemigrations --check` já existe |
| 5 | (a) todo `data-*` emitido tem motor; (b) todo JS de componente registra enhancer; (c) zero `fetch(`/`alert`/`confirm` fora do núcleo |
| 6 | Nenhum include de componente sem `only` |
| 7 | Zero literal de cor fora dos arquivos de token; zero classe de template sem CSS |
| 8 | `pip-audit` e `check --deploy` já existem; adicionar checagem de arquivos indevidos |

A catraca já existente — `python scripts/audit_frontend_standards.py --max-warnings 465` —
tem o número **reduzido a cada PR**. Ele nunca sobe.

## 7. Quadro de acompanhamento

Marque aqui, no mesmo PR que faz o trabalho. `[ ]` pendente · `[~]` em andamento · `[x]` pronto.

### Etapa 1 — Correções críticas isoladas
- [x] `D-01` toast de download sem fundo/sombra (aparece em toda a aplicação)
- [x] `D-02` `.cv-dialog--danger/--warning/--success/--document` sem CSS
- [x] `D-03` `.summary-items` sem estilo (Dashboard)
- [x] `D-04` `variant="muted"` de botão inexistente
- [x] `D-20` / `D-21` `.pte-card` sem regra dark, texto quase preto
- [x] `D-22` `.app-card-toggle` pastel claro em tema escuro
- [x] `J-05` `extra-download.js` morto em 4 módulos — **o enunciado estava vencido**:
  só Eventos passa `extra_download_url`, e só Eventos carregava o script, então não
  havia recurso morto. O defeito real era a armadilha: componente global
  (`rich_menu_link`) com motor local. Script movido para o `base.html`. Junto,
  `J-14`: `masks.js` era carregado duas vezes em `diario_motorista_form` (duas cópias,
  `?v=` diferentes).
- [x] `J-11` `data-confirm-submit` dispara `confirm()` duas vezes — **só ao aceitar**,
  e só quando o atributo está no `<form>`; ao cancelar, o `preventDefault` do clique
  escondia o defeito. A correção sugerida pela auditoria (ouvir só `submit`) teria
  **removido a confirmação** dos botões de excluir, que carregam o atributo no próprio
  `<button>`. Um ouvinte só, resolvendo o dono a partir do `event.submitter`.
- [x] `N-02` listas de Ofícios e OS sem paginação
- [x] `N-03` 3 pares de cor abaixo de 2,3:1
- [x] `N-07` paginação incluída em listas sem `page_obj`
- [x] `S-01` chave Fernet literal em `dev.py` (rotacionar) — **zero chave commitada**:
  dev exige a do `.env` (e recusa placeholder), teste gera a cada execução, CI gera
  no runner. O gate declarado no prompt ("zero chave literal") estava mal formulado,
  mas a intuição era certa: tentei primeiro manter literais "descartáveis" e o
  GitGuardian reprovou — chave Fernet válida commitada é indistinguível de segredo
  real, para o scanner e para quem lê. O critério final é o mais simples: nenhuma.
- [x] tokens indefinidos (`D-01`, `D-03`, `D-06`, `D-20`, `D-21`) — medidos, não
  estimados: sobravam **7**, não 18 (os PRs #64 e #65 já haviam fechado o resto).
  Seis mapeados para tokens existentes; `--color-focus-ring` passou a ser definido
  nos dois temas (`D-06`). Verificação: zero `var(--x)` sem fallback e sem definição.

**Achados novos (28/07, fora das auditorias — descobertos ao destravar o CI):**

- [x] `NOVO-01` 🔴 O passo *restore drill* do CI nunca passou desde que foi criado (`39f16be`, 27/07): `pg_dump`/`pg_restore` liam o socket Unix local em vez do service container. **Corrigido** em `00930fb`.
- [x] `NOVO-02` 🔴 **A suíte é verde em SQLite e vermelha em PostgreSQL** — 2 falhas e 17 erros. Como o CI parava antes de chegar nos testes, isso ficou 5 commits invisível. Produção é PostgreSQL; a suíte local, SQLite. Enquanto essa divergência existir, "812 testes verdes" não é evidência de nada.
- [x] `NOVO-03` 🟠 16 dos 17 erros: os mocks do Google Drive montam `file_id`/`atalho_id` em formato de caminho (`mock-atalho-mock-pasta-mock-pasta-root-Eventos-…`) e estouram `varchar(200)`. SQLite ignora o limite; PostgreSQL não. IDs reais do Drive têm ~33 caracteres — **o defeito está no dublê de teste, não no schema**.
- [x] `NOVO-04` 🟠 `OficioNumberingConcurrencyTests` (`TransactionTestCase` com `reset_sequences = True`) colide com o signal de auditoria: `duplicate key value violates unique constraint "core_auditevent_pkey"`. O `AuditEvent` entrou em 27/07 e nunca rodou contra PostgreSQL.
- [x] `NOVO-05` 🟡 `test_servidores_index_limita_25_por_pagina` assume `pk=1` (`data-delete-url=".../servidores/1/excluir/"`) — dependente de sequência.
- [x] `NOVO-06` 🟡 `test_reprocessar_agenda_tasks_pendentes` responde 400 onde espera 302.

`NOVO-02`..`NOVO-06` **corrigidos e mergeados** (PR #62): 812 testes verdes nos dois bancos.
`NOVO-04` era defeito de produção, não de teste — migrações de dados escreviam na trilha de
auditoria; criar o banco deixava 23 eventos sem ator. Corrigido na raiz, com regressão.

> **Consequência para o plano:** a Etapa 2 só começa com a suíte verde em PostgreSQL — o
> banco de produção. Esse pré-requisito está satisfeito desde o PR #62; a regra permanece
> aqui porque toda etapa seguinte assume a mesma linha de base: **verde nos dois bancos**.

**Achados novos (28/07, descobertos ao medir a paginação de `N-02`):**

- [ ] `NOVO-07` 🟠 **N+1 real na lista de Ordens de Serviço** — ~6 queries por card
  (`ordens_servico/presenters.py`): `_destinos_display_os` refaz a query e anula o
  `prefetch_related` da view; `servidores.count()` roda por card; `_get_assinante_os()` relê o
  singleton de configuração por card. Com 300 OS eram **1.814 queries**; a paginação segurou em
  **135 por página**, mas o custo por card continua. Corrige a §4.1 da auditoria final: "não
  existe N+1" valia só para Ofícios. Fica para a Etapa 4 (camada de views/presenters) ou um PR
  próprio; o teste `ordens_servico/tests/test_list_performance.py` já trava o crescimento e tem
  o teto pronto para ser baixado.
- [x] `NOVO-08` 🟠 **`core/tests/` não tinha `__init__.py`** — 95 testes existentes nunca foram
  descobertos pelo runner (`manage.py test core` rodava 0 testes), incluindo
  `test_tenancy_integrity`, `test_sso`, `test_uploads` e `test_dark_redesign`. Corrigido na
  Etapa 1: todos passam, e a suíte de referência vai de **812 para 924 testes verdes**.

> **Etapa 1 fechada.** Catraca do CI baixada de 465 para **449** avisos. Suíte em 924
> testes verdes nos dois bancos. Três correções de rumo às auditorias ficaram registradas
> acima (`J-05`, `J-11`, tokens) — em todas, o enunciado original estava mais largo ou mais
> antigo do que o código.
>
> **Pendência aberta, herdada do `N-02`:** a paginação fez a busca em tempo real filtrar
> apenas a página corrente. É comportamento que vai ao usuário agora e só se resolve no
> `J-03` (Etapa 5). Decidir se recebe paliativo antes disso.

### Etapa 2 — Rede de segurança
- [x] `T-01` suíte de Prestações: 5 etapas + assinatura pública — **as 6 fatias**
  concluídas: listagem/entrada (12 asserções, isolamento por área pelo caminho real —
  vínculo + sessão + middleware, sem mock) e solicitação do servidor (14 asserções,
  os dois caminhos de gravação; divergência entre eles catalogada em `NOVO-09`) e
  comprovante/anexos (12 asserções, incluindo o portão do arquivo privado:
  anônimo vai ao login, anexo de outra área dá 404, e trocar a prestação-pai na
  URL não abre o arquivo) e relatório técnico (9 asserções, primeira fatia com
  dinheiro; `NOVO-10` catalogado) e finalização/arquivamento (12 asserções; os
  endpoints são alternadores e finalizar não tem pré-condição — caracterizado) e
  assinatura pública (8 asserções de borda: expiração, token adulterado,
  cancelamento, tipo ausente e reenvio). Cobertura do app: 72,00 → 74,59%.
- [x] `N-04` *golden files* dos 11 documentos gerados — 13 testes que **abrem** o
  arquivo produzido e comparam o texto. Cobrem o template, não o construtor de
  contexto: o contexto é sintético de propósito, para isolar as duas falhas. A
  correção dos valores é dos testes de cada módulo.
- [x] `T-03` `coverage` no CI com piso por app
- [ ] `D-02` (backend) testes de contrato de `organizer.py`

### Etapa 3 — Regra de negócio
- [x] `N-01` tabela de diárias com vigência — **as 3 partes** concluídas: o modelo
  `TabelaDiaria` com derivação de 15%/30% no `save()` e semente de `2000-01-01`
  reproduzindo os valores que estavam em código (parte 1, 14 testes); o cálculo
  resolvendo a tabela pela data de saída do roteiro em vez da constante do módulo
  (parte 2, 7 testes); e a seção **Valores de diária** na tela de configurações,
  com três campos onde só um é digitado (parte 3, 6 testes). Cobertura de
  `cadastros`: 60,05 → 62,36%.
  - Falta ainda o **congelamento do valor no roteiro** — hoje o histórico é
    preservado porque a vigência é resolvida pela data de saída, não porque o
    valor esteja gravado no documento. Enquanto a tabela só crescer com vigências
    novas o efeito é o mesmo; editar uma vigência já usada recalcularia o
    passado. Entra com `N-05`.
- [x] `NOVO-10` `diaria_valor_override` como dinheiro validado. O campo não era
  "valor diferente por capricho": é o **valor efetivamente recebido**, e a regra
  que ninguém aplicava é que ele **nunca passa do liberado** — o servidor pode
  receber menos (no saque o caixa não entrega centavos: de R$ 87,17 ele saca
  R$ 87,00), nunca mais. Virou `DecimalField` com teto validado nos dois
  caminhos de gravação, mais um campo de observação para o "(saque)" que antes
  dividia o mesmo `CharField` com o número. O documento sai idêntico. Migração
  exercitada no PostgreSQL contra dados legados; valores que não eram número
  viram observação, sem perda. Cobertura de `core`: 85,99 → 87,11%.
- [x] `NOVO-11` **limites de período pela chegada, não pela saída.** Achado ao
  investigar o `N-05`, comparando com o demonstrativo do sistema oficial de
  solicitação: o tempo de estrada entre dois destinos caía no trecho de retorno,
  que não carrega complemento, e não era cobrado. Dois roteiros de referência,
  antes → depois: R$ 661,81 → **R$ 773,19** e R$ 1.033,07 → **R$ 1.144,45**,
  ambos batendo ao centavo com o oficial. A hora de chegada já existia na tela e
  no banco (`RoteiroTrecho.chegada_dt`); só o cálculo a descartava.
- [x] `N-05` as duas regras de complemento eram **casos extremos de uma regra
  que faltava**: o *trecho tarifário*. O sistema oficial funde períodos
  consecutivos do mesmo grupo (três capitais seguidas = um trecho, com um
  complemento sobre a sobra da soma) e abre trecho novo quando o grupo muda.
  O ramo "por permanência" acertava quando os grupos alternavam a cada destino;
  o ramo "por viagem" acertava quando havia um grupo só. Ambos erravam no meio,
  que é o caso comum. Medido em 10.800 roteiros realistas: **21% davam valor
  diferente do oficial** antes, **0% depois**. Os três demonstrativos oficiais
  viraram teste. A auditoria descreveu o sintoma (duas regras) e não a causa —
  registro histórico mantido como está.
- [~] `NOVO-12` hospedagem 70% / alimentação 30%. O sistema oficial permite
  declarar "Sem Hospedagem" ou "Sem Alimentação" por trecho, zerando a parcela.
  **Decisão de produto (29/07/2026): não implementar as condições editáveis** —
  o ofício nunca pede menos do que o servidor tem direito, então a diária é
  sempre integral. Com as condições padrão o total já bate ao centavo, e é o que
  este sistema calcula. Sobra apenas a pergunta de apresentação: se algum dia o
  documento precisar exibir as duas colunas separadas, é derivação do valor que
  já existe (70% e 30%), sem mudança de regra nem de valor.
- [x] `N-06` **a base geográfica manda**; `CAPITAIS_POR_UF` vira rede de
  segurança para quando ela não tiver a UF. Medi antes de mexer: as 27 capitais
  **convergem** — não havia cobrança a menor, havia risco de passar a haver em
  silêncio. Por isso o teste que importa é o **anti-deriva**, comparando o mapa
  com `scripts/fixture_dados.json` (a base real, 5.571 municípios), e não com
  uma cópia de si mesmo. O fallback é deliberado: consulta seca faria todo
  destino virar `INTERIOR` num banco sem a base importada — a correção
  introduziria o defeito que ela corrige.
- [x] `N-08` / `N-10` **a escada do resto, por duração**. Os dois eram o mesmo
  defeito. A regra oficial, confirmada por cinco demonstrativos — um deles um
  experimento que isola a variável (12h01 dentro do mesmo dia, sem virada de
  meia-noite, rendendo 100%) — é: resto ≤6h nada · >6h≤8h 15% · >8h≤12h 30% ·
  **>12h uma diária cheia**. O calendário sai do cálculo, e com ele some a
  exceção que criava a segunda definição de "diária integral".
  Corrigia nos dois sentidos: pagava a menos em **todo trecho acima de 12
  horas** (até −R$ 259,88) e cobrava diária cheia por dois minutos entre 23:59
  e 00:01. Medido em 10.800 roteiros realistas: 0 divergência depois.
- [x] `N-09` **não reproduz — travado por teste.** Cada trecho calcula
  `valor_1_servidor × servidores`, então o total é o produto exato e a divisão
  de volta não perde centavo. O que faltava era a afirmação: 12 combinações
  (3 formatos de roteiro × 1, 2, 3 e 7 servidores) mais o caso de equipe vazia.
  Provado por canário — quebrando o arredondamento, o teste reprova apontando
  os dois valores. O teste que já existia prova que o total **escala** com a
  equipe, que é outra afirmação: escalar não garante reconciliar.
- [x] `N-10` pernoite curto — era a mesma causa do `N-08` e saiu no mesmo PR:
  o corte por duração aos 12 horas.
- [x] `P-03` **índices compostos**; as duas constraints candidatas foram
  recusadas com evidência, não por cautela. Correção ao enunciado: *toda FK já
  tem índice* (o Django cria por padrão) — o que faltava era o composto que casa
  com a ordenação. Medido: com ele o banco faz uma busca só; sem ele usa o
  índice da FK e monta B-tree temporária para ordenar.
  **Unicidade `(roteiro, ordem)`: recusada** — os trechos são atualizados no
  lugar (`roteiro_logic.py:1581`), então reordenar passa por estado transitório
  com ordens duplicadas e a constraint quebraria a tela.
  **`chegada_dt >= saida_dt`: recusada** — o modelo aceita invertido hoje e o
  `full_clean()` não reclama, então seria regra nova, não codificação de
  invariante. Entra junto com a validação, se você quiser.
- [x] `N-13` `REGRAS_DE_NEGOCIO.md`: 77 → 231 linhas. Diárias documentadas por
  inteiro (grupos, vigência, limites de período, trecho tarifário, faixas de
  complemento, valor recebido e as duas pendências conhecidas), mais numeração
  — três estratégias diferentes, descritas como são — e o vocabulário de status
  de cada fluxo. Corrigida a linha que dizia "não há cálculo de diárias", falsa
  desde a Etapa 3. Duas afirmações minhas estavam erradas na primeira escrita e
  foram corrigidas conferindo o código: o número é reservado na criação (não ao
  sair de rascunho), e a reserva do ofício roda em laço de até 3 tentativas.

> **Etapa 3 fechada.** Os dez defeitos do bloco de diárias saíram, e o cálculo
> passou a bater ao centavo com o sistema oficial de solicitação nos cinco
> demonstrativos levantados — todos travados por teste.
>
> **Dois dos maiores não estavam em auditoria nenhuma.** O `NOVO-11` (o período
> fechava na saída do trecho seguinte, e não na chegada, fazendo o tempo de
> estrada entre destinos sumir da conta) e a faixa de 12h do `N-08` (todo trecho
> acima de 12 horas pagava a menos) só apareceram porque comparamos com o
> sistema real. Três outros — `N-05`, `N-06` e `N-09` — eram **diferentes do que
> a auditoria descrevia**: um era outra causa, um não tinha efeito e um não
> reproduzia.
>
> Fica a lição para as próximas etapas: o número da auditoria é estimativa a
> reconferir, não especificação. Cinco vezes ele não bateu.

### Etapa 4 — Backend de aderência
- [ ] `P-01` selectors em eventos, termos, OS, PT + gate anti-ORM-em-view
  - [x] **eventos** — `eventos/selectors.py` com 13 consultas; as duas escritas que
    moravam na view (termo automático, anexo de solicitação) desceram para
    `services.py`. Catraca nova `--max-orm-em-view` no CI: **61 → 46**. As quatro
    telas do app tiveram a contagem de queries fixada em teste antes de mexer.
    **NOVO — divergência da auditoria:** o inventário vivo contou `.objects` em
    `views.py` como **eventos 15** (auditoria: 17), **termos 6** (7),
    **ordens_servico 3** (7) e **planos_trabalho 5** (5). A auditoria também não
    listou `integracoes/google_drive` (10) nem `core` (9), que são hoje o maior
    bolo restante e estão fora do escopo do `P-01`.
  - [x] **termos** — `termos/selectors.py` com 5 consultas; `_termo_queryset()` e os
    13 `get_object_or_404` da view saíram. Catraca: **46 → 40**. Lista, lista com
    busca e formulário de edição com contagem de queries fixada em teste.
  - [x] **ordens_servico** — `ordens_servico/selectors.py` com 3 consultas; catraca
    **40 → 37**. Lista, lista com busca e formulário de edição fixados em teste.
  - [ ] planos_trabalho (5)
- [ ] `P-02` `core/catalog.py` e migração dos 13 catálogos
- [x] `P-04` **widget base com classes canônicas** (pré-requisito das Etapas 6 e 7) —
  19 contratos CSS centralizados em `core/forms/widgets.py`; 194 `attrs` migrados
  sem alterar o HTML renderizado de Ofícios, Prestações, Plano de Trabalho,
  Roteiros e Eventos.
- [ ] `P-05` `core/errors.py` + varredura dos 57 `except` do Drive
- [ ] `P-06` fatiar `planos_trabalho/views.py` e `oficios/views.py`
- [ ] `P-07` `__str__` nos 3 models de `core`
- [ ] `S-06` documentos assíncronos via Celery

### Etapa 5 — Motores JS
- [x] `J-06` apagados os 9 arquivos órfãos do Anexo A (989 linhas) e as 6
  emissões remanescentes de hooks sem consumidor. O catálogo dizia 8 arquivos,
  mas enumerava 9; os demais hooks da estimativa original já não eram emitidos.
- [ ] `J-02` `CV.registry.destroy(root)` e limpeza do `action-menu`
- [ ] `J-01` registrar 8 componentes como enhancer
- [ ] `J-04` Quick Add/Quick Edit como enhancer
- [ ] `J-03` um motor de filtro por lista (`data-collection-mode`)
- [x] `J-07` migrados todos os consumidores para `CV.http`; `fetch()` e
  `X-CSRFToken` agora só existem no núcleo `static/js/core/http.js`, com gate
  bloqueante no auditor de CI. **NOVO — divergência da auditoria histórica:**
  o inventário vivo encontrou 16 consumidores de `fetch()` (não 13) e 7
  arquivos com `X-CSRFToken` (não 11); todos foram migrados.
- [x] `J-16` criado `CV.util` como dono único de `debounce`, `escapeHtml` e
  normalização textual, com gate bloqueante no auditor de CI. **NOVO —
  divergência da auditoria histórica:** o inventário vivo encontrou 5
  debounces, 2 escapes HTML e 7 normalizações (14 cópias, não 17); todas foram
  removidas. A assinatura pública, que não carrega o núcleo global, passou a
  coalescer o redimensionamento com `requestAnimationFrame`.
- [x] `J-12` criado `CV.feedback` e removidos todos os `alert()`/`confirm()`
  nativos, com gate bloqueante no auditor de CI. **NOVO — divergência da
  auditoria histórica:** o inventário vivo encontrou 12 chamadas (não 13);
  todas foram migradas.
- [ ] `H-01` + `J-08` `CV.locationRows` — fim das 6 cópias de destinos
- [ ] `J-15` `CV.documentSource` · `CV.picker` · `CV.overlay`
- [ ] `J-09` colapsar 22 namespaces em `CV.*`
- [ ] `J-13` `ManifestStaticFilesStorage` no lugar dos 88 `?v=`

### Etapa 6 — Estrutura HTML
- [ ] `H-02` `components/page/flow_base.html` + migrar Prestações, Termos, OS, Eventos, Roteiro avulso
- [ ] `H-05` `components/form/card.html` + migrar 20+ páginas
- [ ] `H-03` `_docs_attach_kinds_attrs.html` — fim dos ordinais latinos
- [ ] `H-04` `form_block.html` com contexto explícito e `only`
- [ ] `D-41` contrato único de classe no `field.html`
- [ ] `H-08` semântica (`<nav>`, `<ul>`, `<table>`, `<footer>`)
- [ ] `H-06` / `H-10` `aria-controls` nos 29 `aria-expanded`; `for`/`id` nos 14 `<label>`

### Etapa 7 — Reconstrução do CSS
- [x] Fase 0: apagados os aliases mortos de tema `dark-dark`, `light-dark`,
  `dark-light` e `light-light`; os seletores canônicos `dark`/`light` foram
  preservados.
- [x] Fase 1: apagados os quatro arquivos confirmados sem referência
  (`app-page.css`, `buttons.css`, `buttons-functional.css`, `app-ui.css`) e os
  ramos mortos `.app-form-shell`/`.form-shell`. **NOVO — divergência do Anexo
  C:** preservados `style.css`, `filter-header.css`, `roteiros-list.css` e
  `eventos-list.css` por referências vivas; `documents.css` também foi mantido
  porque ainda estiliza `.document-card-body`, emitido pelo componente global.
- [x] Fase 2: corrigidos os tokens indefinidos (`D-01`, `D-03`, `D-06`,
  `D-20`, `D-21`). Divergência do inventário histórico: 11 dos 18 nomes já
  estavam definidos ou sem consumidores após correções anteriores; os 7 usos
  indefinidos restantes foram centralizados ou substituídos por tokens canônicos.
- [ ] Fase 3: CSS faltante dos componentes globais
- [ ] Fase 4: tirar `auth.css` e `oficios.css` do `@import` global
- [ ] Fase 5: consolidar escala (raio, sombra, motion, z-index, tipografia)
- [ ] Fase 6: `dark-redesign.css` → `03-theme-dark.css` (só tokens)
- [ ] Fase 7: `oficio-lc` → `cv-record-card` + `cv-fact-block`, `cv-person-row`, `cv-itinerary`
- [ ] Fase 9–12: unificar shells, migrar Roteiros/Termos, trazer login e assinatura ao bundle
- [ ] Fase 13: `cv-notice` (−4 sistemas de alerta) e `cv-metric` (−5 de métrica)
- [ ] Fase 14: gate de CI contra literal de cor e classe sem CSS
- [ ] `R-01` escala de breakpoints (35 → escala única)

### Etapa 8 — Higiene e polimento
- [ ] `G-01` 161 arquivos indevidos no git · `G-02` docs datados → `docs/historico/`
- [ ] `G-03` repositório fora do OneDrive · `N-12` `media/` de 191 MB
- [ ] `S-02` e-mail · `S-03` rate limit no login · `S-04` CSP · `S-05` `SECRET_KEY` default
- [ ] `R-02` sistema de ícones (208 linhas de if/elif, 17 órfãos)
- [ ] `N-11` microcopy: 4 variantes de "Voltar à lista"
- [ ] `P-08` decidir `diario_bordo` · motor de PDF canônico

---

## 7.1 Escopo novo, fora das oito etapas

Pedidos que não vieram das auditorias entram aqui, com posição decidida antes de
começarem. Escopo novo que se infiltra numa etapa em curso é como a Etapa 1
perde o prazo e a Etapa 2 perde a rede.

| Proposta | Estimativa | Situação |
|---|---:|---|
| [Arquitetura de configurações](PROPOSTA_CONFIGURACOES.md) — tela por seções declaradas, config por documento, preferências por usuário | 17–28 dias | **aguardando decisão** de posição na fila |

---

## 8. Os erros que matam este refactor

1. **Começar pelo CSS.** Discutido em §1. É a etapa 7, não a 1.
2. **Renomear e corrigir no mesmo PR.** Quando quebrar, não se sabe qual metade quebrou.
3. **Deixar os três agentes na mesma camada.** Conflito garantido, revisão impossível.
4. **Dar o repositório inteiro de contexto.** Dê a seção da auditoria. O agente que lê 900
   linhas para consertar um `border-radius` acerta menos, não mais.
5. **Afrouxar a catraca para o PR passar.** O número de avisos só desce.
6. **Refatorar Prestações antes da Etapa 2.** É o módulo com dinheiro, assinatura pública e
   cobertura 0,04. Ali, sem teste, o refactor é aposta.
