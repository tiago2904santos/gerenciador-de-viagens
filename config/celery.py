import os

from celery import Celery

# Em producao defina DJANGO_SETTINGS_MODULE=config.settings.prod via .env ou systemd.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("gerenciador_de_viagens")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
