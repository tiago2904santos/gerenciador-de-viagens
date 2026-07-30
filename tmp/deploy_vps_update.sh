#!/usr/bin/env bash
set -Eeuo pipefail

cd /var/www/gerenciador-viagens/app
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="/var/backups/gerenciador-viagens/manual-${STAMP}"
mkdir -p "${BACKUP}"

echo "=== backup .env + docx + HEAD ==="
cp -a .env "${BACKUP}/env"
cp -a documentos/resources "${BACKUP}/resources"
git rev-parse HEAD > "${BACKUP}/before-sha.txt"

set -a
source .env
set +a

echo "=== backup database ==="
PGPASSWORD="${DB_PASSWORD}" pg_dump \
  -h "${DB_HOST:-127.0.0.1}" \
  -p "${DB_PORT:-5432}" \
  -U "${DB_USER}" \
  -d "${DB_NAME}" \
  -Fc -f "${BACKUP}/database.dump"
echo "backup ok: ${BACKUP}"
ls -lah "${BACKUP}"

echo "=== ensure redis up ==="
systemctl enable --now redis-server
systemctl is-active redis-server
redis-cli ping

BEFORE="$(git rev-parse HEAD)"
git fetch origin main
TARGET="$(git rev-parse origin/main)"
echo "BEFORE=${BEFORE}"
echo "TARGET=${TARGET}"

echo "=== checkout origin/main ==="
git checkout -- core/views.py || true
rm -f celerybeat-schedule celerybeat-schedule.db || true
git checkout --detach "${TARGET}"

echo "=== pip install ==="
source /var/www/gerenciador-viagens/venv/bin/activate
python -m pip install -r requirements/lock.txt --quiet

echo "=== migrate ==="
export DJANGO_SETTINGS_MODULE=config.settings.prod
python manage.py migrate --noinput

echo "=== shell bundles (NOVO-12) ==="
python scripts/build_shell_bundles.py

echo "=== collectstatic ==="
python manage.py collectstatic --noinput

echo "=== ensure celery units ==="
if [ ! -f /etc/systemd/system/gerenciador-viagens-celery.service ]; then
  cat > /etc/systemd/system/gerenciador-viagens-celery.service << 'EOF'
[Unit]
Description=Gerenciador de Viagens — Celery worker
After=network.target redis-server.service
Requires=redis-server.service

[Service]
User=root
Group=root
WorkingDirectory=/var/www/gerenciador-viagens/app
EnvironmentFile=/var/www/gerenciador-viagens/app/.env
Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
ExecStart=/var/www/gerenciador-viagens/venv/bin/celery -A config worker --loglevel=info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
fi

if [ ! -f /etc/systemd/system/gerenciador-viagens-celery-beat.service ]; then
  cat > /etc/systemd/system/gerenciador-viagens-celery-beat.service << 'EOF'
[Unit]
Description=Gerenciador de Viagens — Celery beat
After=network.target redis-server.service
Requires=redis-server.service

[Service]
User=root
Group=root
WorkingDirectory=/var/www/gerenciador-viagens/app
EnvironmentFile=/var/www/gerenciador-viagens/app/.env
Environment=DJANGO_SETTINGS_MODULE=config.settings.prod
ExecStart=/var/www/gerenciador-viagens/venv/bin/celery -A config beat --loglevel=info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
fi

# Garantir vars Redis/Celery no .env
grep -q '^REDIS_URL=' .env || echo 'REDIS_URL=redis://127.0.0.1:6379/1' >> .env
grep -q '^CELERY_BROKER_URL=' .env || echo 'CELERY_BROKER_URL=redis://127.0.0.1:6379/0' >> .env
grep -q '^CELERY_RESULT_BACKEND=' .env || echo 'CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0' >> .env
grep -qE '^FIELD_ENCRYPTION_KEYS=.+' .env || {
  echo "ERRO: FIELD_ENCRYPTION_KEYS ausente no .env" >&2
  exit 1
}

systemctl daemon-reload
systemctl enable --now redis-server gerenciador-viagens-celery gerenciador-viagens-celery-beat
systemctl restart gerenciador-viagens gerenciador-viagens-celery gerenciador-viagens-celery-beat
sleep 4

echo "=== health ==="
systemctl is-active redis-server gerenciador-viagens gerenciador-viagens-celery gerenciador-viagens-celery-beat
curl -sS -o /dev/null -w 'health_https %{http_code} %{time_total}s\n' --max-time 15 -k https://gerenciadorviagens.tech/health/
curl -sS -o /dev/null -w 'login_https %{http_code} %{time_total}s\n' --max-time 15 -k https://gerenciadorviagens.tech/login/

echo "=== HEAD + docx ==="
git log -1 --oneline
ls -la documentos/resources/oficio.docx documentos/resources/ordem_servico.docx documentos/resources/ordem_servico_modelos.docx
echo "DONE backup=${BACKUP}"
