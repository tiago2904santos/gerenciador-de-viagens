#!/usr/bin/env bash
# =============================================================================
# deploy_setup.sh — Configuracao inicial do VPS (rode uma vez como root)
# Ubuntu 22.04 / 24.04 LTS
# =============================================================================
set -euo pipefail

APP_USER="viagens"
APP_DIR="/var/www/gerenciador-viagens"
PYTHON_VERSION="3.12"
DB_NAME="viagens_prod"
DB_USER="viagens_user"

echo "==> Atualizando pacotes..."
apt-get update -qq && apt-get upgrade -y -qq

echo "==> Instalando dependencias do sistema..."
apt-get install -y -qq \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-venv \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    build-essential \
    libpq-dev \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    libcairo2 \
    libgdk-pixbuf2.0-0 \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core

echo "==> Criando usuario da aplicacao..."
id -u ${APP_USER} &>/dev/null || useradd --system --shell /bin/bash --home ${APP_DIR} ${APP_USER}

echo "==> Criando diretorios..."
mkdir -p ${APP_DIR}/{media,staticfiles,media/tmp_documentos}
chown -R ${APP_USER}:${APP_USER} ${APP_DIR}

echo "==> Configurando PostgreSQL..."
sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD 'TROQUE-ESTA-SENHA';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" 2>/dev/null || true

echo ""
echo "==> Sistema pronto. Proximos passos:"
echo "    1. Clone o repositorio em ${APP_DIR}/app"
echo "    2. Configure ${APP_DIR}/app/.env (use .env.production.example como base)"
echo "    3. Execute: sudo bash scripts/deploy_update.sh"
echo "    4. Configure Nginx e systemd (veja docs/DEPLOY_VPS.md)"
