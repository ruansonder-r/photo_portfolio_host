"""WSGI entry point.

WhiteNoise is installed as middleware (see settings.MIDDLEWARE), so static
files are served by this same application -- no separate static host needed.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "photo_portfolio.settings")

application = get_wsgi_application()
app = application  # Vercel looks for `app`
