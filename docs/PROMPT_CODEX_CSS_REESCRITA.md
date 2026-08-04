# Prompt para o Codex — reescrita completa do CSS (`NOVO-30`)

Escopo fechado por fase, cada uma com o comando que prova o resultado. Mande **uma fase
por vez**; só abra a seguinte com a anterior mergeada. Convenção de branch:
`codex/novo30-fase<N>-<assunto>` (plano §5.6).

## Linha de base medida em 04/08/2026

Cole estes números no prompt: sem alvo numérico o Codex escolhe o próprio escopo.

| | 04/08 (base) | depois da 3a | alvo |
|---|---:|---:|---:|
| arquivos CSS | 65 | 62 | ≤ 25 |
| linhas de CSS | 42.496 | 40.375 | ≤ 13.000 |
| tokens `--*` | **1.010** (medido depois: 1.034) | **57** | **≤ 60** |
| `data-theme` fora dos arquivos de token | **1.106** | 0 | **0** |
| `!important` | 497 | — | ≤ 20 |
| literais de cor fora dos tokens | 620 | — | 0 |
| `border-radius` distintos | 99 | 53 → **6** (3b) | 6 |
| `padding` distintos | 247 | 214 → **8** (3b) | 8 |
| `margin` distintos | 53 | 50 → **3** (3b) | 8 |
| `border` distintos | 321 | 58 → **3** (3b) | 3 |
| `box-shadow` distintos | 184 (medido: 202) | 136 → **2** (3c) | 4 → **2** (decisao de produto) |
| exceções de arquivo no auditor | 8 (medido: 3) | 2 | 0 |
| avisos do `audit_frontend_standards` | 384 | 212 | 0 |

---

## A regra que organiza tudo: o tema claro é espelho do tema escuro

Esta é a exigência central. Ela tem uma tradução mecânica, e é o gate mais importante:

> **Nenhum arquivo de componente pode conter `html[data-theme=...]`.** Um componente
> declara aparência uma vez, em token semântico. Um tema é só um mapa de valores desses
> tokens. Mudança feita no escuro aparece no claro sozinha, porque só existe uma regra.

Hoje isso é violado **1.106 vezes** — 799 só em `components/theme-dark-components.css`,
mais 38 em `list-header.css`, 31 em `usuarios.css`, 28 em `planos-trabalho-eventos.css`.
Cada uma dessas é uma regra escrita duas vezes que pode divergir, e é por isso que o claro
não acompanha o escuro hoje.

Os **únicos** arquivos onde `data-theme` pode aparecer, ao fim da reescrita:
`00-palette.css` e `01-tokens.css`.

---

## Fase 1 — a camada de token única

**ETAPA e ID:** `NOVO-30`, fase 1.

**FONTE:** `static/css/00-palette.css` (já existe e está correto — não mexa nele) e
`docs/PLANO_REFATORACAO_EXECUCAO.md` §7, bloco "Paleta de tres cores".

**TAREFA:** funda `tokens.css`, `theme.css` e `03-theme-dark.css` num único
`static/css/01-tokens.css` com **no máximo 60 tokens**. Hoje são 1.010 em três arquivos que
se sobrescrevem.

Regras da nova camada:

1. **Cor**: nenhum token de cor novo. As superfícies já existem em `00-palette.css`
   (`--cv-surface-page/card/block`, `--color-accent`, `--on-accent`, `--accent-tint`).
   Adicione só o que falta e não dá para derivar: tinta de texto, tinta apagada, e os três
   estados semânticos (erro, sucesso, alerta). **Toda a demais cor sai de `color-mix()`
   sobre esses.**
2. **Geometria**: escalas fechadas, e nada fora delas.
   - raio: `--r-sm: 8px` · `--r-md: 14px` · `--r-lg: 20px` · `--r-xl: 28px` · `--r-pill: 999px` · `--r-0: 0`
   - espaço: `--sp-1: 4px` até `--sp-8: 48px`, dobrando a escada (4/8/12/16/20/24/32/48)
   - borda: `--bd: 1px solid var(--cv-border)` · `--bd-0: 0` · `--bd-strong: 2px solid var(--cv-border)`
   - sombra: `--sh-sm` · `--sh-md` · `--sh-lg` · `--sh-none`
3. **Um tema é um mapa de valores.** `:root` traz o claro; `html[data-theme="dark"]`
   redeclara **apenas os valores de cor**, nunca geometria e nunca uma regra de componente.
   Se o escuro precisar de raio diferente do claro, a regra está errada.

