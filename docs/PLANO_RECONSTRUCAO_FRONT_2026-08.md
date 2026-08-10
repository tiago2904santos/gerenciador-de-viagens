# Plano de reconstrução do front — CSS, HTML e JavaScript

**Medido em 09/08/2026, por execução.** Este documento é a Fase 7 do
[`PLANO_MESTRE_REFATORACAO.md`](PLANO_MESTRE_REFATORACAO.md), escrita no formato que o **Codex**
executa: etapa numerada, arquivos nomeados, comando que prova, catraca com o número de hoje.

**Regras de conduta:** [`../AGENTS.md`](../AGENTS.md) · **Defeitos:**
[`CATALOGO_DEFEITOS_2026-08.md`](CATALOGO_DEFEITOS_2026-08.md) · **Frente:**
[`PLANO_FRONTEND.md`](PLANO_FRONTEND.md)

---

## 0. Como usar este documento

Uma etapa = um PR = uma sessão. Não emende a etapa seguinte na mesma branch.

Antes de começar **qualquer** etapa:

```bash
source .venv/bin/activate
pip install -r requirements/test.txt     # enquanto o NOVO-75 estiver aberto
python manage.py test --settings=config.settings.test --parallel 4
```

Se a suíte não estiver verde **antes** de você tocar em nada, pare: o problema não é seu e você
não vai conseguir provar o que fez.

Cada etapa abaixo tem sete campos fixos. O campo **Pare e pergunte** não é decorativo — é onde o
enunciado deixa de ter critério objetivo de pronto, e onde o `AGENTS.md` §6 diz que o Codex não
deve decidir sozinho.

**A regra que mais custa caro aqui:** este plano renomeia, move e apaga. O `AGENTS.md` §3.2 e §3.6
valem em toda etapa — nada sai sem prova de `grep` no repositório inteiro, e a prova tem que cobrir
`templates/`, `static/js/`, `static/css/` **e `*.py`**. Contar só template mente: hoje
`templates/components/create_draft.html` tem zero `{% include %}` e está vivo, renderizado por
`oficios/list_views.py:100`, `eventos/views.py:242` e `planos_trabalho/list_views.py:93`.

## 1. O que o dono decidiu, e que este plano fixa

| Decisão | Efeito |
|---|---|
| **Desenho único: o redesenho do escuro passa a valer no claro** | A E8 muda a aparência das 43 telas em modo claro — fonte, tamanho de texto, raio, borda, largura da barra lateral |
| **Componentização por `django-cotton`** | As E3–E6 substituem `{% include %}` por `<c-*>`, com atributo declarado |
| **Runner de JavaScript no CI** | A E1 traz `package.json`, Vitest e um passo de Node no `tests.yml` |
| **Nomes em inglês, sem prefixo `cv-`, pela função** | Já vigente desde o `NOVO-60`; as etapas novas nascem assim |

## 2. Linha de base — cada número com o comando que o produz

Os números do `PLANO_FRONTEND.md` são de 05/08 e envelheceram. **Remeça antes de abrir cada
etapa**; o que estiver diferente é trabalho que aconteceu no meio.

| medida | 05/08 | **09/08** | comando |
|---|---:|---:|---|
| CSS de fonte | 43.038 | **32.931** em 60 arquivos, em 8 pastas | `find static/css -name '*.css' ! -name 'shell.bundle.css' -exec cat {} + \| wc -l` |
| `theme-dark-components.css` | 5.843 | **5.619** | `wc -l static/css/components/theme-dark-components.css` |
| `!important` fora do bundle | 497 | **496** (190 no tema escuro) | `grep -ro '!important' static/css --include='*.css' \| grep -v shell.bundle \| wc -l` |
| arquivos definindo `--color-*` | 9 | **9** | `grep -rl '^\s*--color-' static/css --include='*.css' \| grep -v shell.bundle` |
| imports de CSS em template | 54 em 26 | **97 em 36** | `grep -rn "{% static 'css/" templates --include='*.html' \| wc -l` |
| JS de fonte | 17.859 | **18.382** em 64 arquivos | `find static/js -name '*.js' ! -name 'shell.bundle.js' -exec cat {} + \| wc -l` |
| templates | 462 | **407**, com **82** componentes | `find templates -name '*.html' \| wc -l` |
| `<button>` cru fora de componente | 80 | **82** | `grep -rn '<button' templates --include='*.html' \| grep -v '^templates/components/' \| wc -l` |
| includes sem `only` | "28%" | **275 de 946** | `grep -rho '{%\s*include' templates \| wc -l` menos a variante com `only` |
| suíte | 1.306 · 9,9 s | **1.824 · 7 skips · 14,7 s** | `manage.py test --settings=config.settings.test --parallel 4` |
| auditor de front | 392 (teto 401) | **240 (teto 246)** | `python scripts/audit_frontend_standards.py --max-warnings 246` |
| CSS morto | 0 | **0** | `python scripts/audit_css_morto.py --max 0` |
| paleta duplicada | 0 | **0** | `python scripts/audit_paleta.py --max 0` |
| foco suprimido | — | **30, teto 30 — folga zero** | `python scripts/audit_foco_visivel.py --max 30` |

**O que já está são, e que nenhuma etapa pode estragar:** zero `fetch()` cru, zero `alert()`/
`confirm()` nativos (os 12 hits de `grep` são `CV.feedback.*`), zero `style=` inline, zero
`<script>` inline em template, bundles em dia (`build_shell_bundles.py --check`: 25 CSS, 26 JS).

**A folga zero do foco importa.** `audit_foco_visivel --max 30` está em exatamente 30. Qualquer
bloco novo que apague foco sem substituto reprova o CI. As etapas E6 a E9 mexem em `:focus`; conte
antes e depois.

## 3. A ordem, e por que ela não é negociável

