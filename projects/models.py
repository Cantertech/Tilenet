# your_app_name/models.py

from django.db import models
from django.conf import settings
from django.db.models import JSONField
from django.utils.translation import gettext_lazy as _
from datetime import date
import decimal
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

# Default constants (used by calculations in views)
DEFAULT_WALL_COVERAGE_RATE = decimal.Decimal(12.0)
DEFAULT_FLOOR_COVERAGE_RATE = decimal.Decimal(14.0)
DEFAULT_ADDITIONAL_DAYS = 0
HOURS_PER_WORKDAY = decimal.Decimal(8)

INITIAL_DEFAULT_ROLE_COVERAGE_DATA = {
    'tiler': {'floor': float(DEFAULT_FLOOR_COVERAGE_RATE), 'wall': float(DEFAULT_WALL_COVERAGE_RATE)},
    'master': {'floor': 14.0, 'wall': 12.0},
    'labourer': {'floor': 0.0, 'wall': 0.0},
    'painter': {'wall': float(DEFAULT_WALL_COVERAGE_RATE), 'floor': 0.0},
    'default': {'floor': 10.0, 'wall': 10.0},
}

def get_default_role_coverage_data():
    return INITIAL_DEFAULT_ROLE_COVERAGE_DATA.copy()


# --- Catalogue Models ---

class Unit(models.Model):
    """Units of measurement for materials (e.g., sqm, liter, bag)"""
    name = models.CharField(max_length=50, unique=True, verbose_name=_("Name"))
    abbreviation = models.CharField(max_length=10, blank=True, verbose_name=_("Abbreviation"))

    class Meta:
        verbose_name = _("Unit")
        verbose_name_plural = _("Units")
        ordering = ['name']

    def __str__(self):
        return self.name


class Material(models.Model):
    """A catalogue of materials available (can be global or user-specific)"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_materials',
        null=True,
        blank=True,
        help_text=_("Leave blank for a global material."),
        verbose_name=_("User")
    )
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Unit"))
    default_unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Default Unit Price"))
    default_coverage_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Default Coverage Area per Unit"),
        help_text=_("Default area covered per unit (e.g., sqm per liter).")
    )

    class Meta:
        verbose_name = _("Material")
        verbose_name_plural = _("Materials")
        unique_together = ('user', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.unit.abbreviation if self.unit else 'N/A'})"


# --- Project Settings ---

class DynamicSetting(models.Model):
    """User-specific default settings (used by calculations in views)"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="settings",
        verbose_name=_("User")
    )
    default_wall_coverage_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=DEFAULT_WALL_COVERAGE_RATE,
        verbose_name=_("Default Wall Coverage Rate"),
        help_text=_("Default wall area covered per worker group per day (e.g., sqm/day).")
    )
    default_floor_coverage_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=DEFAULT_FLOOR_COVERAGE_RATE,
        verbose_name=_("Default Floor Coverage Rate"),
        help_text=_("Default floor area covered per worker group per day (e.g., sqm/day).")
    )
    default_additional_days = models.IntegerField(
        default=DEFAULT_ADDITIONAL_DAYS,
        verbose_name=_("Default Additional Days"),
        help_text=_("Default number of additional buffer days for projects.")
    )
    default_painter_coverage_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        verbose_name=_("Default Painter Coverage Rate"),
        help_text=_("Default wall/ceiling area covered per painter per day (e.g., sqm/day).")
    )

    role_coverage_defaults = JSONField(
        default=get_default_role_coverage_data, # Set the initial default data structure
        verbose_name=_("Role Coverage Defaults"),
        help_text=_("JSON structure defining default coverage rates per worker role and work type (floor/wall).")
    )

    class Meta:
        verbose_name = _("Dynamic Setting")
        verbose_name_plural = _("Dynamic Settings")

    def __str__(self):
        return f"{self.user.username}'s Settings"


# --- Core Project Models ---

