#!/usr/bin/env bash
# =============================================================================
# deploy_rollback.sh — desfaz as migrações que ESTE deploy aplicou (QA-03)
# =============================================================================
#
# ## Por que existe
#
# `deploy.yml` tirava um backup cifrado antes do checkout, instalava um
# `trap ERR` e, na falha, chamava `reverter()` — que devolvia só o **código**. O
# backup era criado e nunca usado. Uma falha depois do `migrate` deixava o código
# antigo rodando contra um schema que ele não entende: a aplicação não sobe, e a
# recuperação virava intervenção manual sob pressão.
#
# ## O que ele NÃO faz, de propósito
#
# **Não restaura backup.** Restaurar descarta tudo que foi gravado desde que o
# backup foi tirado — e `restore_backup.sh` ainda sobrescreve o `MEDIA_ROOT`,
# perdendo arquivo enviado por usuário. Um deploy leva minutos; nesses minutos há
# gente trabalhando. Trocar uma incidência por outra sem decisão humana não é
# correção. Quando o desfazer automático não é possível, este script **para e
# instrui**, com o caminho real do backup e o comando pronto.
#
# Desfazer pelo próprio Django é o único caminho que **preserva as gravações
# feitas durante a janela do deploy**. Ele não traz de volta dado que a migração
# de ida apagou — mas esse dado já tinha sido apagado, e aqui o objetivo é o
# schema que o código antigo entende.
#
# ## Ordem de chamada
#
# Tem de rodar **antes** do `git checkout` de volta: desfazer uma migração exige
# os arquivos de migração do commit novo em disco.
#
# ## Uso
#
#   ESTADO_MIGRACOES_ANTES=/tmp/migracoes-antes.txt \
#   BACKUP_FILE=/var/backups/.../gerenciador-....tar.gz.enc \
#     bash scripts/deploy_rollback.sh
#
# Saída 0 = banco no estado de antes (ou nada a fazer).
# Saída 1 = banco **não** foi devolvido; exige decisão humana.
# =============================================================================
set -Eeuo pipefail

: "${ESTADO_MIGRACOES_ANTES:?ESTADO_MIGRACOES_ANTES obrigatório (arquivo com o showmigrations de antes)}"
APP_ROOT="${APP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BACKUP_FILE="${BACKUP_FILE:-}"
PYTHON_BIN="${PYTHON_BIN:-python}"

cd "$APP_ROOT"

# `[X] app.0001_nome` → `app.0001_nome`, só as aplicadas.
# `|| true` nos dois: `grep` sem correspondência sai 1, e com `pipefail` isso
# derrubaria o script no caso mais comum de todos (banco sem migração aplicada).
aplicadas_agora() {
  "$PYTHON_BIN" manage.py showmigrations --plan 2>/dev/null \
    | { grep '^\[X\]' || true; } \
    | awk '{print $2}'
}

instruir_e_sair() {
  local motivo="$1"
  echo ""
  echo "══════════════════════════════════════════════════════════════════════"
  echo " O BANCO NÃO FOI DEVOLVIDO AO ESTADO ANTERIOR"
  echo "══════════════════════════════════════════════════════════════════════"
  echo " Motivo: ${motivo}"
  echo ""
  echo " O código volta para o commit anterior, mas o schema está adiante dele."
  echo " A aplicação provavelmente não sobe. Isto exige decisão humana."
  echo ""
  if [[ -n "${BACKUP_FILE}" ]]; then
    echo " Para restaurar o backup tirado no início deste deploy —"
    echo " ATENÇÃO: isto PERDE tudo que foi gravado desde então, inclusive"
    echo " arquivos enviados, porque o MEDIA_ROOT também é sobrescrito:"
    echo ""
    echo "   cd ${APP_ROOT}"
    echo "   set -a && source .env && set +a"
    echo "   RESTORE_CONFIRM=RESTAURAR bash scripts/restore_backup.sh \\"
    echo "     ${BACKUP_FILE}"
  else
    echo " Nenhum backup foi informado a este script (BACKUP_FILE vazio)."
    echo " Procure o mais recente em /var/backups/gerenciador-viagens/."
  fi
  echo ""
  echo " Alternativa sem perder gravações: desfazer a migração à mão, com o"
  echo " código novo ainda em disco, e só então voltar o código."
  echo "══════════════════════════════════════════════════════════════════════"
  echo "::error title=Rollback de banco exige intervenção::${motivo}"
  exit 1
}

