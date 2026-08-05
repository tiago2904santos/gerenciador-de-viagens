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

- [x] `NOVO-07` 🟠 **N+1 real na lista de Ordens de Serviço** — a lista caiu de
  **138 para 22 queries** por página (fixture com 25 OS, cada uma com 2 destinos,
  3 servidores e 1 ofício). Duas causas, não três: `_destinos_display_os` refazia
  `select_related`/`order_by` sobre o related manager e descartava o prefetch
  (1 query/card), e `_get_assinante_os()` relia o singleton e as assinaturas por
  card (**5** queries/card, não 2). O teto de `test_list_performance.py` desceu de
  140 para 30. **NOVO — divergência da auditoria:** `servidores.count()` **não**
  custava query. `QuerySet.count()` devolve `len(self._result_cache)` quando o
  prefetch já preencheu o cache; o canário confirmou — trocar `len` de volta por
  `.count()` não muda a contagem. Ficou o `len` mesmo assim, porque não depende
  do prefetch existir. Falta a mesma doença em Termos (54 queries/página,
  `termo_cadastro_assinado_info` consulta por linha).
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
- [x] `D-02` (backend) — 6 testes de contrato de `organizer.py` com double de
  Drive com estado: operações idempotentes, árvore/arquivo existente, ausência
  de arquivo, resposta parcial, falha transitória com retry, atalhos/IDs
  persistidos e prevenção de pasta órfã.
- [x] `NOVO-16` — o contrato de pasta órfã criava evento sem `titulo`, entrada
  que deve ser *no-op* até a Etapa 1 ficar completa; a fixture passou a cumprir
  o portão real (`titulo` + data + destino), restaurando a suíte verde.

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
- [x] `P-01` selectors em eventos, termos, OS, PT + gate anti-ORM-em-view — **catraca 61 → 32**
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
  - [x] **planos_trabalho** — `planos_trabalho/selectors.py` com 7 consultas; as duas
    validações de vínculo do autosave de efetivo viraram selectors de existência
    (`cargo_pertence_a_area`/`unidade_pertence_a_area`), não service: são consulta, e
    com recorte por área. `catalog_views.py` (13 consultas) fica de fora de propósito —
    é território do `P-02`, que apaga o arquivo. Catraca: **37 → 32**.
- [x] **`NOVO-13` 🔴 lista de Plano de Trabalho quebrava com plano multi-evento** —
  `prefetch_related("eventos__destino_cidade__estado")` apontava para um campo que
  `EventoPlano` não tem. O Django só valida o segundo nível quando o primeiro traz
  linha, então a página abria enquanto nenhum plano tivesse evento e devolvia 500
  assim que um tivesse. Nenhuma auditoria viu; a suíte não pegava porque nenhum
  teste da lista criava `EventoPlano`. Encontrado ao engrossar o fixture do teste
  de orçamento de queries do `P-01` — o canário do prefetch não disparava, e o
  motivo era que a relação estava vazia.
- [x] `P-02` `core/catalog.py` e migração dos catálogos
  - [x] **motor + `planos_trabalho`** — `core/catalog.py` com `CatalogConfig`; os
    quatro catálogos do PT viraram declarações e `catalog_views.py` (430 linhas)
    foi apagado. 19 testes de caracterização escritos **antes**, contra o código
    antigo, passaram sem alteração contra a fábrica.
    **NOVO — divergências da auditoria:** são **11** catálogos com o padrão
    completo, não 13 (`cadastros/views.py:cidades_index` é lista + export, sem
    CRUD), e **1.008** linhas duplicadas, não ~1.500. E a conta de linhas deste
    PR **sobe**, não desce: −430 do arquivo apagado contra +686 (motor 317,
    declarações 210, presenters 97, selectors 62). O motor se paga a partir do
    segundo app; prometer economia já no primeiro seria falso.
    **`NOVO-14`:** o presenter de presets faz `atividades.order_by(...)` por
    linha e descarta o `prefetch_related` — mesma doença do `NOVO-07`.
    Preservado como estava, porque o `P-02` move e não otimiza.
  - [x] **oficios, eventos, justificativas** — os tres catalogos viraram
    `CatalogConfig`; `oficios/catalog_views.py` (105 linhas) apagado e os blocos
    saem de `eventos/views.py` e `justificativas/views.py`. 16 testes de
    caracterizacao escritos antes, verdes contra a fabrica. A fabrica ganhou
    `contexto_extra` (rotulo de volta condicional) e tres flags para os presenters
    que montam o `set_default_url` por dentro. **NOVO:** a normalizacao do
    `quick_add_next_url` quando `next == fallback` (entrada que a UI nunca produz)
    e a unica diferenca observavel, documentada no teste.
  - [x] **cadastros** — Estados, Unidades, Cargos e Combustíveis viraram quatro
    declarações em `cadastros/catalogs.py`; 11 testes de caracterização foram
    escritos **antes** e passaram contra as duas implementações. A fábrica
    ganhou apenas as variações que já existiam: paginação, `?next=` opcional,
    URLs granulares com retorno, confirmação por GET e erro de vínculo.
    `cadastros/views.py` perdeu 349 linhas. Cidade ficou fora com prova: é lista
    + criação + exportação, sem editar/excluir, portanto não é o CRUD completo
    que `CatalogConfig` representa.
- [x] `P-04` **widget base com classes canônicas** (pré-requisito das Etapas 6 e 7) —
  19 contratos CSS centralizados em `core/forms/widgets.py`; 194 `attrs` migrados
  sem alterar o HTML renderizado de Ofícios, Prestações, Plano de Trabalho,
  Roteiros e Eventos.
- [x] `P-05` `core/errors.py` + varredura dos handlers genéricos do Drive —
  inventário vivo corrigido de 57 para 64; todos chamam captura estruturada
  como primeira instrução e o CI bloqueia regressões por análise da AST.
- [x] `P-06` fatiar `planos_trabalho/views.py` e `oficios/views.py` — fachadas
  reduzidas a 43/38 linhas, 12 módulos por tela abaixo de 500 linhas, imports
  públicos preservados e catraca P-01 adaptada sem esconder as 32 ocorrências.
- [x] `P-07` `__str__` em `core` — o inventário histórico contou 3 classes,
  mas `TimeStampedModel` e `CancelavelModel` são abstratas; só `AuditEvent` é
  model concreto. Sua representação agora identifica ação, model, ID e objeto,
  coberta por teste antes da mudança.
- [x] `S-06` documentos assíncronos via Celery — Ofícios, Justificativas,
  Ordens de Serviço, Planos, Termos e Prestações usam job persistido, polling,
  download protegido por área, deduplicação e retenção de 24 h; a catraca de
  arquitetura mantém geração pesada fora das views.

### Etapa 5 — Motores JS
- [x] `J-06` apagados os 9 arquivos órfãos do Anexo A (989 linhas) e as 6
  emissões remanescentes de hooks sem consumidor. O catálogo dizia 8 arquivos,
  mas enumerava 9; os demais hooks da estimativa original já não eram emitidos.
- [x] `J-02` `CV.registry.destroy(root)` limpa componentes antes de swaps e
  também ao observar nós removidos; o `action-menu` registra a origem do menu
  portado ao `<body>` e o devolve ao dono no `destroy`, eliminando órfãos e IDs
  duplicados.
- [x] `J-01` os 8 componentes sensíveis a swap (`fields`, `masks`,
  `stateToggle`, `cardToggle`, `dropdowns`, `documentNumberField`,
  `locationRows`, `autosave`) registram inicializadores idempotentes no
  `CV.registry`.
