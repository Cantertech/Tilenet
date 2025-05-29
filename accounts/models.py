from datetime import timedelta, timezone
import datetime
import string
from django.db import models
from django.utils.timezone import now
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
import random
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField
from django.conf import settings


class AppVersion(models.Model):
    latest_version = models.CharField(max_length=20)
    force_update = models.BooleanField(default=True)
    update_message = models.TextField()
    download_link = models.URLField()
    platform = models.CharField(max_length=10, default="android")  # or ios

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.platform} - {self.latest_version}"


# Subscription Plan Model (Unchanged)
class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)  # e.g., "Basic Plan"
    price = models.DecimalField(max_digits=10, decimal_places=2)  # e.g., $20.00
    project_limit = models.IntegerField()  
    three_d_view_limit = models.IntegerField()
    manual_estimate_limit = models.IntegerField(default=10)
    duration_in_days = models.IntegerField()  # Plan duration in days

    def __str__(self):
        return f"{self.name} - GHS {self.price} for {self.duration_in_days} days"

# User Profile Model (Modified)
class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='userprofile')
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    company_name = models.CharField(max_length=100, blank=True, null=True)
    website = models.URLField(blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    address = models.CharField(max_length=100, blank=True, null=True)
    estimate_counter = models.PositiveIntegerField(default=0)
    referral_code = models.CharField(max_length=6, unique=True, blank=True, null=True)
    payment_status = models.CharField(
        max_length=10,
        choices=[('Paid', 'Paid'), ('Unpaid', 'Unpaid')],
        default='Unpaid'
    )
    points = models.IntegerField(default=0)  # Field to store the total points

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_unique_referral_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_referral_code():
        while True:
            code = str(random.randint(345000, 699999))
            if not UserProfile.objects.filter(referral_code=code).exists():
                return code

    def __str__(self):
        return self.user.username

class PasswordResetCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    code = models.IntegerField()
    expiration_time = models.DateTimeField()

    def is_expired(self):
        return datetime.now() > self.expiration_time
    


class UserSubscription(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey('SubscriptionPlan', on_delete=models.CASCADE, related_name='subscriptions')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    projects_created = models.PositiveIntegerField(default=0)  
    three_d_views_used = models.PositiveIntegerField(default=0)  
    manual_estimates_used = models.PositiveIntegerField(default=0)  
    is_active = models.BooleanField(default=True)
    project_limit = models.PositiveBigIntegerField(default=7)
    three_d_views_limit = models.PositiveBigIntegerField(default=10)
    manual_estimate_limit = models.PositiveBigIntegerField(default=15)
    payment_status = models.CharField(
        max_length=10,
        choices=[('Paid', 'Paid'), ('Failed', 'Failed'), ('Pending', 'Pending')],
        default='Pending'
    )
    is_trial_active = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.plan.duration_in_days)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.plan.name} ({self.payment_status})"
    
    @property
    def check_and_deactivate_trial(self):
        """Deactivate trial if the 7-day free period is over."""
        if self.is_trial_active and now() >= self.start_date + timedelta(days=7):
            self.is_trial_active = False
            self.payment_status = 'Pending'  # Set payment status to pending after trial ends
            self.save()

    @property
    def has_active_subscription(self):
        """Returns True if the user has a valid subscription (paid or trial active)."""
        if self.is_trial_active:
            return True
        if self.payment_status == 'Paid' and self.end_date > now():
            return True
        return False

    
    
    def upgrade_subscription(self, new_plan):
        """Upgrade the subscription plan by adding limits and extending duration."""
        
        self.plan = new_plan
        self.end_date += timedelta(days=new_plan.duration_in_days)  # Extend the duration

        # Add the new limits without resetting the current usage
        self.projects_created = min(self.projects_created, new_plan.project_limit)
        self.three_d_views_used = min(self.three_d_views_used, new_plan.three_d_view_limit)
        self.save()


    def can_use_feature(self, feature_type):
        """Check if the user can use a specific feature based on their subscription limits."""
        if feature_type == 'estimate':
            return self.projects_created < self.project_limit
        elif feature_type == 'room_view':
            return self.three_d_views_used < self.three_d_views_limit
        elif feature_type == 'manual_estimate':
            return self.manual_estimates_used < self.manual_estimate_limit
        return False

    def record_feature_usage(self, feature_type):
        """Record the usage of a specific feature by incrementing the corresponding counter."""
        if feature_type == 'estimate':
            self.projects_created += 1
        elif feature_type == 'room_view':
            self.three_d_views_used += 1
        elif feature_type == 'manual_estimate':
            self.manual_estimates_used += 1
        self.save()

    def has_access_to_free(self):
        """Check if the user has access to Quick Estimate based on active subscription and validity period."""
        return self.has_active_subscription and self.end_date > now()


