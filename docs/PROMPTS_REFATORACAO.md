# Prompts prontos — refactor guiado pelas auditorias

Copie, cole, ajuste o ID. Cada prompt já traz as cinco partes obrigatórias
(etapa, fonte, escopo fechado, gate, entrega) descritas em
[`PLANO_REFATORACAO_EXECUCAO.md`](PLANO_REFATORACAO_EXECUCAO.md) §5.1.

**Regra que vale para todos:** nunca cole "leia as auditorias e conserte o que achar".
Isso produz escopo inventado, PR gigante e nenhuma rastreabilidade.

---

## Esqueleto

```
Etapa <N> do docs/PLANO_REFATORACAO_EXECUCAO.md — defeito(s) <IDs>.

FONTE: leia SOMENTE <arquivo>#<seção>. Não leia as outras auditorias.

TAREFA: <uma frase imperativa>

ESCOPO FECHADO:
- altere apenas <caminhos>
- NÃO renomeie classe, hook, template ou rota
- NÃO toque em <o que está reservado para outra etapa>

GATE (pronto = todos verdes):
- python manage.py test --settings=config.settings.test
- python scripts/audit_frontend_standards.py --max-warnings <N atual>
- <verificação específica do defeito>

ENTREGA: PR com o corpo do AGENTS.md §5, linha marcada em
docs/PLANO_REFATORACAO_EXECUCAO.md §7, commits citando o ID.
```

---

## Etapa 1 — Correções críticas isoladas

### 1.a Codex — componentes globais sem CSS (`D-01`, `D-02`, `D-03`, `D-04`)

```
Etapa 1 — defeitos D-01, D-02, D-03, D-04.

FONTE: docs/AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md §4.1 (só a tabela 4.1).

TAREFA: escrever o CSS que falta para os quatro componentes globais listados, usando
exclusivamente tokens já definidos em static/css/tokens.css e no tema escuro.

ESCOPO FECHADO:
- altere apenas static/css/components/ e static/css/tokens.css
- NÃO renomeie nenhuma classe (a renomeação é a Etapa 7)
- NÃO invente valor: se o token necessário não existir, defina-o em tokens.css e diga por quê

GATE:
- suíte verde
- audit_frontend_standards não aumenta o número de avisos
- para cada defeito, um print da tela em tema escuro antes/depois no PR:
  D-01 toast de download · D-02 os 4 modais lado a lado · D-03 Dashboard "Viagens próximas"
  · D-04 botões PDF/DOCX do document_card

ENTREGA: PR com o corpo do AGENTS.md §5.
```

### 1.b Cursor — contraste reprovado (`N-03`, `D-20`, `D-21`, `D-22`)

```
Etapa 1 — defeitos N-03, D-20, D-21, D-22.

FONTE: docs/AUDITORIA_FINAL_CORRECAO_E_CUSTO.md §6.2 (tabela de contraste medido) e
docs/AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md §4.2.

TAREFA: corrigir os pares de cor que reprovam WCAG AA, começando pelos 3 abaixo de 2,3:1.

ESCOPO FECHADO:
- static/css/planos-trabalho-eventos.css e static/css/forms.css (bloco .app-card-toggle)
- substituir literais Tailwind (#0f172a, #64748b, #2563eb, #f8fafc, #e2e8f0) por tokens
- NÃO mexa em estrutura de template

GATE:
- cada par corrigido tem contraste medido ≥ 4,5:1 (texto) / 3:1 (UI), com o número no PR
- as telas Plano de Trabalho (cards de evento) e qualquer form com card_toggle conferidas
  nos dois temas, com print

ENTREGA: PR com o corpo do AGENTS.md §5.
```

### 1.c Claude Code — paginação (`N-02`, `N-07`)

```
Etapa 1 — defeitos N-02 e N-07.

FONTE: docs/AUDITORIA_FINAL_CORRECAO_E_CUSTO.md §4 (desempenho medido) e §9.

TAREFA: paginar a lista de Ofícios (oficios/views.py:460) e de Ordens de Serviço, e fazer o
componente de paginação de list_page_cards.html falhar visivelmente (ou não renderizar)
quando page_obj não vier no contexto.

ESCOPO FECHADO:
- views e templates de listagem de oficios e ordens_servico + components/.../paginacao
- preserve os filtros e o isolamento por área existentes (filter_queryset_by_area)
- NÃO altere o motor de filtro JS (é a Etapa 5, J-03)

GATE:
- teste novo: lista com 300 registros responde com N itens por página e contagem de queries
  constante (a auditoria mediu 16 queries fixas — não regrida isso)
- suíte verde
- tamanho do HTML da lista medido antes/depois, no PR

ENTREGA: PR com o corpo do AGENTS.md §5.
```

### 1.d Codex — chave Fernet (`S-01`)

