
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

class Material(models.Model):
    """Model for materials used in estimations"""
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=20)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    project_type = models.CharField(max_length=50, choices=[
        ('tiles', 'Tiles'),
        ('pavement', 'Pavement'),
        ('masonry', 'Masonry'),
        ('carpentry', 'Carpentry'),
    ])
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.project_type})"

class QuickEstimate(models.Model):
    """Model for quick estimates"""
    
    PROJECT_TYPES = [
        ('tiles', 'Tiles'),
        ('pavement', 'Pavement'),
        ('masonry', 'Masonry'),
        ('carpentry', 'Carpentry'),
    ]
    
    ROOM_TYPES = [
        ('bathroom', 'Bathroom'),
        ('kitchen', 'Kitchen'),
        ('living_room', 'Living Room'),
        ('dining', 'Dining'),
        ('corridor', 'Corridor'),
        ('fence_wall', 'Fence Wall'),
        ('porch', 'Porch'),
        ('room', 'Room'),
    ]
    
    MEASUREMENT_UNITS = [
        ('meters', 'Meters'),
        ('feet', 'Feet'),
        ('inches', 'Inches'),
        ('centimeters', 'Centimeters'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quick_estimates')
    name = models.CharField(max_length=255)
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES)
    measurement_unit = models.CharField(max_length=20, choices=MEASUREMENT_UNITS)
    
    length = models.DecimalField(max_digits=10, decimal_places=2)
    breadth = models.DecimalField(max_digits=10, decimal_places=2)
    height = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Floor thickness affects cement calculation
    floor_thickness = models.DecimalField(max_digits=5, decimal_places=2, default=0.05)
    
    # Wastage factor (can be automatic or manual)
    auto_wastage = models.BooleanField(default=True)
    manual_wastage_factor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
    total_area = models.DecimalField(max_digits=10, decimal_places=2)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} - {self.project_type} ({self.created_at.date()})"

class EstimateMaterial(models.Model):
    """Materials used in a specific estimate"""
    estimate = models.ForeignKey(QuickEstimate, on_delete=models.CASCADE, related_name='materials')
    material = models.ForeignKey(Material, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    
    def __str__(self):
        return f"{self.material.name} for {self.estimate.name}"

