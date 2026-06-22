import os

from django.core.wsgi import get_wsgi_application

# Em producao defina DJANGO_SETTINGS_MODULE=config.settings.prod via .env ou systemd.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_wsgi_application()
