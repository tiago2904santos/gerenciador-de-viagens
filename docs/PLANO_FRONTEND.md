# Plano de refatoração do frontend

**Medido em 05/08/2026.** CSS medido por extração e por navegador real (Chromium via CDP);
JavaScript medido por varredura e leitura dirigida. Nada aqui foi herdado das auditorias de julho.

**Regras de conduta:** [`AGENTS.md`](../AGENTS.md) · **Ordem das etapas:**
[`PLANO_MESTRE_REFATORACAO.md`](PLANO_MESTRE_REFATORACAO.md) · **Defeitos:**
[`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md) (prefixos `UI`, `HT`, `JS`)

---

## 1. O estado real

**O JavaScript está melhor do que a fama.** O que o projeto decidiu automatizar, funcionou: zero
`fetch()` cru, zero `alert()`/`confirm()` nativos, zero duplicação de `debounce`/`escapeHtml`/
`normalize`, bundle em dia com as fontes. Os 392 avisos do auditor de CI são **todos de CSS** —
nenhum é de JS.

**O CSS é onde está o peso.** De 2.612 classes declaradas, **937 não aparecem em lugar nenhum** —
nem em template, nem em JS, nem em Python. São 981 blocos somando 168 KB. E o que sobra também não
está bem: o navegador recebe 664–816 KB por página e casa **~10%**.

**O problema não é tamanho, é fronteira.** `oficios.css` (106 KB) é carregado na tela de Prestações
de Contas e usado **0,0%** ali. Não é descuido de um template: o estilo dos componentes
compartilhados mora dentro dos arquivos de domínio, então quem quer o componente leva o domínio
junto. São 54 imports cruzados em 26 templates.

**E o tema escuro é uma camada de exceção.** `theme-dark-components.css` tem 5.843 linhas e 190
`!important` — o tema não é resolvido por token, é resolvido sobrescrevendo componente por
componente. Nove arquivos definem `--color-*`.

**O que o CI não vê.** O auditor cobre 5 dos ~9 invariantes do projeto. Fora do alcance dele
ficaram um **XSS real** (`JS-01`), 15 de 18 componentes sem `destroy` no ciclo de vida (`JS-02`) e
o acoplamento de lógica a nome de classe (`JS-06`) — que é justamente o que decide a ordem deste
plano.

---

## 2. A ordem, e por que ela não é negociável

```
F1 (JS: desacoplar do nome de classe)  ──►  F2 (fundação: ícones + componentes)
                                              │
F0 (XSS e erro silencioso) ─ a qualquer hora  ├──►  F3 (poda do CSS morto)
                                              │        │
                                              │        ▼
                                              └──►  F4 (tokens e tema)
                                                       │
                                                       ▼
                                                 F5 (reconstrução por domínio)
```

**`JS-06` vem antes de qualquer renomeação de CSS.** `classList.contains("cv-search-picker")`
aparece 10 vezes em 9 arquivos de página. Renomear essa classe na etapa de CSS quebraria o
roteamento de foco em 6 telas — em silêncio, sem erro no console e sem teste que pegue, porque não
existe teste de JS (`JS-03`). Esta é a dependência que define tudo: **o JS larga o nome de classe,
depois o CSS pode mexer nos nomes.**

**A poda (F3) vem antes dos tokens (F4).** Não faz sentido reconciliar nove camadas de token sobre
168 KB de regra morta.

**A reconstrução por domínio (F5) vem por último**, porque só depois de F2 se sabe quais
componentes existem, e só depois de F4 existe um vocabulário de token único para escrevê-los.

---

## 3. As etapas

### F0 — Defeitos de segurança e de silêncio · 1,5 dia · risco baixo

Independentes de tudo; podem entrar junto da fase 0 do plano mestre.

| ID | Defeito | Dias |
|---|---|---:|
| `JS-01` 🔴 | XSS: `pasta.name` cru em `aria-label` (`gdrive_config.js:112,117`), enquanto a linha 114 escapa a mesma variável | 0,25 |
| `HT-01` 🔴 | Foco de teclado invisível em `input`/`select`/`textarea` no sistema inteiro, inclusive no login | 1–2 |
| `JS-04` 🟠 | `.then()` sem `.catch` no editor de roteiros: falha de rede na estimativa de distância não avisa nada (`editor/index.js:790-822`) | 0,5 |
| `HT-09` ⚪ | Login sem skip link e sem `aria-describedby` no erro de campo | 0,5 |
| `JS-11` ⚪ | `maskCep` duplicada e `onlyDigits` em 4 cópias | 0,25 |
| `JS-12` ⚪ | `CV.registry` e `CV.componentRegistry` são o mesmo objeto | 0,25 |

**Gate:** teste que prova o escape (entrada com `"` e `<script>`); o `JS-04` verificado com a rede
derrubada; o `HT-01` conferido com navegação por Tab em tema claro e escuro, com print no PR.

### F1 — O JS larga o nome de classe · 5 dias · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `JS-06` 🟡 | Trocar `classList.contains("cv-search-picker")` por `data-entity-picker-root` nos 9 arquivos, no mesmo PR | 1 |
| `JS-05` 🟠 | Estender o auditor de CI: regra para `innerHTML` com interpolação sem `escapeHtml`, e para `registerEnhancer` sem `destroy` | 1,5 |
| `JS-02` 🟠 | `destroy` nos componentes que registram listener em `document`/`window` — `picker.js`, `cv-date-picker.js` e os demais 13 | 2,5 |

`JS-02` entra aqui e não depois porque a poda de CSS vai remover elementos do DOM em massa durante
a verificação, e é exatamente aí que listener órfão aparece.

**Gate:** a regra nova do auditor em vigor, com catraca que só desce; nenhum `registerEnhancer`
sem `destroy` fora da lista de exceções documentada.

### F2 — Fundação · 4 a 6 dias · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `PF-01` 🟠 | Folha de símbolos de ícone: 378 `<svg>` inline = 192 KB por página de lista, vindos de uma cadeia de 222 linhas de `if/elif` | 2–3 |
| `PF-04` 🟡 | Menu de ação sob demanda: 60 menus renderizados para 20 cards | 2–3 |
| `HT-*` | Componentes que faltam e duplicação estrutural — ver §4 | a definir |

Esta etapa **fixa quais classes existem**. É a fronteira: depois dela, o CSS estiliza um conjunto
conhecido.

### F3 — Poda do CSS morto · 4 a 6 dias · risco baixo

| ID | Defeito | Dias |
|---|---|---:|
| `UI-01` 🟠 | 935 classes candidatas em 981 blocos, 168 KB | 4–6 |

**Como fazer, e o que não fazer.** A contagem desta auditoria é o **mapa**, não a licença. O
`AGENTS.md` §3.6 exige prova de grep por arquivo apagado, colada no PR. Um arquivo por PR, na
ordem do peso: `oficios.css` (283 blocos, 47 KB), `dev/ui-lab-fields.css`, `dev/ui-lab-pages.css`,
`page-shell.css`, `roteiros.css`, `cv-buttons.css`.

**As duas exceções conhecidas** — `cv-search-picker--compact` e `cv-search-picker--vehicle` — são
montadas em tempo de execução por `static/js/components/picker.js:144` e **não podem ser
apagadas**. São as únicas: em todo o `static/js` existe um único padrão de classe dinâmica.

**Gate:** cada PR fecha com o auditor de front baixando, a suíte verde e uma passada visual nas
telas do domínio podado, nos dois temas.

### F4 — Tokens e tema · 6 a 8 dias · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `UI-03` 🟠 | Nove arquivos definem `--color-*`; `--step1-surface`/`--step1-panel` redefinidos 15 vezes cada. Reduzir a duas camadas: `tokens.css` (valores) e `03-theme-dark.css` (troca semântica) | 3–4 |
| `UI-02` 🟠 | `theme-dark-components.css` (5.843 linhas, 190 `!important`) deixa de ser camada de exceção e vira consequência do token | 3–4 |

Esta é a etapa que dá o maior ganho estrutural e a que mais exige olho na tela: contraste em tema
claro e escuro, componente a componente, com print antes/depois no PR.

**Gate:** `!important` fora do bundle caindo de 497; nenhum token definido em mais de dois
arquivos; contraste medido (não estimado) nos pares alterados.

### F5 — Reconstrução por domínio · a dimensionar · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `UI-04` 🟠 | 54 imports de CSS de outro domínio em 26 templates: extrair os componentes compartilhados dos arquivos de domínio | a definir |
| `JS-08` 🟡 | 11% do bundle atende menos de 1% das páginas: segundo bundle sob demanda | 2 |
| `JS-09` 🟡 | Tela de espera de documento carrega 264 KB para usar 3,3 KB | 0,5 |
| `JS-07` 🟡 | "Fechar ao clicar fora / Esc" reimplementado 4 vezes | 2 |
| `JS-10` 🟡 | Decidir os stubs do editor de roteiros: completar a extração ou removê-los | 0,25 ou 3+ |

O dimensionamento de `UI-04` depende de F2: quantos componentes precisam sair dos arquivos de
domínio só se sabe depois de saber quais componentes existem.

**Métrica de aceite da frente inteira:** uso de CSS por rota acima de **35%** (hoje: 10,1% a
11,8%), medido pelo mesmo script de `PF-02`.

### F6 — Teste de JavaScript · 5+ dias · risco baixo · etapa própria

`JS-03` — não há runner, não há `package.json`, não há um único teste para 25.492 linhas. Entra
como etapa própria, aditiva, começando pelos módulos mais críticos e mais testáveis:
`core/http.js`, o registry de `core/app.js`, `masks.js`, `components/collection.js`.

Enquanto isso não existir, **toda etapa deste plano depende de conferência visual** — o que é
justamente o motivo de F1 vir antes de qualquer renomeação.

---

## 4. HT — templates e acessibilidade

Os 96 componentes em `templates/components/` estão mais consolidados do que se supunha:
`page_header.html` tem 28 usos, `entity_card.html` atende 7 apps, `pagination.html` já traz
`aria-current` e `aria-live`, e **não há ORM disparado por template** (zero `.all`/`_set.all`
dentro de `{% for %}`). Os defeitos estão concentrados em acessibilidade de formulário.

| ID | Defeito | Dias | Etapa |
|---|---|---:|---|
| `HT-01` 🔴 | **Foco de teclado invisível em todo campo do sistema, inclusive no login** | 1–2 | F0 |
| `HT-02` 🟠 | Erro de campo sem `aria-describedby`/`aria-invalid`/`role="alert"` — no componente com 152 usos | 2–3 | F2 |
| `HT-03` 🟠 | Sem padrão único para erro de formulário: o componente correto tem **zero** usos em produção | 2 | F2 |
| `HT-04` 🟠 | `base.html` carrega ~153 KB de JS e ~37 KB de CSS de domínio em toda página | 2–3 | F5 |
| `HT-05` 🟡 | `empty_state.html` fixa `<h3>`, quebrando a ordem de headings em 9 das 10 listas | 0,5 | F2 |
| `HT-06` 🟡 | 10 componentes mortos (6 órfãos diretos, 4 alcançáveis só sob `DEBUG`) | 0,5–1 | F3 |
| `HT-07` 🟡 | Concatenação condicional com "·" no template, 10 pontos em 8 arquivos, sem parênteses | 1–2 | F5 |
| `HT-08` 🟡 | 80 `<button>` reimplementados fora do componente, em 10 apps | 3–4 | F5 |
| `HT-09` ⚪ | Login é HTML autônomo, sem skip link e sem `aria-describedby` no erro | 0,5 | F0 |
| `HT-10` ⚪ | `data-rg-toggle`/`data-motorista-fixo-toggle` legados ainda emitidos por componente compartilhado | 0,5–1 | F5 |

**`HT-01` sobe para F0** junto com o XSS: é falha WCAG 2.4.7 na primeira tela que qualquer usuário
encontra, e a correção é aditiva.

**`HT-08` tem uma armadilha:** parte dos 80 botões tem handler de JS amarrado à classe. Conferir
`static/js/components/*` antes de cada substituição — mesma família do `JS-06`.

### O que foi verificado e está correto

Registrado para não ser redescoberto: paginação com `aria-current`/`aria-live`; sidebar com
`aria-expanded`/`aria-controls`; `button.html` resolvendo `<a>` vs `<button>`; select customizado
com `aria-labelledby` e `<label for>`; a única tabela de produção com `<caption>` e `th scope`;
contrato `data-collection` respeitado em 100% dos containers.

**Correção de um número que circulou nesta sessão:** as "93 suspeitas" do
`audit_django_architecture.py` **não são 93 `href="#"`**. São o total de quatro categorias
(10 `href_falso_template` + 15 `html_em_presenter` + 26 `query_direta_view` +
42 `get_object_or_404_em_view`). Os `href="#"` reais são **10**, e a classificação individual
mostrou que **todos** estão em `ui_lab2`/`dev/ui_lab` sob `DEBUG` ou sob `is_demo=True` — nenhum
alcançável em produção. Não vira ID.

## 5. O que este plano não faz

- **Não renomeia classe nenhuma antes de F1.** O JS ainda depende do nome em 9 arquivos, e não há
  teste de JS que pegue a quebra.
- **Não apaga CSS pela contagem desta auditoria.** A contagem é o mapa; a prova é por arquivo, no
  PR, como manda o `AGENTS.md` §3.6.
- **Não mexe em `base.html`** fora do necessário para a folha de símbolos e os bundles: é o arquivo
  que toda tela herda, e mudança ali não tem regressão automatizada que a pegue.
- **Não persegue número de Lighthouse.** A régua é a de [`PLANO_DESEMPENHO.md`](PLANO_DESEMPENHO.md):
  KB de HTML, uso de CSS por rota e milissegundos no servidor, tudo reproduzível por comando.