if [[ ! -f "${ESTADO_MIGRACOES_ANTES}" ]]; then
  instruir_e_sair "arquivo de estado anterior não existe: ${ESTADO_MIGRACOES_ANTES}"
fi

DEPOIS="$(mktemp)"
# A saída do `migrate` sobrevive ao script de propósito: se ele falhar, é o que
# quem for consertar precisa ler. Fica no diretório temporário do sistema.
SAIDA_MIGRATE="$(mktemp -t deploy-rollback-migrate-XXXXXX.log)"
trap 'rm -f -- "${DEPOIS}"' EXIT

if ! aplicadas_agora > "${DEPOIS}"; then
  # `manage.py` não roda (venv em estado misto por falha no pip, banco fora do
  # ar). Sem saber o que está aplicado, mexer no banco seria chute.
  instruir_e_sair "não foi possível ler o estado das migrações (manage.py falhou)"
fi

# O que este deploy aplicou = está agora e não estava antes. `comm` exige
# entrada ordenada; a ordem do plano é recuperada depois, pelo próprio arquivo.
NOVAS="$(comm -13 <(sort "${ESTADO_MIGRACOES_ANTES}") <(sort "${DEPOIS}") || true)"

if [[ -z "${NOVAS}" ]]; then
  echo "rollback de banco: nenhuma migração foi aplicada por este deploy — nada a desfazer."
  exit 0
fi

echo "rollback de banco: este deploy aplicou $(wc -l <<< "${NOVAS}") migração(ões):"
sed 's/^/  /' <<< "${NOVAS}"

# Ordem inversa do plano: a última aplicada é a primeira a sair. `grep -x -F -f`
# reordena `NOVAS` conforme o arquivo `DEPOIS`, que está na ordem do plano.
NOVAS_EM_ORDEM="$(grep -x -F -f <(echo "${NOVAS}") "${DEPOIS}" || true)"

# Um `migrate` por app, não por migração: dado o alvo, o Django resolve sozinho
# o plano reverso do app inteiro. A ordem entre apps é a inversa do plano, para
# não tentar desfazer algo de que outra migração ainda aplicada dependa.
apps_em_ordem_inversa() {
  tac <<< "${NOVAS_EM_ORDEM}" | cut -d. -f1 | awk '!visto[$0]++'
}

for app in $(apps_em_ordem_inversa); do
  # Alvo = a última migração deste app que já estava aplicada antes do deploy.
  # Nenhuma → `zero`, que desfaz o app inteiro.
  alvo="$({ grep "^${app}\." "${ESTADO_MIGRACOES_ANTES}" || true; } | tail -1 | cut -d. -f2-)"
  alvo="${alvo:-zero}"
  echo "  desfazendo ${app} → ${alvo}"
  # Saída capturada: o traceback do Django tem ~30 linhas e, impresso inteiro
  # antes da instrução, enterra a única parte que interessa a quem está lendo
  # isto durante um incidente. Fica no arquivo; na tela vão as últimas linhas.
  if ! "$PYTHON_BIN" manage.py migrate "${app}" "${alvo}" --noinput > "${SAIDA_MIGRATE}" 2>&1; then
    echo "  ── falhou; últimas linhas de manage.py migrate ──"
    tail -3 "${SAIDA_MIGRATE}" | sed 's/^/  /'
    echo "  ── saída completa em ${SAIDA_MIGRATE} ──"
    instruir_e_sair "não foi possível desfazer ${app} até ${alvo} (migração irreversível ou erro de dados)"
  fi
  sed 's/^/    /' "${SAIDA_MIGRATE}"
done

# Conferência final. Duas razões: o `migrate` pode sair 0 e mesmo assim o estado
# não bater, e um desfazer com vários apps pode ter tombado no meio — o Django
# desfaz uma migração por vez, então dá para o app A voltar e o B parar numa
# irreversível. Aqui isso vira mensagem, não silêncio.
RESTANTE="$(comm -13 <(sort "${ESTADO_MIGRACOES_ANTES}") <(aplicadas_agora | sort) || true)"
if [[ -n "${RESTANTE}" ]]; then
  instruir_e_sair "sobraram migrações aplicadas depois do desfazer: $(tr '\n' ' ' <<< "${RESTANTE}")"
fi

echo "rollback de banco: estado das migrações devolvido ao de antes do deploy."
