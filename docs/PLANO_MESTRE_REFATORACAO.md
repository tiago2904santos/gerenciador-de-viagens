<<<<<<< HEAD
# Plano mestre do refactor — ciclo de agosto/2026

**Este é o único documento que responde "o que eu faço agora".** Os planos por frente detalham
o como; o catálogo lista os defeitos; este aqui manda na ordem.

| Documento | Papel |
|---|---|
| [`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md) | Todo defeito vigente, com ID, evidência medida e status |
| [`PLANO_BACKEND.md`](PLANO_BACKEND.md) | Camadas, isolamento por área, integridade, consulta (`BE`, `DB`) |
| [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md) | CSS, templates, JS, acessibilidade (`UI`, `HT`, `JS`) |
| [`PLANO_DESEMPENHO.md`](PLANO_DESEMPENHO.md) | Régua e otimizações de entrega (`PF`) |
| [`../AGENTS.md`](../AGENTS.md) | Regras de conduta, limites invioláveis, corpo de PR |
| `historico/2026-07-refactor/` | O ciclo anterior, congelado |

---

## 1. Por que um ciclo novo

O ciclo de julho fechou. Das oito etapas, sete foram concluídas e a oitava ficou pela metade —
92 itens fechados, 6 pendentes. Ele fez o que se propôs: a suíte foi de 812 para **1.301 testes
verdes**, o auditor de front caiu de 465 para **392 avisos**, o motor de diárias passou a bater
ao centavo com os demonstrativos oficiais, e as listas deixaram de ter N+1.

Continuar marcando linha naquele plano seria errado por um motivo simples: **os enunciados
venceram**. O próprio plano registra três correções de rumo (`J-05`, `J-11`, tokens indefinidos)
em que o defeito descrito não era o defeito existente. Depois de ~120 PRs, citar `D-14` é citar
um retrato de julho, não o sistema de hoje.

Este ciclo começa com medição nova. Tudo aqui foi medido em **05/08/2026**, por execução.

## 2. Linha de base medida

> **Esta tabela é de 05/08 e envelheceu — vale o §7.4 deste próprio documento.** Remedida em
> 09/08: a suíte está em **1.824 testes, 7 skips, 14,7 s** (não 1.306 em 9,9 s), o auditor de front
> em **240 avisos com teto 246** (não 392 com teto 401), o CSS de fonte em **32.940 linhas** (não
> 43.038) e o JS em **18.382** (não 17.859). A linha de base vigente do front, com o comando de
> cada número ao lado, está no §2 do
> [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md).

| medida | valor | como |
|---|---|---|
| Suíte | **1.306 testes**, 0 falhas, 4 skips, **9,9 s** | `manage.py test --settings=config.settings.test --parallel 4` |
| Auditor de front | **392 avisos**, 0 erros (teto do CI: 401) | `scripts/audit_frontend_standards.py` |
| ORM em módulo de view | **30** (google_drive 10, core 9, documentos 4, oficios 4, roteiros 2, justificativas 1) | `scripts/audit_django_architecture.py` |
| Classe CSS dentro de `attrs={}` em forms | **0** | grep em todos os `forms.py` |
| Código (fonte) | 93.232 linhas Python · **43.038 CSS** · **17.859 JS** · 462 templates | `wc -l`, excluindo `shell.bundle.*` |
| Código (entregue) | `shell.bundle.css` 17.669 linhas · `shell.bundle.js` 7.633 | concatenação das fontes acima — **não somar aos dois** |
| Modelos e migrações | 54 modelos, 154 migrações, **0 pendentes**, 0 irreversíveis | `makemigrations --check --dry-run` |
| Constraints | 61 `UniqueConstraint` · **2** `CheckConstraint` | introspecção de `_meta.constraints` |
| Índices | 390 em 75 tabelas · **0 GIN, 0 trigram** | `pg_indexes` |
| Isolamento por área | 28 de 54 modelos têm `area`; **27 com `area` anulável**; 123 `.objects.` fora do filtro | introspecção + varredura AST |
| Classes CSS declaradas | **2.612**, das quais **~929** sem uso comprovado | extração + grep em corpus de 4,7 MB, descontando 3 padrões de classe dinâmica |
| CSS entregue por página | 664–816 KB, **~10% casado** | Chromium via CDP |
| HTML da lista de Ofícios | **425 KB** para 20 cards, 192 KB só em SVG inline | `test.Client` + contagem |

## 3. As quatro frentes

**Backend** (`BE`, `DB`) — 63,5 dias. O risco está aqui: isolamento por área é convenção, o banco
não impõe integridade, e há defeitos que o usuário encontra hoje.

**Frontend** (`UI`, `HT`, `JS`) — ver [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md). O peso está aqui:
~36% do CSS sem uso comprovado, tema escuro resolvido por 5.843 linhas de exceção com 190
`!important`, e CSS de domínio alheio importado em 26 templates.

**Desempenho** (`PF`) — 9 a 13 dias próprios. O trabalho aqui é **medir** e cortar o que a
medição apontar; boa parte da otimização real mora nas outras duas frentes, e este plano
fornece a régua que prova o ganho.

**Finalização** — o que falta terminar, não refatorar: `diario_bordo` é um app-casca de 33
linhas com rota não linkada, há presenter morto prometendo "DOCX (em breve)", 13 PRs abertos
sem triagem, dois UI Labs concorrentes sem regra de qual é o vigente, e a arquitetura de
configurações segue como proposta sem posição na fila.

## 4. A fila

| Fase | O que | Frente | Dias | Risco | Por que aqui |
|---|---|---|---:|---|---|
| **0** | **Defeitos que atingem o usuário agora** | `BE-01`…`BE-08`, `JS-01`, `JS-04`, `HT-01`, `HT-09`, `HT-11`, `JS-11`, `JS-12`, `QA-01`, `QA-02`, `QA-04`, `QA-09` | 10 | baixo | Correções isoladas, nenhuma depende de renomear ou mover nada. Se o calendário virar, para-se aqui e o sistema já está melhor. Inclui o wizard de plano de trabalho que não finaliza, a exclusão de anexo por `GET`, um XSS reproduzido no navegador, o foco de teclado invisível em todo campo, campos sem nome acessível, o admin sem rate limit, e a validação central de upload que **nunca roda** nos 5 tipos de anexo de prestação. |
| **1** | **Réguas e rede de segurança** | `PF-07`, `QA-03`, `QA-06`, `QA-07`, `QA-11`, `QA-12` | 7 | médio | `scripts/medir_desempenho.py` no CI com volume realista, `ruff`, Dependabot, o rollback de deploy que hoje não desfaz migração, e o teste da CVE do WeasyPrint que hoje verifica texto-fonte. Sem régua, toda fase seguinte é afirmação sem prova e a regressão volta no PR seguinte sem ninguém ver. |
| **2** | **Isolamento por área vira invariante** | `BE-09`, `BE-10`, `DB-01`…`DB-05` | 18 | **alto** | Quatro vazamentos entre tenants já provados por teste. É o maior risco do sistema e toda fase posterior escreve código que precisa respeitar o recorte. |
| **3** | **O banco defende os dados** | `DB-06`…`DB-08` | 8 | médio | Cascata que apaga comprovante e assinatura; 2 `CheckConstraint` em 54 modelos. Depende da fase 2: pôr `NOT NULL` sobre modelo que ainda vaza é lacrar a porta errada. |
| **4** | **Fundação do front** | `PF-01`, `HT`, `UI` (CSS morto) | ver plano de front | médio | Folha de símbolos de ícone, componentes que faltam, remoção do CSS comprovadamente morto. Fixa **quais classes existem** — pré-requisito da reconstrução. **F1 concluída** (`JS-06`, `JS-05`, `JS-02`); faltam F2 e F3. |
| **5** | **Consulta e índice** | `DB-09`…`DB-12` | 8,5 | médio | Ganho medido de 13× a 29× num índice composto; busca livre em varredura sequencial. Depois da fase 3, porque constraint muda plano de consulta. |
| **6** | **Camadas e duplicação** | `BE-11`…`BE-17` | 17,5 | alto | Editor de roteiro em 3 cópias, `roteiro_logic.py` com 1.779 linhas fora do contrato. Mexe em roteiro e diárias: **plan mode obrigatório**. |
| **7** | **Reconstrução do front** — CSS, HTML e JS. Dimensionada em 09/08 no [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md): doze etapas | `UI`, `HT`, `JS` | ver o documento | médio, com a E8 em **alto** | A mais visível e a mais reversível. Depois da fase 4, que define os nomes. Escopo ampliado por decisão do dono: componentização por `django-cotton`, desenho único entre os temas e teste de JS no CI |
| **8** | **Observabilidade e autorização** | `BE-18`, `BE-19` | 4 | médio | `capture()` só existe num app; `PAPEL_ADMIN` é decorativo. |
| **9** | **Finalização e higiene** | `BE-20`…`BE-25` | 4 | baixo | Fecha a conta: app-casca, código morto, repositório, PRs abertos, vocabulário de rotas. |

### Paralelismo permitido

```
Fase 0 ──► Fase 1 ──┬──► Fase 2 ──► Fase 3 ──► Fase 5
                    │
                    └──► Fase 4 ──► Fase 7
                                    Fase 6 (backend, camadas)
Fase 9 — a qualquer momento, em branch própria
```

- **Backend e frontend correm em paralelo** — são superfícies disjuntas.
- **Fases 4 e 7 nunca correm juntas**: o HTML define o nome, o CSS pinta o nome.
- **`BE-11`, `BE-12` e `BE-13` nunca em paralelo entre si**: são a mesma superfície.
- **Duas frentes nunca na mesma camada ao mesmo tempo.**

### O corte mínimo, se o prazo apertar

**Fases 0 + 1 + 2.** São 35 dias e eliminam as duas respostas indefensáveis:

| Pergunta | Antes | Depois |
|---|---|---|
| "O sistema separa os dados de cada unidade?" | quatro vazamentos provados; o recorte depende de o programador lembrar | invariante no manager, com teste de duas áreas por modelo |
| "O plano de trabalho finaliza?" | o botão recarrega a página em silêncio | finaliza, com teste de regressão |

## 5. Gates

Nenhum PR entra sem os quatro:

1. **Suíte verde** em PostgreSQL, com o número de testes e o tempo no corpo do PR. Reduziu o
   número de testes verdes ou aumentou o tempo em mais de 20%? Justifique.
2. **Catracas só descem.** `audit_frontend_standards.py --max-warnings 401` (medido hoje: 392),
   `audit_django_architecture.py`, `audit_ui_patterns.py`, pisos de `.github/coverage-floors.json`.
3. **Régua de desempenho** (a partir da fase 1): a rota tocada não pode passar do teto declarado
   em queries, tempo, KB de HTML e uso de CSS.
4. **Evidência do defeito.** Todo ID fechado precisa de um teste que falharia antes.

## 6. Ciclo de trabalho

Vale o do [`AGENTS.md`](../AGENTS.md) §4, com dois acréscimos deste ciclo:

- **Uma fase por PR, um dono por PR.** Correção de defeito e renomeação nunca viajam juntas.
- **Toda fase de risco médio ou alto começa em plan mode**, com o plano escrito no PR antes da
  primeira linha de código.

## 7. Os erros que matam este ciclo

1. **Começar pelo CSS.** É a fase 7, não a 1. Ele renomeia classes das quais o JS depende e
   estiliza componentes que a fase 4 ainda vai criar.
2. **Tratar o isolamento por área como detalhe.** É a fase 2 porque é o único defeito cujo
   sintoma é dado de um órgão aparecendo para outro.
3. **Otimizar antes de medir.** A medição desta sessão já derrubou duas suspeitas clássicas: não
   há N+1 nas listas e não há geração documental síncrona. Quem "otimizar" isso trabalha de graça.
4. **Confiar em número velho.** Este documento tem data. Se estiver lendo daqui a três meses,
   meça de novo antes de citar.
5. **Afrouxar catraca para o PR passar.** O número só desce.
6. **Deixar o escopo novo entrar no meio de uma fase.** Vai para o catálogo com `NOVO` e recebe
   posição na fila.

## 8. Decisões pendentes

Precisam de resposta humana; nenhuma bloqueia a fase 0.

| Decisão | Onde entra | Por que precisa de você |
|---|---|---|
| Comportamento de expiração de sessão | `PF-03` (fase 1) | Tirar a escrita do caminho quente muda se a sessão de 8 h conta do login ou da última ação |
| Quais operações exigem `PAPEL_ADMIN` | `BE-19` (fase 8) | O modelo de dados promete três papéis; o código aplica dois |
| ~~Qual UI Lab é o vigente~~ **decidida em 07/08 (PR #247): nenhum — os dois saíram** | `BE-25` (fase 9) | A cascata de componentes órfãos que a decisão deixou é o `NOVO-44`, fechado |
| Arquitetura de configurações | fora das 9 fases | Proposta de 17–28 dias, em `historico/2026-07-refactor/planos/PROPOSTA_CONFIGURACOES.md`; entra como fase própria ou fica fora do ciclo |
| Triagem dos 13 PRs abertos | fase 9 | 12 são de maio–julho, anteriores ao refactor; fechar ou reabrir é chamada sua |
| ~~Catálogo global do `DB-02` (grupo 2)~~ **decidida em 07/08: cópia por área, seguindo o `NOVO-09`** | `DB-02` (fase 2) | Executada nas migrações `eventos/0016` e `planos_trabalho/0024`. **Correção de fato:** as linhas de seed **não** eram "servidas a todas as áreas" — medido nas três áreas, eram vistas por **zero** usuários com área, porque `filter_queryset_by_area` é estrito. Duplicar não repartiu nada: deu a cada área um catálogo que ela não tinha. O resíduo (instalação nova e área criada depois) é o `NOVO-49` |

## 9. Quadro de acompanhamento

Marque aqui, no mesmo PR que faz o trabalho. `[ ]` pendente · `[~]` em andamento · `[x]` pronto.
O detalhe de cada ID está no [`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md).

