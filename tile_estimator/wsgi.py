import os
import sys
import logging
logger = logging.getLogger(__name__)


# Remove the Django setup for this test
from django.core.wsgi import get_wsgi_application
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tile_estimator.settings')
    logger.info("Starting get_wsgi_application()")
    application = get_wsgi_application()
    logger.info("Finished get_wsgi_application()")
except Exception as e:
    import traceback
    print("--- Django WSGI Application Load Error ---", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print("--- End of Error ---", file=sys.stderr)
    raise