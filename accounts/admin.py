
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserProfile

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    # Define the fields for adding/editing users in the admin form
    # You might need to adjust these based on your exact CustomUser model fields
    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}), # USERNAME_FIELD and password
        ('Personal info', {'fields': ('full_name', 'email')}), # Other fields from CustomUser
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    # Add 'phone_number' as the link to the detail view
    list_display_links = ('phone_number',)

    # Correct the list_display:
    # Replace 'company_name' with a method that retrieves it from the profile
    list_display = ('phone_number', 'email', 'full_name', 'is_staff', 'get_company_name') # <-- Fixed here

    # Fields to search by
    search_fields = ('phone_number', 'full_name', 'email')

    # Filters
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups')

    # Ordering
    ordering = ('phone_number',)

    # Add this method to display company_name from the related UserProfile
    def get_company_name(self, obj):
        # Check if the user has a profile associated
        if hasattr(obj, 'profile') and obj.profile:
            return obj.profile.company_name
        return "N/A" # Return "N/A" or a similar placeholder if the profile does not exist

    # Set a more readable column header for the method
    get_company_name.short_description = 'Company Name'

# Optionally, register UserProfile if you want to manage it directly in the admin
# @admin.register(UserProfile)
# class UserProfileAdmin(admin.ModelAdmin):
#     list_display = ('user', 'company_name', 'phone_number', 'address', 'city')
#     search_fields = ('user__email', 'company_name')
# 
# core/admin.py

from .models import AppVersion

@admin.register(AppVersion)
class AppVersionAdmin(admin.ModelAdmin):
    list_display = ('platform', 'latest_version', 'force_update', 'updated_at')

