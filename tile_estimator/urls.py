
"""
URL Configuration for tile_estimator project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.urls import path

import logging
logger = logging.getLogger(__name__)

def health_check(request):
    logger.info("Health check called")
    return HttpResponse("OK")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', health_check),
    path('api/admin/', include('admin_api.urls')),
    path('api/user/', include('accounts.urls')),
    path('api/estimates/', include('estimates.urls')),
    path('api/subscriptions/', include('subscriptions.urls')),
    path('api/suppliers/', include('suppliers.urls')),
    path('api/manual_estimate/',include('manual_estimate.urls')),
    path('api/projects/', include('projects.urls')),  # New projects URLs
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
