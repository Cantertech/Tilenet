import os
import traceback
import sys

from django.core.wsgi import get_wsgi_application

try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tile_estimator.settings') # This should be 'tile_estimator.settings'
    application = get_wsgi_application()
except Exception as e:
    # Log the full traceback to stderr
    print("--- Django WSGI Application Load Error ---", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print("--- End of Error ---", file=sys.stderr)

    # Re-raise the exception so Gunicorn still knows the worker failed
    raise