```
E0 régua ──► E1 teste de JS ──► E2 higiene
                                   │
                                   ▼
                    E3 cotton ──► E4 componentes ──► E5 call sites ──► E6 o que falta
                                                                            │
                                                                            ▼
                                              E7 token ──► E8 desenho ──► E9 tema ──► E10 fronteira
                                                                                          │
                                                                                          ▼
                                                                                     E11 entrega
```

**O HTML define o nome, o CSS pinta o nome.** É a regra do `PLANO_MESTRE` §4, e é o que põe a
componentização (E3–E6) antes da reconstrução visual (E7–E10). Fazer o contrário significa pintar
componentes que a etapa seguinte vai renomear.

**A régua vem antes de tudo** pela lição da Fase 1: sem instrumento, toda etapa vira afirmação sem
prova, e a regressão volta no PR seguinte sem ninguém ver.

**O teste de JS vem antes da higiene** porque a E2 apaga arquivo e move módulo, e é exatamente aí
que se descobre que alguém dependia do que sumiu.

---

## 4. As etapas

### E0 ✅ — A régua · `NOVO-75`, `NOVO-70`, `NOVO-76`, `NOVO-77`–`79` · risco baixo · concluída em 09/08/2026

**Objetivo.** Tornar mensurável o que este plano promete: uso de CSS por rota e divergência entre
os dois temas.

**Resultado.** As 43 rotas foram medidas com usuário dedicado efêmero e base isolada. O CSS ficou
entre **11,3369% e 70,5559%** de uso (11,3369%–19,2908% nas rotas autenticadas). A matriz de tema
fez **129 medições** em 1440, 800 e 500 px: 61.700 elementos comparados, 248.651 diferenças
não-cor e zero diferenças exclusivas entre as ordens claro→escuro e escuro→claro. Uma segunda
execução, sem `--atualizar-tetos`, passou contra `scripts/tetos_front.json`.

**Arquivos.** `requirements/dev.txt` · `scripts/rotas_do_sistema.py` (novo) ·
`scripts/medir_css_por_rota.py` (novo) · `scripts/medir_divergencia_tema.py` (novo) ·
`scripts/tetos_front.json` (novo) · `.github/workflows/tests.yml`

**Passo a passo.**

1. **Primeiro o `NOVO-75`, sozinho no primeiro commit.** `requirements/dev.txt` ganha
   `-r test.txt`. Sem isso o hook `.claude/hooks/session-start.sh:20` continua montando um
   ambiente onde o comando do `AGENTS.md` §7 aborta com `TypeError: cannot pickle 'traceback'
   object`, e nada abaixo é verificável. Prove rodando `--parallel 4` num venv limpo.
2. **`scripts/rotas_do_sistema.py`** — o corpus canônico de rotas, hoje espalhado e podre. Tire de
   `screenshots/auditoria-telas/_capturar.py`, que lista 57 telas das quais **14 são rotas de UI
   Lab que o PR #247 apagou**. Sobram **43**. O corpus mora em `scripts/` porque o `BE-24` vai
   tirar os 39 MB de `screenshots/` do repositório, e a régua não pode ir junto.
3. **`scripts/medir_css_por_rota.py`** — Chromium via CDP (`CSS.startRuleUsageTracking`), medindo
   por rota: bytes de CSS entregues, bytes casados, percentual. Espelhe a interface de
   `scripts/medir_desempenho.py`: `--json`, `--atualizar-tetos`, teto por rota em JSON, saída 1 se
   passar do teto. É o instrumento que faltava para o `PF-02`.
4. **`scripts/medir_divergencia_tema.py`** — `getComputedStyle` no mesmo elemento do mesmo
   documento nos dois temas, comparando **só propriedade que não é cor**. Duas armadilhas já
   medidas e registradas no `NOVO-58`, que você **tem** que reproduzir: desligue `transition` e
   `animation` antes de capturar (senão pega o valor no meio da interpolação — 418 elementos de
   ruído numa medição anterior), e confirme que a ordem de captura não muda o resultado
   (claro→escuro e escuro→claro deram 0 diferenças exclusivas de uma ordem).
5. **Passo no `tests.yml`**, depois do passo de desempenho, com teto que só desce.
6. **`NOVO-76` — decidir o que é o `audit_ui_patterns.py`.** Ele está no ciclo obrigatório do
   `AGENTS.md` §4, sai **1 sempre** (5.173 ocorrências hoje, na `main`) e **não está no
   `tests.yml`**. Ou vira catraca com teto, ou vira relatório e sai do §4 — mas não pode continuar
   sendo um verificador que ninguém pode passar, porque isso treina quem o roda a ignorar a saída.
   A maior parte do ruído é a regra `hex_or_rgba` disparando dentro dos arquivos de token, onde a
   cor literal **é** a definição.

**Prova.**

```bash
python scripts/medir_css_por_rota.py --json /tmp/css.json
python scripts/medir_divergencia_tema.py --json /tmp/tema.json
python manage.py test --settings=config.settings.test --parallel 4
```

**Catraca.** Nasce agora. Grave o medido: uso de CSS por rota (hoje 10,1%–11,8%) e divergência
não-cor (hoje ~45.726 diferenças em 20.203 elementos). Os dois só descem — o primeiro sobe, o
segundo desce; declare o sentido no JSON para não inverter por engano.

**Corpo do PR.** Etapa E0 · resolve `NOVO-75` e `NOVO-70` · a saída dos dois scripts colada,
porque é a linha de base que todas as etapas seguintes citam.

**Pare e pergunte.** Se o CDP não conseguir autenticar nas rotas que exigem login — decida com o
dono entre um usuário de teste dedicado e medir só o que é público. Não meça menos e chame de 43.

---

### E1 ✅ — Rede de teste de JavaScript · `JS-03` · risco baixo · concluída em 09/08/2026

**Objetivo.** Dar às 18.382 linhas de JS o primeiro teste automatizado do projeto.

