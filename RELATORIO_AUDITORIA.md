# Relatório de Auditoria Técnica — Gerenciador de Viagens

**Data:** 2026-06-26
**Escopo:** Revisão completa do sistema (configuração, segurança, arquitetura, qualidade de código, higiene do repositório, testes e CI/CD).
**Stack:** Django 5.2 · PostgreSQL · WeasyPrint/LibreOffice (DOCX→PDF) · pyHanko (assinatura) · integração eProtocolo-PR.

> Modelo usado nesta auditoria: Opus 4.8 (claude-opus-4-8) — já é o modelo mais capaz disponível; não há um "modo turbo" adicional a ativar além do que já está em uso.

---

## 1. Sumário executivo

O projeto é **maduro e bem organizado** para o seu tamanho (~55 mil linhas de Python, 17 apps Django, 320 templates, 69 arquivos de teste). A separação em camadas (`services` / `selectors` / `presenters` / `forms`) é consistente entre os apps, há cuidado real com performance de banco (184 usos de `select_related`/`prefetch_related`) e com segredos (`.env` **não** está versionado; o client eProtocolo cai em *mock* sem credenciais).

Os problemas mais relevantes **não estão na lógica de negócio**, e sim em **configuração de segurança**, **pipeline de deploy** e **higiene do repositório**. Nada bloqueia o funcionamento, mas há riscos concretos de produção que valem correção rápida.

| Severidade | Qtd. | Resumo |
|---|---|---|
| 🔴 Alto | 4 | Validadores de senha ausentes; inconsistência de path no deploy; CI roda só ~13% dos testes; hardening HTTPS incompleto em produção |
| 🟠 Médio | 5 | Tratamento de exceções amplo; logging frágil em prod; lixo versionado no repo; arquivos muito grandes; config de negócio no código |
| 🟡 Baixo | 4 | `.env` de exemplo redundantes; `load_dotenv` duplicado; `ALLOWED_HOSTS=*` no `.env`; duplicação de bloco DATABASES |

---

## 2. Pontos fortes (o que está bem feito)

- **Arquitetura em camadas consistente.** Cada app separa `views.py` (orquestração HTTP) de `services.py` (regras), `selectors.py` (leitura) e `presenters.py` (montagem de contexto). Isso é raro de ver mantido em 17 apps.
- **Segredos fora do versionamento.** `.env` está no `.gitignore` e **não** aparece em `git ls-files`. Apenas os `.env*.example` (sem segredos) estão versionados.
- **Integração externa defensiva.** O eProtocolo opera 100% em *mock* sem credenciais — o sistema "nunca quebra por ausência de configuração". Flags `REAL_READONLY`/`REAL_MUTATIONS_ENABLED` previnem mutações acidentais em produção.
- **Timeouts em todas as chamadas HTTP externas** (ViaCEP, IBGE, Nominatim, OpenRouteService, LibreOffice/unoserver). Nenhuma chamada de rede sem `timeout=`.
- **Dependências bem fixadas.** `requirements/base.txt` usa faixas com limite superior (`Django>=5.2,<6.0`, etc.), evitando upgrades-surpresa.
- **Settings por ambiente** (`base`/`dev`/`test`/`prod`) com `prod.py` exigindo `SECRET_KEY` e variáveis de banco via `os.environ[...]` (falha cedo se faltar).
- **Middleware AJAX-aware** (`core.middleware`) que devolve JSON 401 em vez de HTML de login para chamadas `fetch` — evita o clássico erro "Unexpected token '<'".
- **Sem anti-padrões graves:** nenhum `csrf_exempt`, `eval(`, `exec(` ou `subprocess(shell=True)` em código de aplicação; nenhum `print()` solto em código de produção; nenhum `|safe` em templates; zero `SECRET_KEY`/senha hardcoded fora do `config/`.

---

## 3. Achados por severidade

### 🔴 ALTO

#### A1. `AUTH_PASSWORD_VALIDATORS` ausente
`config/settings/base.py` não define `AUTH_PASSWORD_VALIDATORS`. Sem isso, o Django **aceita senhas fracas** (ex.: `123`, `senha`, igual ao username) em criação de usuários e troca de senha. Para um sistema institucional com login obrigatório, é uma lacuna direta.
**Correção:** adicionar o bloco padrão dos 4 validadores (`UserAttributeSimilarity`, `MinimumLength`, `CommonPassword`, `NumericPassword`) em `base.py`.

