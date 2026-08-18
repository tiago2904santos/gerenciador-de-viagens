# Plano de refatoração do frontend

**Medido em 05/08/2026.** CSS medido por extração e por navegador real (Chromium via CDP);
JavaScript medido por varredura e leitura dirigida. Nada aqui foi herdado das auditorias de julho.

**Regras de conduta:** [`AGENTS.md`](../AGENTS.md) · **Ordem das etapas:**
[`PLANO_MESTRE_REFATORACAO.md`](PLANO_MESTRE_REFATORACAO.md) · **Defeitos:**
[`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md) (prefixos `UI`, `HT`, `JS`)

> ## ⚠️ Este documento cobre até a F4. A F5 mudou de casa.
>
> **As etapas F0 a F4 abaixo estão fechadas** e o texto delas fica como registro do que foi feito
> e por quê. A **F5 ("reconstrução por domínio"), que aqui está descrita como "a dimensionar",
> foi dimensionada em 09/08/2026** e virou documento próprio:
>
> ### → [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md)
>
> Lá estão as doze etapas da Fase 7 do plano mestre — componentização por `django-cotton`, desenho
> único entre os temas, duas camadas de token, fronteira de domínio no CSS e entrega do JS —, cada
> uma com arquivos, comando de verificação e catraca. **A F6 (`JS-03`, runner de teste) também foi
> para lá**, como etapa E1, porque deixou de ser aditiva: ela é a rede que segura as etapas de
> componentização.
>
> **Os números deste documento são de 05/08 e envelheceram.** A linha de base vigente, remedida em
> 09/08 com o comando de cada número ao lado, está no §2 do documento novo. Para dar a ordem de
> grandeza da diferença: a suíte foi de 1.306 para **1.824 testes**, o auditor de front de 392
> para **240 avisos**, o CSS de 43.038 para **32.940 linhas** — e os imports de CSS de domínio
> alheio, que este plano registra em 54, **subiram para 97**.

---

## 1. O estado real

**O JavaScript está melhor do que a fama.** O que o projeto decidiu automatizar, funcionou: zero
`fetch()` cru, zero `alert()`/`confirm()` nativos, zero duplicação de `debounce`/`escapeHtml`/
`normalize`, bundle em dia com as fontes. Os 392 avisos do auditor de CI são **todos de CSS** —
nenhum é de JS.

**O CSS é onde está o peso.** De 2.612 classes declaradas, **~929 não aparecem em lugar nenhum** —
nem em template, nem em JS, nem em Python. São 981 blocos somando 168 KB. E o que sobra também não
está bem: o navegador recebe 664–816 KB por página e casa **~10%**.

**O problema não é tamanho, é fronteira.** `oficios.css` (106 KB) é carregado na tela de Prestações
de Contas e usado **0,0%** ali. Não é descuido de um template: o estilo dos componentes
compartilhados mora dentro dos arquivos de domínio, então quem quer o componente leva o domínio
junto. São 54 imports cruzados em 26 templates.

**E o tema escuro é uma camada de exceção.** `theme-dark-components.css` tem 5.843 linhas e 190
`!important` — o tema não é resolvido por token, é resolvido sobrescrevendo componente por
componente. Nove arquivos definem `--color-*`.

**O que o CI não vê.** O auditor cobre 6 dos ~9 invariantes do projeto. Fora do alcance dele
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

> **F1 concluída em 06/08/2026.** O lado do JavaScript está cortado. Falta o lado do **markup**:
> três templates escrevem o picker à mão e cinco arquivos JS copiam suas classes para montar o
> "cartão de rota relacionada" (`NOVO-16`) — a renomeação da F5 ainda quebra esses. Não bloqueia
> F2 nem F3.

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
| `JS-01` 🔴 | XSS: `pasta.name` cru em `aria-label` (`gdrive-config.js:112,117`), enquanto a linha 114 escapa a mesma variável | 0,25 |
| `HT-01` 🔴 | Foco de teclado invisível em `input`/`select`/`textarea` no sistema inteiro, inclusive no login | 1–2 |
| `JS-04` ✅ | `.then()` sem `.catch` no editor de roteiros. Medido: a falha de rede **cancelava a fila inteira**, não só o trecho que falhou — 1 requisição em vez de 2, 0 de 2 trechos estimados | 0,5 |
| `HT-09` ⚪ | Login sem skip link e sem `aria-describedby` no erro de campo | 0,5 |
| `JS-11` ✅ | `maskCep` duplicada e `onlyDigits` em 4 cópias — `masks.js` não tinha saída pública para `onlyDigits`; agora tem, com gate no auditor | 0,25 |
| `JS-12` ✅ | `CV.componentRegistry` era alias sem nenhum consumidor (enunciado "mesmo objeto" refutado em runtime) | 0,25 |

**Gate:** teste que prova o escape (entrada com `"` e `<script>`); o `JS-04` verificado com a rede
derrubada; o `HT-01` conferido com navegação por Tab em tema claro e escuro, com print no PR.

### F1 — O JS larga o nome de classe · 5 dias · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `JS-06` ✅ | Trocar `classList.contains("cv-search-picker")` por `data-entity-picker-root` — **7 arquivos, 10 ocorrências** (o "9 arquivos" era do enunciado antigo), mais as **34 consultas de parte** do `NOVO-19` | 1 |
| `JS-05` ✅ | Estender o auditor de CI: **4 regras** — `innerHTML` sem `escapeHtml`, `registerEnhancer` sem `destroy`, classe CSS como condição de lógica e `catch` vazio. Cobertura 6 → 10 invariantes | 1,5 |
| `JS-02` ✅ | `destroy` nos componentes que registram listener em `document`/`window` — **14 de 17** sem `destroy`, dos quais **4 vazavam de fato**: `picker.js`, `cv-date-picker.js`, `location-rows.js` e `attach-signed-modal.js` | 2,5 |

`JS-02` entra aqui e não depois porque a poda de CSS vai remover elementos do DOM em massa durante
a verificação, e é exatamente aí que listener órfão aparece.

**Gate:** a regra nova do auditor em vigor, com catraca que só desce; nenhum `registerEnhancer`
sem `destroy` fora da lista de exceções documentada.

### F2 — Fundação · 4 a 6 dias · risco médio

| ID | Defeito | Dias |
|---|---|---:|
| `PF-01` ✅ | Folha de símbolos de ícone: 378 `<svg>` inline = 192 KB por página de lista, vindos de uma cadeia de 222 linhas de `if/elif` — fechado em 06/08: 450,4 → 315,3 KB, 1.244 → 109 nós de forma; comprimido o ganho é nulo, ver catálogo | 2–3 |
| `PF-04` ✅ | Menu de ação sob demanda — **fechado em 07/08 nos seis domínios**: Ofícios 315,3 → 166,5 KB, Eventos 416,3 → 211,9, Termos 317,6 → 147,9, Prestações 383,1 → 259,0, Planos 169,5 → 129,0, OS 166,8 → 126,7; `roteiros` não tem menu | 2–3 |
| `HT-*` | Componentes que faltam e duplicação estrutural — ver §4 | a definir |

Esta etapa **fixa quais classes existem**. É a fronteira: depois dela, o CSS estiliza um conjunto
conhecido.

### F3 — Poda do CSS morto · 4 a 6 dias · risco baixo

| ID | Defeito | Dias |
|---|---|---:|
| `UI-01` 🟠 | ~929 classes candidatas em 981 blocos, 168 KB | 4–6 |

**Como fazer, e o que não fazer.** A contagem desta auditoria é o **mapa**, não a licença. O
`AGENTS.md` §3.6 exige prova de grep por classe apagada, colada no PR.

> **Fechado em 07/08.** A ordem original era um arquivo por PR, na ordem do peso: `oficios.css`
> (283 blocos, 47 KB), `dev/ui-lab-fields.css`, `dev/ui-lab-pages.css`, `page-shell.css`,
> `roteiros.css`, `cv-buttons.css`. Os seis saíram, e **a lista estava curta**: ela nomeava os seis
> maiores, não os seis únicos. Remedindo o `static/css` inteiro sobravam 412 blocos e 71,6 KB em 31
> arquivos, que saíram em duas levas — por regra, não por arquivo.
>
> **A regra de um arquivo por PR morreu no caminho, e a substituta é por família de classe.** Ela
> quebrava no caso comum: classe estilizada em dois CSS e usada em nenhum template é morta nos dois,
> e podar só um lado deixa regra órfã do outro. Em `cv-buttons.css`, 16 das 25 classes mortas.
>
> **O instrumento de verificação também mudou.** Diff de pixel não servia: rodando o mesmo CSS duas
> vezes, 25 das 88 telas divergiam. O piso de ruído era maior que o efeito medido. Trocado por
> `getComputedStyle` — caixa mais 44 propriedades por elemento, determinístico depois de desligar
> `transition` e `animation`: **0 de 41.938** elementos entre duas capturas do mesmo CSS.
>
> A catraca que impede a volta é `scripts/audit_css_morto.py --max 0`, no CI.

**A regra de segurança da poda, corrigida pela verificação de 05/08.** A primeira varredura
concluiu que existia um único padrão de classe montada em tempo de execução. **Estava errada, e o
erro era do método** — ela ancorava na aspa de abertura e só procurava `` `${` ``, perdendo
interpolação no meio da string e toda concatenação com `+`. Existem pelo menos três:

| arquivo | padrão | classes geradas |
|---|---|---|
| `components/picker.js:143-144` | `` `cv-search-picker--${mode}` ``, `--${variant}`, `--${presentation}` | `--single`, `--multi`, `--detailed`, `--compact`, `--vehicle` |
| `pages/usuarios-admin.js:123-124` | `prefix + "__toggle--ready"` / `"--changing"` | `usuario-quick-add__toggle--*`, `area-quick-add__toggle--*` |
| `pages/oficios-viatura-sugestoes.js:127` | `"viatura-sugestao-badge--" + s.reason` | `--motorista`, `--unidade` |

**Nenhuma dessas pode ser apagada**, e todas as três telas são de produção. O número de candidatas
cai para no máximo **~929**. Em Python não há padrão equivalente fora do enum `WidgetStyle`.

> **Portanto, o gate de cada PR de poda é:** a prova de grep tem que cobrir concatenação com `+`
> e interpolação no meio da string, não só `` `${…}` `` no começo. Uma poda guiada pelo método
> antigo apagaria classe viva.

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

### F5 — Reconstrução por domínio · **dimensionada em 09/08 → documento próprio**

> **Esta etapa virou [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md).**
> Os quatro IDs abaixo continuam válidos e estão distribuídos assim: `UI-04` na etapa E10,
> `JS-07`/`JS-08`/`JS-09`/`JS-10` na E11. O documento novo acrescenta o que esta tabela não
> previa — a componentização por `django-cotton` (`NOVO-71`) e o desenho único entre os temas
> (`NOVO-58`), que são a maior parte do trabalho.
>
> A tabela original fica abaixo como registro do dimensionamento de 05/08.


| ID | Defeito | Dias |
|---|---|---:|
| `UI-04` 🟠 PARCIAL | E10: `oficios.css` 19 → 13 imports (−44.376 B em seis listas); `roteiros-list.css` removido (−6.919 B/rota); date/file/search/custom-select fora do shell padrão (−59.338 B nas rotas sem eles); Justificativas sem três CSS de domínio (−128.712 B); Termos sem o CSS de Prestações (−23.003 B); Documentos de Ofícios sem `roteiros.css` (−68.306 B, uso 15,08% → 16,57%). As demais famílias seguem abertas | a definir |
| `JS-08` ✅ | Cinco componentes sob demanda por marcador DOM; shell global −6,0% | 2 |
| `JS-09` 🟡 | Tela de espera de documento carrega 264 KB para usar 3,3 KB | 0,5 |
| `JS-07` ✅ | "Fechar ao clicar fora / Esc": 3 implementações vivas consolidadas em `CV.overlay.attachDismiss` | 2 |
| `JS-10` ✅ | Três stubs sem consumidor do editor de roteiros removidos | 0,25 |

O dimensionamento de `UI-04` depende de F2: quantos componentes precisam sair dos arquivos de
domínio só se sabe depois de saber quais componentes existem.

**Métrica de aceite da frente inteira (`PF-02`, fechada em 13/08):** uso de CSS por rota acima de
**35%**. A linha de base reproduzível era **11,3369%–19,2908% nas rotas autenticadas**; os 15 perfis
por família de tela encerraram o corpus de 43 rotas em **37,5118%–60,3148%**, medido por
`scripts/medir_css_por_rota.py` e guardado em `scripts/tetos_front.json`.

### F6 — Teste de JavaScript · **virou a etapa E1 do documento novo**

`JS-03` — não há runner, não há `package.json`, não há um único teste para 17.859 linhas (hoje
**18.382**). Começa pelos módulos mais críticos e mais testáveis: `core/http.js`, o registry de
`core/app.js`, `masks.js`, `components/collection.js`.

> **Deixou de ser "etapa própria, aditiva".** O dono aprovou o runner, e a reconstrução o
> transformou em **pré-requisito**: as etapas de componentização (E4–E6) trocam o motor de
> renderização de 82 componentes e reescrevem 946 pontos de chamada. Sem teste, a única rede é
> conferência visual em 43 telas, a cada PR. Por isso ele virou a **E1** — logo depois da régua e
> antes de qualquer mudança estrutural.

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
| `HT-02` ✅ 🟠 | Erro de campo sem `aria-describedby`/`aria-invalid`/`role="alert"` — no componente com **154** usos; fechado junto do `HT-12`, que é o mesmo defeito pelo outro lado | 2–3 | F2 |
| `HT-03` ✅ 🟠 | Sem padrão único para erro de formulário: o componente correto tinha **zero** usos em produção — e **jogava a mensagem fora**; agora são 20 chamadores, com o texto real e foco no resumo | 2 | F2 |
| `HT-04` 🟡 | Entrega JS fechada: shell 266.254 → 108.937 B; os ~37 KB de CSS seguem na fronteira `UI-04`/E10 | 2–3 | F5 |
| `HT-05` ✅ 🟡 | `empty_state.html` fixa `<h3>`, quebrando a ordem de headings em **10** das 10 listas | 0,5 | F2 |
| `HT-06` 🟡 | 10 componentes mortos (6 órfãos diretos, 4 alcançáveis só sob `DEBUG`) | 0,5–1 | F3 |
| `HT-07` 🟡 | Concatenação condicional com "·" no template, 10 pontos em 8 arquivos, sem parênteses | 1–2 | F5 |
| `HT-08` 🟡 | 80 `<button>` reimplementados fora do componente, em 10 apps | 3–4 | F5 |
| `HT-09` ⚪ | Login é HTML autônomo, sem skip link e sem `aria-describedby` no erro | 0,5 | F0 |
| `HT-10` ⚪ | `data-rg-toggle`/`data-motorista-fixo-toggle` legados ainda emitidos por componente compartilhado | 0,5–1 | F5 |
| `NOVO-99` ✅ 🔴 | `include ... only` isolava o token CSRF do formulário do editor de roteiro; os três chamadores agora o passam explicitamente | 0,25 | correção imediata |

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

## Piloto visual isolado (13/08/2026)

- [x] `NOVO-20260813-171150-4772a7bebcf5` — sub-headers pareados usam o token principal
  `--color-primary: #223348` diretamente nos temas claro e escuro, sem alias e sem migrar páginas reais.
- [x] `NOVO-20260813-171408-221bef7cfe88` — controles dos sub-headers usam `--color-secondary`
  com a fórmula 88% superfície atenuada e 12% primária nos dois temas do piloto.
- [x] `NOVO-20260813-171859-8fe0da057c11` — hierarquia visual invertida: tira secundária,
  controles primários e nenhuma borda em `input`, `select`, `button` ou ação do sub-header.
- [x] `NOVO-20260813-172249-36d8bc8fea04` — quick-add piloto reduzido ao campo de busca,
  removendo o texto explicativo e a ação de limpar filtros sem afetar páginas reais.
- [x] `NOVO-20260813-172430-f0138f333d5c` — fonte oficial aplicada ao shell, headers,
  sub-headers e controles nativos do piloto por herança explícita.
- [x] `NOVO-20260813-172706-ca9bc207b6d1` — selects nativos avulsos da prévia substituídos
  por duas instâncias do componente oficial `c-ui.forms.select`, ainda sem migração de páginas reais.
- [x] `NOVO-20260813-173205-02d6906c766e` — chevron do select piloto usa o fundo do input,
  volta a ficar visível e gira conforme o estado expandido, sem alterar páginas reais.
- [x] `NOVO-20260813-173642-044c2e0689fc` — opção ativa do menu select exibe um marcador
  gráfico, com escopo preservado mesmo quando o menu é transportado para o `body`.
- [x] `NOVO-20260813-173922-180b4f6bb759` — hover e foco das opções não selecionadas
  usam uma superfície contrastante no tema claro, sem alterar o tema escuro.
- [x] `NOVO-20260813-174203-53f71e9fa7e9` — busca, selects e ação da faixa de filtros
  compartilham `border-radius: var(--radius-sm)` no piloto.
- [x] `NOVO-20260813-174333-fe5e62f284a6` — listbox transportado do select usa a cor primária
  definida diretamente por cada tema do piloto.
- [x] `NOVO-20260813-174518-c11a152b3951` — fundo das três variações de sub-header
  passa a usar a cor primária do piloto.
- [x] `NOVO-20260813-174650-8d42b37baa7e` — cores aprovadas preservadas com semântica corrigida:
  faixa primária e controles internos secundários; o listbox foi alinhado à secundária depois.
- [x] `NOVO-20260813-174920-05e64dddaf01` — listbox usa a mesma espessura e o mesmo token
  de borda do sub-header em cada tema.
- [x] `NOVO-20260813-175332-5e403f4623e7` — primária e secundária do piloto têm valores
  diretos por tema, sem aliases, misturas ou dependências cruzadas.
- [x] `NOVO-20260813-175642-534d862bebf9` — listbox usa a secundária e hover/foco das opções
  usam a primária, sem mudar os valores dos tokens.
- [x] `NOVO-20260813-180435-8659b1be555f` — sub-header stepper do piloto reutiliza o
  `page_stepper` oficial de Ofícios, com conectores, marcadores e estados canônicos.
- [x] `NOVO-20260813-181307-5480426bf196` — marcador atual do stepper usa diretamente
  `--color-acent-primary`, com valor próprio em cada tema do piloto.
- [x] `NOVO-20260813-181456-5fb6cde15b32` — marcador concluído do stepper usa diretamente
  `--color-acent-secundary`, com valor próprio em cada tema do piloto.
- [x] `NOVO-20260813-181722-0ac121ceee46` — respiro vertical do stepper preserva integralmente
  o halo da etapa atual sem remover a rolagem horizontal responsiva.
- [x] `NOVO-20260813-181839-ce8dd0e582cb` — card de roteiro recriado como componente isolado
  na página-piloto, com dados estáticos e CSS próprio para os dois temas.
- [x] `NOVO-20260813-182642-5af6808073e6` — terceiro papel de superfície removido do card
  piloto nos dois temas, sem introduzir nova cor.
- [x] `NOVO-20260813-182804-7bb5ba76ccc5` — botões, linhas de local e valores do card piloto
  usam diretamente sua cor primária nos dois temas.
- [x] `NOVO-20260813-182902-7670c81c1b29` — valores internos de estado e cidade usam a
  secundária, mantendo linhas, botões e métricas na primária.
- [x] `NOVO-20260813-183018-f847a6f4d130` — card completo de Ofício recriado como componente
  isolado na página-piloto, com dados estáticos e temas próprios.
- [x] `NOVO-20260813-183956-c0a8b4f574a0` — painel de coleção de Unidades recriado como
  componente isolado no piloto, com paginação e linhas estáticas.
- [x] `NOVO-20260813-184339-4be90a915693` — sub-header quick-add do piloto ampliado para
  retratar busca, orientação e resultados do fluxo de Justificativas.
- [x] `NOVO-20260813-184600-8256932ed3b4` — cards de formulário e entidade do piloto
  alinhados à fonte e à hierarquia tipográfica canônica dos cards de lista.
- [x] `NOVO-20260813-185012-ea394e1429c9` — opção selecionada do select piloto usa
  `--color-acent-secundary` também durante hover e foco.
- [x] `NOVO-20260813-185458-e5169fc903c8` — toggle do header piloto alterna estado visual,
  `aria-pressed` e título, sem navegação ou recarregamento.
- [x] `NOVO-20260813-185807-5476832caabe` — card de formulário piloto sem borda externa e
  sem divisor inferior no header, preservando superfícies e espaçamentos.
- [x] `NOVO-20260813-185953-04e844fdd145` — busca contextual do quick-add usa a primária,
  enquanto a busca superior permanece na secundária.
- [x] `NOVO-20260813-190246-08d35cec2a64` — filtros, quick-add e stepper exibem a mesma borda
  discreta de 1px, com contraste próprio nos temas claro e escuro.
- [x] `NOVO-20260813-191334-d518c08a44a1` — painel de coleção escuro usa a primária na
  superfície externa e a secundária nas linhas e na paginação.
- [x] `NOVO-20260813-191605-c807e2879db4` — form-card, entity-card e collection-panel usam
  diretamente `--color-primary` e `--color-secondary`, sem aliases de superfície.
- [x] `NOVO-20260813-192058-f5754ae91818` — divisor do footer do entity-card removido e
  espaçamento vertical dos exemplos uniformizado em 20px.
- [x] `NOVO-20260813-192309-77b4176da884` — divisor inferior do header do entity-card removido,
  preservando o espaçamento interno do componente.
- [x] `NOVO-20260813-192620-0d0a2ee2604b` — entity-card alinhado aos paddings do form-card:
  `16px 20px` nas extremidades e `16px` no corpo.

## Conclusão dos cadastros no v2 (18/08/2026)

- [x] `NOVO-20260818-161641-9c71598641c6` — eliminar chamadas visuais legadas restantes em
  `templates/cadastros`, compartilhar uma única confirmação de exclusão v2, consolidar o card de
  módulo usado por Dashboard/Cadastros e remover as parciais comprovadamente sem consumidor.
- [x] `NOVO-20260818-173204-55aec7fb0127` — substituir os campos híbridos de Combustível,
  Unidade e Motoristas da Viatura pelos controles `select_with_action` e `picker` v2, mantendo
  autosave, valores e URLs de gerenciamento.
- [x] `NOVO-20260818-180959-c19b650c0c5b` — substituir os campos híbridos de Cargo e Unidade
  do Servidor pelos controles `select_with_action` e `picker` v2, com ação de gerenciamento
  circular e contextual, mantendo autosave, valores e URLs.
- [x] `NOVO-20260818-183006-40ad9eb5163f` — migrar os cadastros rápidos de Usuários, Áreas e
  Unidades para campos e `form_block` v2, separando cada seção lógica sem alterar os POSTs.
- [x] `NOVO-20260818-190244-36d8603f3b28` — migrar o Tipo da Viatura para o select v2 e
  restringir a ação de gerenciamento dos pickers à linha de busca, sem encolher a lista.
- [x] `NOVO-20260818-192027-451efb3fc693` — substituir os widgets visuais anteriores do
  cadastro rápido de Usuários por `input`, `picker` e `select` v2, sem controles duplicados.
- [ ] `NOVO-20260818-193403-74ca0c875514` — remover Servidores do cadastro rápido de Unidade e
  manter Nome e Sigla na mesma linha no desktop.
