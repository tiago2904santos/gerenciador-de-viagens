# Plano de reescrita do HTML e da biblioteca de componentes globais

**Data:** 05/08/2026 · **Posição na fila:** Etapa 9 (§7.1 do `PLANO_REFATORACAO_EXECUCAO.md`)
**Regras de conduta:** [`AGENTS.md`](../AGENTS.md) — este plano não as substitui, só as aplica ao HTML.
**Base medida:** `main` em `1336 testes verdes / 17,1 s`, auditor frontend em `0 erros, 184 avisos`.

---

## 1. Por que existe um plano novo se a Etapa 6 está fechada

A Etapa 6 fechou os defeitos que a auditoria de HTML catalogou (`H-02`..`H-10`, `D-41`): casco
de fluxo, card mestre, ordinais latinos, semântica de lista, ARIA. Ela consertou **defeitos**.
Ela nunca prometeu **unificar a biblioteca** — e não unificou.

O que sobrou é de outra natureza. Não é um defeito por tela, é uma propriedade do conjunto:
existem hoje **duas bibliotecas de componentes ocupando a mesma pasta**, e a maior parte das
páginas escolhe entre elas por acidente histórico. O sintoma que o usuário relata — "componentes
semelhantes com a mesma função" — é exatamente isto, e é mensurável.

Este plano trata o conjunto. Ele é uma etapa de **estrutura**, não de aparência: nenhuma fase
aqui muda cor, espaçamento ou nome de classe CSS. O que muda é qual arquivo existe, como ele
se chama, onde ele mora e qual contrato ele declara.

---

## 2. Linha de base medida em 05/08/2026

Todo número abaixo veio de comando rodado no `main` desta data. O comando está junto para que
a medição seja refeita, não acreditada.

| Medida | Valor | Como medir |
|---|---:|---|
| Componentes em `templates/components/` | **96** | `find templates/components -name '*.html' \| wc -l` |
| Famílias que existem **duas vezes** (em `components/` e em `components/ui/`) | **8** | `feedback`, `forms`/`form`, `lists`, `cards`, `layouts`/`layout`, `modals`, `filters`, `tables` |
| Componentes sem **nenhuma** referência no repositório | **5** | busca do caminho em `.html`/`.py`/`.js` |
| Componentes referenciados **só** pelo UI Lab ou por teste | **9** | idem, excluindo `templates/dev/`, `templates/ui_lab2/`, `test_*` |
| Aliases de uma linha (arquivo cujo corpo é um único `include`) | **10** | `find templates -name '*.html' -size -2k` + leitura |
| Componentes de botão para um `<button>` | **7** | `ls templates/components/ui/buttons/` |
| Sistemas de confirmação de exclusão coexistindo | **4** | ver §3, `NOVO-42` |
| Grupos de partials locais **byte-idênticos** (SHA-256) | **10** | `sha256sum` sobre `templates/` fora de `dev/` e `ui_lab2/` |
| Páginas `confirm_delete.html` quase idênticas | **12** | `find templates -name confirm_delete.html` |
| Cascos de wizard divergindo em 5 linhas | **2** | `diff templates/oficios/wizard_base.html templates/planos_trabalho/wizard_base.html` |
| Páginas que estendem `base.html` direto × via `flow_base` | **46 × 18** | `grep -rl 'extends "base.html"'` |
| `{% include %}` no total | **1.262** | `grep -rho '{%[ ]*include [^%]*%}' templates \| wc -l` |
| …destes, **sem `only`** | **390** (31%) | mesmo comando, `\| grep -v ' only'` |
| Templatetags do projeto | **0** | `find . -name templatetags -type d` |

**A leitura destes números:** a biblioteca não é grande demais — 96 arquivos para um sistema
deste porte é razoável. O problema é que ela é **duas bibliotecas de ~50**, e o critério para
escolher entre elas não está escrito em lugar nenhum.

### 2.1 Uma correção de método, registrada antes de virar erro

