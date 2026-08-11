# Catálogo de defeitos — ciclo de agosto/2026

**Medido em 05/08/2026.** Este é o catálogo vigente: todo trabalho começa citando um ID daqui.
O ciclo anterior está congelado em `historico/2026-07-refactor/`; os IDs de lá (`D-`, `H-`, `J-`,
`P-`, `S-`, `T-`, `N-`, `NOVO-`) descrevem o código de julho e **não são mais unidade de
trabalho**.

**Ordem de execução:** [`PLANO_MESTRE_REFATORACAO.md`](PLANO_MESTRE_REFATORACAO.md)

## Como ler

| Prefixo | Domínio | Plano |
|---|---|---|
| `BE` | Arquitetura backend: camadas, duplicação, autorização, observabilidade | [`PLANO_BACKEND.md`](PLANO_BACKEND.md) |
| `DB` | Modelo de dados, migrações, constraints, índices, isolamento no nível do dado | [`PLANO_BACKEND.md`](PLANO_BACKEND.md) |
| `UI` | CSS, tokens, tema | [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md) |
| `HT` | Templates, componentes, semântica, acessibilidade | [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md) |
| `JS` | JavaScript | [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md) |
| `PF` | Desempenho de entrega | [`PLANO_DESEMPENHO.md`](PLANO_DESEMPENHO.md) |
| `QA` | Testes, CI, segurança, infraestrutura | [`PLANO_MESTRE_REFATORACAO.md`](PLANO_MESTRE_REFATORACAO.md) |

Severidade: 🔴 crítica · 🟠 alta · 🟡 média · ⚪ baixa.
Origem: `AUD` = auditoria desta sessão · `MED` = medição direta no fio principal · `VER` =
enunciado corrigido pela passada de verificação · `NOVO` = acrescentado depois da abertura do
catálogo · `MOR` = código morto achado por varredura · `COR` = correção de rumo.

> **Cinco números de `NOVO` estão duplicados, e ficam assim de propósito.** `NOVO-27`, `NOVO-45`,
> `NOVO-49`, `NOVO-50` e `NOVO-51` titulam duas entradas diferentes cada, por acidente de sessões
> paralelas. Renumerar quebraria o rastro dos PRs que já os citam, então a colisão fica registrada
> aqui e quem for citar um deles **diz também o domínio** (`NOVO-50/MED` é a paleta; `NOVO-50/PF`,
> o `Nested Loop`).
>
> **A regra que decide entre renumerar e conviver:** o número já foi citado em PR mesclado? Se sim,
> conviva e desambigue pelo domínio. Se não, renumere — foi o que se fez com o levantamento de
> 09/08, que nasceu em `NOVO-66`…`73` e virou `NOVO-69`…`76` quando os PRs #283 e #284 chegaram
> primeiro à `main`.
>
> **E a causa, que continua aberta:** a numeração é descoberta lendo o maior `NOVO` do arquivo.
> Duas sessões que começam juntas leem o mesmo número e reservam o mesmo ID. Cinco colisões em um
> ciclo não é azar, é o método. Quem for fechar isso, feche com um comando que reserva
> (`scripts/`), não com disciplina.

## A passada de verificação de 05/08

Depois de escrito, o catálogo passou por uma rodada adversarial: um cético independente por
prefixo, com a tarefa de **derrubar** cada enunciado no código real — não de conferi-lo. Onde o
achado envolvia número, o cético reproduziu a medição; onde envolvia comportamento, escreveu teste
temporário ou reproduziu no navegador.

Ela se pagou. O saldo, além de vários números ajustados:

- **Um enunciado invertido.** O `DB-01` pedia acrescentar `area` à tabela de diárias. O código
  documenta o oposto como decisão deliberada. A correção proposta reintroduziria a inconsistência
  que o desenho evita — e o defeito real era outro (falta de portão de papel na tela de edição).
- **Um enunciado refutado.** O `JS-12` dizia que dois nomes apontavam para o mesmo objeto; em
  runtime, `===` devolve `false`. O defeito existe com outra causa.
- **Um mecanismo de ataque que não se sustenta.** O `BE-08` alegava vazamento de token por
  `Referer`. O `Referer` reflete a URL da página que fez o POST, não a flash message.
- **Uma alegação de método que estava errada.** O `UI-01` afirmava existir um único padrão de
  classe CSS dinâmica no JS. São pelo menos três — a varredura não cobria concatenação com `+`.
  Isso muda o gate de todo PR de poda de CSS.
- **Um "sem retry" que o código contradiz.** O `BE-15` dizia que a numeração de OS não tinha
  retry; tem, e o cético provou em PostgreSQL forçando colisão.
- **Duas contagens que estavam pequenas demais**, não grandes: o `BE-08` tem 8 sites e não 6, e o
  `BE-16` tem 1 uso de `excluir_com_protecao` e não 3.
- **Erro meu, de método:** os totais de linha somavam os bundles gerados às fontes que os compõem.
  CSS é 43.038 e não 60.707; JS é 17.859 e não 25.492.

Nenhum dos 93 IDs se revelou fabricado ou sem lastro no código. As correções estão registradas
**dentro de cada ID**, em citação destacada, em vez de reescritas em silêncio — pelo mesmo motivo
que as auditorias de julho foram arquivadas sem edição: registro de rumo tem valor, e um catálogo
que apaga os próprios erros ensina a confiar demais nele.

---

## BE — Arquitetura backend

### BE-01 ✅ RESOLVIDO · 🔴 "Finalizar plano" não finaliza e "Voltar" avança · AUD · 0,5 d · risco baixo

`planos_trabalho/view_helpers.py:22` lê apenas `post.get("action")` e cai no default
`"wizard_next"`. Os botões do wizard vêm de `_documentos_preview_footer.html` →
`components/ui/layouts/card_footer_section.html` → `card_footer_actions.html:18`, que emite
`name="wizard_action"`. Não existe **nenhum** `name="action"` nos templates do app
(`grep -rn 'name="action"' templates/planos_trabalho/` → 0).

`oficios/view_helpers.py:25` lê `wizard_action` primeiro, com comentário explicando que
`name="action"` colide com `form.action` no DOM. As duas cópias divergiram.

> **Atenção, e conferido em 05/08 depois do merge do PR #182.** Aquele PR
> (`fix(planos-trabalho): destrava as etapas 1 e 2 do wizard`, `NOVO-58..61`) mexeu **no mesmo
> wizard** e corrigiu quatro defeitos vizinhos — contextualização, *date picker* das diárias, linha
> em branco do efetivo e validação. **Não fechou este.** Verificado contra a `main` de agora:
> `planos_trabalho/view_helpers.py:21` continua lendo só `post.get("action")`, e os templates do
> app seguem com zero `name="action"`. O `BE-01` permanece aberto — não presuma cobertura por
> proximidade.

**Efeito:** o plano não finaliza (o clique recarrega a mesma página, sem mensagem), e cada
"Voltar" empurra o usuário para a etapa seguinte. Quatro telas afetadas.
**Correção:** mover o helper para `core/wizard.py` com a implementação de ofícios e trocar os
imports em `identification_views.py`, `per_diem_views.py`, `activity_views.py`,
`document_views.py`. Teste de caracterização antes.

### BE-02 ✅ RESOLVIDO (504d6bd7) · 🔴 Exclusão de anexo de prestação por `GET`, sem CSRF · AUD · 0,5 d · risco baixo

`prestacoes_contas/document_views.py:341` — `prestacao_documento_excluir` não tem decorator
nenhum. `require_POST` está **importado na linha 9 e nunca aplicado** neste arquivo. O corpo faz
`anexo.arquivo.delete(save=False)` e `anexo.delete()` incondicionalmente (linhas 349-351).
Rota: `prestacoes_contas/urls.py:58`. Medido: `GET` devolve 200 e o anexo some.

**Efeito:** qualquer `GET` autenticado apaga o anexo e o arquivo do storage — prefetch do
navegador, `<img src>` em página de terceiro, crawler interno, link colado em chat. Não há
lixeira.
**Correção:** `@require_POST`; garantir que o JS chame por POST; auditar template que monte a URL
como `<a href>`. Regressão: `GET` deve devolver 405 e o anexo continuar existindo.

### BE-03 ✅ RESOLVIDO · 🟠 Filtro "criado de/até" da lista de ofícios é descartado em silêncio · AUD · 0,5 d

`oficios/selectors.py:103-112` usa `data_criacao__date__gte`/`__date__lte`, mas
`Oficio.data_criacao` é `DateField` (`oficios/models.py:49`). Medido:
`Oficio.objects.filter(data_criacao__date__gte='2020-01-01')` levanta
`FieldError: Unsupported lookup 'date__gte' for DateField`, e `listar_oficios(criacao_de=...)`
devolve a lista inteira. **Dois** blocos `try/except Exception: pass` engolem o erro — linhas 106
e 111.

> **Escopo corrigido pela verificação (05/08):** o enunciado original falava em quatro blocos. São
> dois. Um terceiro (`:127`) segue o mesmo antipadrão no filtro de viagem, mas opera sobre
> `DateTimeField` e **não** dispara este erro; o quarto (`:306`) está em outra função e não tem
> relação com o defeito. Os dois extras continuam valendo como higiene, não como este ID.

**Efeito:** o usuário preenche o intervalo, o sistema devolve a lista inteira e nada indica que o
filtro foi descartado.
**Correção:** `data_criacao__gte`/`__lte`; remover os quatro `except` mudos — validar formato é
papel do form. Teste que filtra por intervalo e exige contagem.

### BE-04 ✅ RESOLVIDO · 🔴 Formulário de evento oferece documentos de outras áreas · AUD · 0,5 d

`eventos/forms.py:258` filtra ofícios com `filter_queryset_by_area(Oficio.objects)` — correto. Nas
16 linhas seguintes, `:264` `OrdemServico.objects`, `:267` `PlanoTrabalho.objects`, `:270`
`TermoAutorizacao.objects` e `:275` `Roteiro.objects` vêm crus, e os quatro modelos têm campo
`area`. Teste com duas áreas: `oficios_vinculados` não vazou; os outros quatro vazaram.

**Efeito:** número, destino e datas de documentos de outra unidade aparecem no picker. Selecionar
um deles faz `core/tenancy.validate_cross_area_foreign_keys` levantar `ValidationError` dentro de
`pre_save` — que estoura como **500**, não como erro de formulário.
**Correção:** envolver os quatro em `filter_queryset_by_area`. Teste de duas áreas cobrindo os
cinco campos.

### BE-05 ✅ RESOLVIDO · 🟠 Seletor de modelo de motivo da OS expõe outras áreas · AUD · 0,25 d

`ordens_servico/forms.py:252` — `ModeloMotivoOficio.objects.filter(ativo=True)` sem recorte, e o
modelo tem `area`. Teste com A1/A2: o queryset devolveu os dois.
**Efeito:** o texto padrão de motivo de outra unidade entra literalmente no documento gerado.

### BE-06 ✅ RESOLVIDO · 🟠 Relatório técnico sai com a cidade-sede de outra área · AUD · 0,25 d

`prestacoes_contas/services.py:117-124` — `_sede()` faz `ConfiguracaoSistema.objects.first()`. É o
único ponto de produção que lê `ConfiguracaoSistema` sem área; todo o resto resolve por área
(`cadastros/models.py:536,574`).
**Efeito:** área recém-criada, que ainda não configurou nada, emite documento oficial com o
município de outra.

### BE-07 ✅ RESOLVIDO · 🟠 Exclusão de anexo dá 500 e deixa registro órfão · AUD · 0,5 d

`core/audit.py:146` faz `str(instance)[:255]` em `capture_before_delete`.
`prestacoes_contas/models.py:307` — `__str__` devolve `self.nome_original or self.arquivo.name`, e
`document_views.py:349-351` apaga o arquivo **antes** de `anexo.delete()`, zerando `FieldFile.name`.
Com `nome_original` vazio (`blank=True, default=""`), `__str__` devolve `None`.
**Efeito:** 500 na exclusão; o arquivo some do disco e a linha fica na tabela.
**Correção:** `str(instance or "")` com fallback `f"{label}#{pk}"`; inverter a ordem no view.

### BE-08 ✅ RESOLVIDO (5115d04d) · 🟠 Oito redirects seguem o que o POST mandar · AUD+VER · 0,5 d

`core/retorno.py` existe para isso e documenta o risco de open redirect no próprio docstring
(linhas 22-28), validando com `url_has_allowed_host_and_scheme`. Não é usado em
`prestacoes_contas` (zero imports). Sites crus: `views.py:383-384`,
`signature_views.py:108,115,120` (`assinatura_rt_gerar`), `:128,140,145`
(`assinatura_db_gerar`), `:150,155` (`assinatura_rt_cancelar`) e `:160,170`
(`assinatura_db_cancelar`). O helper `_redirect_lista` é reusado por 4 views.

> **Corrigido pela verificação (05/08), em dois pontos.** O escopo era **maior**: são 8 sites, não
> 6 — as duas views de cancelamento não estavam catalogadas. Mas o mecanismo de ataque estava
> **errado**: a alegação de que o redirect externo "vaza o token de assinatura pelo `Referer`" não
> se sustenta. O `Referer` enviado ao domínio externo reflete a URL da página que fez o POST, não
> o conteúdo da flash message — que vive em sessão e só é renderizada em página do próprio app. O
> link com token nunca trafega para fora por esse canal.

**Efeito real:** open redirect / *confused deputy* — formulário forjado leva o usuário autenticado
para fora do domínio logo depois de uma ação que gera ou cancela link de assinatura.

### BE-09 ✅ RESOLVIDO · 🔴 Isolamento por área depende de o programador lembrar · AUD · 6 d · risco alto

`core/tenancy.py:57` — `filter_queryset_by_area(queryset, area=None)` é função livre. Nenhum dos
54 modelos declara manager próprio (`default_manager=Manager` em todos). Varredura excluindo
migrations/tests/commands/scripts/admin: **123 ocorrências de `.objects.`** em modelos com campo
`area` fora do filtro, em código de caminho de request.
**Efeito:** o modelo de segurança multi-tenant é convenção, não garantia. `BE-04`, `BE-05`,
`BE-10` e `DB-03` são a prova de que a convenção falha.
**Correção:** `AreaScopedManager` como `objects` nos 28 modelos com `area`, com
`all_objects = models.Manager()` para migração, comando e backfill. App por app, começando por
ofícios, roteiros e prestações.

**Fechado em 06/08/2026, em seis fatias** (#205, #210, #212, #213, #218, #220 e a fatia 6). Os 28
modelos com `area` declaram `objects = AreaScopedManager()` e `all_objects = models.Manager()`, com
`Meta.default_manager_name = "all_objects"`. Catraca em **zero**, travada por
`scripts/audit_area_scoped_managers.py` no CI e por teste de introspecção
(`planos_trabalho/tests/test_recorte_por_area_fatia6.py::OIdEstaFechadoTests`).

Duas decisões fixaram o desenho, e as duas estão documentadas em `core/managers.py`:

1. **Fora de request, `objects` não recorta.** A alternativa faria toda tarefa Celery virar no-op
   silencioso — e `CELERY_TASK_ALWAYS_EAGER` esconderia isso da suíte (`NOVO-20`).
2. **`_default_manager` fica no manager irrestrito.** Admin, `dumpdata`, relações reversas,
   `validate_unique`, o guarda m2m de `core/tenancy.py:116` e o check `core.E001` continuam
   idênticos. O preço é o `NOVO-21`, deliberadamente aberto.

**35 consultas** precisaram de `all_objects`, todas da mesma forma — o escopo é o do próprio
registro, já explícito no filtro — e todas com comentário obrigatório, que a catraca verifica.
Cinco delas fechavam defeito de verdade: as três de `Roteiro` do `NOVO-30`, mais o termo genérico do
evento e o `Prefetch` de servidores, que falhavam **devolvendo vazio**.

**Ainda aberto:** `Justificativa` não tem coluna `area` e herda a fronteira por `oficio__area`
(`NOVO-06`); o `AreaScopedManager` aceita `campo=` para isso, mas aplicá-lo a um modelo sem coluna é
decisão própria e não entrou. O `DB-02` (`area` NOT NULL) fica desbloqueado, com o `NOVO-31` na
frente.

### BE-10 ✅ RESOLVIDO · 🔴 App `justificativas` sem isolamento de área · AUD · 2 d · risco médio

`justificativas/selectors.py:20` (`listar_justificativas`), `:44`, `:48`; `views.py:32`
(`_oficios_summary_for_quick_add`); `forms.py:105` (queryset do picker de ofícios) — nenhum aplica
`filter_queryset_by_area`. O modelo `Justificativa` **não tem campo `area`**, e
`ModeloJustificativa.nome` é `unique=True` global.
**Efeito:** número, protocolo, assunto, servidores, roteiro e viatura de ofícios de outra unidade
aparecem no seletor; justificativas de outra área aparecem na lista e podem ser excluídas por URL.
**Correção:** migração acrescentando `area` (FK PROTECT) aos dois modelos, com backfill a partir
de `oficio.area`; `UniqueConstraint(area, nome)`; filtro nos 4 selectors e nos 2 pickers.

### BE-11 ✅ RESOLVIDO Editor de roteiro em 3 cópias · AUD · 3 d · risco alto

`roteiros/views.py:203` (`novo`, 89 linhas úteis) e `:311` (`editar`, 86 linhas) têm similaridade
0,629 e 41 linhas idênticas; `oficios/route_views.py:100` (`wizard_roteiro`, 175 linhas) partilha
20 linhas idênticas com as outras duas.
**Divergência real já existente:** só `novo`/`editar` tratam roteiro duplicado
(`encontrar_roteiro_duplicado`/`sobrescrever_roteiro_duplicado`); o fluxo do ofício não.
**Correção:** `roteiros/services/editor_flow.py::processar_submissao_editor(...)` devolvendo
resultado tipado, e um presenter único. As três views ficam com ~25 linhas.

**Duas medições corrigem o enunciado.** Contando interseção de multiconjunto de linhas
normalizadas (sem comentário nem branco), `novo` × `editar` dá **55**, não 41 — as duas são mais
parecidas do que o catálogo dizia. E `wizard_roteiro` partilha 20 de **165** linhas úteis: não é a
terceira cópia do editor, é outro fluxo (reuso-sem-cópia, soft-advance, vínculo `Oficio.roteiro`,
ações de wizard, outro template). Passá-lo pela mesma função exigiria bandeiras que desligam metade
dela, ou mudaria o comportamento do fluxo do ofício. Por decisão do usuário o `BE-11` unificou
**`novo` + `editar`**; a orquestração do wizard é o `BE-12`, que já era o PR seguinte.

**Entregue:** `roteiros/services/editor_flow.py` com `ResultadoSubmissaoEditor` (frozen dataclass,
sem `request`/`messages`/`redirect`) e `processar_submissao_editor`;
`roteiros/presenters.py::apresentar_pagina_editor_roteiro` no lugar dos dois dicts de contexto
literais; `roteiros/views.py::_responder_submissao_editor` traduzindo o resultado em redirect ou
erro no form. `novo` 89 → **54** linhas úteis, `editar` 86 → **58**, interseção 55 → **31** — das
quais 7 são só parênteses e vírgula. Comportamento inalterado: as duas mensagens de duplicado
seguem com textos diferentes, `delete_url` segue existindo só em `editar`, e as três telas rendem
prints byte a byte idênticos antes e depois.

**O terceiro pedaço partilhado, esse sim resolvido nos dois lados:** o parse de `autosave_obj_id`
estava copiado em `roteiros/views.py` e `oficios/route_views.py`. Virou
`roteiros/services/autosave.py::pk_de_autosave`. Só o parse — os querysets divergem de propósito
(área ativa contra área do ofício) e continuam em cada view, com o comentário de escopo.

### BE-12 ✅ RESOLVIDO `wizard_roteiro` concentra a regra de vínculo/cópia na view · AUD · 2 d · risco alto

`oficios/route_views.py:100` — 181 linhas e 24 ramos, a maior view do sistema (a segunda tem 125).
Decide vínculo sem cópia ou rascunho novo (`:127-143`), instancia `Roteiro(...)` direto
(`:136`, `:167`) e persiste em quatro pontos (`:94`, `:96`, `:144`, `:183`).
**Efeito:** a regra que mais gera bug de dados neste sistema — roteiro é compartilhado entre
ofícios — não é testável sem subir request HTTP nem reusável pelo fluxo avulso.
**Plan mode obrigatório.**

**A cobertura media o defeito melhor que o tamanho.** Antes de mexer, `coverage` sobre
`oficios/route_views.py` com a suíte da etapa: **69%**, e o que faltava era `:125-160` — o bloco
inteiro de `if form.is_valid() and validated["ok"]`. Nenhum teste do repositório exercitava o
reuso-sem-cópia, a materialização de rascunho novo, nem qualquer das quatro saídas de navegação do
caminho válido. A regra "que mais gera bug de dados neste sistema" tinha cobertura **zero**.

**Entregue:** `oficios/services.py` ganhou `ResultadoRoteiroDoOficio`, `salvar_roteiro_do_oficio`,
`salvar_rascunho_parcial_do_oficio` e `montar_roteiro_inicial_do_oficio`, mais os privados
`_materializar_rascunho_do_oficio` e `_revincular_roteiro_ao_oficio`. A view ficou com navegação,
mensagens e render, e ganhou `_redirect_after_roteiro_save` — nome que segue o par já existente em
`traveler_views.py`.

| | antes | depois |
|---|---:|---:|
| `wizard_roteiro`, linhas úteis | 165 | **124** |
| `wizard_roteiro`, ramos | **33** | **13** |
| cobertura de `route_views.py` | 69% | 88% |

Os 33 ramos eram o triplo da segunda maior view de wizard (12). Com 13, deixa de ser exceção.

**As duas funções de gravação são `@transaction.atomic`** — decisão do usuário. A requisição grava
`Oficio`, `Roteiro`, `RoteiroDestino` e `RoteiroTrecho` (mais um delete de rascunho), e os services
chamados eram atômicos cada um mas o conjunto não. Isto fecha o **item 1** da lista de perigo do
`BE-14`; os outros 46 sites seguem lá.

**O que a extração destravou**, e é o que o enunciado pedia: três cenários que eram intestáveis
antes. Falha no meio da gravação (não deixa roteiro órfão), gravação fora de request (`NOVO-88`), e
a guarda de área cruzada de `vincular_roteiro_ao_oficio_sem_copia` — inalcançável pela view, porque
`obter_roteiro_escolhido_do_post` já filtra pela área do ofício.

### BE-13 ✅ RESOLVIDO · 🟠 `roteiros/roteiro_logic.py` fora do contrato de camadas · AUD · 4 d · risco alto

1.779 linhas, o maior módulo de produção do repositório, 57 definições de topo **todas privadas**,
misturando parsing de request, montagem de contexto e persistência. Importado pelos services.
**Correção:** fatiar por responsabilidade em PRs sucessivos — parsing sai para forms, contexto
para presenters, persistência para services. Depois de `BE-11`.

#### Fatia 1 ✅ — o parsing de request (o resto segue aberto)

**Três correções ao enunciado, medidas antes de mexer.**

**As migrações não importam o módulo.** `roteiros/migrations/0010` e `0012` (e `roteiros/models.py`)
apenas **citam** `roteiro_logic` em comentário, não importam. A amarra que travaria mover código não
existe. Importam de verdade só três módulos, todos em `roteiros/services/`.

**O acoplamento a `request` era raso.** Em 1.845 linhas, `request` aparecia **22 vezes como
`request.POST` e uma como `request.method`** — nada de `user`, `GET`, `area` ou sessão. Sete funções
o recebiam.

**Mover as funções não cabia nesta fatia, e o grafo diz por quê.**
`_build_roteiro_state_from_post` chama 12 funções do próprio módulo e
`_build_roteiro_diarias_from_request` chama 6, incluindo o motor de diárias. Levá-las para um módulo
novo arrastaria meia dúzia junto ou criaria import cruzado de volta.

**O sintoma, com nome:** `docs/PADRAO_SERVICES.md:20` proíbe service manipular `request`, e o código
contornava fabricando **seis objetos falsos** — dois deles dentro do próprio `roteiro_logic`, que
montava um request para chamar a si mesmo. E `_validate_roteiro_state(state, oficio=None)` tinha
**173 linhas e nunca lia `oficio`**: dois chamadores construíam `SimpleNamespace` para alimentar um
parâmetro morto.

**Entregue:** cinco assinaturas passaram a receber `post`; `_setup_roteiro_querysets` ganhou `method`
explícito (o chamador já o tinha e o embrulhava só para desembrulhar do outro lado); **duas funções
foram apagadas** — `_parse_destinos_post` e `_extract_roteiro_posted_trechos` eram invólucros de uma
linha que só desembrulhavam o request para chamar `services/editor_parser.py`; os seis objetos falsos
e o parâmetro morto sumiram; e quatro testes deixaram de montar `RequestFactory` para alcançar o
parser.

| | antes | depois |
|---|---:|---:|
| ocorrências de `request` no módulo | 23 | **1** (o nome de uma função) |
| `SimpleNamespace` em `roteiros/services/` | 3 | **0** |
| defs de topo | 57 | 55 |
| linhas | 1.845 | 1.829 |

**O módulo continua com 1.829 linhas, e isso é o esperado:** esta fatia tira o acoplamento, não o
volume. Ela é pré-requisito das outras duas — função que recebe `request` não pode ser movida para
parser, presenter nem service antes de deixar de recebê-lo.

**Falta para fechar o `BE-13`:** contexto (3 funções, entre elas `_build_roteiro_form_context`, 113
linhas → `presenters.py`) e persistência (3 funções, entre elas o gravador atômico de 3 tabelas).
Levantamento sobre a próxima: das 57 funções, **17 são invólucros de uma linha** para módulos já
extraídos (`services/editor_parser.py`, `editor_context.py`, `editor_state.py`, `map_defaults.py`) —
86 linhas deletáveis a custo zero de teste, e nenhuma chamada de fora do módulo. É a fatia mais
barata que sobrou.

#### Fatia 2 ✅ — contexto para presenters, e os invólucros

**Correção aos meus próprios números.** Eu havia registrado "17 invólucros, 86 linhas, custo zero".
Medido por AST: **14** invólucros (dois já tinham morrido na fatia 1) mais um morto, **40 linhas**, e
o custo não é zero — **107 call sites** a reescrever, `_parse_int` sozinho com 56.

**O contexto era um subgrafo fechado.** `_build_roteiro_form_context` (113 linhas) não tinha
chamador nenhum dentro do módulo e arrastava duas funções que só ela usa
(`_trechos_list_json_compat`, `_build_roteiro_diarias_fallback`). As três foram para
`roteiros/presenters.py`, que é o dono de montar dict para template (`docs/PADRAO_APP.md:10`).

**A fachada foi junto, e esse é o ponto de camada.** `montar_contexto_editor_roteiro` estava em
`services/roteiro_editor.py`; deixá-la lá faria um **service importar um presenter** — a violação que
o `BE-13` existe para corrigir. Com ela no presenter, `oficios/route_views.py` passa a importar de
`roteiros.presenters` (view → presenter, `docs/PADRAO_APP.md:11`) e `services/__init__.py` deixa de
re-exportar.

**Os invólucros.** 14 delegavam em uma linha para funções públicas que o próprio módulo já importava
no topo; o 15º, `_resolve_uf_from_cep`, não tinha chamador em lugar nenhum. Três dos 14 tinham
**zero chamadas** — eram função morta com import órfão junto, e o `ruff` apontou os três imports
depois da remoção.

| | antes da fatia 2 | depois |
|---|---:|---:|
| `roteiro_logic.py` | 1.829 linhas, 55 defs | **1.579 linhas, 37 defs** |
| `presenters.py` | 421 linhas | 589 |

**Rede antes de mover:** havia 20 linhas descobertas no subgrafo, e duas não eram detalhe — o ramo
`roteiro_state is None` (reconstrução do estado) e os ramos que **dividem o valor das diárias pelo
número de viajantes** com `ROUND_HALF_UP`. Sete cenários pela fachada pública, verdes antes da
mudança de arquivo. O caso que trava o arredondamento é 1,00 ÷ 8 = 0,13 (truncando daria 0,12).

**Primeira travessia de fronteira de fim de linha desta etapa:** `roteiro_logic.py` é CRLF puro e
`presenters.py` é LF puro. Os dois seguem homogêneos depois da mudança.

**Falta para fechar o `BE-13`:** a persistência — 3 funções, entre elas
`_salvar_roteiro_avulso_from_roteiro_state`, o gravador atômico de 3 tabelas. É a mais arriscada, e
a única citada por nome em migração, modelo e testes.

#### Fatia 3 ✅ — a persistência sai, e o módulo ganha o nome certo (`BE-13` **fecha**)

**O gravador era um sumidouro fechado**, o melhor caso das três fatias: ninguém dentro do módulo
chamava `_salvar_roteiro_avulso_from_roteiro_state`, e as outras duas
(`_atualizar_datas_roteiro_apos_salvar_trechos`, `_persistir_diarias_roteiro`) só ela chamava. Foram para
`roteiros/services/editor_persistence.py` com `_roteiro_combine_date_time` junto, **as quatro
públicas** — como nos módulos irmãos (`editor_parser` tem 9 públicas e 0 privadas). O
`@transaction.atomic` foi com o gravador, decorando a função, não o módulo.

**O módulo virou `roteiros/services/editor_state_builder.py`.** O nome antigo descrevia um saco de
coisas; o que sobrou tem uma responsabilidade só — montar e validar o estado do editor a partir do
POST e dos trechos gravados. O lugar novo é o que `docs/PADRAO_APP.md:8` reserva para isso; até aqui
era um arquivo solto no topo do app. O ciclo de import que a análise dizia não existir **de fato não
existe**: verificado subindo `manage.py check` com o módulo já dentro do pacote, antes de mover
qualquer linha. Renomeação por `git mv`: rename puro no `git diff --find-renames`, CRLF preservado
(1.337/1.337), e as 73 linhas alteradas são só os imports dos 17 chamadores — **sem alias**, para não
repetir a "abstração adotada pela metade" que este catálogo critica.

| | antes da fatia 3 | depois | acumulado nas 3 fatias |
|---|---:|---:|---:|
| o módulo | 1.579 linhas, 37 defs | **1.337 linhas, 33 defs** | 1.845 → **1.337** (−27%), 57 → **33** defs |
| `editor_persistence.py` | — | **276 linhas, 4 defs, todas públicas** | — |

**O módulo continua grande, e o PR diz isso.** 1.337 linhas dominadas por `_validate_roteiro_state`
(171) e `_build_roteiro_state_from_post` (132). Mas grande **com uma responsabilidade** é outro
problema, que este catálogo não nomeia: o enunciado do `BE-13` é "fora do contrato de camadas", e
parsing de request, contexto e persistência não estão mais lá dentro. As 33 defs seguem privadas de
propósito — dar contrato público a elas é trabalho de quem for reduzir o volume.

**Nota de nome:** as menções a `roteiro_logic` em `docs/` **continuam com o nome antigo de
propósito**. Elas registram medições e decisões datadas ("1.779 linhas", "57 defs"), e reescrevê-las
tornaria o registro falso sobre o próprio passado. Só os documentos de arquitetura viva
(`ROTEIROS_ARQUITETURA.md`, `PADRAO_CRUD.md`) foram ajustados, porque descrevem o hoje.

**A rede desta fatia é pequena, e o motivo está no `NOVO-98`:** três dos cinco cenários que escrevi
passavam com o código quebrado. Sobraram dois que mordem, e a garantia mais importante — o gravador
ser atômico — já tinha teste desde o `DB-08`; conferi por inversão que ele reprova sem o
`@transaction.atomic` em vez de duplicá-lo.

### BE-14 🟠 48 sites de persistência em view, sem service e sem transação · AUD · 3 d

Varredura AST dos `views.py`/`*_views.py`: 48 chamadas `.save`/`.delete`/`.create` fora de
`form.save()` — prestações 21, ofícios 6, planos 6, integrações 6. Caso exemplar:
`prestacoes_contas/views.py:332` `_salvar_solicitacoes_em_lote` tem 47 linhas, 15 ramos, faz
parsing de `request.POST` por regex e grava N linhas em laço.
`transaction.atomic` existe em 57 sites, mas **zero** em `prestacoes_contas/services.py` (643 LOC),
`termos/services.py` (709) e `planos_trabalho/services.py` (1.314).
**Efeito:** salvar o lote de solicitações é operação parcial — se a quinta linha falhar, as quatro
primeiras já foram gravadas.

### BE-15 🟡 Numeração de documento reimplementada 3 vezes · AUD · 2 d · risco alto

(a) `oficios/services.py:425-440` — advisory lock, fallback `select_for_update`, reuso de lacunas,
retry de 3 tentativas; (b) `ordens_servico/models.py:190-245` — `max+1` com
`pg_advisory_xact_lock`/`select_for_update`, **sem reuso de lacuna**, mas **com** retry de 3
tentativas; (c) `planos_trabalho/models.py:537-573` — contador incremental em
`ConfiguracaoSistema.pt_ultimo_numero`, natureza completamente diferente.

> **Enunciado corrigido pela verificação (05/08):** o original dizia que a Ordem de Serviço era
> "sem reuso de lacuna e sem retry". A parte do retry é **falsa** —
> `ordens_servico/models.py:200-214` tem um laço `for attempt in range(3)` que recaptura o
> `IntegrityError` da constraint e tenta de novo. Provado em PostgreSQL real: forçando colisão na
> primeira tentativa, o `save()` se recupera na segunda, sem exceção.

**Efeito real:** OS não reaproveita número cancelado, então as lacunas se acumulam; e uma corrida
perdida devolve `IntegrityError` cru **só depois de esgotar as três tentativas** — bem mais raro
do que o catálogo sugeria.
**Correção:** `core/numeracao.py::reservar_numero(...)`. Teste de concorrência com duas threads
**antes** de qualquer mudança.

### BE-16 🟡 Abstrações de `core` adotadas pela metade · AUD · 2 d · risco baixo

- `core/pagination.contexto_paginacao`: 2 de 14 listas; as outras 12 instanciam `Paginator` direto
  e sobrevivem **6 cópias privadas** de `_pagination_pages` (`cadastros`, `roteiros`, `usuarios`,
  `termos`, `justificativas`, `core/catalog.py`).
- `core/deletion.excluir_com_protecao`: **1 uso** (`cadastros/services.py:30`) contra 45
  `.delete()` cru — uma FK `PROTECT` vira 500 em 44 sites.
- `core/retorno`: **6 módulos** adotam (`cadastros/views.py`, `oficios/view_navigation.py`,
  `eventos/views.py`, `termos/views.py`, `documentos/views.py`, `core/catalog.py`); os 8 sites de
  prestações não (ver `BE-08`).

> **Corrigido pela verificação (05/08):** o catálogo dizia 3 usos de `excluir_com_protecao` e 5
> módulos adotando `core/retorno`. São **1** e **6**. No primeiro caso a assimetria de adoção é
> ainda **pior** do que o registrado.

**Correção:** três PRs mecânicos, verificáveis por grep.

### BE-17 ✅ RESOLVIDO · 🟡 `core/views.py` é 75% fixture de UI Lab · AUD · 1,5 d

**Fechado em 07/08 pela remoção do UI-lab.** `core/views.py` foi de **1.249 para 237 linhas**: saíram
`UI_LAB_PAGE_DEFINITIONS` e as 17 views `ui_lab_*`. Ficou o que sempre foi produção — `health`,
`metrics`, `LoginView`, `dashboard`, `perfil`.

1.261 linhas, das quais **947 (75%)** são símbolos `UI_LAB_*`. O que pertence a `core` — health,
metrics, LoginView, dashboard, perfil — são 314 linhas. Em paralelo existem **dois** UI Labs:
o app `ui_lab2` (656 LOC + 18 templates) e `templates/dev/ui_lab` (19 templates).

### BE-18 🟠 Logging estruturado existe e só um app usa · AUD · 2,5 d

`core/errors.py:20` define `capture(exc, contexto, **dados)` e `core/logging.py:19` serializa em
JSON. As **64 chamadas estão todas** sob `integracoes/google_drive`. Seis apps (cadastros,
diario_bordo, eventos, justificativas, prestacoes_contas, usuarios) não têm logger nem capture.
`prestacoes_contas` tem 6.739 linhas de produção e **não emite um único log**.
157 `except Exception`/bare em produção; **72 (46%) sem nenhum log**.
**Correção:** `capture()` como contrato único, registrado no `AGENTS.md`; regra nova no
`audit_django_architecture.py` com catraca que só desce.

### BE-19 🟠 `require_area_role` tem zero usos · AUD · 1,5 d

`core/permissions.py:28` define `require_area_role(minimum_role)`; grep fora de testes: **zero
chamadas**. `core/context_processors.py:31` calcula `can_admin_area`, usado em **0** templates
(`can_edit_area` aparece em 5). A única barreira real é `AreaRoleRequiredMiddleware`, que só
distingue LEITOR de não-LEITOR.
**Efeito:** `PAPEL_ADMIN` é decorativo — um EDITOR tem os mesmos poderes dentro da área.
**Decisão humana necessária:** quais operações exigem ADMIN.

### BE-20 ✅ RESOLVIDO · 🟡 `diario_bordo` é app-casca morto · MED · 0,5 d

33 linhas de Python no total: `models.py` 49 bytes, `services.py` 54, `forms.py` 66, uma view
`index` que renderiza um placeholder ("Base futura para geracao de diario de bordo a partir de
modelo XLSX"). A funcionalidade real mora em `prestacoes_contas`
(`diario_bordo_form.html`, `diario_motorista_form.html` e 7 partials).
`grep -rn "diario_bordo:index\|diario-bordo" templates/` → **zero**: a rota não é alcançável.
Colateral: o piso de cobertura de 91,17% em `.github/coverage-floors.json` mede 33 linhas.
Era o `P-08` da Etapa 8 do ciclo antigo, nunca decidido.

**Decidido: o app sai.** Prova de morte (`AGENTS.md` §6), varrendo o repositório inteiro — toda
referência ao **app** era fiação, nenhuma era uso:

| onde | o que era |
|---|---|
| `config/settings/base.py:51` | `INSTALLED_APPS` |
| `config/urls.py:28` | a rota `diario-bordo/`, que nenhum template, JS ou `reverse()` alcançava |
| `.github/coverage-floors.json` | o piso de 91,17% sobre 33 linhas |
| `.github/workflows/tests.yml:33` | `COVERAGE_APPS` |
| `README.md`, `docs/ESTADO_ATUAL_3_0.md` | listas de apps |

**Zero imports** do app em qualquer lugar; **sem migrations e sem tabela** (`showmigrations` →
`(no migrations)`). Conferido depois de apagar: `manage.py check` limpo,
`reverse("diario_bordo:index")` → `NoReverseMatch`, `GET /diario-bordo/` → **404**.

Tudo o mais que casa com `diario_bordo` no repositório é a **funcionalidade**, que fica intacta:
`prestacoes_contas/diario_views.py` e `diario_services.py`, `documentos/resources/diario_bordo.xlsx`
com seu golden test, e `naming.nome_diario_bordo` do Drive. O app-casca nunca teve relação com eles
— era só um nome igual.

**Colateral que quase virou vermelho na `main`:** o gate de cobertura percorre as chaves do
`coverage-floors.json` e reprova com `no measured production statements` quando um app não tem
statement medido. Apagar o app e esquecer a chave derrubaria o CI inteiro, com uma mensagem que
fala de cobertura e não de app inexistente. `core/tests/test_pisos_de_cobertura.py` passa a exigir
que `coverage-floors.json` e `COVERAGE_APPS` declarem o mesmo conjunto, e que todo piso tenha
diretório no disco.

### BE-21 ✅ RESOLVIDO · 🟡 Presenter morto prometendo funcionalidade inexistente · MED · 0,25 d

`oficios/presenters.py:621` — `apresentar_opcoes_documentais_oficio()` devolve
`[{"label": "DOCX (em breve)", "enabled": False}, {"label": "PDF (em breve)", "enabled": False}]`.
Grep no repositório inteiro: **1 ocorrência, a própria definição**. Zero chamadores.

**Eram duas, não uma.** O enunciado achou a que procurou pelo nome. Varrendo as **12 funções
públicas** do módulo com AST — contando uso fora *e* dentro dele, que é o que separa morta de
chamada-só-internamente —, duas têm zero dos dois:

| função | fora | dentro |
|---|---|---|
| `apresentar_opcoes_documentais_oficio` | 0 | 0 |
| `apresentar_modelo_motivo_card` (`:828`) | 0 | 0 |

A segunda é um presenter de **card** para modelo de motivo, logo acima de
`apresentar_linha_lista_simples_modelo_motivo` (3 usos), que faz o mesmo trabalho em formato de
linha. A tela migrou de card para lista simples e o presenter de card ficou.

A varredura também desarmou dois falsos positivos: `apresentar_pagina_detalhe_oficio` e
`apresentar_status_etapa_oficio` não têm chamador externo, mas são chamadas **dentro** do módulo
(`:878` e `:811`) por funções vivas. Um grep por "quem importa" as teria apagado.

**Removidas as duas.** `ruff` limpo (nenhum import ficou órfão), `reverse` segue com 36 usos no
módulo, e o texto "em breve" não existe mais em nenhum `.py`, `.html` ou `.js` do repositório.

A primeira era pior que morta: **prometia funcionalidade inexistente**. Se alguém a tivesse ligado a
um template, a tela mostraria dois botões desabilitados jurando DOCX e PDF que nunca foram
escritos.

### BE-22 ✅ RESOLVIDO · 🟡 Dez arquivos `.py` com BOM UTF-8 · AUD · 0,5 d

Todos em `cadastros/`. Quebram `ast.parse` em ferramenta de análise estática.

**O enunciado estava certo** — primeiro desta rodada. Confirmados os 10 `.py`, todos em
`cadastros/`; a varredura do repositório inteiro achou mais um, `docs/REGRAS_DE_NEGOCIO.md`, que
saiu junto por ser o mesmo defeito e 3 bytes.

**E o efeito é maior do que "quebra uma ferramenta".** Lido como `utf-8` — o que praticamente toda
ferramenta faz — o `U+FEFF` vira caractere no início do módulo:

```
SyntaxError: invalid non-printable character U+FEFF
```

`cadastros/views.py` é **o único arquivo do repositório** que obrigava o gate do `S-06`
(`scripts/audit_django_architecture.py:205`) a ler com `utf-8-sig`. Ou seja: **o remendo estava na
régua, não no defeito** — e entrou no mesmo commit (`b182e5f`) que trouxe os BOMs e o arquivo
`tatus` da raiz. Pior, o gate irmão do `P-05` (`drive_excepts_without_capture`) lia com `utf-8`
puro e só não quebrava porque nenhum arquivo do Drive tinha BOM: estava a **um arquivo** de virar
vermelho de bootstrap, do tipo que o `NOVO-25` já custou uma sessão inteira.

**Corrigido:** BOM removido dos 11 arquivos (diff de 11 linhas — conferido byte a byte que só os
3 bytes saíram), o gate do `P-05` passou a ler `utf-8-sig` igual ao irmão, e
`core/tests/test_sem_bom.py` impede a volta. O `utf-8-sig` fica nos dois de propósito: a rede é o
teste, e gate que morre no `ast.parse` é o pior lugar para descobrir o problema.

~~`QA-11` (`reparar-producao.yml` em UTF-16LE) **segue aberto**~~ — **errado, e o erro é meu.** Escrevi
isso lendo a linha do `QA-11` no catálogo, que estava desatualizada: a correção tinha entrado em
`993e14c`, em 05/08. Por causa disso o teste nasceu com uma exceção para um arquivo que já estava
limpo — um buraco na própria rede, por nada. A exceção foi removida junto do fechamento do `QA-11`.

### BE-23 🟡 PARCIAL — sufixo CRUD padronizado; os outros 75% seguem sem vocabulário · AUD · 1 d · risco médio

Das 433 rotas nomeadas, **307 (71%)** não usam nenhum sufixo do `PADRAO_APP.md`. `cadastros` e
`usuarios` usam inglês (`_create`/`_update`/`_delete`); `eventos`, `justificativas`, `oficios`,
`planos_trabalho` e `prestacoes_contas` usam português (`_novo`/`_editar`/`_excluir`). Nenhum app
mistura internamente.
**Não viaja com nenhuma outra etapa:** renomear rota exige `urls.py` + `reverse()` + templates +
testes no mesmo PR.

**Duas unidades de medida, e as duas valem.** As "433 rotas" contam entradas do resolver do Django
(**436** em 06/08) — cada nome por namespace. Contando declarações `name=` nos `urls.py`, são
**283**. Nenhum número está errado; eles medem coisas diferentes, e vale registrar qual é qual para
a próxima medição não parecer contradição.

**Uma parte do enunciado está errada:** *"nenhum app mistura internamente"*. Misturam, todos os
cinco — `planos_trabalho` 4 nomes em inglês contra 11 em português, `justificativas` 1 e 7,
`oficios` 1 e 3, `prestacoes_contas` 1 e 4, `eventos` 1 e 2.

**E o recorte "inglês contra português" cobre só 70 das 283.** As outras **213 (75%)** não usam
nenhum dos dois vocabulários: são `detalhe`, `api_*`, `wizard_*`, `*_pdf`. Padronizar *isso* é
decidir um vocabulário para o sistema inteiro, não traduzir sufixo — e não foi feito aqui.

**Fechado o recorte do sufixo CRUD:** as **28** rotas em português renomeadas pela regra
`_novo→_create`, `_editar→_update`, `_excluir→_delete`, `_lista→_index`.

**Só o `name=` mudou.** O `path()` continua igual, então nenhuma URL salva quebra. O nome da *view*
(`def modelo_excluir`) também ficou: é outra camada, e o `PADRAO_APP.md:12` fala de `urls.py`.

Prova de que foram 28 e só 28: os nomes do resolver antes e depois, **436 → 436**, com o conjunto
novo batendo exatamente o antigo com a regra aplicada. Toda referência era namespeada
(`"app:nome"`) — a varredura por `reverse(f"...")` montado por partes deu **zero** —, o que fez a
troca ser mecânica.

Catraca em `core/tests/test_vocabulario_de_rotas.py`. Ela lê os `urls.py`, **não o resolver**:
parte das rotas de `core` só existe sob `settings.DEBUG` (`core/urls.py:18`), e das 28 em português
**uma** (`core:ui_lab_eventos_lista`) estava justamente ali — um teste via resolver teria deixado
passar. Segundo teste é o piso de 70 nomes com sufixo do padrão, para ninguém "padronizar" apagando
o sufixo em vez de traduzi-lo.

### BE-24 🟡 Repositório com 133 MB de pack e 175 arquivos indevidos · MED+VER · 1 d

`git count-objects -vH` → **size-pack 132,98 MiB** (5 packs), medido na verificação. A primeira
medição desta sessão deu 106,02 MiB; a diferença são commits entrados depois, na mesma sessão —
o número estava desatualizado, não errado quando escrito. Vale como lembrete de que medida de
repositório envelhece rápido e precisa ser refeita no PR que a usa como gate.

`screenshots/` = **89 MB** em 130 arquivos
rastreados (PNGs de 1,5–2,3 MB do UI Lab). Além deles, 175 arquivos rastreados que não deveriam
estar: `tmp/` (23), `media_teste/` (6), `migration_backups/` (2, um deles um `.dump` do banco),
`logs/` (2), `.tmp-footer-check/` (3), `.tmp-sede-destinos-check/` (4), `_tmp_check4.py`,
`_tmp_check5.py`, `tatus` (um `git status` redirecionado por engano),
`.codex-runserver-8001.{err,out}.log`.

> **Remedido em 09/08: `screenshots/` está em 39 MB**, não 89 — parte dos PNGs do UI Lab saiu junto
> com os labs no PR #247. A ordem de grandeza do defeito continua; o número, não. E há uma
> dependência nova: `screenshots/auditoria-telas/_capturar.py` é hoje o **único** lugar do
> repositório que enumera as telas do sistema, e o `NOVO-67` precisa desse corpus. Tirar
> `screenshots/` do repositório **depois** da etapa E0, que move o corpus para `scripts/`, ou o
> `BE-24` leva a régua embora junto com as imagens.
>
> `ui_lab2/` também sobreviveu, como diretório de `__pycache__` — virou o `NOVO-69`.

### BE-25 ✅ RESOLVIDO · 🟡 Dois UI Labs concorrentes, sem regra de qual é o vigente · AUD · 0,75 d

**Fechado em 07/08: não se escolheu um, apagaram-se os dois.** E o código dizia de si mesmo que eram
duas gerações — `ui_lab2/views.py:166` chamava o outro de "UI Lab 1.0".

A assimetria explica por que isto custou o que custou: o **2.0** era app isolado (`ui_lab2/`, 657
linhas) e saiu com `rm -rf` mais duas linhas de registro. O **1.0** não tinha app: vivia dentro de
`core/views.py`, `core/urls.py`, `core/forms/__init__.py` e `core/navigation.py`. Foi 90% do
esforço.

`ui_lab2` (656 LOC + 18 templates) e `templates/dev/ui_lab` (19 templates). Ambos só roteados sob
`DEBUG`, mas `ui_lab2` está em `INSTALLED_APPS` em todos os ambientes
(`config/settings/base.py:54`) e tem piso de cobertura de 67,42%.
**Decisão humana necessária.** O perdedor sai com a prova de grep do `AGENTS.md` §3.6.

---

## DB — Dados, migrações e integridade

### DB-01 ✅ RESOLVIDO · 🟠 A tabela de diárias é nacional e qualquer EDITOR a altera · AUD+VER · 1,5 d · risco médio

> **Este ID foi reescrito pela verificação (05/08). O enunciado original estava invertido** — ele
> pedia exatamente a mudança que o código evita de propósito.

`cadastros/models.py:659-751` — `TabelaDiaria` não tem FK para `AreaTrabalho`, e isso **é decisão
documentada**, não esquecimento. `cadastros/selectors.py:24-28` explica no docstring: *"os valores
de diária vêm de norma externa e valem para todas as áreas — separá-los por área abriria a porta
para duas áreas cobrarem valores diferentes pela mesma viagem"*.

O defeito real é outro, e é de autorização: a tela que edita esses valores
(`cadastros/views.py:620`, rota `configuracao_sistema`) **não tem controle de papel nenhum** além
do bloqueio genérico a LEITOR feito pelo `AreaRoleRequiredMiddleware`. Qualquer EDITOR de qualquer
área altera um parâmetro financeiro **nacional**, sem aviso às demais.

**Correção:** portão de permissão na tela (`require_area_role(PAPEL_ADMIN)` ou permissão de
sistema dedicada — casa com `BE-19`, que aponta `require_area_role` com zero usos) e confirmação
explícita na interface de que o valor vale para todas as áreas.
**O que NÃO fazer:** fragmentar a tabela por área. Reintroduziria exatamente a inconsistência que
o desenho atual evita, e mexeria na regra de dinheiro fechada no ciclo de julho.


> **RESOLVIDO em 06/08/2026.** Decisão do usuário: **portão de superusuário**, não de papel de
> área. Valor nacional não é assunto de área nenhuma — nem da que está mais organizada.
>
> O portão fica no **POST de diárias** (`cadastros/views.py`), e não como decorador da view. Essa
> é a armadilha do defeito e o motivo de metade dos testes: `configuracao_sistema` serve **três
> abas** (`instituicao`, `oficio`, `roteiros`). Um decorador — que é o caminho óbvio — tiraria as
> configurações de instituição e de ofício de todo mundo que não é superusuário.
>
> Ler o valor vigente continua livre para todos: ele entra em todo roteiro calculado. A aba segue
> aberta, com o histórico de vigências e um aviso de somente leitura, **sem o formulário** — porque
> mostrar o formulário e recusar no submit faria a pessoa preencher e perder o que digitou.
>
> **Consequência que vale registrar:** com a decisão por superusuário, `require_area_role`
> (`core/permissions.py:28`) **continua com zero usos**. O `BE-19` previa que este ID fosse a
> estreia dele; não foi. O helper segue esperando um caso de uso real, e a decisão de quais
> operações exigem `PAPEL_ADMIN` continua pendente na §8 do plano mestre.
>
> Sete testes em `cadastros/tests/test_portao_diarias.py`, provados mordendo (EDITOR e ADMIN de
> área gravavam com `302`). Um deles existe só para separar "portão de superusuário" de "portão de
> papel": se alguém trocar por `require_area_role(PAPEL_ADMIN)`, ele reprova.
>
> `cadastros/tests/test_configuracao_diarias.py` passou a logar como superusuário. Aqueles testes
> cobrem o **formulário** — 15% e 30% derivados no servidor, valor zero recusado, vigência
> duplicada recusada —, não a permissão; sem a troca eles passariam a medir o 403 e parariam de
> medir a regra de dinheiro.

### DB-02 ✅ RESOLVIDO (07/08/2026) · 🔴 `area` anulável em 27 de 28 modelos — três dívidas diferentes, não uma · AUD+VER · 5 d · risco alto

> **Enunciado reescrito em 07/08/2026**, como o `NOVO-34` exigia, e **grupo operacional migrado
> no mesmo dia**. O original tratava os 27 modelos como dívida uniforme ("`NOT NULL` nos
> transacionais") — e num banco recém-migrado **cinco modelos já nascem com `area IS NULL` por
> seed de migração**, enquanto a linha global de `ConfiguracaoNumeracaoOficio` **é** o piso de
> numeração. A migração uniforme destruiria mecanismo desenhado de propósito.

Os dois efeitos do enunciado original fecharam com o grupo 1: o balde `area IS NULL` que um
usuário sem vínculo enxergava inteiro (`core/tenancy.py:69-71`) passou a ser **vazio por
construção** para dado operacional, e escrita sem área falha alto (`IntegrityError`) em vez de
gravar órfão invisível. A dívida tinha três formas:

**Grupo 1 — Operacional: `NOT NULL`, feito.** Os oito modelos do `core.E001`: `Oficio`,
`Roteiro`, `Evento`, `TermoAutorizacao`, `OrdemServico`, `PlanoTrabalho`, `PrestacaoContas`,
`DocumentoArtefato` — migrações `*_area_obrigatoria` nos oito apps. Sete dos oito já derivavam a
área sozinhos no `save()`; **`Evento` era a exceção** — nascia sem área mesmo dentro de request —
e passou a derivar como os irmãos, com teste que falharia antes. A migração não precisou esperar
produção: o gate do `NOVO-12` roda `check --deploy --fail-level ERROR` **antes do `migrate`**
(protegido pelo rollback do `QA-03`), e o `core.E001` aborta com a instrução de backfill enquanto
houver órfão — a migração nunca encontra NULL que o operador não tenha visto.
`scripts/validar_not_null_db02.py` mede as oito tabelas sem esperar um deploy (limite 4 do
`AGENTS.md`); o backup já é automático no mesmo fluxo. Dois consertos saíram da janela
pré-migração: `backfill_legacy_areas` deixou de pular modelo com `field.null=False` (o critério
de nulidade em memória o esvaziaria justamente quando ele é necessário) e o signal de prestações
lê `oficio.area_id` (com `null=False`, ler `.area` num órfão levanta `RelatedObjectDoesNotExist`).

**Grupo 2 — Catálogo com padrão global: `NOT NULL` só depois de decisão de produto.**
`TipoEvento` (5 linhas globais de seed), `ProgramaSolicitante` (3), `HorarioAtendimento` (3),
`AtividadePlanoTrabalho` (11), os cadastros básicos (`Servidor`, `Viatura`, `Unidade`, `Cargo`,
`Combustivel`, `ConfiguracaoSistema`) e os modelos de texto (`ModeloMotivoEvento`,
`ModeloMotivoOficio`, `ModeloJustificativa`, `ModeloTextoRelatorioTecnico`,
`PresetAtividadesPlanoTrabalho`). A linha sem área aqui é o item **global** — as
`UniqueConstraint` condicionais em `area__isnull=True` documentam isso como desenho. `NOT NULL`
exige decidir, item a item, se o global vira cópia por área (o caminho do `NOVO-09`) ou ganha
dono. Decisão de produto, não de migração — registrada como `NOVO-45`, com a medição que ela
precisa: **nenhum picker oferta o global a usuário com área.**

**Grupo 3 — Global por projeto: `NOT NULL` fora de questão.** `ConfiguracaoNumeracaoOficio`: a
linha sem área é o piso de numeração de 2026 (`numero_inicial=75`), buscada de propósito com
`Q(area=area) | Q(area__isnull=True)`. Também fora, por razões próprias: `core.AuditEvent` e
`DriveReorganizacaoJob` são `SET_NULL` — a trilha e o job sobrevivem à área apagada; linha sem
área ali é histórico. Os dois auxiliares ficaram anuláveis **nesta rodada**, com razão anotada:
`OficioNumeroLacuna` também serve o piso global (`oficios/models.py:227` filtra lacunas
`area__isnull` de propósito) e entra num eventual redesenho da numeração; `DocumentoGeracao`
recebe a área explícita do request e a leitura já recorta.

**O passo 3 da correção original caiu por desnecessário:** com o grupo 1 `NOT NULL`,
`filter_queryset_by_area` sem área devolve vazio para todo modelo operacional mecanicamente —
mudar a semântica para os grupos 2/3 é parte da decisão do `NOVO-45`, não deste ID.

**Medição em produção:** o gate do `NOVO-12` imprime `core.E001`/`core.W001` a cada deploy — a
contagem real por modelo, no banco onde seed convive com dado de usuário. Se houver órfão
operacional, o primeiro deploy deste ID aborta com a instrução de
`backfill_legacy_areas --area SIGLA --commit`; rodado o backfill, é só disparar de novo.

Evidência: `core/tests/test_deploy_checks.py` prova o `IntegrityError` que falharia antes;
`core/tests/test_area_scoped_manager.py` reescreve o contrato (balde operacional vazio; balde de
catálogo preservado num modelo anulável); a suíte inteira passou a criar dado com área — o custo
virou instrumento reutilizável, `core/testing.py` (`area_de_teste`, `vincular_area`,
`com_request`, `sem_request`). A reescrita também revelou e fechou um N+1 real: a lista de
pendências do Drive materializava a `AreaTrabalho` de cada origem só para comparar pk —
invisível enquanto o legado tinha `area_id NULL`, porque FK `None` nem vai ao banco
(`integracoes/google_drive/status.py`).

> **Grupo 2 executado em 07/08/2026 — e a premissa do enunciado estava errada.**
>
> Decisão do usuário: cópia por área, seguindo o `NOVO-09`. Migrações `eventos/0016` e
> `planos_trabalho/0024`.
>
> **O que a medição corrigiu:** o §8 do plano mestre descrevia as linhas globais como "servidas a
> todas as áreas". **Não eram.** Medido nas três áreas do banco de desenvolvimento: as 22 linhas de
> seed (`TipoEvento` 5, `AtividadePlanoTrabalho` 11, `ProgramaSolicitante` 3, `HorarioAtendimento`
> 3) eram vistas por **zero** usuários com área — só quem não tem área as enxergava, porque
> `filter_queryset_by_area` é estrito e não faz união com o balde nulo. As constraints
> `*_global_unique` provam que um namespace global foi **projetado**; nenhum leitor o realizava.
>
> Isso muda o que a duplicação significa: não repartiu um acervo compartilhado, **deu a cada área um
> catálogo que ela não tinha**. Para o usuário, conteúdo que aparece.
>
> Medido na ida e na volta, num banco de teste: 22 linhas globais → 44 com 2 áreas, **zero** sem
> dono; a volta devolve exatamente 22, todas globais; a ida de novo reproduz o mesmo estado.
>
> **Duas armadilhas herdadas, uma delas cara:**
> 1. **`_base_manager`, nunca `objects`.** Modelo histórico de migração não recebe o manager
>    customizado do `BE-09` — `objects` não existe ali. E o erro **só aparece na volta**, porque a
>    ida sai cedo quando não há área. Apareceu drilando o rollback, não em produção.
> 2. **`SET CONSTRAINTS ALL IMMEDIATE`** antes do `ALTER TABLE`, herdado do `NOVO-09`: sem ele a
>    volta morre no PostgreSQL com `cannot ALTER TABLE ... because it has pending trigger events`.
>
> **`NOT NULL` nestes quatro continua bloqueado, e agora o motivo tem ID:** o `NOVO-49`. Instalação
> nova roda os seeds quando ainda não existe área — a duplicação sai sem fazer nada, por guarda
> explícita — e `criar_area` não semeia catálogo, então área nova nasce com os quatro vazios. É o
> mesmo comportamento que o `NOVO-09` deixou para `ModeloJustificativa`.

### DB-03 ✅ RESOLVIDO · 🟠 Limpeza de rascunhos apaga rascunho de outra área · AUD · 1 d

`roteiros/services/roteiro_editor.py:317` —
`Roteiro.objects.filter(destinos__isnull=True, trechos__isnull=True, saida_dt__isnull=True,
origem_cidade__isnull=True).exclude(pk=roteiro_atual_pk).delete()`, sem recorte por área. Teste
funcional em transação revertida: rascunho da área B apagado por usuário da área A.
**Efeito:** o autosave cria rascunho vazio antes de o usuário digitar. Enquanto um usuário da área
B está com o editor aberto nesse estado, qualquer usuário de outra área que salve um roteiro apaga
o dele — sem mensagem.
**Correção:** `filter_queryset_by_area` na base da consulta **e** recorte por idade
(`created_at__lt=now()-timedelta(minutes=30)`), para não competir com edição em curso.

### DB-04 ✅ RESOLVIDO · 🟡 Cache de artefato documental não recorta por área — risco latente · AUD+VER · 1 d

`documentos/services/document_cache.py:105-133` monta os filtros com `tipo`, `formato`,
`cache_key` e os ids de referência; `area` nunca entra, embora `DocumentoArtefato.area` exista com
índice próprio. A chave (`build_document_cache_key`, `:75-103`) é SHA-256 sem a área.

> **Severidade rebaixada pela verificação (05/08): de alta para média.** O enunciado original
> dizia que documento de uma área "pode ser servido a outra". A verificação rastreou os **6 pontos
> de chamada reais** e nenhum é alcançável sem uma referência que já escopa o resultado a um único
> registro de uma única área: ou passam sempre `oficio_id`/`servidor_id`/`termo_id`, ou pulam a
> leitura do cache quando não há referência (`if plano.evento_id:`, `if oficio is not None:`).
> **O vazamento não se reproduz no código de hoje.**

**Efeito:** é lacuna estrutural, não vulnerabilidade ativa. A função deveria receber `area` como
defesa em profundidade — o próximo chamador que esquecer a referência abre o buraco, e nada no
código o impede.


> **RESOLVIDO em 06/08/2026**, e a classificação de "latente" do enunciado estava certa — mas por
> um motivo diferente do que ele supunha.
>
> **Correção de um erro que quase entrou neste catálogo:** a primeira verificação afirmou que
> `documentos/services/persistence.py:102` cria o `DocumentoArtefato` **sem** preencher `area`, e
> que o campo ficaria `NULL` em todo artefato gerado. **Está errado.** O `create()` de fato não
> passa `area`, mas `DocumentoArtefato.save()` (`documentos/models.py:87-94`) deriva a área do
> ofício, do evento ou do termo. Ler só o `create()` levava à conclusão contrária — e ela teria
> mudado a correção inteira, porque com `area=NULL` toda view de PDF assinado daria 404
> (`documentos/views.py:65` recorta por área). Nada disso acontece.
>
> **O defeito de verdade.** A `cache_key` é um SHA-256 de conteúdo (`document_cache.py:91-103`) e
> não inclui área: dois ofícios de áreas diferentes com o mesmo conteúdo produzem a mesma chave.
> Quem separa as áreas na busca é a **referência** — e ela é opcional. Os cinco chamadores de hoje
> passam uma (`oficios/services.py:88`, `oficios/document_generation.py:67`,
> `ordens_servico/services.py:72`, `termos/services.py:172`, `planos_trabalho/services.py:1208`),
> e é só por isso que o defeito nunca foi alcançável.
>
> **A correção é tornar a chamada sem referência impossível**, e não confiar em quem chama:
> `get_cached_document_artifact` levanta `ValueError` se as quatro referências vierem vazias.
>
> **Por que não recortar por `get_current_area()`:** a geração documental roda **assíncrona**, em
> worker do Celery (`documentos/services/async_generation.py`), onde não existe área ambiente. Um
> recorte por estado ambiente ficaria correto no request e devolveria `None` sempre na worker —
> transformando o cache em nada, silenciosamente. A referência funciona nos dois contextos.
>
> **Por que não pôr área na `cache_key`:** mudaria o hash de todo artefato já gravado, invalidando
> o cache inteiro, para fechar um caminho que a referência já fecha por implicação — um ofício
> pertence a uma área só.
>
> Seis testes em `documentos/tests/test_cache_recorte.py`, sendo o primeiro deles a prova da
> premissa: o artefato herda a área do ofício. Se esse teste cair, o recorte por referência deixa
> de implicar recorte por área e a correção inteira perde o chão.

### DB-05 ✅ RESOLVIDO · 🟡 Placa de viatura única globalmente · AUD · 1,5 d

`cadastros/models.py` — `Viatura.placa = CharField(max_length=7, unique=True)` e
`Viatura.Meta.constraints` vazio. `justificativas/models.py` — `ModeloJustificativa.nome`
`unique=True`, e o modelo sequer tem `area`.
**Efeito:** uma área bloqueia o cadastro de outra e descobre pela mensagem de erro que a placa já
existe em algum lugar — vazamento por canal lateral. Viatura transferida entre unidades não pode
ser registrada nas duas.


> **RESOLVIDO em 06/08/2026.** A metade de `ModeloJustificativa.nome` já tinha saído no `NOVO-09`;
> esta é a de `Viatura.placa`.
>
> `unique=True` global virou **duas** `UniqueConstraint` condicionais, espelhando
> `justificativas/models.py:47-57`: `placa` quando `area IS NULL`, `(area, placa)` quando não.
> Duas e não um `unique_together` porque em SQL `NULL != NULL` — o composto puro deixaria passar
> duas linhas globais com a mesma placa.
>
> **A constraint sozinha não resolvia.** `ViaturaForm.clean_placa` (`cadastros/forms.py:492`) fazia
> a própria consulta, sem recorte, e reprovava antes de o banco ser consultado. Pior: a mensagem
> *"Já existe uma viatura com esta placa"* confirmava a existência de placa de outra unidade — um
> vazamento pequeno, mas entregue por formulário. Agora o recorte sai da área da instância quando
> ela existe e da área ativa quando é cadastro novo, e a mensagem diz "nesta área".
>
> **Validação de dados** (limite 4 do `AGENTS.md`), contra PostgreSQL: 0 placas repetidas dentro de
> área, 0 entre as globais. E o resultado não depende do banco: a constraint nova é **estritamente
> mais permissiva** que a que sai, então nenhum dado existente pode violá-la.
>
> **O achado do drill, e é o que importa operacionalmente:** a volta funciona no dia do deploy e
> **deixa de funcionar depois**. Medido, com duas áreas usando a mesma placa:
>
> ```
> IntegrityError: could not create unique index "cadastros_viatura_placa_af1b9674_uniq"
> DETAIL: Key (placa)=(DRL0A00) is duplicated.
> ```
>
> É inerente: não se reaperta uma unicidade que os dados já usaram alargada. Na janela em que o
> `QA-03` age não há duplicata e a volta passa. Depois, reverter exige decidir **qual viatura some**
> — decisão de gente, não de script. A query que lista o impedimento está no docstring da migração.

### DB-06 ✅ RESOLVIDO · 🔴 Cascata apaga comprovante e assinatura já coletados · AUD · 3 d · risco alto

`prestacoes_contas/signals.py:33` —
`prestacao.servidores_prestacao.exclude(servidor_id__in=ids_atuais).delete()`, disparado por
`post_save` de `Oficio` e por `m2m_changed` de `Oficio.servidores`. Teste funcional em transação
revertida: com 2 servidores, 1 anexo e 1 assinatura, após `oficio.servidores.set([s1])` restaram
`PrestacaoServidor=1, anexos=0, assinaturas=0`.
**Efeito:** trocar um servidor no ofício — edição rotineira — destrói comprovante de saque enviado
pelo servidor, número de solicitação e assinatura eletrônica já coletada. Sem confirmação, sem
soft-delete, com o arquivo órfão no disco.
**Correção:** desativação em vez de exclusão (`removida_em`/`ativa`). Enquanto isso não existir,
bloquear a remoção quando houver anexo ou assinatura não pendente.

> **Resolvido pela desativação, sem a etapa intermediária de bloqueio.** Bloquear a remoção exigiria
> recusar uma edição já cometida — o sinal roda em `post_remove`, depois de a M2M ter mudado —, e o
> único jeito seria levantar exceção dentro da transação do formulário: erro 500 numa tela de uso
> diário. A desativação não precisa recusar nada.
>
> Um campo só, `removida_em` (nulo = na equipe), em vez do par `removida_em`/`ativa` que o enunciado
> sugeria: dois campos podem discordar entre si, um não.
>
> **A regra não é "nunca apagar".** `PrestacaoServidor.sair_da_equipe()` apaga quem não tem nada
> coletado e marca quem tem — as dez cláusulas de `tem_dados_coletados()` estão provadas por
> inversão individual. Manter tudo faria a prestação voltar a exibir a equipe semeada de outro
> ofício, que é o motivo de o sinal existir.
>
> **Sem `--max`/catraca**, e de propósito: o defeito não é uma contagem que desce. É uma regra, e a
> regra está travada por `test_default_manager_name_continua_no_manager_que_filtra` — apontar o
> `_default_manager` para o manager irrestrito desligaria a proteção inteira sem nenhum teste de
> comportamento reclamar.
>
> **Continua aberto pela porta do cadastro:** `NOVO-35`.

### DB-07 ✅ RESOLVIDO · 🟠 Dois `CheckConstraint` em 54 modelos · AUD · 3 d · risco médio

61 `UniqueConstraint` contra 2 `CheckConstraint`
(`tabela_diaria_valor_24h_positivo` e `prest_serv_diaria_recebida_positiva`). Nenhum dos **9 pares
início/fim** tem constraint de ordem: `Evento`, `TermoAutorizacao`, `PlanoTrabalho`, `EventoPlano`,
`OrdemServico`… Medido em transação real: data de fim anterior ao início e diária negativa entram.
**Efeito:** o banco não é última linha de defesa de nada. Qualquer caminho que escape da validação
de formulário — import, comando, migração de dados, correção manual — grava período impossível, e
o valor viaja para o ofício e para a prestação assinada.
**Limite 4 do `AGENTS.md`:** cada migração entra com a query de validação dos dados existentes.

> **De 2 para 25 `CheckConstraint`.** Onze de ordem e doze de sinal, em oito modelos de seis apps.
> O levantamento por introspecção achou **mais** do que o enunciado: `Roteiro` tem **quatro**
> datetimes em cadeia (`saida_dt` → `chegada_dt` → `retorno_saida_dt` → `retorno_chegada_dt`), não
> um par, e `RoteiroTrecho` tem outro par que a lista dos "9 pares" não citava.
>
> **Entram os três elos consecutivos do roteiro e também o limite externo** (`saida_dt` ≤
> `retorno_chegada_dt`). Não é redundância: como `CHECK` com resultado nulo passa, um `chegada_dt`
> vazio quebra a transitividade da cadeia — e o par externo é justamente o que o motor de diárias
> usa para contar dia de viagem.
>
> **`gte`, não `gt`**, nas doze de ordem: evento de um dia tem fim igual ao início, e trecho sem
> deslocamento tem `km_final == km_inicial`. Provado por inversão — trocar por `gt` reprova 22 casos
> de limite. E **`nao_negativo` para valor calculado** (zero é plano sem diária), **`positivo` para
> valor que, existindo, tem de valer alguma coisa**.
>
> **O erro que a inversão pegou em mim.** As condições nasceram com
> `Q(campo__isnull=True) | ...` na frente, e eu havia escrito no docstring que o ramo era necessário
> para `BaseConstraint.validate()`, o caminho Python do `full_clean()`. **Medido, é falso nos dois
> caminhos**: removendo o ramo, nem o banco nem o `full_clean()` mudam de comportamento. Era código
> inerte com aparência de carga útil — pior que um comentário, porque ninguém o removeria sem medo.
> Saiu; a garantia de que nulo passa virou teste (`NuloContinuaPassandoTests`), que é onde ela é
> verificável.
>
> **Limite 4, operável:** `scripts/validar_constraints_db07.py` lê as constraints por introspecção
> e conta as linhas que cada uma reprovaria, saindo com código 1 se houver qualquer uma. As 23
> queries individuais estão nos docstrings das sete migrações, mas 24 queries soltas não são
> procedimento — o script é. Contra o banco de desenvolvimento com dados reais: **0 violações**.
>
> **Não medido em produção.** O banco desta sessão não tem volume para provar coisa alguma sobre a
> base real; o script existe para ser rodado lá antes do deploy.
>
> **De quebra:** `prest_serv_diaria_recebida_positiva` usava o kwarg `check=`, depreciado desde o
> Django 5.1 e removido no 6.0 — o import do modelo já emitia `RemovedInDjango60Warning`.

### DB-08 ✅ RESOLVIDO · 🟠 Coleções ordenadas aceitam duplicata · AUD · 2 d

`RoteiroDestino`, `RoteiroTrecho`, `PlanoDestino`, `EventoPlano` e `DiarioBordoTrecho` têm
`constraints=[]`. Provado em transação real: dois `RoteiroDestino` com a mesma `(roteiro, ordem)`
são aceitos.
**Efeito:** destino duplicado é contado **duas vezes pelo motor de diárias** e impresso duas vezes
no ofício e no termo. Ordem repetida torna a sequência não determinística, mudando o documento
gerado entre duas visualizações do mesmo roteiro.

> **Fatia 1 fechada em 07/08/2026 — e o enunciado errava em três pontos, todos corrigidos por
> medição antes de escrever constraint.**
>
> 1. **`eventos.EventoPlano` não existe.** O modelo é `planos_trabalho.EventoPlano`.
> 2. **`PlanoDestino` não é `(plano, ordem)`.** Um plano guarda ao mesmo tempo os destinos de
>    rascunho (`evento IS NULL`) e as cópias por evento, e `planos_trabalho/services.py:968` copia
>    `d.ordem` tal e qual ao comitar. `(plano, ordem)` **reprovaria produção no primeiro commit de
>    evento** — está travado por `test_o_rascunho_e_a_copia_do_evento_convivem_na_mesma_posicao`,
>    que é a inversão nº 3.
> 3. **Dois dos cinco não aceitam constraint simples.** `RoteiroTrecho`
>    (`roteiros/roteiro_logic.py:1629`) e `DiarioBordoTrecho`
>    (`prestacoes_contas/diario_services.py:282`) reaproveitam as linhas por id e gravam `ordem` uma
>    a uma — trocar duas posições colide no meio do laço. Ficam para a **fatia 2**, junto com a
>    troca dos dois escritores para dois passos.
>
> **A saída óbvia está fechada:** `deferrable=DEFERRED` não serve porque
> `supports_deferrable_unique_constraints` é `False` no SQLite e a suíte roda nos dois bancos — a
> constraint existiria só no PostgreSQL e o SQLite passaria sem testar nada. Medido, e travado em
> `test_o_sqlite_nao_suporta_constraint_adiada`.
>
> **A armadilha do NULL.** `PlanoDestino.evento` é anulável, e em SQL NULL é distinto de NULL num
> índice único: uma constraint só sobre `(plano, evento, ordem)` deixaria **sem proteção justamente
> o caso mais comum**, o rascunho que o formulário grava. Daí o par parcial. É a inversão nº 2.
>
> **Uma reordenação que eu não tinha achado, e quem achou foi a suíte.**
> `roteiros/tests/test_routing.py:503` trocava as posições no lugar
> (`d0.ordem, d1.ordem = 1, 0` + dois `save`) e a constraint reprovou nos dois bancos. Conferido por
> grep: **produção não tem troca no lugar para este modelo** — o único escritor apaga e recria
> (`roteiro_logic.py:1581`). O atalho era do teste. Reescrito para reordenar como produção, e
> conferido por inversão que a asserção **não** ficou vácua: quebrar
> `mark_stale_when_signature_changed` continua reprovando.
>
> Migrações: `roteiros/0012` e `planos_trabalho/0022`, cada uma com o SQL que localiza as linhas em
> produção (limite 4 do `AGENTS.md`). Medido no banco de desenvolvimento: **0 grupos duplicados**
> nas três consultas.

> **Fatia 2 fechada em 07/08/2026 — os dois que faltavam, junto com os escritores.**
>
> `RoteiroTrecho` e `DiarioBordoTrecho` reaproveitam a linha por `id` de propósito: é o que
> preserva o campo manual (KM do diário, tempo adicional e fonte da rota do trecho). Trocar dois
> de lugar colide no meio do laço. Os dois escritores passaram a ter **dois passos** — um `UPDATE`
> único empurra todas as posições para um bloco livre (`+1.000.000`), o laço traz cada uma de volta
> já no lugar, e o `delete()` do fim leva as que sobraram. Aí a constraint simples é segura.
>
> **Uma colisão que não é troca de lugar.** Três idas (0,1,2) e o retorno em 3; o payload novo traz
> duas idas, e o retorno passa a valer 2 — posição que a terceira ida ainda ocupa, porque o
> `delete()` só roda no fim. Não é reordenação, é encolhimento, e nenhum teste cobria.
>
> **Os dois escritores viraram `@transaction.atomic`, e isso é correção, não zelo.** Nem
> `sincronizar_trechos` nem o caminho de autosave do roteiro abriam transação. Sem ela, uma falha
> entre os dois passos deixa linha estacionada com posição 1.000.001 à vista do usuário, e a
> gravação seguinte não conserta — o primeiro passo soma outro deslocamento em cima. No roteiro
> fecha de quebra um buraco anterior: `roteiro.destinos.all().delete()` fora de transação apaga
> todos os destinos e não os devolve se a recriação falhar.
>
> **Correção à fatia 1: aquele "0 grupos duplicados" vale para um modelo, não para os três.**
> `roteiros_roteirodestino` tem 60 linhas no banco de desenvolvimento e a medição ali é real.
> `planos_trabalho_planodestino` e `planos_trabalho_eventoplano` têm **0 linhas** — a consulta
> devolve zero porque não há o que consultar, não porque está limpo. O mesmo vale para os dois
> modelos desta fatia. É o instrumento cego do `NOVO-49`, e as migrações da fatia 2 dizem isso no
> docstring em vez de contar a medição como evidência. Quem decide é o SQL rodado **em produção**,
> antes do deploy.
>
> Migrações: `roteiros/0013` e `prestacoes_contas/0034`.

### DB-09 ✅ RESOLVIDO · 🟠 Lista de roteiros agrega antes do `LIMIT` · AUD · 2 d

`roteiros/selectors.py:36-47` anota `Count('trechos')` e `Count('destinos')` e usa
`.exclude(destinos_count=0, trechos_count=0, ...)`. `EXPLAIN (ANALYZE, BUFFERS)` com 24.000
roteiros (2.000 na área ativa): `Seq Scan on roteiros_roteirotrecho rows=48000`,
`Seq Scan on roteiros_roteirodestino rows=48000`.

| volume | tempo (1ª medição) | tempo (verificação) |
|---:|---:|---:|
| 2.000 | 23,9 ms | — |
| 8.000 | 37,6 ms | — |
| 24.000 | 127,7 ms | **56,6 ms** (`EXPLAIN`) · 60–64 ms (ORM completo) |

> **Número corrigido pela verificação (05/08):** a segunda medição, com o mesmo volume e o mesmo
> `rows=48.000` nos dois `Seq Scan`, deu **menos da metade** do tempo original. O padrão
> estrutural é o mesmo e está confirmado — a agregação varre as tabelas filhas inteiras
> independentemente do filtro de área, que já reduz `Roteiro` a 2.000 por *index scan*. O ganho
> esperado da correção é menor do que o catálogo prometia.

**Efeito:** o custo cresce com o banco inteiro, não com a área do usuário — cada área paga pelo
volume das outras.
**Correção:** `Exists()` correlacionado, que o Postgres avalia com semi-join e curto-circuito por
linha, permitindo parar no `LIMIT`.

> **Fechado em 07/08/2026. O mecanismo prometido não é o que aconteceu — e o ganho é maior do que
> ele daria.**
>
> A correção é mesmo `~Exists(...)` correlacionado, mas **o `LIMIT` não curto-circuita**: o plano
> depois da troca continua lendo as 6.666 linhas da área e ordenando. O ganho vem de outro lugar —
> o `GroupAggregate` sobre 26.664 linhas desaparece, e com ele a varredura das duas tabelas filhas.
> Buffers 7.817 → 659.
>
> **E o índice de ordenação entrou junto, porque sozinho ele não vale nada.** Medido com 20.000
> roteiros em três áreas, mediana de 7 execuções de `EXPLAIN (ANALYZE, BUFFERS)`, tudo no mesmo
> banco:
>
> | forma | ms | buffers | ganho |
> |---|---:|---:|---:|
> | `Count` + `exclude` (como estava) | 78,99 | 7.817 | — |
> | `Exists` | 26,99 | 659 | 2,9× |
> | **`Exists` + índice `(area, -updated_at)`** | **8,86** | **449** | **8,9×** |
> | `Count` + `exclude` + índice (**controle**) | 78,18 | 7.776 | **1,0×** |
>
> A linha de controle é a que explica o `DB-10`. Lá eu medi este mesmo índice e ele deu 0,9×, e
> concluí que "roteiros não ganha". Estava certo sobre o número e incompleto sobre a causa:
> enquanto o `GroupAggregate` varre as tabelas filhas, ele domina o custo e o `Sort` é troco. Os
> dois são uma unidade — separados, um dá 2,9× e o outro dá 1,0×.
>
> **Na rota inteira, 1,54×**: 975,8 → 633,2 ms, medido em processo único com as duas
> implementações alternadas A-B-A-B sobre o mesmo banco (6 rodadas por lado, 962–1016 ms contra
> 619–668 ms). São 343 ms a menos na lista mais lenta do sistema. O 8,9× é da consulta; a rota
> emite 33.
>
> **O risco desta troca nunca foi desempenho, foi semântica.** `.exclude()` com quatro argumentos é
> `NOT (a E b E c E d)`, não quatro exclusões: basta o roteiro ter **um** dos quatro sinais para
> ficar na lista. Escrever isso como quatro `.exclude()` encadeados — o erro natural de quem lê
> rápido — some com rascunho legítimo da tela, em silêncio. `test_lista_de_roteiros_db09` trava a
> tabela-verdade caso a caso, e a inversão para as quatro exclusões separadas reprova exatamente os
> quatro testes de "só com um sinal".
>
> Migração `roteiros/0015` (só o índice; a troca do `exclude` é código).

### DB-10 ✅ RESOLVIDO · 🟡 Falta índice composto para a ordenação real das listas · AUD · 0,5 d

`OrdemServico.Meta.indexes` está vazio, enquanto `ordens_servico/selectors.py:38` ordena por
`('-ano','-numero')` sobre queryset já recortado por área.

**Ganho medido** com `(area_id, ano DESC, numero DESC)`:

| medição | sem índice | com índice | ganho |
|---|---:|---:|---:|
| primeira | 1,965 ms | 0,067 ms | 29× |
| verificação | 0,600 ms | 0,046 ms | **13×** |

As duas concordam na ordem de grandeza e na direção; a segunda é a mais conservadora e é a que
vale como promessa. Achado extra da verificação: o índice único **parcial** já existente
(`(area_id, ano, numero) WHERE ano IS NOT NULL AND numero IS NOT NULL`) **não pode ser usado pelo
planner** nesta consulta — o que reforça a necessidade do índice proposto em vez de enfraquecê-la.
Ofícios têm situação análoga.

> **Fechado em 07/08/2026, e a última frase do enunciado estava errada: ofícios NÃO têm situação
> análoga.**
>
> O índice entrou só em `OrdemServico`, porque foi o único que a medição sustentou. Antes de
> escrever, varri as oito rotas de lista com `EXPLAIN (ANALYZE, BUFFERS)` sobre 20.000 registros
> por domínio em três áreas (semeadura do `scripts/medir_desempenho.py`), e **cinco** ordenavam em
> memória. Criei o índice análogo em cada uma, no mesmo banco, mediana de 7 execuções dos dois
> lados:
>
> | rota | sem | com | ganho | o que mudou |
> |---|---:|---:|---:|---|
> | `ordens_servico` | 8,65 ms | **0,14 ms** | **64×** | `Limit` para na 20ª linha |
> | `oficios` | 143,2 ms | 120,9 ms | 1,2× | o `Sort` some, o tempo não anda |
> | `planos_trabalho` | 125,9 ms | 126,8 ms | 1,0× | idem |
> | `justificativas` | 24,4 ms | 21,3 ms | 1,1× | e os buffers vão de 664 para 40.384 |
> | `roteiros` | 555,7 ms | 611,7 ms | **0,9×** | continua ordenando, e fica pior |
>
> **Correção ao `roteiros` desta tabela, vinda do `DB-09` no mesmo dia:** o 0,9× estava certo, e a
> conclusão "não ganha" estava incompleta. O índice não pagava **enquanto a agregação estava lá**.
> Tirada a agregação, o mesmo índice leva a consulta de 27,0 ms para 8,9 ms. Ele entrou na fatia do
> `DB-09`, com a linha de controle que prova as duas coisas.
>
> Índice nas outras quatro seria custo de escrita sem ganho de leitura. Em `roteiros` o gargalo é a
> agregação antes do `LIMIT` — o `DB-09`. Em `oficios` e `planos_trabalho` o `Limit` já para em 20
> linhas depois do índice, e ainda assim leva ~130 ms: o custo está em `Nested Loop Left Join` com
> `Join Filter` resolvendo o `select_related`. Registrado como `NOVO-50`, **com a ressalva de que
> pode ser artefato de semeadura** e precisa de medição com tabela de cidades realista.
>
> **O número que o usuário sente é 1,08×, não 64×.** A rota de OS emite 19 consultas; a paginada é
> uma delas. Medida a rota inteira, 9 requisições por lado no mesmo banco: 110,4 ms → 102,6 ms.
> O 64× é da consulta isolada e está aqui porque explica o mecanismo, não porque seja a promessa.
> O que cresce é a diferença: o custo do `top-N heapsort` é proporcional ao tamanho da área
> (6.666 linhas aqui), enquanto o caminho indexado é constante.
>
> Migração `ordens_servico/0013`, com o procedimento de `CREATE INDEX CONCURRENTLY` no docstring
> para o caso de a tabela em produção ser grande (limite 4 do `AGENTS.md`).

### DB-11 🟡 As 80 buscas livres são varredura sequencial · AUD · 3 d

80 ocorrências de `__unaccent__icontains`; extensão `unaccent` instalada, `pg_trgm` ausente;
**0 índices GIN ou trigram** em 390 índices. Prova direta: busca de ofícios com `q="ambi"` sobre
24.000 registros → `Seq Scan`, **35,7 ms** na primeira medição e **31,3 ms** (`EXPLAIN`) /
51,1 ms (ORM completo) na verificação, para devolver 20 cards. Os três números batem na ordem de
grandeza.
**Correção em duas frentes:** (1) quando `q` for dígito, trocar `oficio__numero__icontains` por
`oficio__numero=int(q)` — ganho grande, custo quase zero; (2) `pg_trgm` + índices GIN sobre
expressão nas 4 ou 5 colunas realmente buscadas.

> **Medido em 08/08/2026, e a frente (1) não se sustenta: o ganho é zero.**
>
> A promessa era "ganho grande, custo quase zero". Medi a rota de termos com busca numérica
> (`?q=137`) sobre 20.000 registros em três áreas, em processo único, alternando as duas
> implementações A-B, 6 rodadas por lado:
>
> | forma | mediana |
> |---|---:|
> | `oficio__numero__icontains=q` (como está) | 1.836,5 ms |
> | `oficio__numero=int(q)` quando `q` é dígito | 1.870,5 ms |
> | | **0,98×** |
>
> Indistinguível de ruído. O motivo é estrutural: a mesma consulta tem **12** `unaccent__icontains`
> sobre colunas de texto, e todas varrem sequencialmente. Tirar o cast de **uma** coluna inteira não
> muda o plano — o custo já está pago pelos outros doze. Para comparação, a mesma rota **sem busca**
> responde em ~230 ms; a busca acrescenta ~1,6 s, e não é o inteiro que a paga.
>
> **A frente (1) não foi aplicada.** Ela continua defensável como **semântica** — hoje buscar "1"
> casa com o ofício 100 — mas isso é mudança de comportamento visível ao usuário, e fazê-la em nome
> de um ganho que a medição diz não existir seria trocar o comportamento por nada. Se for feita,
> que seja como correção de busca, com esse enunciado.
>
> **Correção de escopo:** `roteiros/selectors.py:83` (`quantidade_diarias__icontains`) parece o mesmo
> defeito e **não é** — `quantidade_diarias` é `CharField` (`roteiros/models.py:80`), então ali não
> há cast. Os únicos sites de `icontains` sobre coluna inteira são `termos/selectors.py:115` e `:126`.
>
> **A frente (2) também não paga, e agora com o índice sendo usado de verdade.** Medido em
> 08/08/2026, depois de o semeador ganhar dimensão realista (`NOVO-50`):
>
> | | mediana da rota |
> |---|---:|
> | sem `pg_trgm` | 1.807,9 ms |
> | com `pg_trgm` + 5 índices GIN de trigrama | 1.810,1 ms |
> | | **1,00×** |
>
> E não é o instrumento cego desta vez: o `EXPLAIN` direto na coluna mais buscada mostra
> `Bitmap Index Scan on trgm_cadastros_servidor_nome`. **O índice é escolhido e não adianta.**
>
> **A causa, medida.** A busca de termos é *uma* consulta com um `OR` de **15 ramos** aplicado como
> `Filter` **depois** de uma cadeia de `Hash Left Join` que já expandiu 20.000 termos em **59.994
> linhas** (a M2M de servidores entra duas vezes). `Rows Removed by Filter: 59700`, e só então o
> `DISTINCT` reduz para 36. Nenhum índice de coluna serve: um ramo de um `OR` que atravessa várias
> tabelas não pode ser empurrado para um *index scan*.
>
> **E a consulta roda três vezes por requisição** — 636 ms + 636 ms + 459 ms de um total de ~1,8 s.
> `termos/views.py:78` chama `listar_termos` para a página e `:80` chama de novo, dentro de
> `anotar_composicao(...).aggregate(...)`, para os contadores das abas.
>
> **A correção real é outra, e não é índice.** Duas frentes de verdade: (a) não repetir a consulta
> três vezes; (b) trocar o `OR` de 15 ramos pós-join por subconsultas por origem
> (`Q(pk__in=...)`/`Exists()` por tabela), para que cada ramo possa usar o próprio índice — e aí
> `pg_trgm` volta a fazer sentido. O enunciado do `DB-11` precisa ser reescrito nesses termos.
>
> **A pergunta do privilégio era desnecessária:** `CREATE EXTENSION pg_trgm` funciona **sem
> superusuário** desde o PostgreSQL 13, em que ela é *trusted* — e o `unaccent` deste projeto já
> tinha sido criado assim.

### DB-12 ✅ RESOLVIDO (parte do índice) · 🟡 Trilha de auditoria cresce sem limite e encarece toda escrita · AUD · 3 d

`core/audit.py:154-159` conecta `pre_save`/`post_save`/`pre_delete` globalmente para 11 apps.
`capture_before_save` (`:78`) faz um `SELECT` extra em cada save de modelo auditado, e
`capture_after_save` grava snapshot completo em `JSONField`. Não há expurgo nem retenção.

> **Enunciado corrigido pela verificação (05/08), em dois pontos.** O `SELECT` extra só ocorre em
> **UPDATE** (quando `instance.pk` já existe), não em CREATE com PK autoincremento — o custo por
> escrita é menor do que o original sugeria. E a afirmação de que `AuditEvent` tinha "um único
> índice além da pkey, sem suporte para consulta por área ou período" é **falsa**: `\d
> core_auditevent` mostra **10 índices** além da pkey, com coluna única tanto em `area_id`
> (auto-criado pela FK) quanto em `created_at` (`db_index=True` explícito). O que falta é o índice
> **composto** `(area_id, created_at)`, para a consulta que cruza os dois eixos — não suporte
> nenhum.

> **Fechado em 08/08/2026, em duas partes com destinos diferentes.**
>
> **O expurgo saiu do escopo, por decisão do usuário.** Trilha de auditoria de órgão público
> costuma ter retenção regulada, e apagar sem base legal é pior que a tabela crescer. Fica como
> pergunta de produto, não de engenharia.
>
> **O índice entrou, e a medição não o justifica na escala de hoje.** Isso está dito na migração e
> aqui, porque é o tipo de coisa que alguém encontra daqui a um ano e não entende. Com 60.000
> eventos:
>
> | áreas | sem | com | ganho | plano |
> |---:|---:|---:|---:|---|
> | 3 | 0,30 ms | 0,26 ms | 1,1× | ignora o índice novo |
> | 20 | 0,49 ms | 0,47 ms | 1,0× | ignora o índice novo |
> | 100 | 1,51 ms | **0,08 ms** | **18,4×** | `Index Scan using core_audit_area_periodo_idx` |
>
> Com poucas áreas, a varredura para trás pelo índice de `created_at` acha as 100 linhas da página
> quase de imediato e o filtro por área sai de graça. O índice entrou como folga de crescimento: o
> número de áreas em produção **não é observável** do ambiente de desenvolvimento, que tem 3 e as
> três são artefato de teste.
>
> **Achado que muda a leitura do enunciado:** a trilha **não tem leitor em código de aplicação**.
> Nenhuma view, nenhum selector, nenhum relatório. O único consumidor é o admin do Django
> (`core/admin.py`), que filtra por `area` e herda o `ordering` do modelo — é dele a consulta que o
> índice serve. `test_a_trilha_nao_tem_leitor_em_codigo_de_aplicacao` reprova se isso mudar, porque
> aí a análise inteira precisa ser refeita.
>
> Migração `core/0004`, com as duas consultas do limite 4 no docstring — inclusive
> `SELECT COUNT(DISTINCT area_id)`, que é a que diz se o índice vale alguma coisa hoje.

**Efeito:** a tabela cresce sem teto e sem ninguém decidir isso, e a consulta que uma tela de
auditoria realmente faz (uma área, um período) cai em dois índices de coluna única em vez de um
composto.

### DB-13 🟡 A composição da diária é texto livre · AUD · 4 d · risco alto · **fora desta rodada**

`roteiros/models.py:78-82` — `quantidade_diarias = CharField(max_length=120)` guarda uma frase
("2 x 100% + 1 x 30%") ao lado de `valor_diarias`. O `Roteiro` não tem FK nem cópia da linha de
`TabelaDiaria` usada.
**Efeito:** não há como responder por consulta "quantas diárias de 30% foram pagas em 2026" nem
reconciliar um valor pago com a tabela vigente na época.
**Por que fica de fora:** mexer aqui reabre a regra de dinheiro, fechada no ciclo de julho com os
demonstrativos oficiais travados por teste. O ganho é de auditabilidade, não de correção.
Catalogado para uma rodada futura, com `DB-01` como pré-requisito.

---

## PF — Desempenho

### PF-01 ✅ 192 KB de SVG repetido por página de lista · MED · 2–3 d

`/oficios/?aba=atuais` com 20 ofícios: 425 KB de HTML, 12.545 linhas, **378 `<svg>` inline
somando 192 KB (45% da página)**, 854 `<path>`.
Causa: `templates/components/ui/icons/icon.html` — 222 linhas de `{% if %}/{% elif %}` (36 ramos)
que emitem o `<svg>` inteiro a cada inclusão.
**Correção:** folha de símbolos + `<use href="#cv-icon-…">`. O ícone cai de ~500 para ~60 bytes.
Sucessor do `R-02` da Etapa 8, que ficou pendente sem o preço medido.

**Fechado em 06/08.** Medido antes de mexer, na régua do `PF-07` (volume 200): 450,4 KB, 380
`<svg>`, 192,6 KB (43%), 856 `<path>` — o enunciado estava perto. Depois: **315,3 KB**, ícone de
**519 para 118 bytes**, folha de 15,5 KB uma vez por página. As nove rotas da régua tiveram o teto
de `kb_html` baixado.

**Duas ressalvas medidas, que o enunciado não previa e o PR registra:**

1. **Comprimido, o ganho é zero.** `gzip -6` da mesma página: **16,4 KB antes, 16,3 KB depois**.
   380 cópias do mesmo `<svg>` são o caso ideal do compressor. O que encolhe de verdade e o gzip
   não alcança é o DOM: **1.244 nós de forma para 109** (856 `<path>` → 63). O ganho é de parse,
   memória e layout — não de rede.
2. **Página com poucos ícones piora.** A folha custa 15,5 KB fixos: `core:dashboard` foi de 25,8
   para 38,8 KB e `roteiros:index` de 92,3 para 93,7 KB. Os dois tetos subiram de propósito.

Some da lista o modo de falha antigo (nome errado desenhava interrogação): `id` inexistente não
desenha nada e não levanta erro. Coberto por `core/tests/test_folha_de_icones.py`.

### PF-02 🟠 90% do CSS entregue não casa com a página · MED · ver plano de front

Medido no Chromium via CDP: 664–816 KB de CSS entregues por rota, **10,1% a 11,8% casado**. Na
rota `/prestacoes-contas/`, `oficios.css` (106 KB) chega com **0,0%** de uso.
O trabalho está no [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md); aqui fica a métrica de aceite:
**uso acima de 35% por rota** ao fim da reconstrução.

### PF-03 ✅ RESOLVIDO · 🟡 Toda requisição escreve na tabela de sessão · MED · 1–2 d · risco médio

`config/settings/base.py:111` — `SESSION_SAVE_EVERY_REQUEST = True`. Custo fixo de uma requisição
autenticada trivial (`/health/`): **7 queries**, três delas a escrita da sessão
(`BEGIN`/`UPDATE django_session`/`COMMIT`). Toda página, todo XHR de autosave, todo polling de
documento abre transação de escrita.
**Decisão humana necessária:** desligar sem mais nada faz a sessão de 8 h expirar a partir do
login, não da última ação. Alternativas: backend `cached_db` ou renovar só perto do fim.

> **Fechado em 07/08/2026, e as duas alternativas da frase acima eram uma só.**
>
> `cached_db` **ou** renovar perto do fim não resolvia: são as duas juntas. Medido com
> `CaptureQueriesContext`, quatro combinações na mesma rota (painel):
>
> | configuração | consultas | em `django_session` | `BEGIN`/`COMMIT` |
> |---|---:|---:|---:|
> | `db` + `save_every=True` (como estava) | 11 | 2 | 2 |
> | `cached_db` + `save_every=True` | 10 | 1 | 2 |
> | **`cached_db` + `save_every=False`** | **7** | **0** | **0** |
> | `cache` puro + `save_every=True` | 7 | 0 | 0 |
>
> **`cached_db` sozinho economiza 1 de 11.** Ele tira a leitura, não a escrita:
> `cached_db.SessionStore.save()` chama o backend de banco **antes** de gravar no cache. Quem tira
> as outras três é desligar `SESSION_SAVE_EVERY_REQUEST` — e aí volta o defeito que a frase acima
> antecipava, a sessão contando do login. Daí o `RenovacaoDeSessaoMiddleware`, que grava a cada
> `SESSION_RENOVACAO_INTERVALO` (padrão: um oitavo da janela, 1 h em 8 h) em vez de a cada
> requisição. A janela efetiva desliza entre 7 h e 8 h.
>
> `cache` puro chegaria no mesmo 7 sem middleware nenhum e está fora: a sessão viveria só no Redis,
> e um reinício dele deslogaria todo mundo de uma vez.
>
> **A armadilha, que custou o desenho inteiro.** A forma óbvia de renovar é
> `set_expiry(agora + idade)`. Ela funciona **e** escreve em `_session_expiry`, o que faz
> `get_expire_at_browser_close()` devolver `False` (`sessions/backends/base.py:403`): o cookie ganha
> `expires` e **sobrevive ao fechamento do navegador**, anulando
> `SESSION_EXPIRE_AT_BROWSER_CLOSE = True` sem ninguém perceber. O middleware usa uma chave privada
> (`_renovada_em`) justamente para não tocar ali, e a inversão para `set_expiry` reprova os dois
> testes de `ExpiracaoAoFecharNavegadorTests` — um deles mostrando o `expires` concreto no cookie.
>
> **Efeito nas catracas de orçamento de queries:** 16 números desceram, em cinco apps. Em regime o
> corte é **−4** (1 leitura + 1 escrita + 2 comandos de transação). Onde é **−1**, o teste mede a
> **primeira** requisição depois do login: ali `core/tenancy.py:52` grava a área na sessão, que por
> isso é salva de qualquer jeito, e só a leitura é economizada. Os tetos do `PF-07` também desceram,
> em todas as nove rotas.
>
> **Uma nota sobre teste que não prova nada.** A primeira versão do teste de `BEGIN`/`COMMIT`
> passava dos dois jeitos: dentro de `TestCase` tudo já roda numa transação e os comandos viram
> `SAVEPOINT`. Foi movido para `TransactionTestCase`, e só aí passou a reprovar quando
> `SESSION_SAVE_EVERY_REQUEST` volta.

### PF-04 ✅ RESOLVIDO · 🟡 60 menus de ação renderizados para 20 cards · MED · 2–3 d · risco médio

Mesma página: 60 blocos `cv-action-menu` (3 por card) e 200 `cv-action-menu__item` (10 por card),
todos no HTML inicial, quando no máximo um fica aberto por vez.

**Os dois números do enunciado estão certos.** Conferi classe por classe: 60 e 200. Eu tinha dito
"120 e 1.000" no PR do `PF-01` e aqui na sessão — era artefato do meu regex, que casava
`cv-action-menu__item-icon` como se fosse `cv-action-menu__item`. O catálogo não estava
subdimensionado; a medição errada era minha.

**O preço, que o enunciado não tinha** (`oficios:index`, volume 200):

| eixo | antes | depois | |
|---|---|---|---|
| HTML bruto | 315,3 KB | **166,5 KB** | −47% |
| HTML `gzip -6` | 16,3 KB | **13,0 KB** | −20% |
| nós de elemento | 3.636 | **1.676** | −54% |
| tempo de servidor (mediana de 7) | 133,8 ms | **86,1 ms** | −36% |

Diferente do `PF-01`, aqui o ganho de rede é real: menu é marcação com URL e rótulo por registro,
não 380 cópias do mesmo `<svg>`.

**Fechado em 07/08 para Ofícios.** A máquina é genérica: `entity_card_menu.html` passou a emitir só
o gatilho quando o menu tem `src`, e o corpo saiu para `entity_card_menu_body.html`. Sem `src`, o
corpo continua embutido — é essa regra que mantém os seis domínios não migrados funcionando sem
tocar em nenhum deles. `oficios:card_menus` serve os três menus de um card de uma vez.

**`planos_trabalho` e `ordens_servico` migrados em 07/08**, no mesmo desenho:

| rota | bruto | gzip | nós de elemento |
|---|---|---|---|
| `planos_trabalho:index` | 169,5 → **129,0 KB** | 11,1 → 10,2 KB | 1.996 → **1.416** |
| `ordens_servico:index` | 166,8 → **126,7 KB** | 10,7 → 10,0 KB | 1.931 → **1.351** |

Tempo de servidor caiu nos dois, mas **este contêiner não mede tempo de forma confiável**: duas
medições da mesma rota, no mesmo código, deram 57,5 e 75,8 ms; a própria régua do `PF-07` já
registrou 94,9 e 2.464,5 ms para `ordens_servico:index` em execuções diferentes. Bytes e nós são
determinísticos e são o que este catálogo guarda.

**`roteiros` não tem menu nenhum** — `roteiros/presenters.py:240` monta o rodapé só com `edit_url` e
`delete_url`. Os 0 menus medidos em `roteiros:index` não eram falta de dado: não há o que migrar.

**`eventos` migrado em 07/08** — o de maior ganho até aqui, porque tem quatro famílias de menu por
card (rodapé, uma por ofício vinculado, uma por documento e uma por servidor com termo):

| `eventos:index` | antes | depois | |
|---|---|---|---|
| bruto | 416,3 KB | **211,9 KB** | −49% |
| `gzip -6` | 19,4 KB | **14,8 KB** | −24% |
| nós de elemento | 4.681 | **2.081** | −56% |

**`termos` migrado em 07/08** — menu no rodapé mais um por linha (cada servidor e a viatura):

| `termos:index` | antes | depois | |
|---|---|---|---|
| bruto | 317,6 KB | **147,9 KB** | −53% |
| `gzip -6` | 14,9 KB | **11,7 KB** | −21% |
| nós de elemento | 3.824 | **1.439** | −62% |

O card de termo era montado com uma dúzia de argumentos escritos direto em
`termos/views.py`. Com o endpoint passou a haver dois chamadores, e repetir os argumentos faria o
menu servido divergir do embutido em silêncio — inclusive furando o próprio teste de paridade, que
compara contra esse caminho. A montagem foi para `termos/card_builder.py`, e os dois chamam.

`_preview_body.html`, que o enunciado contava entre os menus de `termos`, **não é da lista**: é do
wizard de conferência. Três caixas numa página de formulário não são o defeito.

**`prestacoes_contas` migrado em 07/08 — o `PF-04` está fechado:**

| `prestacoes_contas:index` | antes | depois | |
|---|---|---|---|
| bruto | 383,1 KB | **259,0 KB** | −32% |
| `gzip -6` | 17,4 KB | **14,3 KB** | −18% |
| nós de elemento | 3.479 | **2.179** | −37% |

Era o de maior risco e confirmou dois dos três: o domínio não tinha selector de registro único, e
`PrestacaoServidor.objects` filtra removidos mas **não** recorta por área — quem recorta é
`_filter_servidores_by_area`. `get_servidor_prestacao_by_id` nasceu reusando esse helper, e o teste
de área fica vermelho se o endpoint trocar para o manager cru. O terceiro risco, o menu de WhatsApp
com JS próprio, **não se confirmou**: `prestacoes-diaria-wa.js` já voltava do menu para o gatilho
pelo `id`, porque o overlay sempre moveu o menu para o `<body>` ao abrir. Conferido no navegador nos
dois temas.

### Placar do `PF-04`, seis domínios

| rota | antes | depois | nós |
|---|---|---|---|
| `oficios:index` | 315,3 KB | 166,5 KB | 3.636 → 1.676 |
| `eventos:index` | 416,3 KB | 211,9 KB | 4.681 → 2.081 |
| `termos:index` | 317,6 KB | 147,9 KB | 3.824 → 1.439 |
| `prestacoes_contas:index` | 383,1 KB | 259,0 KB | 3.479 → 2.179 |
| `planos_trabalho:index` | 169,5 KB | 129,0 KB | 1.996 → 1.416 |
| `ordens_servico:index` | 166,8 KB | 126,7 KB | 1.931 → 1.351 |

`roteiros` não entra: não tem menu.

### PF-05 🟡 A lista de Ofícios leva 127 ms no servidor · MED · —

Com 17 queries planas e 20 cards. As outras listas ficam entre 15 e 46 ms. É consequência de
`PF-01` e `PF-04`; existe como **métrica de aceite** deles: abaixo de 40 ms sem subir a contagem
de queries.

### PF-06 ✅ RESOLVIDO (parte) · ⚪ Queries duplicadas em duas rotas · MED · 0,5 d cada

`/usuarios/` emite 2 queries idênticas repetidas; `/prestacoes-contas/`, 1. Sintoma de consulta
refeita em camada diferente.

> **Fechado em 08/08/2026 — e o pior caso não estava no enunciado.**
>
> Varri as **dez** rotas de lista agrupando o SQL por texto **e parâmetros**, com o `traceback` de
> quem emitiu cada uma. O placar antes:
>
> | rota | repetidas | consultas a mais |
> |---|---:|---:|
> | **`roteiros:index`** | 5 | **11** |
> | `eventos:index` | 1 | 1 |
> | `ordens_servico:index` | 1 | 1 |
> | `prestacoes_contas:index` | 1 | 1 |
> | `usuarios:index` | 1 | 1 |
>
> `/usuarios/` tinha **1**, não 2. E `roteiros` — que o enunciado não cita — tinha 11.
>
> **`roteiros` (corrigido):** o presenter monta "Cidade/UF" com `cidade.estado.sigla`
> (`presenters.py:19`) e o selector prefetchava só `destinos__cidade`. Cada acesso ao estado voltava
> ao banco, e como os destinos compartilham estado o **mesmo** `SELECT` saía 3 ou 4 vezes.
> `destinos__cidade__estado` fecha isso: a rota foi de **29 para 14 consultas**, e o teto do `PF-07`
> desceu junto nos dois volumes.
>
> **`usuarios` (corrigido):** o badge da aba recontava `auth_user` depois de o `Paginator` ter
> contado o mesmo conjunto — é a "camada diferente" do enunciado, literal. `contadores_administracao`
> passou a aceitar a contagem já feita, e o `Paginator.count` é `cached_property`, então reaproveitar
> não custa consulta. **Só sem busca:** com filtro os dois números divergem de propósito, e há teste
> para isso — a inversão que reaproveita sempre reprova mostrando o badge com o número do filtro.
>
> **Os três de 1 consulta que ficaram**, com o mecanismo já identificado para quem retomar:
> `usuarios` ainda repete o dropdown de área (dois formulários na mesma página montam o mesmo
> `ModelChoiceField`); `ordens_servico` repete `auth_user` entre o `AuthenticationMiddleware` e
> `core/tenancy.py:26`; `prestacoes_contas` repete um `COUNT` de `prestacaoservidor`
> (`views.py:390`). Nenhum passa de 1 consulta e nenhum é do mesmo formato dos dois corrigidos.
>
> **Um teste meu mediu a coisa errada duas vezes**, e as duas versões estão descritas no arquivo:
> a primeira renderizava **zero cards** (a aba padrão filtra por data futura e a fixture não tinha
> `saida_dt`), então passava com o defeito de volta; a segunda exigia "zero consulta repetida" e
> **reprovava a correção**, porque `destinos__estado` e `destinos__cidade__estado` são dois
> prefetches legítimos que emitem SQL idêntico quando os ids coincidem. A asserção final é sobre
> **crescimento**: o custo de estado não pode aumentar quando a página ganha cards.

### PF-07 ✅ RESOLVIDO · 🟠 Cinco listas nunca foram medidas com volume · MED · 3–4 d

Termos, Prestações, Eventos, Planos de Trabalho, OS e Justificativas responderam com base vazia. O
ciclo antigo registrou que **Termos tinha 54 queries por página** e a correção nunca foi
confirmada.
**Correção:** `scripts/medir_desempenho.py` no repositório, semeando cada domínio em dois volumes
(200 e 20.000), com teto por rota no CI. É a Etapa D1 e vem antes de qualquer otimização.

> **Medido em 05/08, em PostgreSQL, página cheia nos dois volumes.** Contagem de consulta e KB
> viraram teto em `scripts/tetos_desempenho.json`; o passo do CI reprova quem passar.
>
> | rota | linhas/pág. | consultas | KB @200 | KB @20.000 | ms @20.000 |
> |---|---:|---:|---:|---:|---:|
> | `core:dashboard` | — | 11 | 23,8 | 23,8 | 27 |
> | `oficios:index` | 20 | 17 | 450,3 | 451,5 | 1.659 |
> | `roteiros:index` | 15 | 32 | 87,9 | 87,9 | 1.132 |
> | `termos:index` | 15 | **55** | 508,9 | 510,0 | 492 |
> | `eventos:index` | 20 | **296** | 589,9 | 632,9 | 1.096 |
> | `planos_trabalho:index` | 20 | 16 | 216,9 | 258,7 | 555 |
> | `ordens_servico:index` | 20 | 19 | 213,4 | 213,8 | 2.619 |
> | `justificativas:index` | 15 | 17 | 289,1 | **15.295** | **19.726** |
> | `prestacoes_contas:index` | 20 | **138** | 497,3 | 581,5 | 614 |
>
> **O "54 por página" de Termos era real e continua lá** — 55 hoje, e nunca tinha sido confirmado.
> **Prestações está em 138**, número que ninguém tinha medido. **Eventos em 296**, invisível na
> linha de base porque o banco estava vazio. Os três viram `NOVO-08`.
>
> A contagem de consulta é **igual nos dois volumes** em todas as rotas: os N+1 são por linha da
> página, não por tamanho do banco. O que escala com volume é tempo — e o HTML de Justificativas,
> que é o `NOVO-07`.
>
> **Duas correções de rumo minhas, registradas porque mudam a conclusão:** (1) a primeira medição
> rodou em **SQLite** e reportava `planos_trabalho:index` em 22 s — artefato do planejador do
> SQLite; em PostgreSQL são 555 ms, e o script agora **recusa** rodar fora do Postgres. (2) As datas
> semeadas caíam fora da aba padrão (`futuras`), então a página 1 do volume 200 vinha com poucas
> linhas e a diferença entre os volumes media *quantas linhas a página tem*, não o tamanho do banco.

---

## JS — JavaScript

O que o projeto decidiu automatizar, funcionou: **zero** `fetch()` cru, **zero** `alert()`/
`confirm()` nativos, zero duplicação de `debounce`/`escapeHtml`/`normalize`, e o bundle em dia com
as fontes (`build_shell_bundles.py --check` = OK, 25 JS + 24 CSS). Os defeitos abaixo estão todos
**fora** do que o auditor de CI mede.

### JS-01 ✅ RESOLVIDO (9d87cad9) · 🔴 XSS por nome de pasta do Google Drive não escapado · AUD · 0,25 d

`static/js/pages/gdrive_config.js:112` e `:117` — `pasta.name` é interpolado cru dentro de
`aria-label="…"` num template literal atribuído a `item.innerHTML`. **Duas linhas abaixo, na 114,
a mesma variável é escapada** com `window.CV.util.escapeHtml(pasta.name)`: o helper é conhecido no
mesmo bloco e foi esquecido nos dois `aria-label`. O dado vem de `CV.http.fetchJson`
(`:167`, `:189`, `:211`), ou seja, do servidor/Drive.
**Efeito:** nome de pasta com `"` fecha o atributo e injeta HTML/atributo arbitrário (por exemplo
`onmouseover`) executado na página autenticada. Em drive compartilhado, o nome pode ser definido
por qualquer pessoa com escrita na pasta.
**Correção:** as duas interpolações passam por `escapeHtml`, igual à 114.

### JS-02 ✅ RESOLVIDO (9195989) · 🟠 Ciclo de vida existe e 14 de 17 componentes não o implementam · AUD+VER · 3–4 d · risco médio

`static/js/core/app.js:126-159` define `CV.registerEnhancer(name, init, destroy)` e
`CV.registry.destroy(root)`, chamado pelo `MutationObserver` (`:137-141`) quando um nó sai do DOM.
São **17** registros (não 18), dos quais só **3** passam `destroy`: `overlay.js:475`,
`wizard-sticky-header.js:118`, `autosave.js:430` — os outros **14** (não 15) não passam. A
verificação também descartou a hipótese de remoção por outro mecanismo: o único `AbortController`
do projeto está em `autosave.js:114-119` e serve para abortar `fetch`, não para desregistrar
listener de DOM.
Consequência concreta: `picker.js:828` (`document.addEventListener("click", …)`) e
`cv-date-picker.js:787-788,794-795` (`document` `click`/`keydown`, `window` `scroll`/`resize`) são
adicionados por instância e nunca removidos. Quando a linha do formulário é removida
(`location-rows.js:585-586`), o listener global continua vivo referenciando nós desconectados.
Sinal agregado: 365 `addEventListener` contra **13** `removeEventListener` nas fontes.

### JS-03 ✅ RESOLVIDO (d5b1d629, 09/08/2026) · Zero teste automatizado para 17.859 linhas de JS · AUD+VER · 5+ d · risco baixo

Não há `package.json`, runner, nem `*.test.js` no repositório. Os únicos scripts com Playwright
são utilitários de captura de tela, fora de qualquer workflow do `.github`. Toda a lógica
client-side — cálculo de diárias no editor de roteiros, autosave, upload, máscaras, e o `JS-01`
acima — só é validada à mão.

> **Número corrigido pela verificação (05/08): 17.859, não 25.492.** A contagem original somava
> `shell.bundle.js` (7.633 linhas) às fontes que o compõem — dupla contagem do mesmo código. Vale
> o mesmo para o CSS: **43.038** linhas de fonte, não 60.707.

**Resolvido na E1.** O repositório ganhou Vitest + jsdom, 34 testes dos contratos públicos de
`CV.http`, registry (`registerEnhancer`/`destroy`), máscaras e coleções, e cobertura V8 por
arquivo. `.github/js-coverage-floors.json` nasce no medido (linhas: 100%, 27,74%, 96,20% e
91,36%, respectivamente), `scripts/check_js_coverage.mjs` bloqueia regressões e o workflow roda
`npm ci` + `npm test` em Node 22. A prova negativa deliberada reprovou com exit 1.

### JS-04 ✅ RESOLVIDO (1a51341) · 🟠 Cadeia de promise sem `.catch` no editor de roteiros · AUD · 0,5 d

`static/js/pages/roteiros/editor/index.js:790-822` — `scheduleAutoEstimarTrechos()` dispara
`runAutoEstimarTrechos` por `setTimeout` (retorno descartado), e o `pending.reduce(...)` (`:806`)
encadeia `CV.http.fetchJson(...).then(...)` **sem nenhum `.catch` na cadeia inteira**. A função
irmã `calculateDiarias()` (`:1386`), na mesma página, trata o erro corretamente.
**Efeito:** falha de rede na estimativa de distância não avisa nada — os campos ficam vazios e o
erro vira promise rejeitada só visível no console.

### JS-05 ✅ RESOLVIDO (9e7f7c3) · 🟠 O auditor de CI cobre 6 dos ~9 invariantes · AUD+VER · 1–2 d

`scripts/audit_frontend_standards.py:139-176` tem **6** regras JS — `raw_fetch`,
`duplicated_csrf_header`, `duplicated_debounce`, `duplicated_escape_html`, `duplicated_normalize`,
`native_feedback` — e `audit_js()` (`:263-268`) pula `*.bundle.js`. (O enunciado original listava
as seis e somava cinco.) Não existe regra para `innerHTML` com dado dinâmico, listener sem
remoção, `catch` vazio, nem uso de nome de classe CSS como condição de lógica.
**Efeito:** `JS-01`, `JS-02` e `JS-06` podem regredir com o CI verde.

### JS-06 ✅ RESOLVIDO (047090f) · 🟡 Nome de classe CSS usado como condição de lógica em 7 arquivos · AUD+VER · 1 d

`classList.contains("cv-search-picker")` aparece **10 vezes em 7 arquivos** (o enunciado original
dizia 9 arquivos e listava 7):
`components/location-rows.js:16`, `pages/ordens-servico-form.js:119,406`,
`pages/viaturas-form.js:62`, `pages/planos-trabalho-wizard.js:14,151,318`,
`pages/termos-form.js:60`, `pages/servidores-form.js:62`, `pages/configuracoes.js:126`.
**É o defeito que fixa a ordem do plano de front:** renomear `cv-search-picker` na etapa de CSS
quebra o roteamento de foco em 6 páginas, em silêncio.
**Correção:** trocar por atributo dedicado (`data-entity-picker-root`) e deixar a classe só para
estilo — **antes** de qualquer renomeação de CSS.

### JS-07 ✅ RESOLVIDO (E11) · "Fechar ao clicar fora / Esc" reimplementado 4 vezes · AUD · 2 d · risco médio

`components/picker.js:798,828`, `components/cv-date-picker.js:728-731,787-788`,
`cv-select.js:131,179,302,313`, `components/picker-select.js:394,432` — quatro implementações sem
função compartilhada.

> **Detalhe corrigido pela verificação (05/08): estava invertido.** O enunciado dizia que só
> `cv-select.js` fechava em `scroll`/`resize`. Ele não tem **nenhum** listener desses. Quem tem é
> `cv-date-picker.js:794-795` — e mesmo ele apenas **reposiciona** o painel aberto
> (`if (isOpen) positionPanel()`), não o fecha. **Nenhuma das quatro** fecha em scroll ou resize.
> A duplicação continua real; a divergência citada, não.

**Fechamento (11/08/2026).** Depois da remoção de `cv-select.js` na E2, restavam três
implementações vivas. `components/overlay.js` agora expõe `CV.overlay.attachDismiss`, com uma zona
interna que aceita painéis portalizados, predicado de abertura, escopo opcional de Escape e
`destroy()`. `picker.js`, `date-picker.js` e `picker-select.js` usam esse contrato; o calendário
continua apenas reposicionando em `scroll`/`resize`. Testes de runtime cobrem clique externo,
painel portalizado, Escape condicional e desmontagem; o gate JavaScript fechou com **43 testes**.

### JS-08 🟡 11% do bundle global atende menos de 1% das páginas · AUD · 2 d · risco médio

| componente | linhas | templates que usam |
|---|---:|---:|
| `cv-select.js` | 343 | 1 (e só sob `DEBUG`, via `ui_lab2/selects.html`) |
| `components/file-picker.js` | 274 | **≥6** |
| `components/card-toggle.js` | 110 | 1 |
| `components/segment-nav.js` | 64 | **≥4** |
| `components/signature-actions.js` | 59 | 3 |
| `components/extra-download.js` | 27 | 1 |

~877 das 7.633 linhas do bundle, baixadas e analisadas em toda navegação.

> **Coluna corrigida pela verificação (05/08).** A contagem original parava no arquivo que declara
> o seletor e não seguia a indireção de `{% include %}` por variável. `segment-nav.js` chega a
> pelo menos 4 templates de produção via `band_tabs_template` (`usuarios/index.html`,
> `usuarios/areas/index.html`, `cadastros/configuracao/form.html`, `termos/index.html`), e
> `file-picker.js` a pelo menos 6 via `attach_signed_modal_enabled` (`list_page_standard.html`,
> `list_page_cards.html`, `oficios/wizard_documentos.html`, `eventos/detalhe.html`,
> `termos/form.html`, `prestacoes_contas/documentos_form.html`). Os outros quatro conferem.
> **Consequência:** o ganho de separar o bundle é menor do que o catálogo prometia, e o corte tem
> que ser decidido por componente, não pelo bloco inteiro.

### JS-09 ✅ RESOLVIDO (E11) · Tela de espera de documento carregava o bundle inteiro para usar 3,3 KB · AUD · 0,5 d

`templates/documentos/geracao_aguarde_embedded.html:27` é um documento autônomo (não estende
`base.html`) que carrega `shell.bundle.js` inteiro. O único uso de `CV.*` na tela é
`CV.http.fetchJson` (`document-generation-wait.js:10`), definido em `core/http.js` (116 linhas).
A tela só mostra um spinner e faz polling.

**Fechado na E11.** A tela embutida agora entrega `core/http.js` diretamente antes de
`document-generation-wait.js`; `shell.bundle.js` não participa mais desse documento autônomo. Na
medição atual, o JavaScript específico da rota caiu de **283.282 para 4.255 bytes** (−279.027;
**−98,5%**), preservando o contrato `CV.http.fetchJson`. O teste da resposta 202 trava presença,
ausência e ordem dos dois scripts para impedir a regressão silenciosa.

### JS-10 ✅ RESOLVIDO (E11) · Modularização do editor de roteiros é fachada · AUD · 0,25 d ou 3+ d

`static/js/pages/roteiros/editor/state.js`, `retorno.js` e `diarias.js` têm **3 linhas cada** e
devolvem só `{ name: 'state' }` etc. São importados e instanciados em `index.js:11-20`, e os
objetos não são usados em mais lugar nenhum. A lógica real continua nas 1.848 linhas de `index.js`
(81% do cluster).
**Efeito:** a estrutura de arquivos mente. Quem procurar a regra de diárias em `diarias.js` não
acha.
**Decisão:** completar a extração (3+ dias, depois de `BE-13`) ou remover os stubs (0,25 d).

**Fechamento (11/08/2026).** Escolhida a poda de comportamento nulo: o grep de repositório inteiro
confirmou que os três objetos só eram publicados em `window.CV.roteiros.modules` e não tinham
consumidor. Os imports, as três propriedades e os arquivos `state.js`, `retorno.js` e `diarias.js`
foram removidos. Os módulos reais `trechos.js` e `mapa.js`, inclusive o bootstrap do mapa, foram
preservados. O contrato de namespace trava a ausência dos stubs; **33 testes focados** ficaram
verdes.

### JS-11 ✅ RESOLVIDO (f9e3f72) · ⚪ Máscara de CEP duplicada e `onlyDigits` em 4 cópias · AUD · 0,25 d

`pages/configuracoes.js:6-9` reimplementa `maskCep` byte a byte em vez de chamar
`CV.masks.format(value, 'cep')`. `onlyDigits` está reimplementado em `roteiros_wizard.js:2`,
`components/document-number-field.js:2`, `components/masks.js:9` e `pages/configuracoes.js:2`.

### JS-12 ✅ RESOLVIDO (bebb379) · ⚪ `CV.registry` e `CV.componentRegistry` são duas definições redundantes · ~~AUD~~ VER · 0,25 d

> **Enunciado original REFUTADO pela verificação (05/08).** Ele dizia que `core/app.js:148-159`
> atribuía os dois nomes **ao mesmo literal**. O cético carregou o `app.js` real no Node e testou
> em runtime: `CV.registry === CV.componentRegistry` devolve **`false`**.

São **dois literais de objeto distintos** (`app.js:148-153` e `:154-159`). Três das quatro
propriedades — `destroy`, `enhance`, `register` — apontam para as mesmas funções
(`registry.destroy === componentRegistry.destroy` → `true`), mas `registered` é uma função anônima
declarada duas vezes, com identidades diferentes.

**O defeito existe, com outra causa:** não é aliasing de um objeto, é duplicação de definição —
uma API pública redundante que pode divergir com o tempo, e já divergiu numa das quatro
propriedades.

---

## HT — Templates, componentes e acessibilidade

Os 96 componentes em `templates/components/` estão mais consolidados do que se supunha:
`page_header.html` com 28 usos, `entity_card.html` em 7 apps, `pagination.html` com `aria-current`
e `aria-live`, e **zero ORM disparado por template**. Os defeitos estão em acessibilidade de
formulário.

### HT-01 ✅ RESOLVIDO · 🔴 Foco de teclado invisível em todo campo do sistema · AUD · 1–2 d

`static/css/base.css:80-87` remove `outline` de `input:focus`, `input:focus-visible`,
`select:focus`, `select:focus-visible`, `textarea:focus` e `textarea:focus-visible`, com o
comentário `/* Campos: sem chrome de hover/focus (temporário). */` e **sem substituto na regra
base**. Repetido em `static/css/forms.css:986-988` (`.main-form-panel .form-control`, presente em
21 templates) e em `static/css/auth.css:208-210` (`.auth-field-input` — os campos de usuário e
senha da **tela de login**, sem regra alternativa em todo o arquivo).
`theme-dark-components.css:875-880` e `roteiros.css:1006-1012` reforçam com
`border-color: transparent !important` no foco de `.cv-field__control`, a classe emitida por
`WidgetStyle.FIELD_CONTROL` (`core/forms/widgets.py:19`) para a maioria dos campos.
`grep -rn "outline:\s*none\|outline:\s*0\b" static/css` → **186** ocorrências.

**Efeito:** quem navega por teclado não vê em qual campo está, em nenhum formulário do sistema,
começando pelo login. Falha WCAG 2.4.7 (AA).
**Correção:** remover as três regras sem substituto e definir `:focus-visible` consistente
(`box-shadow: 0 0 0 2px var(--color-focus-ring)`), reaproveitando o padrão que já existe para
`button:focus-visible, a:focus-visible` em `base.css:49-52`.

> **RESOLVIDO em 06/08/2026.** Medido no navegador, no campo de usuário do login, com foco de
> teclado:
>
> | | antes (`main`) | depois |
> |---|---|---|
> | tema claro | `outline: none 0px` | `outline: 1px solid rgb(21, 91, 154)` offset 2px |
> | tema escuro | `outline: none 0px` | `outline: 1px solid rgb(224, 171, 60)` offset 2px |
>
> **A varredura corrigiu o enunciado: eram 52 blocos, não 3.** O catálogo nomeava os três que
> tinha olhado. Uma análise declaração a declaração — regex por bloco erra, porque `\s*` retrocede
> e faz `outline: none` parecer anel declarado — achou **52** blocos que apagam o foco de campo sem
> pôr nada no lugar. Corrigir 52 daria um diff enorme e ainda deixaria o 53 nascer amanhã.
>
> **A correção é um piso, não uma varredura.** Uma regra de `:focus-visible` com `!important`:
> indicador de foco é chão de acessibilidade, e nenhum componente deveria poder removê-lo. Três
> decisões que não são óbvias:
>
> 1. **`outline`, não `box-shadow`** — os dois blocos que apagam foco com `!important`
>    (`roteiros.css`, `theme-dark-components.css`) zeram `box-shadow` e `border-color` e **não**
>    tocam em `outline`. O anel passa por cima deles sem briga de especificidade.
> 2. **`outline-offset` é requisito, não enfeite** — no escuro o âmbar dá 2,07:1 contra a borda do
>    campo e reprovaria colado nela; afastado, quem fica ao lado é o fundo (7,76:1).
> 3. **`button/a:focus-visible` também estava errado** — usava `rgba(37, 99, 168, 0.45)` fixo, que
>    no tema escuro dá **2,64:1**, reprovando os 3:1 mesmo antes de compor o alfa. Passou a usar o
>    token, que troca com o tema.
>
> **Um erro meu que só o navegador pegou:** a primeira versão pôs o piso só em `base.css` e os
> testes de contrato passaram — mas o login continuou sem anel, porque **aquela tela não carrega
> `base.css`**. Era justamente a tela que este defeito destaca. O piso foi duplicado em `auth.css`,
> com comentário dizendo quando sai.
>
> Catraca nova: `scripts/audit_foco_visivel.py --max 44` (47 → 44 medido com a mesma régua nos dois
> lados). Ela **não** conta `:focus:not(:focus-visible)`, que é o idioma correto — mouse sem anel,
> teclado com.
>
> **Espessura: 1px, por decisão do usuário.** Atende WCAG 2.4.7 (AA), que é o critério citado aqui.
> Deixa de atender 2.4.13 Aparência do Foco, que pede perímetro de 2px e é **AAA**.


### HT-11 ✅ RESOLVIDO · 🔴 Campos de formulário renderizados sem nome acessível · AUD+MED · 1,5 d

`templates/components/ui/forms/field.html` só emite o `<label>` quando a classe do widget **não**
contém `cv-search-picker__native`:

```
{% if "cv-search-picker__native" not in classe_do_widget %}
  <label class="app-form-label cv-field__label" for="{{ field.id_for_label }}">…</label>
{% endif %}
```

A aposta é que o JS transfere o rótulo — e ele transfere um rótulo que não existe.
`WidgetStyle.SEARCH_PICKER_NATIVE` é declarado em 8 arquivos de forms (`cadastros`, `eventos`,
`usuarios`, `termos`, `planos_trabalho`, `ordens_servico`, `core/forms/__init__.py`,
`core/forms/widgets.py`), com 21 ocorrências.

**Medido no navegador**, contando **apenas o controle que o usuário de teclado alcança**:

| tela | campos sem nome acessível |
|---|---:|
| `/cadastros/servidores/novo/` | **1** (`.cv-search-picker__input` de "Unidade") |
| `/termos/novo/` | **4** |
| `/oficios/novo/` | 0 |

> **Contagem corrigida pela verificação (05/08).** A primeira medição deu 3 e 9, e estava
> inflada: contava nós do DOM em vez de controles expostos. `#id_cargo` é um *decoy* — tem
> `aria-hidden="true"` e `tabindex="-1"`, e o controle real é o `<button aria-labelledby>` gerado
> por `picker-select.js:70-90`, **que tem nome**. `#id_unidade`, `#id_oficio`, `#id_servidores` e
> `#id_viatura` estão em `display:none`, fora da árvore de acessibilidade e do *tab order*. E
> `id_oficio_busca` tem `aria-label="Buscar ofício vinculado"` no template. O mecanismo continua
> real, e a causa é mais precisa do que a original: `picker.js:154` cria um
> `<div class="cv-search-picker__label">` que **nunca** é associado ao input por `aria-labelledby`
> nem por `for`.

**Efeito:** leitor de tela anuncia "caixa de combinação" sem dizer de quê. Falha WCAG 4.1.2 (A) —
severidade maior que a do `HT-02`, porque aqui não há nem o rótulo visual associado.

> **RESOLVIDO em 06/08/2026.** Medido no navegador, contando só controle que o teclado alcança:
> `/cadastros/servidores/novo/` e `/termos/novo/` foram a **0** campos sem nome acessível, nos dois
> temas.
>
> A causa era a que a verificação de 05/08 já tinha apontado, e a correção tem duas pontas:
>
> - **`picker.js`** passou a nomear o input que cria, por três fontes em ordem: o rótulo que o
>   próprio picker desenha, o `<label for>` da tela, e o `placeholder` como último recurso. O
>   `<div class="cv-search-picker__label">` *parecia* rótulo, mas `<div>` não rotula nada sem
>   `aria-labelledby`.
> - **`field.html`** parou de omitir o `<label>` dos widgets `cv-search-picker__native` e passou a
>   emiti-lo como `.sr-only`: fora da tela, dentro da árvore de acessibilidade. É de lá que o
>   `picker.js` tira o nome quando o picker não desenha o dele.
>
> A dica (`data-picker-hint`) também era só texto ao lado; virou `aria-describedby` — descrição,
> lida depois do nome e não no lugar dele.


### HT-12 ✅ RESOLVIDO · 🟠 `help_text` declarado no form nunca chega à tela · AUD · 0,5 d

`templates/components/ui/forms/field.html:45` — `{% if help_text %}` imprime **apenas o parâmetro
do include**, nunca `field.help_text`. Forms de produção que declaram `help_text` no campo não o
exibem em lugar nenhum.

> **RESOLVIDO em 07/08/2026, junto do `HT-02`** — são o mesmo defeito por dois lados. Medida a
> superfície: **29 campos em 17 forms** declaram `help_text` e **2 chamadores** (de 154 includes de
> `field.html`) passam o parâmetro. Ou seja, 29 textos escritos e nenhum na tela.
>
> A ajuda passa a sair de `help_text|default:field.help_text` — o parâmetro continua vencendo,
> porque os dois chamadores que o usam trocam a frase por uma da tela deles.
>
> **`|safe`, e não por preguiça.** `UsuarioAreaCreationForm.password1.help_text` é a lista de
> regras de senha do próprio Django, em `<ul><li>`. Sem `|safe` a tela do administrador passaria a
> mostrar a marcação como texto — é o mesmo `|safe` de `django/forms/div.html`, e `help_text` é
> sempre texto de desenvolvedor, nunca de usuário.
>
> **Dois campos ficaram de fora, por motivo diferente e verificado:**
> `PresetAtividadesQuickAddForm.atividades` é `CheckboxSelectMultiple`, e o Django não emite
> `aria-describedby` para widget com `use_fieldset=True` (`boundfield.py:294`) — o texto já está na
> tela como descrição do painel, escrito à mão em `presets/partials/_quick_add_fields.html:12`.
> `TabelaDiariaForm.vigencia_inicio` e `OficioTransporteForm.motorista_oficio_referencia` são
> `HiddenInput`, e o Django pula campo escondido pelo mesmo motivo. Nenhum dos três precisa de
> guarda em `field.html`: **nenhum passa por lá**, e guarda que ninguém exercita já custou caro
> nesta etapa.

### HT-13 ✅ RESOLVIDO · 🟠 `docs/DATA_ATTRIBUTES_JS.md` descreve um contrato que não existe mais · AUD · 0,5 d

O documento cita 4 arquivos JS que já foram removidos e 3 atributos com zero ocorrências no
repositório, enquanto o contrato realmente em uso (`data-entity-picker`, `data-inline-create-*`)
não está documentado. É um `PADRAO_*` que aponta para o passado — quem seguir, erra.

> **RESOLVIDO em 07/08/2026, e o defeito era maior do que o enunciado.** Os 4 arquivos conferem
> (`cv-custom-select.js`, `cv-search-picker.js`, `app-multiselect.js`, `filterable-multiselect.js`).
> Os atributos mortos eram **7**, não 3 — entram também `quick-add-panel`, `data-cv-select-bound`,
> `data-cv-search-picker-ready` e `data-app-multiselect-ready`. E a cobertura era de **19%**: 57
> atributos citados para **298** procurados por JS no repositório.
>
> **Rescrever não resolvia sozinho — foi assim que ele apodreceu da primeira vez.** O que fecha o
> defeito é `core/tests/test_contrato_data_attributes.py`, que confere **nos dois sentidos**:
> tudo que o documento cita existe no código, e todo atributo que um **motor compartilhado** procura
> no DOM está citado. A segunda regra é a que se mantém sozinha: atributo novo em
> `static/js/components/` ou `static/js/core/` reprova a suíte até ser documentado.
>
> **A fronteira é medida, não afirmada.** O documento cobre os motores compartilhados (161
> atributos) e declara não indexar os de uma página só — **137**, cada um com um único consumidor.
> Esse número está no texto e é conferido por teste: número solto em documentação é exatamente o que
> apodrece.
>
> **O parágrafo que lista os removidos fica fora da varredura**, porque cita os mortos **como**
> mortos. Para a exceção não virar porta dos fundos, o que ele contém também é afirmado: os nomes
> precisam estar lá e **não** podem aparecer no corpo vivo.
>
> **Três nomes que eu inventei, pegos pela própria trava:** a primeira versão do teste expandia
> sufixos abreviados do documento (`-trigger`, `-form`) e produziu `data-file-selection-list-item`,
> `data-cv-filter-dropdown-value` e `data-segment-nav`, nenhum existente. A saída foi tirar a
> esperteza do teste e pôr o nome cheio no documento — referência que não dá para grepar não é
> referência.

### HT-14 ✅ RESOLVIDO (E5, 10/08/2026) · 28% dos includes não usavam `only` · AUD · 2 d

Componentes leem contexto ambiente do chamador em vez de receber só o que declaram. É como um
componente passa a depender de uma variável que o chamador tem por acaso — e quebra quando outro
chamador não tem.

> **Remedido em 09/08: são 275 de 946 includes** (29%), não um percentual solto —
> `grep -rho '{%\s*include' templates` contra a variante que termina em `only`.
>
> **E o enunciado descreve o sintoma, não a causa.** A causa é que nenhum componente **declara**
> quais parâmetros aceita, então não há contrato para o `only` proteger — é o `NOVO-68`. Por
> decisão do dono, os dois fecham juntos pela adoção do `django-cotton`, que passa só o atributo
> declarado: o `only` deixa de ser disciplina de quem escreve o `{% include %}` e vira o
> comportamento do motor. **Fila:** etapa E5 do
> [`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md).

**Resolvido na E5.** Os 868 call sites de componentes agora usam tags Cotton com contratos
explícitos e isolamento habilitado. Os 190 includes Django que restaram são parciais de aplicação
ou conteúdo de slot; todos declaram o contexto e usam `only`. A regra `include_without_only` do
auditor transforma o zero atual em catraca de CI.

### HT-15 ✅ RESOLVIDO (58776bcc) · Bloco `cv-itinerary` duplicado em 5 apps · AUD · 1,5 d

Idêntico byte a byte entre dois deles. Mesma família do `HT-08`: markup de `cv-icon-btn` e
`cv-action-menu__item` também reescrito à mão em templates de app.

### HT-02 ✅ RESOLVIDO · 🟠 Erro de campo sem associação programática · AUD · 2–3 d · risco médio

`templates/components/ui/feedback/field_error.html:1` renderiza
`<p class="field-error app-form-error">{{ errors|striptags }}</p>` — sem `id`, sem `role`, sem
atributo nenhum. `templates/components/ui/forms/_field_control.html:24` renderiza o widget cru sem
`aria-describedby`/`aria-invalid`. `grep -rn "aria-invalid"` no repositório inteiro: **zero**.
Esse caminho é o único usado pelos formulários reais: `field.html` tem **152 inclusões**.

**O mecanismo é mais barato de consertar do que parece.** O Django 5.2 já emite
`aria-describedby="id_X_error"` e `id_X_helptext` no widget de todo campo com erro ou `help_text`.
Falta o outro lado: **nenhum componente de erro ou de ajuda emite esses `id`**. A mensagem existe
na tela e o ponteiro do navegador aponta para o vazio.

O contraexemplo está no próprio repositório: `templates/components/ui/forms/file_picker.html:13,67`
já faz certo (`aria-describedby="{{ field_id }}-error"` no controle e
`<p id="…-error" role="alert">` na mensagem) — só não foi generalizado. O componente tem 2 usos.

**Efeito:** leitor de tela que recebe foco num campo inválido não é informado do erro.
**Correção:** dar aos componentes de erro e de ajuda os `id` que o Django já referencia
(`{{ field.auto_id }}_error`, `{{ field.auto_id }}_helptext`) e acrescentar `role="alert"`. Feito
assim, não é preciso tocar em `_field_control.html`.

> **RESOLVIDO em 07/08/2026, e o enunciado estava certo em tudo, inclusive na parte otimista:**
> `_field_control.html` não foi tocado. Os quatro ramos dele (multiselect, search-picker, select,
> widget cru) e o do checkbox saem todos por `{{ field.as_widget }}`, e o Django 5.2 já põe
> `aria-invalid="true"` e `aria-describedby` sozinho (`boundfield.py:290-310`). O que faltava era só
> a âncora do outro lado.
>
> **O `field_id` é o `auto_id`, sem sufixo, e o sufixo é escrito pelo componente** — ele é ditado
> pelo Django, não escolhido por nós. Foram **39 chamadores** que passaram a informá-lo; os que
> renderizam `non_field_errors` ficaram de fora **de propósito**, porque não têm campo, e são o
> `HT-03`.
>
> **A cobertura dos 39 é estática, e teve de ser.** Teste de componente prova o componente; quem
> escreve o `id` é o chamador. `ContratoDosChamadoresTests` varre os `include` nos templates e exige
> `field_id` de todo `errors=X.errors`, proíbe em todo `non_field_errors`, e proíbe string literal
> em `errors=`. Pega o quadragésimo chamador antes de ele existir.
>
> **Dois achados que não estavam no enunciado:**
>
> 1. **`{{ errors|striptags }}` grudava mensagens.** `striptags` era aplicado ao `<ul>` inteiro da
>    `ErrorList` e removia as tags **sem pôr nada no lugar**: dois validadores falhando no mesmo
>    campo saíam como `…ele possui 3).Só dígitos.`. Trocado por `join:" "`. O efeito colateral é o
>    motivo de `ui_lab2/feedback.html` ter mudado: ele passava uma **string** em `errors=`, e `join`
>    sobre string separa caractere por caractere. Agora usa um `BoundField` de verdade — que é o que
>    a demonstração deveria mostrar desde sempre.
> 2. **`card_toggle.html` reescrevia o `<p>` de erro por conta própria.** A primeira versão desta
>    correção deu `id` e `role` à cópia — e **remover qualquer um dos dois não reprovava teste
>    nenhum** (décima e décima primeira vez nesta etapa que uma edição minha não era atribuível). A
>    saída não foi cobrir a cópia: foi apagá-la. O checkbox agora inclui `field_error.html` como
>    todo mundo, e as três propriedades passaram a ser cobertas pelas travas do componente.
>
> **Fora de alcance, medido e nomeado:** `PresetAtividadesQuickAddForm.atividades` é
> `CheckboxSelectMultiple`, e o Django **não** emite `aria-describedby` para widget com
> `use_fieldset=True` — associar ali exige `<fieldset>`/`<legend>`, que é remodelar o painel, não
> ajustar um componente. Não há ponteiro quebrado (o Django não emite nenhum) e o texto está na
> tela; fica registrado como `NOVO-41`.

### HT-03 ✅ RESOLVIDO · 🟠 Sem padrão único para erro de formulário inteiro · AUD · 2 d

`templates/components/ui/feedback/form_errors.html` — o componente feito para isso, que já usa
`alert.html` com `role="alert"` — tem **zero inclusões em produção**; só aparece em
`dev/ui_lab/feedback.html` e `ui_lab2/feedback.html`. No lugar dele coexistem quatro padrões:
11 templates reaproveitam `field_error.html` (sem `role="alert"`) para `form.non_field_errors`
(`cadastros/servidores/form.html:13`, `usuarios/form.html:16`, `termos/form.html:35`,
`ordens_servico/form.html:23`, `eventos/includes/_evento_form_sections.html:2`,
`planos_trabalho/wizard_identificacao.html:14`,
`prestacoes_contas/relatorio_tecnico_form.html:28`, entre outros);
`roteiros/includes/_roteiro_editor.html:40` escreve `<div class="alert alert-danger">` à mão
(classes Bootstrap legadas, fora do design system); `core/login.html:47` usa um quarto padrão,
`auth-error`.
**Efeito:** na maioria dos casos o erro de submissão não é anunciado ao recarregar a página.

> **RESOLVIDO em 07/08/2026.** São **20 chamadores** agora: os 18 que reaproveitavam
> `field_error.html`, o editor de roteiros que escrevia `alert alert-danger py-2` à mão, e o painel
> de cadastro rápido — que **não tinha padrão nenhum**, nem o certo nem um dos quatro errados. Erro
> de `clean()` num quick-add simplesmente não aparecia na tela.
>
> **O componente "certo" jogava a mensagem fora.** Ele sempre imprimia "Revise os campos
> destacados", mesmo com `non_field_errors` de conteúdo — "As duas senhas não conferem", "Já existe
> viatura com esta placa nesta área". Adotá-lo como estava teria **perdido informação em 18 telas**,
> que é o oposto de padronizar. Agora ele mostra o texto real e cai na frase genérica só quando não
> há o que dizer além dela.
>
> **`role="alert"` não fecha o efeito do enunciado, e por isso tem foco.** Região viva anuncia
> *mudança*, e o resumo já está no HTML quando a página carrega — o comportamento varia por leitor
> de tela. `fields-init.js` move o foco para o resumo (`tabindex="-1"`), uma vez por carga de
> página. A trava de "uma vez" não é detalhe: `init` roda de novo a cada re-render parcial, e roubar
> o foco no meio da digitação trocaria um defeito de acessibilidade por outro pior.
>
> **Três coisas que só apareceram por medição, e nenhuma estava no enunciado:**
>
> 1. **Os dois chamadores de formset teriam dado 500.** A primeira versão resolvia a origem com
>    `errors|default:form.non_field_errors` — e variável usada como **argumento de filtro** não cai
>    no `string_if_invalid` como a principal: levanta `VariableDoesNotExist`, e o `{% include %}`
>    propaga. Diário de bordo e efetivo do plano passam `errors` **sem** `form`. Viraram dois ramos.
> 2. **`formset.errors` é verdadeiro sem erro nenhum** — lista com um dict por formulário, e lista
>    de dicts vazios é `True`. Usá-la de guarda faria toda tela com formset abrir com faixa
>    vermelha.
> 3. **O painel de cadastro rápido cortava o que passasse do teto.** Com o resumo, medido em
>    `/usuarios/`: `scrollHeight` 696 contra `clientHeight` 640 — 56 px sumindo em silêncio, e o que
>    sumia era o bloco "Primeiro acesso" inteiro. `max-height` + `overflow: hidden` existe para a
>    animação; virou `overflow-y: auto`, em **duas** folhas, porque `list-header.css` redeclara
>    `overflow: hidden` com a mesma especificidade e vem depois no bundle (`UI-04`).
>
> **O login fica de fora, e é o `HT-09`.** `core/login.html` é HTML autônomo: não estende
> `base.html`, não carrega `base.css` nem o bundle do shell. Sem `fields-init.js` não há foco, e a
> faixa do design system entraria sem o CSS que a pinta. A tela inteira é do `HT-09`.
>
> **Uma exceção nomeada e conferida:** `roteiros/partials/roteiro/_diarias_body.html` mantém
> `alert alert-danger` — não é erro de formulário, é container de status preenchido por JS, e o
> editor escreve `errEl.textContent` direto no elemento, o que apagaria a estrutura interna do
> `alert.html`. Converter exige mexer no JS do editor: é o `BE-13`.

### HT-04 🟠 `base.html` carrega ~153 KB de JS de domínio em toda página · AUD · 2–3 d · risco médio

`templates/base.html:11,44` inclui `shell.bundle.css` (524.763 B) e `shell.bundle.js` (269.990 B)
incondicionalmente. A lista `SHELL_JS` (`scripts/build_shell_bundles.py:24-73`) traz
`cv-date-picker.js` (31.815 B), `picker.js` (36.391 B), `picker-select.js` (18.671 B),
`location-rows.js` (26.241 B), `attach-signed-modal.js` (11.544 B), `file-picker.js` (10.482 B),
`document-source.js` (6.888 B), `signature-actions.js`, `document-download.js`,
`extra-download.js`, `wizard-sticky-header.js` — **≈153 KB, 57% do bundle JS**, exclusivos dos
wizards de ofício/roteiro/termo/prestação. `SHELL_CSS` soma ≈37 KB na mesma situação.
**Efeito:** o dashboard e a tela de cargos pagam o parse do JS de assinatura eletrônica.
**Correção:** separar bundle "núcleo" de bundle "documentos", usando os `{% block extra_js %}`/
`{% block extra_css %}` que `base.html:12-13,45` já tem. Mitigar a regressão silenciosa (template
que esquece de declarar) com regra no auditor ou teste de fumaça por tela.

### HT-05 ✅ RESOLVIDO · 🟡 `empty_state.html` quebra a ordem de headings · AUD+MED · 0,5 d

> **Divergência resolvida por medição.** Uma segunda auditoria independente concluiu "zero salto de
> nível de heading em 412 templates de produção" — análise **estática, por template**, que não
> enxerga a composição da página. Remedi no navegador, e o salto existe em **5 de 5** rotas
> testadas: `/oficios/`, `/roteiros/`, `/termos/`, `/eventos/` e `/cadastros/servidores/`, todas
> com a sequência `H1 → H3 (Nenhum registro cadastrado) → H2, H2…`. Vale a medição ao vivo.

`templates/components/ui/feedback/empty_state.html:3` fixa `<h3>`, sem parâmetro `heading_level` —
padrão que já existe em `components/form/card.html`. Medido com navegador em `/oficios/`:
`H1 → H3 → H2, H2, H2`. Reproduzido em `/eventos/`, `/roteiros/`, `/termos/`,
`/prestacoes-contas/`, `/ordens-servico/`, `/planos-trabalho/`, `/cadastros/servidores/`,
`/cadastros/viaturas/`.
**Efeito:** navegação por headings pula do nível 1 para o 3 sempre que a lista está vazia —
instalação nova, filtro sem resultado. SC 1.3.1 / 2.4.6.

> **RESOLVIDO em 07/08/2026, e o número do enunciado subiu: o pulo era 10 de 10, não 9.** A décima
> é `/justificativas/`, e ela precisava de correção **diferente** das outras nove — foi por isso que
> a auditoria original a deixou de fora. As nove saem com o `<h3>` do estado vazio virando `<h2>`;
> a de justificativas tem, acima da lista, um painel de cadastro rápido cujos dois `form_block`
> pediam `heading_level=3` — filhos diretos do `<h1>` da página, sem heading intermediário. O
> componente só sabia renderizar 3 e 4, então **aquela tela não tinha como não pular nível** por
> mais que o estado vazio fosse corrigido. `form_block.html` ganhou ramo `h2`, **aditivo**: o
> default segue `h4` e nenhum dos ~40 chamadores existentes muda de nível.
>
> **Sem parâmetro `heading_level` no estado vazio, e a decisão veio da inversão.** A primeira versão
> tinha um, com default 2 e ramos 3/4/5, repassado por `list_empty.html`. Tirar o repasse não
> reprovou teste nenhum: nenhum dos sete chamadores passa nível. Foi a **nona** vez nesta etapa que
> um teste meu passava dos dois jeitos, e a lição é a mesma — parâmetro que ninguém exercita parece
> contrato e não é. `list_empty.html` voltou a ser idêntico ao `main`. Quando aparecer chamador
> aninhado sob heading próprio, ele acrescenta o parâmetro junto com o caso que o prova.
>
> **A trava é sobre o HTML renderizado, não sobre o template.** `core/tests/test_ordem_de_headings.py`
> abre as dez listas vazias e derruba a regra "nenhum degrau perdido" na sequência de `<h1>`…`<h6>`
> de cada resposta. É exatamente a diferença que o box acima registra: a auditoria estática, por
> template, não enxerga a composição da página e concluiu "zero salto em 412 templates". Tela nova
> com estado vazio entra na varredura sozinha.
>
> Chamador sem `title` não renderiza heading nenhum — é o caso dos dois usos `variant="compact"`
> (perfil e histórico de diárias), fora deste defeito por construção.

### HT-06 ✅ RESOLVIDO · 🟡 Dez a quatorze componentes mortos · AUD · 0,5–1 d

**Duas auditorias independentes contaram diferente: 10 e 14 de 96.** A divergência é de critério —
uma contou como vivo o componente alcançável a partir de página de laboratório sob `DEBUG`, a
outra não. A prova por arquivo, exigida pelo `AGENTS.md` §3.6, resolve caso a caso no PR.
O agravante que só a segunda viu: **três dos mortos são citados como canônicos em
`docs/COMPONENTES.md`** (`form_errors`, `collection_header`, `list_card_actions`) — e `form_errors`
é justamente o componente que o `HT-03` diz que deveria estar em uso.

Contagem detalhada da primeira auditoria:

**Seis órfãos diretos** (zero referência em `templates/`, `static/` e `*.py`):
`components/lists/main_list_card.html` (o teste `core/tests/test_dark_redesign.py:673` já asserta
que ele **não** aparece no lab — foi descontinuado e não apagado),
`components/perfil/gdrive_card.html`, `components/perfil/partials/_gdrive_card_header_meta.html`,
`components/ui/filters/advanced_filters.html`, `components/ui/filters/search_input.html`,
`components/ui/lists/list_card_actions.html`.

**Quatro alcançáveis só sob `DEBUG`**, via `dev/ui_lab`: `components/lists/list_filters.html`
(único includer é o órfão acima), `components/lists/list_grid.html`,
`components/cards/document_card.html`, `components/ui/tables/data_table.html`.

> **RESOLVIDO em 07/08/2026. As duas auditorias divergiam porque existem TRÊS situações, não duas.**
> A medição por arquivo (`AGENTS.md` §3.6) separou:
>
> | situação | quantos | o que foi feito |
> |---|---:|---|
> | nenhum citador em lugar nenhum | 5 | apagados |
> | citado só por um teste que afirma a **ausência** dele | 1 | apagado |
> | órfão **em cascata**, revelado pelos anteriores | 1 | apagado |
> | alcançável a partir do UI Lab, sob `DEBUG` | 7 | **mantidos** |
>
> **A cascata é o motivo de a regra valer mais que a lista.** `lists/list_filters.html` só era citado
> por `lists/main_list_card.html` — o enunciado já suspeitava — e virou órfão no instante em que o
> outro saiu. Quem contasse uma vez e apagasse a lista deixaria este para trás; quem roda a regra
> **depois** de apagar, não. Foi o teste que apontou, não eu.
>
> **`main_list_card.html` era o caso mais estranho:** o único vestígio dele no repositório era
> `core/tests/test_dark_redesign.py`, e ainda por cima numa asserção de que ele **não** aparece no
> lab. Estava sendo mantido vivo pela própria prova de que não era usado.
>
> **Os 7 do laboratório não foram apagados, e a razão não é cautela.** Apagá-los é decidir para que
> serve o UI Lab — e existem **dois** labs concorrentes sem regra de qual é o vigente, que é o
> `BE-17`. Ficam nominados em `core/tests/test_componentes_sem_orfao.py`, com o citador de cada um,
> para que a decisão seja de um passo: `field_action_button`, `floating_primary_action`,
> `footer_action`, `forms/dropdown`, `collection_header`, `list_grid`, `data_table`.
>
> **Dois dos "citados como canônicos" saíram do `docs/COMPONENTES.md`** (`list_card_actions` e
> `main_list_card`) e o terceiro ganhou a ressalva de que só existe no laboratório
> (`collection_header`). O `form_errors`, que o enunciado citava junto, **deixou de ser morto pelo
> `HT-03`**: hoje tem 20 chamadores.
>
> **`components/cards/document_card.html` não era morto** — o enunciado o listava entre os de
> `DEBUG`, e a medição mostrou consumidor de produção. Não foi tocado.
>
> A trava é `test_componentes_sem_orfao.py`, e é sobre a **regra**: componente novo que ninguém
> renderiza reprova, componente que perde o último consumidor reprova, e a lista do laboratório é
> conferida nos dois sentidos — perder o citador do lab ou ganhar um de produção também reprova.
>
> **Adendo de 07/08/2026:** a decisão veio — o `BE-25` (PR #247) apagou os dois labs — e os 7
> caíram na cascata exatamente como previsto, mais o `document_card` em segunda ordem (os
> citadores de produção que esta nota lhe media eram `list_grid` e `ui_lab2/views.py`). O
> fechamento, com prova por arquivo, é o `NOVO-44`.

### HT-07 ✅ RESOLVIDO (5b58fac7) · Concatenação condicional com "·" no template · AUD · 1–2 d

`templates/eventos/partials/_evento_card_body.html:17` (repetido nas linhas 75 e 137) monta o
subtítulo com uma cadeia de `{% if %}` cujo separador depende de
`oficio.destino_display and oficio.protocolo or oficio.destino_display and
oficio.data_evento_display` — **sem parênteses**, dependendo da precedência do motor de template.
`grep -rn '{% if .*and.* %} ·'` → **10 ocorrências em 8 arquivos**.
O mesmo arquivo tem a maior profundidade de aninhamento do repositório: **6 níveis** (linhas
123-198).
**Correção:** `join_non_empty(parts, sep=" · ")` no presenter, testável.

### HT-08 ✅ RESOLVIDO (70f369c6) · Oitenta `<button>` fora do sistema de componentes · AUD · 3–4 d · risco médio

Por app, excluindo componentes e labs: `prestacoes_contas` 23, `oficios` 15, `eventos` 11,
`planos_trabalho` 10, `roteiros` 10, `termos` 6, `ordens_servico` 3, `core` 1, `usuarios` 1.
`components/ui/buttons/button.html:2` já resolve a semântica (`{% if href %}<a>{% else %}<button>`),
então a maioria é reimplementação de markup, não falta de suporte.
**Efeito:** qualquer mudança de contrato do botão — a começar pelo foco do `HT-01` — precisa ser
replicada em 80 pontos.
**Armadilha:** parte deles tem handler de JS amarrado à classe. Conferir `static/js/components/*`
antes de cada substituição (mesma família do `JS-06`).

### HT-09 ✅ RESOLVIDO · ⚪ Login sem skip link e sem erro associado · AUD · 0,5 d

`templates/core/login.html:1-79` não estende `base.html`: duplica `<!doctype>`, `<head>` e tema.
Medido no navegador: é a **única** das 25 páginas testadas sem `<a class="cv-skip-link">`. Os erros
de campo (`:56`, `:64`) têm `id`, mas `core/forms/__init__.py:14-27` nunca os referencia por
`aria-describedby`.

> **RESOLVIDO em 06/08/2026.** Skip link apontando para `#auth-form`, e os erros de campo passaram
> a ser referenciados por `aria-describedby` + `aria-invalid`.
>
> Duas coisas que a implementação óbvia erraria:
>
> - **o `.cv-skip-link` mora em `components/app-shell.css`**, que só entra pelo bundle do casco.
>   Colar a marcação nesta tela deixaria o link **sem estilo**, visível e atravessado no layout. O
>   estilo foi duplicado em `auth.css`, com comentário dizendo que sai no dia em que o login
>   estender `base.html`.
> - **o `aria-describedby` é ligado no `full_clean`, não no `__init__`** — em `__init__` os erros
>   ainda não existem. Apontar para um `id` ausente seria pior que não apontar: o leitor de tela
>   ignora a referência quebrada e o atributo vira ruído em toda tela de login sem erro.
>
> **O `autofocus` do campo de usuário deixa o skip link fora do Tab para frente** (chega-se a ele
> por Shift+Tab). Quem ele serve de fato é quem lê em sequência com leitor de tela e hoje atravessa
> título, subtítulo e a lista de três recursos antes do primeiro campo.


### HT-10 ✅ RESOLVIDO (e12672ff) · Migração de `data-*` de toggle parada no meio · AUD · 0,5–1 d · risco médio

`docs/DATA_ATTRIBUTES_JS.md:96-97` já marca `data-rg-toggle` e `data-motorista-fixo-toggle` como
legado, com `data-cv-state-trigger` como sucessor. `components/ui/buttons/field_action_button.html:6,16,17`
— um componente compartilhado — ainda emite os dois legados. Só
`roteiros/partials/roteiro/_bate_volta_actions.html:12` usa o canônico.
**Risco:** o próximo desenvolvedor copia o padrão errado do componente compartilhado.

### Verificado e correto — não redescobrir

Paginação (`pagination.html`) com `aria-current` e `aria-live`; sidebar com `aria-expanded` e
`aria-controls`; `button.html` resolvendo `<a>` vs `<button>`; select customizado com
`aria-labelledby` e `<label for>`; a única tabela de produção
(`cadastros/configuracao/partials/_diarias_historico.html`) com `<caption>` e `th scope`; contrato
`data-collection`/`data-collection-mode` respeitado em 100% dos containers; **zero ORM disparado
por template**.

### Não vira ID: os `href="#"`

As **93 suspeitas** do `audit_django_architecture.py` não são 93 `href="#"` — são o total de
quatro categorias (10 `href_falso_template` + 15 `html_em_presenter` + 26 `query_direta_view` +
42 `get_object_or_404_em_view`). Os `href="#"` reais são **10**, e a classificação individual
mostrou que todos estão em `ui_lab2`/`dev/ui_lab` sob `settings.DEBUG` ou em `pdf_viewer.html`
sob `is_demo=True` (passado só por `dev/ui_lab/documents.html:23`). **Nenhum alcançável em
produção.**

---

## UI — CSS

### UI-01 ✅ RESOLVIDO · 🟠 36% das classes declaradas não aparecem em lugar nenhum · MED · ver plano de front

2.612 classes declaradas em `static/css` (fora o bundle, que é concatenação); **~936 sem nenhuma
ocorrência** num corpus de 4,7 MB com todos os templates, todo o JS e todo o Python dos 15 apps.
**981 blocos** cujo seletor só usa classes mortas, somando **168 KB**.

> **Enunciado corrigido pela verificação (05/08).** A versão original deste ID afirmava existir
> **um único** padrão de classe montada dinamicamente em todo o `static/js`. **É falso, e o erro
> era do método**: a varredura ancorava na aspa de abertura e só procurava `${`, então perdeu
> interpolação no meio da string e toda concatenação com `+`. Existem **pelo menos três**
> padrões, em três arquivos de produção:
>
> | arquivo | padrão | classes geradas |
> |---|---|---|
> | `static/js/components/picker.js:143-144` | `` `cv-search-picker--${mode} cv-search-picker--${variant}` `` e `--${presentation}` | `--single`, `--multi`, `--detailed`, `--compact`, `--vehicle` |
> | `static/js/pages/usuarios-admin.js:123-124` | `prefix + "__toggle--ready"` / `"--changing"` | `usuario-quick-add__toggle--*`, `area-quick-add__toggle--*` |
> | `static/js/pages/oficios-viatura-sugestoes.js:127` | `"viatura-sugestao-badge--" + s.reason` | `--motorista`, `--unidade` |
>
> Todas essas classes existem no CSS e estavam sendo contadas como mortas. O número de candidatas
> cai para **no máximo ~929**, e as três telas envolvidas (`usuarios/index.html`,
> `usuarios/areas/index.html`, `oficios/wizard_dados_viajantes.html`) são de produção, não de
> laboratório.
>
> **Consequência operacional, mais importante que o número:** a prova de grep exigida pelo
> `AGENTS.md` §3.6 em cada PR de poda **tem que cobrir concatenação com `+` e interpolação no
> meio da string**, não só `` `${…}` `` no começo. Uma poda guiada pelo método antigo apagaria
> classe viva.
>
> Em Python não há padrão equivalente: nenhuma classe montada por f-string, `+`, `.format()` ou
> `.join()` fora do enum estático `WidgetStyle`.

> **Segunda correção do enunciado (07/08), maior que a primeira.** A revisão de 05/08 disse
> "**pelo menos** três" padrões de classe montada em runtime, todos em JS, e afirmou que em Python
> não havia equivalente. Quatro varreduras independentes, com lentes diferentes, e uma consolidação
> que remediu cada achado contra o inventário de 2.617 classes acharam **25 prefixos**: os 3
> conhecidos mais **22 novos**. E a assimetria é estrutural — **20 dos 22 estão em templates Django
> e Python**, superfície que a varredura original nunca olhou.
>
> **A afirmação sobre Python está refutada**, com três famílias de contraexemplo lidas no arquivo:
>
> | onde | o que monta |
> |---|---|
> | `prestacoes_contas/presenters.py:284` e `:398` | f-string → `prestacao-card-group--{start,middle,end}` |
> | `core/views.py:804` | f-string → `status-chip--{tone}` |
> | `oficios/presenters.py:37-42`, `roteiros/presenters.py:149-164` | função devolve a classe inteira → `roteiro-list-card--faixa-*` |
>
> O que o catálogo acertou: o caminho de widgets está limpo — `WidgetStyle` é enum de 19 literais
> completos. O erro foi generalizar essa limpeza para todo o Python.
>
> **Uma correção de fato no padrão #1:** a montagem está em `picker.js:190-191`, não em `143-144`;
> aquelas linhas só leem os `data-*`.
>
> **O pior caso do repositório** é `cv-search-picker--vehicle`: existe apenas no CSS, em ~22 regras
> de tema escuro. Apagá-la quebraria **só** o tema escuro do picker de viatura — dano invisível para
> quem revisa em tema claro.
>
> **Buracos que continuam abertos, declarados:** seletores de atributo (`[data-state=…]`) correm o
> mesmo risco e ficaram fora de todas as lentes; os vocabulários de `cv-btn--`, `cv-icon-btn--` e
> `cv-chip--` não foram fechados (sabe-se que o prefixo é composto, não quais valores existem);
> `migrations/` não foi varrido; e nada foi executado — a varredura é estática.

**Segunda correção do meu próprio método (07/08).** A derivação de prefixos tratava qualquer
adjacência a `{% templatetag openblock %}` como composição de sufixo. Mas
`class="cv-action-menu__item{% templatetag openblock %} if x {% templatetag closeblock %} is-assinado…"`
emite `" is-assinado"` **com espaço**: é classe separada, não sufixo. A regra passou a exigir que o
que sai da interpolação **cole** no token, e a lista caiu de 160 prefixos para 41. Conferido que
`oficios.css` não muda com a regra nova — as mesmas 8 classes protegidas pelos dois métodos.

**Terceira correção do enunciado: a contagem por arquivo superestima quando a classe é estilizada
em MAIS DE UM CSS.** Medido em `cv-buttons.css`, o menor dos seis:

| | |
|---|---|
| classes no arquivo | 59 |
| sem nenhuma ocorrência em código | **25** ← é o que a auditoria contou (daí "49 blocos") |
| dessas, estilizadas por **outro** CSS | **16** |
| genuinamente órfãs | **9** |

As 16 estão em `action-system.css` (12), `theme-dark-components.css` (5), `cv-select.css` (2),
`ui-lab-fields.css` (2) e `utilities.css` (1). Elas são mortas de verdade — nenhum template as usa —,
mas **removê-las por inteiro exige tocar dois arquivos**, e a regra de um-arquivo-por-PR do
`AGENTS.md` §3.6 não prevê isso. Podar só a metade deixa regra órfã do outro lado.

**Isto precisa de decisão antes de continuar:** ou a regra passa a admitir PR por *família de
classe* em vez de por arquivo, ou o `UI-01` termina deixando ~16 classes meio-podadas só neste
arquivo — e o padrão deve se repetir nos demais.

**`oficios.css` fechado em 07/08.** 106,0 → 65,9 KB (−40,2 KB, −38%), 239 blocos removidos, 178
classes. Prova: **15 de 16 comparações de tela pixel-idênticas** (8 páginas × 2 temas); a 16ª tem 63
pixels de antialiasing na borda de um ícone, delta máximo de 4 em 255. Duas catracas desceram junto:
`audit_frontend_standards` 392 → 387 avisos e `audit_foco_visivel` 44 → 42 blocos.

O número medido ficou **abaixo** do enunciado (239 blocos contra 283) por três motivos, todos na
direção segura: o corpus foi de 9,8 MB em vez de 4,7 MB; classe citada por outro arquivo CSS conta
como viva; e 8 classes foram salvas por prefixo dinâmico — entre elas
`oficio-viatura-reason--unidade`, que **a minha própria derivação de prefixos tinha perdido** porque
o `+` da concatenação fica no início da linha seguinte (`static/js/pages/oficios-transporte.js:254`).

| arquivo | blocos mortos | peso |
|---|---:|---:|
| `oficios.css` ✅ | 283 → medido 239 | 47 KB → medido 40,2 KB |
| `page-shell.css` ✅ | 78 → medido 57 | 14 KB → medido 9,4 KB |
| `roteiros.css` ✅ | 78 → medido 76 | 14 KB → medido 13,9 KB |
| `cv-buttons.css` ✅ | 49 → medido 9 | 11 KB → medido 2,1 KB |
| `dev/ui-lab-fields.css` ✅ | 96 | 18 KB — arquivo apagado inteiro |
| `dev/ui-lab-pages.css` ✅ | 79 | 16 KB — arquivo apagado inteiro |

**Os dois arquivos do lab não foram podados: foram apagados junto com o laboratório**, por decisão
do dono. Antes de apagar, verifiquei a fronteira, e o resultado corrigiu uma afirmação minha:

> Eu tinha escrito que apagar os CSS do lab quebraria produção, porque `cv-field-row` e
> `cv-field__control--select` são usadas em produção e só existiam ali. **Está errado.** Os cinco
> arquivos de `static/css/dev/` são linkados apenas por `templates/ui_lab2/base.html` e
> `templates/dev/ui_lab/base.html`, e nenhum entra no `shell.bundle.css` — **produção nunca os
> carregou**. Logo as duas classes já estavam sem estilo em produção; copiá-las para
> `cv-select.css`/`forms.css` teria **adicionado** aparência inexistente dentro de um PR de deleção.
> Desfiz o "resgate".

**Fica um defeito novo, separado:** `WidgetStyle.FORM_SELECT_FIELD_CONTROL`
(`core/forms/widgets.py:27`) emite `cv-field__control--select` em todo `<select>`, e
`templates/cadastros/servidores/partials/_form_fields.html:11` emite `cv-field-row` — **nenhuma das
duas tem CSS por trás em produção.** Contrato de widget apontando para regra que não existe.
Virou o `NOVO-46`, para deixar de ser nota de rodapé de outro ID.

**A prova de grep exigida pelo `AGENTS.md` §3.6 tem que ser refeita arquivo a arquivo no PR** —
esta contagem é o mapa, não a licença.

---

**Varredura final, 07/08.** Os seis arquivos do plano estavam fechados, mas o plano nomeou só os
seis maiores: uma remedição do `static/css` inteiro achou **412 blocos e 71,6 KB** ainda mortos,
espalhados por **31 arquivos**. O enunciado ("981 blocos, 168 KB") sempre foi do repositório todo;
foi a *lista de trabalho* que parou nos seis.

O resto saiu em duas levas, separadas pela regra — não pelo arquivo:

| leva | regra | arquivos | blocos | peso |
|---|---|---:|---:|---:|
| A | classe morta em código **e** em todo o CSS | 25 | 305 | 49,4 KB |
| B | classe morta em código, estilizada em ≥2 CSS (por família) | 17 | 102 | 21,5 KB |

**O instrumento de verificação mudou, e essa é a correção de método deste ciclo.** Os PRs
anteriores provaram "sem regressão" por diff de pixel. Rodando o rastreador **duas vezes com o CSS
idêntico**, 25 das 88 telas divergiram — antialiasing de texto e um painel de `/usuarios/` que muda
sozinho. O piso de ruído do instrumento ficou **maior** que qualquer diferença que a poda produziu:
ele não conseguia separar "não mudou" de "mudou pouco". A afirmação de 15/16 telas idênticas no PR
do `oficios.css` foi mais sorte que rigor.

A troca foi para `getComputedStyle`: para cada elemento de cada tela, a caixa mais 44 propriedades
que desenham. Determinístico depois de desligar `transition` e `animation` — duas capturas do mesmo
CSS dão **0 de 41.938** elementos diferentes. É o valor que o motor resolveu, que é exatamente o que
uma regra apagada mudaria.

**Resultado da leva A:** 0 de 41.938 elementos com estilo computado diferente, em 88 telas (44
rotas × 2 temas, descobertas por rastreio a partir da barra lateral, não escritas à mão). Catracas:
`audit_frontend_standards` 296 → 248, `audit_foco_visivel` 36 → 35.

**A catraca que fecha o ID:** `scripts/audit_css_morto.py --max 0`, no CI. Os 981 blocos não foram
escritos assim — cada refactor apagou markup e deixou o CSS para trás. Sem catraca o acúmulo
recomeça no próximo PR. O teto nasce em zero porque é onde a leva A o deixou.

**Resultado da leva B:** 102 blocos, 21,5 KB, 17 arquivos, 59 classes — todas com estilo em dois ou
mais CSS, que é o que a regra antiga não sabia podar. Verificação idêntica: **0 de 41.938**
elementos com estilo computado diferente. Catracas: `audit_frontend_standards` 248 → 246,
`audit_foco_visivel` 35 → 32.

**Fechamento, com o total.** Somando os seis arquivos do plano e as duas levas finais:

| | blocos | peso |
|---|---:|---:|
| seis arquivos do plano (PRs anteriores) | 556 | 99,8 KB |
| leva A | 305 | 49,4 KB |
| leva B | 102 | 21,5 KB |
| **total** | **963** | **170,7 KB** |

Contra o enunciado de **981 blocos e 168 KB** — a diferença de blocos é de método (corpus maior,
classe citada por outro CSS conta como viva, 46 prefixos dinâmicos protegidos) e está na direção
segura.

**O que fica declarado como não resolvido**, para o ID não fechar prometendo mais do que entregou:
seletor de atributo (`[data-state=…]`) nunca entrou em lente nenhuma; os 70 nomes mortos dentro de
seletor agrupado vivo são o `NOVO-48`; e as classes `roteiro-list-card--faixa-*` continuam no CSS
protegidas por prefixo, presas ao `NOVO-45`.

### UI-02 🟠 Tema escuro é camada de exceção, não de token · MED

`static/css/components/theme-dark-components.css` tem **5.843 linhas** — o maior arquivo CSS do
projeto depois do bundle — e **190 `!important`**. O tema escuro não é resolvido por token: é
resolvido sobrescrevendo componente por componente. Total de `!important` fora do bundle: **497**.

### UI-03 ✅ RESOLVIDO (E7a) · Nove arquivos definem token de cor · MED

`--color-*` era **definido** em `tokens.css`, `theme.css`, `03-theme-dark.css`,
`components/theme-dark-components.css`, `page-shell.css`, `roteiros.css`, `usuarios.css`,
`justificativas.css` e `gdrive-config.css`. Redefinições campeãs: `--step1-surface` (15×),
`--step1-panel` (15×), `--step1-field` (13×), `--field-border-focus` (7×), `--cv-field-bg` (7×),
`--color-input-bg` (7×).

**Remedido na E7:** eram **oito** arquivos, não nove — `gdrive-config.css` já tinha parado de
definir. E o enunciado não mencionava a família `--theme-*` (40 nomes, 152 definições), que é uma
camada intermediária real entre `--color-*` e os tokens de componente. Consolidar só `--color-*`
teria deixado `--theme-*` como terceira camada global não declarada, que é o oposto do objetivo.

**Como fechou.** `base/theme.css` foi dissolvido: os blocos `:root` e `html[data-theme="light"]`
foram para o fim de `tokens.css`, e o bloco `html[data-theme="dark"]` para o **começo** de
`03-theme-dark.css` — começo, e não fim, porque o `theme.css` carregava antes; apender embaixo
inverteria a disputa e mudaria cor sem mudar valor nenhum. As regras do seletor de tema, que não
eram token, foram para `layout/sidebar.css`.

Em `page-shell.css`, dos 7 `--color-*` (× 2 temas), **4 eram mortos** — só definição, nenhuma
leitura em CSS, JS, Python ou template. Foram apagados (8 declarações). Os 3 vivos foram
**renomeados** para a família do próprio componente (`--text-filter`, `--text-filter-button`,
`--text-filter-placeholder`), ficando junto dos irmãos `--surface-filter-*`/`--border-filter-*` em
vez de migrarem para o arquivo de token e se separarem deles.

**O que a regra alcança.** A catraca (`core/tests/test_tokens_em_duas_camadas.py`) vale para
definição em escopo raiz — `:root` e `html[data-theme=…]`. Re-ligar um token dentro de um seletor
de componente continua permitido, medido: **45 regras globais** leem `var(--color-input-bg)` e
**10** leem `var(--color-focus)`. Um container que re-liga o nome dirige todas elas sem que
nenhuma precise conhecê-lo; proibir obrigaria a duplicar as 55 sob seletor de container, subindo
especificidade — a dívida que a Fase 7 veio pagar. Os 4 sites que exercem a permissão estão
anotados no CSS, cada um dizendo qual regra global dirige.

**A prova.** Nenhum gate do repositório protege valor de token: `medir_divergencia_tema.py` filtra
fora custom property e cor, `audit_paleta.py` compara hex soltos, `test_css_tokens.py` restringe
literal e não local. Dava para trocar uma cor e o CI inteiro passar. Por isso a etapa escreveu
`scripts/resolver_tokens_css.py`, que resolve a cascata nos três escopos raiz e expande `var()` até
o literal: **2131 valores computados, 0 diferenças** antes/depois.

### NOVO-82 ✅ RESOLVIDO (E9-d) · `NOVO` 87 das 143 declarações escuras do `theme.css` já eram mortas · MOR · 1 d

Ao dissolver o `theme.css` (`UI-03`), o bloco `html[data-theme="dark"]` dele passou a conviver com
o bloco próprio do `03-theme-dark.css`, no mesmo arquivo. Aí ficou visível o que a separação
escondia: das 143 declarações que vinham do `theme.css`, **87 já eram sobrescritas** pelo bloco de
baixo — e **57 delas com valor diferente**.

Não é regressão: era assim antes, porque o `theme.css` sempre carregou primeiro. O que muda é que
agora dá para ver. Exemplos: `--app-hero-body-bg` declarava um `linear-gradient` e o que vale é
`var(--color-surface)`; `--app-text-muted` declarava `var(--color-text-muted)` e o que vale é
`var(--color-muted)`.

O custo real é de leitura: quem abrir o arquivo para entender o tema escuro lê 87 declarações
inertes, 57 delas apontando para o lugar errado. Já mordeu uma vez —
`test_dark_redesign.py:618` lia a **primeira** declaração de cada token e passou a ler a perdedora;
o teste foi corrigido para ler a última, que é a que vence a cascata.

Fica para a **E9** (`UI-02`, "o tema escuro dissolvido em token"), que é onde o arquivo é reescrito
de qualquer forma. Apagar as 87 é provável por `scripts/resolver_tokens_css.py` — se a tabela de
valores computados não mudar, nenhuma era viva.

**Fechado na E9-d.** As 87 declarações vencidas foram removidas, incluindo as 57 cujo valor
enganoso diferia do vencedor. O bloco legado caiu de 143 para **56 declarações vivas** e ficou com
**zero nomes** redefinidos pelos blocos canônicos seguintes. O resolvedor manteve os **2.135 valores
computados** e o mesmo SHA-256 antes/depois
(`55c095380e25f0735ad7bb8a40dd23a916df57cb9f47a98e91bd7ed54f064abc`).

### UI-04 🟠 CSS de outro domínio importado em 26 templates · MED

**54 imports** de CSS de domínio alheio. Prestações importa CSS de Ofícios 11 vezes; Termos, 4;
Planos de Trabalho importa de três domínios diferentes. Exemplo com uso medido:
`templates/prestacoes_contas/index.html:11-14` importa `oficios.css` (106 KB, **0,0% de uso na
página**) e `roteiros-list.css` (15 KB, **0,0%**).

A causa não é descuido: o estilo dos componentes compartilhados mora **dentro** dos arquivos de
domínio, então quem quer o componente leva o domínio inteiro junto. É a fronteira que o plano de
front precisa desfazer.

---

## QA — Testes, CI, segurança e infraestrutura

A esteira de CI é disciplinada nos invariantes que decidiu vigiar: catracas de front e de
arquitetura, piso de cobertura por app, SLA de geração de documento medido, e um drill de
backup/restore criptografado a cada push. `manage.py check --deploy` não acusa nada. As lacunas
estão **fora desse perímetro**.

Cobertura total dos 15 apps do CI: **73,21%** (19.955/27.258 statements).

### QA-01 ✅ RESOLVIDO (c4fd659f) · 🟠 Login do Django Admin sem rate limit nenhum · AUD · 1 d

`config/urls.py:9` monta `admin.site.urls` sem `AdminSite` customizado. O único rate limit do
sistema é `core/views.py:969-1006` (`LoginView`), que cobre só `core:login`. O admin usa a própria
view do `AdminSite`, que não passa por ali nem por middleware de throttle. Não há `django-axes`
nem equivalente em `requirements/*.txt`.
**Efeito:** `/admin/` concede superusuário e é a porta sem nenhuma fricção contra força bruta — só
a política de senha (mínimo 12 caracteres) a segura. São 223 rotas de admin no resolver.

### QA-02 ✅ RESOLVIDO (fe43b1d8) · 🟠 O rate limit depende de um Redis que nenhum ambiente declara · AUD · 0,5 d

`config/settings/base.py:113-122` cai para `LocMemCache` quando `REDIS_URL` está vazio. **Nenhum**
dos quatro templates de env declara `REDIS_URL` (`.env.example`, `.env.production.example`,
`.env.producao.example`, `.env.homologacao.example`). `docs/DEPLOY_VPS.md:200,228` documenta
Gunicorn com `--workers 3`.
**Efeito:** com cache por processo e 3 workers, o limite de 5 tentativas/15 min
(`core/views.py:975-976`) vira na prática até ~15 tentativas antes de um worker bloquear sozinho —
e zera a cada `systemctl restart`, que o próprio `deploy.yml` executa a cada deploy.
O time já sabia pela metade: `docs/DOCUMENTOS_GERACAO_DOCX_PDF.md:86` pede `REDIS_URL` em
produção, mas a frase não está na checklist de campos obrigatórios do `DEPLOY_VPS.md:136`.
**Correção:** exigir `REDIS_URL` em `config/settings/prod.py` (falhar cedo, como já se faz com
`FIELD_ENCRYPTION_KEYS`) e declarar nos quatro templates. Resolve também o `QA-09`.

### QA-03 ✅ RESOLVIDO · 🟠 O rollback do deploy não desfaz migração · AUD · 1,5 d · risco médio

`.github/workflows/deploy.yml:77` tira backup **antes** do checkout; `:90` roda
`migrate --noinput` já no código novo; e `reverter()` (`:79-85`) só faz
`git checkout --detach "$BEFORE_SHA"`, reinstala dependências e reinicia — **nunca chama
`scripts/restore_backup.sh`**.
**Efeito:** se uma migração destrutiva for aplicada e um passo posterior falhar (`collectstatic`,
health check em `:116-119`), o `trap ERR` devolve o código antigo rodando contra um schema que ele
não entende. O backup existe e não é usado — a recuperação vira intervenção manual sob pressão.

> **Corrigido em 06/08.** `scripts/deploy_rollback.sh` desfaz as migrações que **este** deploy
> aplicou, comparando o `showmigrations` de antes com o de agora e chamando o desfazer do próprio
> Django, app por app, em ordem inversa do plano.
>
> **Não restaura o backup, e isso é o desenho, não uma lacuna.** Restaurar descarta tudo que foi
> gravado desde que o backup foi tirado, e `restore_backup.sh` ainda sobrescreve o `MEDIA_ROOT` —
> perde arquivo enviado por usuário. Um deploy leva minutos, e nesses minutos há gente trabalhando.
> Trocar uma incidência por outra sem decisão humana não é correção. Quando o desfazer não é
> possível, o script **para e instrui**, com o caminho real do backup e o comando pronto.
> Desfazer pelo Django é o único caminho que **preserva as gravações da janela do deploy**.
>
> **Dois ajustes no `deploy.yml` que reduzem a janela em vez de só tratá-la:**
> `collectstatic` passou a rodar **antes** de `migrate` (não depende do schema e é a falha mais
> provável e mais boba da sequência); e o caminho do `.enc`, que `backup_production.sh` sempre
> imprimiu e o deploy jogava fora, agora é capturado e citado na instrução.
>
> **O rollback roda antes do `git checkout` de volta** — desfazer migração exige os arquivos de
> migração do commit novo em disco.
>
> **Drill no CI** (`tests.yml`, vizinho do drill de restauração): contra Postgres de verdade, com
> delta em **dois** apps de propósito, porque é onde a ordem inversa importa. Provado pegando dois
> rollbacks quebrados — um que não faz nada (`o rollback não devolveu o estado de antes`) e um que
> desfaz só um dos apps (a conferência final do próprio script: `sobraram migrações aplicadas`).
>
> Cinco caminhos exercitados localmente contra Postgres: delta vazio, delta reversível, delta em
> dois apps, migração irreversível (com uma `RunPython` sem `reverse` de verdade) e `manage.py`
> que não roda. Nos dois últimos o script sai 1 **sem ter tocado no banco**.
>
> **Não verificável daqui:** um deploy real contra a VPS. O drill exercita o script; o YAML que o
> chama só é exercitado de fato no primeiro deploy depois deste merge.

### QA-04 ✅ RESOLVIDO (c021ce25) · 🔴 A validação central de upload nunca roda, nos 5 tipos de anexo · AUD+VER · 1,5 d

> **Este ID foi agravado pela verificação (05/08).** A versão original dizia que **um** campo
> (`despacho_assinado`) escapava da política central, e que era o único. A verificação achou algo
> pior, e provou.

`prestacoes_contas/models.py:78-82` — `despacho_assinado` usa só `FileExtensionValidator`, e
`:294-296` — `PrestacaoDocumentoAnexo.arquivo` **declara** `validate_private_document_upload`
(`core/uploads.py:15-49`), que checa tamanho, *magic bytes*, bomba de descompressão e antivírus.

Só que:

1. **`despacho_assinado` é campo legado morto.** Nenhuma view ou form atual escreve nele —
   confirmado por teste: continua vazio depois de um upload real. O upload de verdade vai para
   `PrestacaoDocumentoAnexo.arquivo`.
2. **E o `arquivo`, que tem o validador declarado, nunca o executa.** Todos os caminhos de escrita
   — `document_views.py` e os forms de despacho, ofício assinado, comprovante, RT assinado e
   diário assinado — criam o registro com `.objects.create()` direto, **sem `full_clean()`**.
   Validador de campo não roda em `create()`.

**Provado, não inferido:** um arquivo chamado `despacho.pdf` com conteúdo
`"nao sou um pdf de verdade..."` — sem os *magic bytes* `%PDF-` — foi aceito pela view real
`prestacao_despacho_assinado_anexar` e gravado tal qual. Com `PRIVATE_UPLOAD_MAX_BYTES=1`
sobrescrito, um arquivo de 43 bytes também passou.

**Efeito:** a lacuna não é de um campo, é sistêmica nos **5 tipos de anexo** de prestação de
contas. O validador central citado como presente é, na prática, **código morto**. E o arquivo
depois é sincronizado para o Google Drive
(`integracoes/google_drive/organizer.py:751-754`).
**Correção:** chamar `full_clean()` nos caminhos de escrita, ou mover a validação para o form/
service — e decidir se `despacho_assinado` sai do modelo.

### QA-05 🟡 Cliente real do Google Drive com 42,5% de cobertura · AUD · 3 d

`integracoes/google_drive/services.py` — 301 statements, **42,52%**. A classe `_RealClient`
(a partir de `:218`), com refresh de token OAuth (`:243-250`) e todos os métodos que chamam
`self._svc.files()…execute()` (`:260-330`), está fora do alcance dos testes:
`tests/test_organizer_contract.py:16` define `DriveClientDouble(services._MockClient)` — os testes
exercitam o dublê, não o código que fala com a API. Não há `responses`/`vcr` no projeto.
**Agrava o `QA-10`:** é justamente o app com a menor folga real sobre o piso de cobertura.

### QA-06 🟡 Teste da CVE do WeasyPrint verifica texto-fonte, não comportamento · AUD · 0,5 d

`documentos/tests/test_weasyprint_security.py:8-10` — o único teste é
`assertIn("presentational_hints=False", inspect.getsource(render_pdf_bytes_weasyprint))`. E
`tests.yml:113-115` **ignora `PYSEC-2026-3412` no `pip-audit` citando esse teste** como
justificativa.
**Efeito:** o teste prova que a string existe no código, não que HTML com atributo de apresentação
é bloqueado. Mover a flag para um dict de kwargs, ou abrir um segundo caminho de renderização sem
ela, passa no teste e regride a mitigação que sustenta o *ignore* da CVE.

> **Fechado no PR #186, e depois corrigido de novo.** Foram três formulações, e a terceira só
> existe porque a segunda tinha uma asserção de auto-diagnóstico. Registro porque a lição vale para
> qualquer teste deste repositório que gere documento:
>
> 1. Comparar **bytes do PDF** contra uma referência reconstruída à mão. Reprovou no CI, passou
>    local. Diagnóstico na hora: acoplamento ao ambiente.
> 2. Comparar **o adaptador contra o próprio adaptador**, trocando só a flag, por digest. Reprovou
>    no CI de novo — mas com a mensagem certa: *"duas renderizações idênticas deram documentos
>    diferentes"*.
> 3. **A saída em bytes do WeasyPrint não é reproduzível no runner**, nem entre duas chamadas
>    iguais no mesmo processo, e o efeito é **intermitente** (a mesma suíte passou numa execução e
>    reprovou na seguinte). Logo, comparação de byte, digest ou tamanho é inutilizável aqui: ou
>    reprova sozinha, ou passa vazia — todo `assertNotEqual` entre bytes vira verdadeiro por
>    acidente.
>
> A versão que ficou **não serializa PDF nenhum**: olha o estilo computado da árvore de caixas, que
> é onde a dica de apresentação age e onde o resultado é determinístico. Com as dicas ligadas,
> `bgcolor="#ff0000"` vira fundo vermelho na `<table>` e `color="#00ff00"` vira texto verde no
> `<font>`; desligadas, transparente e preto. É literalmente o que a CVE explora.
> Medido: 8 execuções seguidas, 8 verdes; invertendo a flag no adaptador, 2 de 3 reprovam.

### QA-07 🟡 Nenhum gate de lint, formatação ou tipo em Python · AUD · 1 d

`grep -i "ruff\|black\|flake8\|mypy\|isort\|pylint"` em `requirements/*.txt`,
`.github/workflows/*.yml` e `pyproject.toml` → **vazio**. Os únicos auditores estáticos são os dois
scripts próprios do projeto, que checam regra arquitetural e padrão de front — nenhum pega import
morto, nome não definido em ramo raro ou incompatibilidade de tipo.
**Nota de folga:** `audit_django_architecture.py --max-orm-em-view 30` está com **folga zero** —
30 medido contra teto 30. Qualquer ORM novo em view reprova o CI.

### QA-08 🟡 Dependências de assinatura e criptografia atrasadas · AUD · 2 d · risco médio

`pip list --outdated`: `pyHanko 0.25.3 → 0.36.2` (11 minors), `pyhanko-certvalidator 0.26.8 →
0.31.4`, `redis 5.3.1 → 8.1.0` (3 majors), `reportlab 4.5.1 → 5.0.0`, `weasyprint 68.1 → 69.0`,
`docxtpl 0.19.1 → 0.20.2`, `setuptools 79.0.1 → 83.0.0`.
`pip-audit` rodado na verificação: **"No known vulnerabilities found, 1 ignored"**. A lacuna é de
defasagem, não de vulnerabilidade confirmada.

> **Enunciado corrigido pela verificação (05/08).** O original dizia que "`pyHanko` assina e valida
> PDF digitalmente, e é onde o atraso pesa". **É falso.** `grep -rn "pyhanko"` em todo o `.py` de
> produção devolve **zero** — nenhum import, em lugar nenhum. O fluxo que os usava foi removido
> (`documentos/migrations/0003_remove_assinatura_fields.py`), e a assinatura eletrônica de hoje
> carimba o PDF com `pypdf` + `reportlab`, com hash visual, não PKCS#7/PAdES.
> `pyhanko>=0.21,<0.26` continua em `requirements/base.txt`: é **dependência morta**.
>
> Colateral: `docs/ASSINATURA_ETIQUETA_2_COMPAT.md` descreve o fluxo pyHanko como vigente e está
> desatualizado. Entra como `NOVO-01` abaixo.

**Correção:** antes de agendar atualização trimestral, **decidir se `pyhanko` e
`pyhanko-certvalidator` simplesmente saem** — não há nada para quebrar. `reportlab`, `weasyprint`,
`docxtpl` e `redis` seguem em uso e entram no `pip-compile --upgrade` trimestral, com a suíte
completa a cada bump.

### QA-09 ✅ RESOLVIDO (fe43b1d8) · 🟡 Dois templates de `.env` de produção divergentes · AUD · 0,25 d

`diff .env.production.example .env.producao.example`: nomes de banco diferentes
(`viagens_prod`/`viagens_user` contra `central_viagens_prod`/`central_viagens_prod_user`), caminhos
de mídia diferentes, e o de 32 linhas não tem `DOCUMENTOS_PDF_AUTO_FALLBACK`,
`DOCUMENTOS_PREGENERATE_PDF` nem `DOCUMENTOS_TMP_DIR`, que o de 54 linhas tem. Existem ainda
`.env.example` e `.env.homologacao.example`, com layouts próprios.
**Efeito:** os dois nomes são igualmente plausíveis; seguir o errado configura caminhos que não
batem com o que os scripts de deploy assumem.

### QA-10 🟡 `/metrics/` e margem de cobertura fina · AUD · segue de QA-02 e QA-05

`core/metrics.py:20-38` usa `cache.incr`/`cache.add` do mesmo `CACHES` do `QA-02`: com
`LocMemCache` e 3 workers, `/metrics/` reporta só os contadores do processo que atendeu à
requisição — número sistematicamente subestimado e instável.

Margem sobre o piso de cobertura abaixo de 1 ponto: `integracoes.google_drive` 54,25% contra
53,59% (**0,66 pp sobre 2.516 statements**, ~17 linhas — margem real);
`roteiros` 74,83% contra 74,10% (0,73 pp sobre 4.069 statements);
`diario_bordo` 91,67% contra 91,17% — artefato de arquivo minúsculo (12 statements, 1 linha =
8,3 pp), que se resolve pelo `BE-20`, não perseguindo a métrica.

### QA-11 ✅ RESOLVIDO (993e14c, 05/08/2026) · 🟡 `reparar-producao.yml` em UTF-16LE · AUD · 0,25 d

`file .github/workflows/*.yml`: os outros três são UTF-8; este é "UTF-16, little-endian, with CRLF".
`od` confirma BOM `FF FE` e bytes intercalados com `00`. Mesma família do `BE-22` (BOM em arquivos
Python), agora num workflow.
**Efeito:** o GitHub documenta suporte a BOM UTF-8/16/32, então pode funcionar — o risco é não se
ter certeza, e este é justamente o workflow de **reparo manual de produção**, ou seja, o que se
descobriria quebrado durante um incidente.
**Correção:** reconverter para UTF-8 sem BOM e validar com um `workflow_dispatch` de baixo risco.

> **Esta linha ficou aberta por engano.** A correção entrou em **`993e14c`, em 05/08** — commit cujo
> próprio título cita o ID (`ci: gates de encoding… (QA-06, QA-07, QA-11, QA-12)`) —, o
> `docs/PLANO_MESTRE_REFATORACAO.md:215` já marcava `[x]`, e só o catálogo não foi atualizado.
> Conferido em 06/08: o arquivo é UTF-8 sem BOM, 0 CRLF em 80 linhas, sem mojibake, e
> `core/tests/test_encoding_dos_workflows.py` guarda os três invariantes (BOM, decodificação e
> dupla codificação) nos quatro workflows.

**Sobre a validação por `workflow_dispatch` que o enunciado pedia:** existe uma execução, de
30/07 — `workflow_dispatch`, `conclusion: success`. Ela é **anterior** à conversão, e é justamente
por isso que serve de evidência: o GitHub rodou o arquivo **mesmo em UTF-16**, então o encoding
nunca foi o risco de execução. O risco nomeado era a **incerteza**, e quem a remove é a conversão
mais a catraca. O rastro do defeito ficou congelado no registro daquela execução, cujo campo `name`
até hoje é `Reparar produ├º├úo (FIELD_ENCRYPTION_KEYS)` — o mojibake que aparecia na interface do
Actions.

**Não disparei o workflow para "validar".** É o de reparo manual de produção; rodá-lo por
conferência de encoding seria usar produção como ambiente de teste, e o que se ganharia já está
provado por outros meios.

### QA-12 🟡 Sem Dependabot, sem CodeQL, sem gate de acessibilidade · AUD · 0,25 d + 3 d

`find .github -iname "*dependabot*" -o -iname "*codeql*"` → vazio. O `pip-audit` de
`tests.yml:112-115` só roda em `push`/`pull_request`: CVE divulgada depois do último merge só
aparece no próximo push. E `audit_frontend_standards.py` não tem nenhuma regra de ARIA, contraste
ou `alt` — o `HT-01` (foco invisível) e o `HT-02` (erro sem `aria-describedby`) passariam batidos
por ele indefinidamente.
**Correção:** Dependabot (`pip` + `github-actions`, semanal) é barato e fecha metade da lacuna;
a11y automatizado (axe-core via Playwright, já disponível no ambiente) é investimento maior.

### QA-13 ⚪ 218 de 1.266 testes são "magros" · AUD · —

17,2% dos testes têm no máximo 2 statements no corpo. Não é defeito por si — muitos são asserções
de contrato legítimas —, mas é o número a olhar quando um app "tem cobertura" e ainda assim
regride.

### QA-14 ⚪ CRUD de modelos de texto do Relatório Técnico sem teste · AUD · 0,5 d

`prestacoes_contas/model_views.py` — 66 statements, **25,76%**. As quatro views (`:19-137`) têm a
lógica de criação, edição e exclusão inteiramente fora da cobertura, incluindo o filtro por área
(`:25` e `:92`).

### QA-15 ⚪ Caminhos de erro da geração de PDF sem teste · AUD+VER · 1,5 d

`documentos/services/downloads.py` **0%** (16 statements, trata erro de geração) e
`adapters/weasyprint_pdf.py` ~32% — os dois **confirmados** na verificação.
`adapters/word_pdf.py` 37,35%, `libreoffice_resolve.py` 62,35% e `warm_cache.py` 38,24% vieram da
primeira medição e **não foram confirmados nem contraditados**: medi-los exige a suíte completa, e
ela travou na verificação (ver `NOVO-02` — que em 06/08 **não reproduziu**, então esta medição está
desbloqueada). (`adapters/excel_pdf.py` está em 0% mas é Windows-only
via `win32com.client` — não conta como lacuna.)
**Efeito:** os ramos de erro e *fallback* da função mais central do produto só executam quando algo
já deu errado — exatamente onde falta prova.

### QA-16 ⚪ Sem rastreamento de erro centralizado · AUD · 1 d

`grep -rin "sentry"` → nada. `core/errors.py:capture()` e `core/logging.py:JsonFormatter` produzem
log estruturado em stdout, sem agregação, alerta ou agrupamento.
**Efeito:** numa VPS pequena, sem alguém lendo `journalctl`, uma exceção recorrente (falha
silenciosa de sincronização com o Drive, por exemplo) se acumula sem que ninguém veja.
Casa com o `BE-18`: adotar `capture()` nos outros apps só tem valor pleno se houver onde os
eventos aterrissarem.

### NOVO-01 ⚪ `ASSINATURA_ETIQUETA_2_COMPAT.md` descreve um fluxo que não existe mais · VER · 0,25 d

O documento apresenta o fluxo de assinatura com `pyHanko` como vigente. Ele foi removido
(`documentos/migrations/0003_remove_assinatura_fields.py`), e a assinatura de hoje usa
`pypdf` + `reportlab`. Mesma família do `HT-13`: documentação de contrato apontando para o
passado.

### NOVO-02 ✅ NÃO REPRODUZIDO (06/08/2026) · ⚪ A suíte trava ao combinar certos grupos de apps · VER

Na verificação, rodar `documentos` + `oficios` + `termos` + `prestacoes_contas` + `eventos` juntos
levantou `AttributeError: 'ModelChoiceField' object has no attribute 'to_field_name'`. A suíte
completa e a suíte por app passavam; a combinação parcial não. A linha pedia:
**"Precisa ser reproduzido numa sessão limpa antes de virar trabalho."**

**Reproduzido em 06/08/2026, e não deu.** A combinação exata: **632 testes, OK**, em 22,4 s. A mesma
combinação com `--reverse`: **632 testes, OK**. `to_field_name` não aparece em lugar nenhum do
código do projeto, e não existe subclasse de `ModelChoiceField` que pudesse levantá-lo — todos os
usos são `forms.ModelChoiceField`/`ModelMultipleChoiceField` diretos. O mais provável é ter sido
corrigido de raspão por algum PR desde 05/08. **Se voltar a aparecer, é linha nova, com a
combinação que reproduziu.**

A sondagem não foi em vão: forçar dependência de ordem com `--reverse` na **suíte completa** achou
um vazamento de estado global de verdade, com causa nomeada — está no `NOVO-26`.

### NOVO-03 🔴 `NameError` em rota viva: `_CAMPO_LABELS` indefinido · COR · FEITO (05/08)

`prestacoes_contas/model_views.py` lia `_CAMPO_LABELS` em duas linhas; o nome estava definido no
fim de `prestacoes_contas/views.py`, de onde as quatro views tinham saído. `NameError` — HTTP 500 —
em quatro entradas: `GET /prestacoes-contas/modelos-texto/novo/?campo=…` e o redirect de sucesso de
**criar, editar e excluir** modelo de texto do RT (`_voltar_modelos_url`).

Nenhum teste tocava nessas views. Achado pelo `ruff` (`F821`) na primeira execução do gate do
`QA-07` — nenhum dos dois auditores próprios do projeto lê código como código, que é exatamente a
lacuna que o `QA-07` nomeia.
**Corrigido:** `_CAMPO_LABELS` mora em `model_views.py`, junto de quem lê.
`prestacoes_contas/test_modelos_texto.py` cobre as quatro views (7 testes) — provado falhando com
5 erros antes da correção.

### NOVO-04 🟡 Chave repetida no inventário do UI Lab apagava uma tela · COR · FEITO (05/08)

`ui_lab2/views.py`: `COMPONENT_USAGE` declarava `"status_badge"` duas vezes. Em literal de dict a
segunda ocorrência descarta a primeira em silêncio, então
`templates/components/ui/modals/confirm_delete.html` sumiu do inventário — e o inventário é o que
alguém consulta antes de mexer no componente. `page_header_status_chip` tinha o mesmo caminho
listado duas vezes.
Achado pelo `ruff` (`F601`) na mesma execução. **Corrigido:** listas unidas, duplicata removida.

### NOVO-05 ⚪ O que o `QA-07` deixou de fora: mais regras, formatação e tipo · MED · a dimensionar

O `QA-07` fechou **lint**. O enunciado dele nomeia três coisas — "lint, formatação ou tipo" — e as
outras duas seguem sem gate. Três frentes, deliberadamente separadas:

**1. Ampliar o conjunto do `ruff`.** Entrou `E4`, `E7`, `E9`, `F` (default) e `B`, todos em zero. O
que ficou de fora, medido em 05/08: `I` (ordem de import) 351 · `RUF` 330 · `UP` (pyupgrade) 206 ·
`S` (bandit) 128 · `SIM` 56. `I` e `UP` são reescrita mecânica ampla e precisam entrar sozinhos,
para não afogar um PR de conteúdo. Os números estão anotados em `ruff.toml`.

**2. `S` (bandit) merece ID próprio.** 128 achados de varredura de segurança não são higiene de
estilo e não devem ser triados junto com ordem de import.

**3. Tipo (`mypy`/`pyright`) não foi sequer medido.** Num código de ~93 k linhas sem anotação
sistemática, isso não é "ligar uma regra": é um projeto com fase de adoção gradual. Estimar antes
de agendar.

**Não confundir com dívida nova:** é dívida existente que o gate ainda não vigia.

### NOVO-06 ✅ RESOLVIDO · 🔴 A lista de justificativas mostra as de todas as áreas · COR · 1 d

`justificativas/selectors.py:20` — `listar_justificativas()` devolve
`Justificativa.objects.select_related(...)` **sem nenhum recorte de área**, e `views.py:83` pagina
esse queryset direto.

**Medido em 05/08** com 20.000 justificativas em três áreas: `page_obj.paginator.count` = **20.000**
contra **6.666** na área ativa do usuário. Não é lentidão — é o usuário de uma área vendo o
protocolo, o assunto e a justificativa das outras.

Agrava: `views.py:30`, `_oficios_summary_for_quick_add()`, monta o *picker* de ofícios com
`Oficio.objects` cru — **20.000 entradas contra 6.666 da área** — e o resultado vai para o HTML por
`json_script` (`templates/justificativas/index.html:15`). O dado de outra área não só é contado:
é entregue ao navegador.

**Complicador estrutural, e por isso 1 dia e não 0,25:** `Justificativa` **não tem campo `area`**.
`filter_queryset_by_area` não se aplica direto; o recorte precisa vir por `oficio__area` (ou por um
campo `area` novo, com migração e backfill — aí vira `DB`, não `COR`). A decisão entre os dois
caminhos é parte da tarefa.

> **Corrigido em 06/08. Eram quatro pontos, não dois — e dois deles não são de leitura:**
>
> | # | onde | classe |
> |---|---|---|
> | 1 | `selectors.listar_justificativas()` | leitura: a lista contava e renderizava as de todas as áreas |
> | 2 | `views._oficios_summary_for_quick_add()` | leitura: o *picker* ia inteiro para o HTML por `json_script` |
> | 3 | `forms.JustificativaQuickAddForm.oficios` | **escrita**: dava para criar justificativa em ofício de outra área |
> | 4 | `selectors.get_justificativa_by_id()` | **destrutivo**: `justificativa_excluir` apagava por `pk`, sem recorte |
>
> **Caminho escolhido: `oficio__area`, sem migração.** `filter_queryset_by_area` ganhou um parâmetro
> `campo` (default `"area"`, nada mudou para os outros 20+ chamadores). Com `oficio` obrigatório e
> um-para-um, a área é derivável; uma coluna `area` denormalizada seria uma segunda cópia que pode
> divergir da do ofício sem ninguém notar.
>
> O *picker* passou a ser montado **do queryset do próprio campo do formulário**, não de um queryset
> paralelo — é o que impede o resumo de voltar a divergir do que o formulário aceita, e é como
> `termos` e `ordens_servico` já faziam.
>
> **Medido pela régua do `PF-07`, em `justificativas:index` com 20.000 registros:**
> HTML **15.295 KB → 5.141 KB**, tempo **19,7 s → 5,7 s**. A queda é exatamente a razão de áreas
> (20.000 → 6.666 ofícios), o que confirma que o tamanho era 100% o *picker* sem recorte.
> Tetos baixados em `scripts/tetos_desempenho.json`.
>
> `justificativas/tests/test_vazamento_entre_areas.py` — 9 testes, provados falhando (6 falhas +
> 1 erro) antes da correção.

### NOVO-07 ✅ RESOLVIDO · 🟠 A tela de justificativas cresce com a tabela inteira: 15 MB de HTML · MED · 0,5 d

Consequência direta do `_oficios_summary_for_quick_add()` do `NOVO-06`: sem recorte e **sem
limite**, ele serializa todo ofício do banco no HTML da lista.

**Medido:** 289 KB com 200 ofícios, **15.295 KB com 20.000** — e 19,7 s de resposta. Cresce linear
com a tabela, não com o que a página mostra (15 linhas nos dois casos). É a única rota medida cujo
HTML escala com volume.

O recorte por área do `NOVO-06` divide por três; não resolve. O *picker* precisa de paginação ou de
busca sob demanda, como os outros seletores do sistema já fazem.

> **Escopo corrigido em 06/08, depois do `NOVO-06`.** Duas coisas mudaram no enunciado:
>
> **1. Continua aberto, com número novo:** 15.295 KB → **5.141 KB** com 20.000 ofícios. Melhorou
> 3×, e 5 MB de HTML numa lista de 15 linhas segue sendo defeito.
>
> **2. Não é de justificativas — são três telas.** `termos` e `ordens_servico` montam o mesmo
> resumo (`termos/views.py:423`, `ordens_servico/views.py:351`) e serializam no HTML pelo mesmo
> `json_script`. Elas já recortavam por área, então nunca vazaram — mas o payload delas também
> cresce com o número de ofícios **da área**, sem limite. A régua não pegou porque mede a lista de
> cada domínio, e essas duas são telas de formulário.
>
> **Precisa de decisão de interface antes de virar trabalho:** limitar aos N mais recentes é uma
> regressão funcional silenciosa (some ofício antigo do seletor, e nenhum teste pega); busca sob
> demanda por endpoint é o certo e é trabalho de front. **Não decidir e só limitar seria pior que
> deixar como está.**

> **RESOLVIDO em 06/08/2026** (`claude/novo-07-picker-sob-demanda`). A decisão de interface foi
> tomada — **busca sob demanda por endpoint**, não limite de N — e as três telas foram convertidas.
>
> Medido no servidor de desenvolvimento, com **60 ofícios na área**:
>
> | tela | `<option>` no HTML | blob do `json_script` | página |
> |---|---:|---:|---:|
> | `termos:novo` | 61 → **1** | 45,3 KB → **0 KB** | 92,3 KB → **36,9 KB** |
> | `ordens_servico:nova` | 60 → **0** | 47,4 KB → **0 KB** | 99,9 KB → **42,2 KB** |
>
> E pela régua do `PF-07`, que é a que prova que parou de crescer com a tabela:
>
> | `justificativas:index` | 200 ofícios | 20.000 ofícios |
> |---|---:|---:|
> | antes (`NOVO-06`) | 199,6 KB | **5.398,3 KB** |
> | depois | 142,1 KB | **142,5 KB** |
>
> A diferença entre os dois volumes era 27×; agora é 0,3%. Consultas da rota: 17 → **10**. Teto do
> formulário de termo: 26 → **24** consultas — medido depois do `NOVO-08` entrar no `main`, que
> já havia baixado a mesma catraca de 28 para 26 por outro motivo. As duas quedas somam.
>
> **O plano errou uma coisa e o navegador pegou:** ele mandava ligar o modo remoto em
> `components/picker.js`. Nenhum dos três seletores de ofício é um `picker.js` — os três são
> artesanais, em `js/pages/`, e o `<select>` deles nem tem `data-entity-picker`. A mudança em
> `picker.js` foi revertida (seria código morto, §3.6) e o que é comum às três virou
> `static/js/components/document-search.js`. Só se descobre abrindo a tela.
>
> **Mudança de comportamento a registrar:** abrir o seletor sem digitar nada mostrava **todos** os
> ofícios da área; agora mostra os 30 mais recentes, e digitar refina no servidor. É o preço da
> decisão tomada, e está visível — não é a regressão silenciosa que o enunciado temia.
>
> **Fora do escopo, com ID próprio:** `dmv-oficio-prefill`
> (`templates/prestacoes_contas/partials/_dmv_motorista_body.html:42`) é o quarto consumidor e tem
> a mesma doença, mas é um `<select>` nativo — resolver exige trocar o controle por um seletor de
> busca, o que é mudança de interface.

### NOVO-08 ✅ RESOLVIDO · 🟠 N+1 por linha em três listas: 296, 138 e 55 consultas · MED · 2–3 d

Medido pela régua do `PF-07`, **igual nos dois volumes** — é por linha da página, não por tamanho do
banco:

| rota | consultas | linhas | por linha | onde |
|---|---:|---:|---:|---|
| `eventos:index` | 296 | 20 | ~15 | 123× `cadastros_estado` + 105× `cadastros_cidade` + 20× `justificativas_justificativa` + 20× `planos_trabalho_planodestino` |
| `prestacoes_contas:index` | 138 | 20 | ~7 | a medir por família |
| `termos:index` | 55 | 15 | ~3,7 | o "54 por página" do ciclo antigo, nunca corrigido |

`eventos:index` é o pior e o mais claro: o cartão resolve estado e cidade de cada destino sem
`select_related`/`prefetch_related`. Some 228 das 296.

**Não estava visível na linha de base** porque a linha de base mediu com o banco vazio — é
exatamente o buraco que o `PF-07` existiu para tapar.

> **Corrigido em 06/08.** Medido pela régua do `PF-07`, volume 200 (a contagem é igual nos dois
> volumes — é por linha da página, não por tamanho do banco):
>
> | rota | antes | depois |
> |---|---:|---:|
> | `eventos:index` | 296 | **34** |
> | `prestacoes_contas:index` | 138 | **20** |
> | `termos:index` | 55 | **11** |
>
> **eventos (−262):** o `prefetch_related` cru dos trechos não trazia nenhum dos quatro FKs de
> cidade/estado que o card lê (−160); o caminho `destinos__cidade__estado` trazia o estado *da
> cidade*, mas o presenter lê `d.estado`, o FK do próprio destino (−40); `justificativa` é
> OneToOne reverso lido por ofício (−20); `PlanoTrabalho.destino_display` e
> `OrdemServico.destinos_display` caíam no ramo que consulta porque o prefetch não existia
> (−20 cada). O `order_by("nome")` no `Prefetch` dos destinos da OS é carga útil: a propriedade
> mostra os três primeiros, e sem ele apareceriam outros três.
>
> **prestações (−118):** `_destino_display_oficio` percorria `roteiro.destinos.all()` por card e
> tocava `d.cidade` e `d.estado` de cada um (−99 líquidas); `get_configuracao_sistema()` era
> chamado dentro de cada card, e a configuração é por área — igual para os 20 (−19). O `Prefetch`
> ficou na forma exata do selector irmão (`oficios/selectors.py:72-75`), que alimenta o **mesmo**
> presenter.
>
> **termos (−44):** `servidores_efetivos()` clonava o related manager e **descartava** o cache do
> prefetch, então a consulta do prefetch era 100% desperdiçada e cada linha pagava duas (−30); e
> `termo_cadastro_assinado_info` buscava o artefato assinado uma vez por linha (−14). O
> `mapa_..._em_lote` é irmão do `mapa_artefatos_pdf_termo_cadastro` que já existia por termo.
> **Confirma parcialmente o ciclo de julho:** o "54 por página" era real, mas a causa apontada
> (`termo_cadastro_assinado_info`) era um terço do problema, não o todo.
>
> **Catracas:** `termos` 55→11 e 28→26, `eventos` (detalhe) 78→77, e os tetos da régua para as
> três rotas. `prestacoes_contas` não tinha **nenhum** `assertNumQueries` — ganhou
> `test_orcamento_de_queries.py` com duas asserções: o número exato e, mais importante, que
> **dobrar as linhas não muda a contagem** — a propriedade que define "não é N+1" e que sobrevive
> a alguém atualizar a constante sem pensar. Provada mordendo: sem o `Prefetch`, 34≠20 e o custo
> sobe de 34 para 49 ao dobrar.
>
> **Achado sobre a própria régua, e corrigido junto:** o semeador dava **um** destino por OS e
> **zero** `PlanoDestino`. O corte `[:3]` de `destinos_display` e o ramo ciente de prefetch de
> `destino_display` nunca eram exercitados — a régua media um caminho que produção não usa. Isso
> subiu oito tetos (ver o corpo do PR), todos por medir mais dado, nenhum por regressão.

### NOVO-09 ✅ RESOLVIDO · 🟠 Modelo de justificativa é global e o "padrão" de uma área derruba o das outras · DB · 1,5 d

`ModeloJustificativa` **não tem campo `area`** — ao contrário de `ModeloMotivoOficio`, que tem
(`oficios/models.py:345`) e cujo recorte o `BE-05` já tratou. Três consequências, em ordem de
gravidade:

1. **Efeito colateral entre áreas na escrita.** `models.py:27`:
   `ModeloJustificativa.objects.exclude(pk=self.pk).update(is_padrao=False)` — **sem filtro**.
   Marcar um modelo como padrão na área A **desmarca o padrão de todas as outras áreas**. O
   equivalente em `ModeloMotivoOficio` faz `.filter(area=self.area)` (`oficios/models.py:380`).
2. **O texto de outra unidade entra no documento.** É o mesmo argumento do `BE-05`: o `texto` do
   modelo é copiado para a justificativa e vai literalmente para o documento gerado, com a
   terminologia e os nomes de outra área.
3. **`nome` é `unique=True` global**, então uma área não consegue criar modelo com nome que outra
   já usou.

**Correção:** campo `area`, migração com backfill, `unique` virando `(area, nome)`, e o `is_padrao`
recortado. É `DB`, não `COR` — cai no limite 4 do `AGENTS.md` (migração exige checagem de dados),
e por isso ficou fora do PR do `NOVO-06`.
**Decisão humana antes de executar:** os modelos existentes hoje são compartilhados de fato entre
as áreas? Se forem, o backfill precisa **duplicar** cada modelo por área, não escolher uma.

> **Corrigido em 06/08. Decisão do usuário: duplicar por área** — os modelos de hoje servem a
> todas as unidades, e atribuir todos a uma só deixaria as demais sem texto até recadastrarem.
>
> O model virou espelho de `ModeloMotivoOficio`, e não um desenho novo: mesmo campo `area`, mesmo
> índice `(area, ordem, nome)`, as mesmas quatro `UniqueConstraint` condicionais (global × por
> área — quatro, e não um `unique_together`, porque em SQL `NULL != NULL` e um `unique(area, nome)`
> puro deixaria passar duas linhas globais homônimas) e o mesmo recorte do `is_padrao`. O
> `create`/`update` do catálogo atribui a área ativa, como `oficios.services.criar_modelo_motivo`.
>
> **Um defeito na própria migração, achado drilando o rollback e não em produção.** A **volta**
> morria com `cannot ALTER TABLE ... because it has pending trigger events`: o `RunPython` mexe nas
> linhas e, na mesma transação, o Django tenta recriar o `unique` do nome. Resolvido com
> `SET CONSTRAINTS ALL IMMEDIATE` ao fim de cada sentido, guardado por `vendor == "postgresql"`.
> Sem isso, um deploy que falhasse depois desta migração teria o rollback do `QA-03` quebrado.
>
> **Drill contra dado de verdade** (3 áreas, 2 modelos globais, um deles padrão):
> ida → 6 linhas, uma por área, `is_padrao` preservado **por área**; volta → 2 globais, sem perda;
> e um modelo criado numa área **depois** da migração **sobreviveu ao rollback** — a volta só apaga
> a cópia ainda idêntica a uma linha da primeira área.
>
> `justificativas/tests/test_modelo_por_area.py` — 10 testes, provados mordendo: sem o filtro de
> área no `is_padrao`, 1 reprova; sem o recorte nos selectors, 6 reprovam.

### NOVO-10 ✅ RESOLVIDO · 🔴 Entrar com a senha certa devolve 500: o login da aplicação está quebrado · COR · 0,5 d

`core/views.py:993`, `LoginView.form_valid`: `cache.delete(self._rate_key())`. O método
`_rate_key` **não existe** — ele saiu de `LoginView` quando a regra de limite virou
`core/login_throttle.py` no `QA-01`, e esta chamada ficou para trás.

**Medido:** POST em `/login/` com a senha correta →
`AttributeError: 'LoginView' object has no attribute '_rate_key'` → 500. Reproduzido no `main`
(`993e14c5`) com `curl`, antes de tocar em qualquer coisa. Senha **errada** funciona normalmente,
porque o caminho quebrado é só o de sucesso.

Por que a suíte inteira passava com a porta de entrada arrombada:

- todo teste de tela entra por `self.client.force_login(...)`, que não passa por view nenhuma;
- o único teste de login **bem-sucedido** era `test_login_correto_no_admin_continua_funcionando`,
  e o admin entra pelo wrapper `core/admin_login.py`, não por esta view;
- `test_login_da_aplicacao_bloqueia_no_mesmo_ponto` usa esta porta, mas só com senha errada.

Ou seja: havia teste para "errar a senha 6 vezes" e nenhum para "acertar a senha uma vez".

**Correção:** `login_throttle.chave_de_tentativa(self.request)`, que é a mesma chave que
`registrar_falha` usa — acertar a senha limpa o balde de falhas, que era a intenção original da
linha. Mais dois testes em `core/tests/test_login_throttle.py`, provados falhando com o exato
`AttributeError` antes da correção.

**Achado por acaso**, dirigindo o navegador para conferir o `NOVO-07`. Nenhum auditor apontaria:
não é ORM em view, não é CSS fora de token, e `ruff` não reclama de atributo inexistente
(`F821` só pega nome livre, não `self.x`). Fica a lição para o `PLANO_MESTRE`: caminho de sucesso
sem teste é caminho não coberto, por mais óbvio que pareça.

### NOVO-11 ✅ RESOLVIDO · 🟡 `NOVO` O auditor de ORM em view conta `.objects` dentro de docstring · QA · 0,5 d

> **RESOLVIDO em 07/08/2026.** `contar_orm_em_views` passou a contar sobre a árvore
> sintática (`contar_orm_no_codigo`, `ast.Attribute` com `attr` em
> `{objects, all_objects}` — a proteção do `BE-09` contra renomear preservada).
> A troca **não mudou o número**: 29 por regex e 29 por `ast`, mesmos apps, porque
> hoje nenhum módulo de view tem `.objects` em prosa — a folga que "ninguém sabia
> medir" era zero. A catraca segue em 29.
> `core/tests/test_view_module_boundaries.py::test_orm_em_prosa_nao_conta_e_orm_em_codigo_conta`
> é o teste que falharia antes: docstring e comentário fora, expressão de f-string
> dentro (para o `ast`, ela é código).

`scripts/audit_django_architecture.py`, `contar_orm_em_views`: casa
`re.compile(r"\.objects\b")` no **texto do arquivo**, sem distinguir código de prosa.

Consequência prática, medida no `NOVO-07`: a catraca caiu de 30 para 29 porque saiu uma ocorrência
que estava **dentro de uma docstring** — a frase "a versão anterior montava isto de
`Oficio.objects` cru", escrita no `NOVO-06`. Nenhuma consulta mudou de lugar.

Vale nos dois sentidos, e o pior é o segundo:

- **um comentário segura a catraca no alto**, então ela mede menos do que promete;
- **explicar em prosa um ORM que você acabou de tirar da view faz o número subir**, e o CI reprova
  um PR que está certo. Quem bater nisso vai reescrever o comentário em vez de olhar o código.

**Correção:** contar sobre a árvore sintática (`ast`), não sobre o texto — `ast.Attribute` com
`attr == "objects"`. Aí docstring e comentário deixam de existir para o contador. É o mesmo
caminho que `sync_document_generations_in_views` já poderia querer.

**Não é urgente e não é regressão:** a catraca continua sendo catraca, só que com uma folga que
ninguém sabe medir. Entra na fila de `QA` do plano mestre, não à frente de defeito funcional.

### NOVO-12 ✅ RESOLVIDO · 🔴 `NOVO` Nenhuma régua olha a configuração de produção — `SECRET_KEY` de 9 caracteres · QA · 1 d

> **RESOLVIDO em 07/08/2026**, nas duas pontas que o enunciado pedia, mais uma que
> ele não pedia mas o gate exigia:
>
> 1. **`core.E002` decidido: rebaixado a `core.W002`** (Warning). Produção roda
>    `DOCUMENTOS_DEFAULT_PDF_ENGINE=auto` e não tem unoserver no ar; um `Error`
>    insatisfazível travaria todo deploy — check que ninguém pode satisfazer não é
>    catraca, é ruído. O SLA real de geração continua medido no CI, com unoserver
>    de verdade ("Enforce real document generation SLA"). Quando produção subir o
>    unoserver, repromover a `Error` volta a ser catraca honesta.
> 2. **`python manage.py check --deploy --fail-level ERROR` no `deploy.yml`**,
>    logo após o checkout e o `pip install`, antes do `collectstatic` — com o
>    `.env` real carregado e protegido pelo rollback do `QA-03`. **Depois** do
>    checkout de propósito, e não junto das pré-checagens como o enunciado
>    sugeria: os checks têm de ser os do código que vai entrar no ar. Antes do
>    checkout, o código antigo — com `core.E002` ainda `Error` e produção em
>    `auto` — reprovaria o próprio deploy que corrige o check, e nenhum deploy
>    passaria mais.
> 3. **A ponta que o enunciado não via:** a `SECRET_KEY` fraca que motivou o ID é
>    `security.W009` — **Warning** — e o gate roda `--fail-level ERROR`; sem mais
>    nada, o gate não pegaria o próprio defeito que o motivou. `core.E003` promove
>    os critérios do W009 a `Error` no deploy (≥50 caracteres, ≥5 distintos, sem
>    prefixo `django-insecure-`). Provado nos dois sentidos: chave de 9 caracteres
>    reprova com exit 1; a configuração do CI passa limpa.
>
> A varredura de "variáveis que merecem falhar cedo" achou uma: `ALLOWED_HOSTS`
> vazia com `DEBUG=False` responde 400 a toda requisição e o Django só avisa com
> `security.W020` (Warning). `config/settings/prod.py` agora levanta
> `RuntimeError`, o mesmo padrão de `REDIS_URL`/`FIELD_ENCRYPTION_KEYS`.
> `CSRF_TRUSTED_ORIGINS` ficou de fora de propósito: vazia, o fluxo same-origin
> continua válido — falhar cedo ali seria adivinhar a topologia.
>
> Bônus para o `DB-02`: o gate imprime `core.E001`/`core.W001` a cada deploy — a
> medição em produção que o `NOVO-34` pedia, colhida onde o seed convive com dado
> real.

**Medido em 06/08/2026, no VPS, com `python manage.py check --deploy`:**

```
comprimento           : 9   (o Django quer >= 50)
caracteres distintos  : 8
prefixo inseguro      : False
```

Nove caracteres assinando cookie de sessão e token de recuperação de senha. Com essa chave dá para
**forjar sessão de qualquer usuário**, superusuário incluído. Não era o placeholder do template —
era uma chave curta escolhida à mão, que é justamente o caso que nenhum `grep` por
`troque-por-...` pega.

**Corrigido no servidor no mesmo dia** (`secrets.token_urlsafe(64)`, serviços recarregados, login
reconferido). O defeito que fica **não é a chave** — é o motivo de ela ter durado tanto.

## O buraco

As cinco réguas deste ciclo medem **código e banco**, e nenhuma olha a configuração do ambiente:

| régua | o que mede |
|---|---|
| `ruff` (`QA-07`) | sintaxe e nomes livres em `.py` |
| `audit_django_architecture` | ORM em módulo de view |
| `audit_frontend_standards` | CSS fora de token |
| `build_shell_bundles --check` | bundle desatualizado |
| `medir_desempenho` (`PF-07`) | consultas e KB por rota |

Nenhuma delas pode achar isto, porque o `.env` de produção não existe no CI — e é onde o defeito
mora. Os dois achados desta sessão saíram de **uma pessoa digitando um comando**, não de gate:
`REDIS_URL` ausente e `SECRET_KEY` fraca.

## Por que não é só "rodar `check --deploy` no CI"

O CI não tem — e não deve ter — o `.env` de produção. O lugar certo é **na VPS, dentro do
`deploy.yml`, antes do `migrate`**, junto das pré-checagens que já existem
(`: "${DB_NAME:?...}"`). Ali a config real está carregada e a falha aborta antes do `git checkout`,
que é a única hora em que abortar é barato.

**O que impede ligar hoje, e é preciso resolver antes:** `check --deploy` reprova agora com
`core.E002` — produção está em `DOCUMENTOS_DEFAULT_PDF_ENGINE=auto` e o check exige `unoserver`.
Ligar o gate sem resolver isso trava todo deploy. São duas coisas, nesta ordem:

1. **decidir o `core.E002`**: subir o unoserver em produção e ligar as duas variáveis, **ou**
   rebaixar o check de `Error` para `Warning` com justificativa. Hoje ele é `Error` e produção o
   viola — um check que ninguém pode satisfazer não é catraca, é ruído.
2. **só então** acrescentar `python manage.py check --deploy --fail-level ERROR` ao `deploy.yml`,
   antes do `collectstatic`.

## O que a régua nova precisa cobrir, além do que o Django já vê

`check --deploy` pega `SECRET_KEY` fraca, `DEBUG=True`, cookies sem `Secure`. **Não** pega variável
ausente que só quebra em tempo de execução — `REDIS_URL` só falhou porque o `prod.py` levanta
`RuntimeError` na importação (`QA-02`). O padrão que funcionou é esse: **falhar cedo, no
`settings`, em vez de degradar calado.** Vale varrer que outras variáveis de produção merecem o
mesmo tratamento.

**Prioridade:** 🔴 pelo que o defeito original permitia, não pelo trabalho de fechá-lo. A chave já
foi trocada; o gate é para a próxima.

### NOVO-13 🟠 `NOVO` A limpeza de rascunhos apagava trabalho em curso de outra pessoa da mesma área · COR · 0,5 d

Achado ao consertar o `DB-03`, e é a metade do defeito que o catálogo não viu.

`roteiros/services/roteiro_editor.py:_limpar_rascunhos_vazios` varria o banco atrás de roteiro sem
sede, sem destino, sem trecho e sem saída — sobra de corrida do autosave — e apagava. O enunciado
do `DB-03` diz que faltava recorte de área, e faltava. **Mas recortar por área não bastava**, e a
razão é que `Roteiro` **não tem dono**: só `area` (`roteiros/models.py:46`). Não há campo de
usuário, nem em `Roteiro` nem em lugar nenhum do editor.

Consequência: duas pessoas da **mesma** área criando roteiro ao mesmo tempo. A primeira abre o
formulário — o autosave grava um rascunho ainda vazio. A segunda salva o dela, a limpeza roda, e
o rascunho da primeira é apagado. Sem aviso, sem desfazer, e sem nada na tela sugerindo que
aconteceu: rascunho vazio não aparece em `listar_roteiros` (`roteiros/selectors.py:42` já exclui
roteiro com zero destinos), então a pessoa só descobre quando o formulário para de salvar.

**Corrigido junto com o `DB-03`, e digo por quê** em vez de abrir PR separado: são as mesmas três
linhas de `filter()`. Consertar só o recorte de área e deixar a perda de dado da mesma área para
depois seria entregar uma função que eu acabei de reescrever sabendo que ela ainda destrói
trabalho alheio.

**A correção é um limite de idade**, não um dono: `IDADE_MINIMA_RASCUNHO_ORFAO = 2 horas`. Órfão
mais novo que isso pode ser de alguém editando agora. Duas horas é folgado de propósito — o custo
de esperar é zero, porque o órfão é invisível na interface de qualquer jeito, e o custo de apagar
cedo demais é trabalho perdido.

**O que isso não resolve, e fica anotado:** com o limite, duas pessoas que abram o formulário e
demorem mais de duas horas ainda colidem. A correção completa é `Roteiro` ter dono — campo de
usuário criador —, o que é migração e entra em `DB-02`/Fase 2 quando o modelo for mexido de todo
jeito. Registrado aqui para não se perder.

### QA-17 ⚪ Treze PRs abertos sem triagem · MED · 1 d

PRs #4, #7, #10, #13, #14, #16, #27, #32, #44, #58, #137, #144 são de maio–julho/2026; #178 é de
05/08. O plano antigo já registrava que #27, #32 e #44 foram resolvidos por outros caminhos, e os
PRs seguem abertos.
**Não foi possível medir daqui se ainda aplicam:** o clone desta sessão é *shallow* (128 commits),
então `git diff main...branch` responde "no merge base" para todos. Precisa de histórico completo
ou da API do GitHub. **Decisão humana.**

---

### NOVO-19 ✅ RESOLVIDO (047090f) · 🟡 `NOVO` O JS-06 mirava a raiz do picker; as partes eram 34 seletores a mais · COR · 1 d

O enunciado do `JS-06` conta os 10 `classList.contains("cv-search-picker")` da raiz. Ao abrir o
trabalho, a varredura achou mais **34 seletores de parte** (`.cv-search-picker__input`, `__clear`,
`__control`, `__dropdown`, `__driver-toggle`, `__selected-card`…) em 8 arquivos, mais 1
`classList.contains("cv-search-picker__input")`.

Superfície real: **45 sites em 11 arquivos**, não 10 em 7. Os 34 quebram numa renomeação do bloco
exatamente como os 10 — deixá-los de fora entregaria o pré-requisito da fase 7 pela metade.

Fechado junto do `JS-06`: `picker.js` marca `data-entity-picker-part` em 16 partes e expõe
`CV.picker.part/parts/closestPart`. Conferido no navegador em 5 telas, com paridade exata entre a
contagem por atributo e por classe, e o ciclo completo (digitar → 3 opções → escolher → remover)
funcionando pelo contrato novo.

---

### NOVO-14 🟡 `NOVO` Doze `classList.contains` ainda leem classe de componente como condição · QA · 1 d

Sobra do `JS-06` fora do picker, agora com teto no auditor (`css_class_as_logic`):

| arquivo | ocorrências | classe |
|---|---:|---|
| `static/js/pages/roteiros/editor/index.js` | 6 | `trecho-tempo-viagem-hhmm`, `trecho-tempo-adicional-hhmm` |
| `static/js/cv-select.js` | 2 | `cv-action-dropdown--open`, `cv-filter-dropdown--open` |
| `static/js/components/overlay.js` | 1 | `cv-action-menu--open` |
| `static/js/components/icon-tooltips.js` | 1 | `cv-icon-btn--field-manage` |
| `static/js/components/picker-select.js` | 1 | `cv-custom-select__option--selected` |

Classe de **estado** (`is-*`, `has-*`) fica de fora da regra de propósito: é vocabulário de
comportamento, não nome de componente, e não impede renomear o CSS.

**Fila:** as 6 do editor saem com `BE-11` (fase 6); as outras 6 com a reconstrução do CSS (fase 7),
junto de `HT-08`. Enquanto isso o teto impede que o número suba.

---

### NOVO-15 🟡 `NOVO` Quatorze `innerHTML` com dado dinâmico sem `escapeHtml` · QA · 1–2 d

Achado ao escrever a regra do `JS-05`. **Nenhum é XSS provado** — a maioria interpola constante de
ícone declarada no próprio arquivo (`ROUTE_AVATAR_ICON`, `DOC_AVATAR_ICON`, `svgChevron()`), e
`gdrive_config.js` já escapa os dados desde o `JS-01`. São 14 linhas em 10 arquivos, com teto por
arquivo no auditor.

> **Correção de número.** A primeira varredura desta sessão contou 42. Estava errada: casava
> `innerHTML` com qualquer `+` ou crase na mesma linha, então somava as 26 limpezas
> `innerHTML = ""` e as 4 linhas que já chamam `escapeHtml`. Medir a expressão inteira, até o `;`
> de nível zero, dá **14**. O teto do auditor usa o número medido.

O valor da regra não é a dívida de hoje — é impedir que o próximo `innerHTML` com dado de usuário
entre sem revisão, que é como o `JS-01` nasceu.

---

### NOVO-16 ✅ RESOLVIDO (c6dd81d1) · `NOVO` O markup do picker está copiado à mão em 3 templates e 5 arquivos JS · QA · 2–3 d

O `JS-06` cortou a dependência do **JavaScript** com a classe do picker. Sobrou o outro lado: há
markup que **imita** o picker, escrito à mão, e que a renomeação da fase 7 quebraria visualmente.

- **Templates** com a raiz `cv-search-picker` e as partes BEM escritas à mão:
  `termos/partials/_oficio_body.html`, `ordens_servico/partials/_oficios_body.html`,
  `justificativas/partials/_oficio_picker.html` (mais `eventos/partials/_documento_panel.html` e
  `roteiros/partials/roteiro/_fonte_body.html`, só com as partes). Medido no navegador: em
  `/termos/novo/` há 5 elementos com a classe e 4 com `data-entity-picker-root` — o quinto é o
  template.
- **JS** que monta o "cartão de rota relacionada" com as classes do picker, em 5 cópias:
  `ordens-servico-form.js`, `termos-form.js`, `justificativas-index.js`, `eventos-detalhe.js`,
  `roteiros/editor/index.js`. Mais `oficios-transporte.js`, que reimplementa o picker inteiro.

**Fila:** fase 7, junto de `HT-15` (bloco `cv-itinerary` duplicado em 5 apps) — é a mesma classe de
defeito. Não é bloqueio para F2/F3.

---

### NOVO-20 🟠 `NOVO` `CELERY_TASK_ALWAYS_EAGER` faz a suíte rodar a tarefa dentro do request · QA · 1 d

`config/settings/test.py:64` liga `CELERY_TASK_ALWAYS_EAGER = True`. Em teste, toda tarefa executa
no mesmo thread e no mesmo instante do request que a disparou — com
`core/middleware.py:17` (`_local.request`) populado. Em produção o worker não tem nada disso.

**Efeito:** a classe inteira de regressão "código que depende de contexto ambiente de request"
é **inalcançável por teste**. Foi o que decidiu o desenho do `BE-09`: um `AreaScopedManager` que
recortasse fora de request faria `documentos/tasks.py:33` devolver `None` — engolido pelo
`if oficio is None: return` da própria task — e a geração de PDF viraria no-op silencioso, sem log,
sem retry, com os 1.490 testes verdes. Os 12 lookups de `integracoes/google_drive/tasks.py` têm a
mesma forma.

**Correção:** um helper `sem_request()` público (hoje vive em
`core/tests/test_area_scoped_manager.py`) e a regra de que toda tarefa Celery com efeito de dados
ganha ao menos um teste dentro dele. Alternativa mais forte, e mais cara: um grupo de testes com
`CELERY_TASK_ALWAYS_EAGER = False` e worker de verdade.

**Prioridade:** 🟠 pelo que ela esconde, não pelo trabalho de fechá-la.

---

### NOVO-21 🟡 `NOVO` Campo de FK gerado por `ModelForm` ignora o recorte por área · AUD · 1 d

Decisão deliberada do `BE-09`: `Meta.default_manager_name = "all_objects"`, para não neutralizar o
guarda m2m de `core/tenancy.py:116`, o check `core.E001` de `core/checks.py:50`, os dois comandos de
backfill, o admin e `validate_unique`. O preço é que `ForeignKey.formfield`
(`db/models/fields/related.py:1213`) e `ManyToManyField.formfield` (`:2044`) usam `_default_manager`
— então um `ModelForm` que **não** declare `queryset` explícito continua oferecendo todas as áreas.

Não é regressão: é o comportamento de hoje, que o `BE-09` deliberadamente não fecha. `BE-04` e
`BE-05` foram exatamente essa família de defeito, encontrados um a um.

**Medir antes de classificar a severidade:** quantos `ModelForm` sobre modelo com `area` dependem
do queryset auto-gerado. O repositório já aplica `filter_queryset_by_area` em 64 linhas de
`forms.py`, então a lacuna pode ser pequena — ou pode não ser. A régua natural é estender
`scripts/audit_area_scoped_managers.py` com essa varredura.

### NOVO-28 🟠 `NOVO` A suíte desliga a configuração de numeração e não enxerga o piso do ofício · QA · 0,5 d

`config/settings/test.py:36` põe `OFICIO_NUMERACAO_USAR_CONFIGURACAO = False`; em produção é
`True` (`config/settings/base.py:179`). Com ele desligado, `Oficio.get_next_available_numero`
**nem consulta** `ConfiguracaoNumeracaoOficio` e `piso` é sempre 1.

**Efeito:** o piso de numeração de ofício — inclusive o global semeado por
`oficios/migrations/0017` (`area=None, ano=2026, numero_inicial=75`), do qual todo ofício de 2026
depende — não tem cobertura nenhuma por padrão. Descoberto ao migrar `oficios` no `BE-09`: o site
mais perigoso da fatia (a união `Q(area=area) | Q(area__isnull=True)`) era **inalcançável pela
suíte**, e um recorte errado ali reiniciaria a numeração em produção com os testes verdes. Os
testes da fatia usam `override_settings` para alcançá-lo.

**Terceira ocorrência da mesma família em um dia**, e é o padrão que vale registrar: o ambiente de
teste é mais permissivo que o de produção, e é justamente a diferença que esconde o defeito. As
outras duas: `NOVO-20` (`CELERY_TASK_ALWAYS_EAGER` roda a task dentro do request) e a catraca do
`BE-09`, que caía em `config.settings.dev` e só quebrava **sem** `.env`.

**Correção:** decidir se o `False` ainda serve a algum teste — ele foi posto para tornar a
numeração previsível — e, se servir, invertê-lo (`True` por padrão, `False` só onde for pedido),
para que o padrão da suíte seja o de produção.

---

### NOVO-30 🟠 `NOVO` Três consultas de roteiro sem recorte de área — fechadas pelo `BE-09` · AUD · 0 d

Apareceram na varredura da fatia 3 do `BE-09`, não no catálogo original. Nenhuma tinha filtro de
área nenhum:

- `roteiros/roteiro_logic.py:614` (`_get_roteiro_saved_routes`) — o picker de "roteiros salvos" do
  ofício filtrava só por `status=FINALIZADO`. Uma área via os roteiros finalizados de **todas**.
- `roteiros/roteiro_logic.py:1088` — validava o `roteiro_evento_id` submetido por `pk` e mais nada;
  bastava mandar o id de um roteiro alheio para ele ser aceito. (Havia segunda barreira em
  `vincular_roteiro_ao_oficio_sem_copia`, que compara as áreas — mas ela é a última, não a primeira.)
- `roteiros/services/roteiro_editor.py:302` (`encontrar_roteiro_duplicado`) — filtrava por sede e
  destinos. O estrago não seria só ver: a tela usa o retorno para oferecer **sobrescrever** aquele
  roteiro.

**Efeito:** os dois primeiros expõem sede, destinos e datas de viagem de outra unidade; o terceiro
permite destruir trabalho alheio.

**Correção:** nenhuma linha de correção própria — o `AreaScopedManager` da fatia 3 fecha os três,
e é a demonstração do que o `BE-09` prometia: esquecer o filtro deixa de ser vazamento. Cobertos
por `roteiros/tests/test_recorte_por_area_fatia3.py::VazamentosQueOManagerFechaTests`, que
reprovam se o manager for retirado.

**0 dias** porque o trabalho já está feito; a linha existe para o defeito ficar registrado, e não
para ser executada.

---

### NOVO-27 🟡 `NOVO` `oficios/selectors.py:listar_roteiros_para_oficio` não tem chamador · BE · 0,25 d

Varredura da fatia 3: `grep -rn "listar_roteiros_para_oficio"` devolve **só a própria definição**
(`oficios/selectors.py:162`). Devolve `Roteiro.objects.order_by("-created_at")` sem recorte de área
— hoje inofensivo, porque ninguém chama, e recortado a partir da fatia 3 de qualquer forma.

Não removido aqui por `AGENTS.md` §3.6: código morto sai com a prova de varredura no PR, e isso é
assunto da fase 9, não do `BE-09`.

---

### NOVO-29 🟠 `NOVO` Duas sessões alocam ID `NOVO-` sem reserva e colidem · QA · 0,5 d

Terceira colisão em um dia. Cada sessão pega "o próximo número livre" lendo o catálogo, e duas
sessões que leem ao mesmo tempo pegam o mesmo. Já aconteceu com `NOVO-13` (desfeita renumerando o
do `JS-06` para `NOVO-19`) e agora com **`NOVO-22`, `NOVO-23` e `NOVO-24`** ao mesmo tempo: a
sessão paralela registrou `applyingState`, exclusão de documento assinado e `.then` solto; esta
registrou numeração, consultas de roteiro e selector morto.

**Efeito:** o ID deixa de identificar. Um PR que cita `NOVO-22` passa a ser ambíguo, e o histórico
de "por que isto foi feito" — que é o valor do catálogo — se perde. Pior: a colisão só aparece no
merge, quando os dois lados já escreveram corpo de PR e mensagem de commit com o número errado.

**Correção:** trocar o contador global por um ID que não precise de coordenação. Por exemplo,
prefixo por frente (`NOVO-BE-07`, `NOVO-QA-11`) ou sufixo da data de registro
(`NOVO-2026-08-06-A`). Qualquer esquema serve desde que duas sessões cheguem ao mesmo número
**só** quando estiverem falando do mesmo defeito.

**Enquanto isso:** conferir `grep "^### NOVO-" docs/CATALOGO_DEFEITOS_2026-08.md | tail` **imediatamente
antes** de escrever a entrada, e renumerar as próprias, nunca as alheias — quem chega depois cede.

---

### NOVO-37 ✅ RESOLVIDO · ⚪ `NOVO` `apresentar_acoes_oficio` é construído por card e nunca renderizado · QA · 0,25 d

`oficios/list_views.py:59` faz `card["actions"] = apresentar_acoes_oficio(...)` para cada card da
lista. Nenhum template lê `card.actions`: o único que consumiria, `list_card_actions.html`, não é
incluído por arquivo nenhum do projeto — conferido por grep.

São 20 cards × 3 `reverse()` jogados fora por requisição, na página que o `PF-05` cronometra.

**Como apareceu:** o `test_lista_visualizar_documento_aponta_para_etapa_documentos` afirmava que a
lista continha `oficios:wizard_documentos`, e passava por acidente — `/oficios/1/documentos/` é
prefixo de `/oficios/1/documentos/pdf/`, que é o link de baixar. O link do wizard nunca esteve no
HTML da lista. O `PF-04` moveu os itens de menu para o fragmento, a asserção quebrou, e aí o teste
vacuoso apareceu. O teste foi corrigido para afirmar a URL inteira; a função morta ficou.

**Correção:** apagar a atribuição e, se não sobrar chamador, a função — com a prova de grep que o
`AGENTS.md` §3.6 exige. Não entrou no `PF-04` porque é outro defeito e o §3.6 pede PR próprio.

**Fechado em 07/08.** A afirmação original era imprecisa e a verificação corrigiu: **três** templates
leem `card.actions` — `components/cards/document_card.html`, `components/lists/main_list_card.html` e
`components/ui/lists/list_card_actions.html`. Nenhum está no caminho da lista de Ofícios, que vai por
`list_page_cards.html` → `oficios/partials/oficio_list_card.html` → `entity_card.html`, e este não lê
`actions`. Dos três, `document_card.html` só é alcançado por `list_grid.html`, incluído apenas por
`dev/ui_lab/cards.html`; os outros dois não são incluídos por arquivo nenhum.

**Prova de que era morto:** o HTML da lista, com o `csrf` normalizado, é **byte a byte idêntico**
antes e depois — 170.161 bytes, mesmo `sha256`. Consultas e nós de elemento também não se mexeram.
O tempo não mudou de forma mensurável (86,7 → 88,4 ms de mediana; a diferença é ruído, não ganho).

`main_list_card.html` e `list_card_actions.html` ficam órfãos e são material de `UI-01`, não deste ID.

---

### NOVO-38 ✅ RESOLVIDO · 🟡 `NOVO` O fragmento de menus custa 30 consultas para um card · BE · 0,5 d

`oficios:card_menus` (`PF-04`) chama `apresentar_oficio_card` inteiro para montar 3 menus: **30
consultas e 16,3 ms** por card. A lista faz 17 consultas para 20 cards.

A conta por requisição: `cadastros_cidade` 6, `cadastros_estado` 6, `cargo` 3, `unidade` 3,
`servidor` 2 — 20 das 30 são cabeçalho e linhas de servidor que o fragmento nem renderiza.

**Foi decisão consciente, não descuido.** O caminho alternativo — um presenter só de menus — faria
o menu poder divergir da lista sem ninguém notar, que é exatamente o que
`test_paridade_de_acoes_com_o_caminho_embutido` existe para impedir. Pagar consulta e manter a
paridade por construção é o lado certo dessa troca **enquanto for um domínio só**.

**Efeito real:** abrir um menu passou de 0 para 30 consultas. Numa visita típica (1 ou 2 menus) a
página sai de 17 para ~47; abrir todos os 20 cards daria 617.

**Correção:** `select_related`/`prefetch_related` no caminho do fragmento, ou um argumento que
mande o presenter pular cabeçalho e linhas. Melhor resolver quando os outros seis domínios
migrarem, para o desenho nascer um só.

**Fechado em 07/08**, com os cinco endpoints já existindo — foi o que permitiu ver que havia **dois
problemas diferentes** debaixo do mesmo número:

| endpoint | antes | depois | |
|---|---|---|---|
| `oficios:card_menus` | 30 | **12** | N+1 real |
| `prestacoes_contas:card_menus` | 28 | **15** | N+1 real |
| `eventos:card_menus` | 59 | **45** | quase tudo custo fixo |
| `ordens_servico:card_menus` | 19 | 19 | custo fixo |
| `planos_trabalho:card_menus` | 12 | 12 | custo fixo |
| `termos:card_menus` | 9 | 9 | já estava certo |

**1. N+1 de verdade**, em `oficios` e `prestacoes_contas`: os selectors de registro único não tinham
a carga que os de lista já tinham desde o `NOVO-08`, e o presenter percorre destinos e trechos
tocando `cidade` e `estado` de cada um. Corrigido copiando a forma do selector de lista — a página
de detalhe ganha junto.

**2. Custo fixo de `prefetch_related`, que não é defeito.** Cada nível de `__` numa cadeia de
prefetch é uma consulta. `queryset_evento_detalhe` tem ~20 entradas, várias com três ou quatro
níveis. Numa lista de 20 cards isso se amortiza — `eventos:index` faz 34 consultas para a página
inteira. Para **um** registro, o mesmo custo não amortiza.

Ou seja: comparar "45 consultas para um card" com "34 para vinte" é comparar coisas diferentes.
Baixar os 45 exigiria um queryset mais magro só para o fragmento, e o card de evento realmente lê
planos, ordens, convites e termos — magro demais traz o N+1 de volta. Fica como está, medido e
explicado, em vez de otimizado no escuro.

A rede é `core/tests/test_custo_do_fragmento_de_menus.py`, e guarda o eixo certo: **dobrar o
tamanho do registro não pode dobrar as consultas**. Contar um número fixo envelheceria no primeiro
campo novo.

---

### NOVO-40 ✅ RESOLVIDO · 🟠 `NOVO` Orçamento a frio do LibreOffice calibrado numa geração de runner que não existe mais bloqueia toda prova de CI · QA · 0,25 d

> **Este item nasceu como `NOVO-36` (commit `cae17bc4`) e foi renumerado em 07/08/2026: duas
> sessões escreveram o mesmo ID no mesmo dia.** A outra ocupante, "Reordenar destinos deixa o
> roteiro com chegada antes da saída", ficou com o número porque é citada em **dez** lugares fora do
> catálogo — duas migrações, `roteiros/models.py`, `roteiro_logic.py`, `roteiro_editor.py`, dois
> planos e dois testes —, enquanto esta não é citada em lugar nenhum. É a quarta colisão de
> numeração deste ciclo; a conferência com `grep "^### NOVO-"` **antes** de escrever continua sendo
> a única defesa.

O passo 15 do `tests.yml`, "Enforce real document generation SLA", reprovou três vezes seguidas em
06/08 — runs 653 e 654 (na `main`) e 657 (PR #226) — **só** no orçamento de partida a frio:

| run | commit | a frio | teto | regime estável | teto |
|---|---|---|---|---|---|
| 654 | `b17782a` | **2553,8 ms** | 1500 ms | 96,8 / 98,6 ms | 1000 ms |
| 657 | `2cb4154` | **1868,4 ms** | 1500 ms | 99,7 / 100,9 ms | 1000 ms |

**Não era código.** O teto de 1500 ms nasceu em 03/08 sobre 1119 ms medidos, e desde então nada
mudou em `documentos/`, no adaptador de conversão ou em `requirements/lock.txt`. O que mudou foi a
máquina: o passo "Install LibreOffice" saiu de **28 s** no último run verde (649) para **58, 60 e
77 s** nos três reprovados. Mesma classe de runner, 2 a 3× mais lenta.

**Efeito, que é o que torna isto 🟠 e não ⚪:** o passo 15 fica **antes** da suíte (18), dos pisos de
cobertura (19) e da régua do `PF-07` (20). Enquanto ele reprova, os três saem como *skipped* — a
`main` fica sem prova de CI nenhuma, e todo PR seguinte também. Quatro merges consecutivos entraram
assim: `BE-23`, `NOVO-31`, `DB-06` e `PF-01`.

**Correção:** `--max-cold-ms` de 1500 para **3000**, com as medições anotadas no próprio passo.
`--max-ms` fica em 1000 — é ele que mede o custo que o usuário sente em uso normal, e passou com
folga de 10× nas três reprovações. A partida a frio continua vigiada; o que muda é o orçamento
caber na máquina de hoje em vez de numa que não temos mais.

**O que este ID NÃO resolve:** a fragilidade de origem. Um número absoluto medido em runner
compartilhado vai sair de faixa de novo. O desenho que não tem esse problema mede a **razão**
frio/quente — estável em ~19× nas três amostras, contra um valor absoluto que variou 2,3× — ou
guarda uma janela das últimas N execuções. Fica catalogado; não entra nesta correção, que existe
para destravar a catraca hoje.

---

---

### NOVO-17 ✅ RESOLVIDO · ⚪ `NOVO` `--parallel` abortava a corrida e não relatava falha nenhuma · QA · 0,5 d

Enunciado original: *"`--parallel` esconde a falha real quando o payload do erro não é
serializável"*, culpando "uma asserção que falha carregando o arquivo inteiro na mensagem".

**Correção de rumo: o tamanho do payload não tem nada a ver.** A causa é uma dependência ausente.
O runner paralelo do Django roda cada subsuíte num processo filho e devolve o resultado por
`multiprocessing`, o que exige **picklar o `sys.exc_info()`**. Objeto `traceback` não é picklável
pela stdlib; o `tblib` é a biblioteca que ensina o pickle a serializá-lo, e o Django o usa quando
está instalado (`django/test/runner.py:164`). Ele **não estava em `requirements/`**.

Reproduzido com duas asserções triviais de uma linha:

| | sem `tblib` | com `tblib` |
|---|---|---|
| falhas relatadas (`FAIL:`) | **0** | **2** |
| saída | 125 linhas, terminando em `TypeError: cannot pickle 'traceback' object` | 53 linhas, terminando em `FAILED (failures=2)` |

**Zero, não "escondida":** a corrida abortava no primeiro erro e não relatava nada no formato de
sempre. O Django até imprime `you should install tblib` **e o nome do teste** — mas no topo da
saída, soterrado por ~100 linhas de `RemoteTraceback` do `multiprocessing`. Quem lê o fim vê só o
`TypeError` e conclui instabilidade de infraestrutura, que é exatamente o risco que o enunciado
antecipou, ainda que pela razão errada.

Corrigido declarando `tblib>=3.0,<4.0` em `requirements/test.txt` e fixando `tblib==3.2.2` em
`requirements/test-lock.txt`. Suíte completa: **1.530 testes verdes em série (44,7 s) e em
`--parallel 4` (12,4 s)** — 3,6× mais rápido, e agora utilizável mesmo quando algo falha.

O `tests.yml` roda a suíte **em série**, então o CI nunca viu este defeito: ele custava caro só
para quem roda localmente. As redes de `core/tests/test_suite_paralela.py` cobrem os dois lados —
`tblib` importável e `tblib==` presente no lock que o CI instala, porque é o lock que decide o que
chega lá.

Vizinho do `NOVO-02`, que em 06/08 **não reproduziu** — mas cuja sondagem achou o `NOVO-26`, esse
sim um vazamento de estado global entre testes.

### NOVO-31 ✅ RESOLVIDO · 🟠 `NOVO` `core.E001` não olha nenhum dos seis modelos de `cadastros` · QA · 0,5 d

`core/checks.py:44-68` (`check_operational_records_have_area`, `deploy=True`) reprova o deploy quando
há registro operacional sem área. Mas `_OPERATIONAL_MODELS` (`core/checks.py:10-19`) tem 8 modelos e
**nenhum** é de `cadastros`: `Servidor`, `Viatura`, `Unidade`, `Cargo`, `Combustivel` e
`ConfiguracaoSistema` ficam de fora.

**Efeito:** nada bloqueia hoje um deploy com esses seis cheios de `area IS NULL` — e são justamente
os que os comandos de seed criam sem área (`seed_cadastros_demo.py:84,93,102,112,125`;
`resetar_banco_demo.py:170,179,183,197,216`; `importar_estrutura_pcpr.py:330,337,359,429`).

**Vira pré-requisito do `DB-02`:** tornar `area` NOT NULL nesses modelos exige antes saber quantas
linhas órfãs existem em produção, e o check é o instrumento que deveria dizer.

**Resolvido:** a varredura passou a ser por introspecção do registro de apps, e não uma tupla fixa
que envelhece. Duas severidades, de propósito — `core.E001` (bloqueia o deploy) segue nos oito
modelos operacionais; `core.W001` (só relata) cobre os demais. Promover os vinte a `Error` de uma
vez tornaria vermelho todo deploy até alguém rodar o backfill, e isso não é decisão de um check.

`core.AuditEvent` ficou **fora da varredura por projeto**: `area` ali é `SET_NULL`, então evento
antigo perde a área quando ela é apagada e a trilha precisa sobreviver a isso. Linha sem área ali é
histórico, não pendência — e por isso ele também não entra no `DB-02`.

---

### NOVO-34 ✅ RESOLVIDO · 🔴 `NOVO` Cinco modelos nascem com `area IS NULL` por seed de migração — e o `DB-02` conta com o contrário · DB · 1 d

> **RESOLVIDO em 07/08/2026.** As duas metades da correção: o enunciado do `DB-02`
> foi reescrito com os três grupos abaixo (ver a própria linha do `DB-02`), e a
> medição em produção ganhou canal permanente — o gate do `NOVO-12` roda
> `check --deploy` na VPS a cada deploy e imprime `core.E001`/`core.W001` com a
> contagem por modelo, onde o seed convive com dado real. Melhor que medir uma
> vez: o número chega sozinho, todo deploy.

Medido com o `NOVO-31` recém-consertado, num banco **recém-migrado e sem nenhum dado de usuário**:

```
eventos.TipoEvento=5, oficios.ConfiguracaoNumeracaoOficio=1,
planos_trabalho.ProgramaSolicitante=3, planos_trabalho.HorarioAtendimento=3,
planos_trabalho.AtividadePlanoTrabalho=11
```

Todas criadas por seed de migração (`eventos/0008`, `oficios/0017`, `planos_trabalho/0002` e `0003`,
mais o seed de atividades). **Não são resíduo a sanear: são o padrão global da instalação.**

O caso que fecha o argumento é `oficios.ConfiguracaoNumeracaoOficio`. A linha global é o piso de
numeração de 2026 (`numero_inicial=75`), e `Oficio.get_next_available_numero` a busca **de
propósito** com `Q(area=area) | Q(area__isnull=True)` — foi exatamente o site mais perigoso da fatia
2 do `BE-09`. Tornar aquela coluna NOT NULL destrói o mecanismo de piso global.

**Efeito sobre o `DB-02`:** o enunciado dele diz "`area` anulável em 27 dos 28 modelos", tratando
isso como dívida uniforme. Não é. Há pelo menos três grupos, e eles pedem tratamento diferente:

1. **Operacional** — `Oficio`, `Roteiro`, `Evento`, `PrestacaoContas` e afins: `NOT NULL` é o alvo,
   com backfill antes.
2. **Catálogo com padrão global** — `TipoEvento`, `ProgramaSolicitante`, `HorarioAtendimento`,
   `AtividadePlanoTrabalho`: o global é usado hoje? Se sim, `NOT NULL` exige decidir a qual área ele
   passa a pertencer, ou duplicá-lo por área (foi o caminho do `NOVO-09` para `ModeloJustificativa`).
3. **Global por projeto** — `ConfiguracaoNumeracaoOficio`: a linha sem área **é** o mecanismo.
   `NOT NULL` está fora de questão sem redesenhar a numeração.

**Correção:** reescrever o enunciado do `DB-02` com esses três grupos antes de escrever qualquer
migração, e medir o mesmo número em produção — onde o seed convive com dado real.

---

### NOVO-36 ✅ RESOLVIDO · 🟠 `NOVO` Reordenar destinos deixa o roteiro com chegada antes da saída · COR · 1 d

**Achado pela constraint `roteiro_ida_ordenada`, que por isso ficou de fora do `DB-07`.** Ela existiu
no PR, e `roteiros/tests/test_roteiros_base.py::test_salvar_reordenacao_preserva_dados_dos_trechos_existentes`
reprovou nos dois bancos com `CHECK constraint failed: roteiro_ida_ordenada`.

`roteiros/roteiro_logic.py:219`, em `_atualizar_datas_roteiro_apos_salvar_trechos`. Ao reordenar os
destinos, cada trecho **preserva os horários que já tinha** — é o comportamento que o nome do teste
promete. Só que as datas param de acompanhar a ordem: com dois trechos de ida (01/05 e 02/05)
invertidos, a função lê `saida_dt` do primeiro trecho da nova ordem (02/05) e `chegada_dt` de
`trechos[-2]` (01/05). Resultado gravado: **chegada dois dias antes da saída**.

**Efeito:** `roteiro.chegada_dt` é lido como fallback do retorno em cinco pontos
(`oficios/presenters.py:70` e `:110`, `eventos/presenters.py:183`, `eventos/services.py:314`,
`eventos/forms.py:33`, todos na forma `retorno_chegada_dt or chegada_dt`). Num roteiro sem trecho de
retorno, o período impresso no ofício e no card do evento sai invertido.

**Correção candidata:** derivar `chegada_dt` do trecho de ida **cronologicamente** último, não do
posicionalmente penúltimo — ou não carregar horário através de uma reordenação, que é onde o dado
deixa de descrever o itinerário. A escolha muda o que `chegada_dt` significa, então pede teste de
caracterização antes (limite 3 do `AGENTS.md`, pelo espírito: o valor chega ao motor de diárias por
`eventos/services.py`).

**Por que não foi corrigido junto com o `DB-07`:** pôr o `CHECK` antes de consertar o produtor troca
dado silenciosamente errado por erro 500 numa tela de uso diário. A constraint entra no mesmo PR da
correção.

> **Resolvido pela derivação cronológica, e a constraint entrou junto.** `saida_dt` passa a ser o
> `min` das saídas das idas e `chegada_dt` o `max` das chegadas das idas. Não é regra nova no
> sistema: é a regra que o resto dele já usa — o motor de diárias ordena marcadores por `saida`
> (`services/diarias.py:299`) e escolhe a vigência por `min(saida)` (`:116-118`), e
> `prestacoes_contas/services.py:89` resolve o fim por `order_by('-chegada_dt')` sobre os trechos.
> A derivação posicional do cabeçalho é que era a anomalia.
>
> **Não é regra de dinheiro.** Medido: o motor de diárias não lê `saida_dt` nem `chegada_dt` do
> cabeçalho — ele monta os marcadores a partir de `RoteiroTrecho`. O total é idêntico no caso normal
> e no reordenado. O dano era de cabeçalho e documento, não de valor.
>
> **Duas armadilhas que a verificação adversarial pegou antes de virarem regressão:**
>
> 1. **O fallback óbvio produziria erro 500.** "Sem ida com chegada, cair para o máximo sobre todos
>    os trechos" pegaria `retorno.chegada_dt`, que por construção vem depois de `retorno_saida_dt` —
>    violação determinística de `roteiro_permanencia_ordenada`, constraint **já em produção** desde o
>    `DB-07`. O estado é alcançável por gesto banal: remover a última linha de destino faz o autosave
>    salvar um roteiro cujo único trecho é o de retorno. Hoje esse caminho devolve 200; com o
>    fallback devolveria 500. Virou o teste `test_roteiro_so_com_trecho_de_retorno`.
> 2. **Limpar `retorno_*` quando a fonte é nula apagaria rascunho.** Trecho de retorno que existe mas
>    ainda está sem datas é rascunho legítimo; escrever `None` cegamente descartaria o que o usuário
>    já tinha digitado. A função continua só atribuindo, nunca limpando.
>
> **Leitor acoplado, corrigido junto:** `encontrar_roteiro_duplicado`
> (`roteiros/services/roteiro_editor.py:288`) derivava o mesmo valor pela mesma regra posicional e
> casava contra `Roteiro.saida_dt` no banco. Mudar só o escritor faria os dois discordarem
> exatamente nos roteiros reordenados, e a detecção de duplicata pararia de achá-los em silêncio.
>
> **Máscara que existia e não foi removida:** `roteiros/presenters.py:107-108` troca início e fim
> quando `fim < inicio`. É defesa contra exatamente o dado que este defeito produzia. Fica —
> agora como cinto de segurança, não como remendo.
>
> Quatro inversões: chegada posicional, saída posicional, o fallback e a limpeza incondicional.
> Cada uma reprova o teste que a descreve, e a do fallback reprova com
> `IntegrityError: CHECK constraint failed: roteiro_permanencia_ordenada`.

---

### NOVO-35 ✅ RESOLVIDO · 🔴 `NOVO` Excluir um servidor do cadastro apaga comprovante de prestação por cascata · DB · 1 d

`PrestacaoServidor.servidor` é `on_delete=models.CASCADE` (`prestacoes_contas/models.py:141`).
Excluir um servidor em `cadastros` (`cadastros/services.py:252` → `core.deletion.excluir_com_protecao`)
derruba todas as linhas de prestação dele e, por cascata, os `PrestacaoDocumentoAnexo` presos a
elas — o comprovante de saque entre eles. Medido em transação revertida (ver `DB-06` no
`PLANO_BACKEND.md`): 1 servidor com 1 comprovante, `servidor.delete()`, restam **0 anexos**.

É o mesmo defeito do `DB-06` por outra porta. O `DB-06` fechou a porta da equipe do ofício
(`PrestacaoServidor.sair_da_equipe` preserva quem tem dados coletados); esta continua aberta.

**Protegido hoje só por acidente:** `AssinaturaDocumento.signer` é `on_delete=PROTECT`, então um
servidor que já assinou algum RT não pode ser excluído — o `ProtectedError` vira a mensagem de
`core/deletion.py`. Quem tem comprovante mas ainda não assinou não tem essa proteção.

**Correção candidata:** reusar `PrestacaoServidor.tem_dados_coletados()` em `excluir_servidor` e
levantar `DelecaoProtegidaError` com a contagem, em vez de trocar o `CASCADE` por `PROTECT` — que
tornaria indelével qualquer servidor que já tenha entrado em um ofício, ou seja, quase todos.

**Ficou fora do `DB-06` de propósito:** muda a UX de exclusão no cadastro (mensagem nova numa tela
que o `DB-06` não toca) e precisa da medição de quantos servidores ficariam bloqueados em produção
antes de a regra ser escolhida.

> **Resolvido pela guarda no serviço, com predicado próprio — e não com `PROTECT`.** Medido no banco
> de desenvolvimento: `PROTECT` bloquearia **3 de 4** servidores (todo o que já entrou em qualquer
> ofício, inclusive quem não tem nada a perder); a regra por dado bloqueia **1 de 4**. O critério
> passa a ser o dado, não o vínculo.
>
> **Predicado novo, `tem_prova_irrefazivel()`, mais estreito que o `tem_dados_coletados()` do
> `DB-06`** — e a diferença foi imposta pela verificação adversarial. `tem_dados_coletados` inclui
> `status != PENDENTE`, e `status` é **coletivo**: `view_common._marcar_servidores_pendentes` marca
> toda a equipe pendente do ofício ao salvar um documento **compartilhado** (despacho, RT, diário).
> Medido: basta um colega salvar o despacho para que um servidor semeado por engano passe a "ter
> dados coletados" — e ficasse indelével para sempre, por ação de terceiro. Preservar uma linha e
> prender um cadastro inteiro são decisões de peso diferente; ficam no predicado só os três que não
> voltam: comprovante, assinatura e número da solicitação.
>
> **A armadilha que o `DB-06` criou, e que quase engoliu esta correção.** A guarda tem de consultar
> `PrestacaoServidor.todos`. O acessor reverso `servidor.prestacoes_servidor` herda o
> `_default_manager`, que desde o `DB-06` esconde as linhas com `removida_em` — e o invariante do
> `DB-06` é que linha marcada é **exatamente** a que tem dados. A relação reversa esconde o conjunto
> que a guarda existe para achar. Medido: com a reversa, a guarda bloqueava zero. Travado por
> `RelacaoReversaEscondeAProvaTests`, que não testa a correção — testa a armadilha.
>
> **O encanamento da mensagem estava fechado em dois pontos** e foi aberto: `services.py` levantava
> `CadastroVinculadoError` **sem argumento**, e a view capturava **sem `as exc`**. A mensagem agora
> nomeia o servidor, os ofícios e o que fazer. `_vinculo_error(request, mensagem=None)` ganhou default
> para não reescrever os testes de caracterização dos catálogos, que travam o literal antigo.
>
> **Um teste meu passava dos dois jeitos, de novo (oitava vez).** `test_assinatura_sozinha_bloqueia`
> ficava verde sem a guarda, porque `AssinaturaDocumento.signer` é `PROTECT` e já barrava. O que
> distingue os dois mecanismos é a **mensagem** — o `PROTECT` dá a genérica, a guarda dá a
> específica. Só com a asserção sobre a mensagem o caso passou a ser atribuível à correção.
>
> **O que esta correção NÃO protege, e virou `NOVO-39`:** o valor impresso do ofício e do termo dos
> **colegas** do servidor excluído.

---

### NOVO-39 🟠 `NOVO` Excluir um servidor muda o valor de diária impresso dos colegas dele · COR · 1 d

Achado pela verificação adversarial do `NOVO-35`, sob a lente "dinheiro e documento", e reproduzido:

```
diarias_para_servidores() com 2 servidores: R$ 600,00 (quantidade_servidores=2)
depois de excluir 1 servidor:               R$ 300,00 (quantidade_servidores=1)
```

`Oficio.diarias_para_servidores()` (`oficios/models.py:263-301`) faz
`qtd_servidores = self.servidores.count()` e multiplica **em tempo de renderização**. A contagem
alimenta o ofício (`oficios/documents.py:281`), o **termo de autorização** (`documents.py:341`, via
`_viagem_payload`) e o DOCX (`oficios/docxtpl_context.py:490`).

**Efeito:** excluir um servidor do cadastro — mesmo um que não tem nada a perder, o caso que o
`NOVO-35` deliberadamente libera — muda o total de diárias impresso em documento **de outras
pessoas**. Um ofício reimpresso depois da exclusão não bate com o que foi assinado.

**Por que o `NOVO-35` não resolve:** a guarda dele protege os artefatos do próprio excluído
(comprovante, assinatura, solicitação). O valor dos colegas não é artefato do excluído — é derivado
de uma contagem viva. `PROTECT` resolveria por acidente, ao custo de tornar quase todo servidor
indelével.

**Correção candidata:** congelar a contagem no documento gerado, em vez de recalculá-la a cada
renderização — que é a mesma família do `DB-06` (`TabelaDiaria` guarda os três valores calculados
"para congelar o valor que valeu"). Alternativa mais barata: gravar `quantidade_servidores` no
`Roteiro`/`Oficio` no momento da geração.

---

### NOVO-41 ⚪ `NOVO` Grupo de checkboxes não associa a própria ajuda, e o Django não vai fazer isso · HT · 0,5 d

Achado ao fechar o `HT-02`, e deixado de fora dele **por ser outra correção**, não por cansaço.

`PresetAtividadesQuickAddForm.atividades` é `CheckboxSelectMultiple`. O Django só emite
`aria-describedby` quando `not self.use_fieldset` (`django/forms/boundfield.py:294`), e
`use_fieldset` é `True` exatamente para os widgets de múltiplos controles — porque a associação
correta ali não é um atributo no controle, é `<fieldset>` com `<legend>` envolvendo o grupo.

Hoje o painel escreve o texto à mão, em `planos_trabalho/presets/partials/_quick_add_fields.html:12`
("Clique nas atividades para incluí-las ou retirá-las deste preset."), e o `help_text` declarado no
form diz quase a mesma coisa em outras palavras — **texto duplicado, e o do form nunca aparece**.

**Efeito:** leitor de tela que chega ao grupo de checkboxes não recebe a instrução. Não há ponteiro
quebrado — o Django não emite ponteiro nenhum —, então o `HT-02` fecha verde com este caso aberto.
**Correção:** trocar a `<section>` do painel por `<fieldset>`/`<legend>`, e a descrição por um
`<p id="…_helptext">` referenciado por `aria-describedby` no `<fieldset>`. É remodelar o painel;
cabe na fase de reconstrução, não numa correção de componente.

**Único caso do sistema:** é o único campo de produção com `use_fieldset=True` e `help_text`.

---

### NOVO-42 🟠 `NOVO` Seis telas de catálogo exibem ao usuário o alerta de contrato quebrado do `N-07` · HT · 0,5 d

Visto na tela ao conferir o `HT-02` no navegador, e depois medido por varredura das 20 rotas de
lista com `test.Client`:

```
COM o alerta (6):  /eventos/tipos/  /justificativas/modelos/  /oficios/modelos-motivo/
                   /planos-trabalho/horarios/  /planos-trabalho/programas/  /planos-trabalho/presets/
sem  (14)
```

`components/lists/list_page_quick_add.html:84` inclui a paginação com `paginacao_obrigatoria=True`
— declarando "esta lista É paginada". As seis views acima **não põem `page_obj` no contexto**, e o
componente cumpre o contrato do `N-07` denunciando na tela:

> Paginação indisponível: esta lista foi renderizada sem `page_obj` no contexto.

Num `<p role="alert">` vermelho, acima da lista, **em produção**. Não há gate de `DEBUG`.

**Efeito:** o usuário de seis catálogos vê uma mensagem de erro técnica, com nome de variável
Python, toda vez que abre a tela. Funciona: a lista aparece embaixo. Mas o `role="alert"` faz o
leitor de tela anunciar um erro que não é do usuário.

**O `N-07` não está errado** — ele foi feito exatamente para isso, e achou seis casos reais. O que
falta é fechá-los: ou as seis views passam a paginar (coerente com as outras catorze), ou as seis
telas param de declarar `paginacao_obrigatoria`. A primeira é a certa: catálogo cresce.

**Não é regressão desta etapa** — conferido no `main` antes de qualquer edição do `HT-02`, e o
alerta já estava lá.

**Medição que falta:** quantos ofícios já emitidos teriam contagem diferente hoje. Sem isso não dá
para saber se é dívida histórica ou risco corrente.

---

### NOVO-45 🟠 `NOVO` O catálogo global de seed não é ofertado a usuário com área — os pickers recortam sem fallback · DB · decisão de produto

Medido em 07/08/2026, ao reescrever os testes do `DB-02`. `filter_queryset_by_area` é estrito:
com área ativa devolve só `area = X`, nunca o global (`area IS NULL`). Consequência: os registros
que o seed de migração cria como "padrão da instalação" — 5 `TipoEvento`, 3 `ProgramaSolicitante`,
3 `HorarioAtendimento`, 11 `AtividadePlanoTrabalho` (`NOVO-34`) — não aparecem no picker de um
usuário com vínculo. Exemplo concreto: o wizard de plano valida `programa` contra
`filter_queryset_by_area(ProgramaSolicitante.objects)` (`planos_trabalho/forms.py:618`); numa
instalação recém-migrada a lista vem vazia até a área cadastrar os próprios programas.

**Não é regressão do `DB-02`** — é o comportamento vigente desde o `BE-09`. A reescrita dos testes
só o tornou visível: o teste antigo "via" o global porque o usuário de teste não tinha vínculo e
caía no balde `area IS NULL`, exatamente o estado que o `DB-02` eliminou dos modelos operacionais.

**Decisão de produto, dois caminhos — e o grupo 2 do `DB-02` depende dela:**

- ofertar o global como fallback de leitura (`Q(area=X) | Q(area__isnull=True)`) nos pickers de
  catálogo — e aí `NOT NULL` nesses modelos fica proibido de vez;
- ou materializar o seed por área na criação de cada área (o caminho que o `NOVO-09` já tomou para
  `ModeloJustificativa`) — e aí o grupo 2 pode um dia virar `NOT NULL`.

> **Decidido em 07/08/2026: o segundo caminho.** O usuário escolheu duplicar por área, seguindo o
> `NOVO-09`. Executado nas migrações `eventos/0016` e `planos_trabalho/0024`, que dão a cada área
> os quatro catálogos inteiros — **o acervo existente**.
>
> A outra metade da frase, "na criação de cada área", **não** está feita, e a instalação nova
> também não: `criar_area` não semeia catálogo, e numa base limpa os seeds rodam quando nenhuma
> área existe. É o `NOVO-49`, e é ele que segura o `NOT NULL` nesses quatro.
>
> **Aviso de numeração:** existem hoje duas entradas `NOVO-45` neste arquivo — esta e a do
> `faixa_lateral_class`, de outra sessão. As duas entraram na `main` antes deste PR e não renomeio
> ID de outra sessão pela metade (limite 2 do `AGENTS.md`); fica registrado para quem for
> desempatar.

---

### NOVO-32 🟡 `NOVO` `resetar_banco_demo` recria `ConfiguracaoSistema` sem área · QA · 0,25 d

`cadastros/management/commands/resetar_banco_demo.py:231` instancia `ConfiguracaoSistema()` cru e
salva, criando linha com `area=NULL`. É exatamente o que o docstring de `get_singleton`
(`cadastros/models.py:562-563`) promete nunca recriar. A primeira iteração do comando usa
`get_singleton()` (`:229`); as seguintes, não.

Contradição entre o comando de demonstração e a regra do modelo, e ela repovoa o balde que o
`backfill_legacy_areas` existe para drenar.

---

### NOVO-33 🟡 `NOVO` `_preencher_roteiro_oficio_com_evento` não tem chamador de produção · BE · 0,25 d

`oficios/services.py:205`. Varredura no repositório inteiro: o único chamador é
`oficios/tests/test_services.py:221`. Irmão do `NOVO-27`; código morto sai na fase 9, com a prova de
varredura no PR (`AGENTS.md` §3.6).

---

---

### NOVO-18 🟡 PARCIAL — `.js` fechado, resto na fase 9 · `NOVO` CRLF misto reescreve o diff inteiro · QA · 0,5 d

> **Número corrigido duas vezes.** A primeira medição contou 2 arquivos porque olhou só os que a
> etapa tinha tocado. A segunda, em 06/08, varreu `static/js` e achou 8 mistos + 6 CRLF puro. **A
> terceira varreu o repositório inteiro: são 164 arquivos**, e o título "oito arquivos JS" estava
> errado por uma ordem de grandeza.

| extensão | arquivos com CRLF |
|---|---|
| `.py` | **101** — inclui `roteiros/services/diarias.py` e `roteiro_logic.py`, os dois CRLF puro |
| `.md` | 21 |
| `.html` | 18 |
| `.js` | 14 |
| `.css` | 7 |
| outros | 3 (`requirements/base.txt`, um `.json` de screenshots, e um arquivo `tatus` de 195 linhas na raiz — lixo de um `git status` digitado torto, que é assunto do `BE-24`) |

Qualquer ferramenta que reescreva o arquivo normaliza tudo e produz um diff de arquivo inteiro —
302 e 1.206 linhas para uma troca de uma linha, o que enterra a mudança real na revisão. Aconteceu
duas vezes (F1 e a etapa do `JS-04`) e as duas foram desfeitas editando byte a byte.

**Fechado o recorte `.js`:** os 14 arquivos de `static/js` normalizados para LF (2.630 linhas
trocadas, e o diff é **mecanicamente idêntico** no conteúdo — só o byte de fim de linha muda),
`.gitattributes` com `*.js text eol=lf`, e a rede em `core/tests/test_fim_de_linha_js.py`.
Os bundles não mudaram: `build_shell_bundles.py` lê em modo texto e escreve com `newline="\n"`,
então já normalizava na concatenação.

**Por que só `.js`:** `.gitattributes` **sem** normalização não resolve nada — apenas adia o diff
de arquivo inteiro para o próximo que tocar no arquivo. Regra e normalização andam juntas, então a
regra cobre exatamente o que foi normalizado. Fazer os 164 de uma vez
(`git add --renormalize .`) é o certo, mas **dá conflito em toda branch em voo**, e havia 10 PRs
abertos e as fatias 5 e 6 do `BE-09` em andamento noutra sessão.

**Resta a fase 9:** `.gitattributes` completo + `git add --renormalize .` nos outros 150, com a fila
vazia. Vizinho do `BE-22` (10 arquivos `.py` com BOM) — mesma família, e o sweep dos `.py` deveria
sair junto com ele.

---

### NOVO-22 ✅ RESOLVIDO (1a51341) · 🟠 `NOVO` `applyingState` travado deixa o editor de roteiro inerte · COR · 0,25 d

Achado ao abrir o `JS-04`. `applyState` (`editor/index.js:1427`) faz `applyingState = true` e só
devolve `false` em `:1468`, **dentro do `.then` de sucesso**. Uma exceção em qualquer callback da
cadeia — inclusive na carga inicial do editor (`:1817`) — deixa o flag travado.

A partir daí, `runAutoEstimarTrechos` e os **treze** listeners que checam `if (applyingState) return`
abortam para sempre: o editor aceita cliques e não faz nada, sem erro na tela e sem pista no
console. O próprio arquivo já usa o padrão certo no caminho síncrono (`:1035-1048`, `try/finally`
com `prevApplyingState`); faltava o equivalente assíncrono.

Fechado junto do `JS-04`: o flag volta num `.finally`. No caminho feliz é no-op — o `.then` já o
tinha zerado; no triste, é o que devolve o editor.

---

### NOVO-23 ✅ RESOLVIDO (0b64916) · 🟠 `NOVO` Remover documento assinado falha em silêncio e a página recarrega como se tivesse dado certo · QA · 0,25 d

`static/js/components/attach-signed-modal.js:229` —
`CV.http.request(currentRemoveUrl, { method: 'POST' }).then(function () { window.location.reload(); })`.

Dois buracos no mesmo lugar. Sem `.catch`: falha de rede não remove o documento, não recarrega e
não avisa — o usuário vê o anexo ainda ali e conclui que o clique não pegou. E usa `request`, não
`fetchJson`, então **o status HTTP nunca é checado**: um 500 cai no `.then` de sucesso e recarrega a
página, dando ao usuário a impressão de que o documento assinado foi removido quando não foi.

Achado no inventário do `JS-04`. É o segundo dos dois únicos sítios de rede sem `.catch` fora do
editor de roteiros, e o de sintoma mais grave — mexe em documento assinado.

**Medido no navegador em 06/08**, com o gatilho real do componente e a rota interceptada:

| cenário | antes | depois |
|---|---|---|
| HTTP 500 | **recarregou a página** | não recarrega; faixa diz que o documento continua anexado |
| falha de rede | nada na tela, `Unhandled Promise Rejection` | faixa com texto em português |
| sucesso | recarregou | recarregou (inalterado) |

A conferência achou um defeito na própria correção: a primeira versão jogava `error.message` na
faixa, e falha de rede virava **"Failed to fetch"** na cara do usuário. Só o texto escrito pelo
componente chega à tela agora, marcado com `paraUsuario`. **A mesma assimetria existe em
`calculateDiarias` (`roteiros/editor/index.js:1408`)** e segue lá — registrada aqui para quem
mexer no editor na fase 6.

---

### NOVO-25 ✅ RESOLVIDO (4b162d9) · 🔴 `NOVO` Auditor de área reprovava todo PR do repositório por depender do `.env` do desenvolvedor · QA · 0,25 d

`scripts/audit_area_scoped_managers.py:66` — o gate do `BE-09` sobe o Django de verdade (precisa de
`apps.get_models()`) e apontava para `config.settings.dev`. Esse módulo **exige**
`FIELD_ENCRYPTION_KEYS` no ambiente, e o CI não define a chave. O auditor morria em
`django.setup()` antes de olhar um modelo sequer:

```
RuntimeError: FIELD_ENCRYPTION_KEYS não está definida.
##[error]Process completed with exit code 1.
```

Reprovava **todo PR**, com um traceback sem relação nenhuma com o diff. Verde na máquina de quem
escreveu porque lá existe `.env`; vermelho em qualquer lugar limpo. Foi encontrado quando o CI
reprovou o PR do `NOVO-23` — cujos passos todos passaram antes deste.

Corrigido para `config.settings.test`, que gera a própria chave Fernet
(`config/settings/test.py:35`) e é o que a suíte já usa. `setdefault` preservado: quem exportar o
módulo continua mandando.

O teste (`core/tests/test_auditores_sem_env.py`) roda o script num ambiente cru. **A primeira
versão dele não valia nada** e passava com o script defeituoso: `config/settings/base.py:16` chama
`load_dotenv(BASE_DIR / ENV_FILE)` com caminho **absoluto**, então limpar variáveis não esconde o
`.env` do repositório. É preciso apontar `ENV_FILE` para um arquivo inexistente.

`scripts/inspect_area_conflicts.py:18` tem a mesma linha, mas **não é gate de CI** — é ferramenta
de inspeção manual, e ali `dev` é defensável. Fica anotado, não corrigido.

**Duas sessões acharam isto em paralelo.** A troca de uma linha chegou à `main` pelo PR #207
(`4b162d9`), por leitura estática, antes de qualquer run do CI ter conseguido runner; aqui ela
apareceu pelo caminho oposto — o log do run 31122738847 com o traceback. Na junção ficou a versão
da `main` (a mesma linha, com docstring) mais o teste, que nenhum dos dois lados tinha: sem ele o
gate volta a `dev` na primeira edição distraída e ninguém percebe até o próximo ambiente limpo.

---

### NOVO-24 ✅ RESOLVIDO · ⚪ `NOVO` `.then` escapa do `try/catch` do `async` na configuração do Drive · QA · 0,25 d

`static/js/pages/gdrive_config.js:287` — dentro de um `try` de função `async`,
`loadPastas(currentPaiId()).then(function () { … })` é encadeado **sem `await`**, então o `catch` de
`:292` não o alcança e o `CV.feedback.alert` de `:293` nunca dispara para essa falha.

**Correção de rumo na descrição original.** O inventário do `JS-04` supôs que "a lista não
recarrega"; medido no navegador, ela recarrega normalmente — `loadPastas` tem `try/catch` próprio e
nunca rejeita. O que o `.then` solto de fato causava é outra coisa, e são dois efeitos:

1. **Exceção invisível dentro do callback.** O gatilho real é o modo mock: `services.py:200` monta o
   id da pasta criada como `"mock-nova-" + nome digitado`, e esse id ia **cru** para dentro de um
   seletor de atributo. Um nome com aspas — `Ação "2026"` — produzia
   `Failed to execute 'querySelector' on 'Element': … is not a valid selector`, no console e só no
   console. Na tela: a pasta aparecia na lista, **não vinha selecionada**, e nada explicava por quê.
   `data.pasta` ausente dá no mesmo por outro caminho (`TypeError: … reading 'id'`).
2. **O `finally` passava por cima da recarga.** Medido na ordem dos eventos: o botão voltava a
   `disabled = false` **antes** de a listagem responder, então "Criar pasta" ficava clicável com a
   lista ainda em "Carregando…" — dois cliques, duas pastas.

Corrigido com `await loadPastas(currentPaiId())` seguido de `selecionarPastaCriada(data.pasta)`,
que trata id ausente desistindo (a pasta já existe; a lista recarregada a mostra) e escapa o id com
`CSS.escape` antes do seletor — o mesmo idioma de `picker.js:489`.

A seleção fica **dentro** do `try` mas depois do ponto em que a criação já deu certo, e não pode
lançar: falhar ali não pode virar "não foi possível criar a pasta", que seria a mentira que o
`NOVO-23` acabou de corrigir no modal de assinado.

Teste: `core/tests/test_gdrive_criar_pasta.py` — estático, porque o CI não roda JS (`JS-03`); as 6
asserções falham contra o código antigo.

---

### NOVO-26 ✅ RESOLVIDO · 🟠 `NOVO` Mapa de capitais memorizado no processo decide diária com base desatualizada · COR · 0,5 d

`roteiros/services/diarias.py:66` — `_CAPITAIS_DA_BASE` era um dicionário lido **uma vez por
processo** e nunca invalidado. Quem consome é `classify()`, que decide `CAPITAL` vs `INTERIOR`:
**grupo tarifário, ou seja, valor da diária.**

Achado ao sondar o `NOVO-02`. A combinação de apps que ele descrevia não reproduziu, mas a suíte
**completa** em `--reverse` ficou vermelha:

```
FAIL: eventos.tests.test_orcamento_de_queries…test_o_detalhe_custa_o_mesmo_numero_de_queries
AssertionError: 76 != 77
```

O diff das duas listas de SQL isola uma consulta só —
`SELECT nome, uf FROM cadastros_cidade WHERE capital` — presente em ordem normal e ausente em
`--reverse`, porque algum teste anterior já tinha aquecido o mapa.

**Três caminhos de defasagem, nenhum coberto:**

1. **Testes.** O mapa atravessa o rollback da transação. Só `roteiros/tests/test_diarias_capitais.py`
   se defendia, chamando `limpar_cache_capitais()` no `setUp` e no `addCleanup`; o resto da suíte
   estava exposto.
2. **Importação.** `cadastros/services_importacao.py` escreve `Cidade.capital` por `bulk_create` e
   `bulk_update`. A docstring do cache dizia *"Quem importar a base deve chamar
   `limpar_cache_capitais()`"* e **nenhum importador chamava** — mas o remédio anunciado não
   funcionaria de todo jeito: os importadores são management commands, rodam em processo próprio,
   e os **workers web continuariam com o mapa velho até reiniciar**.
3. **Admin.** `CidadeAdmin` (`cadastros/admin.py:49`) expõe `capital`. Marcar uma capital pelo admin
   não limpava o cache de worker nenhum — nem o do processo que salvou.

**Por que não bastava invalidar:** invalidar por sinal não pega `bulk_create`/`bulk_update`, que é
justamente o que o importador usa. Cobertura parcial aqui significa "às vezes cobra a menor".

> **Correção de um erro meu (06/08).** A primeira redação desta linha dizia também que
> `django.core.cache` "cai em `LocMemCache` sem `REDIS_URL`, que é o caso dos ambientes
> declarados". **Está errado:** `config/settings/prod.py:36` **exige** `REDIS_URL` e levanta
> `RuntimeError` sem ela — foi o que o `QA-02` fechou. Em produção existe cache compartilhado; o
> fallback para `LocMemCache` (`base.py:115`) só vale em dev e teste. A conclusão do `NOVO-26` não
> muda, porque ela se sustenta no argumento dos sinais acima, mas a afirmação sobre produção era
> falsa e enganaria quem for decidir alguma coisa sobre cache depois.

**Corrigido** trocando o cache de processo por `capitais_por_uf()`, sem memória: uma consulta que
devolve `{**CAPITAIS_POR_UF, **base}` — mesma precedência de antes, a base mandando por UF e o mapa
do módulo preenchendo as que faltam, que é o fallback que o `N-06` existe para preservar.
`classify()` ganhou um terceiro parâmetro opcional com o mapa já resolvido, e os dois únicos
chamadores em laço (`infer_tipo_destino_from_paradas`, `build_periods`) resolvem uma vez e passam
adiante: **uma consulta por cálculo, não por marcador**, que era o N+1 que o cache existia para
evitar. `limpar_cache_capitais()` foi removida em vez de virar no-op — nome de função que promete
limpeza convida a confiar nela.

**Orçamento de queries não mudou:** `QUERIES_DETALHE` segue **77** e `QUERIES_DETALHE_COM_OS` segue
**68**. O que mudou é que agora são os mesmos em qualquer ordem — antes o 77 dependia de o cache
estar frio.

Testes em `roteiros/tests/test_diarias_capitais.py`: `test_a_base_editada_passa_a_valer_na_mesma_execucao`
(edita a base no meio da execução e reclassifica — modela o caminho do admin) e
`test_cada_calculo_paga_o_mesmo_custo` (dois cálculos idênticos custam igual; antes o segundo saía
de graça). Os dois **falham contra o código antigo**. `test_o_custo_nao_cresce_com_o_numero_de_destinos`
é a rede anti-N+1 e passa nos dois estados de propósito.

Suíte completa verde nas três formas — série, `--parallel 4` e **`--reverse`**, que era a vermelha.

---

### NOVO-27 ✅ RESOLVIDO · 🟠 `NOVO` Correção do `NOVO-26` virou uma consulta por card na lista de roteiros · COR · 0,25 d

**Regressão minha, achada pelo CI da `main`** — run **651**, passo `Enforce list performance ceilings
(PF-07)`:

```
roteiros:index @ 200:    consultas 47 passou do teto 32
roteiros:index @ 20000:  consultas 47 passou do teto 32
```

Bisect limpo: run **649** (`9af3e59`, até o #213) verde; run **651** (`b630cc3`, já com o #214)
vermelho. A lista renderiza **15** cards e 47 − 32 = **15** — uma consulta por card.

**Causa.** O `NOVO-26` tirou o mapa de capitais da memória do processo, e com razão: ele ficava
velho e `classify` decide valor de diária. Só que `roteiros/views.py` monta um card por roteiro, e
cada card chamava `capitais_por_uf()` por conta própria (`presenters.py` → `_inferir_tipo_destino`
→ `infer_tipo_destino_from_paradas`). O cache que saiu **estava fazendo trabalho real ali**: depois
do primeiro card, os outros catorze saíam de graça.

**A rede do `NOVO-26` mediu o eixo errado.** `test_o_custo_nao_cresce_com_o_numero_de_destinos`
conta marcadores **dentro de um cálculo**. O que estourou foi **cálculos por página** — eixo que eu
não testei.

**Corrigido** resolvendo o mapa uma vez por página e passando adiante, no mesmo desenho que
`classify` e `build_periods` já usavam: `infer_tipo_destino_from_paradas` ganhou o parâmetro
opcional `capitais`, e `apresentar_roteiro_card` também. Medido com a régua de verdade, contra
PostgreSQL: **47 → 33**, e nenhuma outra rota se moveu.

**O teto sobe de 32 para 33, de propósito.** Os 32 tinham sido medidos com o cache de processo já
quente — zero consultas de capitais por página. A consulta que sobra é uma por requisição, e é
exatamente o que o `NOVO-26` comprou: capital marcada no admin passa a valer na requisição
seguinte, em vez de só depois de reiniciar o worker. Subido com `--permitir-subir-teto`, que existe
para isto, e **só** em `consultas` de `roteiros:index` — a régua queria regravar todos os `kb_html`
com ±0,2 de ruído da minha máquina, e isso foi descartado.

Rede nova: `roteiros/tests/test_custo_da_lista.py`. Ela afirma **o número de cards renderizados**
antes de medir — a primeira versão passava contra o código defeituoso porque o fixture sem
`saida_dt` caía fora de todas as abas e a lista vinha vazia. E filtra pelo `WHERE
"cadastros_cidade"."capital"`, não pela palavra solta: `capital` é coluna e aparece em qualquer
select de `Cidade`, o que me fez ler 4 consultas onde havia 1.

---

### NOVO-43 🟠 `NOVO` O teto quente do passo 15 nunca foi calibrado contra a amostra que o decide, e reprovar ali anula todos os gates a jusante · CI · 0,5 d

O passo 15 do `tests.yml` roda `documentos_unoserver_check --benchmark --representative-resources
--iterations 3 --max-ms 1000 --max-cold-ms 3000`. O orçamento **quente** compara `max()` de 4
amostras com 1000 ms, usando `>=`
(`documentos/management/commands/documentos_unoserver_check.py:160`).

Em 07/08 ele reprovou no PR #246 por **0,2 ms** — `1000.2` contra `1000`.

**O teto é o `default` do argparse** (`documentos_unoserver_check.py:35`), não um valor medido:
`git log -S"--max-ms 1000" -- .github/workflows/tests.yml` alcança só `a4739eff`, cuja mensagem é
`commit`. O comentário do próprio passo justifica mantê-lo em 1000 com "o regime estável entre 96 e
101 ms" — que é o **docx**, o modelo que o gate quase nunca pega.

**Medição, 30 execuções (runs 667–696, 07/08 entre 04:41Z e 15:05Z):**

| população | mediana | faixa | quem define o `max()` |
|---|---:|---|---|
| `ordem_servico_modelos.docx` quente | 100,0 ms | 93–110 (60 amostras) | 1 de 30 |
| `diario_bordo.xlsx` quente | ~476 ms | 417,3–528,2 | **29 de 30** |

Máximo quente por execução: mediana 486,9 · média 502,4 · máximo 1000,2. **Vinte e nove valores
entre 417,3 e 528,2, e o intervalo de 528,2 a 1000,2 está vazio** — não há tendência de subida, há
um pico solitário.

**Folga real sobre quem decide: 2,05× na mediana (1000 / 486,9) e 1,89× no pior verde
(1000 / 528,2)** — e não os "10×" que o comentário do passo sugere, que é a folga do docx.

**Três defeitos de desenho, independentes do commit:**

1. **O estatístico é `max()` sobre 4 amostras.** `E[max]` cresce com N: aumentar `--iterations`
   deixa o gate mais **rígido**, não mais preciso.
2. **Teto único sobre duas populações que diferem 4,8×.** Na prática é um gate do xlsx com margem
   apertada e decoração para o docx — que precisaria regredir 10× para tropeçar.
3. **O raio de explosão é anormal.** O passo 15 precede a suíte (18), os pisos de cobertura (19) e a
   régua do `PF-07` (20). Reprovar ali transforma um pico de um runner em **PR sem prova de CI
   nenhuma**. A régua irmã já decidiu por escrito o oposto (`scripts/medir_desempenho.py:34-40`:
   "Tempo não tem teto… este repositório já pagou essa conta") e cita este passo como o exemplo do
   que não fazer.

**O gate está a um fator 2,05 de deixar de funcionar.** Em 06/08, quando a geração de runner mudou,
o valor a frio saltou de ~1119 para 1868–2554 ms (1,7 a 2,3×) e o passo reprovou 3 de 3 vezes,
inclusive na `main` — foi o `NOVO-40`. Uma repetição daquele regime põe a mediana quente em
~1000–1120 ms e a taxa de reprovação perto de 100%.

**Taxa de falso positivo: 1 em 30 execuções (3,3%) na janela medida.** O intervalo de confiança de
95% sobre um único evento vai de ~0,1% a ~17%; não dá para estreitar sem mais janela, e a cauda não
é extrapolável do corpo da distribuição.

**Correção candidata, em ordem de custo/benefício:** preservar `$RUNNER_TEMP/unoserver.log` com
`if: failure()` + `upload-artifact` (hoje o log some, e por isso a causa da parada é
indeterminável); mover o passo para depois da suíte ou para job paralelo, o que corta o dano sem
tocar na estatística; **teto por modelo** em vez de teto global, que devolve margem semelhante às
duas populações e torna o gate do docx ~5× mais sensível; e `>` em vez de `>=`.
**Não** adotar razão frio/quente — os dados a refutam (a razão do docx varia 6,06 a 26,14,
espalhamento de 4,3×, pior que o valor absoluto, 4,0×).

> **Não é regressão do `HT-06`, e a prova é de árvore, não de argumento.** O head que reprovou
> (`2bb1a37a`) e o merge na `main` (`5f1b6503`) têm a **mesma árvore**,
> `23c94658943f0f019469691b4fdd0fcc5a50fd2b`, com as 7 deleções. O run 696 reprovou às 15:07; o run
> **697**, sobre essa árvore idêntica, **passou inteiro** às 15:13, com o máximo quente em 515,7 ms.
> Mesmos bytes, seis minutos, resultados opostos.
>
> Os passos 16 a 20 ficaram `skipped` no run 696 — a suíte, a cobertura e o `PF-07` do `HT-06`
> ficaram sem prova naquele run, e a têm no 697.

### NOVO-44 ✅ RESOLVIDO · 🔴 `NOVO` O `BE-25` apagou os dois labs e deixou a cascata para trás — `main` vermelho em 8 testes · COR · 0,5 d

O PR #247 (`BE-17`, `BE-25`, `UI-01`) apagou `dev/ui_lab` e `ui_lab2` inteiros — a decisão
que faltava — mas não rodou a trava do `HT-06` antes de mesclar: os **7 componentes** de
`SO_NO_LABORATORIO` perderam o último citador naquele commit, e
`core/tests/test_componentes_sem_orfao.py` reprovou na `main` (runs de `ac6b862` e `669afc4`,
8 falhas) e em todo PR aberto contra ela. É a cascata que o próprio `HT-06` previu
("componente que perde o último consumidor também reprova"), na maior escala possível.

**Resolvido em 07/08/2026, no PR #249** (que já estava aberto e precisava da base verde):

- os 7 apagados com prova de grep — zero referências fora de `docs/` — e mais um de
  **segunda ordem** que a primeira leva revelou: `cards/document_card.html`, que o `HT-06`
  mediu vivo porque os citadores dele eram exatamente `list_grid.html` e `ui_lab2/views.py`;
- `SO_NO_LABORATORIO` fica **vazia**, com a trava intacta para o próximo componente que
  nascer alcançável só por página de laboratório;
- piso da varredura 85 → 83, deliberado e comentado;
- `docs/COMPONENTES.md` sem os dois nomes apagados que ainda citava.

**A lição operacional é o motivo de a linha existir:** apagar árvore de template exige rodar
a suíte inteira antes do merge — a trava do `HT-06` é local e barata, e teria segurado o
`main` verde. O run 697 (`NOVO-43`) passou sobre a árvore do #246 por sorte de ordem: o
vermelho só apareceu quando o #247 entrou.

### NOVO-45 🟡 `NOVO` `faixa_lateral_class` é calculada por card em duas listas e nenhum template a lê · MOR · 0,25 d

`roteiros/presenters.py:261` põe `"faixa_lateral_class": _roteiro_faixa_lateral_class(roteiro)` no
dicionário do card, e `oficios/presenters.py:37` tem a função gêmea. As duas resolvem status,
comparam com `timezone.now()` e devolvem uma de cinco classes (`roteiro-list-card--faixa-*`). **Zero
templates leem a chave** — conferido por grep em `templates/` inteiro.

É o mesmo desenho do `NOVO-37` (`apresentar_acoes_oficio`): trabalho por card numa lista, para um
consumidor que deixou de existir e não avisou.

**Como apareceu, que é a parte que interessa.** A poda do `UI-01` marcou os 41 blocos de
`roteiro-list-card__*` como mortos. Antes de apagar fui conferir se o card ainda existia, e achei os
`--faixa-*` **vivos** — vivos porque o literal está no `.py`, que faz parte do corpus. Só que
literal em Python vivo e classe aplicada em HTML são coisas diferentes, e a varredura estática não
distingue as duas. As classes `--faixa-*` continuam no CSS por isso, protegidas pelo prefixo
dinâmico, estilizando um elemento que ninguém emite.

**Consequência para o `UI-01`:** a proteção por prefixo é generosa de propósito, e o preço é este —
classe morta que sobrevive porque o nome dela está numa string. Corrigir o `NOVO-45` derruba junto
os blocos `--faixa-*`.

### NOVO-46 🟡 `NOVO` Contrato de widget e template apontam para CSS que produção nunca carregou · MOR · 0,25 d

Já estava escrito dentro do `UI-01` como "defeito novo, separado"; vira linha para deixar de ser
nota de rodapé. `WidgetStyle.FORM_SELECT_FIELD_CONTROL` (`core/forms/widgets.py:27`) emite
`cv-field__control--select` em todo `<select>` do sistema, e
`templates/cadastros/servidores/partials/_form_fields.html:11` emite `cv-field-row`. As duas só
tinham regra em `static/css/dev/`, que **apenas** `templates/ui_lab2/base.html` e
`templates/dev/ui_lab/base.html` linkavam — nenhum dos dois entra no `shell.bundle.css`.

Com o `BE-25` (PR #247) os dois arquivos foram apagados. Nada mudou de aparência, porque produção
nunca os carregou: as duas classes já eram enfeite. O defeito não é visual, é de contrato — um enum
de widget que promete um gancho de estilo inexistente convida o próximo a estilizar por cima do que
ele acha que existe.

---

### NOVO-47 ✅ RESOLVIDO · 🟠 `NOVO` Duas CVEs do `pypdf` publicadas em 07/08 reprovam o passo 15 na `main` e em todo PR aberto · QA · 0,25 d

`CVE-2026-71852` e `CVE-2026-71870` atingem `pypdf==6.14.2`, a versão travada em
`requirements/lock.txt`. O passo **Audit Python dependencies** passou a reprovar, e por ser o passo
**15** ele anula tudo a jusante: a suíte completa, os pisos de cobertura e a régua do `PF-07` ficam
como `skipped`. Um PR que só mexe em CSS chega vermelho sem ter causado nada — foi assim que
apareceu, no #254.

**Não é regressão de nenhum PR.** O `lock.txt` do #254 é byte a byte igual ao da `main`; o último
verde da `main` (`c310aab`, 16:26) é anterior à publicação dos avisos. É a mesma forma do `NOVO-40`:
gate que depende de fonte externa e envelhece sozinho, sem ninguém tocar no repositório.

**Resolvido em 07/08:** `pypdf` 6.14.2 → 6.15.0, versão de correção indicada pelos dois avisos, em
`lock.txt` (com os dois hashes) e no piso de `base.txt` — subir só o lock deixaria a faixa aceitando
a versão vulnerável de volta na próxima recompilação.

Os três consumidores (`termos/services.py`, `prestacoes_contas/services.py` e
`assinatura_services.py`) usam `PdfReader`/`PdfWriter` na superfície estável; suíte verde, 1.744
testes, e `pip_audit` sem achado além do `PYSEC-2026-3412` já ignorado com justificativa.

### NOVO-48 ✅ RESOLVIDO (27e9642e, 09/08/2026) · `NOVO` Setenta nomes de classe morta sobrevivem dentro de seletor agrupado vivo · MOR · 0,5 d

Medido depois de o `UI-01` fechar: **140 partes de seletor** citando **70 classes** que não existem
em lugar nenhum do código, dentro de blocos que a poda não podia tocar. O caso típico:

```css
.cv-metric__description,
.cv-summary-tile__description,
.pt-resumo-box__sub {   /* <- esta não existe mais */
  color: var(--color-muted);
}
```

`cv-metric__description` é viva, então o bloco fica — e `pt-resumo-box__sub` pega carona.

**Por que não entrou no `UI-01`.** A poda apagou **blocos**; isto exige editar **seletores**, que é
outra operação e outro risco: errar uma vírgula muda quem recebe o estilo, e nenhum teste pega. A
catraca `audit_css_morto.py` também não conta estes — ela pergunta "o bloco inteiro está morto?", e
a resposta aqui é não. Fica declarado como buraco, junto com os seletores de atributo
(`[data-state=…]`), que continuam fora de todas as lentes.

**Peso é quase zero; o custo é de leitura.** Um nome morto num seletor agrupado faz o próximo leitor
acreditar que a classe existe, e é assim que ela reaparece num template.

Os campeões, para dar tamanho: `roteiro-editor__*` (6 nomes), `oficio-documentos-*` (7),
`cv-resource-picker__*` (4), `app-btn--*` e `btn-*` (9 entre os dois vocabulários de botão que o
`cv-btn--` substituiu).

**Resolvido na E2.** A varredura refeita depois do `NOVO-69` encontrou **66 nomes** ainda
presentes: a diferença para 70 é sobreposição dentro da própria etapa, não mudança de critério. O
pruner percorreu também regras aninhadas em `@media`/`@supports`, removeu **168 alternativas de
seletor** e **57 regras completas** em 18 fontes, preservando alternativas vivas de `:is()` e
simplificando `:not()` quando o argumento morto era o único. Depois: zero emissores em templates,
JS e Python de produção, zero seletores fonte com os 66 nomes, parse CSS sem erro,
`audit_css_morto --max 0` verde e `audit_ui_patterns` **2.622 → 2.583**.

---

### NOVO-49 🟠 `NOVO` Área nova nasce sem catálogo, e instalação nova mantém o catálogo no balde sem dono · DB · 1 d

Achado ao executar o grupo 2 do `DB-02`, e é o que **impede** aqueles quatro modelos de virarem
`NOT NULL` agora.

A duplicação por área (decisão do usuário em 07/08, seguindo o `NOVO-09`) resolve o acervo
existente: cada área passa a ter `TipoEvento`, `AtividadePlanoTrabalho`, `ProgramaSolicitante` e
`HorarioAtendimento` — hoje visíveis para **zero** usuários com área. Mas ela não fecha dois casos,
porque não tem como:

1. **Instalação nova.** Os seeds rodam em `eventos/0008`, `planos_trabalho/0002`, `0003` e `0008`,
   e nesse momento **não existe área nenhuma** — a migração de duplicação sai sem fazer nada, por
   guarda explícita. As 22 linhas ficam globais, exatamente como antes.
2. **Área criada depois.** `usuarios/services.py:criar_area` não semeia catálogo. A área nova nasce
   com os quatro catálogos **vazios**, e o usuário tem de recadastrar tudo à mão.

**Não é regressão desta fatia:** o caso 2 já vale para `ModeloJustificativa` desde o `NOVO-09`, que
duplicou o acervo e também não semeou área nova. Esta fatia estende o mesmo comportamento a mais
quatro modelos — e por isso o defeito fica maior e merece ID próprio em vez de nota de rodapé.

**Efeito sobre o `DB-02`:** enquanto a instalação nova produzir linha sem área, `area` não pode ser
`NOT NULL` nesses quatro. A migração de `NOT NULL` reprovaria no primeiro `migrate` de um banco
limpo — que é o banco da suíte, todo dia no CI.

**Correção candidata:** mover a lista canônica de cada catálogo para um módulo de dados iniciais
que dois caminhos consumam — `criar_area`, ao criar a área, e uma migração de saneamento para as
áreas que já existem. Os seeds históricos ficam onde estão (migração aplicada não se reescreve);
o que muda é quem passa a ser a fonte da verdade daqui para a frente. Só então `NOT NULL`.

---

### NOVO-50 🟡 `NOVO` Listas de ofícios e planos gastam ~130 ms em 20 linhas resolvendo `select_related` por `Nested Loop` · PF · a medir

Achado ao medir o `DB-10`, e é o motivo de o índice de ordenação não ter ajudado essas duas.

Depois do índice, o `Limit` **já para em 20 linhas** — o plano está certo nessa parte. Mesmo assim
`oficios:index` leva 120,9 ms e `planos_trabalho:index` 126,8 ms para montar essas 20 linhas. O
tempo está numa pilha de `Nested Loop Left Join` com `Join Filter`, resolvendo o `select_related`
contra `cadastros_cidade`, `cadastros_estado`, `cadastros_cargo`, `cadastros_unidade` e
`cadastros_viatura` sem condição de índice — `Rows Removed by Join Filter: 310`, `90`, `40` por
nível.

**Ressalva que impede fechar isto como defeito confirmado:** o semeador do
`scripts/medir_desempenho.py` cria **50 cidades, 5 estados, 5 cargos**. Tabela de dimensão desse
tamanho torna varredura sequencial mais barata que índice, e o planner escolhe `Nested Loop` com
razão. Em produção a tabela de cidades tem os municípios do país (ordem de 5.500), e o plano pode
ser outro — melhor ou pior.

**Primeiro passo:** medir de novo com `cadastros_cidade` em tamanho realista. Se o `Nested Loop`
sobreviver, é defeito de verdade e a correção provável é reduzir o `select_related` da lista ao que
o card realmente imprime. Se não sobreviver, esta linha vira nota no `DB-10` e o semeador é que
precisa de cidade de verdade — o que valeria por si, porque a régua do `PF-07` mede planos com
tabelas de dimensão irreais.

> **Feito em 08/08/2026, e as duas coisas eram verdade.**
>
> O semeador **precisava** de dimensão realista, e passou a ter: 27 unidades federativas com as
> siglas reais, 5.570 municípios, 3.000 servidores — no lugar de 5, 50 e 100. As tabelas de dimensão
> não crescem com `--volumes` porque são cadastro, não movimento; mas o tamanho delas decide o plano,
> e com 50 cidades o planner escolhia varredura sequencial **com razão**.
>
> **E o `Nested Loop` sobreviveu.** Com as dimensões de produção, `oficios:index` continua montando
> 20 linhas por `Nested Loop Left Join` com `Join Filter` (`Rows Removed by Join Filter: 90`), em
> ~99 ms. Não era artefato de semeadura: é defeito, e continua aberto. A correção provável segue
> sendo reduzir o `select_related` da lista ao que o card imprime.
>
> **O conserto do semeador desbloqueou outra medição na hora:** o `DB-11` (`pg_trgm`) só pôde ser
> respondido depois dele — ver lá.

### NOVO-49 ✅ RESOLVIDO · 🟡 `NOVO` O painel de `/` custava cinco consultas por login para uma tela que o dono não queria · MOR · 0,25 d

> **Aviso de numeração (08/08):** este é o **segundo** `NOVO-49` do arquivo — o outro é o de
> catálogo por área, do `DB-02`. É também a segunda colisão do ciclo: já havia dois `NOVO-45`.
> Não renumerei nenhum dos dois, porque ID de outra sessão não se renomeia pela metade (limite
> 2 do `AGENTS.md`) e branch aberta pode citar qualquer um. **A causa é de processo:** cada
> sessão escolhe "o próximo livre" a partir do próprio instantâneo e duas escolhem o mesmo.

`core/views.py:101` contava total de ofícios, ofícios em rascunho, assinaturas pendentes e prestações
pendentes, e ainda listava as viagens dos próximos 30 dias — **cinco consultas** montadas a cada
acesso. E `/` é `LOGIN_REDIRECT_URL`: toda sessão do sistema começa ali.

O dono pediu para apagar a tela. Como `/` também é o link da marca na barra lateral, o da barra
móvel, o `back_url` de duas telas de `cadastros` e a rota `painel` da régua do `PF-07`, **a rota
fica e o conteúdo sai** — trocar a rota mexeria em cinco lugares, trocar o conteúdo não mexe em
nenhum.

**Resolvido em 08/08:**

- as cinco consultas saíram da view; o que sobra é `render` com três strings;
- `templates/core/dashboard.html` perdeu boas-vindas, indicadores e viagens próximas. O que ficou —
  cabeçalho de página e quatro cartões de módulo — **não tem vocabulário próprio**: nenhuma classe
  `dashboard-*` sobreviveu;
- `static/css/dashboard.css` (138 linhas) apagado, mais 3 blocos e 1 seletor agrupado no tema
  escuro. A exceção de `hex_color_outside_tokens` que o arquivo tinha no auditor saiu junto;
- **cascata**: `components/cards/summary_card.html` perdeu o único citador e foi apagado. Desta vez
  a trava do `HT-06` reprovou **antes do merge** — é a diferença entre este ID e o `NOVO-44`, onde a
  mesma cascata só apareceu com a `main` já vermelha.

**Catracas que descem:** ORM em view **29 → 24** (é a maior queda de uma vez desde o `P-01`), e o
piso de componentes 83 → 82.

**A decisão de conteúdo é do dono e está registrada:** ele escolheu manter a rota e trocar o
conteúdo, entre quatro opções que incluíam redirecionar `/` para Ofícios, Eventos ou Roteiros.

**O PR chegou vermelho, e o defeito é de método.** Apaguei `dashboard.css` com prova de grep em
templates, JS e Python — e esqueci de olhar **CSS citando CSS**: `static/css/style.css:11` tinha
`@import url("./dashboard.css")`, e o `style.css` entra no bundle. Nenhum gate local pegou: a poda
olha bloco, o auditor de front olha linha, e nenhum dos dois resolve caminho de arquivo. Quem pegou
foi o `collectstatic` de produção (WhiteNoise, `MissingFileError`) — no **passo 14** do CI, depois de
os treze anteriores terem passado.

Fechada a lacuna: `scripts/audit_css_morto.py` passou a reprovar `@import` apontando para arquivo
inexistente, e a trava foi conferida com um import falso antes de valer. Custa um segundo, contra o
passo 14 do CI.

### NOVO-50 ✅ RESOLVIDO · 🟠 `NOVO` 255 das 464 cores do sistema são duplicata perceptual de outra · MED · 1 d

Primeira etapa da padronização que o dono pediu ("as cores do sistema também tudo diferente, mas o
sistema deve ser todo padronizado").

**Medido por distância perceptual, não por semelhança de texto.** `#d8a21b` e `#d9a40f` não se
parecem como string e são a mesma cor para o olho; agrupar por prefixo hexadecimal erraria dos dois
jeitos. A medida é **CIEDE2000** sobre Lab, com corte em ΔE 2,5 — o limiar em que um observador
treinado começa a distinguir duas amostras lado a lado.

| | |
|---|---:|
| valores hex distintos | **464** |
| duplicatas perceptuais | **255** |
| restam | **209** |

Os grupos maiores: **26 brancos** em torno de `#ffffff`, **25 azuis pálidos** em torno de `#e3eaf2`,
**16 azuis-marinho** em torno de `#132238`, **13 cinzas-azulados** em `#d4dde9`. Os três dourados da
marca (`#d8a21b`, `#d9a40f`, `#e0a800`) viraram um.

**O que NÃO foi colapsado, e é a parte que importa.** Duas cores a ΔE 1,5 podem ser ruído — ou podem
ser a base e o `:hover` do mesmo botão. Juntar o segundo caso apagaria o feedback de interação **sem
nenhum teste reprovar**: a página continua renderizando, só para de responder ao mouse. A regra: se
a mesma propriedade, no mesmo seletor-base, recebe duas cores diferentes em variantes de estado,
elas ficam. São **207 pares protegidos** assim, e três fusões deixaram de acontecer por causa deles.

**O efeito visual, medido nas 88 telas** (`getComputedStyle`, 41.844 elementos):

| | |
|---|---:|
| elementos com alguma cor diferente | 22.670 (54,2%) |
| ΔE mediano das mudanças | **0,96** |
| ΔE no percentil 95 | 2,23 |
| ΔE máximo | **2,48** |
| mudanças acima de 5 (visível a olho nu) | **0** |

É larga e imperceptível: mais da metade dos elementos mudou, nenhum o suficiente para alguém notar.
Antes/depois em imagem no corpo do PR.

**Catraca:** `scripts/audit_paleta.py --max 0`, no CI. Sem ela, o próximo PR que escrever `#f8fafd`
recria a duplicata — e ninguém vê, porque duas cores a ΔE 2 são a mesma cor na tela e valores
diferentes no arquivo.

**Fica aberto:** os 270 valores `rgb()/rgba()` não entraram nesta conta. E a consolidação de
`--cv-*` para `--color-*` (309 variáveis), decidida pelo dono, é o próximo passo — cor e nome de
token são coisas separadas e não viajam no mesmo PR.

### NOVO-51 🟠 PARCIAL (2 de 4 restantes fechados na E7b) · `NOVO` As 309 variáveis `--cv-*` são apelido de token, não token · MED · 2 d

Segunda etapa da padronização. O dono decidiu que **`--color-*` é a base semântica única** e que as
`--cv-*` somem. Não é um `sed`: `--cv-card-bg` não tem equivalente pelo nome, tem pelo **valor**. A
pergunta certa é "o que esta variável resolve no fim da cadeia, e qual `--color-*` resolve o mesmo".

Resolvendo as 309 **por tema** (o mesmo nome vale coisas diferentes no claro e no escuro):

| | |
|---|---:|
| apelido puro de um `--color-*` | 37 |
| definidas e **nunca usadas** | **58** |
| valor próprio, precisam de token novo | 214 |

**Entrou nesta leva:** as 58 órfãs e 21 dos 37 apelidos. Restam **231** `--cv-*` distintas.

**Na E7b (10/08/2026).** O `NOVO-65` levou as 231 e preservou de propósito a família `cv-field`,
porque o nome sem prefixo já pertencia a outra classe viva. Sobraram **4 nomes** — e um deles não
era apelido, era defeito.

`--cv-field-border` tinha **dois contratos incompatíveis**:

```
tokens.css:148          --cv-field-border: 1px solid var(--color-border-strong)   ← shorthand
03-theme-dark.css:293   --cv-field-border: 1px solid var(--color-input-border)    ← shorthand
select.css:94           --cv-field-border: var(--theme-input-border)              ← cor pura
```

`select.css` está em `:root` e carrega depois de `tokens.css` e antes de `03-theme-dark.css`, então
o token resolvia **cor pura no claro e shorthand no escuro**. Contra isso, 14 consumidores escreviam
`border: 1px solid var(--cv-field-border)` e 1 escrevia `border: var(--cv-field-border, …)`.

Conferido em Chromium com `getComputedStyle`, não deduzido da especificação:

| tema | forma | resultado |
|---|---|---|
| claro | `1px solid var()` — 14 sites | `solid 1px` ✅ |
| claro | `var()` — `file-picker.css:31` | **`style=none width=0px`** ❌ |
| escuro | `1px solid var()` — 14 sites | **`style=none width=0px`** ❌ |
| escuro | `var()` — file-picker | `solid 1px` ✅ |

No escuro os 14 viravam `border: 1px solid 1px solid #607d93`, declaração inválida que o parser
descarta. **Eram 15 bordas invisíveis em produção**, em `page-shell.css:2789,2831`,
`prestacoes_contas.css` (6×), `oficios.css:63`, `roteiros.css:2231` e `file-picker.css:31`.

Resolvido o contrato para cor pura (14 contra 1), o token virou **apelido puro de
`--color-input-border`** nos dois temas — e aí o `NOVO-51` se aplica como escrito. O mesmo valia
para `--cv-field-bg`, apelido puro de `--color-input-bg`. Os dois foram eliminados: 9 definições
apagadas, 36 consumidores apontados para a base semântica única.

**Ficam 2**, e nenhum é apelido: `--cv-field-border-focus` (claro `#0b3a66`, escuro `#286fa4`) e
`--cv-field-focus-ring` (claro `rgba(21, 91, 154, 0.18)`, escuro `none`). Nenhum `--color-*`
resolve o mesmo par. O segundo diverge de **fonte** entre os temas — no escuro vem de
`--focus-ring`, que vale `none` —, e isso toca visibilidade de foco, cujo auditor está com folga
zero (30 de teto 30). Promover os dois a token próprio exige decidir se o anel de foco do campo
deve mesmo sumir no escuro, que é pergunta de acessibilidade e não de vocabulário. Fica para a E8.

**Nota de método.** O auditor `audit_ui_patterns` conta `border: 1px solid var(…)` como
`hardcoded_visual` (o valor não começa com `var`) e **isenta** `border: var(…)`. Ou seja, a forma
quebrada era premiada e a correta é contada: 2453 → 2454. É falha da heurística, não da correção.

**Três correções de método, cada uma achada por medição e não por leitura.**

1. **Renomear a definição do apelido cria um ciclo.** `--cv-btn-docx-color: var(--color-white)`
   renomeado vira `--color-white: var(--color-white)`; o CSS invalida a variável e **tudo** que a
   usa perde o valor. Uma tela sozinha perdeu 60 elementos. O certo é **apagar a definição** do
   apelido e reescrever só os usos — o apelido some, não muda de nome.
2. **Variável CSS é escopada.** Um apelido com override local, renomeado, injeta esse override no
   escopo do token canônico. Ficaram de fora os que têm definição fora da raiz — dos dois lados.
3. **Definição com fallback não tem valor único.** `--cv-sp-selected-card-border:
   var(--theme-border-card, var(--color-border-soft))` vale uma coisa onde `--theme-border-card`
   existe e outra onde não existe; um resolvedor que achata a cadeia erra. Foram 7 apelidos fora da
   leva, depois de moverem 9 bordas de `#e3eaf2` para `#d4dde9`.

**Prova de neutralidade:** 0 de 41.950 elementos em 88 telas. Renomear token tem de ser invisível, e
as três correções acima são o que separou 1.602 elementos diferentes de zero.

**O que falta, e é onde entra decisão e não mecânica.** Os 214 de valor próprio, por natureza:

| natureza | quantas | observação |
|---|---:|---|
| cor | 99 | viram `--color-*` semânticos novos |
| **dimensão** | **73** | `--cv-btn-height: 44px`, `--cv-field-radius: 12px` — **não** são cor. Pedem `--size-*`, `--radius-*`, `--space-*` |
| sombra | 29 | pedem `--shadow-*` |
| gradiente | 8 | `--cv-btn-primary-bg` é um `linear-gradient` inteiro dentro de um token |
| borda-shorthand | 2 | `--cv-field-border: 1px solid #afc0d3` — três valores num token só |

As 73 de dimensão são o achado que muda o plano: um terço do que se chamava de token de cor nunca
foi cor. E há duplicata dentro delas — `--cv-search-picker-radius` e `--cv-field-radius` são os
mesmos `12px` escritos duas vezes.

**Registro, não defeito:** `--focus-ring: none` no tema escuro é **deliberado e documentado**
(`static/css/components/summary-items.css:74`): lá o foco é sinalizado pela borda do controle. Eu
tinha aberto isso como possível falha de acessibilidade e estava errado. Vira decisão quando o
escuro virar a base.

### NOVO-52 ✅ RESOLVIDO · 🔴 `NOVO` O editor de roteiro não tem foco visível em campo nenhum, nos dois temas · HT · 0,25 d

`static/css/roteiros.css` tinha **dois blocos** com `outline: none !important` mirando 16 classes de
campo dentro de `.oficio-roteiro-body`. Eles vencem o piso de acessibilidade do `base.css:111` — que
é `!important` mas perde por ordem de cascata — e apagam o foco de teclado do editor inteiro.

**Medido por navegação de teclado real**, não por leitura de CSS:

| rota | campos alcançados por Tab | com anel de foco |
|---|---:|---:|
| `/roteiros/novo/` | 9 | **0** |
| `/cadastros/configuracao/` | 9 | 9 |
| `/termos/novo/` | 6 | 6 |

As duas últimas são o controle que prova que a medição funciona. E a verificação foi feita na
**árvore inteira de ancestrais**: não havia anel em nível nenhum, e a borda do controle é
transparente — o campo não dava sinal nenhum de estar focado, nos dois temas.

**A intenção dos blocos era legítima**: `:focus-within` casa o container **e** o campo, então sem
cuidado aparecem dois anéis concêntricos. Mas desligar os dois em toda parte troca um problema
cosmético por um de acessibilidade.

**Resolvido em 08/08:** os dois blocos apagados, 67 linhas, **sem CSS novo**. O piso do `base.css`
passa a valer, e é ele que já acende o anel nas telas que funcionavam — ou seja, o editor voltou ao
comportamento padrão do sistema em vez de ganhar um comportamento próprio.

**Uma tentativa minha que estava errada, registrada porque ensina.** Antes de chegar aqui eu
adicionei uma regra global de `:focus-within` no container do picker. Ela produziu **anel duplo** —
confirmado por print, não por medição booleana, que dizia "tem anel" nos dois níveis sem dizer que
eram dois. A regra era desnecessária: o anel canônico deste sistema mora no próprio controle.
Apagar o excesso bastava; acrescentar foi o instinto errado.

**Catraca:** `audit_foco_visivel` **32 → 30**.

### NOVO-53 🟠 PARCIAL · `NOVO` A maiúscula dos campos é decidida campo a campo, em dois apps de onze · HT · 1 d

O dono pediu "tudo uppercase" nos campos e escolheu, entre duas opções, a que **muda o valor** —
máscara — e não `text-transform`. A diferença é de produto: o que chega ao banco vem em maiúscula, e
o documento gerado sai igual à tela.

A regra já existia, copiada: `cadastros/forms.py:65` e `oficios/forms.py:185` fazem
`setdefault("data-mask", "upper")` sobre todo `CharField`. Os outros nove apps não fazem.

**Centralizado em `core/forms/widgets.py`**, no caminho que todo formulário estilizado já usa
(`set_widget_style`). Cobertura medida instanciando todos os formulários dos onze apps: **30 campos
de texto** passam a receber a máscara pelo caminho central.

**As exceções não são estética, são corretude.** Uma delas obriga a lista a existir:

> `username` maiusculizado faz o usuário enviar `TIAGO` contra um registro gravado `tiago`. O Django
> compara byte a byte. **O sistema para de autenticar.**

As demais seguem o mesmo princípio — maiusculizar destrói informação: senha vira outra senha; a
parte local do e-mail é case-sensitive (RFC 5321 §2.4); caminho e query de URL são case-sensitive na
maioria dos servidores. E `textarea` é a exceção que o próprio dono abriu.

Seis testes fixam o contrato, incluindo um que confere que o **motor de JS conhece o modo `upper`** —
sem ele, `data-mask="upper"` poderia ser espalhado pelo sistema apontando para um modo inexistente,
e nada falharia: o atributo ficaria no HTML, inerte.

**Falta, e é onde entra decisão:** **32 campos de texto** declaram o widget inline
(`forms.TextInput(attrs={**widget_attrs(...)})`) e não passam pelo caminho central —
`prestacoes_contas` (11), `planos_trabalho` (8), `eventos` (4), `cadastros` (3), `core` (3),
`oficios` (2), `justificativas` (1). Cobri-los exige decidir campo a campo, porque entre eles estão
`LoginForm.username` e `PerfilUsuarioForm.username`, que **não podem** receber a máscara.

**Fica declarado o que este ID NÃO faz:** os registros já gravados continuam com a caixa que tinham.
A máscara vale do próximo cadastro em diante. Uniformizar o histórico é migração de dados, com
contagem por campo, e é decisão separada.

### NOVO-54 ✅ RESOLVIDO · `NOVO` `.cv-field__control` não tem regra base — o campo é o elemento cru mais 64 correções · UI · 2 d

A classe de campo com maior alcance do sistema — **11 templates, 30 rotas** — não tinha nenhuma
regra base. Ela existia só em **64 regras de sobrescrita** espalhadas por **14 arquivos**, com **70
`!important`**. O que pintava o campo de fato era o seletor de elemento nu `input, select, textarea`
em `base.css:59`.

**Não é que os campos divergiram: nunca existiu um campo.** Existia o elemento cru do navegador e um
monte de correção por cima. Daí saem, medidos:

| propriedade | quantos jeitos |
|---|---:|
| `background` | **27 cadeias distintas** |
| `border-radius` | 13 valores — `12px` escrito com 4 nomes de token, mais 4 literais de `10px` |
| altura | 7, com **5 nomes de token diferentes valendo o mesmo 44px** |

**Remedido na E7c (10/08/2026).** A regra base já existe — `:where(.cv-field__control)` em
`fields/field.css:53`, com especificidade **zero** de propósito. O que falta é remover o que ela
tornou redundante. Contando com parser de blocos (o grep de uma linha subconta: cheguei a reportar
37 no PR #295, e estava errado):

| | |
|---|---:|
| regras que tocam a classe | **63** em 19 arquivos |
| base (`:where`) | 2 |
| estado (`:hover`, `:focus`, `:disabled`…) | 15 |
| tema escuro | 15 |
| contexto (dentro de um container) | 24 |
| outras | 7 |
| `!important` | **67**, em 19 regras |

Os 67 `!important` são o alvo mais óbvio: a base tem especificidade zero, então **nenhuma regra de
classe precisa de `!important` para vencê-la**. Só que "não precisa contra a base" não é o mesmo
que "não precisa contra as outras 62", e a diferença tem que ser medida, não deduzida.

**O que trava a etapa: o instrumento não alcança.** `scripts/medir_campos_computados.py` (novo)
fotografa o estilo computado de todo `.cv-field__control` nas 43 rotas, nos dois temas, em quatro
estados forçados por `CSS.forcePseudoState`. Rodando, ele encontra campo em **8 rotas** — 64
combinações, 224 leituras. As outras 35 devolvem zero, e não por defeito do script: dos 11
templates que emitem a classe, a maioria é partial que só entra no DOM depois de interação
(`cancel_reason_modal.html` atrás de um modal, `_atividades_body.html` dentro de um passo de
wizard, `_diarias_fields.html` num corpo colapsável).

Então um diff vazio hoje prova neutralidade para o que essas 8 rotas exercitam, e **nada além**.
Remover regra de contexto que só vale dentro de modal seria remover sem prova — exatamente o que o
plano proíbe ao exigir "uma medição por vez", e como a primeira tentativa mexeu em 55 elementos
sem querer.

**Nenhuma regra foi removida.** O que ficou pronto foi o instrumento e a medição do próprio
instrumento. Ampliar o alcance — abrir os modais, navegar os passos do wizard, expandir os corpos
colapsáveis — é a primeira metade da E7c, e é o que destrava a segunda.
| borda | 6 formas de declarar a mesma linha de 1px |

**`static/css/components/field.css`** dá o lar que faltava. Os valores são **exatamente** os que
`base.css` já entrega: este ID cria o lugar, não muda a aparência. Misturar as duas coisas num PR só
tornaria impossível atribuir qualquer diferença medida a uma delas.

**A correção de método:** a primeira versão usou `.cv-field__control` nua. Especificidade 0,1,0
contra 0,0,1 do seletor de elemento — a regra base passou a **vencer** estilos de contexto legítimos,
e a medição pegou: **55 elementos** mudaram, com raio indo de 12px para 14px e borda de 0 para 1px em
campos deliberadamente sem borda. Com `:where()`, que zera a especificidade, a regra vira o que uma
base deve ser: vale onde ninguém disse nada e perde para qualquer coisa que diga. **1 elemento de
41.950.**

**O que muda é o lugar.** A partir daqui existe **um** ponto onde a aparência de um campo é
decidida, e as 64 sobrescritas viram dívida visível em vez de arquitetura. A ordem seguinte é
remover as redundantes — as que já declaram o que a base entrega, e cuja remoção é provadamente
neutra — e depois converter as divergentes, uma medição por vez.

### NOVO-55 ✅ RESOLVIDO · `NOVO` Fecha a máscara de maiúscula nos 29 campos que declaravam o widget inline · HT · 0,5 d

Continuação do `NOVO-53`, com o dono aprovando campo a campo. Os 32 que faltavam declaram o widget
inline (`forms.TextInput(attrs={**widget_attrs(...)})`) e por isso não passavam pelo caminho central.

**Três ficaram de fora, e a razão é a mesma do `username`** — maiusculizar destrói o propósito do
campo, não só a estética:

| campo | por quê |
|---|---|
| `LoginForm.username` | o Django compara byte a byte; o sistema para de autenticar |
| `PerfilUsuarioForm.username` | idem |
| `OficioTransporteForm.transporte_busca_ui` | caixa de busca ("Buscar por placa, unidade…"), não é valor gravado |

**Cobertura final: 59 campos de texto com a máscara, e nenhum widget de outro tipo.**

**Dois defeitos meus, achados medindo depois de aplicar.** Nenhum dos dois quebrava teste.

1. **A substituição por janela vazou uma linha.** Trocar `widget_attrs` por `text_attrs` a partir da
   âncora do campo pegou o `forms.NumberInput` da linha seguinte, em dois lugares. Revertidos por uma
   checagem que olha para trás e confirma que o `forms.XxxInput(` que contém a troca é `TextInput`.
2. **O `NOVO-53` marcava widget que não é campo de texto.** A regra perguntava "não está na lista de
   exceções? então marca", e com isso `Select` (12), `CheckboxInput` (3) e `HiddenInput` (2) ganhavam
   `data-mask="upper"` — **17 widgets**. Não quebrava nada: `masks.js` só liga em `input[data-mask]` e
   `textarea[data-mask]`, então o atributo ficava inerte. Mas atributo inerte no HTML é exatamente o
   que o próximo leitor interpreta como contrato. A pergunta foi invertida: agora é `isinstance(widget,
   TextInput)` e não `not isinstance(widget, EXCECOES)`.

O helper `text_attrs` existe para a decisão ficar **no ponto de declaração**: `widget_attrs` devolve
um dicionário e não sabe qual widget vai recebê-lo — o mesmo estilo alimenta `TextInput`,
`EmailInput` e `Textarea`. Quem escreve `text_attrs` está dizendo "este campo é texto simples e vai
em maiúscula", e um revisor vê a decisão campo a campo.

### NOVO-56 ✅ RESOLVIDO · 🔴 `NOVO` Dois formulários maiusculizam `username` — a exceção existe, mas o nome do campo não chega até ela · COR · 0,25 d

`UsuarioEditForm` e `UsuarioAreaCreationForm` põem `data-mask="upper"` no campo de login. É
exatamente o caso que o `NOVO-53` documentou como o motivo de a lista de exceções existir:

> `username` maiusculizado faz o usuário enviar "TIAGO" contra um registro gravado "tiago". O
> Django compara byte a byte. O sistema para de autenticar.

**A regra estava certa; a chamada é que perdia o argumento.** `set_widget_style` recebe `nome` e
consulta `NOMES_SEM_MAIUSCULA`, mas `EstiloCamposMixin` (`usuarios/forms.py:32`) iterava
`self.fields.values()` — que descarta o nome. Sem nome, `nome in NOMES_SEM_MAIUSCULA` é sempre
falso, e a lista de exceções nunca é consultada. O mesmo em mais três laços: `cadastros/forms.py`,
`oficios/forms.py` e `core/forms/__init__.py`.

**Efeito medido, e ele é dos dois lados:** criar usuário por `UsuarioAreaCreationForm` grava
`ADM.TSANTOS`, e o login (`LoginForm.username`, este sem máscara) manda `adm.tsantos` contra ele —
`ModelBackend` usa `get_by_natural_key`, que é `username=` exato. E salvar um usuário existente pelo
`UsuarioEditForm` **reescreve o username de quem já entrava**, tirando o acesso de quem tinha.

**Como apareceu.** Não foi leitura de código: foi o inventário do `NOVO-57` listando
`auth.User.username` entre os campos a migrar. Um comando escrito para contar linhas achou um
defeito de autenticação porque perguntou "quais campos têm a máscara" ao sistema em vez de à
documentação.

**Por que os testes do `NOVO-53` não pegaram.** Os sete existentes chamam `set_widget_style`
diretamente, passando `nome="username"` à mão — e passavam, porque a função está correta. Nenhum
instanciava formulário. A correção traz `MascaraNosFormulariosReaisTests`, que percorre os
formulários dos apps e olha o `data-mask` que vai para o HTML. Visto vermelho com as duas violações
nomeadas antes do conserto.

**Segunda correção, no mesmo lugar.** `BaseCadastroForm` decidia a máscara por conta própria
(`if isinstance(field, forms.CharField): setdefault("data-mask", "upper")`). `EmailField` e
`URLField` **são** `CharField`: o dia em que um cadastro ganhasse e-mail, ele seria maiusculizado em
silêncio. A regra local saiu; quem decide agora é a central, que pergunta pelo widget e pelo nome.

**Medição do antes/depois:** 274 campos de formulário inspecionados, **2 alterados**, ambos
`username`, ambos perdendo a máscara. Nada mais se moveu — as regras locais de `cadastros` e
`oficios` eram exatamente cobertas pela central. A cobertura da máscara vai de **59 para 57**
campos; o número 59 registrado no `NOVO-55` estava certo quando foi medido e incluía estes dois.

### NOVO-57 🟠 PARCIAL · `NOVO` A máscara vale do próximo cadastro; os registros já gravados ficam na caixa antiga · DB · 0,5 d

O `NOVO-53`/`NOVO-55` puseram a máscara em 57 campos de texto. Ela age no navegador, então vale do
próximo salvamento em diante: o que já estava no banco continua como foi digitado. O mesmo campo
passa a ter duas populações, e quem lê a lista vê a diferença.

`core/management/commands/normalizar_maiusculas.py` fecha a dívida. Sem `--commit` ele só relata,
como o `backfill_legacy_areas` — e aqui a convenção pesa mais, porque a operação é destrutiva por
natureza: "São Paulo" vira "SÃO PAULO" e não volta sem backup.

**A lista de campos não está escrita no comando.** Ela é derivada de onde a decisão mora — o widget
do formulário. Campo que ganhar `text_attrs` amanhã entra no relatório sem ninguém editar o arquivo;
campo que sair da máscara some dele. Foi essa escolha que expôs o `NOVO-56`.

**Um defeito meu, achado pela suíte, e ele era sério.** A primeira versão usava `Upper()` do Django,
que vira `UPPER()` no SQL. Isso delega ao banco a definição de "maiúscula" — e quem define isso neste
sistema não é o PostgreSQL, é o `toUpperCase()` do navegador, que a máscara aplica ao digitar. A
suíte mostrou em uma linha: em SQLite, `UPPER('Reunião')` devolve `'REUNIãO'`, maiúsculo só no
ASCII. Num sistema em português quase todo nome tem acento, e o resultado seria caixa **mista** —
pior que o estado que a migração veio corrigir, e irreversível.

Em PostgreSQL com locale UTF-8 o acento sai certo, e é exatamente por isso que não apareceu em
desenvolvimento: lá os dois caminhos concordam. "Certo desde que o servidor esteja com o locale
certo" não é garantia aceitável num `UPDATE` sobre a base inteira. Agora a maiúscula e a comparação
que decide o que diverge usam `str.upper()`, que segue o mesmo mapeamento Unicode do JavaScript. A
escrita é `bulk_update`, que também não dispara `auto_now`.

**Só encontrei porque errei antes.** Rodei a suíte com `config.settings.dev` em vez do
`config.settings.test` que o `AGENTS.md` §7 manda — e `dev` liga o limitador de login, que devolveu
403 em 10 testes de `usuarios.tests.test_admin_page` (reproduzidos na `main` intocada, então não eram
regressão). Ao repetir com as configurações certas, a suíte caiu em SQLite, e foi o SQLite que expôs
o defeito do acento. O gate correto pegou o que o gate errado escondia.

**A colisão de unicidade quem decide é o banco.** "Reunião" e "REUNIÃO" convivem hoje e não convivem
em maiúscula. Agrupar por valor em Python reimplementaria a semântica de unicidade — e ela não é
simples: `TipoEvento` tem duas `UniqueConstraint` com `condition`, uma só para linhas sem área e
outra só para linhas com área; agrupar ignorando a condição bloquearia campo que está bem. Então o
`UPDATE` roda dentro de um savepoint por campo. Passou, passou de verdade — com condição, colação e
índice parcial. Falhou, o savepoint volta, o campo fica de fora e a mensagem do PostgreSQL (que
nomeia a restrição e o valor duplicado) entra no relatório. O bloqueio é **por campo**, não por
linha: migrar as outras e deixar o par para trás daria um campo meio migrado, que é o pior estado.

**A simulação escreve e desfaz**, pelo mesmo caminho da aplicação. Um "vai dar certo" que não tentou
escrever não vale nada num campo com restrição de unicidade.

**Por que fica PARCIAL.** O levantamento abaixo é do banco de **desenvolvimento**, e ele é pequeno
demais para decidir qualquer coisa — 72 linhas no total. O número que importa é o de produção, e
este comando existe justamente para que ele possa ser levantado lá sem escrever nada:

| | |
|---|---|
| campos de modelo com máscara | 44 |
| linhas nesses campos (dev) | 72 |
| linhas divergentes (dev) | 20 |
| campos bloqueados por unicidade (dev) | 0 |

Os quatro campos com divergência em dev: `eventos.TipoEvento.nome` (5), `AtividadePlanoTrabalho.nome`
(11), `HorarioAtendimento.faixa` (3), `usuarios.AreaTrabalho.nome` (1).

**Fecha quando** a contagem rodar contra produção, os campos bloqueados (se houver) forem resolvidos
no sistema, e o `--commit` for aplicado com backup.

### NOVO-58 ✅ RESOLVIDO · `NOVO` Claro e escuro não são dois temas do mesmo sistema: são dois desenhos diferentes · UI · a decidir

Medido com `getComputedStyle` nas 44 rotas, comparando o **mesmo elemento** nas duas versões do
**mesmo documento** e olhando **só propriedades que não são cor** — cor é o que um tema tem direito
de mudar; o resto deveria ser igual.

| | |
|---|---|
| elementos comparados | 20.975 (44 telas) |
| elementos com ao menos uma diferença não-cor | **20.203 — 96%** |
| diferenças no total | 45.726 |
| pares de valor distintos (as *decisões* que divergiram) | **851** |
| elementos que ainda divergem ignorando a fonte | 6.882 (33%) |

**A maior diferença isolada é a fonte do sistema inteiro.** `tokens.css:176` define
`--font-sans: "Segoe UI", Arial, sans-serif`, e `theme-dark-components.css:16` sobrescreve o `body`
com `Inter, "Segoe UI Variable", …`. São **19.896 elementos** com pilha de fonte diferente conforme o
tema.

> **Cuidado com o que este número é.** Ele mede a pilha **declarada**, não a face que o usuário vê.
> `Inter` **não está no repositório** — não há `@font-face` nem arquivo (os únicos em
> `static/vendor/fonts/` são as fontes de assinatura). Então o escuro pede uma fonte que o sistema
> não entrega, e o que aparece depende do que estiver instalado em cada máquina. **Não dá para
> determinar daqui** qual face renderiza para o usuário: neste contêiner Linux, `Inter`,
> `Segoe UI Variable` e `Segoe UI` devolvem largura idêntica (811,06 px para a mesma frase), o que é
> substituição do fontconfig, não instalação. Medir isso exige uma máquina igual à do usuário.

As demais divergências sistemáticas, com a contagem de elementos:

| propriedade | claro | escuro | elementos |
|---|---|---|---|
| `font-size` | 16px | 14px | 533 |
| `line-height` | 24px | 21px | 533 |
| `border-*-width` | 0px | 1px | 1.416 |
| `border-radius` | 14px | 10px | 940 |
| largura da barra lateral | 191/216px | 231/252px | 976 |
| `height` de controle | 46px | 42px | 378 |
| `justify-content` | normal | center | 230 |

Concentradas em `sidebar-*` (2.956 + 2.200 + 880 + 748 + 572 + 440), `cv-custom-select__option`
(1.604), `cv-dialog__*` (1.151) e `cv-date-picker__footer-action` (640).

**Não é deriva acidental: está escrito no cabeçalho do arquivo.**

> `theme-dark-components.css` — *transitional dark-theme component overrides. Long-term: dissolve
> into owning component files. **Extracted from dark-redesign.css** (Etapa 7, Fase 6).*

Houve um redesenho, ele foi aplicado **só no escuro**, e o arquivo que deveria ser transitório virou
5.690 linhas permanentes. O tema claro é o desenho **anterior** ao redesenho — e é o que o sistema
mostra por padrão para quem não escolheu tema.

**O instrumento.** Diferença de ordem de captura foi descartada como artefato: medindo claro→escuro
e escuro→claro nas mesmas 3 rotas, 2.820 diferenças nas duas, **0** exclusivas de uma ordem. E a
transição de tema é desligada antes de medir, senão a captura pega o valor no meio da interpolação
(erro que já custou 418 elementos de ruído numa medição anterior).

**Por que isto muda o plano.** A etapa estava descrita como "inverter o tema: escuro vira base, claro
vira espelho", como se fosse reorganização de token. Não é. Espelhar significa **aplicar o redesenho
ao tema claro**, o que muda a aparência de todas as 44 telas no modo claro — fonte, tamanho de texto,
raio, borda e largura da barra lateral. É trabalho de desenho, não de arrumação, e precisa da decisão
do dono antes da primeira linha de CSS.

**Fechamento da E8 (11/08/2026).** A E8-zero foi repetida depois de todos os recortes intermediários,
sem tocar em CSS: **43 rotas × 3 larguras = 129 medições**, **54.225 elementos comparados**, **0
elementos divergentes, 0 diferenças não-cor e 0 pares distintos**. O instrumento mediu nas duas
ordens de tema e manteve a trava de layout estável; o relatório passou os tetos vigentes. A dívida
descrita acima foi consumida pelas famílias já integradas e não resta redesenho a aplicar. O foco de
campo do `NOVO-51`, por ser cor/a11y, continua uma decisão separada e não altera este fechamento.

### NOVO-59 ✅ RESOLVIDO · 🔴 `NOVO` Todo ícone de botão é invisível no tema claro, no sistema inteiro · UI · 0,25 d

Primeiro recorte do `NOVO-58`, e o único que **não é redesenho: é defeito**. Por isso vem antes de
qualquer decisão de desenho — não depende de escolher nada.

`.cv-icon` é um `<svg>` sem `width`/`height` no atributo, e `.cv-btn__icon` nunca teve regra base.
Quem dava tamanho ao ícone dentro de botão era esta regra, em `theme-dark-components.css:5240`:

```css
/* Ícones dentro de botões: tamanho e alinhamento consistentes. */
:is(html[data-theme="dark"]) .cv-btn__icon .cv-icon { … }
```

O comentário promete consistência; o seletor entrega num tema só. **Sem ninguém dizer o tamanho, o
SVG colapsa.** No claro, o ícone de "Limpar filtros" mede `0×0`; no escuro, `17×17`. Não é ícone
diferente entre os temas — é ícone que **não aparece** no claro, em botão nenhum do sistema.

**Correção:** a regra sai do arquivo de tema e vai para `cv-buttons.css`, sem escopo de tema, com
`:where()` para especificidade zero — mesma razão do `field.css` (`NOVO-54`): base vale onde ninguém
disse nada e perde para contexto que diga, e existem contextos que dimensionam este ícone por conta
própria (`list-header.css:1029`, `action-system.css:340`). O token `--cv-btn-icon-size: 17px` já
morava no `:root` do `tokens.css`, então não foi preciso mover nada de valor.

**Medido nas 88 telas (44 rotas × 2 temas), `getComputedStyle`:**

| | claro antes | claro depois | escuro antes | escuro depois |
|---|---|---|---|---|
| `.cv-icon` com caixa | 103 | **176** | 176 | 176 |
| `.cv-icon` em `0×0` | 323 | **250** | 250 | 250 |

**O claro passou a ser idêntico ao escuro.** Dos 41.950 elementos, 847 mudaram — **todos no tema
claro, zero no escuro**, que é o resultado que a mudança tinha que ter: mover a regra não podia
alterar o tema que já a tinha.

Os 250 que continuam em `0×0` **não são defeito e existem igualmente nos dois temas**: conferido com
`checkVisibility()` em 5 rotas, são **39 ícones dentro de ancestral oculto** (diálogo fechado, menu
não aberto) e **0 ícones visíveis sem caixa**. Elemento escondido não tem caixa; isso é o navegador
funcionando.

**O que não entra aqui:** as outras 850 decisões divergentes do `NOVO-58` (fonte do sistema,
`font-size`, raio, borda, largura da barra lateral). Aquilo é aplicar um redesenho ao tema claro e
muda a aparência de todas as telas — precisa da decisão do dono, e este PR não a antecipa.

### NOVO-51 (continuação) ✅ Poda dos 55 apelidos puros: `--cv-x: var(--y)` deixa de existir · MED · 0,5 d

Terceira e maior leva do `NOVO-51`, e ataca exatamente o que o dono nomeou: *"tudo usando tokens
dentro de tokens ao invés de só usar o token comum"*. `--cv-field-radius: var(--radius-control)` não
é um token — é um segundo nome para um token, e quem lê a regra precisa de dois saltos para saber o
valor.

**`--cv-*` definidos: 230 → 176.** 58 definições apagadas, 149 usos reescritos, 17 arquivos.

**Três travas, e cada uma existe porque já falhou antes:**

1. **Apagar a definição, nunca renomeá-la.** Renomear para o alvo produz `--y: var(--y)` —
   auto-referência, que o CSS invalida. Já custou 60 elementos sem cor numa página.
2. **Só apelido definido no escopo raiz.** O filtro recusou `--cv-btn-docx-bg`,
   `--cv-card-family-bg` e outros 20 por estarem dentro de `html[data-theme="dark"]` ou de um
   componente: ali a troca deixa de ser mecânica, porque o alvo pode estar redefinido em outro
   escopo.
3. **Só `var(--y)` exato, sem fallback.** `var(--y, #e3eaf2)` carrega a decisão de o que fazer
   quando `--y` não existe. Sete apelidos assim já moveram 9 bordas quando tratados como
   equivalentes.

Dos 230, **175 foram recusados** por uma dessas travas — a poda mecânica só alcança o que é
provadamente mecânico. O alvo é resolvido **transitivamente**: `--cv-btn-height-md` →
`--cv-btn-height` → `--control-height-md`, senão a troca só empurraria o salto adiante.

**Um defeito meu, achado pela contagem depois de aplicar.** O apagador exigia `;` no fim da linha, e
`--cv-btn-height-control: var(--control-height-md); /* 44px — emparelha com inputs */` tem comentário
depois do ponto e vírgula. A definição sobreviveu à poda dos usos e virou órfã. Só apareceu porque
conferi "definidos e não usados" em vez de confiar no relatório do próprio script. Removida, com a
prova de ausência que o `AGENTS.md` §3.6 pede: `grep -rn -- "cv-btn-height-control"` em `static`,
`templates` e nos 12 apps → **0**.

**Medição: 0 elementos alterados** em 41.950, nas 88 telas (44 rotas × 2 temas), `getComputedStyle`.
É o resultado exigido — apelido é por definição um nome a mais para o mesmo valor, então trocar o
nome pelo valor não pode mudar pixel nenhum. Qualquer diferença aqui seria prova de que o apelido
**não** era puro.

### Anotação no `NOVO-58`: dois tokens só existem no tema escuro

Levantado ao filtrar os apelidos por escopo. `--cv-card-family-bg` é definido só dentro de
`html[data-theme="dark"]` (`03-theme-dark.css:126`) e lido em duas regras **sem escopo** de
`list-header.css` (linhas 80 e 437); `--color-accent-text` tem um caso igual em
`planos-trabalho-atividades.css:104`. Variável ausente invalida a declaração inteira, sem aviso.

**Conferido no navegador, e NÃO é defeito visível:** no claro o token sai `""` e
`.list-header__rail` fica `rgba(0,0,0,0)` — mas `.cv-record-card__band`, que o comentário da regra
cita como par ("mesmo token da área interna dos cards"), também não é pintado no claro. Os dois
combinam. É declaração que não faz nada, não fundo faltando. Fica registrado como higiene junto do
resto do `NOVO-58`, não como correção urgente — e o `var(--x, fallback)` que já existe em dois usos
do mesmo token (linhas 988 e 993) mostra que alguém já tropeçou nisto antes.

### NOVO-60 🟠 `NOVO` A renomeação por função é 98% mecânica — e os 2% restantes são arqueologia, não digitação · UI · a decidir

Levantamento para a renomeação que o dono aprovou (inglês, sem `cv-`, nome pela função, prefixo só
quando o nome sozinho for ambíguo). O número que decide o formato do trabalho:

| | |
|---|---|
| classes no CSS | 1.864 |
| das quais `cv-*` | 598, em 95 blocos |
| **colidiriam com classe existente se o `cv-` fosse só removido** | **13** |

Ou seja: **585 das 598 podem ser renomeadas mecanicamente.** As 13 exceções são o trabalho de
verdade, e cada uma é um caso.

**Dez das treze estão mortas** — 0 usos como token de classe em `templates/`, `static/js/` e nos
apps: `alert--danger`, `btn`, `btn--ghost`, `btn--lg`, `btn--sm`, `btn-group`, `chip`,
`form-section-header`, `summary-card`, `summary-label`. O único hit de `btn` é
`assertNotIn("btn btn-secondary", source)` em `core/tests/test_dark_redesign.py:562` — um teste que
já guarda a ausência do nome antigo. O único de `chip` é o nome da função
`_evento_temporal_chip`, não uma classe.

**Três estão vivas, e cada uma é um problema diferente:**

| classe | usos | o que realmente é |
|---|---|---|
| `.field` | 89 | 51 no **mesmo elemento** que `cv-field`, 25 sozinha |
| `.alert` | 11 | não faz par com `cv-alert` — faz com **`cv-notice`** |
| `.module-card` | 1 | no mesmo elemento que `cv-module-card` |

O caso do campo mostra o problema inteiro numa linha
(`components/ui/modals/cancel_reason_modal.html:20`):

```html
<div class="field app-form-field cv-field cancel-reason-modal__field">
```

**Quatro nomes para um campo, no mesmo elemento.** E o alerta tem cinco
(`components/ui/feedback/alert.html:21`): `cv-notice cv-notice--{{v}} alert alert-{{v}} alert--{{v}}`.
Não são componentes concorrentes disputando o nome — é o mesmo elemento carregando as duas gerações
ao mesmo tempo. Onde é assim, tirar o nome antigo é **remoção**, não fusão. Onde não é (`.field`
sozinha em 25 lugares, `.alert` que aponta para `cv-notice`), é decisão.

**Correção de rumo, e ela importa para o método.** A primeira medição destes 13 foi por contagem de
elementos no navegador, nas 44 rotas: deu `.alert` = 0 e eu quase registrei "11 de 13 mortas". Está
errado — `.alert` tem 11 usos em template, e só não apareceu porque alerta é renderizado em condição
de erro que a varredura não provoca. **Rota visitada não é cobertura.** Quem decide morte aqui é o
grep por token de classe; o navegador só confirma vida, nunca ausência.

**O `chip` era o candidato natural para o primeiro PR, e é justamente o que não serve.** Renomear
`cv-chip` → `chip` faria os chips passarem a casar com
`html[data-theme="dark"] :is(.badge, .chip, .status-badge, .cv-status-pill)`
(`theme-dark-components.css:3801`), herdando `border-color: var(--color-border-strong)` no escuro.
A regra está morta hoje, mas o nome não estaria depois da troca. `chip` é ambíguo neste código —
`cv-chip`, `.chip`, `.status-chip`, `.badge` —, e é exatamente o caso que a regra do dono cobre.

**Ordem sugerida:** (1) apagar os 10 nomes mortos, com prova de grep; (2) resolver os 3 vivos, um
por vez, porque cada um é uma decisão; (3) só então a renomeação mecânica dos 585, família por
família.

### NOVO-61 ✅ RESOLVIDO · 🟡 `NOVO` Dez nomes de classe mortos sobrevivem dentro de seletor agrupado vivo · MOR · 0,25 d

Primeiro passo da ordem proposta no `NOVO-60`: apagar os nomes provadamente mortos, antes de
qualquer renomeação. Mesma família do `NOVO-48`.

Nove dos dez do `NOVO-60` (`alert--danger`, `btn--ghost`, `btn--lg`, `btn--sm`, `btn-group`,
`chip`, `form-section-header`, `summary-card`, `summary-label`) **mais `cv-btn-group`**, que só
apareceu depois: enquanto `.cv-btn-group, .btn-group` dividiam o seletor, o auditor via um nome
"vivo" e não contava o bloco. Removido o morto, o outro ficou exposto — e também tem **0 usos**.
Nome morto escondendo nome morto é o padrão do `NOVO-48`.

**`.btn` ficou de fora, e a suíte é que decidiu.** Ele tem 0 usos como classe, então entrou na
primeira leva — e `core/tests/test_action_system.py:23` reprovou, porque afirma `.btn,` dentro de
`action-system.css`: o sistema de ação se declara, explicitamente, cobertura dos botões **legados**.
Tirar o nome exigiria mudar esse teste, e mexer num teste para o próprio PR passar é decisão, não
limpeza. Fica para o dono: a rede diz que a cobertura é intencional, o grep diz que não há mais
consumidor.

**Resultado:** 9 blocos apagados, 8 seletores podados, 148 linhas a menos, 9 arquivos.

**O defeito que a medição pegou, e ele teria ido para produção.** A primeira versão dividia o grupo
de seletores com `split(",")`. Isso destrói `:is()`:

```css
:is(html[data-theme="dark"]) :is(.card, .app-card, .module-card, .document-card, .summary-card)
```

Descartar `.summary-card` devolvia `:is(.card, .app-card, .module-card, .document-card` — **com o
parêntese aberto**. Seletor malformado invalida a regra inteira, e o navegador não reclama.

**Medido: 8.196 elementos alterados**, com `.list-header` perdendo `display: flex`, cor, fonte e
altura de uma vez, e a página de eventos indo de 1.100 px para 1.810 px de altura. Chaves e
parênteses do arquivo continuavam balanceados — só o seletor não estava. Nenhum teste pegaria isso;
nenhum gate de CSS pegaria isso. Pegou a comparação de estilo computado.

A divisão agora respeita profundidade de parênteses, e duas travas novas cuidam de **especificidade**:

- **`:not()` fica intocado.** Tirar argumento de lá alarga o que a regra pega e muda a
  especificidade emprestada — em silêncio.
- **`:is()`/`:where()` só são podados quando todos os argumentos são classe simples**, para a
  especificidade do grupo ser a mesma antes e depois. Lista que mistura `.a` e `#b` fica de fora.

E `parte_morta` passou a apagar o conteúdo de `:not()` antes de decidir: em `.a:not(.btn)` a classe
morta é **excluída**, não exigida — tratar a parte como morta apagaria uma regra viva.

**Verificação: 0 elementos alterados** em 41.950, nas 88 telas. `audit_css_morto` volta a 0 depois
de incluir o `cv-btn-group` — a catraca acusou o nome recém-exposto, que é exatamente o serviço dela.
### NOVO-62 ✅ RESOLVIDO · 🟠 `NOVO` A fonte do sistema era pedida e nunca entregue; e só valia num tema · UI · 0,5 d

Primeiro recorte de desenho do `NOVO-58`, com o dono decidindo: **empacotar a Inter**.

O tema escuro declarava `font-family: Inter, …` desde o redesenho
(`theme-dark-components.css:16`) e o claro usava `--font-sans: "Segoe UI", Arial`
(`tokens.css:170`) — **19.896 elementos com pilha diferente conforme o tema**. Pior: a `Inter`
**não estava no repositório**. Sem `@font-face` e sem arquivo, o navegador caía para o próximo item
da pilha, então a letra que o usuário via dependia do que estivesse instalado na máquina dele.

**Agora a fonte é entregue pelo sistema e vale nos dois temas.**

| | antes | depois |
|---|---|---|
| elementos com `font-family` divergente | 19.896 | **0** |
| elementos que divergem em qualquer propriedade não-cor | 20.203 (96%) | **5.850 (28%)** |
| diferenças não-cor no total | 45.726 | 24.608 |

**Por que a variável e não os cortes estáticos.** O CSS declara `font-weight` em **650, 720, 750,
760 e 850**, além dos redondos. Com cortes estáticos esses valores encostam no peso mais próximo —
720 viraria 700 — e o ajuste que alguém fez sumiria sem aviso. Medido no navegador com o arquivo
variável, o mesmo texto em 700/720/750/760 sai com largura **diferente** em cada um: o eixo é
contínuo, não está encostando.

**Por que quatro arquivos.** `unicode-range` faz o navegador baixar só o subconjunto que a página
usa. Os quatro somam 277 KB no repositório, mas **cada tela baixa 48 KB** — conferido escutando as
respostas do navegador: `/login/` e `/oficios/` baixam **um** arquivo,
`inter-latin-wght-normal.woff2`. `latin-ext` só desce se aparecer caractere fora do latim básico, e
o itálico só onde há itálico.

**A verificação que importava era "a fonte carrega mesmo?".** Declaração não prova rendição —
`document.fonts.check()` devolve `true` até quando cai no fallback, e foi por isso que a medição
anterior não conseguiu responder. O teste honesto é largura: o mesmo texto medido com a pilha do
`body` e com `"Inter Variable"` dá **670 px** nos dois, contra **644,61 px** do fallback genérico.
A fonte está ativa, nos dois temas.

**Cobertura.** `fonts.css` entra por `@import` em `style.css` (que serve o app inteiro pelo bundle)
**e** por `<link>` em `templates/core/login.html`, que não carrega o bundle e teria ficado de fora.

Origem: `@fontsource-variable/inter` 5.3.0, SIL Open Font License 1.1. A licença acompanha os
arquivos em `static/vendor/fonts/inter/LICENSE`, como a OFL exige. O CSP já permitia
(`font-src 'self' data:`, `core/middleware.py:128`), e o `collectstatic` de produção coleta os
quatro arquivos com hash.

**O que muda de aparência:** o tema claro inteiro. É a primeira mudança visual deliberada do
programa — todas as anteriores foram medidas exigindo zero diferença.

### NOVO-63 ✅ RESOLVIDO · 🟠 `NOVO` A barra lateral tem geometria diferente por tema — 91% da divergência sai daqui · UI · 1 d

Segundo recorte de desenho do `NOVO-58`, e o que o dono chamou de "geometria global". **A medição
desmentiu o nome, e isso mudou o plano:** dos 533 elementos com `font-size` divergente, **528 são a
barra lateral**; dos 378 com `height` divergente, **todos**. Não existe uma camada global de
geometria neste CSS — o que parecia global era a barra, que aparece nas 44 telas e por isso inflava
a contagem. As duas opções que eu havia oferecido ao dono ("geometria global" e "barra lateral")
eram a mesma opção.

| | antes | depois |
|---|---|---|
| elementos `.sidebar*` divergentes entre temas (não-cor) | 1.096 | **96** |
| elementos divergentes no total (8 rotas × 3 larguras) | 3.393 | 2.253 |

**Medido em três larguras — 1440, 800 e 500 px — e não só no desktop.** Seis das 23 regras de barra
lateral do tema escuro vivem dentro de `@media (max-width: 840px|600px)`. Globalizar uma delas sem
levar a media junto aplicaria geometria de celular em tela cheia, e isso **não apareceria** numa
medição feita só a 1440px: apareceria no celular de alguém.

**O método foi editar o valor no arquivo do componente, não mover a regra.** Mover muda posição na
cascata e especificidade de uma vez; alterar o valor onde ele já mora mantém as duas e deixa a
medição atribuível.

**O defeito que a globalização revelou, e ele já existia.** `.sidebar-module-expand` (o botão que
abre um módulo) declara `font: inherit` — reset habitual de `<button>`. Só que ele **é** um
`.sidebar-link--module`, e `font: inherit` zera também o **tamanho**. Vindo depois, com a mesma
especificidade, ele vencia: o item virava 16px enquanto o item irmão (que não é botão) ficava em
14px, **na mesma lista**.

Isso nunca apareceu porque a regra do tema escuro, mais específica, devolvia o tamanho — **só no
escuro**. Tirada a muleta, o defeito ficou visível nos dois temas, e a medição o pegou na hora
(`font-size 14px → 16px` em 192 elementos do escuro, onde o esperado era zero). Corrigido trocando
`font: inherit` por `font-family`/`font-weight: inherit`, que preservam o reset sem apagar o
tamanho.

**A largura da barra era token, e o token divergia:** `15%` no `tokens.css` contra
`clamp(238px, 17.5vw, 276px)` no tema escuro — 216px contra 252px na mesma janela, e tudo que mora
dentro herdava a diferença. O `clamp` venceu por ser melhor: prende um mínimo legível e um máximo,
em vez de encolher junto com a janela. A `@media (max-width: 1080px)` que apertava a barra para
224px também **só existia no escuro** — foi globalizada em vez de apagada, senão o claro perderia o
aperto justamente onde o espaço é mais escasso.

**O que ficou de fora, de propósito:** em `@media (max-width: 840px)` o tema escuro põe a barra em
`position: fixed` com `height: 100dvh`, e o claro usa `position: relative`. Isso não é geometria, é
**comportamento** — vira gaveta sobreposta em vez de coluna no fluxo, e depende do gatilho e do
fechamento (`.app-mobile-bar__toggle`, `.sidebar-drawer-close`) se comportarem igual nos dois temas.
Fica para um passo próprio, com o navegador abrindo e fechando a gaveta.

**Um teste caiu, e o conserto foi tirar a premissa dele, não afrouxá-lo.**
`test_semantic_dark_contract_covers_core_component_needs` exigia `--sidebar-width:` dentro de
`03-theme-dark.css`. Todo o resto da lista é `--color-*` — são as cores que um tema precisa
declarar. Largura de barra nunca foi cor: estava ali porque o tema escuro a redefinia, e a lista só
registrava esse fato. Com a largura decidida uma vez em `tokens.css`, exigi-la de volta no arquivo
de tema seria exigir que a divergência voltasse.

**Erro de processo meu, registrado porque quase passou.** Encadeei o commit ao `tail` do resultado
da suíte em vez de conferir o resultado antes — o `tail` devolveu sucesso, o commit rodou, e a
falha só apareceu quando fui ler a saída. O commit foi corrigido antes de virar PR, mas a lição é
que "rodei a suíte" e "li o resultado da suíte" são coisas diferentes.

**Sobre o escuro ter mudado em 500 e 800 px:** as regras não-media do tema escuro venciam as regras
de `@media` do claro por especificidade, então o escuro ignorava o próprio ajuste de celular.
Removida a sobrescrita, os dois temas passam a obedecer a mesma media. O valor que prevalece é o
deliberado para telas pequenas.

### NOVO-64 ✅ RESOLVIDO · `NOVO` Os 176 tokens `--cv-*` perdem o prefixo de origem e passam a ser nomeados pela função · MED · 0,5 d

O dono foi explícito: *"não quero mais nada com `cv`, quero que as nomenclaturas sejam focadas na
função do componente e não de onde ele é"*. `--cv-field-radius` não diz o que é o token; diz de que
biblioteca ele veio.

**172 dos 176 renomeados**, em 24 arquivos, 1.366 linhas. `--cv-x` vira `--x`, o que já deixa o nome
sendo a função (`--field-radius`, `--btn-height`, `--dialog-bg`).

**Quatro ficam para depois, e a razão é colisão real**, medida contra o estado anterior — não contra
o posterior, que já contém o resultado da própria troca:

| token | colide com |
|---|---|
| `--cv-field-bg` | `--field-bg` |
| `--cv-field-border` | `--field-border` |
| `--cv-field-border-focus` | `--field-border-focus` |
| `--cv-field-focus-ring` | `--field-focus-ring` |

São dois campos convivendo com nomes paralelos — o mesmo padrão das três classes vivas do
`NOVO-60`. Fundir exige decidir qual valor sobrevive, e isso é do dono.

A substituição é feita **do nome mais longo para o mais curto**, senão `--cv-field-bg` comeria o
prefixo de `--cv-field-bg-hover` e produziria `--field-bg-hover` a partir do lugar errado.

**Medição: 1 elemento alterado em 41.950 — e o piso de ruído também é 1.** Capturando duas vezes com
o **mesmo código**, `.os-model-card` em `/ordens-servico/nova/` no tema escuro difere sozinho: o
fundo dele varia entre execuções (estado de seleção que não é determinístico naquela tela). Rodei o
controle justamente porque "1 elemento mudou" numa renomeação pura não podia ficar sem explicação —
e a explicação é que aquele elemento mudaria de qualquer jeito.

Fica registrado como **ruído conhecido daquela rota**, para a próxima medição não gastar tempo com
ele.

### NOVO-65 ✅ RESOLVIDO · `NOVO` As 545 classes `cv-*` mecânicas perdem o prefixo de origem · MED · 1 d

Continuação do `NOVO-64` (tokens) para as **classes**, fechando o pedido do dono. Também renomeia os
**sete arquivos** que carregavam o prefixo no nome (`cv-buttons.css`, `cv-search-picker.css`,
`cv-select.css`, `components/cv-date-picker.css`, `components/cv-metric.css`,
`components/cv-notice.css`, `js/components/cv-date-picker.js`).

| | |
|---|---|
| classes renomeadas | **545 de 632** |
| ocorrências trocadas | 4.541 + 29 de prefixo + 42 em Python |
| arquivos tocados | 212 |
| elementos alterados | **1** de 41.950 — o ruído conhecido do `NOVO-64` |

**Dez famílias ficam preservadas**, porque o nome sem prefixo já pertence a outra classe **viva**:
`cv-alert`, `cv-btn`, `cv-dialog`, `cv-field`, `cv-field-row`, `cv-form-section-header`, `cv-input`,
`cv-loading`, `cv-module-card`, `cv-page`. A exclusão é por **família inteira**, não por nome: manter
`cv-btn` e renomear `cv-btn--primary` produziria `class="cv-btn btn--primary"`, que é pior que
qualquer um dos dois.

## Quatro defeitos meus, todos pegos pela medição, nenhum por teste

Nenhum destes quebraria a suíte. Todos quebrariam a tela.

**1. O `@import` reescrito.** A regex trocou `@import url("./cv-search-picker.css")` por
`./search-picker.css`, apontando para arquivo inexistente — a família inteira do *picker* ficou sem
estilo. É a mesma classe de defeito que reprovou o CI no `#266`, e foi o gate que eu escrevi lá
(`audit_css_morto` checando `@import`) que acusou. Consertado renomeando os arquivos de verdade.

**2. O token de template.** Em `class="cv-form-section-header{% if ... %}"`, o token capturado pela
descoberta é `cv-form-section-header{%` — que não bate com nenhuma família, escapa da exclusão e é
renomeado, enquanto o CSS (que via o nome limpo) preserva. O cabeçalho de formulário ficou sem
`display`, `padding` e `position`. Corrigido filtrando a descoberta a **identificadores CSS
válidos**.

**3. O prefixo montado em tempo de execução.** `class="icon-btn cv-icon-btn--{{ action }}"` monta a
classe no template. A primeira passada exigia fim de token, e `cv-icon-btn` seguido de `-` não
casava — então o prefixo ficou para trás enquanto o CSS virou `.icon-btn--settings`. Corrigido com
uma segunda passada que reconhece `--`/`__` como continuação.

**4. Classe escrita em Python.** `roteiros/presenters.py:230` monta
`value_class="cv-record-card__info-value--rota"`. Eu tinha varrido só `core/` e `scripts/`; classe de
CSS também mora em presenter. Varredura estendida a todo `*.py`, **protegendo `data-cv-*`** — que é
atributo, não classe, e não muda.

A medição foi de 1.061 → 945 → 894 → 20 → **1** conforme cada um caiu. O número que fechou é o
mesmo piso de ruído do `NOVO-64`: `.os-model-card` em `/ordens-servico/nova/`.

## Dois testes atualizados, e um deles é instrutivo

- `oficios/tests/test_menus_sob_demanda.py:33` tinha `re.compile(r'...\bcv-action-menu\b...')`. O
  `\b` põe um `b` imediatamente antes do nome, então a guarda `(?<![\w-])` da minha regex recusou a
  troca — o teste continuou procurando o nome antigo e não achou menu nenhum. **A guarda funcionou
  como projetada; o custo é que nome dentro de regex escapa da renomeação automática.**
- `docs/DATA_ATTRIBUTES_JS.md` citava `components/cv-date-picker.js`, e o `HT-13` exige que a doc só
  descreva o que existe. Os `data-cv-date-picker-*` **continuam**: atributo não é classe.

### NOVO-66 ✅ RESOLVIDO · `NOVO` Os 60 arquivos de CSS passam a ser agrupados por função · MED · 0,5 d

O dono pediu pastas "agrupadas por função". O critério anterior era só profundidade: **40 arquivos
soltos na raiz** e 21 em `components/`, sem dizer nada sobre o que cada um faz — `buttons.css` e
`oficios.css` moravam lado a lado, e um é componente do sistema enquanto o outro é a tela de um
domínio.

| pasta | arquivos | o que é |
|---|---|---|
| `base/` | 7 | token, tema, reset, utilitário |
| `layout/` | 5 | a moldura da página |
| `fields/` | 8 | entrada de dados |
| `actions/` | 2 | botão e menu de ação |
| `lists/` | 7 | listagem, card, cabeçalho de filtro |
| `feedback/` | 6 | aviso, diálogo, métrica, carregamento |
| `pages/` | 23 | tela de domínio, não componente |

**Três ficam na raiz:** `style.css` (ponto de entrada dos `@import`), `shell.bundle.css` (gerado) e
`components/theme-dark-components.css` — este último porque não pertence a família nenhuma: é o
resíduo do redesenho que o `NOVO-58` está desmontando.

**A ordem da cascata não muda.** `SHELL_CSS` e os `@import` de `style.css` mantêm a mesma sequência;
só o caminho de cada entrada muda. Mover arquivo e reordenar cascata no mesmo PR tornaria qualquer
diferença medida impossível de atribuir.

**Medição: 0 elementos alterados em 41.950.** É o resultado exigido de um move.

**A armadilha do caminho relativo.** `fonts.css` e `prestacoes-assinatura.css` referenciam
`url("../vendor/fonts/…")`. Descer um nível quebra isso **em silêncio** — o navegador não reclama, a
fonte simplesmente não carrega. Os dois ganharam um `../` a mais, e conferi no navegador que a
`Inter` continua sendo baixada e usada (medição de largura, não `fonts.check()`).

**Caminho montado por segmento escapa de substituição textual.** Os testes constroem
`css_root / "components" / "action-system.css"`, com cada pedaço numa string. Trocar `css/components/…`
por `css/actions/…` no texto não alcança isso: **43 testes quebraram** com `FileNotFoundError`.
Corrigido com uma varredura que entende a forma `X / "pasta" / "arquivo.css"`.

### NOVO-67 🟡 `NOVO` O auditor de padrões de front nunca varreu `static/css/components/` · CI · 0,5 d

Descoberto pelo `NOVO-66`. `scripts/audit_frontend_standards.py:444` usava `CSS_DIR.glob("*.css")` —
**varredura rasa**. Enquanto os componentes moravam um nível abaixo, eles simplesmente não entravam
na conta: o auditor via 40 arquivos de 61.

O move tornou isso visível de duas formas, nesta ordem:

1. Com `glob` raso e os arquivos já em subpastas, os avisos caíram de **240 para 18** — o auditor
   passou a enxergar 2 arquivos. **Catraca que desce por cegueira é pior que catraca nenhuma**, e
   esse número teria passado no CI como se fosse melhora.
2. Trocando para `rglob`, o número sobe para **354**: são **114 avisos de dívida preexistente** que
   nunca foram contados.

Neste PR a varredura passou a ser `rglob` (a correção de fato) e os 20 arquivos que vieram de
`components/` entram numa lista `COBERTURA_ADIADA` explícita, com o motivo escrito no código. Assim
o corpo medido continua idêntico ao de antes — 240 avisos —, e um PR que só move arquivo não carrega
114 avisos alheios.

**Abrir a cobertura é trabalho próprio**, com o número já medido: `240 → 354`. Os avisos se
concentram em `actions/` (152) e `pages/` (128).

### NOVO-68 🟠 PARCIAL · `NOVO` 155 regras de geometria deixam de depender do tema · UI · 1 d

Terceiro recorte do `NOVO-58`, e o primeiro **mecânico** — os anteriores (barra lateral) foram
regra a regra.

**A transformação, e por que ela é segura:**

```css
:is(html[data-theme="dark"]) .x { padding: 8px; }
              ↓
:is(html[data-theme])        .x { padding: 8px; }
```

`[data-theme]` e `[data-theme="dark"]` têm **a mesma especificidade** — os dois são um seletor de
atributo (0,1,0) — e a regra fica **no mesmo lugar** do arquivo, dentro do mesmo `@media` se houver.
Nada muda de peso nem de posição na cascata: o escuro recebe exatamente o que já recebia, e o claro
passa a receber a geometria.

Isso só vale porque `data-theme` está **sempre presente**. Conferido no navegador nos três casos de
`prefers-color-scheme` (claro, escuro e sem preferência): `theme-init.js` escreve o atributo em
todos. Se faltasse, a regra não casaria e o elemento cairia na base clara — que é o comportamento de
hoje, então nem assim haveria regressão.

| | |
|---|---|
| regras desescopadas | **155** |
| elementos melhorados no claro | **3.432** |
| elementos alterados no escuro | **1** — o ruído conhecido |
| divergência não-cor entre temas | 13.936 → **11.667** |

**Por que só 155 e não 368.** A versão completa também **partia** os blocos mistos, separando
geometria de cor em dois blocos irmãos — e chegava a derrubar a divergência de 13.936 para **1.826**,
87%. Mas ela mexia em **88 elementos do tema escuro**, que deveria ficar intacto.

Excluir os blocos que declaram *custom property* (o valor de um token pode alimentar outro bloco por
herança, e partir muda de qual escopo ele é lido) levou de 88 para **9**. Os 9 restantes — todos
`record-row`, trocando o fundo — **eu não consegui explicar**: as regras de `record-row` saíram
byte-idêntica do transformador, só com o número de linha deslocado.

Mudança sem explicação no tema que deveria ficar intacto é exatamente o que a medição existe para
barrar. Então a partição fica **fora desta leva**, com o ganho já medido (11.667 → 1.826) para quando
for investigada com calma.

**O que resta no arquivo:** 590 seletores ainda escopados ao escuro contra 175 já globais.

---
---

## Levantamento de 09/08/2026 — a reconstrução do front

Oito defeitos achados ao medir o sistema para escrever o
[`PLANO_RECONSTRUCAO_FRONT_2026-08.md`](PLANO_RECONSTRUCAO_FRONT_2026-08.md), que é a Fase 7 do
plano mestre. Nenhum deles aparece nas medições de 05/08 — quatro são resíduo de PRs recentes, dois
são instrumentos que não funcionam, e um é ambiente.

> **Estes IDs nasceram como `NOVO-66`…`NOVO-73` e foram renumerados para `NOVO-69`…`NOVO-76`.** Os
> PRs #283 e #284 entraram na `main` enquanto este levantamento era escrito, e reservaram
> `NOVO-66`, `NOVO-67` e `NOVO-68` para outros defeitos. Como estes aqui ainda não tinham sido
> citados por nenhum PR mesclado, renumerá-los foi mais barato que criar a quinta colisão do
> catálogo — que é o inverso da decisão tomada para as quatro colisões antigas, e pelo mesmo
> critério: **o que manda é se o número já está em uso em PR mesclado.**
>
> **A colisão não foi acidente de sorte, foi de método.** Dois trabalhos de front correram em
> paralelo na mesma semana, cada um lendo o "maior `NOVO` do catálogo" no seu próprio ponto de
> partida. Enquanto a numeração for descoberta por leitura do arquivo, duas sessões simultâneas vão
> reservar o mesmo número sempre que se cruzarem — e este catálogo já tem cinco provas disso.
>
> **O que o PR #283 mudou embaixo deste levantamento:** os 60 arquivos de CSS saíram da raiz para
> oito pastas por função (`base/`, `layout/`, `fields/`, `actions/`, `lists/`, `feedback/`,
> `components/`, `pages/`). Todos os caminhos citados abaixo e no plano de reconstrução já são os
> novos. Os defeitos foram reconferidos depois do merge: **os oito continuam de pé**.

### NOVO-69 ✅ RESOLVIDO (8133d8af, 09/08/2026) · `NOVO` `cv-select.js` está morto desde o PR #247 e continua no bundle de toda página · MOR · 0,25 d

`static/js/cv-select.js` tem **343 linhas** e responde a `[data-cv-dropdown]` e
`[data-cv-filter-dropdown]`. **Nada no sistema emite esses atributos.** A varredura em `templates/`,
`static/js/` e nos treze apps devolve só três tipos de sobrevivente, nenhum deles um uso:

- comentário e seletor em `static/css/fields/select.css:99,147-148`;
- a tabela de contrato em `docs/DATA_ATTRIBUTES_JS.md:118-124`;
- relatórios em `docs/historico/`.

O `JS-08` já o listava como "343 linhas, 1 template — e só sob `DEBUG`, via `ui_lab2/selects.html`".
O PR #247 apagou os dois UI Labs, e aquele único uso virou **zero**. O arquivo continua em
`SHELL_JS` (`scripts/build_shell_bundles.py:74`), então é baixado e analisado em toda navegação.

**A armadilha, para quem for apagar:** `custom-select` **não** é dele. Esse markup é atendido por
`components/picker-select.js`, via `data-entity-picker` — são 7 templates de produção. Apagar a
família de CSS junto com o JS quebraria os seletores customizados do sistema inteiro.

**Resolvido na E2.** `cv-select.js`, o no-op `CV.fields.initDropdowns`, sua documentação e a
família CSS `action-dropdown`/`filter-dropdown` sem emissor foram removidos; `custom-select` e
`data-entity-picker` permaneceram intactos. `SHELL_JS` passou de 26 para 25 fontes e o bundle JS
versionado caiu de **289.831 para 274.420 bytes** (−15.411 bytes, −5,32%).

### NOVO-70 ✅ RESOLVIDO (7a1e2e03, af97ac56) · `NOVO` A métrica de aceite do `PF-02` não tem instrumento no repositório · QA · 1,5 d

O `PF-02` fixa o aceite da frente de front inteira em **uso de CSS acima de 35% por rota**, contra
os 10,1%–11,8% medidos. **Nenhum script do repositório mede isso.** `scripts/medir_desempenho.py`
mede consultas, KB de HTML e tempo; a medição original de CSS foi feita à mão, com Chromium via
CDP, e não ficou. O mesmo vale para a divergência entre temas do `NOVO-58`: o número existe, o
comando que o produz não.

**Efeito:** a etapa mais cara do ciclo não tem como declarar que terminou, e nenhuma das etapas
intermediárias tem como provar que não regrediu. É exatamente o buraco que a Fase 1 fechou para
desempenho e que segue aberto para CSS.

**E o corpus de rotas está podre.** `screenshots/auditoria-telas/_capturar.py` lista 57 telas, das
quais **14 são rotas de UI Lab que o PR #247 apagou** (`/dev/ui-lab/*` não resolve mais, e
`ui_lab2` não está em `INSTALLED_APPS`). Sobram **43** reais. O corpus precisa sair de
`screenshots/` — 39 MB que o `BE-24` quer tirar do repositório — e virar módulo em `scripts/`.

**Resolvido na E0.** `scripts/rotas_do_sistema.py` fixa as 43 rotas; os dois medidores usam
Playwright/CDP com autenticação efêmera e gravam catracas por rota em `scripts/tetos_front.json`.
A linha de base reproduzida em 09/08/2026 foi **11,3369%–70,5559%** de uso de CSS (o máximo é o
login; nas rotas autenticadas, 11,3369%–19,2908%) e **248.651 diferenças não-cor** em 61.700
elementos, 129 combinações de rota/largura. A captura inversa deu zero diferenças exclusivas.

### NOVO-71 ✅ RESOLVIDO (E3–E5, 10/08/2026) · `NOVO` Componente global não tinha contrato de parâmetro · HT · 6+ d

**275 dos 946 `{% include %}`** do sistema não usam `only`. O componente lê o contexto que o
chamador tem por acaso, e quebra quando outro chamador não tem — que é o `HT-14` pelo lado do
sintoma. O lado da causa é que **não existe declaração**: nenhum componente diz quais parâmetros
aceita, então nem o autor nem o chamador nem o CI sabem qual é o contrato.

O dono decidiu fechar isso por **`django-cotton`** (2.7.2 no índice; Django 5.2.16 no projeto), que
passa só o atributo declarado — o `only` deixa de ser disciplina e vira o comportamento do motor.

**O custo escondido é a configuração, não a migração.** O cotton exige `loaders` explícitos em
`TEMPLATES`, e isso é incompatível com o `APP_DIRS: True` de `config/settings/base.py:161-176`.
Trocar o carregador muda a resolução de **407 templates** de uma vez, e o modo de falhar é
`TemplateDoesNotExist` em rota que ninguém abriu no PR.

**Resolvido.** A E3 instalou e configurou o motor, a E4 converteu os 82 componentes e a E5 migrou
os 868 call sites, habilitou isolamento de contexto e apagou todas as cascas de compatibilidade.

**E3 concluída em 09/08/2026 (`e6a722ae`).** `django-cotton==2.7.2` entrou no lock com hashes e
o projeto passou a usar configuração manual: `SimpleAppConfig`, loader em cache com Cotton antes
de `filesystem.Loader` e `app_directories.Loader`, e a biblioteca de tags em `builtins`. Os cinco
context processors declarados foram preservados e nenhum template mudou. Os **408 templates** do
corpus compilam; 12 telas de domínio e o perfil que hospeda a integração Google renderizam no
servidor sem `TemplateDoesNotExist` e sem erro de console.

**E4 concluída em 10/08/2026.** Os 82 componentes foram convertidos para implementações canônicas
em `templates/cotton/**`, mantendo 82 cascas compatíveis nos caminhos antigos. Os contratos cobrem
todo o inventário, e a régua visual da E0 ficou estável nas 129 combinações de rota e largura. As
catracas fecharam em 0 erros/240 avisos no auditor frontend, 2.535 suspeitas no auditor de padrões e
78 no auditor de arquitetura. A E5 migrou os call sites, explicitou contratos inclusive em slots
e templates dinâmicos, habilitou o isolamento e removeu as cascas; o defeito está fechado.

### NOVO-72 ✅ RESOLVIDO (E2, 09/08/2026) · `NOVO` `ui_lab2/` sobreviveu à remoção do PR #247 · MOR · 0,1 d

O `BE-25` decidiu que nenhum dos dois UI Labs é o vigente e o PR #247 os apagou. `ui_lab2/` ficou
para trás como diretório contendo só `__pycache__/*.pyc`. Não está em `INSTALLED_APPS`, não tem
rota, não tem fonte — é o rastro de um app que não existe mais.

**Resolvido na E2.** O diretório só existia no checkout antigo por conter `__pycache__` ignorado.
Uma worktree limpa de `origin/main` já não o materializa: `git ls-files ui_lab2` e `Test-Path
ui_lab2` retornam, respectivamente, zero arquivos e falso. Não havia fonte versionada a apagar.

### NOVO-73 ✅ RESOLVIDO (8133d8af, 09/08/2026) · `NOVO` Nome e lugar de arquivo JS sem padrão · MOR · 0,5 d

Duas divergências, nenhuma delas cosmética a longo prazo, porque é assim que o próximo
desenvolvedor aprende o padrão errado:

- **Caixa:** `static/js/roteiros_wizard.js` e `static/js/pages/gdrive_config.js` em snake_case,
  contra kebab-case nos outros 62 arquivos.
- **Lugar:** `roteiros.js` (813 linhas em `roteiros-map.js`, mais `roteiros.js` e
  `roteiros_wizard.js`) mora na **raiz** de `static/js/`, ao lado da infra compartilhada
  (`autosave.js`, `theme-toggle.js`), enquanto todo o resto do código de domínio está em
  `static/js/pages/`.

Mover exige atualizar `SHELL_JS` em `scripts/build_shell_bundles.py`, os `{% block extra_js %}` que
os citam e `docs/DATA_ATTRIBUTES_JS.md`.

**Resolvido na E2.** Os quatro módulos agora moram em `static/js/pages/` e usam kebab-case:
`roteiros.js`, `roteiros-map.js`, `roteiros-wizard.js` e `gdrive-config.js`. Templates, testes,
exceções do auditor e documentação foram atualizados no mesmo commit, sem alias de compatibilidade.

### NOVO-74 ✅ RESOLVIDO (E5, 10/08/2026) · `NOVO` Dois namespaces de componente concorrentes, com quatro pastas fantasma · HT

`templates/components/` tem **duas gerações vivas ao mesmo tempo**:

| o que está lá | o que deveria estar |
|---|---|
| `components/buttons/`, `components/forms/`, `components/modals/`, `components/steppers/` — **só `.gitkeep`** | os componentes reais moram em `components/ui/buttons/`, `.../forms/`, `.../modals/` |
| `components/form/` (singular, **1 arquivo, 37 usos**) | convive com `components/forms/` (plural, **vazia**) |
| `components/cards/module_card.html` | ao lado de `components/ui/lists/entity_card.html` |
| `components/feedback/alerts.html` | ao lado de `components/ui/feedback/alert.html` |

Quatro diretórios existem só para segurar um `.gitkeep`, prometendo uma organização que o código
não seguiu. Quem for criar um botão novo tem dois lugares plausíveis e nenhum critério.

**Fila:** etapa E5, junto da migração dos call sites — mover para `templates/cotton/` resolve os
dois namespaces de uma vez, em vez de renomear duas vezes.

**Resolvido na E5.** `templates/cotton/**` é o único namespace: as 82 cascas e os cinco arquivos
`.gitkeep` de `templates/components/**` foram removidos, sem alias de compatibilidade.

### NOVO-75 ✅ RESOLVIDO (e6e9c3d2) · `NOVO` O comando de suíte do `AGENTS.md` não funciona no ambiente que o projeto monta para os agentes · COR · 0,1 d

`requirements/dev.txt` puxa `base.txt` e `lint.txt`, e **não puxa `test.txt`**. O hook
`.claude/hooks/session-start.sh:20` instala só o `dev.txt`. Resultado: `tblib` e `coverage` nunca
entram no ambiente de nenhuma sessão remota.

Sem `tblib`, o comando que o `AGENTS.md` §7 e o `PLANO_MESTRE` §5 mandam rodar —
`manage.py test --settings=config.settings.test --parallel 4` — **aborta com
`TypeError: cannot pickle 'traceback' object` sem dizer qual teste falhou**. E dois testes falham:
`core/tests/test_suite_paralela.py`, que existem justamente para guardar esse contrato e que
descrevem o sintoma com precisão na própria mensagem de falha.

**Medido hoje.** Com `pip install -r requirements/test.txt`, a suíte vai de 2 falhas para
**1.824 testes verdes, 7 skips, 14,7 s** com `--parallel 4`.

**Por que é 🔴 apesar de ser uma linha.** Todo gate de todo PR deste ciclo depende de a suíte
rodar. O defeito não quebra produção — quebra a capacidade de provar qualquer coisa, e o faz de
um jeito que parece falha do trabalho do agente, não do ambiente.

**Resolvido na E0.** `requirements/dev.txt` passou a incluir `test.txt`; ambientes de agente agora
recebem `tblib`, `coverage` e Playwright pelo contrato de dependências do projeto.

### NOVO-76 ✅ RESOLVIDO (a70fe64b) · `NOVO` O `audit_ui_patterns.py` está no ciclo obrigatório e nunca pode passar · COR · 0,5 d

O `AGENTS.md` §4 manda rodar três auditores no passo 5 de toda tarefa, e um deles é
`scripts/audit_ui_patterns.py`. **Ele sai 1 sempre** — hoje, na `main`, com 5.173 ocorrências
informativas, das quais a esmagadora maioria é a regra `hex_or_rgba` disparando dentro dos próprios
arquivos de token (`base/03-theme-dark.css:22-28` etc.), onde a cor literal é a definição e não um
desvio.

Ele também **não está no `tests.yml`** — os seis auditores do CI são `audit_frontend_standards`,
`audit_css_morto`, `audit_paleta`, `audit_foco_visivel`, `audit_django_architecture` e
`audit_area_scoped_managers`. Então é um script que o contrato manda rodar, que sempre reprova, e
que nada verifica.

**O custo não é o exit code, é o que ele ensina.** Um verificador que nunca passa treina quem o
roda a ignorar a saída — e no dia em que ele apontar algo real, ninguém vai olhar. As regras
`IGNORED_PARTS` (`scripts/audit_ui_patterns.py:10`) já reconhecem esse problema para
`templates/components/ui`; falta o mesmo para os arquivos de token, e falta decidir se ele é
catraca (com teto, no CI) ou relatório (e aí sai do §4 do `AGENTS.md`).

**Cuidado ao consertar:** a etapa E4 do plano de reconstrução move componentes para
`templates/cotton/`, e `IGNORED_PARTS` precisa acompanhar no mesmo PR — senão o número se move por
mudança de escopo, não de qualidade.

**Resolvido na E0.** Sem argumentos, o auditor virou relatório e sai zero; no CI, `--max 2622`
torna os 2.622 achados reais uma catraca que só desce. O bundle gerado e as definições de tokens
deixaram de ser contados como dívida duplicada.

### NOVO-77 ✅ RESOLVIDO (7a1e2e03) · `NOVO` O corpus antigo tinha rotas mortas além do UI Lab · QA · 0,25 d

Subtrair apenas as 14 rotas de UI Lab preservava `/oficios/<pk>/assinaturas/` e
`/roteiros/<pk>/`, que já não têm tela própria. O corpus continuaria com 43 entradas, mas duas
delas não mediriam uma interface viva. A E0 substituiu essas entradas pelas listas de Eventos e
Prestações de Contas, que estavam vivas e ausentes, e adicionou testes de resolução, unicidade e
contagem das 43 rotas.

### NOVO-78 ✅ RESOLVIDO (f5f0b9cf) · `NOVO` O gerador demo não acompanhou os modelos por área · COR · 0,5 d

`resetar_banco_demo` abortava em `Roteiro.area_id NOT NULL` e, depois desse primeiro bloqueio,
deixava seis modelos novos com zero registros. Isso impedia criar a base efêmera exigida pelas
réguas da E0. O comando voltou a criar cinco registros de todos os modelos de domínio, respeitando
as áreas nas FKs e M2M, com teste de regressão para os modelos operacionais obrigatórios.

### NOVO-79 ✅ RESOLVIDO (95f9f26d) · `NOVO` Duas rotas do corpus resolviam, mas respondiam 500 · COR · 0,25 d

A navegação real da E0 encontrou dois defeitos que o teste de `resolve()` não alcançava:
`/termos/oficio/<pk>/preview/` tentava serializar instâncias ORM com `DjangoJSONEncoder`, e
`/justificativas/<pk>/editar/` encaminhava `pk` para uma view que não o aceitava. As duas rotas
agora respondem, e cada falha ganhou teste de regressão.

### NOVO-80 ✅ RESOLVIDO (3996f903) · `NOVO` A E5 apagou duas travas de regressão em vez de reapontá-las · QA · 0,25 d

`test_componentes_sem_orfao.py` guardava duas listas nomeadas — os 7 componentes que o `HT-06`
apagou e os 8 que caíram com o UI Lab (PR #247 e a cascata do `NOVO-44`) — afirmando por arquivo
que nenhum deles voltou, que é a prova de grep exigida pelo `AGENTS.md` §3.6.

A E5 extinguiu `templates/components/` e moveu tudo para `templates/cotton/`. Com o diretório
antigo vazio, `(COMPONENTES / rel).exists()` virou vacuamente verdadeira: as asserções passaram a
passar sem testar nada. O teste **tinha** mesmo que mudar; o que faltou foi trocar a raiz por
`COTTON`, e não remover as duas travas. A E4 preservou a forma da árvore ao mover, então as duas
listas seguem válidas letra por letra.

O buraco foi medido, não suposto. Ressuscitando `ui/forms/dropdown.html`:

    volta sem consumidor -> guarda de órfão pega, trava nomeada pega
    volta COM consumidor -> guarda de órfão passa, trava nomeada pega

A segunda linha é o defeito, e é como componente morto reaparece na prática: alguém copia de uma
branch antiga e já sai usando. O `test_todo_componente_tem_quem_o_renderize` não cobre esse caso —
por construção, ele só reclama de quem **não** tem consumidor.

A E6 (todos os cinco IDs, `70f369c6`..`5b58fac7`) passou por esse arquivo três vezes e não repôs
as travas: ajustou apenas a contagem do inventário, de 82 para 85.

### NOVO-81 ✅ RESOLVIDO (3996f903) · `NOVO` O auditor de front audita os testes de JS que a E1 criou · QA · 0,1 d

`audit_frontend_standards.py` varre `static/js/**.js` e pula só `*.bundle.js`. Com o runner de JS
da E1 (`JS-03`), os arquivos `*.test.js` passaram a morar ao lado do código que testam e entraram
na varredura.

O que um teste monta para exercitar uma regra é exatamente o que a regra proíbe em produção:
`innerHTML` de fixture dispara `innerhtml_dynamic_without_escape`, e afirmar sobre classe dispara
`css_class_as_logic`. Como o teto é global (246, com 240 em uso), escrever teste de JS consome a
folga e reprova o CI por escrever teste.

Hoje o defeito é latente: o único `*.test.js` do repositório (`state-toggle.test.js`, da E6) não
dispara nenhuma regra. A trava é para o próximo, e o custo dela é uma linha.

### NOVO-83 🔴 · `NOVO` As duas réguas da E0 não sobem o navegador na sessão remota · COR · 0,25 d

Irmão do `NOVO-72`, e o mesmo formato: **o comando que o projeto manda rodar não roda no ambiente
que o próprio projeto monta para os agentes.**

`medir_divergencia_tema.py:266` e `medir_css_por_rota.py:199` chamavam `playwright.chromium.launch()`
sem `executable_path`. Isso procura um build de Chromium casado com a versão do pacote pip — hoje
`playwright==1.62.0`, que espera o build **1234**.

No CI funciona, porque `tests.yml:391` roda `python -m playwright install --with-deps chromium` e
baixa o build certo. Na sessão remota, não: a imagem já traz o Chromium em
`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`, no build **1194**, e o ambiente pede explicitamente
para **não** rodar `playwright install`. O launch morre com

    Executable doesn't exist at .../chromium_headless_shell-1234/chrome-headless-shell

Por que isso importa mais do que parece: a **E8 inteira** depende dessas duas réguas. O plano diz,
com todas as letras, que a primeira coisa da E8 é remedir — "número velho é o quarto erro que mata
um ciclo" — e a catraca da etapa é a divergência não-cor caindo. Sem o navegador subir, a E8 fica
sem prova e sem catraca, e a alternativa seria mexer em 43 telas no olho.

Descobri tentando fazer exatamente isso: rodar a régua para reescrever a tabela do enunciado.

**Resolvido** por `scripts/navegador_medicao.py`: tenta o caminho normal primeiro e só cai para o
build instalado quando o esperado não existe, e só quando o erro é esse — outro erro sobe sem
disfarce. No CI o primeiro caminho sempre funciona, então lá nada muda.
`core/tests/test_navegador_medicao.py` prende as duas metades, mais uma trava de regressão que
reprova se alguma régua voltar ao `launch()` cru.

**Segundo tropeço, no mesmo caminho.** Com o navegador de pé, a régua ainda parava em
`oficios-detalhe: HTTP 404 em /oficios/1/`. O registro existe; o que faltava era o usuário de
medição ter **vínculo de área** — o sistema é escopado por `AreaTrabalho`, e sem
`VinculoUsuarioArea` as rotas de detalhe respondem 404. O `.github/workflows/tests.yml` faz esse
vínculo; o `AGENTS.md` §7 não menciona, e quem rodar a régua à mão sem ler o workflow cai nele.

### NOVO-84 🔴 · `NOVO` A régua de tema reprovava `roteiros-editar@500` — e tinha razão · COR · 0,5 d

Com o `NOVO-83` resolvido, a régua da E0 finalmente subiu o navegador e parou noutro ponto:

    RuntimeError: a ordem de captura alterou o resultado:
    168 exclusivos claro→escuro; 164 exclusivos escuro→claro

A mensagem não dizia **qual rota**. Deduzi contando linhas do log: `roteiros-editar@500` — e só a
500 px; a 1440 e a 800 a mesma rota passava.

**A trava estava certa, e não foi afrouxada.** Capturando as chaves exclusivas dentro da corrida, as
332 são **todas** de propriedade derivada de layout (`height`, `width`, `transform-origin`,
`perspective-origin`, `grid-template-*`) em 38 containers. Nenhuma é de estilo. E o valor do tema
claro é idêntico nas duas ordens; só o do escuro muda:

| ordem da captura | claro | escuro |
|---|---|---|
| claro→escuro | 4374.84px | **4367.39px** |
| escuro→claro | 4374.84px | **4423.39px** |

As duas leituras do escuro acontecem em sequência **sem troca de tema entre elas** — a captura 1
termina em escuro e a captura 2 começa reaplicando escuro. A página cresceu **56px sozinha**. O
número não era reprodutível porque a página não tinha parado de mudar: `networkidle` diz que a rede
calou, não que o layout assentou.

**Duas hipóteses caíram no caminho, e vale registrar para ninguém repetir:**

- *"O DOM muda entre as capturas e desloca os índices"* — as chaves são `(índice, propriedade, …)`,
  então parecia óbvio. Medido: **1142 elementos, constante**, inclusive através de quatro trocas de
  tema. Falsa.
- *"É corrida de temporização"* — duas corridas completas deram **168/164 idênticos**. Falsa.

**A primeira correção também errou o lugar.** Pus a espera de estabilidade **antes** da primeira
captura, com a página em tema claro. Não adiantou, e quem desmentiu foi a mensagem de erro que eu
tinha acabado de melhorar: `layout estável: True` com a falha intacta. O crescimento vem **depois**
da troca de tema, não antes dela — a espera passou para dentro do `apply()`, valendo em toda
aplicação de tema.

**PARCIAL — e eu cheguei a dar por resolvido, errado.** `settle()` deixou de ser dois
`requestAnimationFrame` e passou a acompanhar `scrollHeight`/`scrollWidth` até três leituras iguais.
Com isso a corrida de 500 px passou uma vez, com as 42 rotas. **Mas a corrida completa (três
larguras) voltou a reprovar na mesma rota**, agora com `164/168` — os mesmos números, invertidos.

Então a falha é **intermitente**, e a leitura anterior de "determinística" também estava errada: as
duas primeiras corridas darem `168/164` idênticos foi coincidência, não determinismo. A passagem do
run de 500 px foi sorte, e eu a tratei como prova. O erro de método aqui foi meu: **uma passagem não
prova ausência de falha intermitente.**

**O que está firme, medido:** aplicado o tema escuro e deixado assentar, a altura fica em **4423px,
estável por 12 segundos** (24 leituras de 0,5 s). O valor que aparece na captura que reprova é
**4367.39px** — 56px a menos. Ou seja, 4423 é o layout escuro de verdade, e 4367 é um estado
intermediário que a janela de estabilidade de 150 ms às vezes toma por assentado.

**O que cresce, medido.** Comparando altura de cada elemento entre os temas a 500 px:
`.form-section-body` **cresce 66,34px** no escuro, enquanto os textos ao redor **encolhem** —
`cv-form-section-header` −17,79px, `form-block__header` e `form-block__copy` −7,61px cada,
`form-section-subtitle` −5,8px. Saldo: **+48,55px**. São métricas de texto divergindo entre os
temas, que é exatamente o assunto da E8 — não é defeito da página, é o defeito que a etapa existe
para fechar.

**Por que a régua tropeça mesmo assim.** Indo de claro para escuro numa página ociosa, o escuro
nasce **já em 4423,39px** — o valor certo — e fica lá por 12 s. O `4367.39px` que aparece na captura
reprovada **não é um estado que assenta em 4423**: é outro layout, que só aparece dentro da captura.
A diferença é a carga: logo antes de aplicar o escuro, a captura faz ~388 mil leituras de
`getComputedStyle` (1.142 elementos × ~340 propriedades). Essa carga atrasa o relayout assíncrono e
o faz cair no meio do laço de diff. Daí a intermitência: é corrida entre o relayout e o laço, e não
falta de espera depois do carregamento.

**Fechado: não havia trabalho assíncrono.** A pergunta estava mal posta, e eu a persegui por três
hipóteses erradas — deslocamento de índice (falsa: 1.142 elementos constantes), carregamento de
fonte (falsa: 4 faces, todas `loaded`, `fonts.ready` não muda altura) e corrida de temporização
simples (falsa: não reproduz em 12 voltas replicando a captura exata).

A causa é **uma regra de CSS**, e ela é síncrona. Instrumentando a corrida para nomear os elementos
em vez de numerá-los, a coluna de largura entregou o caso: `.route-destinos-block__rail` e toda a
subárvore vão de **406px no claro para 378px no escuro**. Subindo a árvore, os 28px nascem em
`section.form-block--resource`:

| propriedade | claro | escuro |
|---|---|---|
| `padding` | **0px** | **14px** |
| `gap` | 16px | 12px |

Perguntando ao navegador quem declara (`CSS.getMatchedStylesForNode`, que é autoridade e não
palpite), a regra é `static/css/components/theme-dark-components.css:2332`:

```css
:is(html[data-theme="dark"]) .form-block {
  background: var(--color-surface-soft);
  border: 0;
  border-radius: 14px;
  grid-template-columns: minmax(0, 1fr);
  margin: 0;
  padding: 14px;
}
```

O `padding: 14px` só existe no escuro. Ele encolhe a caixa de conteúdo em 28px, os filhos vão de 434
para 406, o texto quebra diferente, as alturas crescem, e a página inteira ganha 48,55px —
propagando por **14 níveis** de árvore.

**Por que isso desestabiliza a régua.** A cadeia é longa e cada `getComputedStyle` do laço de diff
força layout. Em algumas corridas a captura lê a árvore com a cadeia ainda propagando, e aí registra
o estado intermediário (4367,39px) em vez do final (4423,39px). Não é falta de espera depois do
carregamento — é reflow profundo acontecendo durante a leitura, e por isso a espera que eu tinha
posto no `settle()` reduziu a frequência sem eliminar.

**O que fazer com isso é decisão da E8, não deste ID.** `.form-block` é classe de layout base, usada
em 23 templates. Igualar o padding entre os temas é sub-etapa da E8 com `PARE E PERGUNTE`, e não
cabe aqui.

**Nota para a E8:** esta regra sozinha concentra quatro das famílias abertas — `padding`
(espaçamento), `border: 0` (a **8b**, e na direção **oposta** à do enunciado, que fala em
0px→1px), `border-radius: 14px` (a **8c** — e o 14px está no **escuro**, não no claro, ao contrário
do que o enunciado diz) e `grid-template-columns`. Vale reabrir a tabela das famílias com isso em
mãos: elas podem não ser quatro frentes espalhadas, e sim poucas regras densas.

Fica também o diagnóstico melhor: quando a trava disparar, o erro passa a dizer qual rota é e se a
página chegou a assentar, que é o que separa "o instrumento falhou" de "a página não para de mudar".

**E fica um achado sobre o sistema, não sobre o instrumento:** trocar para o tema escuro dispara
relayout assíncrono no editor de roteiro a 500 px, com 56px de crescimento. Isso é **comportamento**,
não pintura, e mora perto da família 8h da E8 (a gaveta da barra lateral, que também é comportamento
e também só existe abaixo de 840 px). Vale investigar junto quando a 8h for executada.

### NOVO-85 🔴 · `NOVO` A armadilha de foco da gaveta vazava — e só no tema escuro · A11Y · 0,25 d

Apareceu na investigação da família **8h** da E8, e no lugar do defeito que se esperava: a premissa
catalogada ("a gaveta é `fixed` no escuro e `relative` no claro") **já estava morta** — o `NOVO-68`
globalizou a geometria em 09/08, e `sidebar.css:353` é código que não vence mais nada. No lugar dela
apareceu isto, que é comportamento de verdade.

`sidebar.js` montava a lista de focáveis com

    'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'

e `button:not([disabled])` **casa com botão `tabindex="-1"`** — que o navegador nunca alcança por
Tab. O descarte de `tabindex="-1"` só existia no ramo genérico `[tabindex]`.

Por que isso vira defeito **de um tema só**: o seletor de tema é o último bloco da barra e é um
radiogroup rotativo — `theme-toggle.js:19` deixa `tabindex="0"` apenas no tema ativo. No DOM,
"Escuro" vem antes de "Claro" (`templates/cotton/layout/sidebar.html:102,106`).

| tema | último do DOM | último **tabulável** | batem? |
|---|---|---|---|
| claro | "Claro" (`tabindex="0"`) | "Claro" | ✅ por acidente |
| escuro | "Claro" (`tabindex="-1"`) | "Escuro" | ❌ |

No escuro, `document.activeElement === last` dá falso quando o foco está no último tabulável real, o
`event.preventDefault()` não roda, e **o foco sai da gaveta para o conteúdo atrás do scrim** — com a
gaveta aberta e o `body` travado em `overflow: hidden`. O usuário perde o foco numa região que não
consegue ver nem rolar.

Vale também **antes de o `theme-toggle.js` rodar**: o template nasce com os dois botões em
`tabindex="-1"`, e o script desiste cedo (`if (!shared) return;`) se `CV.theme` faltar.

**Resolvido** trocando a filtragem por `element.tabIndex >= 0` mais o descarte explícito de
`disabled` — o critério do navegador, e não uma aproximação por seletor.

`static/js/components/sidebar.test.js` (novo, 5 casos) prende os dois temas, o estado inicial do
template, o `Shift+Tab` e o botão desabilitado. A prova de que prendem: com o seletor antigo
reposto, **4 dos 5 reprovam — e o que passa é justamente o do tema claro**, que é onde o defeito não
existia.

### NOVO-86 · `NOVO` O `NOVO-81` consertou um varredor de JS; existem dois · QA · 0,1 d

O `NOVO-81` tirou os `*.test.js` da varredura do `audit_frontend_standards.py`, com o argumento de
que o que um teste monta para exercitar uma regra é exatamente o que a regra proíbe em produção. O
argumento estava certo e a correção estava incompleta: **`core/tests/test_javascript_namespace_contract.py`
varre o mesmo `static/js/**` e tinha o mesmo problema.**

Apareceu ao escrever o teste do `NOVO-85`. Para simular a media query da gaveta, ele faz
`window.matchMedia = vi.fn()` — e o contrato reprova qualquer `window.X =` fora de `CV`. O teste
mede código entregue ao navegador; um duplo de teste não é isso.

Diferente do `NOVO-81`, que era latente, este **reprovou de imediato**: a suíte saiu de 1911 verdes
para uma falha, com `static/js/components/sidebar.test.js: window.matchMedia`.

Resolvido com o mesmo descarte, na origem da lista de fontes. A lição que fica é sobre a correção do
`NOVO-81`, não sobre este teste: quando um problema é de categoria — "arquivo de teste sendo lido
como produção" —, consertar a ocorrência que apareceu não fecha a categoria. Valia ter varrido quem
mais lê `static/js/**`.

### NOVO-87 · `NOVO` O fluxo do ofício não detecta roteiro duplicado · AUD · 0,5 d

O catálogo já registrava isto como "divergência real já existente" dentro do `BE-11`. Ao unificar
`novo` e `editar` a divergência ficou isolada e nomeável, então vira linha própria: `novo` e
`editar` chamam `encontrar_roteiro_duplicado`, que procura **qualquer** roteiro idêntico já salvo e
funde os dados nele. `oficios/route_views.py::wizard_roteiro` não chama.

O que o wizard tem é outra coisa: `roteiro_state_equivalente_ao_roteiro` (`:133`) compara o estado
submetido **só** com o roteiro que o usuário escolheu explicitamente no seletor. Se bater, vincula
sem copiar; se não bater, grava rascunho novo. Ou seja, salvar a etapa de roteiro de um ofício pode
criar um roteiro idêntico a um terceiro que o usuário nunca viu, sem aviso.

**Não foi mexido de propósito.** Dar detecção de duplicado ao wizard não é refatoração: muda o que
o usuário vê ao salvar a etapa, e `sobrescrever_roteiro_duplicado` migra ofícios e prestações e
apaga o registro obsoleto — exatamente a classe de operação que o comentário de
`oficios/route_views.py:139` manda nunca fazer com roteiro de outro ofício.

**Antes de decidir, medir:** quantos roteiros idênticos o fluxo do ofício cria de fato em produção.
Se forem poucos, a assimetria é aceitável e vira decisão documentada; se forem muitos, o desenho
tem de mudar — e aí é `BE-12`, não este.

### NOVO-88 ✅ RESOLVIDO `wizard_roteiro` repete dois blocos dentro de si mesma · AUD · 0,25 d

Achado ao medir o `BE-11`, e insumo direto do `BE-12`. A view de 165 linhas úteis tem duas
duplicações internas:

1. **Materializa rascunho + revincula ao ofício**, em `:140-146` e `:168-185`. Mesmo
   `if roteiro_vinculado is None or roteiro_vinculado.status != Roteiro.STATUS_RASCUNHO:` seguido de
   `Roteiro(tipo=…, status=…)`, `form.instance = …`, e depois
   `if oficio.roteiro_id != roteiro_salvo.pk: oficio.roteiro = …; oficio.save(...)`. **Só a segunda
   cópia injeta `area=`** — a primeira deixa o `Roteiro` nascer sem área e depende de quem salva
   para preenchê-la.
2. **O fallback de área** (`from cadastros.models import ConfiguracaoSistema` /
   `area = ConfiguracaoSistema.get_singleton().area`) está escrito duas vezes, em `:79-84` e
   `:170-173`.

A assimetria do item 1 é a parte que importa: duas escritas do mesmo registro com regras de área
diferentes na mesma view, e nada na suíte distingue os dois caminhos.

**Fechado no `BE-12`, e a causa era mais funda do que a redação acima.** As duas cópias viraram
`oficios/services.py::_materializar_rascunho_do_oficio`, com a regra do segundo bloco: `area` do
**ofício**, com queda para `ConfiguracaoSistema`.

Eu tinha escrito que o primeiro bloco estouraria o `NOT NULL` do `DB-02` numa requisição sem área
ativa. **Não estoura** — `get_oficio_by_id` filtra por `filter_queryset_by_area`, que lê o mesmo
thread-local que `Roteiro.save()` vai ler; sem área ativa o ofício já não é encontrado e a view
devolve 404 antes. O que existia era pior de achar: **o roteiro nascia na área certa por
coincidência de duas leituras do mesmo thread-local**, nunca por garantia. Fora de request o
`INSERT` vira `IntegrityError: NOT NULL constraint failed: roteiros_roteiro.area_id` — e foi assim
que o teste provou a correção, porque desfazer o `area=` reproduz exatamente esse erro.
<!-- Renumeração: o `#304` (BE-11) mesclou antes deste ramo e criou `NOVO-87` e `NOVO-88`.
     Estes três nasceram como 88/89/90 no ramo da E8 e viraram 89/90/91 para não colidir.
     Os commits `5d0c151f`, `7a4704f2` e `77dbaac9` citam os números antigos. -->

### NOVO-89 · `NOVO` O padding do `.form-block` entrou fora da escala de espaçamento · UI · 0,1 d

Dívida assumida de propósito na primeira sub-etapa da **E8**, e registrada no mesmo commit que a
criou.

Ao levar `padding: 14px` do tema escuro para a regra base de `.form-block`
(`fields/form-sections.css`), o valor entrou **literal**. A escala de espaçamento não tem 14px: vai
de `--space-3` (12px) para `--space-4` (16px).

**Por que não arredondei.** Usar `--space-4` mexeria **2px no tema escuro**, e a E8 é o claro
alcançando o escuro — não os dois indo para um terceiro lugar. Misturar "igualar os temas" com
"arrumar a escala" na mesma edição é o que torna regressão visual impossível de atribuir, que é o
risco que a etapa mais teme. O escuro tinha que sair byte a byte igual, e saiu: os prints das três
larguras dão dimensão idêntica antes e depois.

O 14px já não era estranho ao claro — `pages/roteiros.css` tem `padding: 14px` sem predicado de tema
no `.route-sede-block`, e `theme-dark-components.css` usa `padding: 12px 14px` em outros pontos. O
valor já circulava; o que este ID registra é que ele agora está na regra **base** de uma classe
presente em 23 templates, e portanto vale a pena resolver de uma vez.

**Fica para a E9** (`UI-02`), que reescreve `theme-dark-components.css` inteiro e é onde a escala
pode ser decidida sem se confundir com a igualação dos temas. Duas saídas possíveis, e a escolha é
do dono: arredondar para `--space-4` (16px, mexe 2px nos dois temas de uma vez) ou criar um token de
14px, se o valor se provar recorrente.

### NOVO-90 · `NOVO` A régua de tema não separa "diverge e pinta" de "diverge e não pinta" · QA · 0,5 d

Achado ao executar a segunda sub-etapa da **E8**, e ele muda como o número da etapa deve ser lido.

`medir_divergencia_tema.py` compara `getComputedStyle` entre os temas e conta toda diferença que não
seja cor. Isso trata como equivalentes duas coisas muito diferentes: propriedade que **muda o que o
usuário vê** e propriedade que o navegador **computa mas não pinta**.

O caso que expôs isso: `-webkit-font-smoothing: antialiased`, declarado só em
`html[data-theme="dark"] body`, valia **60.270 elementos — 48,2% de toda a divergência não-cor do
sistema**, mais que as quatro famílias catalogadas da E8 somadas (~16%).

Medido neste contêiner Linux, com Chromium:

| | |
|---|---|
| estilo computado | `auto` (claro) vs `antialiased` (escuro) — **difere** |
| largura renderizada do mesmo texto | 1264px vs 1264px — **idêntica** |
| print da lista de ofícios, antes e depois de globalizar | **idêntico byte a byte** (mesmo md5, nos dois temas) |

A propriedade tem efeito real no **macOS**. Então a divergência é verdadeira para quem usa Mac — o
tema claro e o escuro renderizam texto diferente lá — e é **invisível** aqui. As duas afirmações
convivem, e a régua não distingue uma da outra.

**Consequência prática, que precisa estar escrita:** a meta do plano para o `NOVO-58` ("divergência
próxima de zero") vai ser cumprida em boa parte por itens sem efeito visual nesta plataforma. Quem
ler só o número vai superestimar o ganho de tela. Uma queda de 48% na métrica pode significar zero
pixel movido — foi exatamente o que aconteceu.

Isto **não** torna a correção errada: globalizar segue o princípio que o próprio projeto escreveu no
`NOVO-62` ("tipografia não é decisão de tema") e conserta a divergência real no macOS. O que o ID
registra é que o instrumento precisa de uma segunda coluna.

O plano já avisava do parente deste defeito, na seção "a armadilha da tipografia": *"o número
19.896 elementos media a pilha declarada, não a face que o usuário vê […] não dá para determinar
daqui o que renderiza na máquina do usuário"*. O aviso valia para `font-family`; vale igual para
tudo que é renderização de texto.

**Saída sugerida para quem pegar este ID:** uma lista de propriedades sabidamente sem efeito de
layout no motor usado pela régua (`-webkit-font-smoothing`, `-moz-osx-font-smoothing`,
`text-rendering`, e as de `transition-*`, que só mudam a curva no tempo), contadas à parte no
relatório. Duas somas, não uma: a que move pixel e a que não move.

### NOVO-91 🔴 · `NOVO` A sessão remota mede ~35% menos divergência que o CI · QA · 0,5 d

Descoberto errando: apertei os tetos de `scripts/tetos_front.json` com números medidos **aqui**, e o
CI reprovou em 25+ rotas. O arquivo estava calibrado para o CI, e eu escrevi por cima dele medições
de outro ambiente.

A prova de que os tetos originais vieram do CI, e não daqui:

| rota | teto gravado | CI mede | local mede |
|---|---:|---:|---:|
| `dashboard@1440` | 1125 | **1125** | 780 |
| `cargo-editar@1440` | 1029 | **1029** | 672 |
| `combustiveis-lista@1440` | 1036 | **1036** | 676 |

Idêntico ao teto no CI, ~35% menor aqui. Não é ruído: são três casas decimais de coincidência em
rotas independentes.

**A causa provável é fonte.** O CI roda `python -m playwright install --with-deps chromium`, que traz
o conjunto de fontes dele; a sessão remota usa o Chromium pré-instalado da imagem, com outro
conjunto. Métrica de texto diferente muda quebra de linha, que muda altura, que muda quantos
elementos divergem. É o mesmo mecanismo que o plano descreve na "armadilha da tipografia" — e a
mesma advertência: *"não dá para determinar daqui o que renderiza na máquina do usuário"*.

**Consequência operacional, que é o que importa:** medição local serve para **comparar antes/depois
no mesmo ambiente** — foi assim que a cadeia do `.form-block` foi diagnosticada, e o diagnóstico
está certo. Não serve para **gravar teto**. Regravar `tetos_front.json` só pode ser feito com números
produzidos pelo CI.

Isso deixa um buraco de processo: hoje o CI **não** commita o JSON de volta (`--json` vai para
`$RUNNER_TEMP` e morre com o job), e regravar teto é passo manual. Ou seja, não existe caminho
suportado para baixar a catraca a partir de uma corrida do CI — que é justamente o que uma etapa como
a E8 precisa fazer a cada sub-etapa.

**Saída sugerida:** um passo opcional no `tests.yml`, disparado por rótulo ou `workflow_dispatch`, que
roda as duas réguas com `--atualizar-tetos` e publica o JSON como artefato — ou abre commit na
branch. Enquanto isso não existe, a catraca só desce quando alguém copiar os números do log do CI à
mão, e o log só mostra as rotas que **reprovaram**.

**Efeito medido apesar de tudo:** o próprio log de reprovação mostra a queda real no ambiente certo.
`configuracao` caiu de 1652 para 1425 a 1440px (−227), e o mesmo nas outras duas larguras (−204 cada).
`eventos-lista@1440` caiu 14. É menos do que os −9.376 medidos localmente, e é o número que vale.

### NOVO-92 · `NOVO` A tradução de ação do rodapé em redirect está copiada em cada passo do wizard · AUD · 0,75 d

Achado ao fechar o `BE-12`. Todo passo de wizard lê a ação do rodapé com
`core/wizard.py::normalizar_acao_do_wizard` — dono único desde o `BE-01` — e depois **cada um
escreve a sua própria cadeia** de `if nav_action == …` para traduzir a ação em mensagem e redirect:

| passo | onde | forma |
|---|---|---|
| `dados_viajantes` | `oficios/traveler_views.py:138` | helper privado `_redirect_after_dados_viajantes_save` |
| `transporte` | `oficios/traveler_views.py:210` | helper privado `_redirect_after_transporte_save` |
| `wizard_roteiro` | `oficios/route_views.py` | helper privado `_redirect_after_roteiro_save` (criado no `BE-12`; antes eram duas cadeias inline dentro da mesma view) |
| `wizard_justificativa` | `oficios/wizard_document_views.py:48` | inline |
| `wizard_documentos` | `oficios/wizard_document_views.py:144` | inline |

São três helpers com o mesmo nome-padrão e nenhum reuso entre arquivos, mais dois inline. É a mesma
família do `BE-01`, que centralizou a *leitura* do botão depois de duas cópias divergentes terem
quebrado a navegação de quatro telas do plano de trabalho — a *escrita* do destino continua
espalhada.

**Não é cópia literal**, e é por isso que não entrou no `BE-12`: cada passo tem destinos próprios, e
`wizard_documentos` ainda tem a ação `finalizar`, que os outros não têm. Unificar exige um mapa de
etapa → próximo/anterior, que é desenho, não extração mecânica. Fica para depois do `BE-13`.
<!-- Renumeração (2a vez nesta etapa): o `#305` (BE-12) mesclou antes deste ramo e criou
     `NOVO-92`. Estes dois nasceram como 92/93 no ramo da E8 e viraram 93/94. Ramos paralelos
     tiram número do mesmo contador sem reserva, e a colisão só aparece no merge — foi a
     segunda vez na mesma sessão (a primeira foi o `#304`, com o `NOVO-88`). -->

### NOVO-93 🔴 · `NOVO` A família 8b não é portável sozinha: no tema claro a borda é a única separação · UI · a decidir

Achado ao executar a **E8**, com o dono já tendo decidido a direção ("o claro perde as bordas"). A
medição contradiz a decisão, e por um motivo que não estava na mesa quando ela foi tomada.

**O que a família 8b parecia ser.** 186 regras predicadas em `html[data-theme="dark"]` declaram
borda. Medindo elemento a elemento nas 43 rotas, **54 têm efeito** — 754 elementos a 1440 e 800, 760
a 500. As outras 132 não mudam nada.

**Por que ela não pode ser aplicada inteira.** No tema escuro `border: 0` funciona porque as
superfícies se separam por **luminância**; no claro elas são todas brancas, e a borda é a única
separação que existe. Levar `border: 0` para o claro apaga a fronteira sem pôr nada no lugar. Cinco
casos verificados, com arquivo e linha:

1. **`.cv-module-card`** — o claro tem `border: 1px solid var(--color-border)` (`lists/cards.css:19`)
   **e** `border-top: 3px solid var(--color-accent-border-strong)` (`cards.css:61`). O shorthand da
   regra escura, neutralizado, **apaga o filete dourado do topo** de todo card do painel.
2. **Os `--step1-*`** (`--step1-surface`, `--step1-panel`, `--step1-field`) são ligados **dentro de
   regra escura** (`theme-dark-components.css:397-400` e `:5015-5017`). Fora dela existem só em
   `.attach-signed-modal__dialog` (`actions/action-system.css:717`) e `.collection-panel`
   (`lists/record-list.css:12`) — escopos que não alcançam o wizard. Um `border: 0` que vem casado
   com `background: var(--step1-surface)` chega ao claro com **variável indefinida**.
3. **`.cv-dialog__notice`** não tem regra clara nenhuma — só as duas escuras
   (`theme-dark-components.css:3937` e `:3948`). Neutralizar a borda desenha **um retângulo em volta
   de um `<p>` sem padding**. Não é mover declaração: é regra base que nunca foi escrita.
4. **Seis componentes ficam branco-no-branco**: `.list-header__wizard-back`, os `−`/`+` do
   `.pt-quantidade-stepper`, os botões de `.form-block__actions` do wizard,
   `.card-footer__secondary .cv-btn`, `.roteiro-mapa__canvas-head .cv-btn--secondary` e — o pior —
   `.roteiro-trecho-card__leg`, onde a borda é a única coisa que separa Saída de Chegada dentro de um
   card branco.
5. **`.search-picker__selected-card:last-child { border-bottom: 0 }`** é declaração morta no escuro
   (outras regras já zeram os quatro lados) e **viva no claro**, onde o card tem borda inteira
   (`fields/search-picker.css:590`). Neutralizada sozinha, o último card fica com contorno em U.

**Consequência para o plano.** A 8b **não é "mover borda"**: é adotar o sistema de superfícies do
escuro, e isso depende de os `--step1-*` existirem no tema claro. **A família está bloqueada na
camada de token, que é a E9.** Enquanto isso não existir, cada regra de borda só pode ser decidida
uma a uma, com print, e a maioria vai na direção contrária à que o enunciado supunha.

**O que entrou apesar disso:** `.sidebar-brand-badge` (86 elementos), onde a borda é decoração — um
anel creme sobre um badge dourado — e não separação.

### NOVO-94 · `NOVO` A família 8g move a régua e não move um pixel · QA · fechada na medição

Terceira ocorrência da mesma armadilha do `NOVO-90`, e a primeira detectada **antes** de virar
commit.

`justify-content` só desloca alguma coisa quando **sobra espaço** no container. Medindo o
deslocamento real do primeiro e do último filho dentro do pai, nos dois temas, nas 43 rotas:

| componente | elementos | `justify-content` difere | filho se move |
|---|---:|---:|---:|
| `.custom-select__option-check` | 72 | 72 | 1px, e só com o menu aberto |
| `.custom-select__chevron` (v2) | 21 | 21 | **0** — caixa de 16px com filho de 16px |
| `.segment-toggle__btn` (ofício/roteiro) | 8 | 8 | 2 |
| `.ordered-field-row__badge` | 3 | 3 | **0** — `display: none` nos dois temas |
| avatares do `search-picker` | 9 | 9 | **0** — `block` no claro contra `inline-flex` no escuro |
| `.empty-state__mark` | 24 | 24 | **0** — `inline` no claro contra `inline-flex` no escuro |
| `.list-tab` (≤600px) | 29 | 29 | **0** — os dois filhos já encostam nas duas bordas |

Das 137 divergências que a família contribui a 1440 e das 170 a 500, o que pinta é **o deslocamento
de 1px de um ícone de confirmação em lista suspensa aberta**. O que difere de verdade nesses
elementos é `display`, largura e padding — geometria real, e que **não pertence a família nenhuma da
tabela do plano**.

**Decisão do dono:** pular a 8g. Fazê-la derrubaria ~150 pontos da catraca sem entregar tela.

**O defeito verdadeiro que a medição encontrou** e que continua aberto: há componentes cujo desenho
inteiro só existe no tema escuro — `.empty-state__mark` (24 elementos, sem nenhuma regra fora do
arquivo escuro), os avatares do picker e o badge do wizard. Isso é maior que uma família e precisa de
decisão própria.
### NOVO-54 (continuação) 🟠 Trinta dos setenta `!important` de `.cv-field__control` não sustentavam nada · UI · 0,5 d

Segunda leva do `NOVO-54`. A primeira deu à classe uma regra base; esta começa a cobrar a dívida que
a base tornou visível.

**O método foi medir, não julgar.** Em vez de ler cada regra e decidir se o `!important` "parece
necessário", removi **todos os 70** de uma vez e medi. Depois fui restaurando até achar quem
realmente sustentava algo.

| passo | `!important` removidos | elementos alterados |
|---|---:|---:|
| todos | 70 | 10 |
| tudo menos `theme-dark-components.css` | 32 | 1 |
| tudo menos o tema e `base.css` | 30 | **0** |

**Os 2 de `base.css` são piso de acessibilidade, e o próprio código já dizia.** São o `outline` de
`:focus-visible` do `HT-01`, cujo comentário explica que **52 blocos** apagam o foco de campo sem pôr
nada no lugar — o `!important` é o que impede qualquer componente de remover o indicador. Removê-los
apagou o anel de foco em `/perfil/` no tema escuro, exatamente como o comentário previa.

**Os 38 do arquivo de tema ficam, e um deles está provado necessário.** Perguntei ao navegador quais
das 11 regras com `!important` daquele arquivo casam com os elementos afetados: **uma só**. As outras
10 miram passos de wizard (`[data-travel-document-wizard-*]`).

**E aí veio a parte que quase passou.** As 44 rotas da medição **não entram nos wizards**, então
aquelas 10 regras nunca eram exercidas — "não mudou nada" ali significaria apenas "não foi testado".
É a mesma armadilha do `.alert` no `NOVO-60`: *rota visitada não é cobertura*.

Estendi o conjunto para **51 rotas**, incluindo `/oficios/<pk>/roteiro/`, `/justificativa/`,
`/documentos/`, `/resumo/` e o editor de roteiro — de 41.946 para **53.636 elementos**, 102 telas.

**Com a cobertura ampliada, os 30 continuam medindo 0.** E aqui o piso de ruído importa: as telas de
wizard têm conteúdo variável, e duas capturas do **mesmo código** já diferem em **14 elementos**
(todos em `/justificativas/`). Os 30 removidos ficam em **zero — abaixo do próprio ruído**.

A comparação passou a ser **por caminho no DOM**, não por índice: com 53.534 elementos numa captura e
53.636 na outra, alinhar por posição compararia elementos diferentes e produziria diferença onde não
há.

**Resta:** 40 `!important` (38 no arquivo de tema, 2 de acessibilidade) e as 68 regras em si, que a
análise por família ainda vai separar entre contexto, estado, tema e divergência real.

### NOVO-95 · `NOVO` A prova por não-interseção não vale: a cascata não é monotônica · QA · fechada na medição

Erro de método cometido na **E9-a**, detectado pela própria régua antes de virar commit. Fica
registrado porque a ideia é tentadora e vai ocorrer a quem retomar a etapa.

**O raciocínio que parecia sólido.** Para descobrir quais das 307 regras só-escuras de cor podem
sumir, a bisecção custaria ~9 rodadas de captura completa. O atalho proposto foi:

> Apague **todas** as candidatas de uma vez e meça o conjunto `S` de elementos que mudaram. Para
> uma regra `R`, se `R` não casa com nenhum elemento de `S`, apagar `R` não muda nada — os
> elementos fora de `S` não mudaram nem com tudo removido, e os de `S` não são tocados por `R`.

Com isso, 307 candidatas viraram **36 provadas** (inócua ∧ exercitada pelo corpus ∧ não de lista
mista).

**A medição derrubou.** Removendo exatamente essas 36: **75 elementos mudaram**, contra um piso de
ruído de 4. E o diagnóstico está no detalhe: **71 dos 75 não estavam em `S`**.

Removendo um **subconjunto**, mudaram elementos que removendo **tudo** não mudavam.

**Por que.** O argumento supõe monotonicidade — que remover menos regras produz um subconjunto das
mudanças. A cascata não funciona assim. Se `A` e `B` competem pelo mesmo elemento e `A` vence:
remover só `A` **promove `B`**, e o valor final pode diferir tanto do estado original quanto do
estado sem as duas. Com `A` e `B` fora, o elemento cai na regra base — que pode calhar de ser o
valor original, e aí ele nem aparece em `S`.

**O que sobra de válido.** O instrumento (`sonda_mesmo_tema.py`: mesmo tema, dois estados de
código, 41.754 elementos chaveados por caminho no DOM, piso de ruído de 4 elementos em
`justificativas-lista`) está certo e é rápido — uma captura completa. O que não vale é **inferir**
o efeito de um diff a partir do efeito de outro. **Meça o diff que você pretende entregar**, não um
diff maior do qual você deduz.

**Consequência para a E9-a:** volta para bisecção de verdade, ou para lotes pequenos medidos um a
um. O custo que o atalho tentava evitar é real e tem de ser pago.

### NOVO-96 ✅ RESOLVIDO · 🔴 `NOVO` A faixa de filtros não tinha fundo no tema claro · UI · 0,25 d

Primeira entrega da **E9**, e um defeito visual real que estava escondido atrás de uma variável.

`lists/list-header.css:85` declara, em regra **sem predicado de tema**:

```css
.list-header__rail {
  /* Mesmo token da área interna dos cards (.record-card__band). */
  background: var(--card-family-bg);
```

`--card-family-bg` existia **só** em `base/03-theme-dark.css:299`. No tema claro a leitura era
inválida (*invalid at computed-value time*) e a propriedade caía para o valor inicial. Medido no
navegador, antes:

| elemento | claro | escuro |
|---|---|---|
| `.list-header__rail` | **transparente** | superfície escura |

O comentário logo acima da declaração chama o elemento de "faixa clara abaixo do título". Ele não
era faixa nenhuma: a barra de filtros de **toda lista do sistema** aparecia sem fundo no tema que o
sistema mostra para quem nunca escolheu tema.

**Correção.** As nove definições `--card-family-*` passam a existir também no `:root` de
`base/tokens.css`. Os valores são **os mesmos** do arquivo escuro, sem uma vírgula de diferença,
porque todos são `var(--color-*)` — a mesma expressão resolve claro no `:root` e escuro no bloco de
tema. Como `tokens.css` carrega antes de `03-theme-dark.css`, o escuro continua ganhando com os
próprios valores, e as definições de lá viraram redundantes (a E9-a decide se saem).

**Prova, com o instrumento novo da etapa** (`sonda_mesmo_tema.py`: mesmo tema, dois estados de
código, 41.754 elementos chaveados por caminho no DOM, `transition` e `animation` desligadas):

| | |
|---|---:|
| elementos alterados no **claro** | **47**, em 33 das 86 capturas |
| elementos alterados no **escuro** | **2** |

Os 2 do escuro são `justificativas-lista`, e são **exatamente o piso de ruído** medido capturando a
mesma base duas vezes — o mesmo par de caminhos, causado por conteúdo que varia entre capturas.
**O tema escuro não se moveu.**

### Anotação: o `.record-card__band` é outro defeito, e continua aberto

Ao medir esta correção ficou claro que `.record-card__band` **não** é o mesmo caso, embora o
comentário do `list-header.css` o cite como fonte. Ele segue transparente no claro depois da
correção, porque a sua única declaração de fundo mora dentro de regra predicada em `dark`
(`theme-dark-components.css:4942`): no claro não existe regra nenhuma para ele.

É a classe "componente cujo desenho só existe no escuro" — a mesma que barrou a família **8b**
(`NOVO-93`) e que apareceu na medição da **8g** (`NOVO-94`, com `.empty-state__mark`). Token não
resolve; precisa de regra base, e isso é decisão de desenho.

### NOVO-97 · `NOVO` A E9-a entrega 32 regras, e o caminho até elas custou três tentativas · UI · em curso

Primeira colheita medida da **E9-a**: 32 regras só-escuras de cor saem do repositório sem mudar um
pixel em tema nenhum.

**O caminho, porque ele é o resultado mais reaproveitável desta sub-etapa.**

| tentativa | o que foi feito | resultado |
|---|---|---|
| 1 | apagar as 307 candidatas e ler o efeito | 6 mudanças **no claro** — impossível para regra predicada em `dark`. Causa: **17 regras de lista mista** (parte do seletor neutra, parte escura) apagadas inteiras |
| 2 | recortar só as partes escuras da lista | **pior**: 274 mudanças no claro, nenhuma das 86 capturas intacta. Separar lista por vírgula com regex quebra `:is()` multi-linha — `lists/list-header.css:578` virou `:hover:not(:disabled))`, com parêntese desbalanceado |
| 3 | regra de lista mista **não entra** | claro **zero** (as 2 leituras eram o piso de ruído). 2.598 mudanças no escuro, que é o sinal real |

Da tentativa 3 saiu a lista de candidatas, e daí veio o `NOVO-95`: a prova por não-interseção não
vale, porque a cascata não é monotônica. As 36 regras "provadas" por aquele atalho reprovaram com
**75 elementos alterados**.

**O que funcionou no lugar da bisecção.** Atribuir o resultado do diff **que foi de fato rodado** —
não de um diff maior do qual se deduz. Perguntando quais das 36 casam com os 75 elementos
alterados, saíram **4 culpadas**:

```
theme-dark-components.css:3782   .icon-btn--whatsapp
theme-dark-components.css:3806   .icon-btn--delete
theme-dark-components.css:5137   .person-row--highlight
theme-dark-components.css:5161   .person-row--highlight .person-row__avatar
```

As duas primeiras pintam ícone de ação lendo `--action-success-*`/`--action-danger-*`; as duas
últimas, a linha destacada do roster. São o caso que quebra a monotonicidade: competem com outra
regra pelo mesmo elemento, então remover uma **promove** a outra.

Removendo as 32 restantes, medido contra o estado imediatamente anterior: **4 elementos alterados,
que são exatamente o piso de ruído** — o mesmo par de caminhos em `justificativas-lista`, nos dois
temas.

**Custo real do método:** duas capturas (~8 min cada) e uma atribuição (~4 min) por lote, e o lote
termina com as culpadas **nomeadas** — não só com "a metade de cima reprovou", que é tudo o que a
bisecção daria pelo mesmo preço.

**Catracas, todas por mérito:**

| | antes | depois |
|---|---:|---:|
| `theme-dark-components.css` | 5.788 linhas | **5.610** |
| `!important` fora do bundle | 466 | **463** |
| `audit_frontend_standards` | 239 | **237** |
| `audit_ui_patterns` | 2.456 | **2.447** |

**O que continua aberto:** 173 candidatas **nunca exercitadas** pelas 43 rotas em repouso — o
elemento só existe com diálogo, menu ou dropdown aberto. Sobre elas a medição não diz nada, e
tratá-las como inócuas seria repetir o `NOVO-90`. Medi-las exige estender o corpus aos estados de
sobreposição, como o `NOVO-54` fez ao ir de 44 para 51 rotas.

### NOVO-98 · `NOVO` Guardas do gravador do editor são inalcançáveis: regra defensiva duplicada do parser · QA · 0,5 d

**Como apareceu.** Escrevendo a rede do `BE-13` fatia 3 eu ia "cobrir as 6 linhas descobertas" de
`_salvar_roteiro_avulso_from_roteiro_state`. Cinco cenários, todos verdes — e **três passavam com o
código quebrado**. A prova por inversão os reprovou como vazios. Investigando o porquê, com sondas no
POST real:

```
tempo_adicional_min = -30 no POST   ->  chega ao gravador como 0
duracao_estimada_min = "" no POST   ->  chega ao gravador como 285 (já derivada)
trecho que duplica o retorno        ->  chega ao gravador já removido
```

`_build_roteiro_state_from_post` e `dedupe_roteiro_loop_retorno_final` **já normalizam** tudo isso a
montante. As guardas correspondentes dentro do gravador (`max(0, …)`, a derivação de
`duracao_estimada_min`, o descarte do trecho que duplica o retorno) são **cópias defensivas de regra
que roda antes**. É por isso que `coverage` nunca as alcançou: não é lacuna de teste, é ramo
inalcançável pelo caminho público.

**Por que registrar em vez de apagar.** O gravador é público desde o `BE-13` fatia 3
(`roteiros/services/editor_persistence.py`), e um chamador futuro pode entrar sem passar pelo parser
— foi justamente o que o `BE-12` fez com `salvar_roteiro_do_oficio`. Apagar as guardas junto com a
mudança de arquivo seria mudar comportamento numa fatia que se comprometeu a não mudar nenhum.

**Correção:** decidir de que lado mora cada regra. Ou o gravador passa a confiar no estado validado
(guardas saem, e o contrato "recebe estado já normalizado" vira docstring e teste), ou a
normalização é dele e o parser para de fazê-la. Hoje as duas fazem, e a segunda é código que nenhum
teste pode exercitar honestamente.

**Escopo medido:** 3 guardas, 6 linhas, em `editor_persistence.py`.

**Lição de método, que vale além deste caso:** cobertura descoberta não é sinônimo de teste faltando.
Antes de escrever teste para uma linha vermelha, vale perguntar se ela é alcançável — a inversão
responde em minutos e evita encher a suíte de cenários que não protegem nada. Este é o terceiro caso
da etapa (`BE-11` e `BE-13` fatia 1 tiveram um cada), e os três só apareceram porque a inversão é
obrigatória.

### NOVO-99 🔴 · `NOVO` O formulário do editor de roteiro não recebe o token CSRF: salvar pela tela devolve 403 · HT · 0,25 d

**Achado ao verificar o `BE-13` fatia 3 na tela.** O plano da fatia exigia *salvar de verdade pelo
navegador*, porque o gravador só roda no POST. O POST voltou **403 — "Verificação CSRF falhou"**, nas
quatro páginas do editor.

**A causa, com o próprio Django dizendo o nome:**

```
UserWarning: A {% csrf_token %} was used in a template, but the context did not
provide the value. This is usually caused by not using RequestContext.
```

`templates/roteiros/includes/_roteiro_editor.html:24` tem `{% csrf_token %}` dentro do
`<form id="roteiro-editor-form">`. Mas os três lugares que incluem esse arquivo fecham o contexto com
`only`:

- `templates/roteiros/roteiro_form_page.html:25`
- `templates/roteiros/partials/roteiro_form.html:1`
- `templates/oficios/wizard_roteiro.html:20`

O `only` isola o contexto e a lista explícita de variáveis **não passa `csrf_token`**. A tag então
renderiza string vazia, e o formulário vai para o navegador sem token. Medido: **1 ocorrência de
`csrfmiddlewaretoken` na página inteira**, e ela é do formulário de logout no cabeçalho — **zero
dentro do formulário do editor**, em `/roteiros/novo/`, `/roteiros/<pk>/editar/` e nas duas variantes
da etapa 2 do ofício.

**Por que a suíte não pega.** O `Client` do Django é isento de CSRF por padrão
(`enforce_csrf_checks=False`), então os 1.954 testes exercitam o POST do editor sem nunca passar pela
checagem. É o `NOVO-20`/`NOVO-28` outra vez: ambiente de teste mais permissivo que produção.

**A correção, provada:** acrescentar `csrf_token=csrf_token` à lista de cada um dos três `include`.
Verificado em processo — com os três ajustados, o token aparece dentro do formulário nas três páginas
e o aviso do Django some; e pelo navegador o POST passa a responder "Roteiro atualizado com sucesso."
com redirecionamento para a lista. **A correção não entra no PR do `BE-13` fatia 3**: é template, é
outra responsabilidade, e a fase 7 está sendo mexida por sessão paralela — conflito garantido.

**Não é regressão da fase 7.** O `only` está nos três `include` desde `a4739eff` (01/08), o commit de
importação do projeto. O `index.html` já passa `:csrf_token="csrf_token"` explicitamente para o
componente de lista — a mesma armadilha, ali resolvida.

**Vale varrer o resto:** qualquer `include ... only` que contenha `{% csrf_token %}` tem o mesmo
defeito, e o aviso do Django é o detector — sobe no log a cada render.
<!-- Renumeração (3a vez nesta reconstrução): o `#312` (BE-13 fatia 3) mesclou antes deste ramo
     e criou `NOVO-98` e `NOVO-99`. Este nasceu como `NOVO-98` no ramo da E9 e virou `NOVO-100`.
     As anteriores foram com o `#304` (`NOVO-88`) e o `#305` (`NOVO-92`). Ramos paralelos tiram
     número do mesmo contador sem reserva, e a colisão só aparece no merge. -->

### NOVO-100 · `NOVO` O sistema de superfície do wizard só existia no tema escuro · UI · 0,5 d

Terceira entrega da **E9**, e a que **destrava a família 8b** (`NOVO-93`).

`theme-dark-components.css` ligava as quatro variáveis do sistema de superfície do wizard —
`--step1-surface`, `--step1-panel`, `--step1-field`, `--step1-empty` — **dentro de uma regra
predicada em `dark`**. No tema claro elas não existiam nesse escopo.

**O tamanho do buraco, contado:**

| leituras de `--step1-*` | quantas |
|---|---:|
| dentro de regra escura | 112 |
| em regra que o claro alcança, **com** `fallback` | 62 |
| em regra que o claro alcança, **sem** `fallback` | **32** |

Essas 32 não resolviam nada no claro.

**É a causa raiz do `NOVO-93`.** No escuro `border: 0` funciona porque o fundo separa as
superfícies; levar só a borda para o claro tirava a fronteira **sem pôr nada no lugar**, porque o
fundo dependia de um token que o claro não tinha. Era por isso que seis componentes ficariam
branco-no-branco, entre eles o `.roteiro-trecho-card__leg`, onde a borda é a única coisa que separa
Saída de Chegada.

**Correção.** As duas regras que ligam os tokens (o cartão do wizard e o `.collection-panel`) são
partidas em duas: um gêmeo `:is(html[data-theme])` carregando **só a definição das variáveis**, e a
regra escura ficando com a **pintura** (`background`, `border-color`, `box-shadow`) e com a
re-ligação de `--color-input-bg`. Pintura é decisão de tema; mexer nela é a 8b, com aprovação
própria. Mesma especificidade, gêmeo adjacente — o argumento da E8.

**Prova** (`sonda_mesmo_tema.py`, 41.754 elementos por caminho no DOM, com `--revelar --pseudo
hover`):

| | |
|---|---:|
| elementos alterados no **claro** | **36**, em 21 capturas |
| elementos alterados no **escuro** | **2** |

Os 2 do escuro são o piso de ruído. As maiores mudanças caem em `oficios-wizard-roteiro`,
`roteiros-editar` e `roteiros-novo` — o wizard, como esperado.

**Correção a um registro anterior:** eu havia escrito no `NOVO-93` que os `--step1-*` chegavam ao
claro "com variável indefinida". Não globalmente — eles têm ligação neutra em
`actions/action-system.css` (`.attach-signed-modal__dialog`) e `lists/record-list.css`
(`.collection-panel`), e lá resolvem bem. O buraco era **só no escopo do wizard**. Isso muda o
conserto: não era criar token, era ampliar escopo.
### NOVO-54 (continuação 2) 🟠 As 72 regras de campo, classificadas por medição, e as 7 que caíram · UI · 1 d

Terceira leva do `NOVO-54`. As duas primeiras deram à classe uma regra base e cobraram 30 dos 70
`!important`. Esta ataca as **regras em si**, por remoção empírica: em vez de ler cada uma e julgar
se "parece necessária", removi e medi.

**Primeiro, o inventário estava vencido.** O `campo.json` da leva anterior tinha 68 regras; a
globalização mecânica do `NOVO-68` reescreveu `[data-theme="dark"]` para `[data-theme]` em dezenas de
seletores depois disso. Os instrumentos casavam regra por **texto do seletor**, então toda regra
reescrita deixou de casar — e "não casou" foi lido como "não vence", isto é, como candidata a
remoção. A poda falhou alto (`bloco em 2053 nao fecha`) em vez de apagar o bloco errado, mas por
sorte, não por desenho. Re-extraído do CSS atual: **72 regras, 40 `!important`**.

*Inventário de CSS tem prazo de validade de um merge.*

**Dois instrumentos, porque um só não responde.** Um diz se a rota chega a **renderizar** o alvo da
regra (`querySelectorAll` do seletor, sem as pseudo-classes de estado); o outro diz se a regra chega
a **ganhar** alguma propriedade (`CSS.getMatchedStylesForNode`, percorrido em ordem de precedência,
honrando `!important`). Sem o primeiro, "nunca venceu" confunde regra morta com regra que rota
nenhuma abriu — a armadilha do `.alert` no `NOVO-60`.

| destino | regras | o que significa |
|---|---:|---|
| vence | 23 | ganha alguma propriedade: fica |
| candidata | 25 | alvo renderizado e mesmo assim não ganha nada |
| sem cobertura | 16 | rota nenhuma renderizou o alvo: não dá para julgar |
| pseudo-elemento | 8 | `::placeholder`, `::-webkit-scrollbar-*`: fora do alcance do CDP |

**Candidata não é sinônimo de podável.** A captura mede o **repouso**: não sabe dizer o que acontece
no `:hover` nem no `:focus`. Das 25 candidatas, 8 descrevem estado e ficaram de fora do lote — provar
com medição de repouso seria trocar prova por suposição. Mais duas ficaram por intenção explícita:
`:where(.cv-field__control)` e a variante `--textarea` "nunca vencem" **porque** `:where()` tem
especificidade zero e perde para o seletor de elemento nu de `base.css` — que é exatamente o que o
`NOVO-54` quer apagar *depois*. Removê-las seria andar para trás.

**A bissecção, com o piso de ruído medido** (duas capturas do mesmo código, 112 telas, 59.006
elementos):

| lote podado | elementos alterados |
|---|---:|
| as 15 do lote inicial | 490 |
| sem as 2 regras amplas do tema | 127 |
| `list-header.css` sozinha responde por | 43 |
| as 7 finais | **4 — o próprio piso** |

**Caíram 7 regras**, provadas neutras: duas de `theme-dark-components.css` em `.composite-field__control`,
uma duplicata de subconjunto (mesmo seletor de `roteiros.css:2412`, declarações contidas nas dela),
`select.css` em `.field-with-action`, `justificativas.css` no textarea do quick-add, `usuarios.css` no
modal de vínculo e a variante escura de `cadastros-config.css`.

**Mais uma família inteira morreu por grep:** `.header-filter-datepicker` — 8 blocos em
`page-shell.css`, incluindo um `@media` que só continha ela. A classe não existe em template, view
nem script, e nada a monta em tempo de execução (`header-filter-input` e `header-filter-select`
existem; `-datepicker` não). Uma das 8 é o `page-shell.css:2542` que aparece como "sem cobertura" na
tabela acima — aqui o grep decidiu, e o navegador só confirmou.

**Uma armadilha que custou uma rodada:** restaurar um **subconjunto** dos blocos podados reinsere
cada um no índice que ele tinha no arquivo original, e com outros blocos ainda ausentes acima ele
aterrissa no lugar errado. As chaves continuam balanceadas e o CSS continua válido — só que a ordem
da cascata mudou, e apareceram 71 diferenças em `/roteiros/` que **não vinham de nenhuma regra
removida**. Bissecção agora sempre parte do estado limpo (`git checkout`) e poda o subconjunto numa
passada só.

**O piso de ruído não era ruído de renderização — era o relógio.** `/justificativas/` mostra
`ATUALIZADA 10/08/2026 23:32`, com precisão de minuto, e numa fonte proporcional os dígitos não têm
todos a mesma largura. Duas capturas em minutos diferentes divergiam em 4 elementos; duas no mesmo
minuto, em zero. O piso oscilava entre 0 e 4 conforme a hora da captura — e um piso que é loteria não
serve de referência. A captura passou a guardar o **texto** de cada elemento e o comparador separa
*"o texto mudou"* (reflow) de *"o estilo mudou"* (cascata). Com isso, piso e mudança medem a mesma
coisa: **0 diferenças de estilo, 4 de conteúdo**, dos dois lados.

**Uma rota do corpus era 404 e ninguém tinha notado.** `page.goto()` não levanta exceção em 404, 500
nem em redirecionamento para o login: devolve a resposta e segue. `/prestacoes-contas/1/` não existe
— o caminho real é `/prestacoes-contas/prestacao/<pk>/documentos/` — e a rota entrava na captura como
uma tela de erro, sem campo nenhum, contando como cobertura. O instrumento agora confere o status e a
URL final, e **aborta**. Foi assim que o defeito apareceu.

**O instrumento do repositório subiu junto.** `scripts/medir_campos_computados.py` dizia, na própria
docstring, que alcançava 8 rotas e que ampliar isso era "trabalho a fazer antes de remover essas
regras". Ganhou `--rotas` (caminhos já resolvidos, com PK); troca de `networkidle` — que nunca
fica ocioso nas páginas de roteiro — por espera até a árvore parar de crescer, porque o editor de
roteiro só materializa os campos depois de `loadCities()` resolver e tempo fixo mediria a página
antes de eles existirem; conferência de status HTTP e de URL final; e **aborta** quando uma rota
falha, em vez de seguir comparando conjuntos de rotas diferentes. Medido: de 64 para **192
combinações** rota|tema|estado e de 224 para **1048 leituras**.

**Resta:** 65 regras. Das 25 candidatas, 8 de estado esperam um instrumento que meça `:hover`/`:focus`
e 2 são a base intocável; 16 sem cobertura precisam de rota que abra modal, passo de wizard ou painel
colapsado; 8 de pseudo-elemento precisam de outro caminho que não o `getMatchedStylesForNode`.

### NOVO-54 (continuação 3) 🟠 As candidatas de estado foram medidas no estado certo · UI · 0,5 d

A classificação anterior deixou oito candidatas de estado para trás porque o instrumento media
repouso. A primeira tentativa de fechar essa lacuna achou quatro defeitos na própria régua antes de
tocar no CSS:

1. `medir_campos_computados.py` fixava um executável Linux em `/opt/pw-browsers`, embora o projeto
   já tivesse `navegador_medicao.abrir_chromium()` para escolher o build correto no CI, na sessão
   remota e no Windows;
2. `focus` e `focus-visible` eram forçados sempre juntos, escondendo a diferença entre foco por
   ponteiro e foco de teclado;
3. transições e animações continuavam ativas. Duas capturas do mesmo código produziram **45
   diferenças falsas**, com cores e sombras fracionárias fotografadas em frames distintos;
4. a documentação dizia que conteúdo e estilo eram separados, mas `JS_COLETA` não registrava o
   conteúdo do controle.

A régua agora usa o lançador canônico, mede `focus`, `focus-visible` e a combinação separadamente,
desliga movimento antes da captura, espera dois frames depois de cada pseudoestado e registra texto
fora do dicionário de estilo. Duas execuções do mesmo código deram **0 diferenças de estrutura, 0 de
estilo e 0 de conteúdo**, em **204 combinações rota|tema|estado e 1.116 leituras**.

Com o piso limpo, as sete candidatas não-base caíram em três cortes, cada um medido em zero:

- alternativas `:hover`/`:focus` repetidas dentro dos mesmos blocos que já continham
  `.cv-field__control`/`.date-picker__control`, em `roteiros.css` e em três regras de
  `theme-dark-components.css`;
- o seletor de estado duplicado e o bloco de foco redundante do Quick Add em `list-header.css`;
- o `outline: none` do campo do wizard de ofícios, inclusive no novo estado isolado `focus`.

O oitavo bloco é o piso global de `:focus-visible` do `HT-01` e **fica**: não é dívida de contexto,
é a trava de acessibilidade que impede as outras regras de apagarem o indicador de teclado.

O corpus adicional também foi refeito sobre o banco descartável: **54 rotas, 312 combinações e
1.488 leituras**. A conferência de status abortou corretamente ao encontrar `/eventos/1/` sem seed;
a rota não foi contada como cobertura. Continuam para a próxima leva os 16 contextos interativos e
os 8 pseudo-elementos (`::placeholder`/`::-webkit-scrollbar-*`).

### NOVO-54 (continuação 4) 🟠 Pseudo-elementos medidos e a classe passa a possuir a base · UI · 0,5 d

A régua passou a fotografar `::placeholder`, `::-webkit-scrollbar`, `-track` e `-thumb`, além de
registrar a cadeia de ancestrais de cada controle. Também ganhou `--seletor`, porque mudar o seletor
nu de `input/select/textarea` alcança controles que ainda não carregam `.cv-field__control` e medir
só a classe não provaria neutralidade do corte.

Duas capturas idênticas do novo formato deram o mesmo SHA-256: **54 rotas, 312 combinações e 1.272
leituras** da classe. A captura ampla de `input, select, textarea` mediu **648 combinações e 7.260
leituras**. Nela, trocar os seletores base de elemento por `:where(input, select, textarea)` e
`:where(textarea)` produziu **0 diferenças de estilo, pseudo-estilo e estrutura**; 1.596 diferenças
eram apenas valores dinâmicos de controles ocultos e ficaram corretamente fora do estilo. Como
`field.css` é carregado depois de `base.css`, a regra canônica da classe passa finalmente a possuir
a aparência sem quebrar controles legados que ainda dependem do seletor de elemento.

As oito regras de pseudo-elemento foram retiradas juntas e repetidas contra o mesmo corpus amplo:
**0 diferenças de pseudo-estilo**. Todas eram redundantes. O bloco
`.justificativa-panel .cv-field__control--textarea` também caiu: o grep do repositório inteiro só
encontrava a própria regra e `test_wizard_justificativa.py` exige explicitamente que essa classe não
seja renderizada.

O inventário atual fica em **47 regras, 13 arquivos, 0 pseudo-regra**. A E7c permanece parcial: os
contextos de diário e `field-with-action` ainda não renderizam um `.cv-field__control` no corpus, e
serão classificados sem inferir ausência a partir de rota visitada.

### NOVO-54 (continuação 5) ✅ Os contextos interativos fecham a E7c · UI · 0,5 d

O corpus ganhou as duas rotas que faltavam: `/prestacoes-contas/prestacao/1/diario/` e
`/planos-trabalho/atividades/`. A primeira materializou **120 leituras** dentro de
`.diario-trecho-block`; a segunda, **48** dentro de `#quick-add-atividade`. `field-with-action` já
existia em **156 combinações**, mas seus controles atuais são `form-select` e `search-picker`, nunca
um ramo exclusivo de `.cv-field__control`.

Com essa cobertura, foram retirados somente ramos de seletor duplicados que casavam o mesmo elemento
por `form-control`, `input`, `select` ou `textarea`: três regras de `field-with-action` em cada uma
das duas folhas, duas do diário, uma do efetivo e duas da solicitação de equipe. O estilo permanece
no contexto; saiu a segunda maneira de selecionar o mesmo nó.

A medição antes/depois cobriu **56 rotas, 672 combinações rota|tema|estado e 7.536 leituras**:
**0 diferenças de estilo, pseudo-estilo e estrutura**. As 1.656 diferenças eram somente valores
dinâmicos, deliberadamente separados do estilo. O inventário fecha em **36 regras vivas de base, a11y ou contexto,
11 arquivos e 0 pseudo-regra**, contra 72 regras no início da classificação. A regra canônica possui
a base, e os contextos restantes são variações medidas, não correções cegas. **E7c concluída.**
