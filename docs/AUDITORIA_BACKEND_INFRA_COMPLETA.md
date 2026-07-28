# Auditoria completa — Backend, Infraestrutura e o que restou

**Escopo:** tudo que as duas auditorias anteriores não cobriram — camada Python inteira (views, models, forms, services, selectors, presenters), settings e segurança, testes, migrações, dependências, geração de documentos, integrações, Celery, deploy/CI, higiene de repositório, e os restos de frontend (breakpoints responsivos, sistema de ícones, templates de PDF, docs).
**Companheiros:** [`AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md`](AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md) (CSS/tema) · [`AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md`](AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md) (estrutura/JS).
**Este documento não altera código.**

---

## Índice

1. [Método e números do sistema](#1-método-e-números)
2. [O padrão de referência — arquitetura declarada vs praticada](#2-o-padrão-de-referência)
3. [Diagnóstico por camada Python](#3-diagnóstico-por-camada-python)
4. [Settings, segurança e infraestrutura](#4-settings-segurança-e-infraestrutura)
5. [Testes](#5-testes)
6. [Geração de documentos e integrações](#6-geração-de-documentos-e-integrações)
7. [Restos de frontend: breakpoints, ícones, PDFs](#7-restos-de-frontend)
8. [Higiene de repositório e documentação](#8-higiene-de-repositório-e-documentação)
9. [Catálogo de defeitos](#9-catálogo-de-defeitos)
10. [Auditoria app por app](#10-auditoria-app-por-app)
11. [Motores globais de backend propostos](#11-motores-globais-de-backend-propostos)
12. [Ordem de execução sugerida](#12-ordem-de-execução-sugerida)

---

## 1. Método e números

### 1.1 Como foi feito

- Inventário de **~55.000 linhas de Python** em 13 apps (excluídos `migrations/`, `tests/`, `.venv`, `legacy/`).
- Classificação por camada (views/models/forms/services/selectors/presenters) e verificação de aderência aos `docs/PADRAO_*.md` que o próprio projeto define.
- **Execução da suíte completa de testes** (não só leitura).
- Varredura de: `except Exception` genérico, ORM em views, constraints/indexes por model, decorators de autorização, secrets no repositório, configuração por ambiente.
- Censo de breakpoints CSS, ícones definidos × usados, arquivos versionados indevidamente, CI.

### 1.2 Números que definem o sistema

| Métrica | Valor | Leitura |
|---|---|---|
| Python de produção | **~55.000 linhas** / 13 apps | — |
| Views | 9.317 linhas em 15 arquivos | 2 monólitos >1.100 linhas |
| Services | 5.218 | camada existe e é usada ✅ |
| Forms | 4.722 | 194 `attrs={...}` com classes CSS em Python |
| Models | 4.239 | 3 apps com **zero** constraint/index |
| Presenters | 3.485 | padrão próprio, bem estabelecido ✅ |
| Selectors | **990** | camada declarada em doc, presente em só 6 de 13 apps |
| **Testes: 812, todos passando, 18,5s** | ✅ | cobertura fortemente assimétrica |
| Linhas de teste | 16.219 | prestações: 351 linhas de teste para 8.238 de código |
| Migrações | 138 | prestações 29, cadastros 23 |
| `except Exception`/`except:` | **155** | 57 só em `integracoes/google_drive` |
| `TODO/FIXME/HACK` no código próprio | **0** | ✅ notável |
| `print()` em produção | **0** | ✅ |
| Breakpoints CSS distintos | **35** (98px–1480px) | não existe escala |
| Ícones: definidos × usados | 44 × 27 | 3 famílias duplicadas |
| CI | ✅ `tests.yml` + `deploy.yml` | existe |
| Config de e-mail | **inexistente** | nenhum `EMAIL_*` em settings |
| Rate limiting / lockout de login | **inexistente** | — |
| Screenshots versionados no git | **130 arquivos** | + `tmp/` 21, `logs/` 2, `migration_backups/` 2 |

---

## 2. O padrão de referência

O projeto **documenta a própria arquitetura** em `docs/PADRAO_APP.md`, `PADRAO_VIEWS.md`, `PADRAO_SERVICES.md`, `PADRAO_SELECTORS.md`, `PADRAO_PRESENTERS.md`, `PADRAO_MODELS.md`, `PADRAO_FORMS.md`, `PADRAO_CRUD.md`. O contrato declarado:

```
urls → views (finas, sem ORM direto)
         ├── selectors  (leitura: querysets nomeados, select_related)
         ├── services   (escrita: transaction.atomic, regras de negócio)
         ├── forms      (validação)
         └── presenters (dict pronto para o template — nada de lógica no template)
core/ → infraestrutura compartilhada (tenancy, permissions, autosave, entity_cards, navigation)
```

**Onde o padrão é seguido de verdade** (referência interna): `oficios` (selectors ✅, services ✅, presenters 1.051 l.), `cadastros` (0 ORM em views), `justificativas` (0 ORM em views), `roteiros` (services divididos em submódulos), `prestacoes_contas` (selectors ✅).

**A infraestrutura de `core/` é enxuta e bem dimensionada** (996 linhas para middleware + tenancy + permissions + audit + autosave + entity_cards + navigation + private_media + uploads) — este é o modelo a preservar.

---

## 3. Diagnóstico por camada Python

### 3.1 Views — dois monólitos e uma camada fantasma

| Arquivo | Linhas | Defs | ORM direto |
|---|---|---|---|
| `planos_trabalho/views.py` | **1.235** | 46 | 5 |
| `oficios/views.py` | **1.170** | 37 | 3 |
| `cadastros/views.py` | 820 | 33 | 0 ✅ |
| `roteiros/views.py` | 713 | 18 | 1 |
| `prestacoes_contas/views.py` | 649 | 16 | 2 |
| `eventos/views.py` | 637 | 24 | **17** |
| `termos/views.py` | — | — | 7 |
| `ordens_servico/views.py` | — | — | 7 |

**Selectors existem em 6 apps** (`cadastros`, `documentos`, `justificativas`, `oficios`, `prestacoes_contas`, `roteiros`) **e faltam exatamente nos apps que mais fazem ORM na view**: `eventos` (17 chamadas), `termos` (7), `ordens_servico` (7), `planos_trabalho` (5). O padrão existe, está documentado, e a metade nova do sistema o ignora.

### 3.2 O CRUD de catálogo está quintuplicado

O fluxo "lista + quick add + editar + definir padrão + excluir" (modelos de motivo, tipos de evento, programas, horários, atividades, presets, modelos de justificativa, modelos de texto, estados, cargos, combustíveis, unidades, cidades) está reimplementado em **5 arquivos**:

- `cadastros/views.py` (820 l., 33 defs — 6 catálogos)
- `oficios/catalog_views.py`
- `eventos/views.py` (tipos)
- `justificativas/views.py`
- `planos_trabalho/catalog_views.py` (4 catálogos)

Cada um repete: montar `quick_add_form`, tratar POST create/edit, validar vínculos antes de excluir, redirecionar com `next`. É o análogo backend do problema Quick Add do JS (auditoria anterior, J-04): **um motor, cinco cópias**. Candidato nº 1 a fábrica genérica (`core/catalog.py` — uma `CatalogConfig` por catálogo).

### 3.3 Models — três apps sem uma única constraint

| App | Constraints | Indexes | Risco |
|---|---|---|---|
| cadastros | 23 | 5 | ✅ |
| planos_trabalho | 14 | 8 | ✅ |
| oficios | 8 | 6 | ✅ |
| eventos | 6 | 3 | ✅ |
| **roteiros** | **0** | **0** | Roteiro/Trecho sem unicidade nem índice — e é a entidade mais consultada do sistema (toda lista carrega trechos) |
| **termos** | **0** | 0 | — |
| **justificativas** | **0** | 0 | — |
| core | 0 | 5 | 3 models **sem `__str__`** |

A memória do projeto registra o sintoma disso: "roteiro duplicado sobrescreve" — deduplicação feita em código de aplicação porque o banco não tem constraint de unicidade.

### 3.4 Forms — 194 `attrs={...}` com classes CSS em Python

Todos os 9 `forms.py` embutem classe CSS e placeholder no widget (`planos_trabalho/forms.py` sozinho tem 48). Consequência direta para a reconstrução do CSS: **renomear uma classe de campo exige tocar 9 arquivos Python**. O contrato de classes de campo (`form-control`, `cv-field__control`, `cv-search-picker__native`…) precisa viver num único lugar (widget base próprio ou o `field.html`), não espalhado em Python.

### 3.5 Tratamento de erro — 155 `except Exception`

Concentração: `integracoes/google_drive` (**57** entre organizer/views/signals/services/status), `prestacoes_contas/services.py` (7), adapters de PDF (11). Para uma integração externa, engolir exceção é às vezes correto — mas 57 no mesmo pacote sem canal de observabilidade padronizado significa que falha de upload/organização de Drive é invisível. `core/logging.py` (JSON estruturado) existe e é usado no prod — os `except` deveriam todos logar por ele.

### 3.6 Autorização — modelo global correto, exceções pontuais

O design é bom: `AjaxAwareLoginRequiredMiddleware` global + `AreaRoleRequiredMiddleware` (área/tenancy) + apenas 8 `@login_not_required` explícitos (fluxo público de assinatura). Só 2 `@login_required` manuais restantes. 46 `@require_POST` ✅.

O que **não** existe: rate limiting no login, lockout por tentativas, e qualquer configuração de e-mail (logo, nenhum fluxo de redefinição de senha possível).

---

## 4. Settings, segurança e infraestrutura

### 4.1 O que está bem (e deve ser preservado)

- Split `base/dev/prod/test` limpo; `prod.py` **exige** `SECRET_KEY`, `FIELD_ENCRYPTION_KEYS` e vars de banco via ambiente (falha cedo).
- Prod: HSTS 1 ano + preload, `SECURE_SSL_REDIRECT`, cookies secure, `SECURE_PROXY_SSL_HEADER` documentado com o porquê, WhiteNoise manifest, logging JSON estruturado com request-context.
- `.env` real **ignorado pelo git** ✅; apenas `.env.*.example` versionados ✅.
- Dependências **pinadas com `lock.txt` + hashes** e `pip-audit` no dev ✅ — acima da média.
- `/health` e `/metrics` com `METRICS_TOKEN`.
- Senha mínima de 12 caracteres; sessão de 8h com expiração no fechamento.
- Campos criptografados (`core/db_fields.py` + `FIELD_ENCRYPTION_KEYS`); antivírus opcional em upload no prod.
- Suporte a SSO via RemoteUser com exigência de MFA por header.

### 4.2 Lacunas

| # | Item | Detalhe |
|---|---|---|
| S-01 🔴 | **Chave Fernet de dev commitada** | `config/settings/dev.py:16-18` embute uma `FIELD_ENCRYPTION_KEYS` literal no repositório. É "só dev", mas é uma chave real no histórico do git — qualquer dado já criptografado com ela (bancos de teste compartilhados, dumps) é decifrável por quem tem o repo. Trocar por geração local/obrigatória no `.env`. |
| S-02 🟠 | **Zero configuração de e-mail** | Nenhum `EMAIL_*` em nenhum settings. Sem reset de senha, sem alerta de erro (`ADMINS`/`mail_admins`), sem notificação. |
| S-03 🟠 | **Sem rate limit / lockout** | Login aceita tentativas ilimitadas. Para sistema institucional exposto, `django-axes` ou equivalente é o mínimo. |
| S-04 🟠 | **Sem CSP** | `SecurityHeadersMiddleware` existe (`core/middleware.py`), mas não emite `Content-Security-Policy`. Relevante porque o roteiro carrega Leaflet de `unpkg.com` (auditoria JS, J-22). |
| S-05 🟡 | `SECRET_KEY` com default `"dev-insecure-key"` no `base.py` | Mitigado pelo prod exigir env — mas o default deveria não existir (falhar em qualquer ambiente sem chave). |
| S-06 🟡 | Celery configurado (`config/celery.py` + redis) mas **um único consumidor** (`google_drive/tasks.py`, 196 l.) | Toda a geração de PDF/DOCX é síncrona no request. As telas de "Gerando documento…" (toast do JS) existem exatamente porque o request bloqueia. |
| S-07 🟡 | `LOGIN_ENFORCED=false` como default de dev | Correto para agentes/testes, mas vale um banner visual no dev para nunca confundir com prod. |

---

## 5. Testes

### 5.1 Estado real

**812 testes, todos passando, 18,5s** (rodado nesta auditoria com `config.settings.test`). Suíte rápida e verde — excelente base para a reconstrução visual/estrutural planejada.

### 5.2 A cobertura é fortemente assimétrica

| App | Código (l.) | Teste (l.) | Razão teste/código |
|---|---|---|---|
| documentos | 4.619 | 1.980 | 0,43 ✅ |
| oficios | 6.434 | 3.308 | 0,51 ✅ |
| core | 3.516 | 1.723 | 0,49 ✅ |
| roteiros | 8.197 | 2.728 | 0,33 |
| termos | 2.294 | 818 | 0,36 |
| usuarios | 515 | 601 | 1,17 ✅ |
| justificativas | 984 | 391 | 0,40 |
| integracoes | 4.790 | 1.600 | 0,33 |
| cadastros | 5.894 | 969 | 0,16 ⚠️ |
| planos_trabalho | 5.379 | 909 | 0,17 ⚠️ |
| eventos | 2.485 | 482 | 0,19 ⚠️ |
| ordens_servico | 2.053 | 359 | 0,17 ⚠️ |
| **prestacoes_contas** | **8.238** | **351** | **0,04** 🔴 |

**Prestações de Contas é o segundo maior app do sistema e o menos testado** — justamente o fluxo com assinatura pública, dinheiro (diárias), prazos e cinco etapas de wizard.

### 5.3 O que não existe

- **Nenhum teste de JS** (0 arquivos). Os 16 motores propostos na auditoria JS nascerão sem rede.
- **T-03 remediado:** o CI mede a suíte completa com `coverage`, publica o percentual
  ordenado dos apps locais e bloqueia regressões contra pisos versionados por app.
- Os 3 scripts de auditoria em `scripts/` (`audit_django_architecture.py`, `audit_frontend_standards.py`, `audit_ui_patterns.py`) **não rodam no CI** — são manuais.

---

## 6. Geração de documentos e integrações

### 6.1 Documentos: 5 motores de PDF empilhados

`documentos/services/` (facade 370 l. + pdf_engine 356 + adapters):

1. **WeasyPrint** (HTML→PDF)
2. **LibreOffice/unoserver** (DOCX→PDF, com docker-compose dedicado)
3. **Word COM** (Windows)
4. **fpdf2** (fallback mínimo)
5. **reportlab+pypdf** (carimbo de assinatura)

A cadeia de fallback é configurável por env (`DOCUMENTOS_SIMPLE_PDF_FALLBACK`, `DOCUMENTOS_PDF_AUTO_FALLBACK`) e tem comando de diagnóstico (`documentos_check`, `documentos_unoserver_check`) ✅. O custo: **o mesmo documento pode sair visualmente diferente conforme o motor que respondeu**, e nada testa a paridade visual entre motores. Decisão pendente: eleger 1 motor canônico por formato e tratar os demais como emergência explícita (com aviso no documento gerado).

### 6.2 Google Drive: o pacote mais frágil do sistema

`integracoes/google_drive` = 4.790 linhas, das quais `organizer.py` sozinho tem **1.181** — e o pacote concentra **57 dos 155 `except Exception`** do sistema. Já produziu os bugs registrados na memória do projeto (pasta órfã por resolução via nome). É o candidato óbvio a: (a) logging estruturado obrigatório em todo `except`; (b) fila de reprocessamento visível (o modelo `DriveArquivo` já guarda estado — falta a tela de pendências ser o canal único); (c) testes de contrato para `organizer.py`.

### 6.3 eProtocolo

Pacote `integracoes/eprotocolo` em modo mock sem credenciais (conforme memória do projeto) — fora do caminho crítico, sem achados.

---

## 7. Restos de frontend

### 7.1 Breakpoints: 35 valores distintos, nenhuma escala

174 `@media` usando **35 larguras diferentes**: 98, 360, 420, 479, 480, 520, 540, 560, 599, 600, 620, 640, 680, 700, 720, 721, 760, 767, 768, 799, 820, 840, 841, 860, 900, 920, 960, 980, 1024, 1080, 1100, 1180, 1181, 1400, 1480px.

Pares off-by-one (`720/721`, `840/841`, `1180/1181`, `767/768`, `599/600`, `479/480`) indicam min/max escritos à mão sem convenção. A reconstrução do CSS (auditoria 1) deve fixar **5–6 tokens de breakpoint** (`--bp-sm/md/lg/xl…`) e proibir literal — hoje seria impossível, porque `@media` não aceita `var()`; a solução é convenção documentada + teste de CI que rejeita valores fora da lista.

### 7.2 Ícones: template de 208 linhas com 3 famílias duplicadas

`components/ui/icons/icon.html` é um `{% if icon == "..." %}` gigante: **44 ícones definidos, 27 usados**. Duplicações semânticas: `pen`/`pencil`/`edit`, `copy`/`copy-modern`/`clipboard-copy`, `whatsapp`/`whatsapp-modern`/`whatsapp-business`, `delete`/`trash`. Nunca usados em produção: `calculator`, `clipboard-copy`, `copy`, `link`, `pen`, `pencil`, `preview`, `settings`\*, `signature`, `trash`, `whatsapp`, `arrow-right`\* (\*usados só via variável). Proposta: sprite SVG único (`<use href="#icon-x">`) + apagar os 17 órfãos + 1 nome por conceito.

### 7.3 Templates de PDF: limpos ✅

`templates/documentos/pdf/*` (312 linhas, zero `<style>` inline, CSS de impressão separado). Única ressalva: as classes `termo-*`/`doc-*` usadas nos previews HTML não existem no bundle da aplicação (registrado na auditoria 1, Anexo B).

---

## 8. Higiene de repositório e documentação

### 8.1 Arquivos que não deveriam estar no git

| Pasta | Versionados | Ação |
|---|---|---|
| `screenshots/` | **130 arquivos** | mover para artefato de CI ou apagar |
| `tmp/` | 21 | gitignore + limpar |
| `media_teste/` | 6 | fixtures pertencem a `*/tests/fixtures/` |
| `logs/` | 2 | gitignore |
| `migration_backups/` | 2 | apagar (o git é o backup) |
| `legacy/` (CV 2.0 inteiro) | 0 versionados, mas **presente no working tree** | mover para fora do projeto (polui buscas, IDE, e o OneDrive sincroniza tudo) |

### 8.2 Documentação: 75 arquivos, duas populações

- **Duráveis** (manter e cobrar aderência): a série `PADRAO_*` (10 docs), `ARQUITETURA.md`, `DESIGN_SYSTEM.md`, `ui-components.md`, `autosave.md`, `AMBIENTES.md`, `DEPLOY_VPS.md`.
- **Fotografias datadas** (20+ `RELATORIO_*`, `AUDITORIA_*` antigas, `*_PLANO.md` já executados, `LEGACY_*_MAP.md`): mover para `docs/historico/` — hoje competem nas buscas com os docs vivos e várias descrevem estados que não existem mais.

### 8.3 O projeto vive dentro do OneDrive

`C:\Users\tiago\OneDrive\...` — a memória do projeto já registra o pip travando por causa disso. OneDrive sincroniza `.venv`, `staticfiles/`, `node_modules`-likes e o `legacy/` inteiro a cada build. Recomendação: mover o repositório para fora do OneDrive (o remoto git já é o backup) ou, no mínimo, marcar `.venv/`, `staticfiles/`, `tmp/`, `legacy/` como "sempre local".

---

## 9. Catálogo de defeitos

🔴 crítico · 🟠 alto · 🟡 médio

| # | Sev | Defeito | Local |
|---|---|---|---|
| P-01 | 🟠 | Selectors ausentes nos 4 apps com mais ORM em view (eventos 17×, termos 7×, OS 7×, PT 5×) | §3.1 |
| P-02 | 🟠 | CRUD de catálogo reimplementado em 5 arquivos | §3.2 |
| P-03 | 🟠 | `roteiros`, `termos`, `justificativas` com **0 constraints e 0 indexes**; dedupe de roteiro feito em aplicação | §3.3 |
| P-04 | 🟠 | 194 `attrs={...}` com classes CSS dentro de `forms.py` — acopla a reconstrução do CSS ao Python | §3.4 |
| P-05 | 🟠 | 155 `except Exception`, 57 no Google Drive, sem logging obrigatório | §3.5 |
| P-06 | 🟡 | `planos_trabalho/views.py` (1.235 l.) e `oficios/views.py` (1.170 l.) monolíticos | §3.1 |
| P-07 | 🟡 | `core/models.py`: 3 models sem `__str__` | §3.3 |
| P-08 | 🟡 | `diario_bordo` é um app-casca (1 URL, 1 placeholder, 0 models) — decidir: implementar ou remover | — |
| S-01 | 🔴 | Chave Fernet literal commitada em `dev.py` | §4.2 |
| S-02 | 🟠 | Zero configuração de e-mail (sem reset de senha, sem alerta de erro) | §4.2 |
| S-03 | 🟠 | Sem rate limit/lockout no login | §4.2 |
| S-04 | 🟠 | Sem Content-Security-Policy (agrava CDN externa do Leaflet) | §4.2 |
| S-05 | 🟡 | `SECRET_KEY` com default inseguro no `base.py` | §4.2 |
| S-06 | 🟡 | Celery ocioso: geração de documento é síncrona no request | §4.2 |
| T-01 | 🔴 | Prestações de Contas: razão teste/código 0,04 (351 l. para 8.238) no fluxo com assinatura pública e dinheiro. Fatia 1/6 concluída: listagem e entrada caracterizadas | §5.2 |
| T-02 | 🟠 | Zero testes de JS | §5.3 |
| T-03 | ✅ | `coverage` no CI com relatório e piso versionado por app | §5.3 |
| T-04 | ✅ | O `coverage run` do CI encerrava antes dos testes: comentários dentro da continuação de linha (`\`) faziam o `#` comentar o resto do comando, levando junto o `--omit` e o `manage.py test`. Introduzido no PR #73, **corrigido no #75** | NOVO |
| NOVO-09 | 🟠 | O número de solicitação tem dois caminhos de gravação que divergem: o autosave (com JS) marca o servidor como `em_preenchimento` e recusa data inválida com mensagem; o lote (`action=save_solicitacoes`, o *fallback* sem JS) não marca o status e engole a data inválida em silêncio, preservando a anterior. O estado do registro passa a depender de o navegador ter JavaScript | NOVO |
| D-01 | 🟡 | 5 motores de PDF sem teste de paridade visual entre eles | §6.1 |
| D-02 | 🟠 | `organizer.py` (1.181 l., 19 `except Exception`) sem testes de contrato | §6.2 |
| R-01 | 🟠 | 35 breakpoints distintos, com 6 pares off-by-one | §7.1 |
| R-02 | 🟡 | Sistema de ícones: 208 linhas de if/elif, 17 órfãos, 3 famílias duplicadas | §7.2 |
| G-01 | 🟡 | 161 arquivos indevidos no git (screenshots, tmp, logs, backups) | §8.1 |
| G-02 | 🟡 | 20+ docs datados competindo com os duráveis | §8.2 |
| G-03 | 🟠 | Repositório dentro do OneDrive (pip trava; sync de `.venv`/`legacy`) | §8.3 |

---

## 10. Auditoria app por app

| App | Código | Aderência ao PADRAO_APP | Principais achados |
|---|---|---|---|
| **core** | 3.516 | ✅ é o padrão | Infra enxuta (996 l. somados). 3 models sem `__str__`. `SecurityHeadersMiddleware` sem CSP. |
| **cadastros** | 5.894 | ✅ views sem ORM | 6 catálogos com CRUD repetido (P-02). 23 constraints ✅. Testes 0,16 ⚠️. |
| **oficios** | 6.434 | ✅ referência | `views.py` 1.170 l. (P-06); `presenters.py` 1.051 l. — dividir por tela. Melhor suíte do sistema (3.308 l.). |
| **eventos** | 2.485 | ❌ pior aderência | **17 ORM em views, sem selectors** (P-01). Testes 0,19. |
| **roteiros** | 8.197 | ⚠️ services ✅, models ❌ | Maior app. **0 constraints/0 indexes** (P-03). Services bem divididos (`roteiro_editor`, `routing/`). |
| **termos** | 2.294 | ⚠️ | 7 ORM em views, sem selectors; 0 constraints. |
| **ordens_servico** | 2.053 | ⚠️ | 7 ORM em views, sem selectors. Testes 0,17. |
| **planos_trabalho** | 5.379 | ⚠️ | `views.py` 1.235 l. (maior do sistema); sem selectors; 14 constraints ✅. Testes 0,17. |
| **prestacoes_contas** | 8.238 | ⚠️ selectors ✅ | **Testes 0,04 (T-01)** — o gap mais perigoso do sistema. 29 migrações. |
| **justificativas** | 984 | ✅ | 0 constraints (baixo risco — catálogo). |
| **documentos** | 4.619 | ✅ | 5 motores PDF (D-01); melhor razão de testes (0,43). |
| **usuarios** | 515 | ✅ | Testes 1,17 ✅. |
| **integracoes** | 4.790 | ❌ | 57 `except Exception` (P-05, D-02). |
| **diario_bordo** | ~0 | — | App-casca (P-08). |

---

## 11. Motores globais de backend propostos

Espelho dos "motores globais" do JS — um dono por capacidade:

| # | Motor | Substitui | Ganho estimado |
|---|---|---|---|
| 1 | **`core/catalog.py`** — fábrica de CRUD de catálogo (`CatalogConfig`: model, form, campos do quick add, regra de exclusão) | 5 implementações (§3.2) | ~1.500 → ~400 linhas; novos catálogos em ~20 linhas |
| 2 | **Selectors obrigatórios** — criar `eventos/selectors.py`, `termos/selectors.py`, `ordens_servico/selectors.py`, `planos_trabalho/selectors.py` e migrar as 36 chamadas ORM | P-01 | teste de CI: `grep .objects` proibido em `views.py` |
| 3 | **Widget base próprio** (`core/forms.py`) que injeta as classes CSS canônicas — `forms.py` dos apps param de conhecer CSS | 194 `attrs` (P-04) | desacopla a reconstrução visual do Python |
| 4 | **`core/errors.py`** — `capture(exc, contexto)` que loga estruturado; proibir `except Exception` sem `capture` via CI | 155 ocorrências (P-05) | Drive deixa de falhar em silêncio |
| 5 | **Geração assíncrona de documentos** — mover `facade.gerar_*` para task Celery com polling (o toast JS já existe) | S-06 | request nunca bloqueia em LibreOffice |
| 6 | **Constraints de dados** — migração única: unicidade de Roteiro (hash do conteúdo), índices de FK quentes em trechos, `__str__` nos models de core | P-03, P-07 | dedupe sai do código de aplicação |
| 7 | **Escala de breakpoints** — 6 valores documentados + teste de CI que rejeita `@media` fora da lista | R-01 | pré-requisito da reconstrução CSS |
| 8 | **Sprite de ícones** — 1 SVG, 27 símbolos, 1 nome por conceito | R-02 | −208 linhas de if/elif |

---

## 12. Ordem de execução sugerida

| Fase | Ação | Resolve | Risco |
|---|---|---|---|
| **0** | Rotacionar a chave Fernet de dev (gerar local, exigir no `.env`); confirmar que nenhum dado real usou a chave commitada | S-01 | zero |
| **1** | Higiene de repo: gitignore + remover screenshots/tmp/logs/backups; mover `legacy/` para fora; mover docs datados para `docs/historico/` | G-01, G-02 | zero |
| **2** | Adicionar `coverage` ao `tests.yml` com piso por app; escrever a suíte de Prestações (fluxo feliz das 5 etapas + assinatura pública) **antes** de qualquer refatoração visual dessas telas | T-01, T-03 | zero |
| **3** | `core/errors.py` + varrer os 57 `except` do Drive | P-05, D-02 | baixo |
| **4** | Selectors nos 4 apps faltantes + teste de CI anti-ORM-em-view | P-01 | baixo |
| **5** | Migração de constraints/indexes (roteiros, termos) | P-03 | médio (validar dados existentes antes) |
| **6** | `core/catalog.py` e migrar os 13 catálogos | P-02 | baixo (suíte cobre catálogos de oficios/justificativas) |
| **7** | Widget base com classes canônicas — **pré-requisito do dicionário de renomeação da auditoria CSS** | P-04 | baixo |
| **8** | Escala de breakpoints + sprite de ícones — junto com a reconstrução CSS já planejada | R-01, R-02 | baixo |
| **9** | Rate limit no login (`django-axes`), e-mail (`ADMINS` + backend SMTP), CSP no `SecurityHeadersMiddleware` | S-02..04 | baixo |
| **10** | Fatiar `planos_trabalho/views.py` e `oficios/views.py` por tela (wizard_*/catalog_*/api_*) | P-06 | baixo |
| **11** | Documentos assíncronos via Celery (o toast já dá a UX) | S-06 | médio |
| **12** | Decidir `diario_bordo` (implementar ou remover) e eleger motor de PDF canônico por formato | P-08, D-01 | decisão de produto |

**Encadeamento com as outras auditorias:** Fase 2 (testes de Prestações) e Fase 7 (widget base) são pré-requisitos diretos da reconstrução CSS/HTML; Fase 4 (selectors) e Fase 6 (catálogo) são independentes e podem correr em paralelo. O restante não bloqueia nada.

---

## Anexo A — Síntese das três auditorias

| Dimensão | Documento | Estado | Nº alvo |
|---|---|---|---|
| CSS / tema escuro | `AUDITORIA_VISUAL_DARK_PAGINA_A_PAGINA.md` | 36.771 linhas, 62 arquivos, 4 camadas de token | ~13.000 linhas, ~40 componentes |
| HTML / JS | `AUDITORIA_HTML_JS_PAGINA_A_PAGINA.md` | 18.301 linhas JS, 12/63 no motor global | ~7.000 linhas, 16 motores |
| Backend / infra | este documento | ~55.000 linhas, 812 testes ✅ | 8 motores backend, cobertura equilibrada |

O backend é a camada mais saudável das três: arquitetura documentada, suíte verde e rápida, deps pinadas, prod endurecido. Os problemas são de **disciplina de aderência** (selectors, catálogo, constraints) e **assimetria de testes** — não de fundação. A ordem certa continua sendo: travar regressão com testes (Prestações), depois reconstruir o visual em cima da suíte verde.