A primeira contagem de órfãos deste plano deu **21 componentes sem uso**. Estava errada: ela
procurava só `{% include "caminho" %}`, e o projeto passa caminho de template **como valor de
parâmetro** (`band_tabs_template="components/lists/list_toggle.html"`,
`body_template="…/_evento_card_body.html"`). Contando também as referências por string, os
órfãos reais são **5**, não 21.

Isso não é detalhe de contagem — é uma **propriedade da arquitetura atual** que qualquer fase
deste plano precisa respeitar: neste projeto, o grafo de dependência entre templates não é
sintático. Ferramenta que só olhe `{% include %}` apaga arquivo vivo. O gate da Fase 0 tem de
resolver o caminho passado por parâmetro, e o `grep` de prova exigido pela regra 6 do
`AGENTS.md` tem de ser pelo caminho, não pelo nome do arquivo.

---

## 3. Catálogo de defeitos (`NOVO-39` a `NOVO-54`)

Entram no catálogo com origem `NOVO`, como manda o `AGENTS.md` §2. Nenhum deles existe nas
auditorias de 27–28/07 — são propriedades do conjunto, e auditoria página-a-página não as vê.

| ID | Sev. | Defeito | Evidência |
|---|:--:|---|---|
| `NOVO-39` | 🟠 | **Duas taxonomias paralelas.** `components/<família>/` e `components/ui/<família>/` coexistem; 8 famílias existem nas duas. Não há regra escrita para escolher. | `components/feedback/alerts.html` × `components/ui/feedback/alert.html`; `components/form/card.html` × `components/ui/forms/form_block.html`; `components/lists/` × `components/ui/lists/` |
| `NOVO-40` | 🟠 | **5 componentes órfãos e 9 vivos só por UI Lab/teste.** `main_list_card.html` tem 167 linhas e é mantido vivo por uma asserção em `test_dark_redesign.py:611` — nenhuma página o usa. | ver §2 |
| `NOVO-41` | 🟠 | **10 aliases de uma linha.** Os 7 `*_list_card.html` de módulo, `field_manage_button`, `floating_primary_action` (o próprio arquivo se declara *"Compatibility alias"*), `feedback/confirm_delete_block`. A padronização de 22/07 declarou ter eliminado aliases; eles voltaram. | `templates/eventos/partials/evento_list_card.html` (1 linha) |
| `NOVO-42` | 🔴 | **4 sistemas de confirmação de exclusão.** `ui/modals/confirm_delete.html` (seção de página, 26 linhas), `ui/modals/delete_confirm_modal.html` (diálogo, 27 linhas), `ui/modals/confirm_action_modal.html` (genérico), `feedback/confirm_delete_block.html` (alias do primeiro). Dois têm nome quase igual e comportamento diferente: um é página, o outro é modal. | `diff` dos dois primeiros: 0 linha em comum |
| `NOVO-43` | 🟠 | **7 componentes de botão.** `button`, `icon_button`, `field_action_button`, `field_manage_button`, `floating_action`, `floating_primary_action`, `footer_action` — para um elemento que a plataforma resolve com `variant` e `shape`. Três deles nunca são usados em produção. | `ls templates/components/ui/buttons/` |
| `NOVO-44` | 🟠 | **3 sistemas de alerta.** `feedback/alerts.html` (loop de `messages`), `ui/feedback/alert.html` (unitário), `ui/feedback/form_errors.html` (que é um `alert` com texto fixo). Todos emitem `cv-notice` **e** a classe legada `alert`. | `templates/components/ui/feedback/alert.html:2` |
| `NOVO-45` | 🟠 | **2 sistemas de card de formulário, ambos vivos e grandes.** `components/form/card.html` (102 linhas, 29 usos) e `components/ui/forms/form_block.html` (112 linhas, 37 usos). Os dois carregam contexto sem `only` e os dois precisaram da mesma correção de vazamento de parâmetro (`H-05`, `H-04`) — o mesmo defeito, consertado duas vezes. | linhas do plano em `H-04`/`H-05` |
| `NOVO-46` | 🟠 | **2 sistemas de item de lista.** `lists/simple_list_row.html` (183 linhas) e `ui/lists/entity_card*` (4 arquivos, 170 linhas). | `wc -l` |
| `NOVO-47` | 🟠 | **10 grupos de partials locais byte-idênticos.** Ex.: `_atividades_wizard_footer` = `_efetivo_diarias_wizard_footer` = `_wizard_footer_next`; `_justificativa_wizard_footer` = `_transporte_footer` = `roteiros/…/actions.html`; `cargos/_quick_add_fields` = `combustiveis/_quick_add_fields`. | `sha256sum` |
| `NOVO-48` | 🟠 | **2 cascos de wizard divergindo em 5 linhas**, e nenhum dos dois usa o `flow_base` criado na Etapa 6 para exatamente isso. | `diff` dos `wizard_base.html` |
| `NOVO-49` | 🟠 | **Não existe casco de página único.** 46 páginas estendem `base.html` e montam o `page-shell` à mão; 18 usam `flow_base`. As 46 repetem `<div class="page-shell page-shell--…">` e o `page_header` linha a linha. | `grep -rl 'extends "base.html"'` |
| `NOVO-50` | 🟠 | **12 páginas `confirm_delete.html` de 11–13 linhas**, idênticas exceto por 3 strings (eyebrow, rótulo, mensagem). | `cadastros/estados/` × `roteiros/` |
| `NOVO-51` | 🟠 | **390 de 1.262 includes sem `only`.** O gate "nenhum include de componente sem `only`" está declarado na tabela de gates da Etapa 6 (§6 do plano) e **nunca foi construído** — não existe em `tests.yml` nem em `scripts/`. | `grep` em `.github/workflows/tests.yml` |
| `NOVO-52` | 🟡 | **Nenhum componente declara contrato.** Zero templatetags no projeto; toda composição é `include` com kwargs soltos. `field.html` recebe 66 chamadas com conjuntos de parâmetros diferentes e nada documenta quais existem. | `find . -name templatetags` |
| `NOVO-53` | 🟡 | **`docs/PADRAO_TEMPLATES.md` descreve uma estrutura que não existe.** Ele manda usar `components/buttons/` (que não existe; é `components/ui/buttons/`) e lista `components/lists/` e `components/cards/` sem mencionar os equivalentes em `ui/`. O padrão vigente diverge do código desde antes da Etapa 6. | leitura direta |
| `NOVO-54` | 🟡 | **Nomenclatura mista.** Nomes de componente em inglês (`entity_card`, `field`), pastas de módulo em português, partials locais com prefixo `_` inconsistente (`evento_list_card.html` sem `_`, `_evento_card_body.html` com), e três convenções de sufixo para a mesma coisa (`_body`, `_fields`, `_section`). | `find templates -name '*.html'` |

