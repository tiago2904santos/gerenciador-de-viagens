#!/usr/bin/env bash
# =============================================================================
# deploy_update.sh — Atualiza o codigo e reinicia o servico
# Execute como root ou com sudo a cada novo deploy
# =============================================================================
set -euo pipefail

APP_USER="viagens"
APP_DIR="/var/www/gerenciador-viagens/app"
VENV_DIR="/var/www/gerenciador-viagens/venv"
PYTHON="python3.12"

echo "==> Ativando venv..."
if [ ! -d "${VENV_DIR}" ]; then
    ${PYTHON} -m venv ${VENV_DIR}
fi
source ${VENV_DIR}/bin/activate

echo "==> Instalando dependencias Python..."
pip install --quiet --upgrade pip
pip install --quiet -r ${APP_DIR}/requirements/prod.txt

echo "==> Rodando migrations..."
cd ${APP_DIR}
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py migrate --noinput

echo "==> Coletando arquivos estaticos..."
DJANGO_SETTINGS_MODULE=config.settings.prod python manage.py collectstatic --noinput --clear

echo "==> Ajustando permissoes..."
chown -R ${APP_USER}:${APP_USER} /var/www/gerenciador-viagens/

echo "==> Reiniciando servico..."
systemctl restart gerenciador-viagens
systemctl status gerenciador-viagens --no-pager

echo "==> Deploy concluido com sucesso."
