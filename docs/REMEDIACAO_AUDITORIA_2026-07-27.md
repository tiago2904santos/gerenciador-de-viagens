# Remediação da auditoria de 27/07/2026

## Estado executivo

Os achados P0 e P1 da auditoria foram tratados no código e cobertos por testes
ou gates de CI. As recomendações P2 receberam correções de desempenho,
paginação, isolamento, observabilidade, segurança de produção e melhoria da
interface.

Dois critérios dependem do ambiente de homologação/produção e não devem ser
declarados concluídos apenas com evidência local:

1. o benchmark representativo DOCX/XLSX precisa passar no unoserver Linux com
   máximo estritamente menor que 1 segundo;
2. os registros legados com `area=NULL` precisam ser atribuídos após backup e
   resolução humana dos conflitos de identidade encontrados.

O deploy é bloqueado quando o segundo item não foi saneado. A CI é bloqueada
quando o primeiro item não atende ao SLA.

## Matriz dos achados

| Achado | Controle implementado | Evidência/gate |
|---|---|---|
| P0-01 mídia privada | download autorizado no Django e `X-Accel-Redirect` para localização Nginx `internal` | testes de acesso e configuração de deploy |
| P0-02 IDOR de roteiro | resolução por área do objeto pai e validação cruzada central | testes negativos de isolamento |
| P0-03 dependências | requisitos atualizados, lock reproduzível e `pip-audit` | workflow de testes |
| P1-01 RBAC | papéis Administrador/Editor/Leitor aplicados no servidor e refletidos na interface | matriz de testes de papel |
| P1-02 `area=NULL` | querysets estritos, comando de backfill e check de deploy bloqueante | `core.E001` até saneamento |
| P1-03 auditoria | eventos imutáveis com ator, contexto, antes/depois e origem | testes de trilha |
| P1-04 numeração | restrição única, advisory lock por área/ano e retry em savepoint | teste de colisão e teste concorrente PostgreSQL |
| P1-05 OAuth | tokens criptografados, mascarados e com rotação de chave | migração e testes |
| P1-06 assinatura pública | token protegido, rate limit persistente, proxy confiável e evidências | testes de abuso/replay |
| P1-07 uploads | política central de tamanho, conteúdo, nome, imagem e antivírus fail-closed | testes de arquivos inválidos |
| P1-08 autenticação | validadores, rate limit, sessão curta, encerramento de sessões e SSO/MFA opcional | testes de autenticação e proxy |
| P1-09/P1-10 CI | suíte completa, migrations, deploy check, auditor frontend e dependências | 804 testes locais verdes; CI PostgreSQL obrigatória |
| P1-11 tarefas | Celery pós-commit, sem threads daemon ou mutação de banco no startup | testes da integração |
| P1-12 operação | health, métricas, logs JSON, backup criptografado, restore drill e rollback | CI e documentação operacional |
| P2-01 GET mutável | criação de rascunho por confirmação + POST | testes dos fluxos |
| P2-02 consultas | paginação, prefetch/select_related e orçamentos de queries | testes de Eventos, Planos e Perfil |
| P2-04 acoplamento | bases comuns movidas para `core`; integração assíncrona explícita | checks e testes |
| P2-05 integridade de área | validação central de FKs e resolução sempre escopada | testes de relações cruzadas |
| P2-06 numeração anual | configuração administrável por área/ano | modelo, migração e admin |
| P2-07/P2-08 produção | stdout JSON, request ID, HTTPS, HSTS e CSP | `check --deploy` na CI |
| P2-09 documentos | versões append-only, hash, ator, proprietário preservado e tombstone | migração e testes |
| P2-10 LGPD | inventário, retenção, incidente, RPO/RTO e responsabilidades | documentação operacional |
| UX/acessibilidade | navegação agrupada, dashboard operacional, módulos redundantes ocultos, um `<main>` e títulos coerentes | auditoria ao vivo e testes |

## SLA de geração documental

O caminho recomendado é:

1. unoserver/LibreOffice residente e aquecido;
2. caminhos locais para evitar base64/XML-RPC quando conversor e aplicação
   compartilham o host;
3. cache Redis por SHA-256 do binário exato;
4. métricas de duração e violações do SLA;
5. gate sem cache usando os maiores modelos reais (`ordem_servico.docx` e
   `diario_bordo.xlsx`), três vezes cada:

```bash
python manage.py documentos_unoserver_check \
  --benchmark --representative-resources --max-ms 1000 --iterations 3
```

Uma execução igual a 1000 ms já reprova. Cache melhora repetições, mas não é
usado para mascarar o benchmark.

## Homologações externas obrigatórias

- executar a CI PostgreSQL/Linux e registrar os seis tempos do benchmark;
- fazer backup antes do backfill de áreas e resolver os conflitos listados pelo
  modo dry-run;
- validar Nginx, TLS, firewall, Redis/Celery e permissões reais;
- realizar pentest externo, teste de carga e restore de produção;
- concluir revisão jurídica/LGPD da assinatura e teste com leitor de tela.