---

## 4. Arquitetura alvo

### 4.1 Uma taxonomia, sem `ui/`

O nível `ui/` não separa nada: `travel/` é domínio e está fora dele, mas `forms/` e `form/`
estão dos dois lados. A regra nova é uma frase:

> **`templates/components/<família>/<componente>.html`.** Uma família, um nível. Domínio de
> viagem continua em `travel/`, que é a única família com regra de negócio dentro.

```
templates/components/
  badges/      chip · status_badge
  buttons/     button · icon_button
  cards/       document_card · module_card · summary_card
  documents/   pdf_viewer · signature_card
  feedback/    notice · field_error · empty_state · placeholder · pendencias_card
  forms/       field · select · multiselect · dropdown · date_picker · file_picker
               document_number_field · card_toggle · section_card (+ footer/actions)
  headers/     page_header · filter_page_header · wizard_page_header · section_header
  icons/       icon
  layout/      sidebar
  lists/       collection · entity_card (+header/footer/menu) · row · file_list · data_table
  menus/       rich_menu_header · rich_menu_link
  navigation/  stepper · tabs · pagination
  overlays/    dialog · dialog_header · delete_dialog · confirm_action_dialog
               cancel_reason_dialog · attach_signed_dialog
  page/        shell · confirm_delete · create_draft
  travel/      (10 arquivos de domínio, preservados)
```

**Alvo: 96 → ~58 arquivos.** Não é meta de contagem — é a consequência de aplicar §4.2. Se ao
final sobrarem 62 porque quatro fusões se provaram erradas na tela, o número certo é 62 e a
divergência entra escrita, como as outras deste repositório.

