try:
    from .celery import app as celery_app
except ModuleNotFoundError:
    # Celery não instalado (ex.: dev local sem broker). O app roda normalmente;
    # o retry em segundo plano fica indisponível e os uploads viram pendência.
    celery_app = None

__all__ = ("celery_app",)
