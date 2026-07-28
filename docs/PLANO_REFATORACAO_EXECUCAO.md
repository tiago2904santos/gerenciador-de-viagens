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

| Pergunta da banca | Hoje | Depois das Etapas 1–3 |
|---|---|---|
| "E quando o valor da diária mudar?" | exige deploy e recalcula o histórico | vigência + valor congelado no documento |
| "A lista aguenta 500 ofícios?" | 11 MB de HTML, sem paginação | paginada |
| "O documento gerado confere?" | nenhum teste abre o arquivo | *golden files* dos 11 documentos |
| "Qual a cobertura?" | assimétrica, Prestações a 0,04 | piso por app no CI |

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
- [ ] `T-01` suíte de Prestações: 5 etapas + assinatura pública
- [ ] `N-04` *golden files* dos 11 documentos gerados
- [ ] `T-03` `coverage` no CI com piso por app
- [ ] `D-02` (backend) testes de contrato de `organizer.py`

### Etapa 3 — Regra de negócio
- [ ] `N-01` tabela de diárias com vigência + congelamento do valor no roteiro
- [ ] `N-05` unificar as duas regras de complemento
- [ ] `N-06` `CAPITAIS_POR_UF` → base geográfica IBGE
- [ ] `N-08` / `N-09` / `N-10` bordas de `_segment_breakdown`, fechamento por servidor, pernoite curto
- [ ] `P-03` constraints e indexes em roteiros/termos/justificativas
- [ ] `N-13` documentar diárias, numeração e status em `REGRAS_DE_NEGOCIO.md`

### Etapa 4 — Backend de aderência
- [ ] `P-01` selectors em eventos, termos, OS, PT + gate anti-ORM-em-view
- [ ] `P-02` `core/catalog.py` e migração dos 13 catálogos
- [ ] `P-04` **widget base com classes canônicas** (pré-requisito das Etapas 6 e 7)
- [ ] `P-05` `core/errors.py` + varredura dos 57 `except` do Drive
- [ ] `P-06` fatiar `planos_trabalho/views.py` e `oficios/views.py`
- [ ] `P-07` `__str__` nos 3 models de `core`
- [ ] `S-06` documentos assíncronos via Celery

### Etapa 5 — Motores JS
- [ ] `J-06` apagar 8 arquivos órfãos + hooks sem dono (−989 linhas)
- [ ] `J-02` `CV.registry.destroy(root)` e limpeza do `action-menu`
- [ ] `J-01` registrar 8 componentes como enhancer
- [ ] `J-04` Quick Add/Quick Edit como enhancer
- [ ] `J-03` um motor de filtro por lista (`data-collection-mode`)
- [ ] `J-07` migrar 13 arquivos para `CV.http`; apagar 11 cópias de CSRF
- [ ] `J-16` `CV.util` (−17 cópias) · `J-12` `CV.feedback` (−13 `alert`/`confirm`)
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
- [ ] Fase 0–1: apagar aliases de tema e CSS morto (−3.000 linhas)
- [ ] Fase 2–3: tokens indefinidos + CSS faltante dos componentes globais
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

## 8. Os erros que matam este refactor

1. **Começar pelo CSS.** Discutido em §1. É a etapa 7, não a 1.
2. **Renomear e corrigir no mesmo PR.** Quando quebrar, não se sabe qual metade quebrou.
3. **Deixar os três agentes na mesma camada.** Conflito garantido, revisão impossível.
4. **Dar o repositório inteiro de contexto.** Dê a seção da auditoria. O agente que lê 900
   linhas para consertar um `border-radius` acerta menos, não mais.
5. **Afrouxar a catraca para o PR passar.** O número de avisos só desce.
6. **Refatorar Prestações antes da Etapa 2.** É o módulo com dinheiro, assinatura pública e
   cobertura 0,04. Ali, sem teste, o refactor é aposta.
