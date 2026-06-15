import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "susi_project.settings")
django.setup()