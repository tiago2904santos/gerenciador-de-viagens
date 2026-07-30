#!/usr/bin/env bash
set -Eeuo pipefail
cd /var/www/gerenciador-viagens/app
source /var/www/gerenciador-viagens/venv/bin/activate
set -a; source .env; set +a
export DJANGO_SETTINGS_MODULE=config.settings.prod

git fetch origin main
git checkout --detach origin/main
python -m pip install -r requirements/lock.txt --quiet
python manage.py migrate --noinput
python scripts/build_shell_bundles.py
python manage.py collectstatic --noinput
systemctl restart gerenciador-viagens gerenciador-viagens-celery gerenciador-viagens-celery-beat
sleep 3
systemctl is-active redis-server gerenciador-viagens gerenciador-viagens-celery
git log -1 --oneline

python <<'PY'
import django
django.setup()
from ordens_servico.models import OrdemServico
from ordens_servico.docxtpl_context import build_os_docxtpl_context
from oficios.models import Oficio
from oficios.docxtpl_context import build_oficio_docxtpl_context
ordem = OrdemServico.objects.filter(area_id=1).order_by('-id').first()
oficio = Oficio.objects.filter(area_id=1).order_by('-id').first()
if ordem:
    ctx = build_os_docxtpl_context(ordem)
    print('OS chefia:', ctx.get('nome_chefia'), '|', ctx.get('cargo_chefia'))
if oficio:
    ctx = build_oficio_docxtpl_context(oficio)
    print('Oficio chefia:', ctx.get('nome_chefia'), '|', ctx.get('cargo_chefia'))
    print('Oficio destinatario:', ctx.get('nome_destinatario'), '|', ctx.get('cargo_destinatario'))
PY
curl -sS -o /dev/null -w 'health %{http_code} %{time_total}s\n' --max-time 15 -k https://gerenciadorviagens.tech/health/
