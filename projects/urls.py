from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'projects', views.ProjectViewSet, basename='project')
router.register(r'units', views.UnitViewSet, basename='unit')
router.register(r'materials', views.MaterialViewSet, basename='material')
router.register(r'project-materials', views.ProjectMaterialViewSet, basename='projectmaterial')
router.register(r'workers', views.WorkerViewSet, basename='worker')
router.register(r'rooms', views.RoomViewSet, basename='room')

custom_urlpatterns = [
    path('estimate/calculate/', views.CreateProjectEstimateView.as_view(), name='create-project-estimate'),
    path('subscription/projects-left/', views.projects_left, name='get-projects-left'),
    path('rooms/3d/update/', views.update_3d_room, name='update-3d-room'),
    path('rooms/3d/generate/', views.generate_3d_room_view, name='generate-3d-room'),
    path('settings/update/', views.update_settings, name='update-user-settings'),
    path('estimate/pdf/generate/', views.generate_estimatepdf, name='generate-estimate-pdf'),
    path('tile-image/process/', views.process_tile_image, name='process-tile-image'),
    path('rooms/3d/manual/',views.generate_manual_estimate_pdf, name ="manual pdf generations"),
    path('<int:pk>/update-status/', views.update_project_status, name='update-project-status'),
]

urlpatterns = [
    path('', include(router.urls)),
    *custom_urlpatterns,
]