def use_feature_if_allowed(user, feature_type):
    try:
        subscription = user.subscription

        # Check if feature can be used
        if not subscription.can_use_feature(feature_type):
            limit_messages = {
                'estimate': "Project estimate limit reached. Please upgrade your plan.",
                'room_view': "3D room view limit reached. Please upgrade your plan.",
                'manual_estimate': "Manual estimate limit reached. Please upgrade your plan.",
            }
            return {
                "success": False,
                "message": limit_messages.get(feature_type, "Feature limit reached. Please upgrade your plan.")
            }

        # Record usage
        subscription.record_feature_usage(feature_type)
        return {"success": True, "message": "Feature used successfully."}

    except UserSubscription.DoesNotExist:
        return {"success": False, "message": "Subscription not found."}


def get_projects_left(user):
    
    try:
        subscription = user.subscription
        projects_left = subscription.plan.project_limit - subscription.projects_created

        if projects_left < 0:
            projects_left = 0  # Ensure we don't return a negative number

        return {"success": True, "projects_left": projects_left}

    except UserSubscription.DoesNotExist:
        return {"success": False, "message": "Subscription not found."}


# Referral Model (Modified)
class Referral(models.Model):
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='referrals', on_delete=models.CASCADE)
    referee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='referred_by', on_delete=models.CASCADE)
    code = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.referrer.username} referred {self.referee.username}"


# Referral Commission Model
class ReferralCommission(models.Model):
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='commissions', on_delete=models.CASCADE)
    referee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='referral_commissions', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    points = models.IntegerField()  # Store points equivalent to amount
    commission_type = models.CharField(max_length=20, choices=[('Initial', 'Initial'), ('Recurring', 'Recurring')])
    paid_at = models.DateTimeField(auto_now_add=True)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.referrer.username} earned commission from {self.referee.username}"


# Optional: Referral Reward Model to track any additional rewards (e.g., e-gift cards)
class ReferralReward(models.Model):
    referrer = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='referrer_rewards', on_delete=models.CASCADE)
    referee = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='referee_rewards', on_delete=models.CASCADE)
    reward_type = models.CharField(max_length=100)
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2)
    awarded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reward for {self.referrer.username} from {self.referee.username}"


class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('The Phone Number field must be set')
        # Normalize the phone number if needed (e.g., remove spaces, add country code prefix)
        # For simplicity, we'll use it as is for now, but consider a dedicated phone number field library.
        # phone_number = self.normalize_phone_number(phone_number) # You might implement this
        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(phone_number, password, **extra_fields)

# Custom User Model
class CustomUser(AbstractBaseUser, PermissionsMixin):
    # Phone number as the unique identifier
    phone_number = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    username = models.CharField(max_length=150, blank=True, null=True, unique=False)
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True, null=True) 

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    # Tell Django to use 'phone_number' as the primary login field
    USERNAME_FIELD = 'phone_number'
   
    REQUIRED_FIELDS = ['full_name'] 

    def __str__(self):
        return self.phone_number
    
class VerificationCode(models.Model):
    """
    Stores verification codes sent to users for phone number verification.
    """
    # Link to the user (optional, if you want to associate codes with registered users)
    # If verifying during registration before user is fully active, linking by phone number is key.
    # Linking to the user is useful after the user object is created.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='verification_codes')

    # Store the phone number the code was sent to
    # Use PhoneNumberField if you have it, otherwise CharField
    # Ensure this matches the type used in your CustomUser model for phone_number
    phone_number = models.CharField(max_length=20, db_index=True) # Or PhoneNumberField()

    code = models.CharField(max_length=6) # Store the generated code (e.g., 6 digits)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False) # To prevent reusing the same code

    class Meta:
        ordering = ['-created_at'] # Order by most recent first

    def __str__(self):
        return f"Code for {self.phone_number}: {self.code}"

    def is_valid(self):
        """Checks if the code is not expired and has not been used."""
        return self.expires_at > timezone.now() and not self.is_used

    @staticmethod
    def generate_code(length=6):
        """Generates a random numeric verification code."""
        # Ensure the code is always digits
        return ''.join(random.choices(string.digits, k=length))

    def save(self, *args, **kwargs):
        # Set expiration time before saving if not already set
        # This uses the VERIFICATION_CODE_EXPIRY_MINUTES setting
        if not self.id and not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=settings.VERIFICATION_CODE_EXPIRY_MINUTES)
        super().save(*args, **kwargs)

