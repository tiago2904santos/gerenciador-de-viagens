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
catálogo.

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

### BE-09 🔴 Isolamento por área depende de o programador lembrar · AUD · 6 d · risco alto

`core/tenancy.py:57` — `filter_queryset_by_area(queryset, area=None)` é função livre. Nenhum dos
54 modelos declara manager próprio (`default_manager=Manager` em todos). Varredura excluindo
migrations/tests/commands/scripts/admin: **123 ocorrências de `.objects.`** em modelos com campo
`area` fora do filtro, em código de caminho de request.
**Efeito:** o modelo de segurança multi-tenant é convenção, não garantia. `BE-04`, `BE-05`,
`BE-10` e `DB-03` são a prova de que a convenção falha.
**Correção:** `AreaScopedManager` como `objects` nos 28 modelos com `area`, com
`all_objects = models.Manager()` para migração, comando e backfill. App por app, começando por
ofícios, roteiros e prestações.

### BE-10 🔴 App `justificativas` sem isolamento de área · AUD · 2 d · risco médio

`justificativas/selectors.py:20` (`listar_justificativas`), `:44`, `:48`; `views.py:32`
(`_oficios_summary_for_quick_add`); `forms.py:105` (queryset do picker de ofícios) — nenhum aplica
`filter_queryset_by_area`. O modelo `Justificativa` **não tem campo `area`**, e
`ModeloJustificativa.nome` é `unique=True` global.
**Efeito:** número, protocolo, assunto, servidores, roteiro e viatura de ofícios de outra unidade
aparecem no seletor; justificativas de outra área aparecem na lista e podem ser excluídas por URL.
**Correção:** migração acrescentando `area` (FK PROTECT) aos dois modelos, com backfill a partir
de `oficio.area`; `UniqueConstraint(area, nome)`; filtro nos 4 selectors e nos 2 pickers.

### BE-11 🟠 Editor de roteiro em 3 cópias · AUD · 3 d · risco alto

`roteiros/views.py:203` (`novo`, 89 linhas úteis) e `:311` (`editar`, 86 linhas) têm similaridade
0,629 e 41 linhas idênticas; `oficios/route_views.py:100` (`wizard_roteiro`, 175 linhas) partilha
20 linhas idênticas com as outras duas.
**Divergência real já existente:** só `novo`/`editar` tratam roteiro duplicado
(`encontrar_roteiro_duplicado`/`sobrescrever_roteiro_duplicado`); o fluxo do ofício não.
**Correção:** `roteiros/services/editor_flow.py::processar_submissao_editor(...)` devolvendo
resultado tipado, e um presenter único. As três views ficam com ~25 linhas.

### BE-12 🟠 `wizard_roteiro` concentra a regra de vínculo/cópia na view · AUD · 2 d · risco alto

`oficios/route_views.py:100` — 181 linhas e 24 ramos, a maior view do sistema (a segunda tem 125).
Decide vínculo sem cópia ou rascunho novo (`:127-143`), instancia `Roteiro(...)` direto
(`:136`, `:167`) e persiste em quatro pontos (`:94`, `:96`, `:144`, `:183`).
**Efeito:** a regra que mais gera bug de dados neste sistema — roteiro é compartilhado entre
ofícios — não é testável sem subir request HTTP nem reusável pelo fluxo avulso.
**Plan mode obrigatório.**

### BE-13 🟠 `roteiros/roteiro_logic.py` fora do contrato de camadas · AUD · 4 d · risco alto

1.779 linhas, o maior módulo de produção do repositório, 57 definições de topo **todas privadas**,
misturando parsing de request, montagem de contexto e persistência. Importado pelos services.
**Correção:** fatiar por responsabilidade em PRs sucessivos — parsing sai para forms, contexto
para presenters, persistência para services. Depois de `BE-11`.

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

### BE-17 🟡 `core/views.py` é 75% fixture de UI Lab · AUD · 1,5 d

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

### BE-20 🟡 `diario_bordo` é app-casca morto · MED · 0,5 d

