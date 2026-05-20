#!/bin/bash
set -euo pipefail

# Only run in remote Claude Code environments
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 300000}'

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-/home/user/gerenciador-de-viagens}"
cd "$PROJECT_DIR"

# --- Install Python dependencies in virtualenv ---
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install -q --upgrade pip
pip install -q -r requirements/dev.txt

# Export venv to session environment
echo "export VIRTUAL_ENV=$VENV_DIR" >> "$CLAUDE_ENV_FILE"
echo "export PATH=$VENV_DIR/bin:\$PATH" >> "$CLAUDE_ENV_FILE"

# --- Setup .env if not present ---
if [ ! -f "$PROJECT_DIR/.env" ]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  # Override values needed for the remote dev environment
  sed -i 's/^SECRET_KEY=.*/SECRET_KEY=dev-insecure-key-for-remote-session/' "$PROJECT_DIR/.env"
  sed -i 's/^ALLOWED_HOSTS=.*/ALLOWED_HOSTS=127.0.0.1,localhost,0.0.0.0,*/' "$PROJECT_DIR/.env"
  echo "LOGIN_ENFORCED=false" >> "$PROJECT_DIR/.env"
fi

# --- Start PostgreSQL ---
pg_ctlcluster 16 main start 2>/dev/null || true

# Wait for PostgreSQL to be ready
for i in $(seq 1 15); do
  pg_isready -q && break
  sleep 1
done

# --- Create database and user ---
DB_USER_NAME=$(grep -m1 '^DB_USER=' "$PROJECT_DIR/.env" | cut -d= -f2)
DB_PASSWORD_VAL=$(grep -m1 '^DB_PASSWORD=' "$PROJECT_DIR/.env" | cut -d= -f2)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER_NAME'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER $DB_USER_NAME WITH PASSWORD '$DB_PASSWORD_VAL';"

DB_NAME_VAL=$(grep -m1 '^DB_NAME=' "$PROJECT_DIR/.env" | cut -d= -f2)
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME_VAL'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME_VAL OWNER $DB_USER_NAME;"

sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME_VAL TO $DB_USER_NAME;" 2>/dev/null || true

# --- Run migrations ---
"$VENV_DIR/bin/python" manage.py migrate --noinput -v 0

# --- Start Django server in background ---
pkill -f "manage.py runserver" 2>/dev/null || true
nohup "$VENV_DIR/bin/python" manage.py runserver 0.0.0.0:8000 \
  > /tmp/django-server.log 2>&1 &

echo "Django server started on port 8000. Logs: /tmp/django-server.log"