### 4.2 Uma função, um componente

Critério para decidir se dois arquivos são o mesmo componente, aplicado nesta ordem:

1. **Mesmo papel na página** (é o alerta? é o botão? é o casco?) → mesmo componente, a
   diferença vira `variant`.
2. **Mesma estrutura, dados diferentes** → mesmo componente, a diferença vira parâmetro ou
   slot de template.
3. **Estrutura diferente, papel igual** (o caso `confirm_delete` página × modal) → **dois**
   componentes, com nomes que digam a diferença (`page/confirm_delete` × `overlays/delete_dialog`).
   Fundir estes dois seria o erro simétrico.
4. **Arquivo cujo corpo é um único `include`** → alias. Alias não é componente. Apaga-se e
   corrige-se a chamada.

### 4.3 Contrato explícito

Sem templatetags, o contrato mora em duas coisas obrigatórias em todo componente:

```django
{# button.html
   params: label, variant=primary|secondary|danger|ghost, icon, href, type=button|submit,
           size=sm|md, extra_class, aria_label
   slots:  (nenhum)
   emite:  .cv-btn .cv-btn--{variant}
#}
```

e **`only` em toda chamada**. As exceções — os portadores de contexto (`section_card`,
`flow_base`) documentados em `H-04`/`H-05` — passam a ser uma **lista fechada** no gate, não um
hábito difuso. Componente com 6 ou mais parâmetros na maioria das chamadas recebe presenter
(`core/presenters/`), conforme `PADRAO_PRESENTERS.md`, e passa a receber **um dicionário**.

### 4.4 Nomenclatura

- Componente global: **inglês**, `snake_case`, substantivo do papel (`entity_card`, não `card2`).
- Sub-partial privado de um componente: prefixo `_`, mesma pasta (`_field_control.html`).
- Partial de app: `<app>/partials/_<assunto>_<slot>.html`, com `<slot>` ∈ `{body, footer, actions, fields}` — três convenções passam a uma.
- Proibido: sufixo de módulo em componente global (`oficio_*`), número de versão, "novo", "v2".

---

## 5. As fases

Cada fase é **um PR**, com o corpo do `AGENTS.md` §5. Nenhuma fase mistura com outra. A ordem
não é negociável nos três primeiros passos: a régua vem antes da obra, e a mudança mecânica de
caminho vem antes de qualquer mudança de markup — senão não se sabe qual metade quebrou
(`AGENTS.md` §8.2).

### Fase 0 — A régua (risco: zero, nenhum HTML muda)

Constrói `scripts/audit_component_library.py` e `core/tests/test_component_library.py`:

- inventário de componentes e famílias, com a taxonomia alvo declarada em código;
- **grafo de uso que resolve caminho passado por parâmetro** (§2.1), não só `{% include %}`;
- órfãos; componentes vivos só por lab/teste; aliases (corpo = um `include`);
- `include` sem `only`, contra a lista fechada de portadores de contexto;
- componentes sem cabeçalho de contrato.

Todos entram como **catraca** com o número de hoje como teto — só desce. Motivo escrito no
`AGENTS.md` §6: quando o alvo é o artefato, o gate tem de olhar o artefato; suíte verde não
prova que a biblioteca encolheu.

**Pronto quando:** o script reproduz os números da §2 e o CI falha se algum deles subir.

### Fase 1 — Taxonomia única (risco: baixo, alcance amplo)

`git mv` de `components/ui/<f>/` para `components/<f>/`, fusão das famílias duplicadas por
pasta (não por conteúdo ainda), e saída dos que não são globais:
`components/perfil/*` → `templates/core/partials/perfil/` (consumidor único),
`components/create_draft.html` → `components/page/create_draft.html` (três apps o renderizam,
é global de verdade).

**Zero mudança de markup. Zero mudança de classe.** Só caminho, em template, `.py`, `.js`, teste
e doc — o mesmo PR, como manda a regra 2 do `AGENTS.md`.

**Pronto quando:** render de todas as páginas antes/depois com diff normalizado **vazio**.
Comparação por `git worktree` no commit anterior, não por `git stash` — a lição de `H-05`.

