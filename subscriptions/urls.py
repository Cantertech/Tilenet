
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import AppVersionCheckAPIView, RequestOTPView, VerifyOTPAndSetPasswordView ,InitiatePaymentAPIView, VerifyPaystackPaymentAPIView, check_payment_status,verify_paystack_otp


router = DefaultRouter()
router.register(r'plans', views.SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'user-subscriptions', views.UserSubscriptionViewSet, basename='user-subscription')
router.register(r'payments', views.PaymentViewSet, basename='payment')

urlpatterns = [
    path('', include(router.urls)),
    path('request-otp/', RequestOTPView.as_view(), name='request-otp'),
    path('verify-otp-and-set-password/', VerifyOTPAndSetPasswordView.as_view(), name='verify-otp-and-set-password'),
    path('initiate-payment/', InitiatePaymentAPIView.as_view(), name='initiate_payment'),
    # path('paystack-webhook/', PaystackWebhookAPIView.as_view(), name='paystack_webhook'),
    path('payment-success/', views.payment_success_page, name='payment_success_page'), # Name matches view for reverse()
     path('check-payment-status/<str:reference>/', check_payment_status, name='check-payment-status'),
     path('app-version/', AppVersionCheckAPIView.as_view(), name='app_version_check'),
     path('verify-paystack-otp/', views.verify_paystack_otp, name='verify_paystack_otp'),
     path('verify-payment/', VerifyPaystackPaymentAPIView.as_view(), name='verify_payment'),
]


