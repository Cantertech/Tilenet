import decimal
from django.db import models
from django.conf import settings


class Customer(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name or '-'} ({getattr(self.user, 'username', '-')})"

    class Meta:
        ordering = ['name']


class Estimate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='estimates')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='estimates')
    title = models.CharField(max_length=255, default="New Estimate")
    estimate_date = models.DateField(auto_now_add=True)
    transport_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profit_type = models.CharField(
        max_length=20, 
        verbose_name=("Original Profit Type Input")
    )
    profit_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name=("Original Profit Value Input")
    )
    estimated_days = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    wastage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    labour_cost_per_day = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name=("Labour Cost Per Day"),
        help_text=("Cost of labour for one day.")
    )
    total_labour_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name=("Total labour cost ")
    )
    total_area_sq_m =models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name=("Total area in square meters")
    )

    labour_per_sq_meter = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name=("Total profit per square meter")
    )

    def __str__(self):
        customer_name = getattr(self.customer, 'name', '-') if self.customer else '-'
        user_name = getattr(self.user, 'username', '-') if self.user else '-'
        return f"Estimate #{self.id or '-'} for {customer_name} by {user_name}"

    class Meta:
        ordering = ['-created_at']


class MaterialItem(models.Model):
    estimate = models.ForeignKey(Estimate, on_delete=models.CASCADE, related_name='materials')
    name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        return round(decimal.Decimal(self.unit_price or 0) * decimal.Decimal(self.quantity or 0), 2)

    def __str__(self):
        return f"{self.name or '-'} ({self.quantity or '-'} @ {self.unit_price or '-'})"

    class Meta:
        ordering = ['name']


class RoomArea(models.Model):
    estimate = models.ForeignKey(Estimate, on_delete=models.CASCADE, related_name='rooms')
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=100, blank=True, null=True)
    floor_area = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    wall_area = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name or '-'} ({self.type or '-'})"

    class Meta:
        ordering = ['name']