- [x] `J-04` Quick Add/Quick Edit agora pertencem a `CV.inlineCreate`, com
  delegação/guards idempotentes; autosave encontra também formulários inseridos
  por AJAX.
- [x] `J-03` `CV.collection` é o dono único de filtros de lista, com modo
  explícito `client|server`; os dois motores antigos e seus hooks foram
  removidos, e as listas paginadas usam somente o modo servidor.
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
- [x] `H-01` + `J-08` `CV.locationRows` é o motor único de linhas de destino:
  os seis consumidores usam `data-location-*`, a cascata consulta por
  `estado.pk`, 1.158 linhas e seis partials de Eventos foram
  removidos; a fronteira legada de Eventos converte pk para sigla/nome somente
  ao serializar seu modelo.
- [x] `J-15` `CV.documentSource` é o motor único de prefill para Termos, OS e
  Diário-motorista; os três consumidores usam JSON seguro e o contrato
  `data-source-document`.
- [x] `CV.picker` é o único namespace e enhancer de seleção; os renderers de
  busca e select usam `data-entity-picker`, sem aliases/motores concorrentes.
- [x] `CV.overlay` concentra diálogos, menus e dropdowns portaled em um único
  enhancer; remove os cinco motores legados e padroniza os gatilhos vivos em
  `data-overlay-*`.
- [x] `J-09` somente `window.CV` é publicado; aliases duplicados, fallbacks
  órfãos e os namespaces de tema/autosave/roteiros foram consolidados.
- [x] `J-13` storage com manifesto, compressão e reescrita de imports ESM;
  150 tokens manuais removidos e `collectstatic` validado na CI.
- [x] **`NOVO-17` 🟠 `whitenoise` prod-only quebrava a suíte fora do CI** —
  achado na conferência das Etapas 1–5. `config/staticfiles.py` importa
  `whitenoise.storage` e é importado por `core/tests/test_static_asset_versioning.py`,
  que roda em toda execução; a dependência estava só em `prod.txt`, então
  qualquer ambiente que instala `dev.txt` (inclusive o hook de sessão do próprio
  projeto) coletava a suíte com `ModuleNotFoundError: No module named 'whitenoise'`
  — **1.229 testes, zero rodando**. O CI passava porque instala `lock.txt`,
  compilado de `prod.txt`. `whitenoise` passou para `base.txt` e o contrato ficou
  guardado por teste. Lição registrada: gate verde no CI não é prova de suíte
  verde, quando CI e dev instalam arquivos de requirements diferentes.
- [x] `J-10` autosave usa um único par de listeners globais e destrói
  listeners de formulário, timers e requests quando o nó sai do DOM.
- [x] `J-19` `CV.log` centraliza debug/warn/error e emite `cv:log`; chamadas
  diretas a `console.*` ficaram proibidas por teste estrutural.

### Etapa 6 — Estrutura HTML
- [x] `H-02` `components/page/flow_base.html` — Prestações, Termos, OS,
  Eventos (detalhe + form) e Roteiro avulso migrados. O casco tem parâmetro e
  bloco porque as páginas variam em **12 eixos** medidos: só as duas linhas do
  meio (`main-form-panel` e `cv-form-section-stack`) eram literalmente iguais.
- [x] `H-05` `components/form/card.html` — em uso nas páginas de fluxo e nos
  ~23 arquivos que ainda escreviam `cv-form-section-header` à mão (Ofícios,
  Planos, cadastros, perfil, drafts, signature, preview).
  - **Lição registrada:** o componente inclui o corpo **sem `only`** por
    necessidade (é portador de contexto, como o `form_block`), e por isso precisa
    **zerar os próprios parâmetros** antes de descer — senão o `body_extra_class`
    do card mestre reaparece em todos os blocos internos. Só apareceu no diff de
    HTML renderizado; nenhum teste pegaria, porque o defeito é uma classe a mais.
  - **Lição de método:** a primeira comparação antes/depois foi **vazia** — o
    `git stash` não achou nada para guardar (tudo já commitado) e as duas
    renderizações usaram o mesmo código. O jeito correto é `git worktree` no
    commit anterior. Comparação que dá zero merece desconfiança, não alívio.
- [x] `H-03` fim dos ordinais latinos — **a auditoria catalogava só
  `_docs_attach_kinds_attrs.html`, e havia um segundo consumidor**: 17 atributos
  ordinais inline em `_prestacao_card_body.html`, onde o `primary` era o
  *relatório técnico* enquanto o `primary` da etapa Documentos era o *despacho* —
  mesmo modal, mesmo nome, documento diferente. O número de documentos era
  constante em três lugares (os 30 atributos do gatilho, a lista `KINDS` do JS e
  os 5 botões escritos à mão no modal). Agora `kinds_de_anexo_assinado` em
  `presenters.py` é o dono do formato, os tipos viajam num payload JSON com chave
  semântica (`despacho`, `oficio`, `rt`, `diario`, `comprovante`) e o JS monta os
  botões. `_docs_attach_kinds_attrs.html` (37 linhas) apagado; `KINDS` e
  `kindPrefix` mortos. Os gatilhos de tipo único (menu do entity card) seguem com
  atributos planos — ali o botão *é* o documento e nunca houve ordinal.
  - **`NOVO-18` 🟠 comentário `{# #}` multilinha vazava para o HTML** — achado com
    Playwright ao conferir este item na tela. `{# #}` é comentário de **uma
    linha**; aberto numa linha e fechado em outra, o Django devolve o texto
    verbatim. Havia um caso **vivo em produção**:
    `templates/oficios/wizard_transporte.html:67`, 6 linhas de comentário
    aparecendo como texto na etapa Transporte do wizard — introduzido pelo PR #119
    e invisível para a suíte, porque nenhum teste lia o HTML daquela região.
    Dentro de uma tag é pior: o navegador vira cada palavra num atributo
    inventado. Os 4 casos do repositório passaram a `{% comment %}`; gate novo
    como **erro** (não catraca) e teste que também mede a premissa do Django.
    Lição: conferência de tela acha o que grep de template e suíte não acham.
- [x] `H-04` `form_block.html` — parâmetros do bloco zerados antes de incluir
  body/actions/footer (mesmo padrão do `card.html`); evita vazamento de
  `body_extra_class`/`title` para blocos aninhados. Presenter com `only` total
  fica como evolução opcional — o vazamento medido está fechado.
- [x] `D-41` contrato único de classe no `field.html` — em vez de só igualar as
  strings, container e rótulo passaram a ser escritos **uma vez** e o que varia
  por tipo saiu para `_field_control.html`; o componente foi de 74 para 51 linhas
  e de 3 contratos para 1. **Divergência da previsão:** eu previa diff visual no
  tema escuro; medindo com `getComputedStyle`, no escuro o valor resolvido é
  idêntico antes e depois — o diff real está no **tema claro** (rótulo de texto
  vai de `rgb(51,76,99)`/700 para `rgb(7,26,51)`/600, igualando o rótulo de
  select que já estava ao lado, no mesmo painel). Achado latente corrigido junto:
  o ramo de `select` lia `widget.attrs.class` sem `|default:""`, e sem classe o
  `{% if %}` engolia o `VariableDoesNotExist` e o `<select>` perdia o rótulo
  inteiro em silêncio — não alcançável hoje, mas passaria a ser. Verificação:
  21 páginas renderizadas antes/depois com diff normalizado, **zero mudanças
  inesperadas**.
