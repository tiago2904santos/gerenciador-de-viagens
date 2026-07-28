# Auditoria final — correção, desempenho, acessibilidade medida e custo do sistema

**Escopo:** o que as três auditorias anteriores não cobriram — se o sistema **faz a coisa certa**, não apenas se o código está bem escrito. Regras de negócio de dinheiro, isolamento multi-área, desempenho medido, acessibilidade medida, documentos gerados, terminologia. Fecha com o **dimensionamento econômico** do sistema.

**Diferença de método:** esta auditoria **executou** o sistema. Rodei a suíte completa, instrumentei as páginas para contar queries, populei o banco para medir escala, e calculei contraste WCAG dos pares de cor reais. Onde as auditorias anteriores deduziram, esta mediu.

**Companheiras:**
[`AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md`](AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md) ·
[`AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md`](AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md) ·
[`AUDITORIA_BACKEND_INFRA_COMPLETA.md`](AUDITORIA_BACKEND_INFRA_COMPLETA.md)

---

## Índice

1. [Dimensão real do sistema](#1-dimensão-real-do-sistema)
2. [Correções às auditorias anteriores](#2-correções-às-auditorias-anteriores)
3. [Regras de negócio — o motor de diárias](#3-regras-de-negócio--o-motor-de-diárias)
4. [Desempenho medido](#4-desempenho-medido)
5. [Segurança medida — tenancy e assinatura pública](#5-segurança-medida)
6. [Acessibilidade medida — contraste WCAG](#6-acessibilidade-medida)
7. [Documentos gerados](#7-documentos-gerados)
8. [Terminologia e microcopy](#8-terminologia-e-microcopy)
9. [Catálogo de defeitos desta auditoria](#9-catálogo-de-defeitos-desta-auditoria)
10. [Consolidado das quatro auditorias](#10-consolidado-das-quatro-auditorias)
11. [Quanto custa este sistema](#11-quanto-custa-este-sistema)
12. [Quanto custa deixá-lo impecável](#12-quanto-custa-deixá-lo-impecável)
13. [Roteiro para a banca técnica](#13-roteiro-para-a-banca-técnica)

---

## 1. Dimensão real do sistema

| Artefato | Quantidade |
|---|---|
| **Linhas de código próprio** | **150.829** |
| — Python (aplicação) | 73.933 |
| — CSS | 40.135 |
| — JavaScript | 18.301 |
| — Templates HTML | 12.324 |
| — Migrações | 6.136 |
| Documentação técnica (Markdown) | 12.755 |
| **Models** | **116** |
| **Endpoints (rotas)** | **429** |
| Templates | 369 (80 componentes globais) |
| Comandos de gestão | 27 |
| **Testes automatizados** | **812** (todos passando, 18,5 s) |
| Apps Django | 13 |
| Dependências de produção | 24 |
| Modelos DOCX | 11 |
| Motores de PDF | 5 |
| Integrações externas | 2 (Google Drive OAuth, OpenRouteService) |
| Commits | 586 |
| Janela de desenvolvimento | 13/05/2026 → 28/07/2026 (~2,5 meses) |

**Contexto que a banca vai notar:** 150 mil linhas em 2,5 meses são ~7,8 commits/dia sustentados. É um ritmo que só se explica com forte alavancagem de ferramentas de IA — e isso é uma resposta legítima, desde que acompanhada de evidência de qualidade (a suíte de 812 testes é essa evidência). Vale antecipar a pergunta em vez de esperá-la.

---

## 2. Correções às auditorias anteriores

Medir desmentiu duas afirmações minhas. Registro por honestidade técnica — se eu não corrigir, a banca corrige.

| Auditoria | Afirmei | Realidade medida |
|---|---|---|
| HTML/JS §3.5 e §8.1 | "`pagination.html` não é `<nav>`" | **Falso.** `templates/components/ui/lists/pagination.html:2` é `<nav class="pagination-shell" aria-label="Paginação">`. Correto desde sempre. |
| HTML/JS §3.5 | Div soup implicaria problema de acessibilidade generalizado | **Parcialmente falso.** A varredura de `<button>` sem `type`, `<img>` sem `alt`, `target=_blank` sem `rel` deu **zero** em todos. A base de acessibilidade é melhor do que a proporção div/section sugeria. |

Também revi o método: na primeira medição de queries eu usei nomes de aba inexistentes (`futuros`, `andamento`) e concluí que a lista renderizava zero cards. Era erro do meu teste — `core/documento_abas.py` define `futuras`/`atuais`/`finalizados`/`cancelados`. Refeito, a lista renderiza corretamente.

---

## 3. Regras de negócio — o motor de diárias

`roteiros/services/diarias.py` (448 linhas) é o código que calcula **dinheiro público**. É o arquivo que uma banca vai abrir primeiro. Está bem escrito — `Decimal` em toda a cadeia, `ROUND_HALF_UP` explícito, comentários que justificam cada decisão de regra, 317 linhas de teste dedicadas. Os problemas são de **arquitetura da regra**, não de implementação.

### 3.1 🔴 Tabela de valores fixada no código-fonte

```python
TABELA_DIARIAS = {
    'INTERIOR':  {'24h': Decimal('290.55'), '15': Decimal('43.58'),  '30': Decimal('87.17')},
    'CAPITAL':   {'24h': Decimal('371.26'), '15': Decimal('55.69'),  '30': Decimal('111.38')},
    'BRASILIA':  {'24h': Decimal('468.12'), '15': Decimal('70.22'),  '30': Decimal('140.43')},
}
```

Três problemas encadeados:

1. **Mudança de decreto exige deploy.** O valor da diária estadual muda por ato normativo. Hoje isso é uma alteração de código, teste, build e publicação — não uma edição em tela por quem tem competência para fazê-la.
2. **Não há vigência.** Não existe `data_inicio_vigencia`. Se o valor mudar, **todo ofício histórico recalculado passa a usar o valor novo** — inclusive os já pagos. Um sistema financeiro precisa reproduzir o cálculo da data do fato gerador.
3. **Não há rastro.** Nenhum registro de qual tabela foi usada em cada ofício. Auditado hoje, um ofício de maio não consegue provar com que valor foi calculado.

O sistema já tem o lugar certo para isso: existe `Configuracao` em `cadastros` e `docs/CONFIGURACOES_SISTEMA.md`. A tabela deveria ser um model `TabelaDiaria(vigencia_inicio, vigencia_fim, tipo, valor_24h, valor_15, valor_30)` com o valor aplicado **congelado no roteiro** no momento do cálculo.

**Como isso soa numa banca:** "e quando o decreto mudar?" é a primeira pergunta. Sem resposta, a arquitetura financeira é considerada imatura, por melhor que seja o resto.

### 3.2 🟠 Duas regras de cobrança diferentes na mesma função

O código tem dois regimes, decididos por `len(tipos_permanencia) > 1`:

| Cenário | Diárias integrais | Complemento (15%/30%) |
|---|---|---|
| **Categoria única** (só interior, ou só capital) | pernoites | **no máximo UM**, medido sobre a viagem inteira (linhas 313-351) |
| **Categorias mistas** (interior + capital) | pernoites por período | **um POR PERÍODO** (linhas 279-303) |

O comentário do próprio código, na linha 308, condena o que o outro ramo faz:

> "Nunca um complemento por trecho — do contrário a mesma viagem acumularia 15% de um trecho + 30% de outro, inflando o total."

Mas é exatamente isso que o ramo de categorias mistas faz. Duas viagens de mesma duração podem ser cobradas de forma diferente só porque uma cruzou a fronteira de uma capital. Pode ser intencional e juridicamente correto — mas **não está documentado em lugar nenhum**, e a `docs/REGRAS_DE_NEGOCIO.md` (77 linhas) não menciona o tema.

Isso é o tipo de coisa que a banca encontra lendo o próprio comentário do código.

### 3.3 🟠 Segunda fonte de verdade geográfica

`CAPITAIS_POR_UF` fixa as 26 capitais em Python, enquanto o sistema importa a base IBGE completa (`cadastros/management/commands/importar_geografia_ibge.py`) e tem model `Cidade`. São duas fontes que podem divergir: uma cidade marcada como capital no banco continua sendo cobrada como interior se o dicionário do código não a listar. `classify()` cai em `'INTERIOR'` por omissão — o erro é sempre **para menos**, o que é melhor que o contrário, mas ainda é erro.

### 3.4 🟡 Cálculo morto no caminho dominante

`_segment_breakdown()` calcula `dias_inteiros` (blocos de 24 h decorridas) e `parcial`. No caminho de categoria única esses valores são **descartados** e substituídos por `pernoites` (noites dormidas). Convivem duas definições de "diária integral" na mesma função: tempo decorrido e noites. Um mantenedor futuro que "corrigir" uma quebra a outra.

### 3.5 🟡 Assimetria de arredondamento

`total_valor` é somado dos subtotais; `valor_por_servidor` é `total / servidores` arredondado. `valor_por_servidor × servidores` pode não fechar com `total_valor`. Numa prestação de contas por servidor, isso aparece como centavos que não batem.

### 3.6 🟡 Um pernoite de duas horas

`count_pernoites()` usa `(chegada.date() - saida.date()).days`. Saída 15/03 23:00, chegada 16/03 01:00 → **1 pernoite = 1 diária integral (R$ 290,55)** por duas horas de viagem. Pode ser a regra correta do decreto (cruzou a noite), mas não há teste cobrindo essa borda nem menção na documentação.

---

## 4. Desempenho medido

Instrumentei as páginas com `CaptureQueriesContext` e populei o banco progressivamente.

### 4.1 ✅ Não existe N+1 **em Ofícios** — resultado forte

| Registros na lista | Queries | HTML |
|---|---|---|
| 1 ofício | **16** | 66 KB |
| 20 ofícios | **16** | 452 KB |

**+0,00 query por registro adicional.** A estratégia de `prefetch_related` de `oficios/selectors.py` (17 otimizações em 14 funções, com `Prefetch` aninhado para servidores, termos, destinos e trechos) funciona. Páginas em banco vazio ficam entre 6 e 16 queries — dentro do razoável.

Este é o melhor resultado das quatro auditorias e vale ser apresentado ativamente: é a pergunta clássica de banca sobre Django, e a resposta é medida, não afirmada.

> **Correção (28/07, PR da Etapa 1 / `N-02`).** A medição acima cobriu **só a lista de
> Ofícios**. Medida do mesmo jeito, a lista de **Ordens de Serviço tem N+1 clássico**:
> 26 queries com 1 OS, 134 com 20, **1.814 com 300** — ~6 queries por card. A frase
> "não existe N+1" vale para Ofícios, não para o sistema. Ver `NOVO-07`.

### 4.2 🔴 O problema é o payload, não a query

**22,1 KB de HTML por ofício.** Projeção:

| Ofícios na lista | HTML transferido |
|---|---|
| 20 | 0,4 MB |
| 50 | 1,1 MB |
| 100 | 2,2 MB |
| 300 | **6,5 MB** |
| 1.000 | **21,6 MB** |

E aqui está a causa:

### 4.3 🔴 Duas listas principais não paginam

| Lista | Paginação |
|---|---|
| Eventos | ✅ 20/página |
| Roteiros | ✅ 15/página |
| Termos, Planos de Trabalho, Prestações, Justificativas, Cadastros | ✅ |
| **Ofícios** | ✅ 20/página — *corrigido na Etapa 1* |
| **Ordens de Serviço** | ✅ 20/página — *corrigido na Etapa 1* |
| `oficios/catalog_views.py` (modelos de motivo) | ❌ |
| `planos_trabalho/catalog_views.py` (4 catálogos) | ❌ |

Agravante: `list_page_cards.html` **inclui o componente de paginação** em todas as listas. Como `page_obj` nunca entra no contexto dessas páginas, o `{% if page_obj %}` falha em silêncio e o componente não renderiza. A interface parece suportar paginação e não suporta.

**Ofícios é a lista mais usada do sistema e a que você indicou como referência visual.** Com 300 ofícios num ano — plausível para um órgão — a página entrega 6,5 MB e monta ~1.200 cards no DOM. Numa apresentação com dados reais, isso trava.

**Medido depois da correção**, com a mesma instrumentação e 300 registros:

| Lista | HTML antes | HTML depois | Queries antes | Queries depois |
|---|---|---|---|---|
| Ofícios | 5.855 KB | **434 KB** | 16 | **17** (as 16 + o `COUNT` do `Paginator`) |
| Ordens de Serviço | 2.648 KB | **205 KB** | 1.814 | **135** (`NOVO-07` em aberto) |

Os catálogos (`catalog_views.py`) seguem sem paginação — fora do escopo da Etapa 1.

---

## 5. Segurança medida

### 5.1 ✅ Isolamento por área é sólido

`core/tenancy.py` implementa `filter_queryset_by_area()` com política **estrita**: sem área resolvida, o queryset filtra `area__isnull=True` — nunca devolve tudo. Aplicado **192 vezes** na camada de dados. Os `get_object_or_404` passam por querysets já filtrados (`_evento_queryset()`, `filter_queryset_by_area(...)`), fechando o vetor de IDOR por troca de ID na URL.

Complementos: `validate_cross_area_foreign_keys` impede FK cruzando áreas; `core/permissions.py` implementa RBAC ordinal (leitor 10 / editor 20 / admin 30) com `AREA_RBAC_REQUIRE_MEMBERSHIP`; middleware global de login com apenas 8 `@login_not_required` explícitos.

### 5.2 ✅ Fluxo público de assinatura é bem desenhado

Melhor do que eu esperava encontrar. `prestacoes_contas/assinatura_views.py`:

- Token armazenado **criptografado** (`EncryptedTextField`) com hash SHA-256 indexado para lookup.
- **Expiração** (`link_expira_em`) e invalidação após assinatura (`link_ativo`).
- **Rate limiting em duas dimensões**: por IP+token (`_MAX_TENTATIVAS`) e global por token (`× 4`), com IP e token digeridos por SHA-256 nas chaves de cache.
- Confirmação de identidade em sessão antes de permitir assinar.
- `hash_documento` SHA-256 do PDF assinado para verificação de integridade.

Numa banca, este fluxo é um ponto forte a exibir — não uma vulnerabilidade a defender.

### 5.3 Lacunas confirmadas (já em `AUDITORIA_BACKEND_INFRA_COMPLETA`)

Chave Fernet de dev commitada (`config/settings/dev.py:16`), sem rate limit no login administrativo, sem CSP, sem configuração de e-mail.

---

## 6. Acessibilidade medida — contraste WCAG

Calculei a razão de contraste real de 28 pares cor-texto/fundo do tema escuro. Critério: WCAG 2.1 AA (4,5:1 texto normal, 3:1 texto grande).

### 6.1 ✅ O sistema de tokens está bem calibrado — 23 de 28 aprovam

| Par | Razão | |
|---|---|---|
| texto padrão / card | **13,77** | ✅ |
| heading / card | **14,65** | ✅ |
| input text / campo | **15,07** | ✅ |
| label / card | 10,67 | ✅ |
| muted / card | 8,13 | ✅ |
| warning / card | 8,32 | ✅ |
| accent-text dourado / card | 7,30 | ✅ |
| success / card | 7,20 | ✅ |
| help / card | 6,89 | ✅ |
| placeholder / campo | 6,73 | ✅ |
| info / card | 6,47 | ✅ |
| danger / card | 5,71 | ✅ |
| subtle / card | 5,16 | ✅ |
| disabled / fundo disabled | 4,56 | ✅ (no limite) |
| sidebar, botões, chips | 6,19 – 13,56 | ✅ |

A paleta escura foi pensada. Isso também é apresentável.

### 6.2 🔴 As 5 reprovações são exatamente as que a auditoria de CSS previu

| Par | Razão | Mínimo | Onde |
|---|---|---|---|
| **`.pte-card__title`** — token `--color-text-strong` indefinido → `#0f172a` | **1,17** | 4,5 | `planos-trabalho-eventos.css:86` |
| **`.pte-card__value--valor`** — `--color-primary-strong` `#0b3a66` | **1,31** | 4,5 | `planos-trabalho-eventos.css:147` |
| `--color-primary` `#12507f` usado como texto sobre card | **1,80** | 4,5 | vários |
| **`.pte-events__banner`** — `--color-info-strong` indefinido → `#1d4ed8` | **2,27** | 4,5 | `planos-trabalho-eventos.css:17` |
| `.oficio-lc__action-menu-*-icon` — sem override no escuro | **2,96** | 4,5 | `oficios-list-header.css:128-200` |

**1,17:1 é texto praticamente invisível.** Aparece nos cards de evento do Plano de Trabalho — telas de etapa 1 e 4. Se a banca abrir essa tela no tema escuro, o defeito é imediato e não precisa de ferramenta para ser visto.

A validação cruzada importa: a auditoria de CSS deduziu esses cinco por análise estática de tokens indefinidos; a medição confirmou os cinco, com os números exatos. Nenhum falso positivo, nenhum falso negativo entre os pares testados.

---

## 7. Documentos gerados

**11 modelos DOCX** em `documentos/resources/` (ofício, justificativa, ordem de serviço, plano de trabalho simples e multievento, relatório técnico, termo de autorização em 3 variantes). Contexto montado por 1.278 linhas em três `docxtpl_context.py`.

**A saída não foi verificada por ninguém — nem por mim.** Existem testes de contexto (`test_docxtpl_diarias.py`, `test_docxtpl_nested_templates.py`, `test_facade_pdf_single_docx.py`) que validam o dicionário entregue ao template, mas **nenhum abre o arquivo produzido**. Com 5 motores de PDF e fallback automático (`DOCUMENTOS_PDF_AUTO_FALLBACK`), o mesmo ofício pode sair por WeasyPrint numa máquina e por fpdf2 em outra — e ninguém compara.

**Este é o maior risco não medido do sistema.** O produto final do sistema é o documento. Um teste de contexto prova que a variável chegou; não prova que a quebra de página está certa, que a tabela de diárias cabe, que a assinatura carimbou no lugar.

Recomendação mínima antes da banca: gerar um de cada tipo com dados realistas, conferir contra o modelo oficial do órgão, e guardar os PDFs como *golden files* de referência.

Higiene relacionada: `media/` tem **191 MB e 19.175 arquivos** de documentos gerados em desenvolvimento. Está no `.gitignore` ✅, mas sincroniza pelo OneDrive.

---

## 8. Terminologia e microcopy

| Ação | Variantes encontradas |
|---|---|
| Voltar para a lista | `Voltar` (21), `Voltar à lista` (11), **`Voltar a lista`** (1 — sem crase), `Voltar para lista` (1) |
| Voltar para etapa anterior | `Voltar ao diário` / `Voltar ao Diário de Bordo` (capitalização divergente), `Voltar ao ofício` / `Voltar aos Documentos` (sentence case × Title Case) |
| Avançar no wizard | `Salvar e avançar` (6) × `Avançar` (4) — mesma ação, wizards diferentes |
| Salvar | 17 variantes com o nome da entidade (`Salvar cargo`, `Salvar cidade`, `Salvar tipo`…) × `Salvar` genérico (6) |
| Concluir | `Finalizar Ofício` / `Finalizar plano` / `Finalizar prestação` — capitalização divergente |

Um erro de português (`Voltar a lista`) e três padrões de capitalização convivendo. Numa apresentação institucional, isso é visível para qualquer pessoa da banca, inclusive as não técnicas — e custa quase nada para corrigir.

---

## 9. Catálogo de defeitos desta auditoria

🔴 crítico · 🟠 alto · 🟡 médio

| # | Sev | Defeito | Local |
|---|---|---|---|
| N-01 | 🔴 | Tabela de diárias fixada no código, sem vigência e sem congelamento do valor no documento | `roteiros/services/diarias.py:11-27` |
| N-02 | 🔴 | ~~Lista de Ofícios e de Ordens de Serviço sem paginação — 22,1 KB de HTML por card; 300 ofícios = 6,5 MB~~ **corrigido na Etapa 1** | `oficios/views.py:460`, `ordens_servico/views.py` |
| N-03 | 🔴 | 5 pares de cor reprovam WCAG AA, sendo 3 abaixo de 2,3:1 (praticamente ilegíveis) | §6.2 |
| N-04 | 🔴 | Nenhum teste verifica o **conteúdo** do documento gerado, com 5 motores de PDF intercambiáveis | `documentos/services/` |
| N-05 | 🟠 | Duas regras de cobrança de complemento coexistem; o comentário do código condena o que o outro ramo faz | `diarias.py:279-303` × `313-351` |
| N-06 | 🟠 | `CAPITAIS_POR_UF` duplica a base geográfica IBGE — divergência silencia como cobrança a menor | `diarias.py:29-57` |
| N-07 | 🟠 | ~~Componente de paginação incluído em listas que nunca recebem `page_obj` — falha em silêncio~~ **corrigido na Etapa 1** | `list_page_cards.html:16` |
| N-08 | 🟡 | `_segment_breakdown` produz valores descartados no caminho dominante — duas definições de "diária integral" | `diarias.py:140-168` |
| N-09 | 🟡 | `valor_por_servidor × servidores` pode não fechar com `total_valor` | `diarias.py:409-415` |
| N-10 | 🟡 | Pernoite de 2 horas gera diária integral, sem teste de borda nem documentação | `diarias.py:125-133` |
| N-11 | 🟡 | 4 variantes de "Voltar à lista", incluindo erro de crase; 3 padrões de capitalização | §8 |
| N-12 | 🟡 | `media/` com 191 MB / 19.175 arquivos sincronizando pelo OneDrive | — |
| N-13 | 🟡 | `docs/REGRAS_DE_NEGOCIO.md` tem 77 linhas para um sistema de 116 models — não documenta diárias, numeração nem status | `docs/` |

**Achados novos desta auditoria, descobertos ao medir a Etapa 1** (origem: `NOVO`):

| # | Sev | Defeito | Local |
|---|---|---|---|
| NOVO-07 | 🟠 | N+1 na lista de Ordens de Serviço: ~6 queries por card (`_destinos_display_os` refaz a query e anula o `prefetch_related`; `servidores.count()` por card; `_get_assinante_os()` relê o singleton de configuração por card). A paginação limitou o dano a 135 queries por página, mas o custo por card continua | `ordens_servico/presenters.py:76,124,205` |
| NOVO-08 | 🟠 | `core/tests/` não tinha `__init__.py`: **95 testes existentes nunca rodaram** desde que a pasta foi criada — incluindo `test_tenancy_integrity`, `test_sso`, `test_uploads` e `test_dark_redesign`. Corrigido na Etapa 1 (todos passam; a suíte vai de 812 para 924) | `core/tests/__init__.py` |

---

## 10. Consolidado das quatro auditorias

| Dimensão | Estado atual | Alvo | Defeitos 🔴 |
|---|---|---|---|
| **CSS / tema escuro** | 36.771 linhas, 62 arquivos, 4 camadas de token, 18 tokens indefinidos | ~13.000 linhas, ~40 componentes | 5 |
| **HTML / JS** | 18.301 l. JS, 12 de 63 arquivos no motor global, 6 cópias do sistema de destinos | ~7.000 l., 16 motores | 5 |
| **Backend / infra** | 73.933 l., 812 testes verdes, prod endurecido | cobertura equilibrada, 8 motores | 2 |
| **Correção / desempenho / a11y** | sem N+1 ✅, tenancy sólido ✅, 2 listas sem paginação, diárias sem vigência | — | 4 |
| **Total** | **150.829 linhas** | **~110.000** | **16 críticos** |

### O que está genuinamente bom (e deve ser apresentado)

1. **812 testes verdes em 18,5 s** — suíte rápida o suficiente para rodar a cada commit.
2. **Zero N+1 medido** — a camada de selectors com `Prefetch` aninhado funciona.
3. **Isolamento multi-área estrito**, aplicado 192 vezes, sem vetor de IDOR encontrado.
4. **Fluxo de assinatura pública** com token criptografado, hash indexado, expiração e rate limit em duas dimensões.
5. **Paleta escura calibrada** — 23 de 28 pares aprovam WCAG AA, a maioria com folga.
6. **Produção endurecida** — HSTS com preload, cookies secure, logging JSON estruturado, chaves obrigatórias por ambiente, dependências pinadas com hash, `pip-audit`.
7. **Arquitetura documentada** — 10 documentos `PADRAO_*` que descrevem o contrato de camadas.
8. **Zero TODO/FIXME, zero `print()`, zero estilo inline, zero URL hardcoded.**

### Os 16 defeitos críticos, por natureza

| Natureza | Quantos | Exemplo |
|---|---|---|
| Regra de negócio / dinheiro | 1 | tabela de diárias sem vigência |
| Desempenho | 1 | listas sem paginação |
| Acessibilidade | 1 | 3 pares abaixo de 2,3:1 |
| Cobertura de teste | 2 | Prestações 0,04; documento gerado nunca aberto |
| Arquitetura JS | 3 | 51 de 63 arquivos fora do motor global |
| Arquitetura CSS | 5 | componentes globais sem cor própria |
| Segurança | 1 | chave Fernet commitada |
| Duplicação estrutural | 2 | destinos ×6, catálogo ×5 |

---

## 11. Quanto custa este sistema

Três metodologias, porque uma banca de órgão público vai reconhecer pelo menos uma delas.

### 11.1 Método A — Pontos de Função (linguagem de licitação)

Contagem estimada a partir dos artefatos reais:

| Tipo | Base | PF estimados |
|---|---|---|
| Arquivos Lógicos Internos (ALI) | ~50 agrupamentos lógicos (116 models, muitos filhos) | 400–500 |
| Arquivos de Interface Externa (AIE) | 2 integrações (Drive, ORS) + base IBGE | 20–30 |
| Entradas Externas (EE) | ~120 transações de escrita (429 rotas, descontadas variantes) | 480–600 |
| Saídas Externas (SE) | 11 documentos + relatórios + exportações | 150–200 |
| Consultas Externas (CE) | ~60 listas, filtros e APIs de leitura | 180–240 |
| **Total bruto** | | **1.230–1.570 PF** |
| Ajuste de complexidade (multi-tenant, criptografia, assinatura digital, 5 motores PDF, SSO) | ×1,15 | **1.410–1.800 PF** |

**Preço de mercado brasileiro por PF** (contratos públicos de fábrica de software, 2026):

| Faixa | R$/PF | Custo total |
|---|---|---|
| Conservadora (fábrica de baixo custo) | R$ 700 | **R$ 987 mil – R$ 1,26 mi** |
| Média de mercado | R$ 1.000 | **R$ 1,41 mi – R$ 1,80 mi** |
| Órgão federal / alta exigência | R$ 1.400 | **R$ 1,97 mi – R$ 2,52 mi** |

### 11.2 Método B — Esforço bottom-up (equipe convencional)

| Frente | Base | Dias-pessoa |
|---|---|---|
| Modelagem de dados e migrações | 116 models, 13 apps, multi-tenant | 46 |
| CRUD de catálogos | 13 catálogos | 20 |
| Listas complexas (cards, abas, filtros, autosave) | 5 | 25 |
| Wizards multi-etapa | 18 etapas em 6 fluxos | 54 |
| Motor de roteiro, diárias e rota externa | — | 25 |
| Geração de documentos (11 modelos, 5 motores) | — | 30 |
| Assinatura eletrônica (cripto, carimbo, fluxo público) | — | 25 |
| Integração Google Drive (OAuth, organizer, signals) | 4.790 l. | 30 |
| Multi-tenant + RBAC + SSO + auditoria + criptografia | — | 25 |
| Autosave e camada JS | 18.301 l. | 20 |
| Design system e CSS | 80 componentes | 40 |
| Suíte de testes | 812 testes | 41 |
| Infra, deploy, CI, Celery, observabilidade | — | 20 |
| Documentação técnica | 12.755 l. | 15 |
| **Subtotal técnico** | | **416** |
| Gestão, reuniões, retrabalho, homologação (+25%) | | 104 |
| **Total** | | **~520 dias-pessoa** |

| Composição | Valor-dia | Custo |
|---|---|---|
| Equipe interna CLT (2 plenos + 1 sênior + design/QA parcial) | R$ 650/dia efetivo | **R$ 338 mil** |
| Consultoria PJ (blended sênior/pleno) | R$ 1.000/dia | **R$ 520 mil** |
| Fábrica de software (com margem e overhead) | R$ 1.600/dia | **R$ 832 mil** |

### 11.3 Método C — Custo real incorrido

586 commits, 13/05 a 28/07/2026, ~55 dias úteis, autoria concentrada. Ou seja: **o custo real ficou próximo de 55–70 dias-pessoa** — cerca de **10× menos** que o método B.

A diferença é a alavancagem de IA no desenvolvimento. É um dado a favor, não contra, **desde que sustentado por evidência**: 812 testes verdes, arquitetura documentada, zero TODO, produção endurecida. A banca vai perguntar; a resposta é essa, com a suíte rodando na frente deles.

### 11.4 Síntese

> **Valor de reposição do sistema: R$ 500 mil a R$ 1,8 milhão**, conforme a metodologia de contratação.
> Faixa mais defensável numa banca pública: **R$ 900 mil – R$ 1,4 milhão** (≈1.500 PF × R$ 700–950).

Números de apoio para o slide: 150.829 linhas de código próprio · 116 models · 429 endpoints · 812 testes automatizados · 13 módulos · 11 modelos documentais · 2 integrações externas · construído em 2,5 meses.

---

## 12. Quanto custa deixá-lo impecável

Somando as fases das quatro auditorias:

| Frente | Escopo | Dias-pessoa |
|---|---|---|
| **Bloco 0 — Correções críticas isoladas** | 16 defeitos 🔴 sem renomeação: tokens indefinidos, paginação em Ofícios/OS, contraste, chave Fernet, `confirm()` duplo, `extra-download.js`, toast sem fundo | **8–12** |
| **Bloco 1 — Rede de segurança** | Suíte de Prestações (5 etapas + assinatura), *golden files* dos 11 documentos, `coverage` no CI | **18–24** |
| **Bloco 2 — Regra de negócio** | Tabela de diárias com vigência + congelamento no roteiro; unificar as duas regras de complemento; documentar em `REGRAS_DE_NEGOCIO.md`; constraints em roteiros/termos | **15–20** |
| **Bloco 3 — Motores JS** | 16 motores globais, contrato único de `data-*`, `CV.registry.destroy`, eliminar as 6 cópias do sistema de destinos | **30–40** |
| **Bloco 4 — Reconstrução CSS** | 4 camadas de token → 1, dissolver `dark-redesign.css`, renomear `oficio-lc` → `cv-record-card`, 40 componentes, escala de breakpoints | **35–45** |
| **Bloco 5 — Estrutura HTML** | `flow_base` de wizard, card mestre como componente, `form_block` com contexto selado, semântica e ARIA | **20–25** |
| **Bloco 6 — Backend** | Selectors nos 4 apps, `core/catalog.py`, widget base com classes canônicas, `core/errors.py` | **25–30** |
| **Bloco 7 — Higiene e polimento** | Repositório, docs históricos, microcopy, ícones, rate limit, e-mail, CSP | **10–14** |
| **Total** | | **161–210 dias-pessoa** |

| Cenário | Prazo | Custo (R$ 1.000/dia-pessoa) |
|---|---|---|
| Solo, dedicação integral | 8–10 meses | — |
| Solo com alavancagem de IA (ritmo já demonstrado) | **2,5–3,5 meses** | — |
| 2 desenvolvedores | 4–5 meses | **R$ 161 mil – R$ 210 mil** |
| 3 desenvolvedores + design | 3 meses | **R$ 180 mil – R$ 230 mil** |

**Proporção que vale citar:** o refactor completo custa entre **12% e 23%** do valor de reposição do sistema. Para uma dívida técnica desse porte, é uma proporção saudável — dívida técnica acima de 30% do valor do ativo costuma indicar que reescrever sai mais barato que corrigir. Não é o caso aqui.

---

## 13. Roteiro para a banca técnica

### 13.1 Ordem obrigatória

**Bloco 0 e Bloco 1 antes de qualquer refactor.** Não porque são mais importantes, mas porque:

- O Bloco 0 são 16 correções isoladas que **não dependem de renomear nada** — se a apresentação antecipar, você para aqui e o sistema está apresentável.
- O Bloco 1 é a rede que impede o refactor de quebrar o que funciona. Refatorar 40.000 linhas de CSS com Prestações a 0,04 de cobertura e documentos nunca verificados é o cenário em que o sistema chega pior à banca do que está hoje.

Blocos 2 a 7 podem ser reordenados conforme o calendário. O Bloco 4 (CSS) é o mais longo e o mais visível — mas também o mais reversível, porque a suíte não depende de nome de classe.

### 13.2 O que a banca vai perguntar, e a resposta

| Pergunta provável | Resposta hoje |
|---|---|
| "Tem N+1 nas listas?" | ✅ Não — medido: 16 queries fixas para 1 ou 20 registros |
| "Como isola dados entre áreas?" | ✅ `filter_queryset_by_area` estrito, 192 aplicações, sem IDOR |
| "Como protege o link público de assinatura?" | ✅ Token criptografado + hash indexado + expiração + rate limit duplo |
| "Qual a cobertura de testes?" | ⚠️ 812 testes verdes, mas assimétrica — Prestações a 0,04 |
| **"E quando o valor da diária mudar?"** | ❌ **Hoje exige deploy e recalcula o histórico** |
| **"A lista aguenta 500 ofícios?"** | ❌ **Não pagina — 11 MB de HTML** |
| "Atende acessibilidade?" | ⚠️ 23 de 28 pares aprovam AA; 3 abaixo de 2,3:1 |
| "O documento gerado confere?" | ❌ **Nenhum teste abre o arquivo produzido** |
| "Quanto custaria contratar isso?" | ✅ R$ 900 mil – R$ 1,4 mi (≈1.500 PF) |

As quatro respostas negativas estão todas nos Blocos 0, 1 e 2 — **entre 41 e 56 dias-pessoa**. É o mínimo para a banca não encontrar nenhuma resposta ruim.

### 13.3 Uma recomendação sobre postura

O sistema tem qualidades reais e mensuráveis — ausência de N+1, isolamento multi-área, assinatura pública bem projetada, suíte rápida, produção endurecida. E tem dívida real e mensurável — 4 camadas de token, 51 arquivos JS fora do motor global, regra financeira fixada no código.

Apresentar as duas listas, com número em cada linha, é mais forte do que apresentar só a primeira. Uma banca técnica desconfia de sistema sem defeito conhecido; ela avalia bem quem sabe exatamente onde estão os seus. As quatro auditorias existem justamente para isso — são a evidência de que o sistema é conhecido pelo autor, não apenas escrito por ele.
