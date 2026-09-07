import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_homework.settings")

try:
    from celery import Celery

    app = Celery("django_homework")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()
except ImportError:  # pragma: no cover
    app = None