- [x] `H-08` semântica — **o item estava em grande parte obsoleto quando o abri**:
  `page_stepper.html:2`, `list_tabs.html:6` e `pagination.html:18` já eram
  `<nav>`, e `card_footer_actions.html:1` já era `<footer>`. A parte de rodapé
  que a auditoria pede seria **regressão**: os ~30 `<div class="cv-form-card__footer">`
  são wrapper de layout POR FORA daquele `<footer>`, e trocá-los produziria
  `<footer>` dentro de `<footer>` (inválido por spec) além de quebrar
  `oficios/tests/test_views.py:245`, que faz `html.index('<section class="cv-card-footer-section">')`.
  Registrado por escrito para ninguém "corrigir" isso depois.
  Feito de fato: as 7 listas de servidores e 6 de trechos viraram `<ul>`/`<li>`
  em 6 partials de card. Duas coisas que a auditoria não previa: o `{% empty %}`
  emitia `<p>` como filho direto (inválido em `<ul>`) e **não existia reset de
  lista** — sem `list-style: none` e `padding-inline-start: 0`, o user agent
  empurra todo o conteúdo do card 40px para a direita (conferido em print; os
  bullets não aparecem porque `display: grid` blockifica os `<li>`, então minha
  previsão do plano acertou o recuo e errou o marcador).
  `cv-card-grid` ficou **fora**, de propósito: envolver os `<article>` em `<li>`
  quebraria em silêncio `.cv-card-grid > .prestacao-card-group--*`
  (`prestacoes_contas.css:717-748`). Vai na Etapa 7 fase 7, que reescreve esse
  markup.
- [x] `H-06` / `H-10` `aria-controls` nos gatilhos com `aria-expanded`
  (componentes globais + card bodies); `for`/`id` nos 6 labels reais de
  `_diario_trecho_body.html` (o inventário de 14 da auditoria estava parcialmente
  obsoleto — vários já eram label wrapping).

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
- [x] Fase 3: CSS faltante dos componentes globais
- [x] Fase 4: tirar `auth.css` e `oficios.css` do `@import` global
- [x] Fase 5: consolidar escala (raio, sombra, motion, z-index, tipografia)
- [x] Fase 6: `dark-redesign.css` → `03-theme-dark.css` (só tokens) +
  `components/theme-dark-components.css` (overrides transitórios; dissolver nas fases seguintes)
- [x] Fase 7: `oficio-lc` → `cv-record-card` + `cv-fact-block`, `cv-person-row`, `cv-itinerary`
- [x] Fase 9–12: unificar shells (`cv-page--*`), migrar Termos/Roteiros para
  `list_page_cards`, card canônico no `_roteiro_editor`, login e assinatura
  pública em tokens/`data-theme`. **Deferido (Fase 9):** aliases legados
  `travel-document-wizard`, `app-wizard`, `document-form-page`, `os-page` e
  `evento-guided-page` mantidos — ainda referenciados em `oficios.css`,
  `theme-dark-components.css` e JS; remoção na fase de limpeza pós-shell.
- [x] Fase 13: `cv-notice` (−4 sistemas de alerta) e `cv-metric` (−5 de métrica)
- [x] Fase 14: gate de CI contra literal de cor e classe sem CSS
  (`core/tests/test_css_tokens.py` — hex/rgb fora de tokens + classes canônicas
  em templates críticos)
- [x] `R-01` escala de breakpoints (34 valores únicos → 17 na escala fechada;
  tokens documentados em `tokens.css`; gate em `test_css_tokens.py`)

> **Etapa 7 concluída (30/07/2026).** Reconstrução do CSS: aliases mortos removidos,
> tokens indefinidos corrigidos, componentes globais (`cv-notice`, `cv-metric`,
> `cv-record-card`), tema escuro separado, shells unificados e escala de breakpoints
> fechada. Próximo: Etapa 8 — higiene e polimento.

### Etapa 8 — Higiene e polimento
- [x] `NOVO-12` 🟠 **Shell sem bundle** — `base.html` carregava 24 CSS + 25 JS por
  página. Entrega agora é `static/css/shell.bundle.css` + `static/js/shell.bundle.js`
  (fontes intactas; gerador `scripts/build_shell_bundles.py` com `--check`;
  `theme-shared.js`/`theme-init.js` permanecem no `<head>` sem defer). Hook de
  build antes do `collectstatic` nos scripts de deploy. Gate em
  `core/tests/test_shell_bundles.py`.
- [ ] `G-01` 161 arquivos indevidos no git · `G-02` docs datados → `docs/historico/`
- [ ] `G-03` repositório fora do OneDrive · `N-12` `media/` de 191 MB
  *(ação de ambiente: mover o clone para fora do OneDrive ou marcar `.venv/`,
  `staticfiles/`, `media/`, `tmp/`, `legacy/` como "sempre local" — sem isso o
  local continua lento mesmo com o bundle)*
- [ ] `S-02` e-mail · `S-03` rate limit no login · `S-04` CSP · `S-05` `SECRET_KEY` default
- [ ] `R-02` sistema de ícones (208 linhas de if/elif, 17 órfãos)
- [ ] `N-11` microcopy: 4 variantes de "Voltar à lista"
- [ ] `P-08` decidir `diario_bordo` · motor de PDF canônico
- [x] `NOVO-20` 🟠 **Header de wizard alinhado às listas** — `wizard_page_header`
  (`.list-header--wizard` + stepper no rail + sticky `is-detached`).
  Substitui o `page-header-stack` horizontal dos wizards.

### Regressões da remodelagem visual (04/08/2026)

A reescrita visual de Administração, Termos e Usuários entrou direto no `main`, sem
PR e sem atualizar teste no mesmo commit. Resultado medido em 04/08: **13 testes
vermelhos e o CI reprovando desde 31/07** (último verde às 15:32 daquele dia).
Quatro eram defeito de código, oito eram asserção envelhecida e uma era teste frágil.
A separação importa: só as quatro primeiras mudavam o comportamento do sistema.

- [x] `NOVO-25` 🟠 **`?v=` manual voltou em 12 templates** — `base.html`,
  `usuarios/index.html`, `usuarios/areas/*`, `eventos/detalhe.html`,
  `planos_trabalho/wizard_*`, entre outros, mais um `@import` em `style.css`.
  Desfazia o `J-13`: com a `VersionedStaticFilesStorage` o nome já sai com hash,
  então o parâmetro só quebrava o cache de longo prazo sem ganho nenhum.
- [x] `NOVO-26` 🟠 **N+1 em Termos, o que faltava do `NOVO-07`** —
  `termo_cadastro_assinado_info` consultava `DocumentoArtefato` uma vez por
  servidor na tela de edição. Novo selector `mapa_artefatos_pdf_termo_cadastro`
  resolve o termo inteiro numa query. Medido com 3 servidores: **4 → 1**
  consulta à tabela; e o total parou de crescer com a equipe (9 servidores não
  custam mais que 3). O orçamento da tela vai de 21 para 28 — os 7 restantes
  são o `NOVO-27`, que é constante.
- [x] **Catraca de ORM 36 → 30** — o rótulo da sede das Configurações voltou
  copiado **byte a byte** nas views de Eventos, Termos e Ordens de Serviço
  (mesmo md5 nas três). Centralizado em `cadastros.selectors.rotulo_da_sede_configurada`.
  Junto, dois breakpoints fora da escala fechada do `R-01`
  (`planos-trabalho-eventos.css`: 700px → 720px, 620px → 640px; ambos sobem, que
  é a direção que não abre janela de overflow).
