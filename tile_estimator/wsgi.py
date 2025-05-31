import os
import sys
import logging

logger = logging.getLogger(__name__)

# This is our simple, callable WSGI application
def application(environ, start_response):
    # This log will appear if a request actually reaches this function
    logger.info("Test WSGI app received request.")
    status = '200 OK'
    headers = [('Content-type', 'text/plain')]
    start_response(status, headers)
    return [b"Hello, Railway! This is a test app."]

# This log will appear if the wsgi.py file is successfully loaded by Gunicorn
logger.info("Minimal WSGI application defined and ready.")

# IMPORTANT: We are temporarily commenting out/removing all Django-related setup.
# This ensures Django is NOT loaded during this test, focusing only on Gunicorn's
# ability to run a basic Python web application.
# try:
#     os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project_name.settings')
#     from django.core.wsgi import get_wsgi_application
#     application = get_wsgi_application()
# except Exception as e:
#     import traceback
#     print("--- Django WSGI Application Load Error (Test) ---", file=sys.stderr)
#     traceback.print_exc(file=sys.stderr)
#     print("--- End of Error (Test) ---", file=sys.stderr)
#     raise