
from django.contrib import admin
from .models import Material, QuickEstimate, EstimateMaterial

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'unit_price', 'project_type')
    list_filter = ('project_type',)
    search_fields = ('name', 'description')

class EstimateMaterialInline(admin.TabularInline):
    model = EstimateMaterial
    extra = 0
    readonly_fields = ('total_price',)

@admin.register(QuickEstimate)
class QuickEstimateAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'project_type', 'room_type', 'total_area', 'estimated_cost', 'created_at')
    list_filter = ('project_type', 'room_type', 'created_at')
    search_fields = ('name', 'user__username', 'user__email')
    readonly_fields = ('total_area', 'estimated_cost', 'created_at', 'updated_at')
    inlines = [EstimateMaterialInline]
    
    fieldsets = (
        (None, {
            'fields': ('user', 'name', 'project_type', 'room_type')
        }),
        ('Dimensions', {
            'fields': ('measurement_unit', 'length', 'breadth', 'height', 'floor_thickness')
        }),
        ('Wastage', {
            'fields': ('auto_wastage', 'manual_wastage_factor')
        }),
        ('Results', {
            'fields': ('total_area', 'estimated_cost', 'created_at', 'updated_at')
        }),
    )