- [x] **Chip de status sumido do wizard** — achado ao investigar a asserção
  vencida, e **não era asserção vencida**: `wizard_page_header.html` (o header do
  `NOVO-20`) deixou de emitir o chip, e `eventos/detalhe.html` **já passava**
  `status_label`/`status_variant` para ele. Ou seja, Eventos também estava sem
  status na tela, em silêncio. O parâmetro voltou, pelo mesmo componente que a
  band das listas usa — que era o objetivo declarado do `NOVO-20`.
- [x] **Teste frágil por data** — `test_eventos_index_filtra_area_do_usuario`
  criava evento em 01/08 fixo. Quando o calendário passou de 04/08 o evento caiu
  na aba "anteriores" e o teste acusou **vazamento de área** onde só havia data
  vencida. Ancorado em `localdate() + 7 dias`.

> **Pendência aberta:** `NOVO-27` 🟡 — `ConfiguracaoSistema.get_singleton()` é
> relido várias vezes por request (4× em Ordens de Serviço, mais 4× `AreaTrabalho`),
> e `resolver_sede_ids_desde_configuracao` busca a `Cidade` com `select_related`,
> descarta o objeto e devolve só os IDs, obrigando quem chama a consultar a mesma
> linha de novo. Custo constante, não escala com dados — por isso ficou fora deste
> PR, mas é a explicação dos +7/+4 nos orçamentos de query.

### Paleta de tres cores (04/08/2026) — `NOVO-28`

Decisao de produto tomada num laboratorio de paleta interativo, com as cores medidas
antes de escolhidas. O sistema passa a se pintar com **tres superficies que se revezam**
mais um acento; botoes cheios e estados semanticos sao as unicas excecoes, e estao
declaradas no gate.

| | claro | escuro |
|---|---|---|
| fundo do site | `#eceef1` | `#0d0f11` |
| `cv-form-section-card` | `#ffffff` | `#191c1f` |
| `cv-form-block` | `#eceef1` (= fundo) | `#23272b` |
| acento | `#155b9a` | `#d8a21b` |

A regra: **um componente nunca escolhe a propria cor** — recebe `--cv-surface-next` de
quem o contem. Campo dentro de bloco fica com a cor do card; o mesmo campo dentro do card
fica com a do bloco. Detalhe, hover de lista e foco usam `color-mix` do acento a 15% sobre
`--cv-surface`, que e herdada — a cor de fundo nao se repete em declaracao nenhuma.

- [x] **PR A** — camada de sementes (`static/css/00-palette.css`), rodizio nos dois
  ancoras, reaponte de 22 tokens de superficie do shell, 48 do `--step1-*` e 35 fundos de
  controle, fim das bordas de foco, login e assinatura publica. Catraca de literais
  **660 -> 620**; `auth.css` deixou de ser excecao nos dois auditores (zero literal).
- [x] **PR A2** (`NOVO-29`) — **o login virou o modelo padrao**, por decisao de produto.
  Geometria: raio do card 16 -> **28px**, sombra `sm` -> **`strong`**, campo 12 -> **14px**
  e 44 -> **48px** de altura. E o acento virou **pontual**: a faixa cheia do cabecalho
  (`list-header__band`, que usava o gradiente `--app-hero-stage-bg`) passou a superficie
  de card, com titulo em tinta normal e eyebrow no acento — exatamente onde o acento
  aparece no login. Mais 7 superficies do rail de filtros e do quick-create entraram na
  paleta. Avisos de frontend 387 -> **384**.
- [ ] **PR B** — dissolver `components/theme-dark-components.css` (5.843 linhas, 665
  regras com `:is(...)`/`[data-*]`). **E o que impede o tema escuro de obedecer a paleta:**
  medido com `scripts/medir_paleta.py`, o claro ficou com o nucleo na paleta e o escuro
  com 18 cores fora so no Dashboard.
- [ ] **PR C** — as 318 regras de `hover`/`focus` que ainda mexem em borda.
- [ ] **PR D** — os ~620 literais restantes fora dos arquivos de token.

> **Duas licoes do PR A.** A primeira: `--cv-surface-next` **nao pode** ser intermediado por
> um token declarado no `:root`. Propriedade customizada e substituida no elemento onde e
> declarada, entao `--color-input-bg: var(--cv-surface-next)` no `:root` congelaria o valor
> da raiz e o rodizio morreria em silencio — os 35 fundos de controle foram trocados no
> **ponto de uso**. A segunda: a ordem de carga importa e nao aparece no tema claro. A
> paleta precisa vir **depois** de `01-tokens.css`, porque os dois declaram no mesmo
> seletor `html[data-theme="dark"]`; antes dele, o acento novo e ignorado so no escuro.

### Reescrita completa do CSS — `NOVO-30`

> **Refazer (04/08/2026):** as fases 1–4 mergeadas nos PRs #156–#159 foram revertidas
> para refazer do zero, uma fase por PR, com a coordenação visual institucional
> (card → bloco → campo; claro espelho do escuro).

- [x] **Fase 1 — camada unica de tokens (refazer):** `tokens.css`, `theme.css` e
  `03-theme-dark.css` consolidados em `01-tokens.css` (27 tokens canônicos +
  aliases temporários remapeados para a paleta institucional). Declaracoes `--*`
  fora de `00-palette.css` / `01-tokens.css`: **0**. Coordenacao visual: superfícies
  e tinta dos aliases espelham card → bloco → campo das imagens de referencia.
- [x] **Fase 2 — regra do espelho (refazer):** `data-theme` eliminado dos componentes; `theme-dark-components.css` dissolvido em `app-shell.css` (regras theme-agnostic + tokens). Gate estrutural: **1.098 -> 0**. Coordenacao visual institucional nos dois temas.

- [x] **`NOVO-31` 🔴 a fase 1 mediu o lado errado — e por isso "27 tokens" eram 1.034.**
  Medido em 04/08 ao abrir a fase 3: `01-tokens.css` tinha **1.034 nomes distintos
  em 2.078 declaracoes**, 88 blocos de regra de componente, **duas copias literais**
  do mesmo bloco (`.sidebar-theme` / `.app-theme-grid`) e linhas de **11.959
  caracteres** — o mesmo artefato que o `AGENTS.md` §6 descreve como reprovado.
  O gate da fase 1 contava token declarado **fora** da camada e dava zero; nunca
  olhou para dentro. E o regex era ancorado em inicio de linha, entao um `:root`
  minificado de 3.902 caracteres contava como **um** token. A fase 2 entao empurrou
  para la os blocos `data-theme` que precisava tirar dos componentes, e o gate dela
  (1.098 → 0) tambem passou. **Licao:** quando o alvo e um numero do artefato, o gate
  tem de contar o artefato inteiro — nao a borda dele.