**São 95 IDs no catálogo e 92 neste quadro.** Os três de fora estão de fora de propósito:
`PF-02` e `PF-05` são **métricas de aceite** de outros IDs, não trabalho próprio (uso de CSS por
rota e tempo da lista de Ofícios); `DB-13` (composição da diária como texto livre) está
deliberadamente fora desta rodada, porque mexer nele reabre a regra de dinheiro — está catalogado
para uma rodada futura, com `DB-01` como pré-requisito.

### Fase 0 — Defeitos que atingem o usuário agora ✅ **COMPLETA** (06/08/2026)
- [x] `BE-01` wizard de plano de trabalho não finaliza e "Voltar" avança
- [x] `BE-02` exclusão de anexo por `GET`, sem CSRF
- [x] `JS-01` XSS: nome de pasta do Drive cru em `aria-label`
- [x] `HT-01` foco de teclado invisível em todo campo, inclusive no login
- [x] `BE-04` formulário de evento oferece documentos de outras áreas
- [x] `BE-03` filtro de data da lista de ofícios descartado em silêncio
- [x] `BE-05` seletor de modelo de motivo da OS expõe outras áreas
- [x] `BE-06` relatório técnico sai com a cidade-sede de outra área
- [x] `BE-07` exclusão de anexo dá 500 e deixa registro órfão
- [x] `BE-08` oito redirects seguem o que o POST mandar
- [x] `JS-04` `.then()` sem `.catch` no editor de roteiros — a fila de estimativa morria inteira
      no primeiro erro, não só o trecho que falhou. Achou `NOVO-22` (`applyingState` travado,
      **fechado junto**), `NOVO-23` (remoção de assinado que mentia, **fechado** no PR #208) e
      `NOVO-24` (`.then` solto na criação de pasta do Drive, **fechado**). Os três achados do
      inventário estão resolvidos.
- [x] `HT-09` login sem skip link e sem erro associado
- [x] `HT-11` campos de formulário renderizados sem nome acessível (5 medidos em 2 telas)
- [x] `QA-01` login do Django Admin sem rate limit nenhum
- [x] `QA-02` rate limit depende de um Redis que nenhum ambiente declara
- [x] `QA-04` 🔴 a validação central de upload nunca roda, nos 5 tipos de anexo
- [x] `QA-09` dois templates de `.env` de produção divergentes
- [x] `JS-11` `maskCep` duplicada e `onlyDigits` em 4 cópias — a causa era falta de saída pública
      em `masks.js`, não desleixo; duas regras novas no auditor impedem a volta
- [x] `JS-12` `CV.componentRegistry` era alias **sem nenhum consumidor** — o enunciado "mesmo
      objeto" já tinha sido refutado em runtime; o defeito real era código morto

### Fase 1 — Réguas e rede de segurança ✅ **COMPLETA** (07/08/2026)
- [x] `PF-07` `scripts/medir_desempenho.py` com dois volumes, no CI — achou `NOVO-06`
      (vazamento entre áreas, **fechado**), `NOVO-07` (15 MB de HTML, **fechado**) e `NOVO-08`
      (N+1 de 296, 138 e 55, **fechado**: 34, 20 e 11). Os três saíram da régua; nenhum aparecia
      na linha de base, que mediu com o banco vazio.
- [x] `NOVO-07` seletor de ofício sob demanda nas três telas — `justificativas:index` de
      **5.398 KB para 142,5 KB** com 20.000 ofícios, e a diferença entre os dois volumes caiu de
      27× para 0,3%: a página parou de crescer com a tabela. Tetos da régua baixados.
- [x] `NOVO-10` 🔴 entrar com a senha certa devolvia 500 — `LoginView.form_valid` chamava
      `self._rate_key()`, método que o `QA-01` levou embora. Achado dirigindo o navegador para
      conferir o `NOVO-07`, não por auditor. **Caminho de sucesso sem teste é caminho não
      coberto:** havia teste para errar a senha seis vezes e nenhum para acertar uma.
- [x] `QA-03` rollback de deploy não desfaz migração — `scripts/deploy_rollback.sh` + drill no CI.
      Não restaura backup de propósito: para e instrui. **Fecha a Fase 1.**
- [x] `QA-06` teste da CVE do WeasyPrint verifica texto-fonte, não comportamento
- [x] `QA-07` sem lint/formatação/tipo em Python no CI — **lint fechado** (`ruff` em zero,
      gate em `tests.yml`). Formatação e tipo seguem abertos como `NOVO-05`. A folga zero do
      `--max-orm-em-view 30` continua de pé: qualquer ORM novo em view reprova o CI.
- [x] `NOVO-11` o auditor de ORM em view conta `.objects` dentro de docstring — a contagem agora
      é por `ast` (`contar_orm_no_codigo`), com teste que falharia antes. A troca não mudou o
      número: 29 por regex e 29 por árvore, mesmos apps — a folga que "ninguém sabia medir" era
      zero, e a catraca segue em 29.
- [x] `NOVO-12` 🔴 nenhuma régua olha a configuração de produção — `check --deploy --fail-level
      ERROR` no `deploy.yml`, após o checkout (os checks têm de ser os do código que entra no
      ar; antes dele, o E002 antigo travaria o próprio deploy da correção), antes do
      `collectstatic` e protegido pelo rollback do `QA-03`. O
      `core.E002` foi decidido: **rebaixado a `core.W002`** (produção roda `auto`; check
      insatisfazível não é catraca, é ruído — o SLA real segue medido no CI com unoserver de
      verdade). E a ponta que o enunciado não via: `SECRET_KEY` fraca é `security.W009`,
      **Warning**, que `--fail-level ERROR` não trava — `core.E003` promove os critérios a
      `Error`, senão o gate não pegaria o próprio defeito que o motivou. `ALLOWED_HOSTS` vazia
      passou a falhar cedo no `prod.py`, padrão `REDIS_URL`. **Fecha a Fase 1 inteira.**
- [x] `QA-11` `reparar-producao.yml` em UTF-16LE
- [x] `QA-12` sem Dependabot, sem CodeQL, sem gate de acessibilidade — **Dependabot entrou**;
      CodeQL e gate de acessibilidade seguem abertos

### Fase 2 — Isolamento por área
- [x] `DB-03` limpeza de rascunhos apaga rascunho de outra área — e mais: sem limite de idade, ela
      apagava o rascunho que outra pessoa da **mesma** área estava editando, porque `Roteiro` não
      tem dono. Registrado como `NOVO-13` e corrigido junto (mesmas três linhas de `filter`).
- [x] `BE-09` `AreaScopedManager` nos 28 modelos com `area` — **fechado; catraca em **zero**, em 6 fatias, medida por
      `scripts/audit_area_scoped_managers.py`.** Duas decisões fixaram o desenho: (1) fora de
      request `objects` **não** recorta — a alternativa faria toda tarefa Celery virar no-op
      silencioso (`NOVO-20`); (2) `_default_manager` fica no manager irrestrito, para não
      neutralizar o guarda m2m, o `core.E001` e os comandos de backfill — o preço é o `NOVO-21`.
  - [x] fatia 1 — mecanismo, catraca, testes de contrato, `termos` e `ordens_servico` (26 restantes)
  - [x] fatia 2 — `oficios` (4 modelos, 11 sites de `all_objects`; 22 restantes). Duas
        descobertas: o modelo histórico de migração **perde** o `objects` a partir do
        `AlterModelManagers` do app (`core/managers.py` documenta a regra), e a suíte
        desligava o piso de numeração — `NOVO-28`
  - [x] fatia 3 — `roteiros` + `eventos` (4 modelos, 6 sites de `all_objects`; 18
        restantes). Fechou **três vazamentos reais** que não estavam no catálogo
        (`NOVO-30`) e mostrou que renomear para `all_objects` desinflava a catraca de
        ORM-em-view — o auditor passou a contar os dois nomes
  - [x] fatia 4 — `prestacoes_contas` + `documentos` (4 modelos, 4 sites; 14 restantes).
        Encostou no caminho **assíncrono**: `_objeto_do_job` é genérico sobre cinco
        modelos de apps migrados em fatias diferentes, e lá a forma certa é
        `_base_manager`, não `all_objects` — `Servidor` só entra na fatia 5
  - [x] fatia 5a — `cadastros`, os 5 modelos de cadastro básico (5 sites; 9 restantes).
        Dois deles falhariam **vazios**, não com erro: o termo genérico do evento e o
        `Prefetch` de servidores. `129` chamadas fora de teste, não 84 — meu grep usava
        `\.objects\.` e a forma dominante aqui é `filter_queryset_by_area(X.objects)`
  - [x] fatia 5b — `ConfiguracaoSistema` (2 sites; 8 restantes). `get_singleton` **não**
        precisou mudar: a consulta `area IS NULL` dele só é alcançada quando já não há
        área corrente, por retorno antecipado — a suposição do plano original estava
        errada. Quem precisou foi `get_for_area` e o lock de `proximo_numero`
  - [x] fatia 6 — `planos_trabalho`, `justificativas`, `integracoes`, `core.AuditEvent`
        (8 modelos, 8 sites; **catraca em 0**). Fecha o ID. `AuditEvent` ganhou teste dos
        dois lados: a leitura recorta, a escrita continua gravando
- [x] `BE-10` app `justificativas` sem isolamento — **já estava resolvido** pelo `NOVO-06` e pelo
      `NOVO-09`; a verificação de 06/08 conferiu os quatro pontos do enunciado um a um. A Fase 2
      tem 6 IDs, não 7.
- [x] `DB-01` `TabelaDiaria` sem `area` — o enunciado estava invertido: a tabela é nacional de
      propósito. O trabalho era o portão, e ele ficou em **superusuário** (decisão do usuário), no
      POST de diárias e não na view, que serve três abas. `require_area_role` segue com zero usos.
- [x] `DB-02` `area` anulável em 27 de 28 modelos — **enunciado reescrito em 07/08** com os
      três grupos do `NOVO-34` (operacional / catálogo com padrão global / global por projeto),
      `Evento.save()` derivando a área como os outros sete, e o **grupo operacional migrado no
      mesmo dia: `NOT NULL` nos 8 modelos do `core.E001`, em oito migrações
      `*_area_obrigatoria`.** A migração não precisa esperar produção: o gate do `NOVO-12` roda
      antes do `migrate` (protegido pelo rollback do `QA-03`) e aborta no `core.E001` enquanto
      houver órfão, então ela nunca encontra NULL — `backfill` primeiro, deploy de novo depois;
      `scripts/validar_not_null_db02.py` mede sem esperar um deploy (limite 4). O balde legado
      operacional ficou vazio **por construção**, escrita sem área falha alto, e o passo
      "`filter_queryset_by_area` sem área vira `none()`" caiu por desnecessário para o grupo 1.
      Grupos 2 e 3 seguem anuláveis **por desenho**; a decisão de produto do grupo 2 está no §8
      e no `NOVO-45`. A conversão da suíte rendeu `core/testing.py` (área e vínculo de teste,
      `com_request`) e fechou de carona um N+1 nas pendências do Drive. **Fecha a Fase 2.**
- [x] `DB-04` cache documental não recorta por área — latente, como o enunciado dizia, mas por
      outro motivo: quem separa as áreas é a **referência**, que era opcional. Agora é obrigatória
      (`ValueError` sem ela). A afirmação de que todo artefato nascia `area=NULL` **era falsa** —
      `DocumentoArtefato.save()` deriva a área; está corrigida no catálogo.
- [x] `DB-05` placa de viatura única globalmente — a metade de `ModeloJustificativa` já tinha
      saído no `NOVO-09`. A constraint sozinha não bastava: `ViaturaForm.clean_placa` consultava
      sem recorte e a mensagem de erro confirmava placa de outra unidade. Drill mostrou que a
      **volta da migração deixa de funcionar** depois que duas áreas usarem a mesma placa.

### Fase 3 — O banco defende os dados
- [x] `DB-06` cascata apaga comprovante e assinatura já coletados — `sair_da_equipe` marca
      (`removida_em`) quem tem dado coletado e apaga quem não tem; `_default_manager` esconde os
      marcados, então os ~15 pontos de leitura (inclusive `prefetch_related` por string) herdam o
      filtro. Readicionar o servidor à equipe restaura tudo. O achado adjacente saiu como `NOVO-35`,
      **também fechado**: excluir o servidor no cadastro passou a ser recusado quando apagaria
      comprovante, assinatura ou número de solicitação — com predicado próprio, mais estreito que o
      do `DB-06`, porque prender um cadastro pesa mais do que preservar uma linha.
- [x] `DB-07` 2 `CheckConstraint` em 54 modelos — viraram **26**: doze de ordem (o último veio com o
      `NOVO-36`) e doze de sinal, em
      oito modelos de seis apps, saídas de três fábricas em `core/constraints.py`. O levantamento
      por introspecção achou mais pares do que o enunciado (a cadeia de quatro datetimes do
      `Roteiro`, e o par do `RoteiroTrecho`). `scripts/validar_constraints_db07.py` é o
      procedimento do limite 4 do `AGENTS.md`: conta o que cada constraint reprovaria, antes do
      deploy.
- [x] `DB-08` coleções ordenadas aceitam duplicata — **5 de 5**. Fatia 1: `RoteiroDestino`,
      `PlanoDestino` (par parcial, porque `evento` é anulável) e `EventoPlano`. Fatia 2:
      `RoteiroTrecho` e `DiarioBordoTrecho`, que reordenam linha a linha e por isso levaram os
      dois escritores para **dois passos** (bloco livre, depois posições finais) e para dentro de
      `transaction.atomic` — nenhum dos dois abria transação. A medição de duplicata só vale em
      produção: quatro das cinco tabelas estão vazias no banco de desenvolvimento

### Fase 4 — Fundação do front
- [x] `JS-06` JS larga o nome de classe `cv-search-picker` — e as **partes** junto (`NOVO-19`):
      a superfície real era 45 sites em 11 arquivos, não 10 em 7. Contrato novo:
      `data-entity-picker-root`/`-part` + `CV.picker.rootFor/part`
- [x] `JS-05` auditor de CI cobre `innerHTML` e `registerEnhancer` sem `destroy` — 4 regras novas
      (6 → 10 invariantes), com `JS_EXCEPTIONS` de **teto por arquivo**: dentro do teto é exceção
      informativa, acima é erro. Achou `NOVO-14` e `NOVO-15`
- [x] `JS-02` `destroy` nos componentes que registram listener global — o número é **14 de 17**,
      não 15, e só 4 vazavam de fato. Um deles (`attach-signed-modal`) não estava no enunciado.
      Medido no navegador: 15→17→19→21 antes, 14→16→14 depois
- [x] `PF-01` folha de símbolos de ícone (192 KB por página de lista) — 06/08
- [x] `PF-04` menu de ação sob demanda (60 menus para 20 cards) — **os seis domínios**:
      Ofícios 315,3 → 166,5 KB, Eventos 416,3 → 211,9, Termos 317,6 → 147,9,
      Prestações 383,1 → 259,0, Planos 169,5 → 129,0, OS 166,8 → 126,7; `roteiros` não tem menu
- [x] `HT-02` erro de campo sem `aria-describedby`/`aria-invalid`/`role="alert"` — o Django 5.2 já
      emitia os dois atributos; faltava a **âncora**. 39 chamadores passaram a informar `field_id`,
      com varredura estática cobrindo o quadragésimo antes de ele existir
- [x] `HT-12` `help_text` declarado no form nunca chega à tela — 29 campos em 17 forms declaravam,
      **2 chamadores** de 154 passavam o parâmetro. Residual `use_fieldset` virou `NOVO-41`
- [x] `HT-03` sem padrão único para erro de formulário — eram **quatro** padrões e o componente
      certo tinha **zero** chamadores; agora são 20, e o resumo mostra a mensagem de verdade em
      vez de uma frase genérica. O painel de cadastro rápido não tinha padrão **nenhum**
- [x] `HT-05` `empty_state.html` quebra a ordem de headings — o pulo era **10 de 10** listas, não 9;
      o título vira `<h2>` e `form_block` ganha ramo `h2` (aditivo) para o cadastro rápido de
      justificativas. Sem parâmetro `heading_level`: a inversão mostrou o repasse inerte
- [x] `UI-01` poda das ~929 classes candidatas — **963 blocos, 170,7 KB** removidos; a unidade de PR
      virou a **família de classe**, não o arquivo, e a verificação virou `getComputedStyle` (0 de
      41.938 elementos) porque o diff de pixel tinha ruído maior que o efeito. Travado por
      `scripts/audit_css_morto.py --max 0` no CI. Resíduo declarado: `NOVO-48`
- [x] `HT-06` 10 a 14 componentes mortos, três deles citados como canônicos — **7 apagados**
      (um deles órfão em cascata, revelado pela própria trava) e **7 do UI Lab mantidos**, porque
      apagá-los é decidir qual dos dois labs é o vigente (`BE-17`). `form_errors` saiu da lista:
      o `HT-03` lhe deu 20 chamadores
- [x] `HT-13` `docs/DATA_ATTRIBUTES_JS.md` descreve um contrato que não existe mais — eram **7**
      atributos mortos, não 3, e a cobertura era de 19% (57 de 298). Rescrito a partir da
      medição e **travado nos dois sentidos** por teste, que é o que impede de apodrecer de novo

### Fase 5 — Consulta e índice ✅ **COMPLETA** (12/08/2026)
- [x] `DB-09` lista de roteiros agrega antes do `LIMIT` — `~Exists()` no lugar de
      `Count` + `.exclude(...=0)`, **junto** com o índice `(area, -updated_at)`: separados dão
      2,9× e 1,0×, juntos 8,9× na consulta e **1,54× na rota** (975,8 → 633,2 ms). O `LIMIT`
      não curto-circuita como o enunciado previa; quem sai é o `GroupAggregate`
- [x] `DB-10` índice composto para a ordenação real das listas — **um índice, não cinco**.
      Das cinco listas que ordenavam em memória, só `OrdemServico` ganha (64× na consulta,
      1,08× na rota); nas outras quatro o índice análogo não move o tempo e em `roteiros`
      piora. "Ofícios têm situação análoga" era falso, e o que sobra ali é o `NOVO-50`
- [x] `DB-11` busca livre de Termos multiplicava 20.000 linhas por três M2M e rodava três vezes —
      `Exists()` por origem + contagem das abas reutilizada pelo paginador. O `PF-07` agora mede
      `termos:index:busca` permanentemente: **1.807,9 → 391,4 ms (4,62×)** em 20.000 registros,
      com 6 queries. `pg_trgm` não entrou: a medição anterior deu 1,00× e provou que o gargalo era
      a forma da consulta, não a ausência de cinco índices
- [x] `DB-12` trilha de auditoria sem índice, sem expurgo — **só o índice**. O expurgo saiu
      por decisão do usuário (retenção de trilha de órgão público é pergunta de produto).
      O índice entrou como folga: medido, o planner só o escolhe por volta de 100 áreas,
      e produção não é observável daqui. A trilha não tem leitor fora do admin
- [x] `PF-03` toda requisição escreve na tabela de sessão — decisão tomada em 07/08:
      `cached_db` **mais** renovação periódica, que são uma coisa só (`cached_db` sozinho
      economiza 1 de 11; as outras 3 dependem de desligar `SESSION_SAVE_EVERY_REQUEST`).
      11 → 7 consultas em toda requisição autenticada, em todas as nove rotas medidas
- [x] `PF-06` queries duplicadas em `/usuarios/` e `/prestacoes-contas/` — o pior caso não
      estava no enunciado: **`roteiros:index` tinha 11 consultas a mais**, e foi de 29 para
      14. `/usuarios/` tinha 1, não 2, e foi corrigida. Sobram três de 1 consulta, com o
      mecanismo já identificado no catálogo

### Fase 6 — Camadas e duplicação
- [x] `BE-11` editor de roteiro em 3 cópias — **eram 2**: medida a interseção, `novo` × `editar` dá
      55 linhas idênticas (o enunciado dizia 41) e `wizard_roteiro` só 20 de 165. As duas primeiras
      foram unificadas atrás de `roteiros/services/editor_flow.py`; a terceira é outro fluxo e cai
      no `BE-12`. Sobrou `NOVO-87` (o ofício não detecta duplicado — decisão adiada, não esquecida)
- [x] `BE-12` `wizard_roteiro` com a regra dentro da view — a regra de vínculo/cópia virou
      `oficios/services.py::salvar_roteiro_do_oficio`, com `atomic`. 33 → 13 ramos, 165 → 124
      linhas úteis, cobertura de `route_views.py` de 69% para 88%. Fecha o `NOVO-88` e o item 1 da
      lista do `BE-14`. Sobrou `NOVO-92` (a tradução de ação do rodapé, copiada em cada passo)
- [x] `BE-13` `roteiro_logic.py` fora do contrato de camadas — **três fatias, três PRs**. F1
      (parsing): `request` no módulo caiu de 23 ocorrências para 1, os 6 objetos falsos e o parâmetro
      morto de `_validate_roteiro_state` sumiram. F2 (contexto + invólucros): a fachada do contexto
      migrou de service para presenter, e 15 invólucros morreram. F3 (persistência): o gravador
      atômico de 3 tabelas foi para `roteiros/services/editor_persistence.py` com nomes públicos, e o
      módulo virou `roteiros/services/editor_state_builder.py` — nome e lugar do que sobrou.
      **1.845 → 1.337 linhas (−27%), 57 → 33 defs.** Continua grande, mas com uma responsabilidade
      só. Sobrou `NOVO-98` (guardas defensivas do gravador, inalcançáveis pelo caminho público).
      **Fecha a corrente `BE-11`/`BE-12`/`BE-13`**
- [x] `BE-14` 48 sites de persistência em view, sem transação — **eram 36**, mais 4 por método de
      modelo que grava por dentro. **Fatia 1 (o dinheiro do RT) feita**: a persistência de
      `rt_views.py` virou `prestacoes_contas/rt_services.py`, o módulo caiu de 305 para 203 linhas
      com zero acessos de manager, e as gravações fora de transação foram de 36 para 33. Fecha
      `NOVO-101` (a catraca `P-01` media 24 com 35 no chão) e `NOVO-102` (gravação em laço escondida
      em `view_common.py`). **Fatia 2 (solicitação) feita**: as duas rotas foram para
      `solicitacao_services.py` com transação, `views.py` caiu de 743 para 674 linhas e as gravações
      fora de transação de 33 para 29. Sobrou `NOVO-103` (as duas rotas divergem em três pontos, e a
      divergência estava registrada com o ID de outro defeito — é decisão de produto). **Fatia 3
      (anexos) feita**: `atomic` na linha e `transaction.on_commit` no arquivo, porque ali `atomic`
      sozinho inverteria o órfão do `BE-07`. O defeito maior não era gravação parcial: era
      destruição — um `create` que falhasse levava o documento assinado anterior do disco e do
      banco. Gravações fora de transação: 29 → 24; catraca `P-01` desce de 33 para 31. Sobrou
      `NOVO-104` (arquivo órfão no storage não tem quem varra). **Fatia 4 (diário) feita**: os três
      caminhos de escrita de `diario_views.py` foram para `diario_services.py`, o módulo caiu de 388
      para 345 linhas com zero acessos de manager, gravações fora de transação 24 → 19 e catraca
      `P-01` 31 → 27. Sobrou `NOVO-107` (a fixture monta ofício sem roteiro e o teste de diário fica
      verde por omissão). **Prestações fecha aqui; o `BE-14` não.** A fatia 1 disse que 2, 3 e 4
      fechariam o defeito, e a frase valia para prestações — 21 dos 36 sites. **Restam 19**, em
      `planos_trabalho` (6), `oficios` (4), `eventos` (2), `prestacoes_contas/model_views.py` (3) e
      uma cada em `core`, `ordens_servico`, `roteiros` e `termos`. **Fatia 5: `planos_trabalho` +
      `oficios`**, que somam 10 dos 19 e incluem a pior função restante
      (`_apply_efetivo_snapshot`: `save` + `create` + `delete` em laço)

      `NOVO-104` (arquivo órfão no storage não tem quem varra). **Fatia 5 (planos + ofícios)
      feita**: `planos_trabalho` ganhou a primeira camada de escrita da sua história —
      `efetivo_services.py` e `identificacao_services.py`, 5 `atomic` onde antes havia **zero
      em 1.314 linhas** — e `criar_rascunho_de_roteiro_do_oficio` entrou em `oficios/services.py`
      ao lado do irmão do `BE-12`. Gravações fora de transação: 24 → 19 na fatia 4 e → 17 nesta.
      Sobrou `NOVO-108`: **a contagem por AST erra nos dois sentidos e não serve mais de alvo** —
      superconta 7 (cinco `delete()`, que o `Collector` do Django já faz em transação, e dois ramos
      mutuamente exclusivos) e subconta o pior caso restante, `eventos/views.py::detalhe`, que
      aparece com 1 e faz ~12 gravações em 6 tabelas. **Fatia 6: `eventos`**, dirigida por leitura
      de caminho e não pelo contador. **Fatia 6 feita**: a etapa 1 de `eventos::detalhe` virou
      `salvar_identificacao_evento`, um service atômico para Evento, M2M, destinos, cinco famílias de
      documento e termo automático. Falha no último passo desfaz todas as seis tabelas; 43 testes de
      Eventos verdes. O `P-01` permanece 27 porque o `NOVO-108` provou que esse caminho era invisível
      ao contador. Fecha `BE-14` e `NOVO-108`; a dívida unitária de posição em camada segue no `BE-16`
- [x] `BE-15` numeração reimplementada 3 vezes — **fatia 1 (a mecânica) feita**: o lock e o laço
      de retry, que eram ~60 linhas copiadas entre ofício e OS, viraram `core/numeracao.py`; a
      política de escolha de cada documento fica onde estava, porque diferente ali é desenho, não
      defeito. Apareceu um quarto site que o enunciado não citava (a edição de número manual), que
      passou a usar o lock **sem** o retry. Fecha `NOVO-109`: a detecção de colisão lia a mensagem
      do `IntegrityError` e **só funcionava no PostgreSQL** — em metade da suíte o retry era código
      morto, e o teste que o cobria fabricava a própria evidência. **Fatia 2**: OS reaproveita
      número liberado por exclusão (decisão do dono; único ponto que muda número emitido) — **feita**
      com `OrdemServicoNumeroLacuna`, exclusão atômica e consumo por área/ano; salto manual não vira
      lacuna e falha no registro desfaz a exclusão. 53 testes de OS verdes.
      **Fatia 3 feita**: `salvar_plano_numerado` preserva contador e sufixo do Plano, mas une avanço
      e `INSERT` na mesma transação e usa o retry comum. Colisão real repete; falha após reserva
      desfaz o contador; escolha+gravação compartilham o savepoint; a concorrência PostgreSQL agora
      mede duas linhas gravadas. 116 testes verdes
- [x] `BE-16` abstrações de `core` adotadas pela metade — **fatia 1 (paginação) feita**: os 15
      pontos usam `contexto_paginacao`, as 6 cópias de `_pagination_pages` foram removidas e não há
      `Paginator(...)` em produção fora do módulo comum. Termos mantém o total pré-agregado via
      `paginator_class`; chaves e filtros do contexto foram preservados. 922 testes consumidores
      verdes. **Fatia 2 (exclusão protegida) feita**: catálogos e serviços de exclusão de entidades
      acionados pelo usuário adotam `core.deletion`; `PROTECT` vira erro de domínio/mensagem e não
      500. Remoções internas de filhos, arquivos, cache, sessão e rascunhos ficam fora por contrato.
      A regressão de OS prova que bloqueio não cria lacuna; 299 testes consumidores verdes.
      **Fatia 3 (retorno) feita**: as duas cópias sobreviventes — catálogo e upload assinado de
      Prestações — delegam a `core.retorno`; leitura de `next` e validação de host têm um único dono.
      Fallback, fragmento de modal e recusa de host externo estão cobertos por 93 testes. BE-16
      fechado
- [x] `BE-17` `core/views.py` é 75% fixture de UI Lab — **fechado pelo PR #247**, que apagou os
      dois labs e as 1.013 linhas de fixture; a cascata de componentes que ele deixou é o
      `NOVO-44`

### Fase 7 — Reconstrução do front (CSS, HTML e JavaScript)

**Dimensionada em 09/08/2026 no [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md)**,
que é o documento a seguir para esta fase: doze etapas (E0–E11), cada uma com arquivos, comando de
verificação e catraca. O escopo cresceu em relação ao que este quadro previa, por três decisões do
dono: **componentização por `django-cotton`**, **desenho único entre os temas claro e escuro** e
**runner de teste de JavaScript no CI**.

O quadro abaixo é por ID; a ordem de execução é a das etapas, não a desta lista.

- [x] `NOVO-75` 🔴 `dev.txt` não puxa `test.txt` — o `--parallel 4` aborta em toda sessão remota · **E0**
- [x] `NOVO-70` a métrica de aceite do `PF-02` não tem instrumento; corpus de rotas com 14 telas mortas · **E0**
- [x] `NOVO-76` `audit_ui_patterns.py` está no ciclo obrigatório do `AGENTS.md` §4 e sai 1 sempre · **E0**
- [x] `NOVO-77` corpus antigo mantinha duas telas mortas além do UI Lab · **E0**
- [x] `NOVO-78` fixture demo não acompanhou área obrigatória e seis modelos novos · **E0**
- [x] `NOVO-79` duas rotas canônicas resolviam, mas respondiam 500 · **E0**
- [x] `JS-03` runner de teste de JavaScript — deixou de ser aditivo, virou pré-requisito · **E1**
- [x] `NOVO-69` `cv-select.js` (343 linhas) morto desde o PR #247, ainda no bundle · **E2**
- [x] `NOVO-72` `ui_lab2/` sobreviveu ao PR #247 · **E2**
- [x] `NOVO-73` nome e lugar de arquivo JS sem padrão · **E2**
- [x] `NOVO-48` 70 nomes de classe morta dentro de seletor agrupado vivo · **E2**
- [x] `NOVO-71` componente global sem contrato de parâmetro → `django-cotton` · **E3–E5**
- [x] `HT-14` 275 de 946 includes não usam `only` — contratos e `only` obrigatórios · **E5**
- [x] `NOVO-74` dois namespaces de componente, quatro pastas fantasma de `.gitkeep` · **E5**
- [x] `HT-08` 82 `<button>` fora do sistema de componentes · **E6**
- [x] `HT-15` bloco `cv-itinerary` duplicado em 5 apps · **E6**
- [x] `NOVO-16` markup do picker copiado à mão em 3 templates e 5 arquivos JS · **E6**
- [x] `HT-10` `data-*` de toggle legado em componente compartilhado · **E6**
- [x] `HT-07` concatenação condicional com "·" no template · **E6**
- [x] `NOVO-80` a E5 apagou duas travas de regressão em vez de reapontá-las · **E6**
- [x] `NOVO-81` o auditor de front audita os `*.test.js` que a E1 criou · **E6**
- [x] `NOVO-99` os três `include ... only` do editor passam o token CSRF explicitamente · **correção imediata**
- [x] `UI-03` nove (medidos: oito) arquivos definem token de cor → duas camadas · **E7a**
- [x] `NOVO-82` 87 declarações escuras inertes, visíveis desde a fusão do `theme.css` · **E9**
- [x] `NOVO-114` a régua de mesmo tema citada pela E9 não estava versionada; sonda reproduzível,
      contexto público/autenticado correto e contrato automatizado · **E9**
- [x] `NOVO-119` separa 354 regras compartilhadas da camada escura; o arquivo transitório cai de
      5.555 para 2.434 linhas e de 184 para 98 `!important`, com cascata estável · **E9**
- [x] `NOVO-51` os 2 apelidos puros da família `cv-field` (e 15 bordas invisíveis) · **E7b**
- [x] `NOVO-51` os 2 de valor próprio foram fechados em 11/08 após a decisão por anel visível no
      escuro: zero definições `--cv-field-*` vivas no CSS de fonte; a reauditoria de 12/08 encontra
      somente comentários históricos nos bundles/folhas · **E7b**
- [x] `NOVO-54` 72 regras (30 `!important` e 7 regras já fora); as 7 candidatas de estado não-base
      também fecharam por medição (2 blocos removidos e 5 grupos de seletor simplificados). A regra
      base agora vence o seletor de elemento cru com neutralidade medida; as 8 pseudo-regras e 1
      contexto órfão caíram; diário, quick-add e `field-with-action` fecharam no corpus ampliado · **E7c**
- [x] `NOVO-58` claro e escuro têm desenho único: 54.225 elementos, 129 medições, 0 divergências não-cor · **E8**
- [x] `UI-02` camada escura reconciliada: regras compartilhadas saíram; restam somente seletores
      predicados por tema, sob catraca (5.619 → 2.434 linhas; 190 → 98 `!important`) · **E9**
- [x] `UI-04` fronteiras CSS fechadas no escopo medido: 97 imports históricos → **82 atuais** em
      37 templates; três folhas sem regra casada saíram na reauditoria final (`NOVO-120`) · **E10**
- [x] `HT-04` entrega fechada: shell JS 266.254 → 108.937 bytes e componentes CSS pesados sob
      demanda; a reauditoria final separa a eficiência do bundle da fronteira de domínio · **E11/E10**
- [x] `JS-07` 3 implementações vivas de "fechar ao clicar fora / Esc" → `CV.overlay.attachDismiss` · **E11**
- [x] `JS-08` cinco componentes sob demanda por marcador DOM; shell 283.128 → 266.254 bytes · **E11**
- [x] `JS-09` tela embutida entrega só `http.js` + polling: 283.282 → 4.255 bytes de JS · **E11**
- [x] `JS-10` três stubs sem consumidor removidos; módulos reais e bootstrap preservados · **E11**

**Fechados nesta fase antes do dimensionamento** (a reconstrução parcial de 07–08/08, que o quadro
não registrava): `NOVO-50/MED` paleta de 255 cores duplicadas · `NOVO-51` poda dos 55 apelidos
puros de token · `NOVO-52` foco no editor de roteiro · `NOVO-53`/`NOVO-55`/`NOVO-56`/`NOVO-57`
máscara de maiúscula · `NOVO-59` ícone de botão invisível no tema claro · `NOVO-60` levantamento da
renomeação por função · `NOVO-61` dez nomes mortos em seletor agrupado · `NOVO-62` `Inter`
empacotada e válida nos dois temas · `NOVO-63` geometria da barra lateral globalizada ·
`NOVO-64` 176 tokens sem prefixo · `NOVO-65` 545 classes sem prefixo.

### Fase 8 — Observabilidade e autorização
- [x] `BE-18` handlers genéricos mudos 73 → 0; exceções esperadas tipadas, falhas inesperadas
      observadas e catraca AST permanente no CI
- [x] `BE-19` decisão de autorização registrada; helper e contexto sem consumidor removidos sem
      inventar operação exclusiva de ADMIN
- [x] `QA-16` Sentry opcional integrado ao Django e a `capture()`, sem PII/tracing e com falha segura
- [x] `QA-10` causa fechada por `QA-02`: Redis obrigatório em produção compartilha os contadores
      entre workers; margem concreta do Drive segue em `QA-05`
- [x] `QA-05` cliente real do Google Drive coberto por 12 testes de contrato na fronteira da API
- [x] `QA-14` CRUD de modelos do Relatório Técnico — já fechado por 7 testes em `993e14c5`;
      status reconciliado
- [x] `QA-15` oito provas dos erros de download, WeasyPrint, storage e fila; 22 testes do conjunto
      de geração/conversão verdes
- [x] `QA-13` indicador reconciliado como sinal de triagem, não meta de tamanho de teste

### Fase 9 — Finalização e higiene
- [x] `BE-20` `diario_bordo` é app-casca — **removido**: 33 linhas, rota inalcançável, sem
      migration nem tabela. A funcionalidade real, em `prestacoes_contas`, ficou intacta
- [x] `BE-21` presenter morto prometendo "DOCX (em breve)" — **removido**; a varredura por AST
      achou **dois** presenters mortos no módulo, não um
- [x] `BE-22` 10 arquivos `.py` com BOM — **fechado**: eram 11 (10 `.py` + um `.md`), e o
      `cadastros/views.py` era o único que obrigava o gate do `S-06` a ler com `utf-8-sig`
- [x] `BE-23` vocabulário de rotas — 28 sufixos CRUD padronizados e protegidos por catraca;
      operações de domínio permanecem descritivas por decisão explícita
- [x] `BE-24` artefatos locais removidos após extrair o corpus — **135 arquivos / 43,18 MiB**;
      `.gitignore` impede a reentrada
- [x] `BE-25` decidir qual UI Lab é o vigente — **decidido e executado no PR #247: nenhum dos
      dois.** A cascata (7 componentes órfãos + 1 de segunda ordem, `main` vermelho em 8 testes)
      ficou para trás e foi fechada como `NOVO-44`
- [x] `NOVO-44` o `BE-25` apagou os labs e deixou a cascata do `HT-06` para trás — 8 componentes
      apagados com prova de grep, `SO_NO_LABORATORIO` vazia com a trava intacta, piso 85 → 83
- [x] `QA-08` dependências atrasadas — `pyhanko` morto removido; `docxtpl` 0.20.2, WeasyPrint 69,
      ReportLab 5 e Redis 8.1 atualizados em fatias isoladas com locks reproduzíveis
- [x] `NOVO-118` `docxcompose` declarado diretamente após o upgrade expor a transitividade oculta
- [x] `NOVO-01` contrato de assinatura reescrito para os fluxos reais, sem backend pyHanko fictício
- [x] `NOVO-02` suíte trava ao combinar certos grupos de apps — **não reproduziu** em 06/08 (a
      combinação do catálogo passa, inclusive em `--reverse`). A sondagem achou o `NOVO-26`
      (mapa de capitais memorizado no processo decidindo diária com base velha, **fechado**)
- [x] `NOVO-27` regressão do `NOVO-26`: uma consulta de capitais por card na lista de
      roteiros (teto do `PF-07` 32 → 47). Corrigida; teto sobe a 33 de propósito
- [x] `NOVO-115` resíduo do PR #58: documentos vinculáveis acompanham o período ainda não salvo e
      o picker recupera a ação de limpar, sobre os componentes atuais
- [x] `NOVO-117` resíduo do PR #4: marcador de combustível `CB` → `CT` reaplicado no renderer atual
- [x] `QA-17` triagem dos PRs abertos — eram 17: 12 fechados, 3 upgrades de Actions mesclados e
      2 intenções reaplicadas com `NOVO-115`/`NOVO-117`; fila antiga zerada
=======
# Plano mestre do refactor — ciclo de agosto/2026

**Este é o único documento que responde "o que eu faço agora".** Os planos por frente detalham
o como; o catálogo lista os defeitos; este aqui manda na ordem.

| Documento | Papel |
|---|---|
| [`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md) | Todo defeito vigente, com ID, evidência medida e status |
| [`PLANO_BACKEND.md`](PLANO_BACKEND.md) | Camadas, isolamento por área, integridade, consulta (`BE`, `DB`) |
| [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md) | CSS, templates, JS, acessibilidade (`UI`, `HT`, `JS`) |
| [`PLANO_DESEMPENHO.md`](PLANO_DESEMPENHO.md) | Régua e otimizações de entrega (`PF`) |
| [`../AGENTS.md`](../AGENTS.md) | Regras de conduta, limites invioláveis, corpo de PR |
| `historico/2026-07-refactor/` | O ciclo anterior, congelado |

---

## 1. Por que um ciclo novo

O ciclo de julho fechou. Das oito etapas, sete foram concluídas e a oitava ficou pela metade —
92 itens fechados, 6 pendentes. Ele fez o que se propôs: a suíte foi de 812 para **1.301 testes
verdes**, o auditor de front caiu de 465 para **392 avisos**, o motor de diárias passou a bater
ao centavo com os demonstrativos oficiais, e as listas deixaram de ter N+1.

> **Ciclo de agosto encerrado em 13/08/2026.** Todos os **224 cabeçalhos de defeito ou fatia** do
> catálogo têm desfecho marcado, as dez fases abaixo não possuem item pendente e as duas métricas
> transversais de aceite foram cumpridas: `PF-02` em **37,5118%–60,3148%** de CSS usado por rota e
> `PF-05` em **33,2 ms / 7 consultas** no regime quente canônico.

Continuar marcando linha naquele plano seria errado por um motivo simples: **os enunciados
venceram**. O próprio plano registra três correções de rumo (`J-05`, `J-11`, tokens indefinidos)
em que o defeito descrito não era o defeito existente. Depois de ~120 PRs, citar `D-14` é citar
um retrato de julho, não o sistema de hoje.

Este ciclo começa com medição nova. Tudo aqui foi medido em **05/08/2026**, por execução.

## 2. Linha de base medida

> **Esta tabela é de 05/08 e envelheceu — vale o §7.4 deste próprio documento.** Remedida em
> 09/08: a suíte está em **1.824 testes, 7 skips, 14,7 s** (não 1.306 em 9,9 s), o auditor de front
> em **240 avisos com teto 246** (não 392 com teto 401), o CSS de fonte em **32.940 linhas** (não
> 43.038) e o JS em **18.382** (não 17.859). A linha de base vigente do front, com o comando de
> cada número ao lado, está no §2 do
> [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md).

| medida | valor | como |
|---|---|---|
| Suíte | **1.306 testes**, 0 falhas, 4 skips, **9,9 s** | `manage.py test --settings=config.settings.test --parallel 4` |
| Auditor de front | **392 avisos**, 0 erros (teto do CI: 401) | `scripts/audit_frontend_standards.py` |
| ORM em módulo de view | **30** (google_drive 10, core 9, documentos 4, oficios 4, roteiros 2, justificativas 1) | `scripts/audit_django_architecture.py` |
| Classe CSS dentro de `attrs={}` em forms | **0** | grep em todos os `forms.py` |
| Código (fonte) | 93.232 linhas Python · **43.038 CSS** · **17.859 JS** · 462 templates | `wc -l`, excluindo `shell.bundle.*` |
| Código (entregue) | `shell.bundle.css` 17.669 linhas · `shell.bundle.js` 7.633 | concatenação das fontes acima — **não somar aos dois** |
| Modelos e migrações | 54 modelos, 154 migrações, **0 pendentes**, 0 irreversíveis | `makemigrations --check --dry-run` |
| Constraints | 61 `UniqueConstraint` · **2** `CheckConstraint` | introspecção de `_meta.constraints` |
| Índices | 390 em 75 tabelas · **0 GIN, 0 trigram** | `pg_indexes` |
| Isolamento por área | 28 de 54 modelos têm `area`; **27 com `area` anulável**; 123 `.objects.` fora do filtro | introspecção + varredura AST |
| Classes CSS declaradas | **2.612**, das quais **~929** sem uso comprovado | extração + grep em corpus de 4,7 MB, descontando 3 padrões de classe dinâmica |
| CSS entregue por página | 664–816 KB, **~10% casado** | Chromium via CDP |
| HTML da lista de Ofícios | **425 KB** para 20 cards, 192 KB só em SVG inline | `test.Client` + contagem |

## 3. As quatro frentes

**Backend** (`BE`, `DB`) — 63,5 dias. O risco está aqui: isolamento por área é convenção, o banco
não impõe integridade, e há defeitos que o usuário encontra hoje.

**Frontend** (`UI`, `HT`, `JS`) — ver [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md). O peso está aqui:
~36% do CSS sem uso comprovado, tema escuro resolvido por 5.843 linhas de exceção com 190
`!important`, e CSS de domínio alheio importado em 26 templates.

**Desempenho** (`PF`) — 9 a 13 dias próprios. O trabalho aqui é **medir** e cortar o que a
medição apontar; boa parte da otimização real mora nas outras duas frentes, e este plano
fornece a régua que prova o ganho.

**Finalização** — o que falta terminar, não refatorar: `diario_bordo` é um app-casca de 33
linhas com rota não linkada, há presenter morto prometendo "DOCX (em breve)", 13 PRs abertos
sem triagem, dois UI Labs concorrentes sem regra de qual é o vigente, e a arquitetura de
configurações segue como proposta sem posição na fila.

## 4. A fila

| Fase | O que | Frente | Dias | Risco | Por que aqui |
|---|---|---|---:|---|---|
| **0** | **Defeitos que atingem o usuário agora** | `BE-01`…`BE-08`, `JS-01`, `JS-04`, `HT-01`, `HT-09`, `HT-11`, `JS-11`, `JS-12`, `QA-01`, `QA-02`, `QA-04`, `QA-09` | 10 | baixo | Correções isoladas, nenhuma depende de renomear ou mover nada. Se o calendário virar, para-se aqui e o sistema já está melhor. Inclui o wizard de plano de trabalho que não finaliza, a exclusão de anexo por `GET`, um XSS reproduzido no navegador, o foco de teclado invisível em todo campo, campos sem nome acessível, o admin sem rate limit, e a validação central de upload que **nunca roda** nos 5 tipos de anexo de prestação. |
| **1** | **Réguas e rede de segurança** | `PF-07`, `QA-03`, `QA-06`, `QA-07`, `QA-11`, `QA-12` | 7 | médio | `scripts/medir_desempenho.py` no CI com volume realista, `ruff`, Dependabot, o rollback de deploy que hoje não desfaz migração, e o teste da CVE do WeasyPrint que hoje verifica texto-fonte. Sem régua, toda fase seguinte é afirmação sem prova e a regressão volta no PR seguinte sem ninguém ver. |
| **2** | **Isolamento por área vira invariante** | `BE-09`, `BE-10`, `DB-01`…`DB-05` | 18 | **alto** | Quatro vazamentos entre tenants já provados por teste. É o maior risco do sistema e toda fase posterior escreve código que precisa respeitar o recorte. |
| **3** | **O banco defende os dados** | `DB-06`…`DB-08` | 8 | médio | Cascata que apaga comprovante e assinatura; 2 `CheckConstraint` em 54 modelos. Depende da fase 2: pôr `NOT NULL` sobre modelo que ainda vaza é lacrar a porta errada. |
| **4** | **Fundação do front** | `PF-01`, `HT`, `UI` (CSS morto) | ver plano de front | médio | Folha de símbolos de ícone, componentes e remoção do CSS comprovadamente morto. Fixa **quais classes existem** — pré-requisito da reconstrução. **Concluída** nas três fatias, com os resíduos posteriores registrados e fechados por ID. |
| **5** | **Consulta e índice** | `DB-09`…`DB-12` | 8,5 | médio | Ganho medido de 13× a 29× num índice composto; busca livre em varredura sequencial. Depois da fase 3, porque constraint muda plano de consulta. |
| **6** | **Camadas e duplicação** | `BE-11`…`BE-17` | 17,5 | alto | Editor de roteiro em 3 cópias, `roteiro_logic.py` com 1.779 linhas fora do contrato. Mexe em roteiro e diárias: **plan mode obrigatório**. |
| **7** | **Reconstrução do front** — CSS, HTML e JS. Dimensionada em 09/08 no [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md): doze etapas | `UI`, `HT`, `JS` | ver o documento | médio, com a E8 em **alto** | A mais visível e a mais reversível. Depois da fase 4, que define os nomes. Escopo ampliado por decisão do dono: componentização por `django-cotton`, desenho único entre os temas e teste de JS no CI |
| **8** | **Observabilidade e autorização** | `BE-18`, `BE-19` | 4 | médio | `capture()` só existe num app; `PAPEL_ADMIN` é decorativo. |
| **9** | **Finalização e higiene** | `BE-20`…`BE-25` | 4 | baixo | Fecha a conta: app-casca, código morto, repositório, PRs abertos, vocabulário de rotas. |

### Paralelismo permitido

```
Fase 0 ──► Fase 1 ──┬──► Fase 2 ──► Fase 3 ──► Fase 5
                    │
                    └──► Fase 4 ──► Fase 7
                                    Fase 6 (backend, camadas)
Fase 9 — a qualquer momento, em branch própria
```

- **Backend e frontend correm em paralelo** — são superfícies disjuntas.
- **Fases 4 e 7 nunca correm juntas**: o HTML define o nome, o CSS pinta o nome.
- **`BE-11`, `BE-12` e `BE-13` nunca em paralelo entre si**: são a mesma superfície.
- **Duas frentes nunca na mesma camada ao mesmo tempo.**

### O corte mínimo, se o prazo apertar

**Fases 0 + 1 + 2.** São 35 dias e eliminam as duas respostas indefensáveis:

| Pergunta | Antes | Depois |
|---|---|---|
| "O sistema separa os dados de cada unidade?" | quatro vazamentos provados; o recorte depende de o programador lembrar | invariante no manager, com teste de duas áreas por modelo |
| "O plano de trabalho finaliza?" | o botão recarrega a página em silêncio | finaliza, com teste de regressão |

## 5. Gates

Nenhum PR entra sem os quatro:

1. **Suíte verde** em PostgreSQL, com o número de testes e o tempo no corpo do PR. Reduziu o
   número de testes verdes ou aumentou o tempo em mais de 20%? Justifique.
2. **Catracas só descem.** `audit_frontend_standards.py --max-warnings 401` (medido hoje: 392),
   `audit_django_architecture.py`, `audit_ui_patterns.py`, pisos de `.github/coverage-floors.json`.
3. **Régua de desempenho** (a partir da fase 1): a rota tocada não pode passar do teto declarado
   em queries, tempo, KB de HTML e uso de CSS.
4. **Evidência do defeito.** Todo ID fechado precisa de um teste que falharia antes.

## 6. Ciclo de trabalho

Vale o do [`AGENTS.md`](../AGENTS.md) §4, com dois acréscimos deste ciclo:

- **Uma fase por PR, um dono por PR.** Correção de defeito e renomeação nunca viajam juntas.
- **Toda fase de risco médio ou alto começa em plan mode**, com o plano escrito no PR antes da
  primeira linha de código.

## 7. Os erros que matam este ciclo

1. **Começar pelo CSS.** É a fase 7, não a 1. Ele renomeia classes das quais o JS depende e
   estiliza componentes que a fase 4 ainda vai criar.
2. **Tratar o isolamento por área como detalhe.** É a fase 2 porque é o único defeito cujo
   sintoma é dado de um órgão aparecendo para outro.
3. **Otimizar antes de medir.** A medição desta sessão já derrubou duas suspeitas clássicas: não
   há N+1 nas listas e não há geração documental síncrona. Quem "otimizar" isso trabalha de graça.
4. **Confiar em número velho.** Este documento tem data. Se estiver lendo daqui a três meses,
   meça de novo antes de citar.
5. **Afrouxar catraca para o PR passar.** O número só desce.
6. **Deixar o escopo novo entrar no meio de uma fase.** Vai para o catálogo com `NOVO` e recebe
   posição na fila.

## 8. Decisões registradas

Registro histórico das decisões. Todas as que pertenciam às dez fases foram respondidas; a
arquitetura de configurações permaneceu deliberadamente fora deste ciclo.

| Decisão | Onde entra | Por que precisa de você |
|---|---|---|
| ~~Comportamento de expiração de sessão~~ **decidida em 07/08: `cached_db` + renovação periódica** | `PF-03` (fase 1) | Janela deslizante de 7–8 h sem escrita em toda requisição; fechamento do navegador preservado |
| ~~Quais operações exigem `PAPEL_ADMIN`~~ **decidida em 12/08: nenhuma operação existente é elevada arbitrariamente** | `BE-19` (fase 8) | Administração global já exige `is_staff`; operações da área pertencem a EDITOR; helper morto removido |
| ~~Qual UI Lab é o vigente~~ **decidida em 07/08 (PR #247): nenhum — os dois saíram** | `BE-25` (fase 9) | A cascata de componentes órfãos que a decisão deixou é o `NOVO-44`, fechado |
| Arquitetura de configurações | fora das 9 fases | Proposta de 17–28 dias, em `historico/2026-07-refactor/planos/PROPOSTA_CONFIGURACOES.md`; entra como fase própria ou fica fora do ciclo |
| ~~Triagem dos PRs abertos~~ **concluída pelo `QA-17`** | fase 9 | Eram 17: 12 fechados, 3 upgrades mesclados e 2 intenções reaplicadas como `NOVO-115`/`NOVO-117` |
| ~~Catálogo global do `DB-02` (grupo 2)~~ **decidida em 07/08: cópia por área, seguindo o `NOVO-09`** | `DB-02` (fase 2) | Executada nas migrações `eventos/0016` e `planos_trabalho/0024`. As linhas de seed eram vistas por **zero** usuários com área. O resíduo de instalação/área nova foi fechado pelo `NOVO-49`: fonte canônica, seed transacional e `NOT NULL` nas migrações `usuarios/0002`, `eventos/0017` e `planos_trabalho/0025`. |

## 9. Quadro de acompanhamento

Marque aqui, no mesmo PR que faz o trabalho. `[ ]` pendente · `[~]` em andamento · `[x]` pronto.
O detalhe de cada ID está no [`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md).

**O quadro original acompanha 93 IDs; o catálogo cresceu durante a execução e hoje contém 224
cabeçalhos de defeito ou fatia, todos com desfecho marcado.** Os dois itens transversais são
**métricas de aceite** de outros IDs, não trabalho próprio: `PF-02` mede uso de CSS por rota (**cumprido: 37,5118%–60,3148%**) e
`PF-05`, tempo da lista de Ofícios (**cumprido: 33,2 ms e 7 consultas**). O `DB-13`, antes adiado
pelo risco monetário, entrou depois do `DB-01`: composição
estruturada e auditável sem mudar nem recalcular a regra de dinheiro.

### Fase 0 — Defeitos que atingem o usuário agora ✅ **COMPLETA** (06/08/2026)
- [x] `BE-01` wizard de plano de trabalho não finaliza e "Voltar" avança
- [x] `BE-02` exclusão de anexo por `GET`, sem CSRF
- [x] `JS-01` XSS: nome de pasta do Drive cru em `aria-label`
- [x] `HT-01` foco de teclado invisível em todo campo, inclusive no login
- [x] `BE-04` formulário de evento oferece documentos de outras áreas
- [x] `BE-03` filtro de data da lista de ofícios descartado em silêncio
- [x] `BE-05` seletor de modelo de motivo da OS expõe outras áreas
- [x] `BE-06` relatório técnico sai com a cidade-sede de outra área
- [x] `BE-07` exclusão de anexo dá 500 e deixa registro órfão
- [x] `BE-08` oito redirects seguem o que o POST mandar
- [x] `JS-04` `.then()` sem `.catch` no editor de roteiros — a fila de estimativa morria inteira
      no primeiro erro, não só o trecho que falhou. Achou `NOVO-22` (`applyingState` travado,
      **fechado junto**), `NOVO-23` (remoção de assinado que mentia, **fechado** no PR #208) e
      `NOVO-24` (`.then` solto na criação de pasta do Drive, **fechado**). Os três achados do
      inventário estão resolvidos.
- [x] `HT-09` login sem skip link e sem erro associado
- [x] `HT-11` campos de formulário renderizados sem nome acessível (5 medidos em 2 telas)
- [x] `QA-01` login do Django Admin sem rate limit nenhum
- [x] `QA-02` rate limit depende de um Redis que nenhum ambiente declara
- [x] `QA-04` 🔴 a validação central de upload nunca roda, nos 5 tipos de anexo
- [x] `QA-09` dois templates de `.env` de produção divergentes
- [x] `JS-11` `maskCep` duplicada e `onlyDigits` em 4 cópias — a causa era falta de saída pública
      em `masks.js`, não desleixo; duas regras novas no auditor impedem a volta
- [x] `JS-12` `CV.componentRegistry` era alias **sem nenhum consumidor** — o enunciado "mesmo
      objeto" já tinha sido refutado em runtime; o defeito real era código morto

### Fase 1 — Réguas e rede de segurança ✅ **COMPLETA** (07/08/2026)
- [x] `PF-07` `scripts/medir_desempenho.py` com dois volumes, no CI — achou `NOVO-06`
      (vazamento entre áreas, **fechado**), `NOVO-07` (15 MB de HTML, **fechado**) e `NOVO-08`
      (N+1 de 296, 138 e 55, **fechado**: 34, 20 e 11). Os três saíram da régua; nenhum aparecia
      na linha de base, que mediu com o banco vazio.
- [x] `NOVO-07` seletor de ofício sob demanda nas três telas — `justificativas:index` de
      **5.398 KB para 142,5 KB** com 20.000 ofícios, e a diferença entre os dois volumes caiu de
      27× para 0,3%: a página parou de crescer com a tabela. Tetos da régua baixados.
- [x] `NOVO-10` 🔴 entrar com a senha certa devolvia 500 — `LoginView.form_valid` chamava
      `self._rate_key()`, método que o `QA-01` levou embora. Achado dirigindo o navegador para
      conferir o `NOVO-07`, não por auditor. **Caminho de sucesso sem teste é caminho não
      coberto:** havia teste para errar a senha seis vezes e nenhum para acertar uma.
- [x] `QA-03` rollback de deploy não desfaz migração — `scripts/deploy_rollback.sh` + drill no CI.
      Não restaura backup de propósito: para e instrui. **Fecha a Fase 1.**
- [x] `QA-06` teste da CVE do WeasyPrint verifica texto-fonte, não comportamento
- [x] `QA-07` sem lint/formatação/tipo em Python no CI — **lint fechado** (`ruff` em zero,
      gate em `tests.yml`). Formatação, famílias adicionais e tipo foram dimensionados no
      `NOVO-05` (571 arquivos fora do formato; 3.782 erros de tipo), sem fingir que uma ativação
      global seria correção atômica. A folga zero do
      `--max-orm-em-view 30` continua de pé: qualquer ORM novo em view reprova o CI.
- [x] `NOVO-11` o auditor de ORM em view conta `.objects` dentro de docstring — a contagem agora
      é por `ast` (`contar_orm_no_codigo`), com teste que falharia antes. A troca não mudou o
      número: 29 por regex e 29 por árvore, mesmos apps — a folga que "ninguém sabia medir" era
      zero, e a catraca segue em 29.
- [x] `NOVO-12` 🔴 nenhuma régua olha a configuração de produção — `check --deploy --fail-level
      ERROR` no `deploy.yml`, após o checkout (os checks têm de ser os do código que entra no
      ar; antes dele, o E002 antigo travaria o próprio deploy da correção), antes do
      `collectstatic` e protegido pelo rollback do `QA-03`. O
      `core.E002` foi decidido: **rebaixado a `core.W002`** (produção roda `auto`; check
      insatisfazível não é catraca, é ruído — o SLA real segue medido no CI com unoserver de
      verdade). E a ponta que o enunciado não via: `SECRET_KEY` fraca é `security.W009`,
      **Warning**, que `--fail-level ERROR` não trava — `core.E003` promove os critérios a
      `Error`, senão o gate não pegaria o próprio defeito que o motivou. `ALLOWED_HOSTS` vazia
      passou a falhar cedo no `prod.py`, padrão `REDIS_URL`. **Fecha a Fase 1 inteira.**
- [x] `QA-11` `reparar-producao.yml` em UTF-16LE
- [x] `QA-12` Dependabot semanal (`pip` + Actions), CodeQL para Python/JavaScript e axe-core no
      corpus real: 43 rotas × 2 temas; baseline por alvo impede dívida nova e só pode descer
- [x] `NOVO-43` SLA documental depois da suíte, log como artefato e mediana quente com teto por
      modelo (`docx=250 ms`, `xlsx=750 ms`); pico isolado não apaga os gates funcionais

### Fase 2 — Isolamento por área ✅ **COMPLETA** (13/08/2026)
- [x] `DB-03` limpeza de rascunhos apaga rascunho de outra área — e mais: sem limite de idade, ela
      apagava o rascunho que outra pessoa da **mesma** área estava editando, porque `Roteiro` não
      tem dono. Registrado como `NOVO-13` e corrigido junto (mesmas três linhas de `filter`).
- [x] `BE-09` `AreaScopedManager` nos 28 modelos com `area` — **fechado; catraca em **zero**, em 6 fatias, medida por
      `scripts/audit_area_scoped_managers.py`.** Duas decisões fixaram o desenho: (1) fora de
      request `objects` **não** recorta — a alternativa faria toda tarefa Celery virar no-op
      silencioso (`NOVO-20`); (2) `_default_manager` fica no manager irrestrito, para não
      neutralizar o guarda m2m, o `core.E001` e os comandos de backfill — o preço é o `NOVO-21`.
  - [x] fatia 1 — mecanismo, catraca, testes de contrato, `termos` e `ordens_servico` (26 restantes)
  - [x] fatia 2 — `oficios` (4 modelos, 11 sites de `all_objects`; 22 restantes). Duas
        descobertas: o modelo histórico de migração **perde** o `objects` a partir do
        `AlterModelManagers` do app (`core/managers.py` documenta a regra), e a suíte
        desligava o piso de numeração — `NOVO-28`
  - [x] fatia 3 — `roteiros` + `eventos` (4 modelos, 6 sites de `all_objects`; 18
        restantes). Fechou **três vazamentos reais** que não estavam no catálogo
        (`NOVO-30`) e mostrou que renomear para `all_objects` desinflava a catraca de
        ORM-em-view — o auditor passou a contar os dois nomes
  - [x] fatia 4 — `prestacoes_contas` + `documentos` (4 modelos, 4 sites; 14 restantes).
        Encostou no caminho **assíncrono**: `_objeto_do_job` é genérico sobre cinco
        modelos de apps migrados em fatias diferentes, e lá a forma certa é
        `_base_manager`, não `all_objects` — `Servidor` só entra na fatia 5
  - [x] fatia 5a — `cadastros`, os 5 modelos de cadastro básico (5 sites; 9 restantes).
        Dois deles falhariam **vazios**, não com erro: o termo genérico do evento e o
        `Prefetch` de servidores. `129` chamadas fora de teste, não 84 — meu grep usava
        `\.objects\.` e a forma dominante aqui é `filter_queryset_by_area(X.objects)`
  - [x] fatia 5b — `ConfiguracaoSistema` (2 sites; 8 restantes). `get_singleton` **não**
        precisou mudar: a consulta `area IS NULL` dele só é alcançada quando já não há
        área corrente, por retorno antecipado — a suposição do plano original estava
        errada. Quem precisou foi `get_for_area` e o lock de `proximo_numero`
  - [x] fatia 6 — `planos_trabalho`, `justificativas`, `integracoes`, `core.AuditEvent`
        (8 modelos, 8 sites; **catraca em 0**). Fecha o ID. `AuditEvent` ganhou teste dos
        dois lados: a leitura recorta, a escrita continua gravando
- [x] `BE-10` app `justificativas` sem isolamento — **já estava resolvido** pelo `NOVO-06` e pelo
      `NOVO-09`; a verificação de 06/08 conferiu os quatro pontos do enunciado um a um. A Fase 2
      tem 6 IDs, não 7.
- [x] `DB-01` `TabelaDiaria` sem `area` — o enunciado estava invertido: a tabela é nacional de
      propósito. O trabalho era o portão, e ele ficou em **superusuário** (decisão do usuário), no
      POST de diárias e não na view, que serve três abas. `require_area_role` segue com zero usos.
- [x] `DB-02` `area` anulável em 27 de 28 modelos — **enunciado reescrito em 07/08** com os
      três grupos do `NOVO-34` (operacional / catálogo com padrão global / global por projeto),
      `Evento.save()` derivando a área como os outros sete, e o **grupo operacional migrado no
      mesmo dia: `NOT NULL` nos 8 modelos do `core.E001`, em oito migrações
      `*_area_obrigatoria`.** A migração não precisa esperar produção: o gate do `NOVO-12` roda
      antes do `migrate` (protegido pelo rollback do `QA-03`) e aborta no `core.E001` enquanto
      houver órfão, então ela nunca encontra NULL — `backfill` primeiro, deploy de novo depois;
      `scripts/validar_not_null_db02.py` mede sem esperar um deploy (limite 4). O balde legado
      operacional ficou vazio **por construção**, escrita sem área falha alto, e o passo
      "`filter_queryset_by_area` sem área vira `none()`" caiu por desnecessário para o grupo 1.
      O grupo 2 foi saneado e tornou-se obrigatório no `NOVO-49`; apenas o grupo 3 segue
      anulável **por desenho**. A conversão da suíte rendeu `core/testing.py` (área e vínculo de teste,
      `com_request`) e fechou de carona um N+1 nas pendências do Drive. **Fecha a Fase 2.**
- [x] `NOVO-49` fonte canônica dos quatro catálogos semeados; área nova recebe 22 itens em
      transação única, instalações existentes são saneadas e `area` passa a `NOT NULL`
- [x] `DB-04` cache documental não recorta por área — latente, como o enunciado dizia, mas por
      outro motivo: quem separa as áreas é a **referência**, que era opcional. Agora é obrigatória
      (`ValueError` sem ela). A afirmação de que todo artefato nascia `area=NULL` **era falsa** —
      `DocumentoArtefato.save()` deriva a área; está corrigida no catálogo.
- [x] `DB-05` placa de viatura única globalmente — a metade de `ModeloJustificativa` já tinha
      saído no `NOVO-09`. A constraint sozinha não bastava: `ViaturaForm.clean_placa` consultava
      sem recorte e a mensagem de erro confirmava placa de outra unidade. Drill mostrou que a
      **volta da migração deixa de funcionar** depois que duas áreas usarem a mesma placa.

### Fase 3 — O banco defende os dados ✅ **COMPLETA** (13/08/2026)
- [x] `DB-13` composição das diárias estruturada e vinculada à tarifa usada — teste monetário de
      caracterização veio antes; linhas novas congelam faixa, percentual, quantidade, vigência,
      valor e subtotal. O backfill só interpreta resumos inequívocos e não recalcula históricos.
- [x] `DB-06` cascata apaga comprovante e assinatura já coletados — `sair_da_equipe` marca
      (`removida_em`) quem tem dado coletado e apaga quem não tem; `_default_manager` esconde os
      marcados, então os ~15 pontos de leitura (inclusive `prefetch_related` por string) herdam o
      filtro. Readicionar o servidor à equipe restaura tudo. O achado adjacente saiu como `NOVO-35`,
      **também fechado**: excluir o servidor no cadastro passou a ser recusado quando apagaria
      comprovante, assinatura ou número de solicitação — com predicado próprio, mais estreito que o
      do `DB-06`, porque prender um cadastro pesa mais do que preservar uma linha.
- [x] `NOVO-39` exclusão cadastral mudava o total de diárias dos colegas — o ofício agora
      persiste o efetivo monetário; somente uma alteração deliberada da equipe renova o snapshot.
      A migração `oficios/0020` congela o efetivo vigente nos registros existentes.
- [x] `DB-07` 2 `CheckConstraint` em 54 modelos — viraram **26**: doze de ordem (o último veio com o
      `NOVO-36`) e doze de sinal, em
      oito modelos de seis apps, saídas de três fábricas em `core/constraints.py`. O levantamento
      por introspecção achou mais pares do que o enunciado (a cadeia de quatro datetimes do
      `Roteiro`, e o par do `RoteiroTrecho`). `scripts/validar_constraints_db07.py` é o
      procedimento do limite 4 do `AGENTS.md`: conta o que cada constraint reprovaria, antes do
      deploy.
- [x] `DB-08` coleções ordenadas aceitam duplicata — **5 de 5**. Fatia 1: `RoteiroDestino`,
      `PlanoDestino` (par parcial, porque `evento` é anulável) e `EventoPlano`. Fatia 2:
      `RoteiroTrecho` e `DiarioBordoTrecho`, que reordenam linha a linha e por isso levaram os
      dois escritores para **dois passos** (bloco livre, depois posições finais) e para dentro de
      `transaction.atomic` — nenhum dos dois abria transação. A medição de duplicata só vale em
      produção: quatro das cinco tabelas estão vazias no banco de desenvolvimento

### Fase 4 — Fundação do front ✅ **COMPLETA** (13/08/2026)
- [x] `JS-06` JS larga o nome de classe `cv-search-picker` — e as **partes** junto (`NOVO-19`):
      a superfície real era 45 sites em 11 arquivos, não 10 em 7. Contrato novo:
      `data-entity-picker-root`/`-part` + `CV.picker.rootFor/part`
- [x] `JS-05` auditor de CI cobre `innerHTML` e `registerEnhancer` sem `destroy` — 4 regras novas
      (6 → 10 invariantes), com `JS_EXCEPTIONS` de **teto por arquivo**: dentro do teto é exceção
      informativa, acima é erro. Achou `NOVO-14` e `NOVO-15`
- [x] `JS-02` `destroy` nos componentes que registram listener global — o número é **14 de 17**,
      não 15, e só 4 vazavam de fato. Um deles (`attach-signed-modal`) não estava no enunciado.
      Medido no navegador: 15→17→19→21 antes, 14→16→14 depois
- [x] `PF-01` folha de símbolos de ícone (192 KB por página de lista) — 06/08
- [x] `PF-04` menu de ação sob demanda (60 menus para 20 cards) — **os seis domínios**:
      Ofícios 315,3 → 166,5 KB, Eventos 416,3 → 211,9, Termos 317,6 → 147,9,
      Prestações 383,1 → 259,0, Planos 169,5 → 129,0, OS 166,8 → 126,7; `roteiros` não tem menu
- [x] `HT-02` erro de campo sem `aria-describedby`/`aria-invalid`/`role="alert"` — o Django 5.2 já
      emitia os dois atributos; faltava a **âncora**. 39 chamadores passaram a informar `field_id`,
      com varredura estática cobrindo o quadragésimo antes de ele existir
- [x] `HT-12` `help_text` declarado no form nunca chega à tela — 29 campos em 17 forms declaravam,
      **2 chamadores** de 154 passavam o parâmetro. Residual `use_fieldset` virou `NOVO-41`
- [x] `HT-03` sem padrão único para erro de formulário — eram **quatro** padrões e o componente
      certo tinha **zero** chamadores; agora são 20, e o resumo mostra a mensagem de verdade em
      vez de uma frase genérica. O painel de cadastro rápido não tinha padrão **nenhum**
- [x] `HT-05` `empty_state.html` quebra a ordem de headings — o pulo era **10 de 10** listas, não 9;
      o título vira `<h2>` e `form_block` ganha ramo `h2` (aditivo) para o cadastro rápido de
      justificativas. Sem parâmetro `heading_level`: a inversão mostrou o repasse inerte
- [x] `UI-01` poda das ~929 classes candidatas — **963 blocos, 170,7 KB** removidos; a unidade de PR
      virou a **família de classe**, não o arquivo, e a verificação virou `getComputedStyle` (0 de
      41.938 elementos) porque o diff de pixel tinha ruído maior que o efeito. Travado por
      `scripts/audit_css_morto.py --max 0` no CI. Resíduo declarado: `NOVO-48`
- [x] `HT-06` 10 a 14 componentes mortos, três deles citados como canônicos — **7 apagados**
      (um deles órfão em cascata, revelado pela própria trava) e **7 do UI Lab mantidos**, porque
      apagá-los é decidir qual dos dois labs é o vigente (`BE-17`). `form_errors` saiu da lista:
      o `HT-03` lhe deu 20 chamadores
- [x] `HT-13` `docs/DATA_ATTRIBUTES_JS.md` descreve um contrato que não existe mais — eram **7**
      atributos mortos, não 3, e a cobertura era de 19% (57 de 298). Rescrito a partir da
      medição e **travado nos dois sentidos** por teste, que é o que impede de apodrecer de novo

### Fase 5 — Consulta e índice ✅ **COMPLETA** (12/08/2026)
- [x] `DB-09` lista de roteiros agrega antes do `LIMIT` — `~Exists()` no lugar de
      `Count` + `.exclude(...=0)`, **junto** com o índice `(area, -updated_at)`: separados dão
      2,9× e 1,0×, juntos 8,9× na consulta e **1,54× na rota** (975,8 → 633,2 ms). O `LIMIT`
      não curto-circuita como o enunciado previa; quem sai é o `GroupAggregate`
- [x] `DB-10` índice composto para a ordenação real das listas — **um índice, não cinco**.
      Das cinco listas que ordenavam em memória, só `OrdemServico` ganha (64× na consulta,
      1,08× na rota); nas outras quatro o índice análogo não move o tempo e em `roteiros`
      piora. "Ofícios têm situação análoga" era falso; o `NOVO-50/PF` separou as causas: ids antes
      da hidratação, contagens agregadas, relações achatadas e fragmento por conteúdo derrubaram
      Ofícios de 125,5 para **33,2 ms** no volume 200 e de 1.554,4 para **163,9 ms** em 20.000;
      consultas **13 → 7**, fechando também o `PF-05`
- [x] `DB-11` busca livre de Termos multiplicava 20.000 linhas por três M2M e rodava três vezes —
      `Exists()` por origem + contagem das abas reutilizada pelo paginador. O `PF-07` agora mede
      `termos:index:busca` permanentemente: **1.807,9 → 391,4 ms (4,62×)** em 20.000 registros,
      com 6 queries. `pg_trgm` não entrou: a medição anterior deu 1,00× e provou que o gargalo era
      a forma da consulta, não a ausência de cinco índices
- [x] `DB-12` trilha de auditoria sem índice, sem expurgo — **só o índice**. O expurgo saiu
      por decisão do usuário (retenção de trilha de órgão público é pergunta de produto).
      O índice entrou como folga: medido, o planner só o escolhe por volta de 100 áreas,
      e produção não é observável daqui. A trilha não tem leitor fora do admin
- [x] `PF-03` toda requisição escreve na tabela de sessão — decisão tomada em 07/08:
      `cached_db` **mais** renovação periódica, que são uma coisa só (`cached_db` sozinho
      economiza 1 de 11; as outras 3 dependem de desligar `SESSION_SAVE_EVERY_REQUEST`).
      11 → 7 consultas em toda requisição autenticada, em todas as nove rotas medidas
- [x] `PF-06` queries duplicadas em `/usuarios/` e `/prestacoes-contas/` — o pior caso não
      estava no enunciado: **`roteiros:index` tinha 11 consultas a mais**, e foi de 29 para
      14. `/usuarios/` tinha 1, não 2, e foi corrigida. Sobram três de 1 consulta, com o
      mecanismo já identificado no catálogo

### Fase 6 — Camadas e duplicação ✅ **COMPLETA** (13/08/2026)
- [x] `BE-11` editor de roteiro em 3 cópias — **eram 2**: medida a interseção, `novo` × `editar` dá
      55 linhas idênticas (o enunciado dizia 41) e `wizard_roteiro` só 20 de 165. As duas primeiras
      foram unificadas atrás de `roteiros/services/editor_flow.py`; a terceira é outro fluxo e cai
      no `BE-12`. Sobrou `NOVO-87` (o ofício não detecta duplicado — decisão adiada, não esquecida)
- [x] `NOVO-87` wizard de Ofício não faz fusão destrutiva automática; diagnóstico JSON mede por
      área os grupos em que cada roteiro idêntico é usado por Ofício, sem falsos pares entre áreas
- [x] `BE-12` `wizard_roteiro` com a regra dentro da view — a regra de vínculo/cópia virou
      `oficios/services.py::salvar_roteiro_do_oficio`, com `atomic`. 33 → 13 ramos, 165 → 124
      linhas úteis, cobertura de `route_views.py` de 69% para 88%. Fecha o `NOVO-88` e o item 1 da
      lista do `BE-14`. Sobrou `NOVO-92` (a tradução de ação do rodapé, copiada em cada passo)
- [x] `BE-13` `roteiro_logic.py` fora do contrato de camadas — **três fatias, três PRs**. F1
      (parsing): `request` no módulo caiu de 23 ocorrências para 1, os 6 objetos falsos e o parâmetro
      morto de `_validate_roteiro_state` sumiram. F2 (contexto + invólucros): a fachada do contexto
      migrou de service para presenter, e 15 invólucros morreram. F3 (persistência): o gravador
      atômico de 3 tabelas foi para `roteiros/services/editor_persistence.py` com nomes públicos, e o
      módulo virou `roteiros/services/editor_state_builder.py` — nome e lugar do que sobrou.
      **1.845 → 1.337 linhas (−27%), 57 → 33 defs.** Continua grande, mas com uma responsabilidade
      só. Sobrou `NOVO-98` (guardas defensivas do gravador, inalcançáveis pelo caminho público).
      **Fecha a corrente `BE-11`/`BE-12`/`BE-13`**
- [x] `BE-14` 48 sites de persistência em view, sem transação — **eram 36**, mais 4 por método de
      modelo que grava por dentro. **Fatia 1 (o dinheiro do RT) feita**: a persistência de
      `rt_views.py` virou `prestacoes_contas/rt_services.py`, o módulo caiu de 305 para 203 linhas
      com zero acessos de manager, e as gravações fora de transação foram de 36 para 33. Fecha
      `NOVO-101` (a catraca `P-01` media 24 com 35 no chão) e `NOVO-102` (gravação em laço escondida
      em `view_common.py`). **Fatia 2 (solicitação) feita**: as duas rotas foram para
      `solicitacao_services.py` com transação, `views.py` caiu de 743 para 674 linhas e as gravações
      fora de transação de 33 para 29. `NOVO-103` foi fechado em 13/08/2026: as duas rotas agora
      validam antes de gravar, rejeitam a requisição inválida inteira e marcam o mesmo status. **Fatia 3
      (anexos) feita**: `atomic` na linha e `transaction.on_commit` no arquivo, porque ali `atomic`
      sozinho inverteria o órfão do `BE-07`. O defeito maior não era gravação parcial: era
      destruição — um `create` que falhasse levava o documento assinado anterior do disco e do
      banco. Gravações fora de transação: 29 → 24; catraca `P-01` desce de 33 para 31. Sobrou
      `NOVO-104` (arquivo órfão no storage não tem quem varra). **Fatia 4 (diário) feita**: os três
      caminhos de escrita de `diario_views.py` foram para `diario_services.py`, o módulo caiu de 388
      para 345 linhas com zero acessos de manager, gravações fora de transação 24 → 19 e catraca
      `P-01` 31 → 27. Sobrou `NOVO-107` (a fixture monta ofício sem roteiro e o teste de diário fica
      verde por omissão). **Prestações fecha aqui; o `BE-14` não.** A fatia 1 disse que 2, 3 e 4
      fechariam o defeito, e a frase valia para prestações — 21 dos 36 sites. **Restam 19**, em
      `planos_trabalho` (6), `oficios` (4), `eventos` (2), `prestacoes_contas/model_views.py` (3) e
      uma cada em `core`, `ordens_servico`, `roteiros` e `termos`. **Fatia 5: `planos_trabalho` +
      `oficios`**, que somam 10 dos 19 e incluem a pior função restante
      (`_apply_efetivo_snapshot`: `save` + `create` + `delete` em laço)

      `NOVO-104` (arquivo órfão no storage não tem quem varra). **Fatia 5 (planos + ofícios)
      feita**: `planos_trabalho` ganhou a primeira camada de escrita da sua história —
      `efetivo_services.py` e `identificacao_services.py`, 5 `atomic` onde antes havia **zero
      em 1.314 linhas** — e `criar_rascunho_de_roteiro_do_oficio` entrou em `oficios/services.py`
      ao lado do irmão do `BE-12`. Gravações fora de transação: 24 → 19 na fatia 4 e → 17 nesta.
      Sobrou `NOVO-108`: **a contagem por AST erra nos dois sentidos e não serve mais de alvo** —
      superconta 7 (cinco `delete()`, que o `Collector` do Django já faz em transação, e dois ramos
      mutuamente exclusivos) e subconta o pior caso restante, `eventos/views.py::detalhe`, que
      aparece com 1 e faz ~12 gravações em 6 tabelas. **Fatia 6: `eventos`**, dirigida por leitura
      de caminho e não pelo contador. **Fatia 6 feita**: a etapa 1 de `eventos::detalhe` virou
      `salvar_identificacao_evento`, um service atômico para Evento, M2M, destinos, cinco famílias de
      documento e termo automático. Falha no último passo desfaz todas as seis tabelas; 43 testes de
      Eventos verdes. O `P-01` permanece 27 porque o `NOVO-108` provou que esse caminho era invisível
      ao contador. Fecha `BE-14` e `NOVO-108`; a dívida unitária de posição em camada segue no `BE-16`
- [x] `BE-15` numeração reimplementada 3 vezes — **fatia 1 (a mecânica) feita**: o lock e o laço
      de retry, que eram ~60 linhas copiadas entre ofício e OS, viraram `core/numeracao.py`; a
      política de escolha de cada documento fica onde estava, porque diferente ali é desenho, não
      defeito. Apareceu um quarto site que o enunciado não citava (a edição de número manual), que
      passou a usar o lock **sem** o retry. Fecha `NOVO-109`: a detecção de colisão lia a mensagem
      do `IntegrityError` e **só funcionava no PostgreSQL** — em metade da suíte o retry era código
      morto, e o teste que o cobria fabricava a própria evidência. **Fatia 2**: OS reaproveita
      número liberado por exclusão (decisão do dono; único ponto que muda número emitido) — **feita**
      com `OrdemServicoNumeroLacuna`, exclusão atômica e consumo por área/ano; salto manual não vira
      lacuna e falha no registro desfaz a exclusão. 53 testes de OS verdes.
      **Fatia 3 feita**: `salvar_plano_numerado` preserva contador e sufixo do Plano, mas une avanço
      e `INSERT` na mesma transação e usa o retry comum. Colisão real repete; falha após reserva
      desfaz o contador; escolha+gravação compartilham o savepoint; a concorrência PostgreSQL agora
      mede duas linhas gravadas. 116 testes verdes
- [x] `BE-16` abstrações de `core` adotadas pela metade — **fatia 1 (paginação) feita**: os 15
      pontos usam `contexto_paginacao`, as 6 cópias de `_pagination_pages` foram removidas e não há
      `Paginator(...)` em produção fora do módulo comum. Termos mantém o total pré-agregado via
      `paginator_class`; chaves e filtros do contexto foram preservados. 922 testes consumidores
      verdes. **Fatia 2 (exclusão protegida) feita**: catálogos e serviços de exclusão de entidades
      acionados pelo usuário adotam `core.deletion`; `PROTECT` vira erro de domínio/mensagem e não
      500. Remoções internas de filhos, arquivos, cache, sessão e rascunhos ficam fora por contrato.
      A regressão de OS prova que bloqueio não cria lacuna; 299 testes consumidores verdes.
      **Fatia 3 (retorno) feita**: as duas cópias sobreviventes — catálogo e upload assinado de
      Prestações — delegam a `core.retorno`; leitura de `next` e validação de host têm um único dono.
      Fallback, fragmento de modal e recusa de host externo estão cobertos por 93 testes. BE-16
      fechado
- [x] `BE-17` `core/views.py` é 75% fixture de UI Lab — **fechado pelo PR #247**, que apagou os
      dois labs e as 1.013 linhas de fixture; a cascata de componentes que ele deixou é o
      `NOVO-44`

### Fase 7 — Reconstrução do front (CSS, HTML e JavaScript) ✅ **COMPLETA** (13/08/2026)

**Dimensionada em 09/08/2026 no [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md)**,
que é o documento a seguir para esta fase: doze etapas (E0–E11), cada uma com arquivos, comando de
verificação e catraca. O escopo cresceu em relação ao que este quadro previa, por três decisões do
dono: **componentização por `django-cotton`**, **desenho único entre os temas claro e escuro** e
**runner de teste de JavaScript no CI**.

O quadro abaixo é por ID; a ordem de execução é a das etapas, não a desta lista.

- [x] `NOVO-75` 🔴 `dev.txt` não puxa `test.txt` — o `--parallel 4` aborta em toda sessão remota · **E0**
- [x] `NOVO-70` a métrica de aceite do `PF-02` não tem instrumento; corpus de rotas com 14 telas mortas · **E0**
- [x] `NOVO-76` `audit_ui_patterns.py` está no ciclo obrigatório do `AGENTS.md` §4 e sai 1 sempre · **E0**
- [x] `NOVO-77` corpus antigo mantinha duas telas mortas além do UI Lab · **E0**
- [x] `NOVO-78` fixture demo não acompanhou área obrigatória e seis modelos novos · **E0**
- [x] `NOVO-79` duas rotas canônicas resolviam, mas respondiam 500 · **E0**
- [x] `JS-03` runner de teste de JavaScript — deixou de ser aditivo, virou pré-requisito · **E1**
- [x] `NOVO-69` `cv-select.js` (343 linhas) morto desde o PR #247, ainda no bundle · **E2**
- [x] `NOVO-72` `ui_lab2/` sobreviveu ao PR #247 · **E2**
- [x] `NOVO-73` nome e lugar de arquivo JS sem padrão · **E2**
- [x] `NOVO-48` 70 nomes de classe morta dentro de seletor agrupado vivo · **E2**
- [x] `NOVO-71` componente global sem contrato de parâmetro → `django-cotton` · **E3–E5**
- [x] `HT-14` 275 de 946 includes não usam `only` — contratos e `only` obrigatórios · **E5**
- [x] `NOVO-74` dois namespaces de componente, quatro pastas fantasma de `.gitkeep` · **E5**
- [x] `HT-08` 82 `<button>` fora do sistema de componentes · **E6**
- [x] `NOVO-14` nove leituras de classe visual como lógica → ARIA, `hidden` e `data-*` dedicados · **E6**
- [x] `NOVO-15` oito expressões dinâmicas em `innerHTML` → APIs de DOM e parsing isolado · **E6**
- [x] `HT-15` bloco `cv-itinerary` duplicado em 5 apps · **E6**
- [x] `NOVO-16` markup do picker copiado à mão em 3 templates e 5 arquivos JS · **E6**
- [x] `HT-10` `data-*` de toggle legado em componente compartilhado · **E6**
- [x] `HT-07` concatenação condicional com "·" no template · **E6**
- [x] `NOVO-80` a E5 apagou duas travas de regressão em vez de reapontá-las · **E6**
- [x] `NOVO-81` o auditor de front audita os `*.test.js` que a E1 criou · **E6**
- [x] `NOVO-99` os três `include ... only` do editor passam o token CSRF explicitamente · **correção imediata**
- [x] `UI-03` nove (medidos: oito) arquivos definem token de cor → duas camadas · **E7a**
- [x] `NOVO-82` 87 declarações escuras inertes, visíveis desde a fusão do `theme.css` · **E9**
- [x] `NOVO-114` a régua de mesmo tema citada pela E9 não estava versionada; sonda reproduzível,
      contexto público/autenticado correto e contrato automatizado · **E9**
- [x] `NOVO-119` separa 354 regras compartilhadas da camada escura; o arquivo transitório cai de
      5.555 para 2.434 linhas e de 184 para 98 `!important`, com cascata estável · **E9**
- [x] `NOVO-51` os 2 apelidos puros da família `cv-field` (e 15 bordas invisíveis) · **E7b**
- [x] `NOVO-51` os 2 de valor próprio foram fechados em 11/08 após a decisão por anel visível no
      escuro: zero definições `--cv-field-*` vivas no CSS de fonte; a reauditoria de 12/08 encontra
      somente comentários históricos nos bundles/folhas · **E7b**
- [x] `NOVO-54` 72 regras (30 `!important` e 7 regras já fora); as 7 candidatas de estado não-base
      também fecharam por medição (2 blocos removidos e 5 grupos de seletor simplificados). A regra
      base agora vence o seletor de elemento cru com neutralidade medida; as 8 pseudo-regras e 1
      contexto órfão caíram; diário, quick-add e `field-with-action` fecharam no corpus ampliado · **E7c**
- [x] `NOVO-58` claro e escuro têm desenho único: 54.225 elementos, 129 medições, 0 divergências não-cor · **E8**
- [x] `UI-02` camada escura reconciliada: regras compartilhadas saíram; restam somente seletores
      predicados por tema, sob catraca (5.619 → 2.434 linhas; 190 → 98 `!important`) · **E9**
- [x] `UI-04` fronteiras CSS fechadas no escopo medido: 97 imports históricos → **82 atuais** em
      37 templates; três folhas sem regra casada saíram na reauditoria final (`NOVO-120`) · **E10**
- [x] `HT-04` entrega fechada: shell JS 266.254 → 108.937 bytes e componentes CSS pesados sob
      demanda; a reauditoria final separa a eficiência do bundle da fronteira de domínio · **E11/E10**
- [x] `JS-07` 3 implementações vivas de "fechar ao clicar fora / Esc" → `CV.overlay.attachDismiss` · **E11**
- [x] `JS-08` cinco componentes sob demanda por marcador DOM; shell 283.128 → 266.254 bytes · **E11**
- [x] `JS-09` tela embutida entrega só `http.js` + polling: 283.282 → 4.255 bytes de JS · **E11**
- [x] `JS-10` três stubs sem consumidor removidos; módulos reais e bootstrap preservados · **E11**

**Fechados nesta fase** (inclui a reconstrução parcial de 07–08/08, que o quadro não registrava, e
o fechamento operacional posterior do `NOVO-57`): `NOVO-50/MED` paleta de 255 cores duplicadas ·
`NOVO-51` poda dos 55 apelidos
puros de token · `NOVO-52` foco no editor de roteiro · `NOVO-53`/`NOVO-55`/`NOVO-56` máscara de
maiúscula · `NOVO-57` histórico normalizado em produção (6.597 valores, 77 gravados e zero
divergentes após backup e pós-checagem) · `NOVO-59` ícone de botão invisível no tema claro ·
`NOVO-60` levantamento da
renomeação por função · `NOVO-61` dez nomes mortos em seletor agrupado · `NOVO-62` `Inter`
empacotada e válida nos dois temas · `NOVO-63` geometria da barra lateral globalizada ·
`NOVO-64` 176 tokens sem prefixo · `NOVO-65` 545 classes sem prefixo.

### Fase 8 — Observabilidade e autorização ✅ **COMPLETA** (13/08/2026)
- [x] `BE-18` handlers genéricos mudos 73 → 0; exceções esperadas tipadas, falhas inesperadas
      observadas e catraca AST permanente no CI
- [x] `BE-19` decisão de autorização registrada; helper e contexto sem consumidor removidos sem
      inventar operação exclusiva de ADMIN
- [x] `QA-16` Sentry opcional integrado ao Django e a `capture()`, sem PII/tracing e com falha segura
- [x] `QA-10` causa fechada por `QA-02`: Redis obrigatório em produção compartilha os contadores
      entre workers; margem concreta do Drive segue em `QA-05`
- [x] `QA-05` cliente real do Google Drive coberto por 12 testes de contrato na fronteira da API
- [x] `QA-14` CRUD de modelos do Relatório Técnico — já fechado por 7 testes em `993e14c5`;
      status reconciliado
- [x] `QA-15` oito provas dos erros de download, WeasyPrint, storage e fila; 22 testes do conjunto
      de geração/conversão verdes
- [x] `QA-13` indicador reconciliado como sinal de triagem, não meta de tamanho de teste

### Fase 9 — Finalização e higiene ✅ **COMPLETA** (13/08/2026)
- [x] `BE-20` `diario_bordo` é app-casca — **removido**: 33 linhas, rota inalcançável, sem
      migration nem tabela. A funcionalidade real, em `prestacoes_contas`, ficou intacta
- [x] `BE-21` presenter morto prometendo "DOCX (em breve)" — **removido**; a varredura por AST
      achou **dois** presenters mortos no módulo, não um
- [x] `BE-22` 10 arquivos `.py` com BOM — **fechado**: eram 11 (10 `.py` + um `.md`), e o
      `cadastros/views.py` era o único que obrigava o gate do `S-06` a ler com `utf-8-sig`
- [x] `BE-23` vocabulário de rotas — 28 sufixos CRUD padronizados e protegidos por catraca;
      operações de domínio permanecem descritivas por decisão explícita
- [x] `BE-24` artefatos locais removidos após extrair o corpus — **135 arquivos / 43,18 MiB**;
      `.gitignore` impede a reentrada
- [x] `BE-25` decidir qual UI Lab é o vigente — **decidido e executado no PR #247: nenhum dos
      dois.** A cascata (7 componentes órfãos + 1 de segunda ordem, `main` vermelho em 8 testes)
      ficou para trás e foi fechada como `NOVO-44`
- [x] `NOVO-44` o `BE-25` apagou os labs e deixou a cascata do `HT-06` para trás — 8 componentes
      apagados com prova de grep, `SO_NO_LABORATORIO` vazia com a trava intacta, piso 85 → 83
- [x] `QA-08` dependências atrasadas — `pyhanko` morto removido; `docxtpl` 0.20.2, WeasyPrint 69,
      ReportLab 5 e Redis 8.1 atualizados em fatias isoladas com locks reproduzíveis
- [x] `NOVO-118` `docxcompose` declarado diretamente após o upgrade expor a transitividade oculta
- [x] `NOVO-01` contrato de assinatura reescrito para os fluxos reais, sem backend pyHanko fictício
- [x] `NOVO-02` suíte trava ao combinar certos grupos de apps — **não reproduziu** em 06/08 (a
      combinação do catálogo passa, inclusive em `--reverse`). A sondagem achou o `NOVO-26`
      (mapa de capitais memorizado no processo decidindo diária com base velha, **fechado**)
- [x] `NOVO-27` regressão do `NOVO-26`: uma consulta de capitais por card na lista de
      roteiros (teto do `PF-07` 32 → 47). Corrigida; teto sobe a 33 de propósito
- [x] `NOVO-115` resíduo do PR #58: documentos vinculáveis acompanham o período ainda não salvo e
      o picker recupera a ação de limpar, sobre os componentes atuais
- [x] `NOVO-117` resíduo do PR #4: marcador de combustível `CB` → `CT` reaplicado no renderer atual
- [x] `QA-17` triagem dos PRs abertos — eram 17: 12 fechados, 3 upgrades de Actions mesclados e
      2 intenções reaplicadas com `NOVO-115`/`NOVO-117`; fila antiga zerada
>>>>>>> 9f64b66119bb3589c6733e10a16a086f858aa02f
