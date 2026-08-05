# `NOVO-30` fase 1 — estado da fusão da camada de tokens

> **Superado em 05/08.** As fases 2–4 fizeram a fusão da camada de tokens por
> outro caminho (o que está em `static/css/01-tokens.css` hoje é o resultado
> delas, não desta proposta). Este documento e o `docs/PROPOSTA_01_TOKENS.css`
> ficam como registro do inventário medido — os números continuam válidos e
> foram o insumo das fases seguintes —, não como plano a executar.

**04/08/2026.** Documento de passagem: o que foi medido, o que foi decidido e o que
falta. Existe porque a fusão é maior do que uma sessão comporta com verificação
honesta, e a metade sem verificação não vale nada.

## Por que a entrega do Codex foi recusada

Commit `8996de60`, branch `codex/novo30-fase1-tokens`. Rodei os gates:

**Passou:** os três arquivos foram fundidos e apagados, suíte verde (1307), −3.472
linhas, avisos 384 → 335, exceções 5 → 3, zero token fora da camada. A paleta
sobreviveu — conferido na tela nos dois temas.

**Reprovou:**

1. **519 tokens distintos em 934 declarações**, contra a meta de ≤ 60. Não houve
   consolidação, houve mudança de endereço: `--theme-surface-card` e `--shadow-card`
   estão declarados **5 vezes** no mesmo arquivo.
2. **1.637 linhas com sete blocos `:root` e cinco `html[data-theme="dark"]`**
   intercalados — quem vence depende da ordem. Oito linhas passam de 2.000
   caracteres; a maior tem **11.959**. Blocos repetidos literalmente
   (`.sidebar-theme` e `.app-theme-grid` aparecem duas vezes; as linhas 1530 e 1531
   são idênticas). É assinatura de concatenação, não de fusão.
3. **59 seletores de componente dentro do arquivo de tokens.** `.cv-form-block`
   passou a ser estilizado em dois lugares — pior de manter, não melhor.
4. **Editou `test_paleta.py` para acomodar o código.** O mecanismo sobreviveu, então
   não foi burla; mas o padrão é o que a regra 5 do `AGENTS.md` proíbe.
5. **Regressão visual:** o campo de busca do rail voltou a `#f8fafd`. Cadeia:
   `list-header.css:355` → `var(--step1-field, …)` caindo no fallback.

## Inventário medido (a partir de `main`, 7f273a52)

| | |
|---|---:|
| tokens declarados em `tokens.css` + `theme.css` + `03-theme-dark.css` | **499** |
| referenciados fora da camada | **359** |
| **órfãos — morrem sem substituto** | **140** |
| pares (valor claro, valor escuro) distintos entre os usados | 269 |
| grupos por família semântica + valor | 284 |

O salto de 284 para ~47 **não é mecânico**: exige decidir que as ~50 variações de
quase-branco e quase-cinza são, pela paleta, uma das três superfícies. Foi por isso
que a tarefa saiu do Codex (`AGENTS.md` §6).

## O que já está pronto

**`docs/PROPOSTA_01_TOKENS.css`** — a camada canônica escrita e documentada:
**47 tokens**, um bloco `:root`, um `html[data-theme="dark"]` que redeclara
**somente cor** (4 tokens: tinta e os três estados). Geometria, tipografia, sombra e
movimento são iguais nos dois temas — é a regra do espelho por construção.

Tinta e borda são **derivadas por `color-mix` sobre a superfície**, não escolhidas:
`--cv-ink-muted` é 62% de tinta sobre o card, `--cv-border` é 14%. Trocar a
superfície move as duas sozinhas.

**`scripts/mapear_tokens.py`** — o motor do mapa. Resolve a cadeia `var()` de cada
token nos dois temas, agrupa por família semântica e escolhe o canônico mais próximo
(cor por **ΔE em Lab**, geometria por degrau da escala). Mapeou **199 dos 359**.

## O que falta

1. **Os 149 tokens sem mapa.** Não são resto fácil — cada família precisa de regra
   própria: valores `rgba()`, compostos (`1px solid var(…)`), gradientes, e tokens
   que só existem no escuro (valor claro vazio). Os mais usados estão listados pela
   saída do script.
2. **Aplicar o mapa** em 65 arquivos CSS, templates e JS.
3. **Apagar** `tokens.css`, `theme.css`, `03-theme-dark.css` e ligar a camada nova no
   `style.css` e no `build_shell_bundles.py`, **depois** de `00-palette.css`.
4. **Caçar as regressões.** É a parte grande e a que não pode ser pulada: uma troca
   desse tamanho mexe em toda tela. `scripts/medir_paleta.py` nos dois temas, e a
   suíte não substitui isso — ela não olha a tela.

## Gate da fase, quando for executada

```bash
python manage.py test --settings=config.settings.test          # >= 1307 verdes
python scripts/audit_frontend_standards.py --max-warnings 384
python scripts/build_shell_bundles.py --check
python - <<'PY'
import pathlib, re
t = (pathlib.Path('static/css/01-tokens.css')).read_text()
assert t.count(':root {') == 1, 'mais de um bloco :root'
assert t.count('html[data-theme="dark"] {') == 1, 'mais de um bloco escuro'
assert not re.search(r'^\s*\.[a-z]', t, re.M), 'seletor de componente na camada de tokens'
assert max(len(l) for l in t.splitlines()) <= 120, 'linha acima de 120 caracteres'
n = len(re.findall(r'^\s*--[a-z0-9-]+\s*:', t, re.M))
assert n <= 60, f'{n} tokens, teto 60'
PY
```

> **Nota de método.** A entrega do Codex tinha suíte verde e mesmo assim estava
> errada. A suíte prova que nada quebrou; não prova que o objetivo foi atingido.
> Para esta fase o critério é o arquivo em si — número de tokens, número de blocos,
> ausência de seletor — e por isso o gate acima olha o arquivo, não o comportamento.