### Fase 2 — Aliases e órfãos (risco: baixo)

Apaga os 5 órfãos, os 10 aliases (com a chamada corrigida no mesmo PR) e decide, um a um, os
9 vivos só por lab/teste: promover a uso real ou apagar **junto com a asserção que os segura**.
`main_list_card.html` (167 linhas, zero páginas) é o caso-teste desta fase.

Prova de deleção no corpo do PR pelo **caminho**, não pelo nome (§2.1).

**Pronto quando:** o auditor da Fase 0 reporta 0 órfãos e 0 aliases.

### Fase 3 — Confirmação e overlays (`NOVO-42`, risco: médio)

Um diálogo (`overlays/dialog.html`) com presets; uma página de confirmação
(`page/confirm_delete.html`) que as 12 páginas de módulo passam a **estender**, passando 3
strings. −12 arquivos, −1 alias, e o par de nomes quase iguais deixa de existir.

Risco médio porque exclusão é ação destrutiva: teste de fluxo (GET mostra, POST exclui, vínculo
bloqueia) para os 12 antes de tocar em qualquer um.

### Fase 4 — Botões (`NOVO-43`, risco: baixo)

7 → 2. `button.html` ganha `shape=pill|circle`, `placement=inline|footer|floating`;
`icon_button.html` permanece por ser um elemento com regra de acessibilidade própria
(`aria-label` obrigatório). Os 3 sem uso em produção morrem na Fase 2 e não chegam aqui.

### Fase 5 — Feedback (`NOVO-44`, risco: baixo)

`alerts` + `alert` + `form_errors` → `feedback/notice.html` (com `variant` e um modo `messages`).
`field_error`, `empty_state`, `placeholder`, `pendencias_card` permanecem — papéis distintos
pelo critério §4.2.1.

### Fase 6 — Card de formulário (`NOVO-45`, risco: médio)

`form/card.html` + `ui/forms/form_block.html` → `forms/section_card.html`, com o zeramento de
parâmetros de `H-04`/`H-05` escrito **uma vez**. 66 chamadas afetadas. Risco médio por ser o
componente mais aninhado do sistema e o que já produziu vazamento de parâmetro duas vezes.

Verificação obrigatória: render antes/depois das 21 páginas de formulário, diff normalizado, e
print nos dois temas.

### Fase 7 — Listas (`NOVO-46`, risco: médio · pode virar 2 PRs)

**7a — casco:** `list_page_cards` + `list_page_standard` + `list_page_quick_add` + `list_grid`
+ `list_filters` → `lists/collection.html` com `layout=cards|rows` e `quick_add` opcional.
As 24 páginas de índice passam a ter uma só forma.
**7b — item:** `simple_list_row` (183 linhas) + `entity_card*` → `lists/entity_card.html` +
`lists/row.html`, com o menu e o rodapé como sub-partials.

Se a medição de 7a mostrar que os três cascos divergem em mais de 4 eixos, **fatiar antes de
começar** — é o limite que o `AGENTS.md` §6 impõe: etapa que não cabe numa sessão com
verificação junto se fatia, não se entrega pela metade.

### Fase 8 — Casco de página (`NOVO-48`, `NOVO-49`, risco: médio)

`page/shell.html` com `variant=list|form|wizard|confirm|simple`, absorvendo `flow_base` e os
dois `wizard_base.html`. As 46 páginas que montam `page-shell` à mão passam a estender.

O `flow_base` da Etapa 6 documenta que as páginas variavam em **12 eixos** e que só 2 linhas
eram literalmente iguais. Este plano não contradiz aquela medição: o `shell` não força as 46 a
serem iguais, ele dá nome aos eixos (bloco e parâmetro) em vez de deixá-los implícitos em 46
cópias de `<div class="page-shell …">`.

### Fase 9 — Partials de app (`NOVO-47`, `NOVO-54`, risco: baixo)

Os 10 grupos byte-idênticos viram 1 cada (os de rodapé de wizard sobem para
`components/forms/section_card_actions.html`; os `_quick_add_fields` idênticos viram um partial
compartilhado). Convenção de nome do §4.4 aplicada aos ~200 partials de app.