#### A2. Inconsistência de path no `deploy.yml` (deploy pode quebrar)
`.github/workflows/deploy.yml` mistura **dois nomes de diretório base** diferentes:
```
cd /var/www/gerenciador-viagens/app                 # sem "de"
source /var/www/gerenciador-de-viagens/venv/...     # COM "de"
systemctl restart gerenciador-viagens
```
O `app/` e o `venv/` apontam para árvores diferentes (`gerenciador-viagens` vs `gerenciador-de-viagens`). No mínimo um dos dois está errado; se for o `venv`, o `pip install`/`migrate`/`collectstatic` rodam fora do ambiente esperado. Além disso o deploy não tem nenhum tratamento de falha (um `git pull` ou `migrate` que falha deixa o serviço meio-migrado).
**Correção:** unificar o path base; idealmente parametrizar via `secrets`/variável e usar `set -e` no script.

#### A3. CI executa apenas ~13% da suíte de testes
`.github/workflows/tests.yml` roda **somente 10 módulos do app `documentos`**, ignorando os outros ~59 arquivos de teste (`roteiros`, `oficios`, `cadastros`, `planos_trabalho`, `prestacoes_contas`, etc.). Regressões em roteiros/ofícios/cadastros **não são detectadas** no PR. Há `roteiros/tests/test_routing.py` com 1083 linhas que nunca roda no CI.
**Correção:** rodar `python manage.py test --settings=config.settings.test` (suíte inteira). Se alguns testes exigem dependências de sistema, separar em jobs e não simplesmente omiti-los.

#### A4. Hardening HTTPS incompleto em produção
`config/settings/prod.py` define HSTS + cookies `Secure`, mas **faltam**:
- `SECURE_SSL_REDIRECT = True` (forçar https);
- `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` — atrás de Nginx, sem isso o Django pensa que a conexão é HTTP, `request.is_secure()` retorna `False` e a marcação `Secure`/HSTS pode não se comportar como esperado.

Rode `python manage.py check --deploy --settings=config.settings.prod` para a lista completa.

---

### 🟠 MÉDIO

#### M1. Tratamento de exceções excessivamente amplo
78 ocorrências de `except Exception`/`except:` em código de aplicação. Captura larga tende a **engolir erros reais** (incluindo `KeyboardInterrupt`/bugs de programação) e dificulta diagnóstico. Onde for "tolerância intencional" (ex.: geração de PDF com fallback), capturar a exceção específica e **logar** o erro engolido.

#### M2. Logging de produção frágil
`prod.py` define um único `FileHandler` apontando para `/var/www/gerenciador-viagens/logs/django.log` (mesmo path divergente do A2), nível `ERROR`, sem handler de console e sem rotação. Se o diretório não existir, a inicialização do logging falha; sem console, em container/systemd você perde visibilidade. Considerar `logging.handlers.RotatingFileHandler` + handler de console (`stdout`) e criar o diretório no deploy.

#### M3. Arquivos "lixo" versionados (incham o clone)
Estão rastreados pelo git arquivos que não deveriam estar:
- `tatus` (8 KB) — saída acidental de `git branch` (lista de branches `ajuste/...` com códigos ANSI). Provável `git branch > tatus` / erro de digitação.
- `lista de unidades.csv` na raiz (com espaços no nome).
- `logs/geocodificar_cidades-*.log` (logs de execução).
- `media_teste/documentos/gerados/...` (DOCX/PDF/TXT de teste).
- `migration_backups/20260616-170253/before_reset_central_viagens.dump` (dump binário) e `import_legacy_sqlite.py` (789 linhas de script descartável).
- `tmp/rt_unpacked/...` (ZIP DOCX desempacotado, inclui fonte de 1,6 MB).
- `screenshots/**/*.png` — vários PNGs de **~2 MB cada** (auditoria de UI / baselines), somando dezenas de MB.
- `scripts/fixture_dados.json` (1,9 MB).

**Impacto:** clone lento e histórico inflado permanentemente. **Correção:** `git rm --cached` nesses caminhos, adicionar ao `.gitignore` (`tatus`, `*.dump`, `media_teste/`, `migration_backups/`, `tmp/`, `screenshots/` ou ao menos os PNGs grandes) e mover artefatos grandes para fora do repo.

#### M4. Arquivos muito grandes (manutenibilidade)
`roteiros/roteiro_logic.py` tem **1751 linhas**; `planos_trabalho/views.py` 1288; `oficios/views.py` 1285; `prestacoes_contas/views.py` 1131; `protocolos/services.py` 1059. Módulos desse tamanho são difíceis de revisar e testar. Avaliar fatiamento por subdomínio (o app `roteiros` já tem `services/` modularizado — vale estender o mesmo padrão ao `roteiro_logic.py`).

#### M5. Configuração de negócio embutida em código
`base.py` traz `OFICIO_NUMERO_INICIAL = {2026: 75}` (piso de numeração por ano) hardcoded. Regras desse tipo mudam por ano/órgão; o ideal é tirar do código (variável de ambiente, ou a tabela `ConfiguracaoSistema` que já existe no app `cadastros`).