class Project(models.Model):
    """Model representing a project estimation."""

    PROJECT_TYPE_CHOICES = [
        ('tiling', _('Tiling')),
        ('pavement', _('Pavement')),
        ('masonry', _('Masonry')),
        ('carpentry', _('Carpentry')),
        ('painting', _('Painting')),
        ('plumbing', _('Plumbing')),
        ('others', _('Others')),
    ]

    MEASUREMENT_UNIT_CHOICES = [
        ('meters', _('Meters')),
        ('feet', _('Feet')),
        ('inches', _('Inches')),
        ('centimeters', _('Centimeters')),
    ]

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects',
        verbose_name=_("User")
    )
    name = models.CharField(max_length=255, verbose_name=_("Project Name"))
    estimate_number = models.CharField(max_length=50, unique=True, blank=True, verbose_name=_("Estimate Number"))
    date = models.DateField(default=date.today, verbose_name=_("Project Date"))
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status")
    )
    location = models.CharField(max_length=255, blank=True, verbose_name=_("project Location"))

    customer_name = models.CharField(max_length=255, blank=True, verbose_name=_("Customer Name"))
    customer_location = models.CharField(max_length=255, blank=True, verbose_name=_("Location"))
    customer_phone = models.CharField(max_length=50, blank=True, verbose_name=_("Phone Number"))

    project_type = models.CharField(
        max_length=20,
        choices=PROJECT_TYPE_CHOICES,
        default='tiling',
        verbose_name=_("Project Type")
    )
    measurement_unit = models.CharField(
        max_length=20,
        choices=MEASUREMENT_UNIT_CHOICES,
        default='meters',
        verbose_name=_("Measurement Unit")
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))

    wastage_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=decimal.Decimal(10),
        verbose_name=_("Wastage Percentage (%)"),
        help_text=_("Percentage added to material quantities for wastage.")
    )
    mortar_thickness = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=decimal.Decimal(10),
        verbose_name=_("Mortar thickness)"),
        help_text=_("The thcikness of the cement to be added.")
    )

    PROFIT_TYPE_CHOICES = [
        ('percentage', _('Percentage')),
        ('fixed', _('Fixed Amount')),
        ('per_area', _('Per Unit Area')),
    ]
    profit_type = models.CharField(
        max_length=20,
        choices=PROFIT_TYPE_CHOICES,
        default='percentage',
        verbose_name=_("Profit Type")
    )
    profit_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=decimal.Decimal(0),
        verbose_name=_("Profit Value")
    )
   
    total_floor_area = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=decimal.Decimal(0),
        verbose_name=_("Total Floor Area")
    )
    total_wall_area = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=decimal.Decimal(0),
        verbose_name=_("Total Wall Area")
    )
    total_area = models.DecimalField(max_digits=14, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("Total Area Calculated"))
    total_labor_cost = models.DecimalField(max_digits=16, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("Total Labor Cost"))
    cost_per_area = models.DecimalField(max_digits=12, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("Cost Per Unit Area"))
    estimated_days = models.IntegerField(default=1, verbose_name=_("Estimated Days"))
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("profit"))
    created_at = models.DateTimeField(auto_now_add=True)
    transport = models.DecimalField(max_digits=14, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("Transport"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Project")
        verbose_name_plural = _("Projects")
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.name} ({self.estimate_number})"

    def save(self, *args, **kwargs):
        if not self.estimate_number:
            prefix = 'EST'
            last_project = Project.objects.order_by('id').last()
            next_id = 1 if last_project is None else last_project.id + 1
            self.estimate_number = f"{prefix}-{next_id:06d}"

        super().save(*args, **kwargs)

class BaseRoomDetails(models.Model):
    """
    Abstract base model for project type-specific room details (data only).
    Concrete models inherit from this and define their unique fields.
    Calculations using these fields happen externally (e.g., in views).
    """
    # Fields for GenericForeignKey linkage
    room_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    room_object_id = models.PositiveIntegerField()
    room = GenericForeignKey('room_content_type', 'room_object_id')

    class Meta:
        abstract = True


# --- Concrete Room Details Models (Pure Data Containers) ---

class TilingRoomDetails(BaseRoomDetails):
    """Details for a Room in a Tiling project (data only)."""
    stair_length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Stair Length"))
    stair_breadth = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Stair Breadth"))
    number_of_steps = models.IntegerField(null=True, blank=True, verbose_name=_("Number of Steps"))
    landing_length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Landing Length"))
    landing_breadth = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Landing Breadth"))
    number_of_landings = models.IntegerField(null=True, blank=True, verbose_name=_("Number of Landings"))
    has_metal_strip = models.BooleanField(default=False, verbose_name=_("Has Metal Strip"))

    class Meta:
        verbose_name = _("Tiling Room Details")
        verbose_name_plural = _("Tiling Room Details")

    def __str__(self):
        return f"Tiling Details for {self.room.name if self.room else 'Unnamed Room'}"
    
    def calculate_area_details(self, room_instance):
 
        floor_area = room_instance.length * room_instance.breadth if room_instance.length is not None and room_instance.breadth is not None else decimal.Decimal(0)
        perimeter = 2 * (room_instance.length + room_instance.breadth) if room_instance.length is not None and room_instance.breadth is not None else decimal.Decimal(0)
        wall_area = perimeter * room_instance.height if perimeter > 0 and room_instance.height is not None else decimal.Decimal(0)

        total_area = floor_area + wall_area # Adjust if total_area is calculated differently

        return floor_area, wall_area, total_area


class PaintingRoomDetails(BaseRoomDetails):
    """Details for a Room in a Painting project (data only)."""
    door_count = models.IntegerField(null=True, blank=True, verbose_name=_("Number of Doors"))
    door_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Area per Door"), help_text=_("Area to subtract from wall area for one door."))
    window_count = models.IntegerField(null=True, blank=True, verbose_name=_("Number of Windows"))
    window_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Area per Window"), help_text=_("Area to subtract from wall area for one window."))
    num_paint_coats = models.IntegerField(null=True, blank=True, verbose_name=_("Number of Paint Coats"))
    surface_type = models.CharField(max_length=100, blank=True, verbose_name=_("Surface Type"))

    class Meta:
        verbose_name = _("Painting Room Details")
        verbose_name_plural = _("Painting Room Details")

    def __str__(self):
        return f"Painting Details for {self.room.name if self.room else 'Unnamed Room'}"

# Add other *RoomDetails models here for different project types


class Room(models.Model):
    """
    A room or area within a project. Links to type-specific details (data only)
    using Content Types. Calculations happen externally (e.g., in views).
    """

    ROOM_TYPE_CHOICES = [
        ('bathroom', _('Bathroom')),
        ('living_room', _('Living Room')),
        ('corridor', _('Corridor')),
        ('bedroom', _('Bedroom')),
        ('compound', _('Compound')),
        ('porch', _('Porch')),
        ('dining', _('Dining')),
        ('fence_wall', _('Fence Wall')),
        ('kitchen', _('Kitchen')),
        ('master_bedroom', _('Master Bedroom')),
        ('staircase', _('Staircase')),
        ('other', _('Other')),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='rooms',
        verbose_name=_("Project")
    )
    name = models.CharField(max_length=100, verbose_name=_("Room/Area Name"))
    room_type = models.CharField(
        max_length=20,
        choices=ROOM_TYPE_CHOICES,
        default='other',
        verbose_name=_("Room Type")
    )

    length = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Length"))
    breadth = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Breadth"))
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name=_("Height"))

    # Generic Foreign Key to Room Details (Data only)
    details_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'model__in': ('tilingroomdetails', 'paintingroomdetails')}, # Limit to our details models
        verbose_name=_("Details Type")
    )
    details_object_id = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("Details ID"))
    details = GenericForeignKey('details_content_type', 'details_object_id')

    # Stored fields for calculated areas (values set by views/external logic)
    floor_area = models.DecimalField(max_digits=14, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("Floor Area Calculated"))
    wall_area = models.DecimalField(max_digits=14, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("Wall Area Calculated"))
    total_area = models.DecimalField(max_digits=14, decimal_places=2, default=decimal.Decimal(0), verbose_name=_("Total Area Calculated"))


    class Meta:
        verbose_name = _("Room")
        verbose_name_plural = _("Rooms")
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()})"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)

        if is_new and self.project and not self.details: # Check if details are not already linked
             details_model = None
             if self.project.project_type == 'tiling':
                  details_model = TilingRoomDetails
             elif self.project.project_type == 'painting':
                  details_model = PaintingRoomDetails
             # Add elif for other project types

             if details_model:
                  details_instance = details_model.objects.create(
                      room_content_type=ContentType.objects.get_for_model(self),
                      room_object_id=self.pk
                  )
                  # No need to save Room again if using GenericForeignKey correctly.
                  # The link is established on the details instance creation.
                  # However, GenericForeignKey access often expects content_type/object_id on the *source* model.
                  # Re-saving the Room updates the fields used by GenericForeignKey lookup.
                  self.details_content_type = ContentType.objects.get_for_model(details_instance)
                  self.details_object_id = details_instance.pk
                  self.save(update_fields=['details_content_type', 'details_object_id'])


    def delete(self, *args, **kwargs):
        # Delete the associated details object if it exists
        if self.details:
            self.details.delete()
        super().delete(*args, **kwargs)


