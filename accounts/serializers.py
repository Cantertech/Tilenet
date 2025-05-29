from datetime import timedelta
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import CustomUser, UserProfile, SubscriptionPlan, UserSubscription
from django.utils.timezone import now
from rest_framework.exceptions import ValidationError


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['company_name', 'phone_number', 'address', 'city']


class VerifyNewUserOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)

    def validate_phone_number(self, value):
        if not User.objects.filter(phone_number=value, is_active=False).exists():
             # We look for an inactive user, assuming they just signed up and need verification
            raise serializers.ValidationError("No unverified user found with this phone number.")
        return value

    def validate_otp(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("OTP must be a 6-digit number.")
        return value

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    Serializer for the SubscriptionPlan model.
    """
    class Meta:
        model = SubscriptionPlan
        fields = '__all__'


class UserSubscriptionSerializer(serializers.ModelSerializer):
    """
    Serializer for the UserSubscription model.
    """
    plan = SubscriptionPlanSerializer(read_only=True)  # Nested plan details
    is_active = serializers.BooleanField(read_only=True)  # Computed property for subscription status

    class Meta:
        model = UserSubscription
        fields = ['plan', 'start_date', 'end_date', 'payment_status', 'is_active']


# class PaymentSerializer(serializers.ModelSerializer):
#     """
#     Serializer for the Payment model.
#     """
#     class Meta:
#         model = Payment
#         fields = ['id', 'amount', 'payment_date', 'status', 'reference']


# class UserRegistrationSerializer(serializers.ModelSerializer):
#     """
#     Serializer for user registration, including the profile and subscription data.
#     """
#     profile = UserProfileSerializer()
#     subscription_plan_id = serializers.IntegerField(write_only=True, required=False)
#     subscription = UserSubscriptionSerializer(read_only=True)

#     class Meta:
#         model = User
#         fields = ['username', 'email', 'password', 'profile', 'subscription_plan_id', 'subscription']
#         extra_kwargs = {
#             'password': {'write_only': True},
#         }

#     def create(self, validated_data):
#         try: 
#             print("passed test 1")
#             profile_data = validated_data.pop('profile')
#             subscription_plan_id = validated_data.pop('subscription_plan_id', None)

#             # Clean up fields
#             username = validated_data['username'].strip()
#             email = validated_data['email'].strip()
#             password = validated_data['password']

#             # Create user with hashed password
#             print("passed test 2")
#             user = User.objects.create_user(
#                 username=username,
#                 email=email,
#                 password=password
#             )

#             # Create profile
#             print("passed test 3")
#             UserProfile.objects.create(user=user, **profile_data)

#             # Handle subscription
#             if subscription_plan_id:
#                 try:
#                     print("passed test 4")
#                     plan = SubscriptionPlan.objects.get(id=subscription_plan_id)
#                     UserSubscription.objects.create(
#                         user=user,
#                         plan=plan,
#                         end_date=now() + timedelta(days=plan.duration_in_days),
#                         payment_status='Pending'
#                     )
#                 except SubscriptionPlan.DoesNotExist:
#                     raise ValidationError({'subscription_plan_id': 'Subscription plan does not exist'})

#             return user

#         except Exception as e:
#             raise ValidationError({'detail': str(e)})
class CustomUserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer()
    # No 'username' field needed here unless you want to explicitly manage it.
    # 'email' is now optional
    email = serializers.EmailField(required=False, allow_blank=True) # Allow empty email

    class Meta:
        model = CustomUser
        # Ensure 'phone_number' is in fields.
        # Remove 'username' from fields, as it's now optional and not primary.
        fields = ['id', 'phone_number', 'full_name', 'email', 'password', 'profile','username','first_name','last_name']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        profile_data = validated_data.pop('profile')
        password = validated_data.pop('password')

        # Create the CustomUser instance using the manager's create_user method
        user = CustomUser.objects.create_user(
            phone_number=validated_data.get('phone_number'), # Get phone_number from validated data
            password=password,
            full_name=validated_data.get('full_name', ''),
            username=validated_data.get('username', ''),
            email=validated_data.get('email', ''), # Pass email if it's optional/blank
            first_name = validated_data.get('first_name', ''),
            last_name = validated_data.get('last_name', ''),
            is_active=True,
        )

        # Create the UserProfile linked to the new user
        UserProfile.objects.create(user=user, **profile_data)

        return user

    def validate_phone_number(self, value):
        # Optional: Add more robust phone number validation here
        if not value.strip():
            raise serializers.ValidationError("Phone number cannot be empty.")
        if CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("A user with this phone number already exists.")
        return value

class ContactMessageSerializer(serializers.Serializer):
    """
    Serializer for contact messages.
    """
    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    message = serializers.CharField(max_length=1000)