33 linhas de Python no total: `models.py` 49 bytes, `services.py` 54, `forms.py` 66, uma view
`index` que renderiza um placeholder ("Base futura para geracao de diario de bordo a partir de
modelo XLSX"). A funcionalidade real mora em `prestacoes_contas`
(`diario_bordo_form.html`, `diario_motorista_form.html` e 7 partials).
`grep -rn "diario_bordo:index\|diario-bordo" templates/` → **zero**: a rota não é alcançável.
Colateral: o piso de cobertura de 91,17% em `.github/coverage-floors.json` mede 33 linhas.
Era o `P-08` da Etapa 8 do ciclo antigo, nunca decidido.

### BE-21 🟡 Presenter morto prometendo funcionalidade inexistente · MED · 0,25 d

`oficios/presenters.py:621` — `apresentar_opcoes_documentais_oficio()` devolve
`[{"label": "DOCX (em breve)", "enabled": False}, {"label": "PDF (em breve)", "enabled": False}]`.
Grep no repositório inteiro: **1 ocorrência, a própria definição**. Zero chamadores.

### BE-22 🟡 Dez arquivos `.py` com BOM UTF-8 · AUD · 0,5 d

Todos em `cadastros/`. Quebram `ast.parse` em ferramenta de análise estática.

### BE-23 🟡 Vocabulário de rotas divergente · AUD · 1 d · risco médio

Das 433 rotas nomeadas, **307 (71%)** não usam nenhum sufixo do `PADRAO_APP.md`. `cadastros` e
`usuarios` usam inglês (`_create`/`_update`/`_delete`); `eventos`, `justificativas`, `oficios`,
`planos_trabalho` e `prestacoes_contas` usam português (`_novo`/`_editar`/`_excluir`). Nenhum app
mistura internamente.
**Não viaja com nenhuma outra etapa:** renomear rota exige `urls.py` + `reverse()` + templates +
testes no mesmo PR.

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

### BE-25 🟡 Dois UI Labs concorrentes, sem regra de qual é o vigente · AUD · 0,75 d

`ui_lab2` (656 LOC + 18 templates) e `templates/dev/ui_lab` (19 templates). Ambos só roteados sob
`DEBUG`, mas `ui_lab2` está em `INSTALLED_APPS` em todos os ambientes
(`config/settings/base.py:54`) e tem piso de cobertura de 67,42%.
**Decisão humana necessária.** O perdedor sai com a prova de grep do `AGENTS.md` §3.6.

---

## DB — Dados, migrações e integridade

### DB-01 🟠 A tabela de diárias é nacional e qualquer EDITOR a altera · AUD+VER · 1,5 d · risco médio

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

### DB-02 🔴 `area` anulável em 27 de 28 modelos · AUD · 5 d · risco alto

Só `usuarios.VinculoUsuarioArea` tem `area` NOT NULL. Os outros 27 — `Oficio`, `Roteiro`,
`PrestacaoContas`, `TermoAutorizacao`, `OrdemServico`, `PlanoTrabalho`, `Evento`, `Servidor`,
`Viatura`, `DocumentoArtefato`… — aceitam NULL. E `core/tenancy.py:63-67`:
`if area is None: return queryset.filter(area__isnull=True)`.
**Efeito, nos dois sentidos:** um usuário autenticado sem vínculo de área vê e edita **o balde
inteiro** de dados legados sem área; e todo código que roda sem request (tarefa assíncrona de
geração documental, comando, signal fora de ciclo) grava com `area=None`.
**Correção em três passos:** (1) rodar `backfill_legacy_areas` e provar com
`select count(*) where area_id is null` por tabela; (2) `NOT NULL` nos modelos transacionais via
migração com validação; (3) só então mudar o comportamento de `filter_queryset_by_area` sem área.

### DB-03 🟠 Limpeza de rascunhos apaga rascunho de outra área · AUD · 1 d

`roteiros/services/roteiro_editor.py:317` —
`Roteiro.objects.filter(destinos__isnull=True, trechos__isnull=True, saida_dt__isnull=True,
origem_cidade__isnull=True).exclude(pk=roteiro_atual_pk).delete()`, sem recorte por área. Teste
funcional em transação revertida: rascunho da área B apagado por usuário da área A.
**Efeito:** o autosave cria rascunho vazio antes de o usuário digitar. Enquanto um usuário da área
B está com o editor aberto nesse estado, qualquer usuário de outra área que salve um roteiro apaga
o dele — sem mensagem.
**Correção:** `filter_queryset_by_area` na base da consulta **e** recorte por idade
(`created_at__lt=now()-timedelta(minutes=30)`), para não competir com edição em curso.

### DB-04 🟡 Cache de artefato documental não recorta por área — risco latente · AUD+VER · 1 d

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

### DB-05 🟡 Placa de viatura única globalmente · AUD · 1,5 d

`cadastros/models.py` — `Viatura.placa = CharField(max_length=7, unique=True)` e
`Viatura.Meta.constraints` vazio. `justificativas/models.py` — `ModeloJustificativa.nome`
`unique=True`, e o modelo sequer tem `area`.
**Efeito:** uma área bloqueia o cadastro de outra e descobre pela mensagem de erro que a placa já
existe em algum lugar — vazamento por canal lateral. Viatura transferida entre unidades não pode
ser registrada nas duas.

### DB-06 🔴 Cascata apaga comprovante e assinatura já coletados · AUD · 3 d · risco alto

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

### DB-07 🟠 Dois `CheckConstraint` em 54 modelos · AUD · 3 d · risco médio

61 `UniqueConstraint` contra 2 `CheckConstraint`
(`tabela_diaria_valor_24h_positivo` e `prest_serv_diaria_recebida_positiva`). Nenhum dos **9 pares
início/fim** tem constraint de ordem: `Evento`, `TermoAutorizacao`, `PlanoTrabalho`, `EventoPlano`,
`OrdemServico`… Medido em transação real: data de fim anterior ao início e diária negativa entram.
**Efeito:** o banco não é última linha de defesa de nada. Qualquer caminho que escape da validação
de formulário — import, comando, migração de dados, correção manual — grava período impossível, e
o valor viaja para o ofício e para a prestação assinada.
**Limite 4 do `AGENTS.md`:** cada migração entra com a query de validação dos dados existentes.

### DB-08 🟠 Coleções ordenadas aceitam duplicata · AUD · 2 d

`RoteiroDestino`, `RoteiroTrecho`, `PlanoDestino`, `EventoPlano` e `DiarioBordoTrecho` têm
`constraints=[]`. Provado em transação real: dois `RoteiroDestino` com a mesma `(roteiro, ordem)`
são aceitos.
**Efeito:** destino duplicado é contado **duas vezes pelo motor de diárias** e impresso duas vezes
no ofício e no termo. Ordem repetida torna a sequência não determinística, mudando o documento
gerado entre duas visualizações do mesmo roteiro.

### DB-09 🟠 Lista de roteiros agrega antes do `LIMIT` · AUD · 2 d

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

### DB-10 🟡 Falta índice composto para a ordenação real das listas · AUD · 0,5 d

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

### DB-11 🟡 As 80 buscas livres são varredura sequencial · AUD · 3 d

80 ocorrências de `__unaccent__icontains`; extensão `unaccent` instalada, `pg_trgm` ausente;
**0 índices GIN ou trigram** em 390 índices. Prova direta: busca de ofícios com `q="ambi"` sobre
24.000 registros → `Seq Scan`, **35,7 ms** na primeira medição e **31,3 ms** (`EXPLAIN`) /
51,1 ms (ORM completo) na verificação, para devolver 20 cards. Os três números batem na ordem de
grandeza.
**Correção em duas frentes:** (1) quando `q` for dígito, trocar `oficio__numero__icontains` por
`oficio__numero=int(q)` — ganho grande, custo quase zero; (2) `pg_trgm` + índices GIN sobre
expressão nas 4 ou 5 colunas realmente buscadas.

### DB-12 🟡 Trilha de auditoria cresce sem limite e encarece toda escrita · AUD · 3 d

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

### PF-01 🟠 192 KB de SVG repetido por página de lista · MED · 2–3 d

`/oficios/?aba=atuais` com 20 ofícios: 425 KB de HTML, 12.545 linhas, **378 `<svg>` inline
somando 192 KB (45% da página)**, 854 `<path>`.
Causa: `templates/components/ui/icons/icon.html` — 222 linhas de `{% if %}/{% elif %}` (36 ramos)
que emitem o `<svg>` inteiro a cada inclusão.
**Correção:** folha de símbolos + `<use href="#cv-icon-…">`. O ícone cai de ~500 para ~60 bytes.
Sucessor do `R-02` da Etapa 8, que ficou pendente sem o preço medido.

### PF-02 🟠 90% do CSS entregue não casa com a página · MED · ver plano de front

Medido no Chromium via CDP: 664–816 KB de CSS entregues por rota, **10,1% a 11,8% casado**. Na
rota `/prestacoes-contas/`, `oficios.css` (106 KB) chega com **0,0%** de uso.
O trabalho está no [`PLANO_FRONTEND.md`](PLANO_FRONTEND.md); aqui fica a métrica de aceite:
**uso acima de 35% por rota** ao fim da reconstrução.

### PF-03 🟡 Toda requisição escreve na tabela de sessão · MED · 1–2 d · risco médio

`config/settings/base.py:111` — `SESSION_SAVE_EVERY_REQUEST = True`. Custo fixo de uma requisição
autenticada trivial (`/health/`): **7 queries**, três delas a escrita da sessão
(`BEGIN`/`UPDATE django_session`/`COMMIT`). Toda página, todo XHR de autosave, todo polling de
documento abre transação de escrita.
**Decisão humana necessária:** desligar sem mais nada faz a sessão de 8 h expirar a partir do
login, não da última ação. Alternativas: backend `cached_db` ou renovar só perto do fim.

### PF-04 🟡 60 menus de ação renderizados para 20 cards · MED · 2–3 d · risco médio

Mesma página: 60 blocos `cv-action-menu` (3 por card) e 200 `cv-action-menu__item` (10 por card),
todos no HTML inicial, quando no máximo um fica aberto por vez.

### PF-05 🟡 A lista de Ofícios leva 127 ms no servidor · MED · —

Com 17 queries planas e 20 cards. As outras listas ficam entre 15 e 46 ms. É consequência de
`PF-01` e `PF-04`; existe como **métrica de aceite** deles: abaixo de 40 ms sem subir a contagem
de queries.

### PF-06 ⚪ Queries duplicadas em duas rotas · MED · 0,5 d cada

`/usuarios/` emite 2 queries idênticas repetidas; `/prestacoes-contas/`, 1. Sintoma de consulta
refeita em camada diferente.

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

### JS-02 🟠 Ciclo de vida existe e 14 de 17 componentes não o implementam · AUD+VER · 3–4 d · risco médio

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

### JS-03 🟠 Zero teste automatizado para 17.859 linhas de JS · AUD+VER · 5+ d · risco baixo

Não há `package.json`, runner, nem `*.test.js` no repositório. Os únicos scripts com Playwright
são utilitários de captura de tela, fora de qualquer workflow do `.github`. Toda a lógica
client-side — cálculo de diárias no editor de roteiros, autosave, upload, máscaras, e o `JS-01`
acima — só é validada à mão.

> **Número corrigido pela verificação (05/08): 17.859, não 25.492.** A contagem original somava
> `shell.bundle.js` (7.633 linhas) às fontes que o compõem — dupla contagem do mesmo código. Vale
> o mesmo para o CSS: **43.038** linhas de fonte, não 60.707.

### JS-04 🟠 Cadeia de promise sem `.catch` no editor de roteiros · AUD · 0,5 d

`static/js/pages/roteiros/editor/index.js:790-822` — `scheduleAutoEstimarTrechos()` dispara
`runAutoEstimarTrechos` por `setTimeout` (retorno descartado), e o `pending.reduce(...)` (`:806`)
encadeia `CV.http.fetchJson(...).then(...)` **sem nenhum `.catch` na cadeia inteira**. A função
irmã `calculateDiarias()` (`:1386`), na mesma página, trata o erro corretamente.
**Efeito:** falha de rede na estimativa de distância não avisa nada — os campos ficam vazios e o
erro vira promise rejeitada só visível no console.

### JS-05 🟠 O auditor de CI cobre 6 dos ~9 invariantes · AUD+VER · 1–2 d

`scripts/audit_frontend_standards.py:139-176` tem **6** regras JS — `raw_fetch`,
`duplicated_csrf_header`, `duplicated_debounce`, `duplicated_escape_html`, `duplicated_normalize`,
`native_feedback` — e `audit_js()` (`:263-268`) pula `*.bundle.js`. (O enunciado original listava
as seis e somava cinco.) Não existe regra para `innerHTML` com dado dinâmico, listener sem
remoção, `catch` vazio, nem uso de nome de classe CSS como condição de lógica.
**Efeito:** `JS-01`, `JS-02` e `JS-06` podem regredir com o CI verde.

### JS-06 🟡 Nome de classe CSS usado como condição de lógica em 7 arquivos · AUD+VER · 1 d

`classList.contains("cv-search-picker")` aparece **10 vezes em 7 arquivos** (o enunciado original
dizia 9 arquivos e listava 7):
`components/location-rows.js:16`, `pages/ordens-servico-form.js:119,406`,
`pages/viaturas-form.js:62`, `pages/planos-trabalho-wizard.js:14,151,318`,
`pages/termos-form.js:60`, `pages/servidores-form.js:62`, `pages/configuracoes.js:126`.
**É o defeito que fixa a ordem do plano de front:** renomear `cv-search-picker` na etapa de CSS
quebra o roteamento de foco em 6 páginas, em silêncio.
**Correção:** trocar por atributo dedicado (`data-entity-picker-root`) e deixar a classe só para
estilo — **antes** de qualquer renomeação de CSS.

### JS-07 🟡 "Fechar ao clicar fora / Esc" reimplementado 4 vezes · AUD · 2 d · risco médio

`components/picker.js:798,828`, `components/cv-date-picker.js:728-731,787-788`,
`cv-select.js:131,179,302,313`, `components/picker-select.js:394,432` — quatro implementações sem
função compartilhada.

> **Detalhe corrigido pela verificação (05/08): estava invertido.** O enunciado dizia que só
> `cv-select.js` fechava em `scroll`/`resize`. Ele não tem **nenhum** listener desses. Quem tem é
> `cv-date-picker.js:794-795` — e mesmo ele apenas **reposiciona** o painel aberto
> (`if (isOpen) positionPanel()`), não o fecha. **Nenhuma das quatro** fecha em scroll ou resize.
> A duplicação continua real; a divergência citada, não.

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

### JS-09 🟡 Tela de espera de documento carrega 264 KB para usar 3,3 KB · AUD · 0,5 d

`templates/documentos/geracao_aguarde_embedded.html:27` é um documento autônomo (não estende
`base.html`) que carrega `shell.bundle.js` inteiro. O único uso de `CV.*` na tela é
`CV.http.fetchJson` (`document-generation-wait.js:10`), definido em `core/http.js` (116 linhas).
A tela só mostra um spinner e faz polling.

### JS-10 🟡 Modularização do editor de roteiros é fachada · AUD · 0,25 d ou 3+ d

`static/js/pages/roteiros/editor/state.js`, `retorno.js` e `diarias.js` têm **3 linhas cada** e
devolvem só `{ name: 'state' }` etc. São importados e instanciados em `index.js:11-20`, e os
objetos não são usados em mais lugar nenhum. A lógica real continua nas 1.848 linhas de `index.js`
(81% do cluster).
**Efeito:** a estrutura de arquivos mente. Quem procurar a regra de diárias em `diarias.js` não
acha.
**Decisão:** completar a extração (3+ dias, depois de `BE-13`) ou remover os stubs (0,25 d).

### JS-11 ⚪ Máscara de CEP duplicada e `onlyDigits` em 4 cópias · AUD · 0,25 d

`pages/configuracoes.js:6-9` reimplementa `maskCep` byte a byte em vez de chamar
`CV.masks.format(value, 'cep')`. `onlyDigits` está reimplementado em `roteiros_wizard.js:2`,
`components/document-number-field.js:2`, `components/masks.js:9` e `pages/configuracoes.js:2`.

### JS-12 ⚪ `CV.registry` e `CV.componentRegistry` são duas definições redundantes · ~~AUD~~ VER · 0,25 d

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

### HT-01 🔴 Foco de teclado invisível em todo campo do sistema · AUD · 1–2 d

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

### HT-11 🔴 Campos de formulário renderizados sem nome acessível · AUD+MED · 1,5 d

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

### HT-12 🟠 `help_text` declarado no form nunca chega à tela · AUD · 0,5 d

`templates/components/ui/forms/field.html:45` — `{% if help_text %}` imprime **apenas o parâmetro
do include**, nunca `field.help_text`. Forms de produção que declaram `help_text` no campo não o
exibem em lugar nenhum.

### HT-13 🟠 `docs/DATA_ATTRIBUTES_JS.md` descreve um contrato que não existe mais · AUD · 0,5 d

O documento cita 4 arquivos JS que já foram removidos e 3 atributos com zero ocorrências no
repositório, enquanto o contrato realmente em uso (`data-entity-picker`, `data-inline-create-*`)
não está documentado. É um `PADRAO_*` que aponta para o passado — quem seguir, erra.

### HT-14 🟡 28% dos includes não usam `only` · AUD · 2 d

Componentes leem contexto ambiente do chamador em vez de receber só o que declaram. É como um
componente passa a depender de uma variável que o chamador tem por acaso — e quebra quando outro
chamador não tem.

### HT-15 🟡 Bloco `cv-itinerary` duplicado em 5 apps · AUD · 1,5 d

Idêntico byte a byte entre dois deles. Mesma família do `HT-08`: markup de `cv-icon-btn` e
`cv-action-menu__item` também reescrito à mão em templates de app.

### HT-02 🟠 Erro de campo sem associação programática · AUD · 2–3 d · risco médio

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

### HT-03 🟠 Sem padrão único para erro de formulário inteiro · AUD · 2 d

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

### HT-05 🟡 `empty_state.html` quebra a ordem de headings · AUD+MED · 0,5 d

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

### HT-06 🟡 Dez a quatorze componentes mortos · AUD · 0,5–1 d

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

### HT-07 🟡 Concatenação condicional com "·" no template · AUD · 1–2 d

`templates/eventos/partials/_evento_card_body.html:17` (repetido nas linhas 75 e 137) monta o
subtítulo com uma cadeia de `{% if %}` cujo separador depende de
`oficio.destino_display and oficio.protocolo or oficio.destino_display and
oficio.data_evento_display` — **sem parênteses**, dependendo da precedência do motor de template.
`grep -rn '{% if .*and.* %} ·'` → **10 ocorrências em 8 arquivos**.
O mesmo arquivo tem a maior profundidade de aninhamento do repositório: **6 níveis** (linhas
123-198).
**Correção:** `join_non_empty(parts, sep=" · ")` no presenter, testável.

### HT-08 🟡 Oitenta `<button>` fora do sistema de componentes · AUD · 3–4 d · risco médio

Por app, excluindo componentes e labs: `prestacoes_contas` 23, `oficios` 15, `eventos` 11,
`planos_trabalho` 10, `roteiros` 10, `termos` 6, `ordens_servico` 3, `core` 1, `usuarios` 1.
`components/ui/buttons/button.html:2` já resolve a semântica (`{% if href %}<a>{% else %}<button>`),
então a maioria é reimplementação de markup, não falta de suporte.
**Efeito:** qualquer mudança de contrato do botão — a começar pelo foco do `HT-01` — precisa ser
replicada em 80 pontos.
**Armadilha:** parte deles tem handler de JS amarrado à classe. Conferir `static/js/components/*`
antes de cada substituição (mesma família do `JS-06`).

### HT-09 ⚪ Login sem skip link e sem erro associado · AUD · 0,5 d

`templates/core/login.html:1-79` não estende `base.html`: duplica `<!doctype>`, `<head>` e tema.
Medido no navegador: é a **única** das 25 páginas testadas sem `<a class="cv-skip-link">`. Os erros
de campo (`:56`, `:64`) têm `id`, mas `core/forms/__init__.py:14-27` nunca os referencia por
`aria-describedby`.

### HT-10 ⚪ Migração de `data-*` de toggle parada no meio · AUD · 0,5–1 d · risco médio

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

### UI-01 🟠 36% das classes declaradas não aparecem em lugar nenhum · MED · ver plano de front

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

| arquivo | blocos mortos | peso |
|---|---:|---:|
| `oficios.css` | 283 | 47 KB |
| `dev/ui-lab-fields.css` | 96 | 18 KB |
| `dev/ui-lab-pages.css` | 79 | 16 KB |
| `page-shell.css` | 78 | 14 KB |
| `roteiros.css` | 78 | 14 KB |
| `cv-buttons.css` | 49 | 11 KB |

**A prova de grep exigida pelo `AGENTS.md` §3.6 tem que ser refeita arquivo a arquivo no PR** —
esta contagem é o mapa, não a licença.

### UI-02 🟠 Tema escuro é camada de exceção, não de token · MED

`static/css/components/theme-dark-components.css` tem **5.843 linhas** — o maior arquivo CSS do
projeto depois do bundle — e **190 `!important`**. O tema escuro não é resolvido por token: é
resolvido sobrescrevendo componente por componente. Total de `!important` fora do bundle: **497**.

### UI-03 🟠 Nove arquivos definem token de cor · MED

`--color-*` é **definido** em `tokens.css`, `theme.css`, `03-theme-dark.css`,
`components/theme-dark-components.css`, `page-shell.css`, `roteiros.css`, `usuarios.css`,
`justificativas.css` e `gdrive-config.css`. Redefinições campeãs: `--step1-surface` (15×),
`--step1-panel` (15×), `--step1-field` (13×), `--field-border-focus` (7×), `--cv-field-bg` (7×),
`--color-input-bg` (7×).

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

### QA-11 🟡 `reparar-producao.yml` em UTF-16LE · AUD · 0,25 d

`file .github/workflows/*.yml`: os outros três são UTF-8; este é "UTF-16, little-endian, with CRLF".
`od` confirma BOM `FF FE` e bytes intercalados com `00`. Mesma família do `BE-22` (BOM em arquivos
Python), agora num workflow.
**Efeito:** o GitHub documenta suporte a BOM UTF-8/16/32, então pode funcionar — o risco é não se
ter certeza, e este é justamente o workflow de **reparo manual de produção**, ou seja, o que se
descobriria quebrado durante um incidente.
**Correção:** reconverter para UTF-8 sem BOM e validar com um `workflow_dispatch` de baixo risco.

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
ela travou na verificação (ver `NOVO-02`). (`adapters/excel_pdf.py` está em 0% mas é Windows-only
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

### NOVO-02 ⚪ A suíte trava ao combinar certos grupos de apps · VER · a investigar

Na verificação, rodar `documentos` + `oficios` + `termos` + `prestacoes_contas` + `eventos` juntos
levantou `AttributeError: 'ModelChoiceField' object has no attribute 'to_field_name'`. A suíte
completa e a suíte por app passam; a combinação parcial não. Cheira a estado global vazando entre
testes, ou a ordem de importação — e é o tipo de coisa que só aparece quando alguém tenta medir
cobertura de um subconjunto, que é exatamente o que o `QA-15` precisa fazer.
**Precisa ser reproduzido numa sessão limpa antes de virar trabalho.**

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

### NOVO-07 🟠 A tela de justificativas cresce com a tabela inteira: 15 MB de HTML · MED · 0,5 d

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

### QA-17 ⚪ Treze PRs abertos sem triagem · MED · 1 d

PRs #4, #7, #10, #13, #14, #16, #27, #32, #44, #58, #137, #144 são de maio–julho/2026; #178 é de
05/08. O plano antigo já registrava que #27, #32 e #44 foram resolvidos por outros caminhos, e os
PRs seguem abertos.
**Não foi possível medir daqui se ainda aplicam:** o clone desta sessão é *shallow* (128 commits),
então `git diff main...branch` responde "no merge base" para todos. Precisa de histórico completo
ou da API do GitHub. **Decisão humana.**
