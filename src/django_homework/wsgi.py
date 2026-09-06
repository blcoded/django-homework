"""
WSGI config for django_homework project.
"""

import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application

BASE_DIR = Path(__file__).resolve().parent.parent.parent
src_dir = BASE_DIR / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_homework.settings")

application = get_wsgi_application()
