# Auditoria completa do Gerenciador de Viagens

**Data:** 27/07/2026  
**Escopo:** código-fonte, configurações Django, banco local, testes, dependências Python, integrações, documentos, interface, acessibilidade, desempenho e processo de deploy.  
**Método:** inspeção estática, comandos de diagnóstico, execução segmentada de testes, consultas no banco local, medição de requisições Django e navegação autenticada em desktop/mobile.

## 1. Conclusão executiva

O sistema tem uma base funcional forte, bom volume de testes e fluxos documentais sofisticados. Contudo, **não deve ser considerado pronto para produção sensível sem uma rodada de correções de segurança e operação**.

Foram identificadas quatro frentes que precisam de tratamento imediato:

1. Arquivos de mídia privados podem ser publicados diretamente pelo Nginx, sem autenticação.
2. Existe um caminho concreto para vincular um roteiro avulso de outra área a um ofício.
3. As dependências instaladas incluem versões afetadas por avisos de segurança publicados.
4. Os papéis Administrador, Editor e Leitor existem, mas não são aplicados às operações dos módulos.

Além disso, há riscos importantes em numeração concorrente, rastreabilidade, assinatura pública, tokens OAuth, uploads, deploy, backups, tarefas assíncronas e isolamento de registros legados.

### Avaliação resumida

| Dimensão | Avaliação | Comentário |
|---|---:|---|
| Funcionalidade | Boa | Muitos fluxos já estão implementados e testados |
| Segurança | Crítica | Há exposições confirmadas e controles ausentes |
| Isolamento por área | Insuficiente | A base funciona, mas há exceções perigosas e legado compartilhado |
| Integridade documental | Regular | Há hash e snapshots, mas falta trilha de auditoria e imutabilidade real |
| Confiabilidade operacional | Insuficiente | Deploy sem gate, sem health check, rollback ou backup formalizado |
| Desempenho | Regular | N+1 e respostas grandes em páginas centrais |
| Manutenibilidade | Regular | Arquivos muito grandes e forte acoplamento entre views, signals e serviços |
| UX e responsividade | Boa | Interface consistente e mobile funcional |
| Acessibilidade | Regular/boa | Estrutura geral boa, com problemas pontuais de landmarks e hierarquia |

## 2. Achados críticos — P0

### P0-01 — Arquivos privados expostos por `/media/`

**Evidência:** `docs/DEPLOY_VPS.md:320-322` configura:

```nginx
location /media/ {
    alias /var/www/gerenciador-viagens/media/;
}
```

Os diretórios de mídia incluem PDFs gerados, PDFs assinados, anexos de eventos e documentos de prestação de contas. Essa configuração permite que quem conheça ou descubra a URL acesse o arquivo diretamente, ignorando login, área de trabalho, permissões e links temporários do Django.

**Impacto:** vazamento de dados pessoais e documentos institucionais.

**Correção:** tornar a mídia privada; servir arquivos somente após autorização no Django, usando `X-Accel-Redirect` para uma localização Nginx `internal`. Manter público apenas o fluxo de assinatura/link temporário, com expiração e validação próprias.

### P0-02 — Possível vínculo de roteiro entre áreas

**Evidência:** `oficios/services.py:140-154` aceita qualquer roteiro `AVULSO` pelo `pk`, sem aplicar o filtro da área atual. `oficios/views.py:734-744` também recupera o rascunho do autosave apenas pelo `pk`.

Um usuário autenticado pode enviar manualmente o identificador de um roteiro avulso pertencente a outra área e vinculá-lo ao ofício da sua área.

**Impacto:** quebra de isolamento, exposição indireta e corrupção de relações entre áreas.

**Correção:** toda resolução de objetos recebidos do cliente deve partir de um queryset filtrado pela área do objeto pai/solicitação. Adicionar validação de mesma área no serviço e testes negativos de IDOR para todos os relacionamentos.

### P0-03 — Dependências com avisos de segurança conhecidos

A consulta de todas as versões instaladas na `.venv` à API OSV retornou avisos ativos. Casos prioritários:

- Django `5.2.13`: avisos corrigidos em `5.2.14` e `5.2.15`, incluindo conteúdo sensível em cache/cookies e falha de conexão após `STARTTLS`.
- `pypdf 6.11.0`: avisos de negação de serviço; um dos reparos está em `6.12.0`.
- `weasyprint 63.1`: bypass de proteção SSRF corrigido em `68.0`; o requisito atual limita a versão a `<64`.
- `cryptography 45.0.7`: aviso relacionado ao OpenSSL incluído nos wheels corrigido em `48.0.1`; o requisito atual limita a versão a `<46`.
- Também foram reportados avisos para Pillow, idna, pyasn1 e urllib3.

