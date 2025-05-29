
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'products', views.SupplierProductViewSet, basename='supplier-product')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'reviews', views.SupplierReviewViewSet, basename='supplier-review')

urlpatterns = [
    path('', include(router.urls)),
]