class ProjectMaterial(models.Model):
    """Represents a specific material and its quantity used in a project (Data only)."""
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name=_("Project")
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='project_usages',
        verbose_name=_("Material")
    )
    name = models.CharField(max_length=255, verbose_name=_("Material Name"))
    unit = models.CharField(max_length=50, verbose_name=_("Unit"), default="")

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=decimal.Decimal(0),
        verbose_name=_("Quantity Needed (Raw)"),
        help_text=_("Quantity needed for this project BEFORE wastage. Set by views/external logic.")
    )

    # Stored fields for calculated totals (values set by views/external logic)
    quantity_with_wastage = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=decimal.Decimal(0),
        verbose_name=_("Quantity with Wastage")
    )

    class Meta:
        verbose_name = _("Project Material")
        verbose_name_plural = _("Project Materials")
        unique_together = ('project', 'material')
        ordering = ['name']


    def __str__(self):
        display_name = self.name if self.name else (self.material.name if self.material else "Unnamed Material")
        unit_display = f" {self.unit}" if self.unit else ""
        return f"{display_name} ({self.quantity}{unit_display})"

    def save(self, *args, **kwargs):
        if not self.pk and self.material:
             if not self.name:
                 self.name = self.material.name
             if not self.unit and self.material.unit:
                 self.unit = self.material.unit

        # Calculations must be done in views/external logic before calling save
        super().save(*args, **kwargs)

    # Delete method is standard, no external trigger needed here