- Pela dimensao medida (8.287 referencias `var()`, 761 aliases vivos, 3.622
  declaracoes de geometria), a fase 3 foi **fatiada em tres PRs** antes de comecar
  (`AGENTS.md` §6):
  - [x] **Fase 3a — a camada de token de verdade.** 1.034 → **57** tokens (teto 60);
    `01-tokens.css` de 1.639 → **125** linhas, um `:root` e um `html[data-theme]`,
    zero regra de componente, zero linha acima de 200 caracteres. As 7.775
    referencias repontadas para o vocabulario canonico, com decisao de **papel** por
    familia — nao por proximidade de valor. Eixos que a fase 1 esqueceu (tipografia,
    altura de controle, movimento, camada) entraram como token canonico; o resto
    saiu por `color-mix()` no ponto de uso. **A sidebar entrou na paleta** (decisao
    de produto, 04/08): superficie de card, tinta normal, icone e ativo no acento.
    Catraca de frontend **335 → 212**; excecoes de arquivo **3 → 2**. Cores fora da
    paleta medidas em 10 telas: **60 → 16** (as 16 restantes sao as derivacoes
    declaradas do `NOVO-28` — hover e detalhe em `color-mix` do acento).
    Suite **1.308 → 1.314** verdes (6 gates novos).
    - **Tres defeitos que a suite verde nao pegaria**, achados na tela e no diff:
      as tres ancoras do rodizio (`.cv-form-section-card`, `.cv-form-block`,
      `.cv-form-block .cv-form-block`) moravam na camada de token e teriam sumido —
      voltaram para `components/form-sections.css`, que e onde o proprio
      `00-palette.css` diz que elas vivem; um token que guardava
      `12px 16px 12px 32px` casou com a regex de sombra e virou
      `padding: var(--sh-lg)` no cabecalho do card; e `--cv-chip-border-width: 1px`
      arredondou para o primeiro degrau da escada de espaco, **engrossando a borda
      do chip em quatro vezes**. Dai os gates novos de *familia* e de *escada*.
    - **Um defeito de tela pura:** `.sidebar-account__name` era `#ffffff` literal.
      Com a sidebar clara, o nome do usuario ficou branco no branco. Nenhum teste
      pega isso; o print pegou.
  - [x] **Fase 3b — geometria: raio, espaco e borda.** As quatro escadas fechadas:
    raio **53 → 6** · padding **214 → 8** · margem **50 → 3** · borda **58 → 3**.
    - **A regra que organizou a fatia:** a forma curta ficou reservada para valor da
      escada; **assimetria foi para a forma logica** (`padding-block`/`padding-inline`,
      `margin-block`, `border-color`/`border-style`/`border-width`,
      `border-start-start-radius`). Sem isso nao fecha: so as 450 paddings
      assimetricas ja estouram qualquer teto de string. E como o gate entregue mede
      **as duas formas**, o valor nao tem para onde se esconder — o canario prova
      (`padding-inline: 13px` e `border-radius: 7px` reprovam os dois testes).
    - **Piso e teto da escada, de novo.** `1px`/`2px` de borda continuam literais
      (traco, nao espaco) e `max-width: 960px` continua literal (layout). O que a
      escada cobre e o meio.
    - **`!important` sai antes de contar.** Ele e alvo declarado da fase 4; se
      contasse, `border-radius: 0 !important` seria uma string a mais e a 3b teria de
      resolver `!important` junto — o erro nº 2 da §8.
    - **`NOVO-32` 🟡 borda que nunca foi pintada.** `.prestacao-file-picker` declarava
      `border: var(--cv-border)` — forma curta so com cor, entao o estilo vale `none`
      e o navegador nao pinta nada. Preservei o comportamento (`border: 0`) com o
      motivo escrito no arquivo: restaurar a borda e decisao de produto, nao
      arredondamento de geometria.
    - Suite **1.314 → 1.316** verdes (dois gates novos). Catraca de frontend segue em
      **212** e as excecoes em **2** — a 3b nao mexe em literal de cor.
  - [x] **Fase 3c — sombra minima e fim do foco.** O alvo do prompt (≤ 4 sombras, anel
    de foco migrando para `outline`) foi **substituido por duas decisoes de produto**
    de 04/08:
    - **Uma sombra so, minima.** `box-shadow` 129 → **2** valores (`var(--sh-sm)`,
      `none`). O degrau encolheu de `0 2px 8px` a 10% para `0 1px 2px` a 8%;
      `--sh-md` e `--sh-lg` sairam da camada. O que se destaca do fundo passa a se
      destacar pela superficie da paleta e pela borda.
    - **O sistema nao sinaliza foco.** Nem anel, nem halo, nem contorno: `outline`
      ficou com **um** valor (`none`), as 109 sombras de foco sairam e `--focus-ring`
      deixou de existir. Vocabulario 57 → **54** tokens.
      **REGRESSAO CONSCIENTE:** e falha de WCAG 2.4.7 (Focus Visible) — quem navega
      por teclado perde a unica pista de onde esta. Levantei antes de executar, a
      decisao foi reafirmada, e esta registrada aqui e em `static/css/base.css` para
      ninguem descobrir por acidente. Se voltar, volta pelo reset global, num lugar so.
    - **A faixa de acento virou borda.** Os 21 `inset 4px 0 0 var(--color-accent)`
      nunca foram sombra: eram uma faixa a esquerda desenhada com `inset`. Agora sao
      `border-inline-start`, que e o que sempre foram.
    - **`NOVO-33` 🟠 nove focos invalidos herdados da 3a** — a substituicao daquela
      fase emitiu a *forma* do halo dentro de declaracoes que ja tinham forma
      (`outline: 2px solid 2px solid var(--focus-ring)`,
      `box-shadow: 0 0 0 2px 0 0 0 3px var(--focus-ring)`). O navegador descartava as
      nove, entao esses focos nao pintavam nada desde a 3a. Sumiram junto com o foco;
      quem achou foi a medicao de abertura da fatia seguinte, nao a suite.
    - Suite **1.316 → 1.320** verdes (4 gates novos, os dois principais com canario).
      Catraca de frontend **212 → 210**.
- [x] **Fase 4 — fim das excecoes e do `!important`.** `!important` **474 → 18**;
  excecoes de arquivo do auditor **3 → 0**; avisos **210 → 201**.
  - **O numero saiu de medicao, nao de estimativa.** `scripts/medir_estilos.py`
    (novo, versionado ao lado do `medir_paleta.py`) captura o `getComputedStyle` de
    **1.488 elementos** — 5 telas × 2 temas × 24 propriedades. Removi os 474, refiz a
    captura e comparei: os **456 cosmeticos mudaram ZERO propriedade computada**. Eles
    venciam adversarios que a fase 2 (theme-dark-components) e a 3a (os 1.034 tokens
    que se sobrescreviam) ja tinham dissolvido — ninguem tinha voltado para conferir.
  - **Os 18 que ficaram sao estruturais** (`display`, `opacity`, `content`): escondem
    ou mostram, e a medicao de 5 telas nao alcanca wizard, modal e editor. Apagar ali
    seria risco que o instrumento nao ve. Cada um carrega, agora, o comentario de uma
    linha dizendo **qual regra ele vence** — exigencia do prompt, travada por teste:
    sem justificativa escrita o gate reprova.
  - **A primeira remocao mostrou o que o `!important` escondia:** com os 474 fora, 118
    elementos do date-picker *apareceram* — `[hidden] { display: none !important }` em
    `base.css` e a unica coisa que faz o atributo `hidden` vencer o
    `.cv-date-picker__panel { display: grid }`. E o caso exemplar de `!important`
    legitimo, e so a captura de elementos (nao a de propriedades) mostrou.
  - **As excecoes eram tres, nao duas** — a terceira (`cards.css`) nao aparecia na
    contagem porque so conta excecao *disparada*. Todas mortas: `.roteiro-editor__*`
    mudou de `forms.css` para `roteiros.css`, `.oficio-card` ja nao existia em
    `cards.css`, e a camada de token deixou de ser dispensa para virar **parte da
    definicao da regra** de literal de cor — carrega-la como excecao era o auditor nao
    conhecer a propria arquitetura.
  - **`NOVO-34` 🟠 botao de upload sem letra no modal de anexo.** Com o `!important`
    fora, `test_papel_dos_tokens` acusou `#attach-signed-modal .cv-file-picker__upload`
    pintando fundo E texto com `--color-accent`. O `!important` estava **vencendo o par
    certo** declarado no componente: o defeito existia, escondido pela propria muleta.
  - Suite **1.320 → 1.323** verdes (3 gates novos).

  > **O que a fase 4 NAO baixa, e de quem e:** o prompt pedia `--max-warnings 0`. Dos
  > 201 avisos restantes, **109 sao `hex_color_outside_tokens`** (PR D do `NOVO-28`),
  > **92 sao `legacy_page_header`** e **10 `href_hash`** — os dois ultimos em template,
  > territorio das Etapas 6 e 8. Zerar dentro da fase 4 seria fazer o trabalho de tres
  > frentes no mesmo PR, que e o erro nº 2 da §8. A catraca desce no que esta fase
  > legitimamente remove; o resto tem dono nomeado aqui.