Renomeação em massa: template + qualquer `*_template=` que aponte para eles + teste, no mesmo PR.

### Fase 10 — Contrato e `only` (`NOVO-51`, `NOVO-52`, risco: baixo)

Cabeçalho de contrato em todos os ~58 componentes; os 390 `include` sem `only` vão a **zero**
fora da lista fechada; presenter para os componentes de ≥6 parâmetros. O gate da Fase 0 deixa
de ser catraca e vira **erro**.

### Fase 11 — Documentação e fechamento (risco: zero)

`PADRAO_TEMPLATES.md` reescrito para descrever o que existe (`NOVO-53`); `COMPONENTES.md`,
`COMPONENTES_DOMINIO.md` e `ui-components.md` reconciliados num só catálogo; UI Lab renderizando
a biblioteca final — e passando a ser **o consumidor de referência**, não o esconderijo de
componente sem uso.

---

## 6. Gates novos no CI

| Fase | Gate acrescentado a `.github/workflows/tests.yml` |
|---|---|
| 0 | `audit_component_library.py --max-*` com todos os números de hoje como teto |
| 2 | órfãos = 0 · aliases = 0 (erro, não catraca) |
| 3 | um só componente por papel de overlay (mapa declarado no auditor) |
| 7 | um só casco de coleção; nenhuma página de índice monta lista à mão |
| 8 | nenhuma página fora de `components/` emite `class="page-shell` |
| 10 | `include` sem `only` = 0 fora da lista fechada · todo componente com cabeçalho de contrato |

A catraca existente (`audit_frontend_standards.py --max-warnings 184`) **não sobe em nenhuma
fase**. Como este plano não mexe em CSS, o esperado é que ela fique parada — se ela descer, o
PR explica por quê; se subir, o PR está errado (`AGENTS.md` §3.5).

---

## 7. O que este plano NÃO faz

Escopo deliberadamente fora, para não se infiltrar depois:

- **Não renomeia classe CSS.** Nenhuma. Quando uma fusão obrigar a escolher entre duas classes
  (o caso `cv-notice` × `alert` da Fase 5), o componente canônico **emite as duas** e a remoção
  da perdedora fica para uma fase de CSS posterior, com o dicionário de renomeação. Etapa de
  HTML e etapa de CSS não viajam no mesmo PR (`AGENTS.md` §3.1).
- **Não muda nome de campo, `id` de formulário, `name` de input ou URL.** O backend não sabe
  que esta etapa aconteceu.
- **Não toca em regra de negócio**, em `roteiros/services/diarias.py` nem em nada de dinheiro.
- **Não reescreve JS**, além de atualizar caminho de template e seletor que dependa de arquivo
  movido. Motor de JS é Etapa 5, fechada.
- **Não altera os PDFs** (`templates/documentos/pdf/`): são documentos oficiais com layout
  travado por *golden file* (`N-04`).
- **Não mexe no UI Lab** antes da Fase 11 — ele é o espelho, e espelho se ajusta por último.

---

## 8. Riscos e como cada um é contido

| Risco | Contenção |
|---|---|
| **Suíte verde não prova que a biblioteca encolheu.** É literalmente a lição escrita no `AGENTS.md` §6, paga com duas fases recusadas do Codex. | Gate da Fase 0 mede **o artefato** (contagem de arquivos, órfãos, aliases), não o comportamento. Nenhuma fase fecha só com a suíte. |
| **Apagar arquivo vivo** por causa do grafo de dependência não-sintático (§2.1). | O auditor resolve caminho por parâmetro; prova de deleção no PR é pelo caminho completo. |
| **Regressão visual que nenhum teste pega** (uma classe a mais, um recuo de 40px — os dois casos reais de `H-05` e `H-08`). | `scripts/medir_paleta.py` + render antes/depois com diff normalizado, por `git worktree`, nos dois temas. Print no corpo do PR. |
| **Fase grande demais para uma sessão** (7 e 8 são as candidatas). | Fatiar antes de começar. Meia fase entregue sem verificação é o defeito que o `AGENTS.md` §6 existe para lembrar. |
| **Escopo se infiltrando**: consertar um defeito visual visto de passagem. | Registra no catálogo com `NOVO` e segue. Correção de defeito e renomeação nunca viajam juntas. |

