
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import AppVersionCheckAPIView, RequestOTPView, VerifyOTPAndSetPasswordView ,InitiatePaymentAPIView, PaystackWebhookAPIView, check_payment_status


router = DefaultRouter()
router.register(r'plans', views.SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'user-subscriptions', views.UserSubscriptionViewSet, basename='user-subscription')
router.register(r'payments', views.PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
    path('request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('verify-otp-and-set-password/', VerifyOTPAndSetPasswordView.as_view(), name='verify-otp-and-set-password'),
    path('initiate-payment/', InitiatePaymentAPIView.as_view(), name='initiate_payment'),
    path('paystack-webhook/', PaystackWebhookAPIView.as_view(), name='paystack_webhook'),
    path('payment-success/', views.payment_success_page, name='payment_success_page'), # Name matches view for reverse()
     path('check-payment-status/<str:reference>/', check_payment_status, name='check-payment-status'),
     path('app-version/', AppVersionCheckAPIView.as_view(), name='app_version_check')
]

# {
#     "amount": 150.75,
#     "email": "user@example.com",
#     "phoneNumber": "0241234567",
#     "mobileOperator": "mtn",
#     "customerName": "John Doe"
# }