**Resultado.** Vitest + jsdom executam **34 testes** sobre os quatro primeiros módulos. A
cobertura medida e fixada como piso por arquivo é: `http.js` 100% de linhas, `app.js` 27,74%,
`masks.js` 96,20% e `collection.js` 91,36%. O CI usa Node 22, `npm ci` e `npm test`; a prova
negativa elevou temporariamente o piso de linhas de `app.js` para 100% e o verificador saiu 1,
informando 27,74% abaixo do piso. Nenhum teto existente foi desligado ou afrouxado.

**Arquivos.** `package.json` (novo) · `vitest.config.js` (novo) · `static/js/**/*.test.js` (novos)
· `.github/workflows/tests.yml` · `.gitignore`

**Passo a passo.**

1. `package.json` com Vitest + jsdom. Node 22 já está no contêiner; no CI use
   `actions/setup-node@v4` com `cache: npm`.
2. Comece pelos quatro módulos mais críticos e mais testáveis, nesta ordem:
   `static/js/core/http.js` (116 linhas, é o cliente que todo mundo usa),
   o registry de `static/js/core/app.js` (`registerEnhancer`/`destroy` — o contrato que o `JS-02`
   fechou e que nada guarda hoje), `static/js/components/masks.js` (função pura, barata),
   `static/js/components/collection.js`.
3. Piso de cobertura próprio, no formato de `.github/coverage-floors.json`. Comece no medido.
4. `node_modules/` no `.gitignore`.

**Prova.** `npm test` verde no CI, e o piso reprovando quando você o baixa de propósito uma vez
para conferir que a catraca morde.

**Catraca.** Piso de cobertura de JS, novo. Só sobe.

**Corpo do PR.** Etapa E1 · resolve `JS-03` · número de testes e cobertura por módulo.

**Pare e pergunte.** Se `npm ci` estourar o tempo do CI ou brigar com o `pip-audit` do passo de
dependências, pergunte antes de desligar qualquer um dos dois. `AGENTS.md` §3.5: catraca não se
afrouxa para o PR passar.

---

### E2 ✅ — Higiene: o morto e os nomes · `NOVO-69`, `NOVO-72`, `NOVO-73`, `NOVO-48` · concluída em 09/08/2026

**Objetivo.** Tirar do caminho o que está morto e padronizar nome e lugar, antes que a
componentização os carregue para dentro do desenho novo.

**Resultado.** `cv-select.js` e seu contrato/no-op/CSS órfão saíram; `SHELL_JS` ficou com 25
fontes e o bundle versionado caiu **289.831 → 274.420 bytes**. Os quatro módulos de página agora
estão em `static/js/pages/` com kebab-case. `ui_lab2/` não existe numa worktree limpa (era apenas
cache ignorado). A poda CSS, re-medida depois da sobreposição com `NOVO-69`, removeu **66 nomes**,
168 alternativas e 57 regras completas; o bundle CSS caiu **485.262 → 479.996 bytes** e a catraca
de padrões de UI desceu **2.622 → 2.583**.

**Arquivos.** `static/js/cv-select.js` · `scripts/build_shell_bundles.py` · `ui_lab2/` ·
`static/js/roteiros*.js` · `static/js/pages/gdrive_config.js` · `static/css/**` (seletores
agrupados) · `docs/DATA_ATTRIBUTES_JS.md`

**Passo a passo.**

1. **`NOVO-69` — apagar `static/js/cv-select.js` (343 linhas).** Ele responde a
   `data-cv-dropdown` e `data-cv-filter-dropdown`, e **nada no sistema emite esses atributos**: o
   que sobrou são um comentário em `static/css/fields/select.css:99,147-148`, a tabela de
   `docs/DATA_ATTRIBUTES_JS.md:118-124` e o histórico. O `JS-08` dizia "1 uso, sob `DEBUG` via
   `ui_lab2`" — o PR #247 apagou os labs e o uso virou zero. Tire-o também de `SHELL_JS`
   (`scripts/build_shell_bundles.py:74`) e regenere os bundles. Atualize a doc: o `HT-13` exige que
   ela descreva só o que existe. **Cuidado:** `custom-select` **não** é dele — quem atende esse
   markup é `components/picker-select.js`, via `data-entity-picker`. Não apague a família de CSS.
2. **`NOVO-72` — apagar `ui_lab2/`.** Sobrou como diretório de `__pycache__`; não está em
   `INSTALLED_APPS` nem no `urls.py`.
3. **`NOVO-73` — nome e lugar.** `roteiros_wizard.js` → kebab-case; `pages/gdrive_config.js` →
   `pages/gdrive-config.js`; e o domínio sai da raiz de `static/js/` para `pages/`
   (`roteiros.js`, `roteiros-map.js`, `roteiros_wizard.js`). Atualize `SHELL_JS`, os
   `{% block extra_js %}` que os citam e a doc.
