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
| **7** | **Reconstrução do CSS** | `UI` | ver plano de front | médio | A mais visível e a mais reversível. Depois da fase 4, que define os nomes. |
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
| Catálogo global do `DB-02` (grupo 2): cada item vira cópia por área ou ganha dono? | `DB-02` (fase 2) | `TipoEvento`, `ProgramaSolicitante`, `HorarioAtendimento`, `AtividadePlanoTrabalho` têm linhas globais de seed servidas a todas as áreas; `NOT NULL` ali exige decidir o destino de cada uma (o `NOVO-09` duplicou `ModeloJustificativa` por área — é um precedente, não uma regra) |

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
- [~] `DB-02` `area` anulável em 27 de 28 modelos — **enunciado reescrito em 07/08** com os
      três grupos do `NOVO-34` (operacional / catálogo com padrão global / global por projeto)
      e o primeiro passo do grupo operacional fechado: `Evento.save()` deriva a área como os
      outros sete modelos do `core.E001`, com teste que falharia antes. O que resta **depende
      de produção**, na ordem do enunciado novo: backfill provado pelo gate do `NOVO-12` (que
      imprime `core.E001`/`W001` a cada deploy), migração `NOT NULL` dos oito operacionais
      (limite 4 do `AGENTS.md`), e só então `filter_queryset_by_area` sem área vira `none()`.
      Grupos 2 e 3 seguem anuláveis **por desenho**; a decisão de produto do grupo 2 está
      no §8.
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
- [~] `DB-08` coleções ordenadas aceitam duplicata — **3 de 5**: `RoteiroDestino`,
      `PlanoDestino` (par parcial, porque `evento` é anulável) e `EventoPlano`. `RoteiroTrecho` e
      `DiarioBordoTrecho` reordenam por troca linha a linha e precisam do escritor em dois
      passos antes da constraint — fatia 2

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

### Fase 5 — Consulta e índice
- [ ] `DB-09` lista de roteiros agrega antes do `LIMIT`
- [ ] `DB-10` índice composto para a ordenação real das listas
- [ ] `DB-11` 80 buscas livres sem índice
- [ ] `DB-12` trilha de auditoria sem índice, sem expurgo
- [ ] `PF-03` toda requisição escreve na tabela de sessão (**depende de decisão de produto**)
- [ ] `PF-06` queries duplicadas em `/usuarios/` e `/prestacoes-contas/`

### Fase 6 — Camadas e duplicação
- [ ] `BE-11` editor de roteiro em 3 cópias
- [ ] `BE-12` `wizard_roteiro` com a regra dentro da view
- [ ] `BE-13` `roteiro_logic.py` fora do contrato de camadas
- [ ] `BE-14` 48 sites de persistência em view, sem transação
- [ ] `BE-15` numeração reimplementada 3 vezes
- [ ] `BE-16` abstrações de `core` adotadas pela metade
- [x] `BE-17` `core/views.py` é 75% fixture de UI Lab — **fechado pelo PR #247**, que apagou os
      dois labs e as 1.013 linhas de fixture; a cascata de componentes que ele deixou é o
      `NOVO-44`

### Fase 7 — Reconstrução do CSS
- [ ] `UI-03` nove arquivos definem token de cor → duas camadas
- [ ] `UI-02` tema escuro deixa de ser camada de exceção (5.843 linhas, 190 `!important`)
- [ ] `UI-04` 54 imports de CSS de outro domínio, em 26 templates
- [ ] `HT-04` `base.html` carrega ~153 KB de JS de domínio em toda página
- [ ] `HT-08` 80 `<button>` fora do sistema de componentes
- [ ] `HT-15` bloco `cv-itinerary` duplicado em 5 apps
- [ ] `HT-14` 28% dos includes não usam `only`
- [ ] `HT-07` concatenação condicional com "·" no template
- [ ] `HT-10` `data-*` de toggle legado em componente compartilhado
- [ ] `JS-07` "fechar ao clicar fora / Esc" em 4 cópias
- [ ] `JS-08` 11% do bundle atende menos de 1% das páginas
- [ ] `JS-09` tela de espera carrega 264 KB para usar 3,3 KB
- [ ] `JS-10` decidir os stubs do editor de roteiros
- [ ] `JS-03` runner de teste de JavaScript (etapa própria)

### Fase 8 — Observabilidade e autorização
- [ ] `BE-18` `capture()` só existe em um app; 72 `except` mudos
- [ ] `BE-19` `require_area_role` com zero usos
- [ ] `QA-16` sem rastreamento de erro centralizado
- [ ] `QA-10` `/metrics/` conta só o worker que atendeu
- [ ] `QA-05` cliente real do Google Drive com 42,5% de cobertura
- [ ] `QA-14` CRUD de modelos do Relatório Técnico sem teste
- [ ] `QA-15` caminhos de erro da geração de PDF sem teste
- [ ] `QA-13` 218 testes "magros" — número a olhar, não meta a perseguir

### Fase 9 — Finalização e higiene
- [x] `BE-20` `diario_bordo` é app-casca — **removido**: 33 linhas, rota inalcançável, sem
      migration nem tabela. A funcionalidade real, em `prestacoes_contas`, ficou intacta
- [x] `BE-21` presenter morto prometendo "DOCX (em breve)" — **removido**; a varredura por AST
      achou **dois** presenters mortos no módulo, não um
- [x] `BE-22` 10 arquivos `.py` com BOM — **fechado**: eram 11 (10 `.py` + um `.md`), e o
      `cadastros/views.py` era o único que obrigava o gate do `S-06` a ler com `utf-8-sig`
- [~] `BE-23` vocabulário de rotas divergente — **sufixo CRUD fechado** (28 rotas PT→EN,
      com catraca). Resta o vocabulário dos outros 75% dos nomes, que é decisão de sistema
- [ ] `BE-24` 89 MB de screenshots e 175 arquivos indevidos no repositório
- [x] `BE-25` decidir qual UI Lab é o vigente — **decidido e executado no PR #247: nenhum dos
      dois.** A cascata (7 componentes órfãos + 1 de segunda ordem, `main` vermelho em 8 testes)
      ficou para trás e foi fechada como `NOVO-44`
- [x] `NOVO-44` o `BE-25` apagou os labs e deixou a cascata do `HT-06` para trás — 8 componentes
      apagados com prova de grep, `SO_NO_LABORATORIO` vazia com a trava intacta, piso 85 → 83
- [ ] `QA-08` dependências atrasadas — e `pyhanko` é dependência **morta**, decidir se sai
- [ ] `NOVO-01` `ASSINATURA_ETIQUETA_2_COMPAT.md` descreve fluxo que não existe mais
- [x] `NOVO-02` suíte trava ao combinar certos grupos de apps — **não reproduziu** em 06/08 (a
      combinação do catálogo passa, inclusive em `--reverse`). A sondagem achou o `NOVO-26`
      (mapa de capitais memorizado no processo decidindo diária com base velha, **fechado**)
- [x] `NOVO-27` regressão do `NOVO-26`: uma consulta de capitais por card na lista de
      roteiros (teto do `PF-07` 32 → 47). Corrigida; teto sobe a 33 de propósito
- [ ] `QA-17` triagem dos 13 PRs abertos
