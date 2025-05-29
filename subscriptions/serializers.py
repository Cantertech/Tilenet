
from rest_framework import serializers
from .models import SubscriptionPlan, UserSubscription, PaymentTransaction
from django.utils import timezone
from datetime import timedelta
# your_app_name/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal # Import Decimal

User = get_user_model()

class PhoneNumberSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)

    def validate_phone_number(self, value):
        # Basic phone number validation (you might want a more robust regex)
        if not value.startswith('+') or not value[1:].isdigit():
            raise serializers.ValidationError("Phone number must start with '+' and contain only digits.")
        return value

class VerifyOTPAndSetPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(min_length=8, write_only=True)
    confirm_password = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("New passwords do not match.")
        return data

    def validate_phone_number(self, value):
        # Ensure the phone number exists in the system if this is a password reset
        # For a new user registration, you might remove this check or modify it.
        if not User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("No user found with this phone number.")
        return value
    
class InitiatePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True,  min_value=Decimal('1.00'))
    phoneNumber = serializers.CharField(max_length=15, required=True) # Max length for phone numbers
    mobileOperator = serializers.ChoiceField(
        choices=[('mtn', 'MTN'), ('telecel', 'Telecel'), ('airtel-tigo', 'AirtelTigo')],
        required=True
    )
    customerName = serializers.CharField(max_length=100, required=False, allow_blank=True)
    plan_name = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_phoneNumber(self, value):
        # Basic phone number validation for Ghana (starts with 0, 9 digits after 0)
        if not (value.startswith('0') and len(value) == 10 and value[1:].isdigit()):
            raise serializers.ValidationError("Phone number must be a valid Ghanaian number (e.g., 0541234567).")
        return value

    def validate(self, data):
        # You can add more complex cross-field validation here if needed
        return data

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'

class InitiateMobileMoneySerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    email = serializers.EmailField()
    mobile_number = serializers.CharField(max_length=15) # e.g., +233241234567
    network = serializers.CharField(max_length=10) # e.g., 'MTN', 'VODAFONE', 'AIRTELTIGO'
    callback_url = serializers.URLField(required=False)


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    projects_remaining = serializers.IntegerField(read_only=True)
    room_views_remaining = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = UserSubscription
        fields = ('id', 'user', 'plan', 'plan_name', 'start_date', 'end_date', 
                  'is_active', 'payment_status', 'amount_paid',
                  'projects_used', 'room_views_used', 
                  'projects_remaining', 'room_views_remaining', 'is_expired')
        read_only_fields = ('user', 'start_date', 'payment_id', 'payment_status')
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        
        # Set end date based on the plan's duration
        plan = validated_data.get('plan')
        start_date = timezone.now()
        end_date = start_date + timedelta(days=plan.duration_days)
        
        validated_data['start_date'] = start_date
        validated_data['end_date'] = end_date
        validated_data['amount_paid'] = plan.price
        
        return super().create(validated_data)

class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = '__all__'
        read_only_fields = ('user', 'created_at')
    
    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)