Referências primárias: [Django GHSA-5hrc-gvxj-w55p](https://github.com/advisories/GHSA-5hrc-gvxj-w55p), [Django GHSA-mm6v-q8q9-pgcf](https://github.com/advisories/GHSA-mm6v-q8q9-pgcf), [WeasyPrint GHSA-983w-rhvv-gwmv](https://github.com/advisories/GHSA-983w-rhvv-gwmv), [cryptography GHSA-537c-gmf6-5ccf](https://github.com/advisories/GHSA-537c-gmf6-5ccf) e [pypdf GHSA-248m-82v9-q6g6](https://github.com/advisories/GHSA-248m-82v9-q6g6).

**Correção:** atualizar imediatamente os pacotes, rever os limites de versão, gerar lockfile reproduzível e executar `pip-audit`/OSV em toda pull request. Antes de liberar versões maiores de renderizadores, executar regressão visual e documental.

## 3. Achados de alta prioridade — P1

### P1-01 — Papéis de acesso não são aplicados

`usuarios.models.VinculoUsuarioArea` define `ADMIN`, `EDITOR` e `LEITOR`, mas a busca no código não encontrou decisões de autorização baseadas em `papel` nos módulos de negócio. Na prática, a área restringe visibilidade, mas um Leitor pode alcançar operações de criação, alteração, cancelamento e exclusão.

**Correção:** criar uma camada central de autorização, por exemplo `require_area_role()`/permissions por ação; negar no servidor e refletir a permissão na interface. Cobrir cada módulo com matriz Leitor × Editor × Admin.

### P1-02 — Registros com `area=NULL` são compartilhados

`core/tenancy.py:67-68` inclui `area__isnull=True` para qualquer área ativa. Isso foi criado como compatibilidade legada, mas torna registros sem área visíveis transversalmente.

No banco local há registros operacionais sem área, incluindo 7 eventos, 8 ofícios, 1 plano de trabalho e 1 prestação de contas. Há também catálogos e jobs sem área.

**Correção:** classificar quais dados são realmente globais, migrar os demais para uma área obrigatória e substituir o significado implícito de `NULL` por um escopo explícito. Depois, remover a compatibilidade dos querysets operacionais.

### P1-03 — Não há trilha de auditoria de domínio

Os modelos têm timestamps, mas não registram de forma consistente:

- quem criou ou alterou;
- mudança anterior e nova;
- quem cancelou/excluiu;
- motivo da mudança;
- origem da operação;
- versão do documento.

Diversos fluxos fazem exclusão física, inclusive planos, termos, ordens, anexos e arquivos.

**Impacto:** baixa rastreabilidade administrativa, probatória e de suporte.

**Correção:** adotar eventos de auditoria imutáveis, incluir ator e contexto, preferir cancelamento/tombstone para documentos oficiais e versionar substituições. Definir retenção conforme a política institucional e LGPD.

### P1-04 — Numeração de Ordem de Serviço não é segura sob concorrência

`ordens_servico/models.py:178-198` calcula `último número + 1` sem transação com trava. O modelo não possui `UniqueConstraint` para área, ano e número.

**Impacto:** duas requisições simultâneas podem gerar o mesmo número.

**Correção:** usar alocador transacional por área/ano com `select_for_update`, restrição única no banco e retry controlado em conflito.

### P1-05 — Tokens OAuth do Google Drive em texto puro

`integracoes/google_drive/models.py:18-19` armazena `access_token` e `refresh_token` diretamente em `TextField`. O admin ainda os inclui como campos somente leitura.

**Correção:** criptografia de campo com chave fora do banco, rotação de chave, mascaramento no admin, escopos mínimos e procedimento de revogação. Avaliar secret manager.

### P1-06 — Proteção da assinatura pública é contornável

`prestacoes_contas/assinatura_views.py` limita cinco tentativas por sessão do navegador. Limpar cookies ou abrir outra sessão reinicia a contagem. O IP usa o primeiro valor de `X-Forwarded-For` sem uma política explícita de proxies confiáveis.

O link de assinatura usa token aleatório e expiração, o que é positivo, mas a identificação por link + CPF/nome e a assinatura gráfica precisam de validação jurídica para o nível probatório pretendido.

**Correção:** rate limit persistente por token e IP, hash do token no banco, trusted proxy, proteção contra replay, trilha de evidências e revisão jurídica do método de aceite. Não indexar `link_token` no campo de busca do admin.

### P1-07 — Validação desigual de uploads

O upload de PDF assinado valida extensão, tamanho e cabeçalho, mas anexos de eventos/prestações não usam uma política central equivalente.

**Correção:** limite por arquivo, quantidade e total da requisição; validação por conteúdo; decodificação segura de imagens/PDF; nomes normalizados; quarentena e antivírus; armazenamento fora da árvore pública.

### P1-08 — Senhas e sessões abaixo do necessário

`AUTH_PASSWORD_VALIDATORS` não está configurado e resulta em lista vazia. A sessão usa o padrão do Django, aproximadamente 14 dias. Não há evidência de rate limit de login, MFA ou SSO.

**Correção:** validadores de senha, bloqueio progressivo/rate limit, expiração por inatividade, encerramento de outras sessões após troca de senha e, preferencialmente, SSO/MFA institucional.

### P1-09 — Deploy não depende da suíte de testes

`.github/workflows/tests.yml:28-41` executa apenas dez módulos do núcleo documental. A suíte encontrada possui 769 testes. `.github/workflows/deploy.yml:23-32` publica todo push em `main` diretamente, sem dependência do workflow de testes, health check, rollback ou backup.

**Correção:** CI obrigatória com suíte completa, migrações, `check --deploy`, lint/auditorias e segurança; gerar artefato imutável; deploy por versão; backup pré-migração; health check e rollback automático.

### P1-10 — Suíte completa está vermelha

`manage.py test --parallel 4` encontrou 769 testes e falhou. A execução serial confirmou testes com nomes de rota removidos, como `cadastros:cargo_create`, `combustivel_create` e `unidade_create`. No paralelo, o Python 3.14 ainda mascara parte do diagnóstico ao não conseguir serializar um traceback.

**Correção:** corrigir os contratos obsoletos e manter `main` verde. Até estabilizar o paralelo, executar serialmente na CI para preservar o erro real.

### P1-11 — Threads em processo web para trabalho assíncrono

`integracoes/google_drive/signals.py` e `integracoes/google_drive/views.py` iniciam `threading.Thread(..., daemon=True)`. Em Gunicorn, essas tarefas podem se perder em restart, duplicar entre workers e não têm garantia de entrega.

O `AppConfig.ready()` do Drive também acessa/muda o banco na inicialização, gerando aviso no `manage.py check`.

**Correção:** mover todo trabalho para Celery, disparar após `transaction.on_commit`, tornar tarefas idempotentes e remover mutações de banco do startup. O ambiente local atual não tem Celery/Redis instalados apesar de constarem nos requisitos.

### P1-12 — Backup, restauração e observabilidade não estão definidos

Não foi encontrado procedimento operacional completo para backup automático de PostgreSQL e mídia, retenção, criptografia, restore testado, RPO/RTO, endpoint de health/readiness ou alerta centralizado.

**Correção:** política 3-2-1 adequada ao ambiente, backups de banco e arquivos consistentes, simulação periódica de restore, health checks, métricas, logs estruturados e alertas.

## 4. Prioridade média — P2

### P2-01 — Criação de rascunhos por GET

`eventos/views.py:406-410`, `oficios/views.py:578-581` e `planos_trabalho/views.py:386-390` criam e salvam registros ao abrir uma URL GET. Cliques acidentais, prefetch e abandono produzem rascunhos e consomem numeração.

No banco local foram encontrados rascunhos com mais de sete dias: 7 eventos, 10 ofícios, 14 planos e 16 roteiros.

**Correção:** criação por POST ou no primeiro salvamento válido, autor do rascunho e rotina segura de expiração/limpeza.

### P2-02 — Consultas excessivas e respostas grandes

Medições autenticadas no banco local:

| Página | Consultas | Tempo observado | Resposta |
|---|---:|---:|---:|
| Dashboard | 6 | 929 ms no primeiro acesso | 24 KB |
| Roteiros | 14 | 198 ms | 26 KB |
| Eventos | 74 | 460 ms | 155 KB |
| Ofícios | 8 | 58 ms | 43 KB |
| Termos | 28 | 130 ms | 87 KB |
| Planos | 43 | 159 ms | 102 KB |
| Prestações de contas | 79 | 290 ms | 448 KB |
| Perfil | 79 | 210 ms | 55 KB |

Com apenas 24 eventos, 27 prestações e 175 servidores, Eventos, Prestações e Perfil já exibem sinais claros de N+1 e excesso de payload.

**Correção:** paginação, `select_related`/`prefetch_related`, contagens anotadas, carregamento sob demanda do status do Drive e testes com orçamento de queries.

### P2-03 — Arquivos centrais grandes demais

Exemplos:

- `prestacoes_contas/views.py`: 1.606 linhas;
- `roteiros/roteiro_logic.py`: 1.603;
- `planos_trabalho/views.py`: 1.397;
- `oficios/views.py`: 1.292;
- `static/css/dark-redesign.css`: 4.622;
- `static/js/pages/roteiros/editor/index.js`: 2.036.

**Correção:** extrair casos de uso, selectors, políticas de autorização, validadores e componentes por contexto. Reduzir lógica de domínio em views e signals.

### P2-04 — Acoplamento e direção de dependências

`TimeStampedModel` e `CancelavelModel` vivem em `cadastros`, embora sejam bases usadas por outros domínios. Signals dependem de request corrente por thread-local e disparam integrações.

**Correção:** mover abstrações comuns para `core`, usar serviços explícitos e eventos pós-commit. Fazer a migração de bases de modelo com cuidado para não alterar tabelas.

### P2-05 — Integridade entre áreas depende só da aplicação

O banco local não apresentou relações cruzadas atuais nas FKs verificáveis, o que é positivo. Porém, o banco não impede que objetos de áreas diferentes sejam associados em várias FKs/M2M.

**Correção:** validações centralizadas e testes de isolamento por relação; onde viável, modelagem/chaves que permitam restrição no banco.

### P2-06 — Configuração anual em código

`config/settings/base.py:116-120` contém `OFICIO_NUMERO_INICIAL = {2026: 75}`.

**Correção:** mover pisos/exceções de numeração para configuração administrável e auditável por área e ano.

### P2-07 — Logging de produção é rígido

`config/settings/prod.py:55-67` força `/var/www/gerenciador-viagens/logs/django.log`. Isso impede executar `check --deploy` fora dessa estrutura e reduz portabilidade.

**Correção:** log em stdout por padrão, com agregador externo, ou caminho por variável de ambiente. Adicionar `check --deploy` em ambiente Linux na CI.

### P2-08 — Cabeçalhos de segurança incompletos

Produção possui cookies seguros, HSTS, `nosniff`, referrer policy e proxy SSL configurados. Não foi encontrada política CSP nem `SECURE_SSL_REDIRECT`; a aplicação depende do Nginx para redirecionamento.

**Correção:** definir CSP após remover scripts inline, explicitar/validar redirecionamento HTTPS e automatizar `manage.py check --deploy`.

### P2-09 — Documentos “históricos” não são totalmente imutáveis

`DocumentoArtefato` possui hash, snapshot e cache, bons controles de integridade. Porém, o proprietário usa `CASCADE`, arquivos assinados podem ser substituídos/removidos e não há ator/versão imutável.

**Correção:** definir formalmente o ciclo de vida; para documento oficial, usar versões append-only, retenção e tombstone.

### P2-10 — Privacidade e LGPD sem política técnica visível

O sistema processa CPF, RG, telefone, documentos, dados de viagem e assinatura. Não foram encontrados classificação de dados, prazos de retenção, relatório de acessos, anonimização ou processo de atendimento ao titular.

**Correção:** inventário de dados pessoais, base legal/finalidade, minimização, retenção, controle de acesso, logs e procedimento de incidente.

## 5. Produto, UX e acessibilidade

### Pontos positivos

- Tema visual consistente e profissional.
- Responsividade confirmada em viewport de 390 × 844, sem overflow horizontal nas telas verificadas.
- Controles visíveis possuem rótulos; não foram encontrados IDs duplicados nem botões sem nome acessível nas páginas amostradas.
- Há link “Pular para o conteúdo principal”.
- Não surgiram erros de console durante a navegação amostrada.

### Melhorias recomendadas

1. O dashboard mostra indicadores neutros (`—` / “aguardando dados”) apesar de haver dados. Transformá-lo em painel operacional com pendências, documentos aguardando assinatura, viagens próximas e alertas.
2. A navegação é longa e plana. Agrupar itens por Planejamento, Documentos, Execução/Prestação e Administração.
3. `Diário de Bordo` aparece como módulo isolado incompleto, enquanto o fluxo real está em Prestação de Contas. Consolidar ou ocultar o placeholder.
4. A página Documentos também aparenta placeholder, embora a infraestrutura documental seja central. Reposicionar como acervo/pesquisa ou removê-la da navegação até estar pronta.
5. Em `/perfil/` há dois elementos `<main>` e a hierarquia salta de `h3` para `h4`/`h5`. Manter um único landmark principal e uma árvore de títulos coerente.
6. Há scripts inline e `href="#"` em componentes, o que dificulta CSP e pode causar comportamento ruim de teclado.
7. Corrigir textos como “de este documento” para “deste documento” e “Proximo” para “Próximo”.
8. Completar teste manual de teclado, foco de modais, contraste e leitor de tela nos wizards críticos antes da homologação.

O auditor frontend existente retornou **0 erros, 459 avisos e 11 exceções**. A existência do auditor é positiva, mas o volume de avisos reduz sua utilidade; é necessário resolver ou classificar a dívida e tornar os novos erros bloqueantes na CI.

## 6. Testes e verificações executados

| Verificação | Resultado |
|---|---|
| `manage.py check` | Passou, com aviso de acesso ao banco em `AppConfig.ready()` |
| `makemigrations --check --dry-run` | Sem migrações pendentes |
| `pip check` | Sem dependências quebradas no ambiente |
| Verificação documental | DOCX e PDF via LibreOffice OK; fallback simples OK |
| Suíte Django descoberta | 769 testes |
| Suíte completa | Falha por testes/rotas legados; paralelo mascara parte do erro no Python 3.14 |
| Auditor de arquitetura | 141 suspeitas; requer triagem, mas confirma concentração de responsabilidades |
| Auditor frontend | 0 erros, 459 avisos, 11 exceções |
| OSV das versões instaladas | Avisos ativos em dependências centrais |
| Navegação visual | Desktop e mobile funcionais nas páginas centrais |
| Console do navegador | Sem erros na amostra |
| Isolamento atual de FKs | Nenhuma divergência encontrada na amostra consultada |

## 7. Plano de correção recomendado

### Primeiras 72 horas

1. Bloquear acesso público direto a `/media/`.
2. Corrigir as duas resoluções não filtradas de roteiro em Ofícios e criar testes de IDOR.
3. Atualizar Django, pypdf e demais pacotes corrigíveis; rever os limites de cryptography/WeasyPrint.
4. Impedir deploy automático enquanto a CI essencial não estiver verde.
5. Criar backup completo de banco e mídia e validar uma restauração.

### Semana 1

1. Aplicar RBAC real em todos os módulos.
2. Corrigir numeração concorrente de Ordem de Serviço.
3. Criptografar tokens Google e endurecer assinatura pública.
4. Centralizar validação de uploads.
5. Corrigir a suíte completa e fazê-la obrigatória.
6. Remover threads daemon e acesso ao banco no startup.

### Dias 8–30

1. Implantar trilha de auditoria e política de retenção.
2. Migrar registros operacionais sem área e remover compartilhamento implícito.
3. Implementar health check, observabilidade, rollback e restore drill.
4. Corrigir N+1 e adicionar paginação/orçamento de queries.
5. Trocar criação por GET por fluxo seguro de rascunho.

### Dias 31–90

1. Modularizar os maiores arquivos e reduzir acoplamento de signals/views.
2. Consolidar Diário de Bordo e Acervo de Documentos.
3. Transformar o dashboard em ferramenta operacional.
4. Fechar auditoria de acessibilidade WCAG nos fluxos críticos.
5. Formalizar matriz de dados/LGPD, RPO, RTO e governança documental.

## 8. Critérios de aceite para produção

O sistema pode avançar para uma homologação de produção sensível quando, no mínimo:

- mídia estiver privada;
- IDOR de roteiros estiver corrigido e coberto;
- dependências críticas estiverem atualizadas;
- RBAC estiver aplicado no servidor;
- suíte completa e checks de deploy estiverem verdes;
- backups e restauração estiverem testados;
- numeração concorrente estiver protegida;
- tokens OAuth estiverem criptografados;
- assinatura pública tiver rate limit persistente;
- deploy possuir health check e rollback;
- houver responsável e prazo aceito para cada P1 remanescente.

## 9. Limitações da auditoria

Esta foi uma auditoria técnica aprofundada do workspace e do ambiente local. Ela **não substitui**:

- pentest externo com infraestrutura de produção;
- revisão jurídica da assinatura e LGPD;
- inspeção de Nginx, PostgreSQL, firewall, DNS, TLS e permissões reais do servidor;
- teste de carga representativo;
- restore real dos backups de produção;
- auditoria integral com leitor de tela e tecnologias assistivas.

Esses itens devem compor a fase de homologação, especialmente porque parte do risco depende da configuração efetivamente implantada.