- [x] **`NOVO-39` 🟡 os 92 `legacy_page_header` eram defeito da regra, nao divida do
  template.** 05/08/2026. A regra era `class="[^"]*\bpage-header\b`, e `\b` trata o
  hifen como fronteira: ela casava `page-header-band`, `page-header-stack` e
  `page-header-rail` — a familia do **componente canonico**, cujo proprio cabecalho se
  declara "Cabecalho canonico de pagina". A classe crua `page-header`, alvo real da
  regra, aparece **zero** vezes. E a mensagem mandava migrar para **`app-page-hero`,
  que nao existe** no repositorio — nem em CSS, nem em template, nem em JS. Seguir o
  aviso teria renomeado **106 usos do componente vigente** para um componente
  inexistente.
  Corrigida a **regra**, nao o template. A regra irma no CSS tinha o mesmo defeito, com
  60 falsos positivos latentes (nao apareciam porque so roda em `GLOBAL_CSS`). A
  excecao de arquivo do dashboard caiu junto: sobrevivia ao defeito, nao a um uso —
  `TEMPLATE_EXCEPTIONS` fica vazio, como o `CSS_EXCEPTIONS` ficou na fase 4.
  Catraca **184 → 92**. `core/tests/test_auditor_page_header.py` trava os dois lados: a
  familia canonica nao pode ser acusada, **e** a classe crua tem de continuar sendo —
  senao a correcao vira afrouxamento. Um terceiro teste exige que o caminho citado na
  mensagem exista; aviso que aponta para lugar nenhum ensina a ignorar o auditor.
  Canario rodado.
- [x] **`NOVO-40` 🟡 a ancora vazia chegava por tres caminhos; a regra via um.**
  05/08/2026. `href="#"` nao e link: e link que **pula a pagina para o topo**. O
  `DESIGN_SYSTEM.md` ja proibia e o auditor tinha regra — que olhava so o literal
  escrito no template. Os outros dois caminhos:
  **(2) parametro de componente** — `secondary_url="#"`, `back_url="#"`,
  `primary_action_url="#"`: **19** ocorrencias, contra 10 visiveis;
  **(3) dado de contexto** — **43** valores `"#"` nas constantes de demonstracao de
  `core/views.py` e `ui_lab2/views.py`, que nenhuma regra sobre arquivo de template
  alcanca, porque o `#` nao esta no `.html`. Uma unica pagina de vitrine entregava
  **180** ancoras vazias.
  Os 72 usos passaram a apontar para a **propria vitrine**: demonstra a variante
  ancora do componente sem pular a pagina. A regra do auditor passou a ver a forma
  (2). A forma (3) so cai renderizando, entao o gate e
  `core/tests/test_ancora_vazia.py`: **renderiza as 22 telas de vitrine mais o
  dashboard e o perfil e conta `href="#"` no HTML entregue**. Canario rodado nos
  dois. Catraca **92 → 82**.
- [x] **Fase 5a — apagar a regra que ninguem alcanca. Feita em 05/08.**
  O enunciado original ("62 → ≤25 arquivos, ≤13.000 linhas") nao bate com o
  repositorio depois das fases 1–4, e continua nao batendo: **nao ha arquivo
  orfao**. Os 63 estao vivos — 35 pelo `style.css`/bundle e 28 por
  `{% block extra_css %}`. "62 → ≤25" nao sai de delecao, sai de **fundir**
  arquivo, que e outra operacao e mexe na ordem da cascata. O que era delecao de
  verdade foi feito:
  - **5.404 linhas fora**, 783 cortes, **429 classes que nenhum template, JS ou
    Python emite**. A lista completa em `docs/evidencias/`. Os maiores: `roteiros.css`
    (1.420), `oficios.css` (992), `page-shell.css` (492).
  - **Instrumento: `scripts/css_classes_mortas.py`**, agora versionado — na
    passagem anterior a analise nao foi commitada e so o resultado sobreviveu,
    entao ninguem podia repetir a medicao. O criterio esta no docstring dele.
  - **Prova de que a tela nao mudou:** `medir_estilos.py --diff`, **8.070 elementos
    em 60 telas** (30 paginas × 2 temas), **0 propriedade computada alterada**.
    A lista de paginas foi ampliada de 5 para 30 exatamente porque as cinco
    originais nao carregavam `roteiros.css` nem metade do que o corte pegou.
  - **Para chegar a ≤13.000 linhas faltariam ~24.000 alem disso**, e essas so
    saem consolidando regra duplicada entre os 63 arquivos: reescrita, nao
    faxina. Fica como **fase 5b**, com alvo e medicao proprios.
  - **`NOVO-35` ✅ o instrumento media transicao em voo.** Duas causas, nao uma. A
    primeira (elemento capturado sob o ponteiro, em `:hover`) ja tinha sido
    corrigida. A segunda so apareceu quando se rodou o instrumento **duas vezes
    contra o mesmo CSS**: trocar de tema dispara `transition` de cor, e a leitura
    saia `rgb(150,138,70)` numa execucao e `rgb(151,138,70)` na seguinte. Era esse
    o ruido dos "6 propriedades num card do Dashboard" que travou a fase 5 em
    04/08 — instrumento, nao defeito. Corrigido levando toda animacao ao fim antes
    da captura; a partir dai duas execucoes iguais dao diferenca **0**, e so entao
    o instrumento serve de gate.
  - **`NOVO-36` ✅ gate novo: sintaxe de CSS** (`core/tests/test_css_sintaxe.py`).
    A primeira aplicacao do corte partiu um `:is(` multilinha ao meio. O efeito
    nao e local: o navegador descarta **todas as regras seguintes** — 716 de 1.878
    no bundle, e os icones sumiram do sistema inteiro. E o que passou incolume:
    a suite (1.323 verdes, nenhum teste le CSS), o balanco de chaves,
    `collectstatic` e `build_shell_bundles --check`. So a medicao no navegador viu.
    O gate agora recusa parentese aberto em seletor e item vazio em lista de
    seletores, sem precisar de navegador — e foi conferido com canario.

