# accounts/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission, Group # Import Django's built-in Permission and Group models

# Import Simple JWT's base serializer for token obtain
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# Get the active user model (which is your CustomUser)
User = get_user_model()

# --- 1. Custom Serializer for Superuser Login (Simple JWT) ---
# This serializer will be used by Simple JWT's TokenObtainPairView
# to authenticate a user and ensure they are a superuser before issuing tokens.
class SuperuserTokenObtainPairSerializer(TokenObtainPairSerializer):
    # You can customize the fields here if needed, but typically
    # Simple JWT's default handles USERNAME_FIELD and password.
    # Example: If your USERNAME_FIELD is 'phone_number', it will look for 'phone_number' in request.data

    @classmethod
    def get_token(cls, user):
        # Get the standard access and refresh tokens from the parent class
        token = super().get_token(user)

        # Add custom claims to the token payload if you want to include
        # user information directly in the access token (optional but common).
        # These claims are accessible on the frontend by decoding the access token.
        token['phone_number'] = str(user.phone_number) # Ensure phone_number is a string
        token['full_name'] = user.full_name
        token['is_staff'] = user.is_staff
        token['is_superuser'] = user.is_superuser
        # Add any other relevant user fields

        return token

    def validate(self, attrs):
        # Call the parent class's validate method to authenticate the user
        # This method takes the credentials (e.g., phone_number and password)
        # from attrs, authenticates the user, and on success, sets self.user
        # and returns the default token payload (which includes 'access' and 'refresh').
        data = super().validate(attrs)

        # --- Add the superuser check AFTER successful authentication ---
        # If the user authenticated successfully (self.user is set) but is NOT a superuser,
        # raise a validation error.
        if not self.user.is_superuser:
            raise serializers.ValidationError(
                "No superuser account found with the given credentials."
            )

        # If the user is a superuser, the parent's validate method already returned
        # the data containing the 'access' and 'refresh' tokens.
        # We just return that data.
        return data

# --- 2. Serializer for Listing/Retrieving Users (Admin Dashboard) ---
# This serializer is used to display user information in the admin list or detail views.
class UserSerializer(serializers.ModelSerializer):
    # You might add calculated fields here if needed, e.g., subscription status

    class Meta:
        model = User # Use your custom user model
        # Specify the fields you want to expose in the API response for users.
        fields = [
            'id',
            'phone_number',
            'full_name',
            'first_name', # Include first and last name if you use them
            'last_name',
            'email',
            'is_active',
            'is_staff',
            'is_superuser',
            'date_joined',
            # Add any other fields you want to display
        ]
        # Make sensitive fields or fields managed by the system read-only
        read_only_fields = [
            'date_joined',
            # 'is_staff', # You might make these read-only for non-superuser admins
            # 'is_superuser', # Only superusers should likely be able to change this
        ]

# --- 3. Serializer for Creating Users (Admin Dashboard) ---
# This serializer is used when an admin creates a new user via the API (POST request).
# It includes the password field for setting the initial password.
class CreateUserSerializer(serializers.ModelSerializer):
    # Define password as a write-only field so it's not included in the response
    password = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = [
            'phone_number',
            'full_name',
            'first_name',
            'last_name',
            'email',
            'password', # Include password for creation
            'is_active',
            'is_staff',
            'is_superuser',
        ]
        # You might restrict which fields non-superuser admins can set here
        # extra_kwargs = {
        #     'is_staff': {'required': False},
        #     'is_superuser': {'required': False},
        # }


    # Override the create method to use the user manager's create_user method
    # This ensures password hashing and correct user creation logic is used.
    def create(self, validated_data):
        # Extract password from validated_data as create_user handles it separately
        password = validated_data.pop('password', None)

        # Use the custom user manager's create_user method
        user = User.objects.create_user(
            phone_number=validated_data['phone_number'],
            password=password,
            # Pass the remaining validated data as extra_fields
            **validated_data
        )
        return user

# --- 4. Serializer for Updating Users (Admin Dashboard) ---
# This serializer is used when an admin updates an existing user (PUT/PATCH requests).
# It typically excludes the password field or handles it separately if password changes are allowed here.
class UpdateUserSerializer(serializers.ModelSerializer):
    # If you want to allow password changes via this serializer,
    # you would add a password field here and override the update method.
    # password = serializers.CharField(write_only=True, required=False) # Optional password field

    class Meta:
        model = User
        # Specify the fields that can be updated via this serializer.
        # Exclude sensitive fields like password or unique identifiers like phone_number
        # unless you have specific logic to handle their updates.
        fields = [
            'full_name',
            'first_name',
            'last_name',
            'email',
            'is_active',
            'is_staff',
            'is_superuser',
            # Add other fields that can be updated
        ]
        # Make fields that should not be changed read-only
        read_only_fields = [
            'phone_number', # Phone number is typically not changed after creation
            # 'is_superuser', # Only superusers should likely be able to change this
            # 'is_staff', # You might make this read-only for non-superuser admins
        ]

    # If you added a password field above, override update to handle it:
    # def update(self, instance, validated_data):
    #     password = validated_data.pop('password', None)
    #     user = super().update(instance, validated_data)
    #     if password:
    #         user.set_password(password)
    #         user.save()
    #     return user


# --- 5. Serializer for Django Permissions ---
# Used to list available permissions for assigning to users/groups in the admin frontend.
class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename'] # Expose relevant permission fields
        read_only_fields = fields # Permissions are typically read-only via this API


# --- 6. Serializer for Django Groups ---
# Used to list available groups for assigning users to groups in the admin frontend.
class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name'] # Expose relevant group fields
        read_only_fields = fields # Groups are typically read-only via this API (creation/deletion is admin site or separate API)

# --- You might also need serializers for other admin-related models ---
# Example: Serializer for UserSubscription if you list/manage subscriptions
# class UserSubscriptionSerializer(serializers.ModelSerializer):
#     user = UserSerializer(read_only=True) # Nest user info
#     plan = SubscriptionPlanSerializer(read_only=True) # Assuming SubscriptionPlanSerializer exists

#     class Meta:
#         model = UserSubscription
#         fields = '__all__' # Or specify fields
