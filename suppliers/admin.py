
from django.contrib import admin
from .models import Supplier, SupplierProduct, Order, OrderItem, SupplierReview

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'is_verified', 'rating')
    list_filter = ('is_verified', 'city')
    search_fields = ('name', 'description', 'address', 'city')

@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'price', 'unit', 'category', 'in_stock')
    list_filter = ('category', 'in_stock', 'supplier')
    search_fields = ('name', 'description', 'supplier__name')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'supplier', 'status', 'subtotal', 'total', 'created_at')
    list_filter = ('status', 'payment_method', 'created_at')
    search_fields = ('user__username', 'user__email', 'supplier__name', 'payment_reference')
    inlines = [OrderItemInline]

@admin.register(SupplierReview)
class SupplierReviewAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'user', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('supplier__name', 'user__username', 'comment')