- [x] **Fase 5a — correcao: o corte apagou CSS em uso.** 05/08/2026.
  - **`NOVO-37` 🔴 nome composto apagado: card de 3 e de 5+ servidores perdeu uma
    coluna.** O template escreve `cv-person-list--n{{ card.servidores_count }}` em
    **cinco** partials (oficios, termos, planos, ordens de servico, eventos). O nome
    final **nunca existe inteiro** em lugar nenhum, entao uma varredura literal
    conclui que `.cv-person-list--n3` nao tem consumidor. A fase 5a apagou `--n0`,
    `--n3` e `--n5..--n9`; sobrou `--n1`, que aparece literal num template. Efeito:
    card com 3 ou 5 a 9 servidores caiu de **tres colunas para as duas** da regra
    base. Medido no navegador: **7 variantes erradas** antes, **0** depois.
  - **Por que nenhuma das provas da 5a viu.** A suite nao le CSS. O gate de sintaxe
    so olha sintaxe. E a medicao de estilo computado **depende do dado**: nao existe,
    nos dados de desenvolvimento, card com 3 ou 5+ servidores nas 30 paginas — o
    seletor nem chega a ser exercitado. Ampliar a lista de paginas nao resolveria;
    o furo e de dado, nao de cobertura de rota.
  - **A defesa entra em dois niveis.** `core/tests/test_css_nome_composto.py` declara
    a familia e exige a regra de cada variante que existe — canario rodado, reprova
    exatamente `--n3` e `--n5..--n9`. E `scripts/audit_css_morto.py`, cujo criterio
    considera viva a classe cujo **bloco base** o codigo emite; e o que impede o
    proximo corte de repetir o erro. Catraca em **314** (`--max-regras`), medida:
    sao as regras que a varredura da 5a nao alcancava (`@media` aninhado).
  - **O que NAO era regressao:** outras cinco classes emitidas tambem perderam toda
    regra — `cv-fact-block--valor`, `cv-field-grid--2`, `cv-file-widget__action`,
    `prestacao-file-widget__action`, `ui-lab-section--status`. Todas tinham corpo
    **vazio** ou so comentario. Nao pintam nada; ficaram apagadas.
  - **`NOVO-38` 🟠 `NameError` na tela de modelo de texto do RT.** Segue igual: era o
    `NOVO-36` da sessao paralela, que ficou com o numero mas nao com a correcao.
    `prestacoes_contas/model_views.py` usa `_CAMPO_LABELS` sem definir nem importar;
    todo GET de "novo modelo" e de "editar" leva 500 e **nenhum teste tocava nessas
    rotas**. Corrigido, com `prestacoes_contas/test_modelos_texto_crud.py`.
  - **`NOVO-35` reaberto e fechado de novo.** A causa `:hover` tinha uma segunda
    camada: `page.click` no login deixa o ponteiro em (1007, 593) e o Playwright nao
    o devolve na navegacao — cai dentro do 4o card do Dashboard. `mouse.move(2, 2)`
    nao resolve porque (2, 2) e a sidebar. Agora o ponteiro sai da tela e o
    instrumento **aborta** se algo abaixo do `<body>` seguir em `:hover`. O `--diff`
    tambem passou a acusar **elemento que sumiu**: area < 2px sai da captura, entao
    um colapso de layout sumia em vez de virar diferenca.

- [x] **Fase 5b — as 314 regras que a 5a nao alcancava.** 05/08/2026.
  - **314 regras, 248 classes, 2.706 linhas** em 21 arquivos. Sao as que a varredura
    da 5a nao via: ela era regex com lookbehind em `}` e pulava a primeira regra de
    dentro de cada `@media`. O parser que conta chaves enxerga.
    Fontes de CSS: **35.120 → 32.741 linhas**. Catraca de `audit_css_morto` **314 → 0**,
    na CI e na suite.
  - **A varredura de tela cresceu para 48 paginas / 96 telas / 20.284 elementos.**
    Faltavam as 16 rotas de `/dev/ui-lab/*` — unico consumidor de `static/css/dev/*`,
    que era o **segundo e o terceiro maiores blocos do corte**. E o `roteiro-novo`,
    a pagina do maior bloco, estava **saindo da medicao por timeout** de
    `networkidle` sem ninguem notar; agora cai para `load`. Resultado: **0
    propriedades mudadas, 0 elementos sumiram**.
  - **A checagem que pegou o `NOVO-37` foi refeita aqui, antes de commitar:** das 217
    classes que perderam toda regra, **nenhuma e emitida** por template ou JS.
  - Catraca de avisos **184 → 182**.

- [x] **`NOVO-41` 🟡 literais de cor: 81 hex + 71 `rgba()` que a regra nem via.**
  05/08/2026. Decisao de produto do usuario: **derivar dos tokens**, aceitando que a
  cor pintada mude. O que se descobriu no caminho:
  - **A regra so olhava `#hex`.** Havia **71 literais `rgba()`** invisiveis para ela —
    quase tantos quanto os 81 contados. O menu de acoes tinha uma paleta inteira de
    categoria (mensagem, oficial, documento, rota, pacote) escrita em `rgba()`.
  - **Dois falsos positivos da propria regra:** hex dentro de comentario de BLOCO
    (o auditor so pulava a linha que ABRE o comentario) e hex em comentario de fim de
    linha documentando valor velho. Corrigido o rastreio de bloco no auditor.
  - **Quase entrou um defeito de contraste meu:** trocar `color: #fff` por
    `var(--on-accent)` poe tinta quase preta sobre gradiente vermelho no tema escuro
    (`--on-accent` segue o acento, que la e dourado). Dai `--on-state`, que segue o
    **estado**: branco no claro (5,4:1 no perigo) e escuro no escuro (6,6:1) — medido.
  - **`NOVO-42` 🟠 contraste do botao WhatsApp.** Branco sobre `#25d366` da **1,98:1**,
    reprova qualquer criterio. Preexistente. Trocado por tinta escura: **8,85:1**.
  - **O teto de 60 tokens reprovou em 63 e nao foi levantado.** Tres dos que eu tinha
    criado sairam derivados: "mensagem" e o proprio `--cv-state-success` (delta maximo
    de 9/255), "documento" e o perigo abafado, e a tinta de marca virou `color-mix`.
    Ficou em **52**.
  - Efeito medido: **241 propriedades em 54 elementos**, todas de cor, so em tela de
    vitrine — porque e la que os botoes de estado aparecem com os dados de
    desenvolvimento. **Isso e limite do dado, nao prova de que producao nao mudou** —
    a mesma armadilha do `NOVO-37`. Prints antes/depois em `docs/evidencias/novo30-cores/`.
  - Catraca **129 → 0**. Medido na base com o #171 e o #172 dentro: `--max-warnings 0`
    **passa**. E o alvo que o prompt do `NOVO-30` fixou na fase 4 e que ficou quatro
    fases em aberto, com dono nomeado em cada uma — 109 literais de cor (`NOVO-41`),
    92 `legacy_page_header` (`NOVO-39`, que era defeito da regra), 10 `href_hash`
    (`NOVO-40`) e 1 `domain_selector_in_global` (seletor citado dentro de comentario
    de bloco). Daqui em diante o auditor nao tem divida a tolerar: aviso novo reprova.

- [x] **`NOVO-43` 🔴 os alvos "≤25 arquivos" e "≤13.000 linhas" NAO sao alcancaveis por
  consolidacao — medido, nao estimado.** 05/08/2026.
  - **Fundir arquivo quebra a cascata.** Tentei: 17 arquivos de pagina em 6, na ordem
    exata que os templates carregam. Resultado medido: **13.118 propriedades mudadas**
    em 96 telas. O motivo e estrutural — CSS de pagina e escopado POR PAGINA; fundido,
    cada pagina passa a receber as regras da outra. `/cadastros/` herdou `usuarios.css`
    e mexeu ate na sidebar. Revertido.
  - **Nao ha 19.000 linhas de duplicata para tirar.** A duplicata EXATA no repositorio
    inteiro e de **~700 linhas** (96 copias), e dessas so **110** saem com seguranca:
    o resto e a mesma regra dentro e fora de um `@media`, que nao e a mesma regra. Com
    a profundidade do at-rule na chave, a poda deu **0 propriedades mudadas**.
  - **A conta nao fecha:** 4.221 regras para 32.678 linhas dao ~7,7 linhas por regra.
    Chegar a 13.000 exigiria apagar ~60% das REGRAS — apagar estilo em uso, nao
    consolidar. E o que nao tinha consumidor ja saiu na 5b, com a catraca em zero.
  - **"≤25 arquivos" tambem briga com o `NOVO-12`,** que decidiu de proposito manter os
    arquivos-fonte como unidade de edicao e resolver o waterfall com bundle. Os 23 do
    shell ja chegam ao navegador como **um** arquivo. Fundir as fontes desfaria essa
    decisao para melhorar um numero que o usuario nao sente.
  - **Se o alvo tiver de valer**, o caminho e outro: escopar cada folha de pagina por
    uma classe de pagina antes de fundir. E reconstrucao de cascata, com alvo e
    medicao proprios — nao cabe nesta fase e nao e faxina.

  > **Para quem pegar a fase 6 (consolidacao):** o alvo e regra **duplicada** entre
  > arquivos, nao regra morta — essa acabou, e a catraca esta em zero. Sao 62
  > arquivos e 32.741 linhas para os alvos de ≤25 e ≤13.000, e eles so saem
  > **fundindo arquivo**, o que mexe na ordem da cascata. A medicao tem de ser a
  > mesma: `medir_estilos.py --diff` com as 48 paginas, exigindo 0.