```
Etapa 1 — defeito S-01.

FONTE: docs/AUDITORIA_BACKEND_INFRA_COMPLETA.md §4.2.

TAREFA: remover a chave Fernet literal de config/settings/dev.py, passar a exigi-la via
variável de ambiente e documentar a geração em .env.example e docs/AMBIENTES.md.

ESCOPO FECHADO:
- config/settings/, .env.example, docs/AMBIENTES.md
- NÃO altere lógica de criptografia de campo
- se algum dado real foi cifrado com a chave commitada, PARE e reporte: rotação exige
  re-cifragem, que é decisão do humano

GATE:
- python manage.py check --settings=config.settings.dev falha com mensagem clara sem a var
- suíte verde
- grep confirma zero chave literal no repositório

ENTREGA: PR com o corpo do AGENTS.md §5.
```

---

## Etapa 2 — Rede de segurança (Claude Code)

```
Etapa 2 — defeitos T-01 e N-04. Use plan mode antes de escrever.

FONTE: docs/AUDITORIA_BACKEND_INFRA_COMPLETA.md §5 e
docs/AUDITORIA_FINAL_CORRECAO_E_CUSTO.md §7.

TAREFA: escrever a suíte que falta em Prestações de Contas (razão teste/código hoje: 0,04
— 351 linhas para 8.238) cobrindo o fluxo feliz das 5 etapas + o fluxo de assinatura
pública, e criar golden files para os 11 documentos gerados, verificando o CONTEÚDO do
arquivo produzido (não só o status 200).

ESCOPO FECHADO:
- prestacoes_contas/tests/, documentos/tests/, .github/workflows/tests.yml
- NÃO altere código de produção. Se um teste revelar um defeito, registre-o como linha
  NOVO no catálogo da auditoria e siga — a correção é outro PR.

GATE:
- suíte verde, com o número de testes antes/depois no PR
- coverage adicionado ao CI com piso por app; prestacoes_contas com piso declarado
- cada golden file tem um comentário dizendo o que garante

ENTREGA: PR com o corpo do AGENTS.md §5 e as linhas da Etapa 2 marcadas no plano.
```

---

## Etapa 3 — Diárias (Claude Code, plan mode obrigatório)

```
Etapa 3 — defeitos N-01, N-05, N-06, N-08, N-09, N-10. Plan mode ANTES de escrever.

FONTE: docs/AUDITORIA_FINAL_CORRECAO_E_CUSTO.md §3 inteira (o motor de diárias).

TAREFA, em três PRs separados e nesta ordem:
  PR1 — testes de caracterização: provar, com teste, o comportamento ATUAL de
        roteiros/services/diarias.py, incluindo as bordas N-08, N-09 e N-10. Zero mudança
        de comportamento neste PR.
  PR2 — tabela de diárias com vigência (data de início/fim) + congelamento do valor no
        roteiro/documento no momento da emissão. Histórico não pode ser recalculado.
  PR3 — unificar as duas regras de complemento (N-05) e trocar CAPITAIS_POR_UF pela base
        geográfica IBGE já existente (N-06).

ESCOPO FECHADO:
- roteiros/services/, roteiros/models.py (+ migração), roteiros/tests/
- NÃO altere template nem CSS
- toda migração vem com query de validação dos dados existentes no corpo do PR

GATE:
- PR1: suíte verde, cobertura de diarias.py declarada no PR
- PR2: teste que prova que mudar a tabela NÃO altera documento já emitido
- PR3: teste que prova que as duas regras antigas convergem para a nova, com os valores
- docs/REGRAS_DE_NEGOCIO.md atualizado no PR3 (N-13)

ENTREGA: 3 PRs, cada um com o corpo do AGENTS.md §5.

PARE E PERGUNTE se: a vigência exigir decisão sobre qual tabela vale hoje, ou se as duas
regras de complemento divergirem em valor para algum caso real.
```

---

## Etapa 4 — Backend (Claude Code + Codex)

### 4.a Claude Code — selectors (`P-01`)

```
Etapa 4 — defeito P-01.

FONTE: docs/AUDITORIA_BACKEND_INFRA_COMPLETA.md §3.1 + docs/PADRAO_SELECTORS.md.

TAREFA: criar a camada de selectors nos 4 apps com mais ORM em view (eventos 17×, termos 7×,
ordens_servico 7×, planos_trabalho 5×), seguindo o padrão já praticado em roteiros e oficios.

ESCOPO FECHADO:
- <app>/selectors.py e as views que passam a consumi-los
- preserve o isolamento por área (filter_queryset_by_area) em cada query movida
- NÃO otimize query nesta passada: mover, não mudar. A auditoria mediu ZERO N+1 — regredir
  isso reprova o PR.

GATE:
- suíte verde
- contagem de queries das listas afetadas idêntica antes/depois (cole os números)
- gate de CI novo: falha se houver .objects. dentro de views.py

ENTREGA: um PR por app.
```