---

## 9. Quadro de acompanhamento

`[ ]` pendente · `[~]` em andamento · `[x]` pronto. Marcar **no mesmo PR** que faz o trabalho.

- [ ] **Fase 0** — auditor + catraca da biblioteca (`NOVO-40`, `NOVO-41`, `NOVO-51`, `NOVO-52`)
- [ ] **Fase 1** — taxonomia única (`NOVO-39`)
- [ ] **Fase 2** — órfãos e aliases apagados (`NOVO-40`, `NOVO-41`)
- [ ] **Fase 3** — overlays e confirmação (`NOVO-42`)
- [ ] **Fase 4** — botões 7 → 2 (`NOVO-43`)
- [ ] **Fase 5** — feedback 3 → 1 (`NOVO-44`)
- [ ] **Fase 6** — card de formulário 2 → 1 (`NOVO-45`)
- [ ] **Fase 7a** — casco de coleção (`NOVO-46`)
- [ ] **Fase 7b** — item e linha de lista (`NOVO-46`)
- [ ] **Fase 8** — casco de página único (`NOVO-48`, `NOVO-49`, `NOVO-50`)
- [ ] **Fase 9** — partials de app deduplicados e renomeados (`NOVO-47`, `NOVO-54`)
- [ ] **Fase 10** — contrato e `only` (`NOVO-51`, `NOVO-52`)
- [ ] **Fase 11** — documentação e UI Lab (`NOVO-53`)

---

## Anexo A — Dicionário de renomeação (antes → depois)

Obrigatório pela regra 2 do `AGENTS.md`: renomear exige o dicionário atualizado no mesmo PR.
Esta é a versão-alvo; cada fase marca as linhas que executou.

### A.1 Movidos sem fusão (Fase 1)

| Antes | Depois |
|---|---|
| `components/ui/badges/chip.html` | `components/badges/chip.html` |
| `components/ui/badges/status_badge.html` | `components/badges/status_badge.html` |
| `components/ui/buttons/button.html` | `components/buttons/button.html` |
| `components/ui/buttons/icon_button.html` | `components/buttons/icon_button.html` |
| `components/ui/feedback/field_error.html` | `components/feedback/field_error.html` |
| `components/ui/feedback/empty_state.html` | `components/feedback/empty_state.html` |
| `components/ui/feedback/pendencias_card.html` | `components/feedback/pendencias_card.html` |
| `components/feedback/module_placeholder.html` | `components/feedback/placeholder.html` |
| `components/ui/forms/field.html` | `components/forms/field.html` |
| `components/ui/forms/_field_control.html` | `components/forms/_field_control.html` |
| `components/ui/forms/select.html` · `multiselect` · `dropdown` | `components/forms/` (mesmos nomes) |
| `components/ui/forms/date_picker.html` · `_date_picker_icon` | `components/forms/` (mesmos nomes) |
| `components/ui/forms/file_picker.html` · `document_number_field` · `card_toggle` | `components/forms/` (mesmos nomes) |
| `components/ui/headers/page_header.html` · `filter_page_header` · `wizard_page_header` | `components/headers/` (mesmos nomes) |
| `components/ui/headers/_list_header_band.html` | `components/headers/_band.html` |
| `components/ui/icons/icon.html` | `components/icons/icon.html` |
| `components/layout/sidebar.html` | *(inalterado)* |
| `components/ui/lists/file_list.html` | `components/lists/file_list.html` |
| `components/ui/tables/data_table.html` | `components/lists/data_table.html` |
| `components/ui/menus/rich_menu_header.html` · `rich_menu_link` | `components/menus/` (mesmos nomes) |
| `components/ui/navigation/page_stepper.html` | `components/navigation/stepper.html` |
| `components/lists/list_tabs.html` | `components/navigation/tabs.html` |
| `components/lists/list_toggle.html` | `components/navigation/tabs_toggle.html` |
| `components/ui/lists/pagination.html` | `components/navigation/pagination.html` |
| `components/ui/modals/dialog_header.html` | `components/overlays/dialog_header.html` |
| `components/ui/modals/cancel_reason_modal.html` | `components/overlays/cancel_reason_dialog.html` |
| `components/ui/modals/attach_signed_modal.html` | `components/overlays/attach_signed_dialog.html` |
| `components/ui/modals/confirm_action_modal.html` | `components/overlays/confirm_action_dialog.html` |
| `components/ui/modals/delete_confirm_modal.html` | `components/overlays/delete_dialog.html` |
| `components/ui/modals/confirm_delete.html` | `components/page/confirm_delete.html` *(é página, não modal)* |
| `components/page/flow_base.html` | `components/page/shell.html` |
| `components/create_draft.html` | `components/page/create_draft.html` |
| `components/partials/_create_draft_body.html` | `components/page/_create_draft_body.html` |
| `components/cards/*` · `components/documents/*` · `components/travel/*` | *(inalterados)* |
| `components/perfil/**` (8 arquivos) | `templates/core/partials/perfil/**` *(deixa de ser global)* |

