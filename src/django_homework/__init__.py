"""
django_homework package initialization.
"""

__version__ = "0.1.0"

try:
    from .celery import app as celery_app
    __all__ = ("celery_app",)
except ImportError:  # pragma: no cover
    pass


def main() -> None:
    """CLI entrypoint delegating to Django management."""
    import os
    import sys
    from pathlib import Path

    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    src_dir = BASE_DIR / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_homework.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