### 4.b Codex — widget base (`P-04`, pré-requisito das Etapas 6 e 7)

```
Etapa 4 — defeito P-04. Este PR desbloqueia as Etapas 6 e 7.

FONTE: docs/AUDITORIA_BACKEND_INFRA_COMPLETA.md §3.4.

TAREFA: extrair os 194 attrs={...} com classe CSS espalhados pelos forms.py para uma camada
de widgets base em core/, de modo que a classe CSS de um campo passe a ter UM lugar de
definição — hoje o Python está acoplado ao nome da classe e trava a reconstrução do CSS.

ESCOPO FECHADO:
- core/forms/widgets.py (novo) + os forms.py de cada app
- as classes emitidas devem ser EXATAMENTE as de hoje: este PR não renomeia nada,
  só centraliza. A renomeação é a Etapa 7.

GATE:
- suíte verde
- diff do HTML renderizado de 5 formulários representativos é vazio (prove no PR)
- grep: zero 'class' dentro de attrs={} nos forms.py

ENTREGA: PR com o corpo do AGENTS.md §5.
```

---

## Etapa 5 — Motores JS

### 5.a Codex — limpeza (`J-06`, fase 0)

```
Etapa 5, fase 0 — defeito J-06.

FONTE: docs/AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md Anexo A (tabela de arquivos órfãos).

TAREFA: apagar os 8 arquivos JS órfãos listados (989 linhas) e os ~15 hooks data-* sem dono.

ESCOPO FECHADO:
- static/js/ e os templates que emitem os hooks mortos
- para CADA arquivo apagado, cole no PR o grep provando zero referência em
  templates/, static/, e nos .py

GATE:
- suíte verde
- servidor sobe sem erro de console em: Ofícios (lista e wizard), Prestações (5 etapas),
  Roteiros (editor), Eventos, Plano de Trabalho

ENTREGA: PR com o corpo do AGENTS.md §5 e a prova de grep por arquivo.
```

### 5.b Claude Code — ciclo de vida (`J-01`, `J-02`, `J-04`)

```
Etapa 5, fases 3–5 — defeitos J-02, J-01, J-04. Use plan mode.

FONTE: docs/AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md §4.1, §4.2 e §11 (contrato data-*).

TAREFA: adicionar CV.registry.destroy(root), chamá-lo antes de replaceWith em
live-search-submit, fazer o action-menu devolver o menu ao dono no destroy, e registrar como
enhancer os 8 componentes que hoje morrem em troca de DOM (fields-init, masks, state-toggle,
card-toggle, cv-select, document-number-field, destination-section, autosave).

ESCOPO FECHADO:
- static/js/core/ e os 8 componentes citados
- NÃO unifique os motores de filtro nesta passada (J-03 é o PR seguinte)
- NÃO renomeie hook (a renomeação é a fase 21)

GATE:
- roteiro manual no PR: filtrar uma lista em card e provar que Quick Add, autosave e menu de
  ações continuam funcionando depois do AJAX
- zero id duplicado no DOM após 3 filtragens consecutivas
- suíte verde

ENTREGA: PR com o corpo do AGENTS.md §5.
```

### 5.c Codex — migrações mecânicas (`J-07`, `J-16`, `J-12`)

```
Etapa 5, fases 7–9 — defeitos J-07, J-16, J-12.

FONTE: docs/AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md §4 (catálogo J) e §10 (motores propostos).

TAREFA, um PR por item:
  1. migrar os 13 arquivos com fetch() cru para CV.http e apagar as 11 cópias de CSRF
  2. criar CV.util (debounce, escapeHtml, normalize) e remover as 17 cópias
  3. criar CV.feedback e substituir os 13 alert()/confirm()

ESCOPO FECHADO: static/js/ apenas.

GATE por PR:
- grep prova zero ocorrência do padrão antigo fora do núcleo
- suíte verde
- gate de CI novo proibindo o padrão antigo

ENTREGA: 3 PRs.
```

---

## Etapa 6 — HTML (Claude Code, conferido no Cursor)

```
Etapa 6 — defeitos H-02 e H-05.

FONTE: docs/AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md §3 e Anexo B (templates duplicados).
PRÉ-REQUISITO: Etapa 4.b (P-04) mergeada.

TAREFA: criar components/page/flow_base.html e migrar Prestações (5 telas), Termos, OS,
Eventos-detalhe e Roteiro-avulso; criar components/form/card.html (card mestre com header) e
migrar as 20+ páginas que hoje repetem o header à mão.

ESCOPO FECHADO:
- templates/ apenas
- as classes CSS emitidas continuam AS MESMAS de hoje; este PR muda estrutura, não nome
- todo include novo usa `only`

GATE:
- suíte verde
- cada página migrada conferida no navegador nos dois temas (Cursor faz esta conferência),
  com print antes/depois
- contagem de linhas de template antes/depois no PR

ENTREGA: um PR por família de página (Prestações, Termos, OS, Eventos, Roteiros).
```