**ESCOPO FECHADO:** só criar `01-tokens.css` e apagar os três antigos, atualizando os
`@import` e `scripts/build_shell_bundles.py`. **Não toque em arquivo de componente nesta
fase** — eles vão continuar funcionando por alias temporário: no fim de `01-tokens.css`,
mapeie os nomes velhos ainda usados para os novos (`--color-surface: var(--cv-surface-card)`
etc.). Esses aliases morrem na fase 3.

**GATE — pronto é quando estes três comandos saem com 0:**

```bash
python manage.py test --settings=config.settings.test          # 1307 testes verdes
python scripts/audit_frontend_standards.py --max-warnings 384  # catraca nao sobe
python - <<'PY'
import pathlib, re
n = 0
for f in pathlib.Path('static/css').rglob('*.css'):
    if f.name in ('shell.bundle.css', '00-palette.css', '01-tokens.css'): continue
    n += len(re.findall(r'^\s*--[a-z0-9-]+\s*:', f.read_text(errors='replace'), re.M))
print('tokens fora da camada:', n); assert n == 0, 'token declarado fora de 01-tokens.css'
PY
```

---

## Fase 2 — a regra do espelho

**ETAPA e ID:** `NOVO-30`, fase 2. **É a fase que resolve o problema que você descreveu.**

**TAREFA:** eliminar as 1.106 ocorrências de `data-theme` fora da camada de token.

Procedimento, arquivo por arquivo, começando por `components/theme-dark-components.css`
(799 das 1.106):

1. Para cada regra sob `html[data-theme="dark"]`, identifique **o que ela muda** em relação
   à regra clara equivalente.
2. Se muda **só cor**: apague a regra escura e faça a regra clara usar um token. O valor do
   escuro vira o valor daquele token em `html[data-theme="dark"]` dentro de `01-tokens.css`.
3. Se muda **geometria** (raio, padding, borda, sombra): isso é defeito, não tema. Escolha
   **um** valor — o do escuro, que é o consolidado — e use nos dois.
4. Se a regra escura existe só para vencer especificidade (`:is(...)`, `[data-*]`,
   `!important`): apague-a e **baixe a especificidade da regra clara** em vez de subir a
   escura. Foi a guerra de especificidade que produziu os 497 `!important`.

**Não invente componente novo e não renomeie classe nenhuma nesta fase.** Renomear e
corrigir no mesmo PR é o erro nº 2 da §8 do plano.

**GATE:**

```bash
python manage.py test --settings=config.settings.test
python - <<'PY'
import pathlib
permitidos = {'00-palette.css', '01-tokens.css', 'shell.bundle.css'}
sujos = {f.as_posix(): f.read_text(errors='replace').count('data-theme')
         for f in pathlib.Path('static/css').rglob('*.css')
         if f.name not in permitidos and 'data-theme' in f.read_text(errors='replace')}
print(sujos or 'limpo'); assert not sujos, 'tema dentro de componente'
PY
```

Ao fim desta fase, `components/theme-dark-components.css` **não existe mais**.

---

## Fase 3 — geometria padronizada e fim dos aliases

> **Corrigido em 04/08/2026 (`NOVO-31`).** A linha de base desta fase estava errada: o
> enunciado supunha "27 tokens canônicos + aliases", e o arquivo tinha **1.034 nomes em
> 2.078 declarações**, 88 blocos de regra de componente e linhas de 11.959 caracteres. O
> gate da fase 1 media token **fora** da camada e nunca dentro. Medido de novo, a fase 3
> tinha 8.287 referências `var()` e 3.622 declarações de geometria — não cabia num PR, e
> saiu em três: **3a** (camada de token), **3b** (raio/espaço/borda) e **3c** (sombra e
> foco) — as três feitas. Na 3c o alvo mudou por decisão de produto: **uma** sombra
> mínima em vez de quatro, e **nenhum** indicador de foco em vez de migrar o anel para
> `outline` (regressão de WCAG 2.4.7 registrada no plano).
>
> Duas correções ao método, que valem para as fases seguintes:
>
> 1. **O gate abaixo mede só a forma curta.** `padding-inline`, `border-color` e
>    `border-start-start-radius` passam por baixo dele — dá para "zerar" o contador
>    empurrando o valor para a forma longa. O gate entregue mede as duas, e mede também
>    a *família* do token: `padding: var(--sh-lg)` é sintaticamente válido, o navegador
>    descarta a declaração e o card fica sem respiro, sem quebrar teste nenhum. Foi
>    exatamente o que aconteceu ao consolidar um token que guardava `12px 16px 12px 32px`.
> 2. **Escala fechada tem piso e teto.** Abaixo de 4px é espessura de traço (1px de borda
>    virava 4px — quatro vezes mais grossa) e acima de 48px é medida de layout
>    (`max-width: 960px` virava 48px). Nos dois extremos o valor fica literal; a escada
>    não se estica para cobri-los.