### A.2 Fundidos (Fases 3–7)

| Antes | Depois | Fase |
|---|---|:--:|
| `feedback/confirm_delete_block.html` *(alias)* | apagado → `page/confirm_delete.html` | 3 |
| 12 × `<app>/confirm_delete.html` | estendem `page/confirm_delete.html` | 3 |
| `buttons/field_action_button` · `field_manage_button` · `floating_action` · `floating_primary_action` · `footer_action` | `buttons/button.html` (`shape`/`placement`) | 4 |
| `feedback/alerts.html` · `ui/feedback/alert.html` · `ui/feedback/form_errors.html` | `feedback/notice.html` | 5 |
| `form/card.html` · `ui/forms/form_block.html` | `forms/section_card.html` | 6 |
| `ui/layouts/card_footer_section.html` | `forms/section_card_footer.html` | 6 |
| `ui/layouts/card_footer_actions.html` | `forms/section_card_actions.html` | 6 |
| `ui/layouts/collection_header.html` | `headers/section_header.html` | 6 |
| `lists/list_page_cards` · `list_page_standard` · `list_page_quick_add` · `list_grid` · `list_filters` | `lists/collection.html` | 7a |
| `lists/list_empty.html` *(alias)* | apagado → `feedback/empty_state.html` | 7a |
| `lists/simple_list.html` · `simple_list_row.html` | `lists/row.html` (+ `lists/collection.html`) | 7b |
| `ui/lists/entity_card*` (4) | `lists/entity_card.html` + 3 sub-partials `_` | 7b |
| 7 × `<app>/partials/*_list_card.html` *(aliases)* | apagados; a página passa `body_template` | 7b |
| `oficios/wizard_base.html` · `planos_trabalho/wizard_base.html` | `page/shell.html` `variant=wizard` | 8 |

### A.3 Apagados sem substituto (Fase 2)

| Arquivo | Motivo |
|---|---|
| `components/ui/filters/search_input.html` | zero referências no repositório |
| `components/ui/filters/advanced_filters.html` | zero referências |
| `components/ui/lists/list_card_actions.html` | zero referências |
| `components/perfil/gdrive_card.html` | zero referências (o consumidor inclui o `_body` direto) |
| `components/perfil/partials/_gdrive_card_header_meta.html` | zero referências |
| `components/lists/main_list_card.html` | 167 linhas, nenhuma página; vivo só por `test_dark_redesign.py:611` — apagar junto com a asserção |
| `components/documents/partials/_signature_card_*.html` | avaliar na Fase 2: vivos só por lab/teste |

> Os 9 "vivos só por lab/teste" (`data_table`, `collection_header`, `form_errors`,
> `field_action_button`, `footer_action`, `floating_primary_action`, `dropdown`, `list_grid`,
> `main_list_card`) recebem decisão **individual e escrita** na Fase 2. Promover a uso real e
> apagar são as duas respostas aceitáveis; "deixar como está porque o lab usa" não é.