4. **`NOVO-48` — os 70 nomes de classe morta dentro de seletor agrupado vivo.** 140 partes de
   seletor. Isto **não** é o que o `audit_css_morto.py` mede (ele pergunta "o bloco inteiro está
   morto?"), então a prova é por `grep` por nome, um a um. Faça por família, não por arquivo.

**Prova.** Para cada nome apagado, `grep` no repositório inteiro colado no PR, cobrindo
concatenação com `+` e interpolação no meio da string — não só `` `${…}` `` no começo
(`AGENTS.md` §3.6). Mais:

```bash
python scripts/build_shell_bundles.py --check
python scripts/audit_css_morto.py --max 0
python manage.py test --settings=config.settings.test --parallel 4
```

**Catraca.** `audit_frontend_standards --max-warnings 246` (hoje 240) e `audit_css_morto --max 0`.

**Corpo do PR.** Etapa E2 · resolve `NOVO-69`, `NOVO-72`, `NOVO-73`, `NOVO-48` · KB a menos no
bundle JS.

**Pare e pergunte.** Nada aqui exige decisão. Se um `grep` voltar com hit que você não sabe
classificar, **não apague** — registre no catálogo e siga.

---

### E3 ✅ — Cotton instalado, nada migrado · `NOVO-71` (parte) · concluída em 09/08/2026

**Objetivo.** Trocar o carregador de template sem tocar em um único template, para que a suíte
prove que só o carregador mudou.

**Resultado.** `django-cotton==2.7.2` foi pinado e travado com hashes. O loader efetivo é
`cached.Loader` → `django_cotton.cotton_loader.Loader` → `filesystem.Loader` →
`app_directories.Loader`; `cotton`, `cotton:vars` e `cotton:slot` estão em `builtins`. Os cinco
context processors do projeto permaneceram idênticos, nenhum arquivo em `templates/` mudou e os
408 templates compilam. A navegação real cobriu uma tela de cada domínio, mais o perfil da
integração Google, sem erro do Django ou do console.

**Arquivos.** `requirements/base.txt` · `requirements/lock.txt` · `config/settings/base.py:161-176`

**Passo a passo.**

1. `django-cotton==2.7.2` em `requirements/base.txt`; regenere `lock.txt` com
   `pip-compile --generate-hashes` (o cabeçalho do arquivo traz o comando exato).
2. `TEMPLATES` sai de `APP_DIRS: True` para `loaders` explícitos — o cotton exige, e os dois são
   mutuamente exclusivos no Django. **Preserve os cinco context processors**, inclusive os dois do
   projeto (`core.context_processors.area_permissions` e `.navigation`), e mantenha
   `APP_DIRS`-equivalente na lista de loaders (`app_directories.Loader`), senão todo template de
   app some.
3. **Nenhum template muda neste PR.** Nenhum `<c-*>` ainda.

**Prova.** A suíte inteira — 1.824 testes — verde antes e depois, com o número no corpo. É a única
prova que existe aqui, e é suficiente **só** porque nada mais mudou.

**Catraca.** Nenhuma nova. As existentes não podem mexer.

**Corpo do PR.** Etapa E3 · `NOVO-71` (parte) · o diff de `settings` lado a lado, com a lista de
loaders explicada linha a linha.

**Pare e pergunte — este é o passo mecânico mais arriscado do plano.** Errar a lista de loaders não
dá erro bonito: dá `TemplateDoesNotExist` numa rota que ninguém abriu no PR, com 407 templates em
jogo. Se a suíte passar mas você tiver **qualquer** dúvida sobre a ordem dos loaders, pare e
pergunte antes de mesclar. E confira, com o servidor de pé, pelo menos uma tela de cada app.

---

### E4 ✅ — Os componentes globais viram cotton · `NOVO-71` · concluída em 10/08/2026

**Objetivo.** Dar a cada componente global um contrato de parâmetro declarado, em vez de contexto
herdado por acaso.

**Concluída.** Os **82 componentes globais** agora têm implementação canônica em
`templates/cotton/**`; os 82 caminhos antigos em `templates/components/**` ficaram como cascas de
compatibilidade para a migração dos 946 call sites na E5. A conversão foi entregue em 21 commits
por família, com contrato automatizado cobrindo o inventário completo. A régua da E0 permaneceu
idêntica nas **129 combinações** (43 rotas × 3 larguras). Localmente, os 1.852 testes foram
coletados e só restaram as limitações já conhecidas do host Windows; as catracas fecharam em
`audit_frontend_standards`: **0 erros/240 avisos**, `audit_ui_patterns`: **2.535 suspeitas**,
`audit_django_architecture`: **78 suspeitas**, e os bundles do shell estão atualizados. O isolamento
de contexto e a remoção das cascas pertencem deliberadamente à E5, quando os call sites passarem a
usar slots e atributos Cotton diretamente.

**Arquivos.** `templates/cotton/**` (novos) · `templates/components/**` (viram cascas) ·
`scripts/audit_ui_patterns.py:10`

**Passo a passo.**

1. Converta **do mais usado para o menos**, uma família por commit. A ordem, medida hoje por
   inclusão em `templates/`:

   | componente | usos |
   |---|---:|
   | `ui/forms/field.html` | 128 |
   | `ui/icons/icon.html` | 101 |
   | `ui/forms/form_block.html` | 92 |
   | `ui/buttons/button.html` | 65 |
   | `ui/menus/rich_menu_link.html` | 43 |
   | `ui/feedback/field_error.html` | 41 |
   | `form/card.html` | 37 |
   | `ui/badges/chip.html` | 30 |
   | `ui/layouts/card_footer_section.html` · `ui/buttons/icon_button.html` · `ui/menus/rich_menu_header.html` | 23 cada |

   Depois a cauda, até os 82.
2. Cada componente vira `templates/cotton/<família>/<nome>.html`, com os atributos declarados. O
   include antigo **fica**, como casca de uma linha que chama o cotton — assim os call sites
   migram na E5 e este PR não precisa tocar em 946 pontos.
3. **`scripts/audit_ui_patterns.py:10` ignora `templates/components/ui`.** Mover componente para
   `templates/cotton/` move a catraca se `IGNORED_PARTS` não for atualizado no mesmo PR. É o
   efeito colateral mais fácil de esquecer desta etapa.

**Prova.** Suíte verde a cada família. E, para cada componente convertido, a régua de divergência
da E0 rodando antes e depois: **a conversão não pode mudar um pixel**, porque o que muda aqui é o
contrato, não a aparência. Diferença medida é defeito seu, não do desenho.

**Catraca.** `audit_frontend_standards --max-warnings 246`, `audit_ui_patterns` sem crescer, e a
régua de divergência da E0 estável.

**Corpo do PR.** Etapa E4 · `NOVO-71` · quais famílias saíram, com usos antes e depois.

**Pare e pergunte.** Componente cujo contrato de parâmetro for ambíguo — o mesmo nome de variável
significando coisas diferentes em chamadores diferentes. Não invente o contrato: registre e
pergunte.

---

### E5 ✅ — Call sites migrados, cascas apagadas · `HT-14`, `NOVO-74` · concluída em 10/08/2026

**Objetivo.** Fechar o "mudar o modelo muda todas as páginas" no motor, não na disciplina.

**Concluída.** Os **868 call sites de componentes** foram migrados, app por app, para tags
`<c-…>`. Os 82 componentes canônicos permanecem exclusivamente em `templates/cotton/**`; as 82
cascas, os cinco `.gitkeep` e todo o diretório rastreado `templates/components/**` foram removidos.
O isolamento de contexto do Cotton está habilitado e os **190 includes Django remanescentes** —
parciais de aplicação e slots, não componentes — declaram parâmetros e terminam em `only`.
`audit_frontend_standards` agora reprova tanto include de componente quanto include sem `only`.
Os contratos estáticos percorrem composição, slots e templates dinâmicos; a suíte coletou 1.866
testes e, no host Windows, restaram apenas as duas limitações já conhecidas (WeasyPrint/GTK e o
subprocesso do auditor por socket). A régua visual da E0 permaneceu estável nas 129 combinações.

**Arquivos.** todos os `templates/<app>/**` · `templates/components/**` (removidos ao fim)

**Passo a passo.**

1. App por app, um commit por app: `{% include "components/…" %}` vira `<c-…>`.
2. Ao fim de cada família, apague a casca da E4.
3. **`NOVO-74` — um namespace só.** Hoje existem dois (`components/*` e `components/ui/*`), mais
   quatro pastas fantasma só com `.gitkeep` (`components/buttons`, `forms`, `modals`, `steppers`)
   enquanto os componentes reais moram em `components/ui/buttons/` etc., mais
   `components/form/` (singular, 37 usos) convivendo com `components/forms/` (plural, vazia).
   Tudo passa a ser `templates/cotton/<família>/<nome>.html`; as pastas fantasma saem.
4. **`HT-14` fecha por construção**: cotton passa só o atributo declarado, então os 275 includes
   sem `only` deixam de existir como categoria.

**Prova.**

```bash
grep -rn '{% include "components/' templates --include='*.html'   # tem que voltar vazio ao fim
grep -rc 'components/' --include='*.py' .                          # os render() do Python também
python manage.py test --settings=config.settings.test --parallel 4
python scripts/medir_divergencia_tema.py                           # sem mudança de pixel
```

**Catraca.** Regra nova no `audit_frontend_standards`: `{% include %}` de componente reprova. E o
número de includes sem `only` vai a zero.

**Corpo do PR.** Etapa E5 · resolve `HT-14` e `NOVO-74` · quantos call sites por app.

**Pare e pergunte.** Template renderizado do Python por caminho (o caso do `create_draft.html`) —
esses não aparecem em `grep` de template, e mudar o caminho quebra a view em silêncio.

---

### E6 ✅ — Os componentes que faltam · `HT-08`, `HT-15`, `NOVO-16`, `HT-10`, `HT-07`, `NOVO-80`, `NOVO-81` · concluída em 10/08/2026

> **Como fechou, e o que o enunciado errou.** Os cinco IDs saíram em `70f369c6`..`5b58fac7`; as
> duas travas de regressão saíram no PR #293 (`3996f903`).
>
> O enunciado do `HT-08` dizia que "a maioria é reimplementação de markup, não falta de suporte".
> Era o contrário. O componente tinha lista fechada de 29 variáveis, e os `<button>` do sistema
> dependiam de `id`, `formaction`, `data-*` fora do catálogo, `hidden` e `tabindex` — nada disso
> saía. A correção começou pelo componente (`attrs`, `slot` e `class_name`, que troca a base em
> vez de apendar), e só depois pelos call sites. Duas telas autônomas (`core/login.html` e
> `prestacoes_contas/assinatura/`) são `<html>` sem a folha de ícones, e migrar direto quebrava
> `test_folha_de_icones`; elas usam `plain_button.html`, sem dependência de ícone.
>
> O `NOVO-80` não estava no enunciado: a E5 apagou duas travas de regressão em vez de reapontá-las
> quando `templates/components/` virou `templates/cotton/`. Sem elas, componente morto que volta
> **e já vem sendo usado** não é pego por nada — o guarda de órfão, por construção, só reclama de
> quem não tem consumidor.

**Enunciado original, para registro:**

**Objetivo.** Acabar com o markup reescrito à mão que a componentização deixou para trás.

**Passo a passo, um ID por commit.**

1. **`HT-08` — 82 `<button>` crus** fora de `templates/components/`, assim distribuídos hoje:
   `prestacoes_contas` e `oficios` 6 arquivos cada, `roteiros` e `planos_trabalho` 5, `eventos` 4,
   `termos` 2, e um em cada de `usuarios`, `ordens_servico`, `core` e `base.html`. **Armadilha do
   catálogo:** parte deles tem handler de JS amarrado à classe — confira `static/js/components/*`
   antes de cada substituição, mesma família do `JS-06`.
2. **`HT-15` — `cv-itinerary` em 5 apps**, idêntico byte a byte entre dois deles:
   `oficios/partials/_oficio_card_body.html`, `eventos/…/_evento_card_body.html`,
   `roteiros/…/_roteiro_card_body.html`, `prestacoes_contas/…/_prestacao_card_body.html`,
   `planos_trabalho/…/_plano_card_body.html`. Um cotton só.
3. **`NOVO-16` — o markup do picker copiado à mão**, em 3 templates e 5 arquivos JS (mais
   `oficios-transporte.js`, que reimplementa o picker inteiro). É o outro lado do `JS-06`: o JS já
   largou o nome de classe, o markup não.
4. **`HT-10` — `data-rg-toggle`/`data-motorista-fixo-toggle`** ainda emitidos por
   `components/ui/buttons/field_action_button.html:6,16,17`, um componente **compartilhado**, com
   `data-cv-state-trigger` como sucessor já documentado.
5. **`HT-07` — o "·" concatenado no template**, 10 pontos em 8 arquivos, sem parênteses,
   dependendo da precedência do motor. Vai para o presenter como `join_non_empty(parts, sep=" · ")`,
   que é testável.

**Prova.** Suíte verde; `grep '<button'` fora de componente caindo de 82 rumo a zero; a régua de
divergência da E0 estável; e, para o `HT-07`, teste de presenter que falharia antes.

**Catraca.** `audit_ui_patterns` regra `raw_button` caindo, e `audit_foco_visivel --max 30` — que
está com **folga zero**, então todo botão novo precisa nascer com foco visível.

**Pare e pergunte.** Botão cujo handler de JS depende da classe atual e cuja substituição mudaria
comportamento. Registre e pergunte antes de trocar.

---

### E7a ✅ — Token em duas camadas: onde o token mora · `UI-03` · concluída em 10/08/2026

> **O que o enunciado errou.** Eram **oito** arquivos definindo `--color-*`, não nove. E ele não
> mencionava a família `--theme-*` (40 nomes, 152 definições), que é camada intermediária real —
> consolidar só `--color-*` deixaria uma terceira camada global não declarada.
>
> `base/theme.css` foi dissolvido. Em `page-shell.css`, 4 dos 7 `--color-*` eram mortos e os 3
> vivos foram renomeados para a família do componente, em vez de migrarem para o arquivo de token.
>
> A catraca vale para **escopo raiz**; re-ligação dentro de componente continua permitida, porque
> 45 regras globais leem `var(--color-input-bg)` e 10 leem `var(--color-focus)` — proibir custaria
> duplicar 55 regras sob seletor de container e **subir** especificidade.
>
> A prova é `scripts/resolver_tokens_css.py`: 2131 valores computados, 0 diferenças. Ela existe
> porque nenhum gate do repositório protegia valor de token.

### E7b — Token em duas camadas: a família `cv-field` · `NOVO-51`, `NOVO-54` · risco médio

Medido: `NOVO-51` são **4 nomes** (`--cv-field-bg`, `--cv-field-border`, `--cv-field-focus-ring`,
`--cv-field-border-focus`), e `--cv-field-border` carrega **dois contratos incompatíveis** — 4
consumidores leem como shorthand (`border: var(--cv-field-border)`), 3 leem como cor
(`1px solid var(--cv-field-border)`). `--cv-field-border-focus` não nasce em nenhuma das duas
camadas, só em `fields/select.css:95`.

`NOVO-54` são **37 regras** em 11 arquivos, não 64. Só 2 usam `:where()`.

**Enunciado original da E7, para registro:**

**Objetivo.** Um vocabulário de token único, antes de reescrever qualquer aparência.

**Arquivos.** `static/css/base/tokens.css` · `static/css/base/03-theme-dark.css` · e os sete que precisam
parar de definir cor: `theme.css`, `components/theme-dark-components.css`, `page-shell.css`,
`roteiros.css`, `usuarios.css`, `justificativas.css`, `gdrive-config.css`

**Passo a passo.**

1. Duas camadas e só duas: **`tokens.css`** (o valor) e **`03-theme-dark.css`** (a troca
   semântica). Os outros sete param de definir `--color-*`.
2. Feche o que sobrou do **`NOVO-51`** (as `--cv-*` que ainda são apelido, não token) e do
   **`NOVO-54`** (as 64 sobrescritas de `.cv-field__control` — o `NOVO-65` preservou a família
   `cv-field` de propósito, porque o nome sem prefixo já pertence a outra classe viva; são 260
   ocorrências hoje. A regra base as tornou redundantes —
   remova primeiro as provadamente neutras, depois converta as divergentes, **uma medição por
   vez**).
3. Método já validado no `NOVO-54` e que você deve repetir: regra base entra com `:where()`, que
   zera a especificidade. Sem isso a base **vence** estilo de contexto legítimo — a primeira versão
   mudou 55 elementos por causa disso.

**Prova.** `audit_paleta --max 0`, a régua de divergência da E0, e a contagem de arquivos que
definem `--color-*` indo de 9 para 2.

**Catraca.** Regra nova: token definido em mais de dois arquivos reprova.

**Pare e pergunte.** Token cujo valor difere entre os arquivos que o definem hoje — aí não há
"consolidar", há escolher, e a escolha muda a tela.

---

### E8 — O desenho único · `NOVO-58` · risco **alto** · a dimensionar

> **PARE E PERGUNTE EM TODAS AS SUB-ETAPAS.** Esta etapa não é trabalho de Codex no sentido do
> `AGENTS.md` §6: aplicar um redesenho a 43 telas não tem critério objetivo de pronto. O que o
> plano consegue dar é a régua da E0, que transforma "está certo" no número de divergências
> não-cor, e a exigência de print antes/depois nos dois temas. **A aprovação de cada família é do
> dono.**

**Objetivo.** O redesenho que existe só no tema escuro passa a valer no claro, para que os dois
temas sejam o mesmo desenho com paletas diferentes.

**Contexto medido (`NOVO-58`, 07/08).** 20.975 elementos comparados em 43 telas; **20.203 (96%)**
divergiam em ao menos uma propriedade que não é cor; 45.726 diferenças, 851 pares de valor
distintos. Não é deriva acidental: o cabeçalho de `theme-dark-components.css` diz que houve um
redesenho ("*Extracted from dark-redesign.css*") e ele nunca chegou ao claro. **O tema claro é o
desenho anterior — e é o que o sistema mostra para quem nunca escolheu tema.**

> **⚠️ Este enunciado envelheceu em dois dias, e a primeira coisa que a E8 faz é remedir.**
> Os `NOVO-62` e `NOVO-63` fecharam as duas maiores famílias **depois** dessa medição:

| # | família | contagem de 07/08 | estado em 09/08 |
|---|---|---:|---|
| 8a | tipografia | 19.896 | ✅ **fechada pelo `NOVO-62`** — `Inter` empacotada em `static/vendor/fonts/inter/`, `--font-sans` em `base/tokens.css:176` valendo nos dois temas, `font-family` removido de `theme-dark-components.css:14` |
| 8d | barra lateral | 976 | ✅ **fechada pelo `NOVO-63`** — `.sidebar*` divergente de 1.096 para **96**; a largura virou um token só |
| 8e | `font-size`/`line-height` | 533 | ✅ **em quase tudo**: o `NOVO-63` mediu que **528 dos 533** eram a barra lateral |
| 8f | altura de controle | 378 | ✅ **toda**: o `NOVO-63` mediu que os 378 eram a barra lateral |
| 8b | borda `0px` → `1px` | 1.416 | 🔴 **bloqueada na camada de token — `NOVO-92`** (remedida em 10/08; ver abaixo) |
| 8c | raio `14px` → `10px` | 940 | ✅ **fechada em 10/08** — 43 das 116 regras, 1.116 elementos |
| 8g | `justify-content` `normal` → `center` | 230 | ⛔ **pulada por decisão do dono — `NOVO-93`**: move a régua e não move um pixel |
| 8h | **gaveta da barra lateral** | — | 🟠 **aberta, deixada de fora de propósito pelo `NOVO-63`**: sob `@media (max-width: 840px)` o escuro usa `position: fixed` + `height: 100dvh` e o claro `position: relative`. Isso não é geometria, é **comportamento** — vira gaveta sobreposta em vez de coluna no fluxo, e depende de `.app-mobile-bar__toggle` e `.sidebar-drawer-close` se comportarem igual nos dois temas |

**Portanto a 8-zero é remedir.** Rode `scripts/medir_divergencia_tema.py` da E0 e reescreva a
tabela acima antes de tocar em CSS. O `PLANO_MESTRE` §7.4 é explícito: número velho é o quarto erro
que mata um ciclo.

#### A remedição de 10/08, e o instrumento que ela exigiu

A tabela de 07/08 conta **elementos que divergem**. Isso confunde três coisas diferentes, e as três
apareceram na E8:

1. a regra existe e muda o que se vê;
2. a regra existe, diverge, e **não pinta nada** (o `NOVO-90`: `-webkit-font-smoothing` divergia em
   20.100 elementos e os prints saíam idênticos byte a byte);
3. o elemento está fora da tela naquela largura ou naquele estado — menu fechado, diálogo fechado,
   barra de celular escondida no desktop. Pinta, mas só depois de o usuário abrir alguma coisa.

Medido **regra a regra**, com o predicado de tema retirado do seletor e os elementos procurados nas
43 rotas, nas três larguras, depois do `#304`:

| família | regras só-escuras | com efeito | elementos @1440 | @800 | @500 | dos quais visíveis @1440 |
|---|---:|---:|---:|---:|---:|---:|
| 8b borda | 186 | **54** | 754 | 754 | 760 | 285 |
| 8c raio | 116 | **43** | 1.116 | 1.116 | 1.128 | 451 |
| 8g `justify-content` | 16 | **7** | 137 | 137 | 170 | — |

Duas conclusões que a contagem antiga escondia:

- **214 das 318 regras catalogadas não mudam nada** — ou o elemento não existe naquelas rotas, ou o
  claro já computa o mesmo valor. Contá-las como trabalho pendente superestimava a etapa.
- **"Invisível" quer dizer coisas diferentes na 8g e na 8b/8c.** Na 8g a propriedade *não consegue*
  pintar (não há folga no container, ou o elemento nem é caixa flex no claro) — é inútil por
  construção, e virou o `NOVO-93`. Na 8b/8c o elemento só não está na tela **no estado de repouso**;
  ele pinta quando o menu ou o diálogo abre. Por isso a 8c foi feita inteira e a 8g não foi feita.

**Instrumento novo desta etapa:** o print antes/depois deixou de ser conferência visual e virou
número. `prova_pixel.py` fotografa 10 componentes × 3 larguras × 2 temas e conta pixels diferentes.
A 8c fechou com **0 pixels diferentes no tema escuro nas 30 comparações** e mudança em 8 dos 10
componentes no claro. Sem isso não há como distinguir o caso 1 do caso 2.

**Duas lições de método que o `NOVO-63` pagou e você não deve pagar de novo:**

- **Meça em três larguras — 1440, 800 e 500 px.** Seis das 23 regras de barra lateral do tema
  escuro vivem dentro de `@media`. Globalizar uma sem levar a media junto aplica geometria de
  celular em tela cheia, e isso **não aparece** numa medição só a 1440px: aparece no celular de
  alguém.
- **Edite o valor onde ele já mora; não mova a regra.** Mover muda posição na cascata e
  especificidade de uma vez, e aí nenhuma diferença medida é atribuível.

**A armadilha da tipografia, para quando alguém reabrir o assunto.** O número "19.896 elementos"
media a pilha **declarada**, não a face que o usuário vê. Neste contêiner Linux, `Inter`,
`Segoe UI Variable` e `Segoe UI` devolvem largura idêntica — isso é substituição do fontconfig, não
instalação. **Não dá para determinar daqui** o que renderiza na máquina do usuário; essa
conferência exige uma máquina igual à dele.

**Prova.** `scripts/medir_divergencia_tema.py` caindo a cada sub-etapa, com o número no PR, mais
print antes/depois nos dois temas, nas três larguras.

**Catraca.** A divergência não-cor da E0, que só desce.

---

### E9 — O tema escuro dissolvido em token · `UI-02` · risco médio · 3–4 d

**Objetivo.** `theme-dark-components.css` deixa de ser camada de exceção e vira consequência do
token.

**Contexto.** 5.619 linhas e 190 `!important` — o maior arquivo CSS do projeto depois do bundle.
Ele só é grande porque carrega **geometria**; com a E8 feita, o que sobra é diferença de cor, que
o token resolve.

**Prova.** `!important` fora do bundle caindo de 496; linhas do arquivo caindo de 5.619; a régua de
divergência estável (a E9 não pode mudar aparência — a E8 já mudou).

**Catraca.** Contagem de `!important` fora do bundle, nova, só desce.

**Pare e pergunte.** Todo `!important` que você **não** conseguir remover: ele está compensando
especificidade que alguém depende. Liste-os no PR em vez de forçar.

---

### E10 — A fronteira de domínio · `UI-04` · risco médio · a dimensionar

**Objetivo.** Componente compartilhado para de morar dentro de arquivo de domínio, para que quem
quer o componente pare de levar o domínio junto.

**Contexto medido hoje.** **97 imports de CSS em 36 templates** (eram 54 em 26 em 05/08 — piorou).
`oficios.css` é importado 19 vezes, `roteiros.css` e `prestacoes_contas.css` 10 cada, `termos.css`
9. Em `templates/prestacoes_contas/index.html`, `oficios.css` (106 KB) chega com **0,0% de uso**.

**Passo a passo.** Extraia os componentes compartilhados dos arquivos de domínio para
`fields/`, `actions/`, `lists/` e `feedback/`, domínio por domínio, e derrube o import correspondente. Dimensione com a
régua da E0: o que não é usado na rota não devia estar sendo entregue nela.

**Prova.** `scripts/medir_css_por_rota.py` — **é aqui que a métrica de aceite da frente inteira
tem que bater: uso acima de 35% por rota**, contra os 10,1%–11,8% de hoje.

**Catraca.** Uso de CSS por rota, da E0. Só sobe.

---

### E11 — A entrega do JavaScript · `HT-04`, `JS-07`, `JS-08`, `JS-09`, `JS-10` · risco médio · 5 d

**Objetivo.** Parar de entregar em toda página o que só algumas usam.

**Passo a passo, um ID por commit.**

1. **`HT-04`** — `base.html:11,45` carrega `shell.bundle.css` e `shell.bundle.js`
   incondicionalmente, e ~153 KB do JS (57% do bundle) são exclusivos dos wizards de
   ofício/roteiro/termo/prestação. Separe bundle "núcleo" de bundle "documentos", usando os
   `{% block extra_js %}`/`{% block extra_css %}` que `base.html:12-13,46` já tem. Mitigue a
   regressão silenciosa — template que esquece de declarar — com regra no auditor ou teste de
   fumaça por tela.
2. **`JS-07`** — "fechar ao clicar fora / Esc" em 4 cópias (`picker.js`, `date-picker.js`,
   `cv-select.js` — que a E2 já apagou —, `picker-select.js`). `components/overlay.js:471-503` já
   tem a base. **Correção do catálogo que você precisa conhecer:** nenhuma das quatro fecha em
   `scroll`/`resize`; só `date-picker.js:794-795` **reposiciona**. Não implemente um fechamento que
   não existia.
3. **`JS-08`** — corte por componente, não pelo bloco. A coluna "templates que usam" do enunciado
   original estava errada: `segment-nav.js` chega a ≥4 templates e `file-picker.js` a ≥6, por
   `{% include %}` com variável. O ganho é menor do que o catálogo prometia.
4. **`JS-09`** — `templates/documentos/geracao_aguarde_embedded.html:27` é documento autônomo que
   carrega 264 KB para usar `CV.http.fetchJson` (3,3 KB).
5. **`JS-10`** — decidir os stubs de 3 linhas do editor de roteiros (`state.js`, `retorno.js`,
   `diarias.js`): completar a extração ou removê-los. **Depende do `BE-13`** — pergunte.

**Prova.** KB por rota antes/depois, `npm test` da E1 verde, suíte verde.

**Catraca.** Os tetos de `scripts/tetos_desempenho.json`, que já existem por rota e volume.

---

## 5. Aceite da frente inteira

A reconstrução termina quando, medido por comando e não por opinião:

| critério | hoje | meta |
|---|---:|---|
| uso de CSS por rota (`PF-02`) | 10,1%–11,8% | **> 35%** |
| divergência não-cor entre temas (`NOVO-58`) | 20.203 elementos (96%) em 07/08, **antes** dos `NOVO-62`/`63` — remeça na E0 | **próximo de zero** |
| `!important` fora do bundle (`UI-02`) | 496 | queda declarada |
| arquivos definindo `--color-*` (`UI-03`) | 9 | **2** |
| imports de CSS de domínio alheio (`UI-04`) | 97 em 36 templates | queda declarada |
| includes sem `only` (`HT-14`) | 275 de 946 | **0**, por construção |
| `<button>` fora do componente (`HT-08`) | 82 | **0** |
| teste automatizado de JS (`JS-03`) | 0 | piso no CI |

## 6. O que este plano não faz

- **Não mexe no backend.** A Fase 6 (`BE-11`…`BE-16`) é superfície disjunta e pode correr em
  paralelo, em branch própria. A exceção é o `JS-10`, que depende do `BE-13`.
- **Não renumera os IDs colididos do catálogo.** `NOVO-45`, `NOVO-49`, `NOVO-50` e `NOVO-51`
  aparecem duas vezes cada, por acidente de sessões paralelas. Renumerar quebra o rastro dos PRs
  que já os citam; a colisão fica registrada e os IDs novos começam em `NOVO-69`.
- **Não persegue número de Lighthouse.** A régua é a deste documento e a do
  [`PLANO_DESEMPENHO.md`](PLANO_DESEMPENHO.md): KB, consultas, uso de CSS por rota e divergência
  entre temas — tudo reproduzível por comando.