---

### 🟡 BAIXO

- **B1.** Quatro arquivos de exemplo de ambiente com sobreposição: `.env.example`, `.env.homologacao.example`, `.env.producao.example` **e** `.env.production.example` (`producao` vs `production` — provável duplicata). Consolidar.
- **B2.** `load_dotenv` é chamado em `dev.py` (linha 9) **e** em `base.py` (linha 16). Funciona por causa do `override=False`, mas é redundante e confunde a ordem de precedência.
- **B3.** `.env` (dev/remoto) tem `ALLOWED_HOSTS=...,*` e `DEBUG=True`. É aceitável em dev e o `prod.py` ignora isso (força `DEBUG=False` e lê `ALLOWED_HOSTS` do ambiente), mas convém um comentário explícito de que `*` **nunca** pode vazar para produção.
- **B4.** Bloco `DATABASES` é duplicado quase idêntico entre `dev.py` e `prod.py`. Poderia ser uma função utilitária compartilhada em `base.py`.

---

## 4. Notas por área

| App | LOC | Observação |
|---|---:|---|
| `roteiros` | 9.614 | Maior app; lógica de rotas/diárias bem fatiada em `services/`, exceto `roteiro_logic.py` (1751 linhas) que concentra demais. |
| `oficios` | 7.943 | Geração documental (docxtpl). Camadas bem separadas; `views.py` grande. |
| `cadastros` | 6.457 | Núcleo de domínio (servidores, cidades, viaturas, `ConfiguracaoSistema`). Bons *management commands* de importação (IBGE/CSV). |
| `documentos` | 5.212 | 76 arquivos — núcleo DOCX/PDF com adapters (WeasyPrint/LibreOffice) e fallback. **Único app coberto pelo CI.** |
| `planos_trabalho` | 5.462 | `views.py`/`services.py`/`forms.py` todos grandes. |
| `prestacoes_contas` | 4.456 | OK. |
| `protocolos` | 4.395 | Integração eProtocolo; `services.py` 1059 linhas. |
| `termos` / `justificativas` / `eventos` / `ordens_servico` | — | Menores, consistentes com o padrão. |
| `diario_bordo` (33 linhas) e `usuarios` (31 linhas) | — | Praticamente vazios — esqueletos. Confirmar se são *placeholders* intencionais ou apps a remover. |

---

## 5. Segurança — checklist

| Item | Estado |
|---|---|
| `.env` fora do git | ✅ |
| Segredos só via `os.environ` | ✅ |
| `DEBUG=False` em prod | ✅ (forçado) |
| `SECRET_KEY` obrigatória em prod | ✅ |
| Cookies `Secure` + HSTS | ✅ |
| Validadores de senha | ❌ (A1) |
| `SECURE_SSL_REDIRECT` / `SECURE_PROXY_SSL_HEADER` | ❌ (A4) |
| `csrf_exempt` / `eval` / `shell=True` | ✅ nenhum |
| Timeouts em chamadas externas | ✅ |
| Chave OpenRouteService só no backend | ✅ (comentado e respeitado) |

---

## 6. Recomendações priorizadas (quick wins primeiro)

1. **(A1)** Adicionar `AUTH_PASSWORD_VALIDATORS` em `base.py`. *(5 min, alto retorno de segurança)*
2. **(A4)** Adicionar `SECURE_SSL_REDIRECT` e `SECURE_PROXY_SSL_HEADER` em `prod.py`; rodar `check --deploy`. *(10 min)*
3. **(A2/M2)** Corrigir o path divergente no `deploy.yml` e no `LOGGING`; adicionar `set -e`. *(15 min, evita deploy quebrado)*
4. **(A3)** Fazer o CI rodar a suíte completa (`manage.py test`). *(20 min, pega regressões de verdade)*
5. **(M3)** `git rm --cached` no lixo versionado (`tatus`, `media_teste/`, `migration_backups/`, `tmp/`, PNGs grandes, `lista de unidades.csv`) e atualizar `.gitignore`. *(30 min, repo mais leve para sempre)*
6. **(M5/B1/B2/B4)** Limpezas de configuração (tirar `OFICIO_NUMERO_INICIAL` do código, consolidar `.env.example`, remover `load_dotenv` duplicado).
7. **(M1/M4)** Refatorações graduais: estreitar `except Exception` com log, e fatiar `roteiro_logic.py` / views >1000 linhas — sem pressa, conforme tocar cada área.

---

*Auditoria de revisão de código. Nenhuma alteração funcional foi feita ao gerar este relatório — apenas leitura e análise. As correções acima são propostas; posso implementá-las sob demanda.*
