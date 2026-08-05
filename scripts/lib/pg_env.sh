# shellcheck shell=bash
# Traduz as variáveis de banco da aplicação (DB_*, do .env) para as que o
# cliente libpq realmente lê (PG*). Sem isto, `pg_dump`/`pg_restore` ignoram o
# .env, caem no socket Unix local e tentam autenticar com o usuário do SO —
# que em produção é o usuário do SSH e não existe como role (`NOVO-55`).
#
# Quem já define PG* explicitamente vence: é assim que o drill de restore do CI
# aponta para o service container do Postgres sem depender de um .env.
_pg_env_from_db_vars() {
  if [[ -z "${PGHOST:-}" && -n "${DB_HOST:-}" ]]; then
    export PGHOST="${DB_HOST}"
  fi
  if [[ -z "${PGPORT:-}" && -n "${DB_PORT:-}" ]]; then
    export PGPORT="${DB_PORT}"
  fi
  if [[ -z "${PGUSER:-}" && -n "${DB_USER:-}" ]]; then
    export PGUSER="${DB_USER}"
  fi
  if [[ -z "${PGPASSWORD:-}" && -n "${DB_PASSWORD:-}" ]]; then
    export PGPASSWORD="${DB_PASSWORD}"
  fi
}

_pg_env_from_db_vars