---

## Etapa 7 — CSS

### 7.a Codex — fases 0 a 2 (risco zero, −3.000 linhas)

```
Etapa 7, fases 0–2.

FONTE: docs/AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md §10 (fases 0, 1 e 2) e Anexo C
(destino de cada arquivo).

TAREFA:
  fase 0 — apagar os 4 aliases mortos de tema (dark-dark, light-dark, dark-light, light-light)
  fase 1 — apagar o CSS morto listado no Anexo C com ❌ (app-page.css, buttons.css,
           buttons-functional.css, roteiros-list.css, app-ui.css, style.css, filter-header.css,
           documents.css, eventos-list.css) e os blocos .app-form-shell/.form-shell
  fase 2 — corrigir os 18 tokens indefinidos (D-01, D-03, D-06, D-20, D-21)

ESCOPO FECHADO:
- static/css/ apenas
- prova de grep por arquivo apagado, no PR
- NÃO renomeie classe (fase 7 é outro PR)

GATE:
- audit_frontend_standards com --max-warnings REDUZIDO (declare o número novo)
- as 76 páginas de produção abrem sem regressão visual — conferir as 10 mais usadas com print
- suíte verde

ENTREGA: 3 PRs, um por fase.
```

### 7.b Cursor — fase 7, o maior vazamento de nome

```
Etapa 7, fase 7 — renomeação de oficio-lc.

FONTE: docs/AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md §7 (dicionário de renomeação) e §6
(entity_card emite classes oficio-lc, usado por 6 módulos).

TAREFA: renomear oficio-lc → cv-record-card e extrair cv-fact-block, cv-person-row,
cv-itinerary, atualizando NO MESMO PR: templates, os 7 arquivos CSS que estilizam oficio-lc,
o JS que usa os seletores, e o dicionário de renomeação da auditoria.

ESCOPO FECHADO:
- um módulo por vez (comece por Ofícios, depois Roteiros, OS, PT, Eventos, Prestações)
- NÃO mude aparência nesta passada: o diff visual deve ser ZERO

GATE:
- grep: zero ocorrência de oficio-lc fora do dicionário histórico
- print antes/depois de cada módulo nos dois temas — devem ser idênticos
- suíte verde

ENTREGA: um PR por módulo.
```

---

## Etapa 8 — Higiene (Codex)

```
Etapa 8 — defeitos G-01, G-02, N-12, R-02, N-11.

FONTE: docs/AUDITORIA_BACKEND_INFRA_COMPLETA.md §8 e
docs/AUDITORIA_FINAL_CORRECAO_E_CUSTO.md §8.

TAREFA:
- .gitignore + remover do índice os 161 arquivos indevidos (screenshots, tmp, logs, backups,
  _tmp_check*.py, tatus)
- mover os 20+ docs datados para docs/historico/, mantendo os duráveis na raiz de docs/
- padronizar o microcopy: uma única forma de "Voltar à lista" (hoje são 4, uma com erro de
  crase) e um único padrão de capitalização

ESCOPO FECHADO:
- NÃO apague nada de docs/: mover, com os links internos atualizados
- NÃO mexa em media/ ou em backups fora do repositório: isso é operação, não código

GATE:
- git status limpo; git ls-files não lista mais nenhum dos 161
- todos os links relativos entre docs continuam resolvendo (verifique)
- suíte verde

ENTREGA: 3 PRs (git, docs, microcopy).
```

---

## Anti-prompts — o que não pedir

| Não peça | Por quê | Peça em vez disso |
|---|---|---|
| "Leia as auditorias e comece o refactor" | 2.700 linhas de contexto, escopo inventado, PR de 200 arquivos | O prompt da etapa, com IDs |
| "Deixe o CSS bonito" | Não há critério de pronto | "Defina o CSS de D-02 usando tokens; prove com print nos dois temas" |
| "Refatore Prestações" | Módulo com dinheiro e cobertura 0,04 | Etapa 2 primeiro; depois o refactor com a suíte de rede |
| "Renomeie tudo para o padrão novo" | Renomeação parcial quebra silenciosamente | Um módulo por PR, com diff visual zero |
| "Aumente o --max-warnings para o CI passar" | Desliga a catraca | Reduza a dívida até o número atual passar |
| "Otimize as queries" | A auditoria mediu zero N+1; risco de regredir | Só se houver medição mostrando o contrário |
