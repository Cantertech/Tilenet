from django.urls import path
from . import views
from .views import (
    Room3DViewAccessAPIView, VerifyNewUserOTPView, check_subscription, check_version, get_manual_left, get_rooms_left, get_user_details, initialize_payment, register_user,update_password,password_reset, login_user, list_subscription_plans, update_subscription,send_message,GetReferralCodeView,get_plan_details, update_user_details,get_projects_left
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView



urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  
    path('login/',login_user, name='login_user'),
    path('project_left/',get_projects_left, name='project_left'),
    path('room_left/',get_rooms_left, name='project_left'),
    path('register/', register_user, name='register_user'),
    path('send-message/', send_message, name='send_message'),
    path('password_reset/',password_reset , name='password-reset'),
    path('plans/', list_subscription_plans, name='list_plans'),
    path('subscription/', update_subscription, name='update_subscription'),
    path('referral_code/',GetReferralCodeView, name ='referral_code'),
    path('update_password/',update_password, name ='update_password'),
    path('get_plan_details/',get_plan_details, name = 'get_plan_details'),
    path('check_subscription_status/',check_subscription, name = 'check_subscription_plan'),
    path('get_user_details/',get_user_details, name = 'get_user_details'),
    path('update_user_details/',update_user_details, name = 'update_user_details'),
    path('initialize-payment/', initialize_payment, name='initialize_payment'),
    path('send-verification-sms/', views.send_verification_sms, name='send_verification_sms'),
    path('Get_user_name/', views.user_contact_info_view, name='contact_info'),
    path('verify-phone-number/', views.verify_phone_number, name='verify_phone_number'),
    path('room_access/', Room3DViewAccessAPIView.as_view(), name='room-view-access'),
    path('manual_left/',get_manual_left, name='get_manual_left'),
    path('verify-new-user-otp/', VerifyNewUserOTPView.as_view(), name='verify-new-user-otp'),
    path('api/check-version/', check_version, name='check-version'),
]
