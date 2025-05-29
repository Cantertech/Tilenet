# your_app_name/admin.py

from django.contrib import admin
# Import other necessary models and classes
from .models import (
    Project, Room, ProjectMaterial, Worker, Unit, Material,
    DynamicSetting, Tile,
    TilingRoomDetails, PaintingRoomDetails,
)
# No need for Sum or ContentType admin imports unless specifically used here

# --- Inlines for Project Admin (Keep as previously corrected) ---
# ... RoomInline, ProjectMaterialInline, WorkerInline classes ...
class RoomInline(admin.TabularInline):
    model = Room
    extra = 0
    readonly_fields = ('floor_area', 'wall_area', 'total_area', 'display_details')
    fields = ('name', 'room_type', 'length', 'breadth', 'height', 'floor_area', 'wall_area', 'total_area', 'display_details')
    show_change_link = True

    def display_details(self, obj):
        if obj.details:
            detail_type = type(obj.details).__name__
            if isinstance(obj.details, TilingRoomDetails):
                details = obj.details
                return f"Tiling: Steps={details.number_of_steps or 0}, Landings={details.number_of_landings or 0}, Metal Strip={details.has_metal_strip}, Stair L={details.stair_length or 0}, Stair B={details.stair_breadth or 0}"
            elif isinstance(obj.details, PaintingRoomDetails):
                details = obj.details
                return f"Painting: Coats={details.num_paint_coats or 0}, Doors={details.door_count or 0} ({details.door_area or 0}/ea), Windows={details.window_count or 0} ({details.window_area or 0}/ea), Surface='{details.surface_type or 'N/A'}'"
            return f"Details: {detail_type}"
        return "-"
    display_details.short_description = 'Details'

class ProjectMaterialInline(admin.TabularInline):
    model = ProjectMaterial
    extra = 0
    readonly_fields = ('quantity_with_wastage',)
    fields = ('material', 'name', 'unit', 'quantity', 'quantity_with_wastage')

class WorkerInline(admin.TabularInline):
    model = Worker
    extra = 0
    readonly_fields = ('coverage_area', 'total_cost')
    fields = ('role', 'count', 'rate', 'rate_type', 'coverage_area', 'special_equipment_cost_per_day', 'total_cost')

# --- Model Admins (Keep as previously corrected, except MaterialAdmin list_filter) ---

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'project_type', 'estimate_number', 'total_area', 'created_at')
    list_filter = ('project_type', 'created_at', 'status')
    search_fields = ('name', 'customer_name', 'estimate_number', 'user__username')
    inlines = [RoomInline, ProjectMaterialInline, WorkerInline]
    readonly_fields = (
        'estimate_number', 'total_area', 'total_labor_cost',
        'cost_per_area', 'estimated_days',
        'created_at', 'updated_at',
    )
    fieldsets = (
        (None, {'fields': ('user', 'name', 'status', 'date', 'estimate_number')}),
        ('Customer Details', {'fields': ('customer_name', 'customer_location', 'customer_phone')}),
        ('Project Details', {'fields': ('project_type', 'measurement_unit', 'description')}),
        ('Financial Settings', {'fields': ('wastage_percentage', 'profit_type', 'profit_value')}),
        ('Calculated Totals', {
            'fields': (
                'total_area', 'estimated_days',
                'total_labor_cost', 'cost_per_area',
            )
        }),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'room_type', 'project', 'floor_area', 'wall_area', 'total_area', 'display_details_summary')
    list_filter = ('room_type', 'project__name')
    search_fields = ('name', 'project__name')
    fields = ('project', 'name', 'room_type', 'length', 'breadth', 'height', 'floor_area', 'wall_area', 'total_area')
    readonly_fields = ('floor_area', 'wall_area', 'total_area', 'display_details_summary')

    def display_details_summary(self, obj):
        if obj.details:
            if isinstance(obj.details, TilingRoomDetails):
                details = obj.details
                return f"Tiling: Steps={details.number_of_steps or 0}, Landings={details.number_of_landings or 0}, Metal Strip={details.has_metal_strip}, Stair L={details.stair_length or 0}, Stair B={details.stair_breadth or 0}"
            elif isinstance(obj.details, PaintingRoomDetails):
                details = obj.details
                return f"Painting: Coats={details.num_paint_coats or 0}, Doors={details.door_count or 0} ({details.door_area or 0}/ea), Windows={details.window_count or 0} ({details.window_area or 0}/ea), Surface='{details.surface_type or 'N/A'}'"
            return f"Details: {type(obj.details).__name__}"
        return "-"
    display_details_summary.short_description = 'Details'


@admin.register(ProjectMaterial)
class ProjectMaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'project', 'material', 'unit', 'quantity', 'quantity_with_wastage')
    list_filter = ('project__name', 'material__name')
    search_fields = ('name', 'project__name', 'material__name')
    fields = ('project', 'material', 'name', 'unit', 'quantity', 'quantity_with_wastage',)
    readonly_fields = ('quantity_with_wastage',)


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('role', 'project', 'count', 'rate', 'rate_type', 'coverage_area', 'total_cost')
    list_filter = ('role', 'project__name', 'rate_type')
    search_fields = ('project__name', 'role')
    fields = ('project', 'role', 'count', 'rate', 'rate_type', 'coverage_area', 'special_equipment_cost_per_day', 'total_cost')
    readonly_fields = ('coverage_area', 'total_cost')

# --- Admin registrations for other models ---

@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'abbreviation')
    search_fields = ('name', 'abbreviation')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'unit',  'default_coverage_area')

    # CORRECTED AGAIN: Use the field name 'user' directly.
    # Django admin will automatically provide the __isnull filter options.
    list_filter = ('user', 'unit__name') # Changed from 'user__isnull'

    search_fields = ('name', 'user__username')
    fields = ('user', 'name', 'unit', 'default_unit_price', 'default_coverage_area')


@admin.register(DynamicSetting)
class DynamicSettingAdmin(admin.ModelAdmin):
    list_display = ('user', 'default_wall_coverage_rate', 'default_floor_coverage_rate', 'default_additional_days')
    search_fields = ('user__username',)
    readonly_fields = ('user',)


@admin.register(Tile)
class TileAdmin(admin.ModelAdmin):
    list_display = ('id', 'processed_image', 'uploaded_at')
    readonly_fields = ('uploaded_at',)
    # Keep or add image preview if needed
    # ... image_tag method ...
    # fields = ('processed_image', 'image_tag', 'uploaded_at')
    # readonly_fields = ('uploaded_at', 'image_tag')