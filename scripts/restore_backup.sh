#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  echo "Uso: restore_backup.sh /caminho/gerenciador-*.tar.gz.enc" >&2
  exit 2
fi
: "${DB_NAME:?DB_NAME obrigatório}"
: "${BACKUP_ENCRYPTION_KEY:?BACKUP_ENCRYPTION_KEY obrigatório}"
: "${RESTORE_CONFIRM:?Defina RESTORE_CONFIRM=RESTAURAR para confirmar}"
[[ "${RESTORE_CONFIRM}" == "RESTAURAR" ]] || {
  echo "Confirmação inválida." >&2
  exit 2
}

# Mesma ponte DB_* -> PG* do backup_production.sh, e pelo mesmo motivo: quem
# restaura na VPS tem o .env da aplicação, e `pg_restore` só lê as PG*. Inline
# nos dois porque cada script tem de rodar sozinho a partir do checkout.
export PGHOST="${PGHOST:-${DB_HOST:-127.0.0.1}}"
export PGPORT="${PGPORT:-${DB_PORT:-5432}}"
if [[ -z "${PGUSER:-}" && -n "${DB_USER:-}" ]]; then
  export PGUSER="${DB_USER}"
fi
if [[ -z "${PGPASSWORD:-}" && -n "${DB_PASSWORD:-}" ]]; then
  export PGPASSWORD="${DB_PASSWORD}"
fi

ENCRYPTED="$(readlink -f "$1")"
MEDIA_ROOT="${MEDIA_ROOT:-/var/www/gerenciador-viagens/media}"
WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf -- "${WORK_DIR}"
}
trap cleanup EXIT

sha256sum --check "${ENCRYPTED}.sha256"
openssl enc -d -aes-256-cbc -pbkdf2 \
  -in "${ENCRYPTED}" \
  -out "${WORK_DIR}/backup.tar.gz" \
  -pass env:BACKUP_ENCRYPTION_KEY
mkdir -p "${WORK_DIR}/payload"
tar -C "${WORK_DIR}/payload" -xzf "${WORK_DIR}/backup.tar.gz"
(
  cd "${WORK_DIR}/payload"
  sha256sum --check SHA256SUMS
)

pg_restore --no-password --clean --if-exists --no-owner --dbname="${DB_NAME}" \
  "${WORK_DIR}/payload/database.dump"
mkdir -p "${MEDIA_ROOT}"
tar -C "${MEDIA_ROOT}" -xzf "${WORK_DIR}/payload/media.tar.gz"
