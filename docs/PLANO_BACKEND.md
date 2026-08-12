# Plano de refatoração do backend

**Medido em 05/08/2026** sobre o código de hoje, não sobre as auditorias de julho. Cada afirmação
tem arquivo:linha, saída de comando ou teste funcional atrás dela.

**Regras de conduta:** [`AGENTS.md`](../AGENTS.md) · **Ordem das etapas:**
[`PLANO_MESTRE_REFATORACAO.md`](PLANO_MESTRE_REFATORACAO.md) · **Defeitos:**
[`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md) (prefixos `BE` e `DB`)

---

## 1. O estado real

O ciclo de julho entregou o que era mecânico. As camadas existem nos 14 apps, `P-04` (classe CSS
dentro de `attrs={}` em forms) está em **zero**, as views emagreceram — 315 funções somam 6.880
linhas e só 3 passam de 100 LOC — e a suíte tem 1.306 testes verdes em ~10 s.

O que sobrou não é estilo. É risco, e está concentrado em três lugares:

**Primeiro, o isolamento por área é uma convenção, não um invariante.** `core/tenancy.py:57`
define `filter_queryset_by_area()` como função livre, aplicada à mão. Nenhum dos 54 modelos
declara manager próprio. Existem 123 usos de `.objects.` sobre modelos com campo `area` fora
desse filtro em código de caminho de request. Quatro vazamentos foram **provados por teste**, não
inferidos: o app `justificativas` inteiro, quatro dos cinco *pickers* do formulário de evento, o
seletor de modelo de motivo da Ordem de Serviço e a limpeza de rascunhos do editor de roteiros —
que **apaga rascunho de outra área**.

**Segundo, o banco não defende nada.** 61 `UniqueConstraint` contra **2** `CheckConstraint` em 54
modelos. Data de fim anterior ao início e diária negativa entram, medido em transação real. Nenhuma
das coleções ordenadas (destinos, trechos) impede linha duplicada — e destino duplicado é contado
duas vezes pelo motor de diárias.

**Terceiro, há defeitos que atingem o usuário agora.** O wizard de plano de trabalho não finaliza
e o botão "Voltar" avança; a exclusão de anexo de prestação de contas acontece por `GET`, sem CSRF
e sem confirmação; o filtro de data da lista de ofícios é descartado em silêncio por um
`except Exception: pass`.

---

## 2. As etapas

### B0 — Defeitos que atingem o usuário agora · 3,5 dias · risco baixo

Oito correções isoladas, nenhuma depende de renomear ou mover nada. Se o calendário virar, é
aqui que se para com o sistema melhor do que estava.

| ID | Defeito | Onde | Dias |
|---|---|---|---:|
| `BE-01` 🔴 | "Finalizar plano" não finaliza; "Voltar" avança | `planos_trabalho/view_helpers.py:22` lê só `post.get("action")`; a cadeia `_documentos_preview_footer.html` → `card_footer_section.html` → `card_footer_actions.html:18` emite `name="wizard_action"`. Zero `name="action"` nos templates do app: o helper cai no default `wizard_next` **sempre** | 0,5 |
| `BE-02` 🔴 | Exclusão de anexo por `GET`, sem CSRF e sem confirmação | `prestacoes_contas/document_views.py:341` — nenhum decorator; `require_POST` está **importado na linha 9 e nunca aplicado** neste arquivo | 0,5 |
| `BE-03` 🟠 | Filtro "criado de/até" descartado em silêncio | `oficios/selectors.py:103-112` usa `__date__gte` em `DateField`; **2** `except Exception: pass` (linhas 106 e 111) escondem o `FieldError` | 0,5 |
| `BE-04` 🔴 | Formulário de evento oferece documentos de outras áreas | `eventos/forms.py:264,267,270,275` — a linha 259 filtra, as 4 seguintes não | 0,5 |
| `BE-05` 🟠 | Seletor de modelo de motivo da OS expõe outras áreas | `ordens_servico/forms.py:252` | 0,25 |
| `BE-06` 🟠 | Relatório técnico sai com a cidade-sede de outra área | `prestacoes_contas/services.py:117` — `ConfiguracaoSistema.objects.first()` | 0,25 |
| `BE-07` 🟠 | Exclusão de anexo dá 500 e deixa registro órfão | `core/audit.py:146` `str(instance)` quando `__str__` devolve `None` | 0,5 |
| `BE-08` 🟠 | **Oito** redirects seguem o que o POST mandar | `prestacoes_contas/views.py:383-384` e `signature_views.py` (7 sites, incluindo as duas views de cancelamento) ignoram `core/retorno.py` | 0,5 |

**Gate:** suíte verde; um teste de regressão por defeito; nos dois de área, teste com duas áreas
afirmando `queryset.filter(area=outra).count() == 0`.

### B1 — Isolamento por área vira invariante · 18 dias · risco alto

A etapa mais importante do plano inteiro. Enquanto o recorte depender de o programador lembrar,
todo código novo é uma chance de vazar, e a revisão humana é o único portão.

| ID | Defeito | Dias |
|---|---|---:|
| `BE-09` 🔴 | `AreaScopedManager` como `objects` nos 28 modelos com `area`, mantendo `all_objects` para migração/comando/backfill. App por app, começando por ofícios, roteiros e prestações | 6 |
| `BE-10` 🔴 | App `justificativas` sem `area`: lista, pickers e exclusão por URL expõem todos os tenants (`justificativas/selectors.py:20,44,48`, `views.py:32`, `forms.py:105`) | 2 |
| `DB-01` 🟠 | Tabela de diárias é **nacional por decisão documentada**, e a tela que a edita não tem portão de papel: qualquer EDITOR altera valor de todas as áreas (`cadastros/views.py:620`) | 1,5 |
| `DB-02` 🔴 | `area` anulável em 27 dos 28 modelos; sem área ativa, `filter_queryset_by_area` devolve o balde `area IS NULL` inteiro (`core/tenancy.py:63`) | 5 |
| `DB-03` 🟠 | Limpeza de rascunhos apaga rascunho de outra área (`roteiros/services/roteiro_editor.py:317`) | 1 |
| `DB-04` 🟡 | Cache de artefato documental não recorta por área — risco latente, sem caminho alcançável hoje (`documentos/services/document_cache.py:105`) | 1 |
| `DB-05` 🟠 | Placa de viatura e nome de modelo de justificativa são únicos globalmente | 1,5 |

> **`DB-02` foi reescrito em 07/08/2026** (exigência do `NOVO-34`): não é dívida uniforme de
> 27 modelos, são **três grupos** — operacional (`NOT NULL` com backfill antes; `Evento.save()`
> já deriva a área, era o único dos oito que não derivava), catálogo com padrão global
> (`NOT NULL` só depois de decisão de produto) e global por projeto
> (`ConfiguracaoNumeracaoOficio`: a linha sem área **é** o mecanismo — `NOT NULL` fora de
> questão). O enunciado vigente, com a ordem do que resta, está na linha do `DB-02` do
> catálogo; a medição de produção chega sozinha pelo gate do `NOVO-12` a cada deploy.

> **`DB-01` foi reescrito pela verificação de 05/08 e o enunciado original estava invertido.** Ele
> pedia acrescentar `area` à `TabelaDiaria` — exatamente o que `cadastros/selectors.py:24-28`
> documenta como decisão deliberada, para impedir que duas áreas cobrem valores diferentes pela
> mesma viagem. **Não fragmentar a tabela.** O trabalho é o portão de permissão, e casa com o
> `BE-19` (`require_area_role` com zero usos). O esforço cai de 4 dias para 1,5.

**Ordem interna:** `DB-03` e `BE-04`/`BE-05` primeiro (correções pontuais), depois `BE-09`
(o manager), e só então `DB-02` (`NOT NULL`), que depende do backfill estar provado.

**Gate:** para cada modelo migrado, um teste de duas áreas; `select count(*) where area_id is
null` por tabela colado no PR; a suíte inteira verde sem `all_objects` aparecer em código de
request.

### B2 — O banco passa a defender os dados · 8 dias · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `DB-06` ✅ | ~~Remover um servidor da equipe do ofício apaga em cascata comprovante e assinatura já coletados (`prestacoes_contas/signals.py:33`)~~ — **fechado**: `sair_da_equipe` marca em vez de apagar quem tem dados coletados | 3 |
| `DB-07` ✅ | ~~2 `CheckConstraint` em 54 modelos: 9 pares início/fim sem ordem garantida, dinheiro negativo aceito~~ — **fechado**: 26 constraints, 24 novas, provadas por inversão individual (a última veio com o `NOVO-36`) | 3 |
| `DB-08` 🟠 | Coleções ordenadas aceitam duplicata: destino repetido é contado duas vezes pelo motor de diárias e impresso duas vezes | 2 |

**Limite 4 do `AGENTS.md` vale integralmente aqui:** cada migração entra com a query de validação
dos dados existentes no corpo do PR e o procedimento de backup citado.

**Gate para `DB-06`:** teste que remove um servidor com anexo e assinatura e exige que ambos
sobrevivam. — **cumprido** por `prestacoes_contas/test_remocao_equipe.py::GateDB06Tests`.

> **`DB-06` fechado. O que a correção resolveu, e o que ela deliberadamente não resolveu.**
>
> Reprodução antes de mexer, com 2 servidores, 1 comprovante e 1 assinatura, após
> `oficio.servidores.set([s1])`: `PrestacaoServidor=1, anexos=0, assinaturas=0`, e o arquivo do
> comprovante **ainda no disco**, sem dono. Igual ao que o catálogo mediu.
>
> A troca não foi "nunca apagar": foi **apagar só o que não custa nada**. Linha sem trabalho de
> usuário continua sendo excluída — é o que impede a prestação de exibir a equipe semeada de outro
> ofício, que era o defeito que este sinal existe para resolver. Linha com comprovante, assinatura,
> número de solicitação, valor de diária, data, status ou arquivamento é marcada (`removida_em`) e
> some das telas sem perder nada. Readicionar o servidor à equipe desfaz a marca e devolve tudo —
> é o "desfazer" que o defeito dizia não existir.
>
> **O filtro mora no `_default_manager`**, não espalhado pelos ~15 pontos de leitura. Foi decisão de
> engenharia, não de estilo: `view_common.py:257-262`, `views.py:730` e `selectors.py:100` fazem
> `prefetch_related` **por string**, que não tem onde receber um filtro. É o inverso da decisão do
> `BE-09` (onde o `_default_manager` fica irrestrito) porque o recorte aqui é do próprio registro,
> não do observador — e a diferença está escrita no docstring de `PrestacaoServidorAtivosManager`,
> travada por teste (`test_default_manager_name_continua_no_manager_que_filtra`).
>
> **As dez cláusulas de `tem_dados_coletados()` foram provadas por inversão, uma a uma.** Na
> primeira rodada, apagar a cláusula da assinatura deixava a suíte **verde** — o teste do gate cria
> anexo *e* assinatura, então nenhum dos dois decidia nada. Sétimo caso desta refatoração em que um
> teste meu não provava o que dizia provar. Corrigido com um caso por sinal, com ofício novo em cada
> um (a primeira versão reaproveitava a prestação e o dado do caso anterior mantinha os seguintes
> verdes).
>
> **Fora do escopo, registrado como `NOVO-35` — e depois fechado.** `PrestacaoServidor.servidor` é
> `CASCADE`, então excluir o servidor no cadastro continuava apagando o comprovante. Medido: 1 anexo
> → 0 após `servidor.delete()`. A correção não trocou o `CASCADE` por `PROTECT` (que bloquearia 3 de
> 4 servidores no banco de dev contra 1 de 4 da regra por dado): guarda no serviço, com predicado
> próprio `tem_prova_irrefazivel()`, mais estreito que o `tem_dados_coletados()` daqui. A diferença
> não é estilo — `tem_dados_coletados` inclui `status`, que é **coletivo**, e um colega salvando o
> despacho tornaria indelével um servidor semeado por engano.
>
> Aquela correção também revelou uma armadilha que **este** ID criou: o acessor reverso
> `servidor.prestacoes_servidor` herda o `_default_manager` e esconde as linhas com `removida_em` —
> que são, por construção, exatamente as que têm dados. Uma guarda pela relação reversa bloquearia
> zero. Está travado por teste em `cadastros/tests/test_exclusao_de_servidor.py`.


> **`DB-07` fechado. O que o levantamento achou além do enunciado.**
>
> Introspecção sobre os 54 modelos, não a lista do catálogo: `Roteiro` tem **quatro** datetimes em
> cadeia (`saida_dt` → `chegada_dt` → `retorno_saida_dt` → `retorno_chegada_dt`) e `RoteiroTrecho`
> tem um par próprio — nenhum dos dois estava nos "9 pares". Total final: 11 constraints de ordem e
> 12 de sinal, mais as 2 que já existiam — o décimo segundo elo de ordem saiu do PR como `NOVO-36`,
> **e voltou junto com a correção dele**, fechando a cadeia em 26.
>
> **Os testes escrevem por `queryset.update()`, não por `save()`.** É o caminho que o defeito
> descreve — o que escapa da validação de formulário. Um teste que passasse pelo `save()` poderia
> ficar verde sem constraint nenhuma, porque a normalização do modelo corrigiria o valor antes de
> ele chegar ao banco.
>
> **Duas inversões, e uma delas me pegou.** Tirar as 23 constraints das migrações reprova 24 casos,
> um por constraint, cada um se nomeando; trocar `gte` por `gt` reprova 22 casos de limite. A que
> pegou: as condições nasceram com um ramo `Q(campo__isnull=True) |` que eu justifiquei no docstring
> como necessário ao caminho Python do `full_clean()`. Removido o ramo, **nada mudou em nenhuma das
> duas camadas** — era inerte. Saiu do código; a garantia virou teste.
>
> **`scripts/validar_constraints_db07.py` é o limite 4 do `AGENTS.md` como procedimento**, não como
> anexo: lê as constraints por introspecção — a mesma verdade que as migrações aplicam, não uma
> tradução manual delas — e sai com código 1 se alguma linha existente violar. Contra o banco de
> desenvolvimento: 0 violações em 25 constraints. **Contra produção, ainda não rodado** — e é lá que
> a resposta importa.

### B3 — Consulta e índice · 8,5 dias · risco médio

Esta etapa é a que o [`PLANO_DESEMPENHO.md`](PLANO_DESEMPENHO.md) mede e não executa.

| ID | Defeito | Ganho medido | Dias |
|---|---|---|---:|
| `DB-09` 🟠 | Lista de roteiros agrega antes do `LIMIT` (`roteiros/selectors.py:36`): trocar `annotate(Count)+exclude` por `Exists()` correlacionado | 24.000 roteiros: **56,6–127,7 ms** em duas medições | 2 |
| `DB-10` 🟡 | Falta índice composto para a ordenação real das listas (`OrdemServico.Meta.indexes` vazio, ofícios idem) | **13× a 29×** em duas medições | 0,5 |
| `DB-11` ✅ | A pior busca livre expandia 20.000 Termos em ~60.000 linhas por três M2M e rodava três vezes; virou `Exists()` por origem + contagem reutilizada, com cenário permanente no `PF-07` | busca de Termos em 20.000: **1.807,9 → 391,4 ms (4,62×)** | 3 |

> **Os três números foram medidos duas vezes, por auditores independentes, e as faixas acima são as
> duas medições.** Onde divergiram, a promessa que vale é a mais conservadora. O `DB-09` é o caso
> mais relevante: a segunda medição deu menos da metade do tempo da primeira, com o mesmo volume e
> o mesmo `rows=48.000` nos dois `Seq Scan` — o padrão estrutural está confirmado, o ganho é menor
> do que o catálogo prometia. Achado extra da verificação no `DB-10`: o índice único **parcial** já
> existente não pode ser usado pelo planner nesta consulta, o que reforça a necessidade do
> composto.
| `DB-12` 🟡 | Trilha de auditoria sem índice por área/período, sem expurgo, com um `SELECT` extra por `save` (`core/audit.py:78,154`) | — | 3 |

**Gate:** `EXPLAIN (ANALYZE, BUFFERS)` antes e depois no corpo do PR, com o mesmo volume semeado.

### B4 — Camadas e duplicação · 17,5 dias · risco alto

| ID | Defeito | Dias |
|---|---|---:|
| `BE-11` 🟠 | Editor de roteiro em 3 cópias (`roteiros/views.py:203,311` e `oficios/route_views.py:100`); só duas tratam roteiro duplicado | 3 |
| `BE-12` 🟠 | `wizard_roteiro` concentra a regra de vínculo/cópia de roteiro na view: 181 linhas, 24 ramos, 4 gravações | 2 |
| `BE-13` 🟠 | `roteiros/roteiro_logic.py`: 1.779 linhas, 57 funções privadas, fora do contrato de camadas, importado pelos services | 4 |
| `BE-14` ✅ | 48 sites de persistência em módulo de view sem service e sem transação — fechado em 6 fatias; o último caminho multigravação, identificação de Evento (~12 writes/6 tabelas), virou um service atômico com rollback provado nos cinco documentos vinculáveis | 3 |
| `BE-15` 🟡 PARCIAL | Numeração: mecânica comum pronta; OS agora reaproveita somente lacuna registrada por exclusão, com rollback; falta o Plano de Trabalho entrar na reserva/retry comum | 2 |
| `BE-16` 🟡 | Abstrações adotadas pela metade: paginação em 2 de 14 listas, exclusão protegida em 3 de 48 sites, 6 cópias de `_pagination_pages` | 2 |
| `BE-17` 🟡 | `core/views.py` é 75% fixture de UI Lab (947 de 1.261 linhas), e existem **dois** UI Labs paralelos | 1,5 |

**`BE-11`, `BE-12` e `BE-13` são a mesma superfície.** Fazer na ordem: editor primeiro (reduz o
tamanho do problema), `wizard_roteiro` em seguida, fatiar `roteiro_logic.py` por último, uma
responsabilidade por PR. **Plan mode obrigatório** nos três — mexem em roteiro e diárias.
`BE-15` exige teste de concorrência com duas threads antes de qualquer mudança.

### B5 — Observabilidade e autorização · 4 dias · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `BE-18` 🟠 | `core.errors.capture` tem 64 chamadas, **todas** em `integracoes/google_drive`; `prestacoes_contas` tem 6.739 linhas e não emite um único log. 157 `except Exception`, 72 sem log nenhum | 2,5 |
| `BE-19` 🟠 | `require_area_role` tem **zero** usos; `PAPEL_ADMIN` é decorativo — um EDITOR tem os mesmos poderes de um ADMIN | 1,5 |

**Gate de `BE-18`:** regra nova no `audit_django_architecture.py` reprovando `except` sem `capture`
nem `logger`, com catraca que só desce.

### B6 — Higiene e decisões pendentes · 4 dias · risco baixo

| ID | Defeito | Dias |
|---|---|---:|
| `BE-20` ✅ | `diario_bordo` é app-casca: 33 linhas de Python, 1 rota não linkada em template nenhum, funcionalidade real mora em `prestacoes_contas`. Piso de cobertura de 91,17% mede 33 linhas | 0,5 |
| `BE-21` ✅ | Presenter morto que promete funcionalidade inexistente: `oficios/presenters.py:621` devolve "DOCX (em breve)"/"PDF (em breve)" e tem zero chamadores | 0,25 |
| `BE-22` ✅ | ~~10 arquivos `.py` com BOM UTF-8 (todos em `cadastros/`), que quebram `ast.parse` em ferramenta de análise~~ — **fechado**; eram 11, e o remendo `utf-8-sig` estava na régua do `S-06` | 0,5 |
| `BE-23` 🟡 PARCIAL | 307 de 433 rotas nomeadas fora do vocabulário do `PADRAO_APP.md`; 5 apps em português, 2 em inglês — **as 28 com sufixo CRUD em português foram renomeadas, com catraca**; os 75% sem sufixo nenhum seguem abertos | 1 |
| `BE-24` 🟡 | Repositório com 106 MB de *pack*, 89 MB em `screenshots/`; 175 arquivos rastreados que não deveriam estar (`tmp/`, `media_teste/`, `migration_backups/*.dump`, `logs/`, `.tmp-*/`, `_tmp_check*.py`, `tatus`, `.codex-*.log`) | 1 |
| `BE-25` 🟡 | Decidir qual UI Lab é o vigente (`ui_lab2`, 656 LOC + 18 templates, contra `templates/dev/ui_lab`, 19 templates) e apagar o outro com a prova de grep do `AGENTS.md` §3.6 | 0,75 |

`BE-23` não viaja com nenhuma outra etapa: renomear rota exige `urls.py` + `reverse()` +
templates + testes no mesmo PR.

---

## 3. Ordem e paralelismo

```
B0 (defeitos ao vivo) ──► B1 (área) ──► B2 (constraints) ──► B3 (índices)
                             │
                             └──► B4 (camadas) ──► B5 (observabilidade)

B6 (higiene) — a qualquer momento, em branch própria
```

**B0 antes de tudo**: são defeitos que o usuário encontra hoje e não dependem de nada.

**B1 antes de B2**: adicionar `NOT NULL` e `CheckConstraint` sobre um modelo cujo recorte de área
ainda vaza é lacrar a porta errada.

**B2 antes de B3**: constraint muda o plano de consulta; criar índice antes obriga a refazer a
medição depois.

**B4 pode correr em paralelo com B2/B3** — camadas e esquema são superfícies disjuntas —, mas
`BE-11`/`BE-12`/`BE-13` nunca em paralelo entre si.

**Total: 63,5 dias-pessoa.**

## 4. O que este plano não faz

- **Não reescreve `prestacoes_contas` do zero.** É o app com mais dinheiro e assinatura pública;
  entra por fatias com teste de caracterização antes de cada uma.
- **Não muda a regra de diárias.** O motor foi fechado no ciclo de julho, com os demonstrativos
  oficiais travados por teste. `DB-13` (composição da diária como texto livre, sem vínculo com a
  tabela que produziu o valor) fica catalogado e **fora desta rodada** — mexer nele é abrir de
  novo a regra de dinheiro, e o ganho é de auditabilidade, não de correção.
- **Não decide a arquitetura de configurações.** A proposta está em
  `docs/historico/2026-07-refactor/planos/PROPOSTA_CONFIGURACOES.md`; a posição dela na fila está
  no plano mestre.
