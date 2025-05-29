# subscriptions/admin.py
from django.contrib import admin
from .models import SubscriptionPlan, UserSubscription, PaymentTransaction # Assuming these are in .models
from .models import OTP # Assuming OTP is also in .models

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'duration_days', 'max_projects', 'max_room_views', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')

@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 'is_active', 'payment_status', 'projects_remaining', 'room_views_remaining')
    list_filter = ('is_active', 'payment_status', 'plan')
    search_fields = ('user__username', 'user__email', 'payment_id')
    readonly_fields = ('projects_remaining', 'room_views_remaining')

    fieldsets = (
        (None, {
            'fields': ('user', 'plan', 'start_date', 'end_date', 'is_active')
        }),
        ('Payment Information', {
            'fields': ('payment_id', 'payment_status', 'amount_paid')
        }),
        ('Usage Statistics', {
            'fields': ('projects_used', 'room_views_used', 'projects_remaining', 'room_views_remaining')
        }),
    )

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    # Corrected list_display to use 'amount' and 'mobile_operator'
    list_display = ('user', 'amount', 'status', 'mobile_operator', 'reference', 'created_at')
    # Corrected list_filter to use 'mobile_operator' and remove 'currency'
    list_filter = ('status', 'mobile_operator', 'created_at') # Filtering by 'created_at' is often useful
    search_fields = ('user__username', 'user__email', 'reference', 'phone_number') # Added phone_number and reference for search
    readonly_fields = (
        'user', 'reference', 'amount', 'paystack_amount_pesewas', 'email',
        'phone_number', 'mobile_operator', 'customer_name', 'plan_name',
        'paystack_response_status', 'paystack_response_message', 'gateway_response',
        'created_at', 'updated_at' # Ensure updated_at is also here if you want to view it
    )
    # Using fieldsets for better organization in the admin form
    fieldsets = (
        (None, {
            'fields': ('user', 'reference', 'status')
        }),
        ('Payment Details', {
            'fields': ('amount', 'paystack_amount_pesewas', 'email', 'phone_number', 'mobile_operator', 'customer_name', 'plan_name')
        }),
        ('Paystack Response', {
            'fields': ('paystack_response_status', 'paystack_response_message', 'gateway_response')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',) # Makes these fields collapsible
        }),
    )


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'code', 'created_at', 'is_verified', 'expires_at')
    search_fields = ('phone_number',)
    list_filter = ('is_verified',)