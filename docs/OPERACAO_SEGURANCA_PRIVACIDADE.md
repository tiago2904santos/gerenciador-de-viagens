# Operação, segurança e privacidade

## Backups e restauração

- RPO alvo: 24 horas; RTO alvo: 4 horas.
- Agendar `scripts/backup_production.sh` diariamente fora do horário de pico.
- O pacote contém PostgreSQL, mídia privada, SHA-256 e commit implantado; ele é
  cifrado com AES-256/PBKDF2 antes de sair do host.
- Manter 30 dias no servidor, uma cópia em `BACKUP_RCLONE_REMOTE` e uma terceira
  cópia institucional imutável/offline. A chave fica no secret manager, nunca no
  banco ou no repositório.
- A CI executa um restore completo a cada mudança. Produção deve fazer um restore
  isolado trimestral e registrar duração, responsável e resultado.
- `scripts/restore_backup.sh` exige `RESTORE_CONFIRM=RESTAURAR`; usar somente em
  banco/host previamente isolado ou durante procedimento formal de recuperação.

## Classificação e retenção LGPD

| Classe | Exemplos | Acesso | Retenção técnica sugerida |
|---|---|---|---|
| Identificação | nome, CPF, RG, telefone | área autorizada | vínculo + prazo legal institucional |
| Operacional | roteiro, ofício, diárias, viatura | área autorizada | prazo arquivístico aplicável |
| Probatória | PDF, assinatura, hash, evidências | Editor/Admin; link temporário específico | append-only conforme tabela de temporalidade |
| Credencial | tokens OAuth | serviço e administradores restritos | até revogação, com rotação |
| Auditoria | ator, IP, mudanças e request ID | administradores/auditoria | mínimo definido pela controladoria |

Antes da produção, o encarregado de dados deve aprovar base legal, finalidade,
tabela de temporalidade e canal de atendimento ao titular. Exclusão de documento
oficial é representada por cancelamento/revogação (tombstone); versões assinadas
não são apagadas nem substituídas.

## Direitos do titular e incidentes

1. Registrar solicitação e validar identidade por canal institucional.
2. Consultar os eventos de auditoria e exportar apenas os dados autorizados.
3. Retificar o cadastro de origem; preservar versões probatórias quando houver
   obrigação legal, documentando a restrição.
4. Em incidente, revogar sessões/tokens, preservar evidências, delimitar áreas e
   titulares afetados e acionar encarregado, segurança e jurídico.

## Observabilidade e alertas

- `/health/` é readiness e verifica o PostgreSQL.
- `/metrics/` expõe contadores Prometheus somente com
  `Authorization: Bearer $METRICS_TOKEN`; nunca publicar o token no frontend.
- Logs estruturados saem em stdout com `request_id`; o proxy também devolve
  `X-Request-ID`.
- Alertar para taxa de HTTP 5xx, latência p95, indisponibilidade do health,
  fila Celery crescente, jobs órfãos, falhas de antivírus, falhas de backup e
  geração documental p95 acima de 1 segundo.
- O benchmark operacional é
  `python manage.py documentos_unoserver_check --benchmark --representative-resources --max-ms 1000 --iterations 3`.

## SSO e MFA institucional

- Ative `SSO_REMOTE_USER_ENABLED=true` somente quando o Django estiver
  inacessível diretamente e atrás de proxy listado em `TRUSTED_PROXY_IPS`.
- O proxy deve remover cabeçalhos recebidos do cliente e preencher
  `X-Authenticated-User` apenas após autenticação no provedor institucional.
- Com `SSO_MFA_REQUIRED=true`, o proxy também deve enviar `X-Auth-MFA: true`.
  Sem essa asserção, a identidade é recusada.
- MFA, desligamento de contas e políticas de risco permanecem sob controle do
  provedor institucional; testar o fluxo completo antes da homologação.

## Assinatura pública

O sistema registra token em hash, expiração, tentativas persistentes por IP e
token, aceite e artefato assinado. O método de identificação e o nível probatório
devem ser homologados pelo jurídico; a aplicação técnica não substitui essa
decisão. Proxies confiáveis devem ser declarados explicitamente e o link nunca
deve aparecer em logs, buscas administrativas ou analytics.
