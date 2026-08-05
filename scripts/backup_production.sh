#!/usr/bin/env bash
set -euo pipefail

: "${DB_NAME:?DB_NAME obrigatório}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY obrigatório}"

# pg_dump lê PGHOST/PGPORT/PGUSER/PGPASSWORD, nunca DB_*. Quem chama isto com
# o .env da aplicação (cron diário, execução manual na VPS) só tem DB_*, e sem
# esta ponte o pg_dump tenta o socket Unix usando o usuário do SO como role —
# que não existe no Postgres. Quem já exporta PG* explicitamente continua
# mandando: é o caso do CI, que fala com um service container por TCP.
export PGHOST="${PGHOST:-${DB_HOST:-127.0.0.1}}"
export PGPORT="${PGPORT:-${DB_PORT:-5432}}"
if [[ -z "${PGUSER:-}" && -n "${DB_USER:-}" ]]; then
  export PGUSER="${DB_USER}"
fi
if [[ -z "${PGPASSWORD:-}" && -n "${DB_PASSWORD:-}" ]]; then
  export PGPASSWORD="${DB_PASSWORD}"
fi

APP_ROOT="${APP_ROOT:-/var/www/gerenciador-viagens/app}"
MEDIA_ROOT="${MEDIA_ROOT:-/var/www/gerenciador-viagens/media}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/gerenciador-viagens}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="${BACKUP_ROOT}/gerenciador-${STAMP}.tar.gz"
ENCRYPTED="${ARCHIVE}.enc"

# O diretório pai precisa existir antes do mktemp; sem isto o deploy
# aborta com "No such file or directory" na VPS nova.
mkdir -p -- "${BACKUP_ROOT}"
WORK_DIR="$(mktemp -d "${BACKUP_ROOT}/.backup-${STAMP}-XXXXXX")"

cleanup() {
  rm -rf -- "${WORK_DIR}"
}
trap cleanup EXIT

# --no-password: sem terminal, a senha ausente vira prompt que só morre no
# command_timeout do deploy (10 min). Falhar na hora diz o que faltou.
pg_dump --no-password --format=custom \
  --file="${WORK_DIR}/database.dump" "${DB_NAME}"
tar -C "${MEDIA_ROOT}" -czf "${WORK_DIR}/media.tar.gz" .
git -C "${APP_ROOT}" rev-parse HEAD > "${WORK_DIR}/commit-sha.txt"
(
  cd "${WORK_DIR}"
  sha256sum database.dump media.tar.gz commit-sha.txt > SHA256SUMS
)
tar -C "${WORK_DIR}" -czf "${ARCHIVE}" .
openssl enc -aes-256-cbc -pbkdf2 -salt \
  -in "${ARCHIVE}" \
  -out "${ENCRYPTED}" \
  -pass env:BACKUP_ENCRYPTION_KEY
sha256sum "${ENCRYPTED}" > "${ENCRYPTED}.sha256"
rm -f -- "${ARCHIVE}"

# Segunda cópia fora do host, quando o remote institucional estiver definido.
if [[ -n "${BACKUP_RCLONE_REMOTE:-}" ]]; then
  rclone copy "${ENCRYPTED}" "${ENCRYPTED}.sha256" "${BACKUP_RCLONE_REMOTE}"
fi

find "${BACKUP_ROOT}" -maxdepth 1 -type f \
  \( -name 'gerenciador-*.tar.gz.enc' -o -name 'gerenciador-*.tar.gz.enc.sha256' \) \
  -mtime "+${RETENTION_DAYS}" -delete

printf '%s\n' "${ENCRYPTED}"
