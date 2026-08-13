# Plano de desempenho

**Medido em 05/08/2026.** Todos os números deste documento vieram de execução, não de leitura de
código. Os comandos estão em cada seção, para que qualquer pessoa reproduza e conteste.

**Regras de conduta:** [`AGENTS.md`](../AGENTS.md) · **Ordem das etapas:**
[`PLANO_MESTRE_REFATORACAO.md`](PLANO_MESTRE_REFATORACAO.md) · **Defeitos:**
[`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md) (prefixo `PF`)

---

## 1. O que **não** é problema

Esta seção existe para impedir trabalho inútil. Três suspeitas clássicas foram medidas e
refutadas; qualquer proposta que volte a prometê-las está vendendo trabalho já feito.

### 1.1 N+1 nas listas: resolvido — mas isso não é o mesmo que "rápido"

Teste de escala — a **contagem** de queries cresce com o volume de registros?

| rota | 20 registros | 200 registros | veredicto |
|---|---:|---:|---|
| `/oficios/?aba=atuais` | 17 queries | **17 queries** | plana |
| `/roteiros/` | 11 queries | **11 queries** | plana |
| `/cadastros/servidores/` | 9 queries (200 reg.) | **9 queries** (600 reg.) | plana, pagina 25/pág. |

O ciclo de julho fez esse trabalho. As listas medidas paginam e não emitem query por registro.

**Onde eu estava errado.** Contagem plana não quer dizer consulta barata. A medição acima usou
200 registros; com **24.000** o quadro muda, e a diferença está no `EXPLAIN`, não na contagem:

| medição com 24.000 roteiros (2.000 na área ativa) | 1ª medição | verificação independente |
|---|---|---|
| lista de roteiros, 2.000 registros | 23,9 ms | — |
| lista de roteiros, 8.000 registros | 37,6 ms | — |
| lista de roteiros, 24.000 registros | 127,7 ms | **56,6 ms** |
| busca de ofícios (`q="ambi"`), `Seq Scan` em 24.000 linhas | 35,7 ms | **31,3 ms** |
| lista de OS com índice `(area, -ano, -numero)` | 1,965 → 0,067 ms (29×) | 0,600 → 0,046 ms (**13×**) |

Os três foram medidos duas vezes, por auditores independentes. **A promessa que vale é a coluna
da direita**, mais conservadora. O padrão estrutural — agregação antes do `LIMIT`, varredura
sequencial na busca, ausência de índice composto — está confirmado nas duas.

O custo cresce com o **banco inteiro**, não com a área do usuário: cada área paga pelo volume
das outras. As causas são de modelagem, não de view — `annotate(Count(...))` + `exclude(...)`
forçando agregação antes do `LIMIT`, ausência de índice composto para a ordenação real e 80
filtros `__unaccent__icontains` sem nenhum índice GIN/trigram (0 em 390 índices).

> **Atualização de 12/08/2026 (`DB-11`).** O diagnóstico por contagem de lookup acertou o sintoma
> e errou a solução do pior caso. Cinco índices GIN foram escolhidos pelo planner e deram **1,00×**
> na busca de Termos, porque o `OR` atravessava três M2M, expandia 20.000 Termos para ~60.000 linhas
> e era executado três vezes. A correção virou as M2M em `Exists()` e reutilizou a contagem das
> abas no paginador: **1.807,9 → 391,4 ms (4,62×)** no PostgreSQL 16, com 20.000 registros. A régua
> agora inclui permanentemente `termos:index:busca`; índice de texto futuro precisa demonstrar
> ganho no cenário concreto, não nasce da contagem global de `icontains`.

Essas correções estão no [`PLANO_BACKEND.md`](PLANO_BACKEND.md), porque são mudanças de esquema
sujeitas ao limite 4 do `AGENTS.md` (migração exige validação de dados). Aqui elas entram como
**régua**: a Etapa D1 mede com volume, não com 200 linhas.

> **Ressalva:** só três domínios foram semeados na medição de contagem. Termos, Prestações,
> Eventos, Planos de Trabalho, OS e Justificativas responderam com base vazia — os números delas
> não valem, e medi-las é o primeiro item da Etapa D1.

### 1.2 Geração de documento: já é assíncrona

`scripts/audit_django_architecture.py` reporta **0** ocorrências de geração documental síncrona
em view, e a suíte confirma o desenho por job com polling
(`oficios/tests/test_documento_pdf_erro_amigavel.py`, teste
`test_baixar_oficio_docx_entrega_resultado_do_job`). Não há request bloqueando em `docxtpl`.

### 1.3 Peso de rede dos assets: aceitável

| arquivo | bruto | gzip | brotli |
|---|---:|---:|---:|
| `static/css/shell.bundle.css` | 512 KB | 77 KB | **60 KB** |
| `static/js/shell.bundle.js` | 264 KB | 55 KB | **46 KB** |

`config/staticfiles.py` usa `CompressedManifestStaticFilesStorage` do WhiteNoise, com `brotli`
instalado. **No fio são ~106 KB, não 776 KB.** Um plano que prometa "cortar 776 KB de download"
está errado sobre o próprio diagnóstico. O custo está em outro lugar — §2.1 e §2.2.

---

## 2. O que **é** problema, medido

Ordenado por ganho ÷ esforço.

### 2.1 `PF-01` — 192 KB de SVG repetido por página de lista

`/oficios/?aba=atuais` com **20 ofícios** (uma página):

| item | contagem | peso |
|---|---:|---:|
| HTML total | 12.545 linhas | **425 KB** |
| `<svg>` inline | **378** | **192 KB — 45% da página** |
| `<path>` | 854 | — |
| menus de ação `cv-action-menu` | **60** (3 por card) | — |
| itens de menu `cv-action-menu__item` | **200** (10 por card) | — |

São ~19 ícones por card, cada um emitido como `<svg>` completo, com os mesmos atributos
repetidos literalmente (`fill="none" stroke="currentColor" stroke-width="1.75"
stroke-linecap="round" stroke-linejoin="round"`).

**Causa:** `templates/components/ui/icons/icon.html` — 222 linhas de `{% if %}/{% elif %}`
(36 ramos) que emitem o `<svg>` inteiro a cada inclusão. Além do peso, cada um dos 378 ícones
faz o motor de template percorrer a cadeia de ramos.

**Correção:** folha de símbolos incluída uma vez por página
(`<svg hidden><symbol id="cv-icon-edit" viewBox="0 0 24 24">…</symbol>…</svg>`) e
`<svg class="cv-icon"><use href="#cv-icon-edit"></use></svg>` nos pontos de uso. O ícone cai de
~500 bytes para ~60, e os 36 ramos viram um lookup.

**Ganho esperado:** −180 KB de HTML por página de lista; menos tempo de template.
**Esforço:** 2–3 dias. **Risco:** baixo — `cv-icon` continua sendo a classe de estilo.

Este é o `R-02` da Etapa 8 do ciclo antigo, que ficou pendente enunciado como "sistema de
ícones (208 linhas de if/elif, 17 órfãos)". O que faltava era o preço.

### 2.2 `PF-02` — 90% do CSS entregue não casa com a página

Medido no Chromium real (CDP: `CSS.startRuleUsageTracking` + `CSS.getStyleSheetText` por folha):

| rota | nós de DOM | CSS entregue | casado | uso |
|---|---:|---:|---:|---:|
| `/` | 235 | 664 KB | 78 KB | 11,8% |
| `/oficios/` | 424 | 809 KB | 84 KB | 10,4% |
| `/roteiros/` | 275 | 785 KB | 81 KB | 10,3% |
| `/termos/` | 338 | 800 KB | 81 KB | **10,1%** |
| `/prestacoes-contas/` | 399 | 816 KB | 84 KB | 10,3% |
| `/eventos/` | 453 | 786 KB | 84 KB | 10,7% |

Folhas na rota `/prestacoes-contas/`:

| folha | tamanho | uso |
|---|---:|---:|
| `shell.bundle.css` | 511 KB | **8,1%** |
| `oficios.css` | 106 KB | **0,0%** |
| `forms.css` | 34 KB | 0,0% |
| `cv-select.css` | 28 KB | 28,2% |
| `prestacoes_contas.css` | 26 KB | 0,0% |
| `theme.css` | 24 KB | 66,6% |
| `roteiros-list.css` | 15 KB | 0,0% |
| `tokens.css` | 11 KB | 100,0% |

O custo não é download (§1.3) — é o navegador construir e manter uma árvore de ~2.600 regras
para casar ~10% delas, em toda navegação.

**Correção:** é obra do [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md) (`UI-*`), não deste plano.
Aqui fica a **métrica de aceite**: uso de CSS por rota acima de 35% ao fim da reconstrução.

> **Ressalva:** o banco desta sessão estava vazio; as telas tinham 134–453 nós. Com listas
> cheias o número de nós sobe e o uso de CSS sobe um pouco — mas não muda a ordem de grandeza,
> porque a maior parte das regras não pertence ao domínio da página.

### 2.3 `PF-03` — toda requisição escreve na tabela de sessão

`config/settings/base.py:111` — `SESSION_SAVE_EVERY_REQUEST = True`.

Custo fixo de uma requisição autenticada trivial (`/health/`, sem template de aplicação):
**7 queries**, das quais três são a escrita da sessão:

```
SELECT django_session          -- leitura da sessão
SELECT auth_user               -- usuário
SELECT usuarios_vinculousuarioarea  -- vínculo de área
SELECT 1                       -- health check
BEGIN / UPDATE django_session / COMMIT   -- gravação em TODA requisição
```

Toda página, todo XHR de autosave, todo polling de documento abre uma transação de escrita.

**O que a flag compra:** expiração deslizante — a sessão de 8 h
(`SESSION_COOKIE_AGE = 28800`) reinicia a cada atividade. Desligar sem mais nada faz a sessão
expirar 8 h **depois do login**, e o usuário cai no meio do trabalho.

**Correção proposta:** manter o comportamento e tirar a escrita do caminho quente — backend
`cached_db` (`SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"`) com cache local,
ou renovar só quando faltar menos de 1 h para expirar. **Decisão de produto necessária** antes
de mexer: qual é o comportamento de expiração desejado.
**Esforço:** 1–2 dias + a decisão. **Risco:** médio — mexe em sessão de usuário logado.

### 2.4 `PF-04` — 60 menus de ação renderizados para 20 cards

Na mesma página de Ofícios: 60 blocos `cv-action-menu` e 200 `cv-action-menu__item`, ou seja
3 menus por card com 10 itens, todos no HTML inicial, quando no máximo um fica aberto por vez.

**Correção:** um único menu por página, preenchido no clique a partir dos `data-*` do card
(o motor de menu já existe em `static/js`). **Ganho:** parte dos 425 KB e menos nós de DOM.
**Esforço:** 2–3 dias. **Risco:** médio — mexe em interação já testada; exige teste de regressão
de teclado e leitor de tela.

### 2.5 `PF-05` — a lista de Ofícios leva mais de 100 ms no servidor

Com 17 queries planas e 20 cards, o tempo não está no banco:

| rota | ms no servidor |
|---|---:|
| `/oficios/?aba=atuais` | **115–166** (três medições) |
| `/cadastros/servidores/` | 27 |
| `/justificativas/` | 46 |
| `/roteiros/` | 20 |

> **Faixa, não número.** A verificação independente mediu 115,1 ms e 165,9 ms nas mesmas
> condições — variação de ~43% entre execuções. Tempo de parede é sensível ao ambiente; **a
> contagem de 17 queries é o número sólido aqui**, e o teto do CI deve ser generoso o bastante
> para não virar teste instável.

É consequência direta de `PF-01` e `PF-04` — renderizar 378 ícones e 60 menus. Fica catalogado
à parte porque é a **métrica de aceite** deles: a rota precisa cair para a faixa das outras
listas (< 40 ms) sem que a contagem de queries suba.

> **Parcial em 13/08/2026.** A rota caiu de 13 para 9 consultas e de 125,5 para 76,7 ms no
> volume 200; em 20.000 registros, 1.554,4 virou 235,6 ms. A eliminação das contagens repetidas
> resolveu a escala principal e baixou as catracas, mas o aceite de 40 ms segue aberto. O
> processador de navegação repetido por componentes Cotton também ganhou cache por requisição;
> sua medida final será registrada pelo CI da fatia.

### 2.6 `PF-06` — queries duplicadas em duas rotas

`/usuarios/` emite **2** queries idênticas repetidas; `/prestacoes-contas/`, **1**. Volume
pequeno, mas é sintoma de consulta refeita em camada diferente (selector e presenter pedindo a
mesma coisa). **Esforço:** 0,5 dia cada. **Risco:** baixo.

### 2.7 `PF-07` — cinco listas nunca foram medidas com volume

Termos, Prestações de Contas, Eventos, Planos de Trabalho, Ordens de Serviço e Justificativas
responderam com base vazia. O ciclo antigo registrou que **Termos tinha 54 queries por página**
(`termo_cadastro_assinado_info` consultando por linha) e a correção nunca foi confirmada.
Enquanto não houver medição com volume, não se sabe.

**Correção:** semear cada domínio e medir, antes de qualquer otimização. É a Etapa D1.

---

## 3. As etapas

| # | Etapa | Defeitos | Dias | Risco | Gate |
|---|---|---|---:|---|---|
| **D1** ✅ | **Régua de desempenho** — `scripts/medir_desempenho.py` no repositório, semeando cada domínio **em dois volumes (200 e 20.000)**, medindo queries, tempo, KB de HTML e uso de CSS por rota; teto por rota no CI | `PF-07` | 3–4 | baixo | O script roda no CI e falha se qualquer rota passar do teto declarado, nos dois volumes |
| **D2** | **Folha de símbolos de ícone** | `PF-01` | 2–3 | baixo | `/oficios/` abaixo de 250 KB de HTML; suíte verde; telas conferidas nos dois temas |
| **D3** 🟠 | **Menu de ação sob demanda** | `PF-04`, `PF-05` | 2–3 | médio | `PF-04` entregue; `/oficios/` em 76,7 ms e 165,6 KB, ainda acima do aceite de 40 ms / 150 KB |
| **D4** | **Sessão fora do caminho quente** | `PF-03` | 1–2 | médio | Requisição autenticada trivial sem `UPDATE django_session`; decisão de expiração registrada |
| **D5** | **Consultas duplicadas** | `PF-06` | 1 | baixo | Zero query repetida nas rotas medidas |
| **D6** | **Aceite do CSS** (depois do `PLANO_FRONTEND`) | `PF-02` | — | — | Uso de CSS acima de 35% em todas as rotas medidas |

**Total próprio: 9–13 dias-pessoa.** O `PF-02` não soma porque o trabalho está no plano de front;
aqui ele só tem a régua.

## 4. Ordem e dependências

```
D1 (régua) ──┬──► D2 (ícones) ──► D3 (menus) ──► [aceite PF-05]
             ├──► D4 (sessão)
             └──► D5 (duplicadas)
                                   PLANO_FRONTEND ──► D6 (aceite CSS)
```

> **D1 fechada em 05/08.** A régua está em `scripts/medir_desempenho.py`, os tetos em
> `scripts/tetos_desempenho.json` e o gate no `tests.yml`. Ela achou de saída um vazamento
> entre áreas (`NOVO-06`), uma tela de 15 MB (`NOVO-07`) e N+1 de 296/138/55 consultas em três
> listas (`NOVO-08`) — nenhum deles visível na linha de base, que mediu com o banco vazio.
> O `NOVO-08` é trabalho de desempenho e entra nesta fila; o `NOVO-06` é vazamento de dado
> entre áreas e **não espera a fila de desempenho**.
>
> **Os três fechados em 06/08.** O `NOVO-07` foi o que mais rendeu: `justificativas:index` saiu de
> **5.398 KB para 142,5 KB** com 20.000 ofícios, e a diferença entre os volumes 200 e 20.000 — que
> era 27× — virou 0,3%. Consultas da rota: 17 → 10. Tetos rebaixados em
> `scripts/tetos_desempenho.json`, que é onde a catraca fica.

**D1 vem primeiro e não é negociável.** Sem a régua no CI, toda etapa seguinte é afirmação sem
prova, e a regressão volta no PR seguinte sem ninguém ver. D2 antes de D3 porque o menu carrega
ícones: trocar o ícone primeiro reduz o tamanho do problema do menu.

## 5. O que este plano não faz

- **Não introduz cache de página nem de fragmento.** Com queries planas e tempo dominado por
  render de ícone, cache seria esconder o problema e criar invalidação para manter.
- **Não mexe em índice nem em consulta de banco.** O ganho existe e é grande (§1.1), mas toda
  correção ali é mudança de esquema ou de selector, sujeita ao limite 4 do `AGENTS.md`. Mora no
  [`PLANO_BACKEND.md`](PLANO_BACKEND.md); aqui fica só a régua que prova o ganho.
- **Não promete número de Lighthouse.** A régua é a do §3: queries, milissegundos no servidor,
  KB de HTML e uso de CSS — tudo reproduzível por comando, sem depender de rede externa.