class Worker(models.Model):
    """Groups of workers assigned to a specific project task (Data only)."""

    WORKER_ROLE_CHOICES = [
        ('labourer', _('Labourer')),
        ('master', _('Master')),
        ('supervisor', _('Supervisor')),
        ('tiler', _('Tiler')),
        ('mason', _('Mason')),
        ('carpenter', _('Carpenter')),
        ('painter', _('Painter')),
        ('plasterer', _('Plasterer')),
        ('others', _('Others')),
    ]

    RATE_TYPE_CHOICES = [
        ('daily', _('Daily')),
        ('hourly', _('Hourly')),
    ]

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='workers',
        verbose_name=_("Project")
    )
    role = models.CharField(
        max_length=20,
        choices=WORKER_ROLE_CHOICES,
        verbose_name=_("Role")
    )
    count = models.PositiveIntegerField(default=1, verbose_name=_("Number of Workers"))
    rate = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_("Rate"))
    rate_type = models.CharField(
        max_length=10,
        choices=RATE_TYPE_CHOICES,
        default='daily',
        verbose_name=_("Rate Type")
    )
    coverage_area = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Coverage Area per Day"),
        help_text=_("Area this group can cover per day. Set by views/external logic.")
    )

    # Type-specific fields (data only)
    special_equipment_cost_per_day = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Special Equipment Cost/Day")
    )

    # Stored field for calculated total cost (value set by views/external logic)
    total_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=decimal.Decimal(0),
        verbose_name=_("Total Labor Cost for this group")
    )

    class Meta:
        verbose_name = _("Worker Group")
        verbose_name_plural = _("Worker Groups")
        ordering = ['role']

    def __str__(self):
        return f"{self.get_role_display()} ({self.count}) for {self.project.name if self.project else 'No Project'}"

    def save(self, *args, **kwargs):
         # Calculations must be done in views/external logic before calling save
         super().save(*args, **kwargs)

    # calculate_cost method is removed
    # Delete method is standard, no external trigger needed


class Tile(models.Model):
    """Model related to image processing of tiles, separate from estimation core (Data only)"""
    processed_image = models.ImageField(
        upload_to='tiles/media/processed/',
        verbose_name=_("Processed Image")
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Uploaded At"))

    class Meta:
        verbose_name = _("Tile Image")
        verbose_name_plural = _("Tile Images")
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Tile Image {self.id} ({self.uploaded_at.strftime('%Y-%m-%d %H:%M')})"

# No signals or recalculation methods within models. Calculations are external.