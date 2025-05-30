import os
import traceback
import sys
import logging # Add this line
from django.core.wsgi import get_wsgi_application

logger = logging.getLogger(__name__) # Add this line

try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tile_estimator.settings')
    logger.info("Starting get_wsgi_application()") # Add this
    application = get_wsgi_application()
    logger.info("Finished get_wsgi_application()") # Add this
except Exception as e:
    print("--- Django WSGI Application Load Error ---", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    print("--- End of Error ---", file=sys.stderr)
    raise