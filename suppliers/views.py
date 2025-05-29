
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from .models import Supplier, SupplierProduct, Order, SupplierReview
from .serializers import (
    SupplierSerializer, SupplierDetailSerializer, SupplierProductSerializer,
    OrderSerializer, SupplierReviewSerializer
)

class SupplierViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for viewing suppliers"""
    queryset = Supplier.objects.filter(is_verified=True)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['city']
    search_fields = ['name', 'description', 'city']
    ordering_fields = ['name', 'rating', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return SupplierDetailSerializer
        return SupplierSerializer
    
    def get_permissions(self):
        """Anyone can view suppliers"""
        return [AllowAny()]
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get products for a specific supplier"""
        supplier = self.get_object()
        products = supplier.products.filter(in_stock=True)
        serializer = SupplierProductSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get reviews for a specific supplier"""
        supplier = self.get_object()
        reviews = supplier.reviews.all().order_by('-created_at')
        serializer = SupplierReviewSerializer(reviews, many=True)
        return Response(serializer.data)

class SupplierProductViewSet(viewsets.ReadOnlyModelViewSet):
    """API endpoint for viewing supplier products"""
    queryset = SupplierProduct.objects.filter(in_stock=True)
    serializer_class = SupplierProductSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'category', 'in_stock']
    search_fields = ['name', 'description', 'category']
    ordering_fields = ['name', 'price', 'created_at']
    
    def get_permissions(self):
        """Anyone can view products"""
        return [AllowAny()]

class OrderViewSet(viewsets.ModelViewSet):
    """API endpoint for managing orders"""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Only show user's own orders"""
        return Order.objects.filter(user=self.request.user).order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order"""
        order = self.get_object()
        
        # Only pending or confirmed orders can be cancelled
        if order.status not in ['pending', 'confirmed']:
            return Response(
                {"detail": "Only pending or confirmed orders can be cancelled."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        return Response({"detail": "Order cancelled successfully."})

class SupplierReviewViewSet(viewsets.ModelViewSet):
    """API endpoint for managing supplier reviews"""
    serializer_class = SupplierReviewSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SupplierReview.objects.filter(user=self.request.user)