---

## 7.1 Escopo novo, fora das oito etapas

### Rascunhos antigos triados em 29/07

- [x] **#32** — destino em CAIXA ALTA no documento da Ordem de Serviço. Confirmado
  presente e corrigido: `format_document_display` no `_destinos_display`.
- [x] **#44 (metade)** — `Cache-Control: no-store` ausente nas respostas de PDF; o
  navegador podia servir a versão pré-retificação. A **outra metade do #44 já
  estava corrigida**: `assunto_termo` hoje só devolve "autorização"/"convalidação",
  nunca "retificação"/"complementação" — o rótulo do número virou campo separado.
- [x] **#27** — substituído pelo #106 (recursão do editor de roteiro).

Pedidos que não vieram das auditorias entram aqui, com posição decidida antes de
começarem. Escopo novo que se infiltra numa etapa em curso é como a Etapa 1
perde o prazo e a Etapa 2 perde a rede.

| Proposta | Estimativa | Situação |
|---|---:|---|
| Reescrita visual Administração (Cadastros + Usuários) | 4 PRs | ✅ PR1–PR4 (D-53/D-54 local/D-55/step1 Cadastros+Usuários) |
| Linha de Cadastros roster (`cv-record-row`) | 1 PR | ✅ D-52 parcial — avatar/subtitle/facts; sem `simple-list-item` |
| Filtro por cargo na lista de Servidores (top 3) | — | ✅ NOVO-21 — abas na `list-toolbar` |
| Filtro unidade/combustível na lista de Viaturas | — | ✅ NOVO-22 — unidade da config + top 3 combustíveis |
| Ação flutuante secundária empilhada | — | ✅ NOVO-23 — modificador `--stacked` era vencido pela base de `cv-buttons.css` |
| Usuários/Áreas em duas listas (`list_page_standard`) | 1 PR | ✅ NOVO-24 — camadas `selectors`/`presenters`/`services` no app `usuarios`; ORM em view 39 → 36 |
| [Arquitetura de configurações](PROPOSTA_CONFIGURACOES.md) — tela por seções declaradas, config por documento, preferências por usuário | 17–28 dias | **aguardando decisão** de posição na fila |
| [Etapa 9 — HTML e biblioteca de componentes globais](PLANO_HTML_COMPONENTES_GLOBAIS.md) — taxonomia única, um componente por função, casco de página único | 12 PRs | 📋 plano escrito 05/08; Fase 0 a começar |

### Etapa 9 — Reescrita do HTML e da biblioteca de componentes (05/08/2026)

A Etapa 6 fechou os defeitos de HTML que a auditoria catalogou (`H-02`..`H-10`, `D-41`). Ela
não unificou a biblioteca, e não prometia isso. O que sobrou é propriedade do conjunto, não
defeito de tela: **`templates/components/` abriga hoje duas taxonomias paralelas**
(`components/<família>/` e `components/ui/<família>/`, com 8 famílias existindo nas duas), e a
página escolhe entre elas por acidente histórico.

Medido no `main` de 05/08 (`1336` testes verdes, auditor em `184` avisos): 96 componentes, 5
órfãos, 9 vivos só por UI Lab/teste, 10 aliases de uma linha, 4 sistemas de confirmação de
exclusão, 7 componentes de botão, 10 grupos de partials byte-idênticos, 12 páginas
`confirm_delete.html` quase iguais, 2 cascos de wizard divergindo em 5 linhas, 46 páginas
montando `page-shell` à mão contra 18 no `flow_base`, e **390 de 1.262 includes sem `only`** —
o gate declarado na tabela da §6 para a Etapa 6 nunca foi construído.

Catálogo `NOVO-39` a `NOVO-54`, arquitetura alvo, as 12 fases, os gates novos e o dicionário de
renomeação completo estão em [`PLANO_HTML_COMPONENTES_GLOBAIS.md`](PLANO_HTML_COMPONENTES_GLOBAIS.md).

- [ ] `NOVO-39` 🟠 duas taxonomias paralelas de componentes (8 famílias duplicadas)
- [ ] `NOVO-40` 🟠 5 componentes órfãos · 9 vivos só por UI Lab/teste (`main_list_card`, 167 linhas, é mantido vivo por uma asserção)
- [ ] `NOVO-41` 🟠 10 aliases de uma linha — a padronização de 22/07 declarou tê-los eliminado
- [ ] `NOVO-42` 🔴 4 sistemas de confirmação de exclusão, dois com nome quase igual e comportamento diferente
- [ ] `NOVO-43` 🟠 7 componentes de botão para um `<button>`
- [ ] `NOVO-44` 🟠 3 sistemas de alerta
- [ ] `NOVO-45` 🟠 2 sistemas de card de formulário (102 e 112 linhas), que precisaram da **mesma** correção de vazamento duas vezes (`H-04`, `H-05`)
- [ ] `NOVO-46` 🟠 2 sistemas de item de lista
- [ ] `NOVO-47` 🟠 10 grupos de partials locais byte-idênticos (SHA-256)
- [ ] `NOVO-48` 🟠 2 cascos de wizard divergindo em 5 linhas; nenhum usa o `flow_base` criado para isso
- [ ] `NOVO-49` 🟠 não existe casco de página único (46 × 18)
- [ ] `NOVO-50` 🟠 12 páginas `confirm_delete.html` idênticas exceto por 3 strings
- [ ] `NOVO-51` 🟠 390 de 1.262 includes sem `only`; gate da Etapa 6 nunca construído
- [ ] `NOVO-52` 🟡 nenhum componente declara contrato; zero templatetags, kwargs soltos
- [ ] `NOVO-53` 🟡 `PADRAO_TEMPLATES.md` descreve estrutura de diretórios que não existe
- [ ] `NOVO-54` 🟡 nomenclatura mista (pt/en, prefixo `_` inconsistente, 3 convenções de sufixo)

> **Correção de método registrada antes de virar erro.** A primeira contagem de órfãos deste
> plano deu 21 — estava errada. Ela procurava só `{% include "caminho" %}`, e o projeto passa
> caminho de template **como valor de parâmetro** (`band_tabs_template=`, `body_template=`).
> Contando as referências por string, os órfãos reais são 5. Não é detalhe de contagem: neste
> repositório o grafo entre templates **não é sintático**, e ferramenta que só olhe `include`
> apaga arquivo vivo. O `grep` de prova da regra 6 do `AGENTS.md` tem de ser pelo caminho.

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
