
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
import random
import string
from django.utils import timezone

User = get_user_model()

class SubscriptionPlan(models.Model):
    """Model for subscription plans available in the system"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_days = models.IntegerField()
    max_projects = models.IntegerField(help_text="Maximum number of main projects allowed")
    max_room_views = models.IntegerField(help_text="Maximum number of room views allowed")
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name} - {self.price} GHS"

class UserSubscription(models.Model):
    """Model for tracking user subscriptions"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='user_subscriptions')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Payment tracking
    payment_id = models.CharField(max_length=255, blank=True)
    payment_status = models.CharField(max_length=50, default='pending')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Usage tracking
    projects_used = models.IntegerField(default=0)
    room_views_used = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.start_date.date()} to {self.end_date.date()})"
    
    @property
    def is_expired(self):
        """Check if the subscription has expired"""
        from django.utils import timezone
        return self.end_date < timezone.now()
    
    @property
    def projects_remaining(self):
        """Calculate remaining projects"""
        return max(0, self.plan.max_projects - self.projects_used)
    
    @property
    def room_views_remaining(self):
        """Calculate remaining room views"""
        return max(0, self.plan.max_room_views - self.room_views_used)


class OTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True) # OTP can be for existing or new user
    phone_number = models.CharField(max_length=15, unique=True) # Must be unique for active OTPs
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = ''.join(random.choices(string.digits, k=6))
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=5) # OTP valid for 5 minutes
        super().save(*args, **kwargs)

    def is_valid(self):
        return timezone.now() < self.expires_at and not self.is_verified

    def __str__(self):
        return f"OTP for {self.phone_number}: {self.code}"


class PaymentTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    reference = models.CharField(max_length=50, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2) # Amount in GHS
    paystack_amount_pesewas = models.PositiveIntegerField() # Amount sent to Paystack (in pesewas)
    email = models.EmailField()
    phone_number = models.CharField(max_length=15)
    mobile_operator = models.CharField(max_length=20) # e.g., 'mtn', 'vodafone'
    customer_name = models.CharField(max_length=100, blank=True, null=True)
    plan_name = models.CharField(max_length=50, blank=True, null=True) # If you want to store the plan

    status = models.CharField(
        max_length=20,
        
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    paystack_response_status = models.BooleanField(null=True) # Paystack's initial 'status'
    paystack_response_message = models.TextField(blank=True, null=True)
    gateway_response = models.CharField(max_length=100, blank=True, null=True) # From Paystack webhook

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.reference} for {self.user.email} - {self.status}"