**TAREFA:** trocar todo valor solto pelas escalas da fase 1 e apagar os aliases temporários.

- 99 raios → 6 · 247 paddings → 8 · 53 margens → 8 · 321 bordas → 3 · 184 sombras → 4
- Onde um valor não cair exatamente na escala, **arredonde para o degrau mais próximo**.
  Não crie degrau novo: a escala é fechada. Se um componente parecer exigir um valor fora
  dela, o componente está errado.
- Apague os aliases de nome velho do fim de `01-tokens.css`. Nada deve mais referenciar
  `--color-surface`, `--surface-form-section`, `--step1-*` e afins.

**GATE:**

```bash
python manage.py test --settings=config.settings.test
python - <<'PY'
import pathlib, re
ESCALA = {'border-radius': 6, 'padding': 8, 'margin': 8, 'border': 3, 'box-shadow': 4}
for prop, teto in ESCALA.items():
    vals = set()
    for f in pathlib.Path('static/css').rglob('*.css'):
        if f.name == 'shell.bundle.css': continue
        vals |= set(re.findall(rf'{prop}:\s*([^;]+)', f.read_text(errors='replace')))
    print(f'{prop}: {len(vals)} (teto {teto})')
    assert len(vals) <= teto, f'{prop} fora da escala: {sorted(vals)[:12]}'
PY
```

---

## Fase 4 — fim das exceções e do `!important`

**TAREFA:** zerar as 8 exceções de arquivo declaradas em
`scripts/audit_frontend_standards.py` e em `core/tests/test_css_tokens.py`, e derrubar os
497 `!important` para ≤ 20.

Cada `!important` que sobrar precisa de comentário de uma linha dizendo **qual regra de
terceiro ele está vencendo** — se não estiver vencendo nada de fora, é para apagar.

Baixe as catracas para o número novo no mesmo PR (elas só descem — `AGENTS.md`, regra 5).

**GATE:**

```bash
python manage.py test --settings=config.settings.test
python scripts/audit_frontend_standards.py --max-warnings 0
grep -rc '!important' static/css --include='*.css' --exclude='shell.bundle.css' \
  | awk -F: '{s+=$2} END {print "important:", s; exit (s>20)}'
```

---

## Fase 5 — apagar o CSS antigo

**TAREFA:** remover todo arquivo que a reescrita deixou órfão, até chegar a ≤ 25 arquivos
e ≤ 13.000 linhas.

**Regra 6 do `AGENTS.md` vale integralmente:** nada é apagado sem prova. Para cada arquivo
removido, cole no corpo do PR o `grep` no repositório inteiro — templates, JS, CSS e Python
— mostrando zero referências. Arquivo sem prova volta.

**GATE:**

```bash
python manage.py test --settings=config.settings.test
python scripts/build_shell_bundles.py --check
python manage.py collectstatic --noinput --clear --settings=config.settings.prod
find static/css -name '*.css' ! -name 'shell.bundle.css' | wc -l          # <= 25
find static/css -name '*.css' ! -name 'shell.bundle.css' -exec cat {} + | wc -l   # <= 13000
```

---

## Vale para todas as fases

**Não mexa em `static/css/00-palette.css`.** As três superfícies e o acento estão medidos e
decididos; ele é a fonte da verdade da cor.

**Verificação visual obrigatória antes de abrir o PR.** Rode:

```bash
python manage.py runserver 127.0.0.1:8000 --noreload &
python scripts/medir_paleta.py
```

Ele abre as telas nos dois temas e lista **toda cor fora da paleta**. Cole a saída no corpo
do PR. Uma fase que aumenta o número de cores fora da paleta está errada, mesmo com a suíte
verde — a suíte não olha a tela.

**Entrega:** PR com o corpo do `AGENTS.md` §5, a linha da fase marcada em
`docs/PLANO_REFATORACAO_EXECUCAO.md`, e prints antes/depois nos dois temas.

**O que NÃO fazer, em nenhuma fase:** renomear classe (é etapa própria), mexer em template
ou JS (a estrutura já está consolidada), criar token fora da camada única, e afrouxar
qualquer catraca para o PR passar.
