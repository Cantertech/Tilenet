from datetime import datetime, timedelta, timezone
import re
import traceback
from urllib import request
from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view,permission_classes
from django.contrib.auth.models import User

from subscriptions.models  import OTP
from .models import AppVersion, CustomUser, PasswordResetCode, VerificationCode, use_feature_if_allowed
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.db import models
from django.core.mail import send_mail
from rest_framework import status
from .serializers import ContactMessageSerializer, CustomUserSerializer, UserSubscriptionSerializer, VerifyNewUserOTPSerializer
from django.contrib.auth.tokens import default_token_generator
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User
from .models import UserProfile, SubscriptionPlan, UserSubscription
from .serializers import ContactMessageSerializer, SubscriptionPlanSerializer
from django.utils.timezone import now
from django.shortcuts import get_object_or_404, render
from django.db.models import Count
from .models import Referral  
from django.http import JsonResponse
import random
from django.contrib.auth.hashers import make_password
from .models import UserProfile,Referral  
import random
from accounts.serializers import UserSubscription  
import requests
from django.http import JsonResponse
from django.conf import settings
from .utils import generate_verification_code,  send_sms_africastalking
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .serializers import (
    VerifyNewUserOTPSerializer # Import the new serializer
)


User = get_user_model()
import africastalking

# Initialize Africa's Talking (make sure settings.AFRICASTALKING_USERNAME etc. are correctly loaded)
africastalking.initialize(settings.AFRICASTALKING_USERNAME, settings.AFRICASTALKING_API_KEY)
sms = africastalking.SMS


# --- Helper function for sending SMS to reduce repetition ---
def send_otp_sms(phone_number, otp_code):
    message = f"Your verification code is: {otp_code}. It is valid for {settings.VERIFICATION_CODE_EXPIRY_MINUTES} minutes."
    try:
        response = sms.send(message, [phone_number])
        print(f"Africa's Talking SMS response: {response}")
        if response and response.get('SMSMessageData') and \
           response['SMSMessageData'].get('Recipients') and \
           response['SMSMessageData']['Recipients'][0].get('status') == 'Success':
            return True, "OTP sent successfully."
        else:
            error_message = response['SMSMessageData']['Recipients'][0]['status'] if response and response.get('SMSMessageData') else 'Unknown AT error'
            print(f"Africa's Talking SMS sending failed: {error_message}")
            return False, f"Failed to send OTP via SMS: {error_message}"
    except africastalking.AfricasTalkingException as e:
        print(f"Africa's Talking API error: {e}")
        return False, f"Africa's Talking API error: {e}"
    except Exception as e:
        print(f"Generic error sending SMS: {e}")
        return False, f"An unexpected error occurred while trying to send SMS: {e}"


def initialize_payment(request):
    if request.method == 'POST':
        # Extracting the payload 
        data = request.POST
        email = data.get('email')
        amount = int(data.get('amount')) * 100  

        # Paystack initialization URL
        url = "https://api.paystack.co/transaction/initialize"

        # Headers for the API request
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        # Data for the API request
        payload = {
            "email": email,
            "amount": amount,
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data['status']:
                return JsonResponse({
                    "status": "success",
                    "authorization_url": response_data['data']['authorization_url'],
                })

            return JsonResponse({
                "status": "error",
                "message": response_data.get('message', 'Unable to initialize payment'),
            }, status=400)

        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)

@api_view(['GET'])
def check_version(request):
    platform = request.GET.get("platform", "android")  # You can pass this from the app
    version = AppVersion.objects.filter(platform=platform).last()

    return Response({
        "latest_version": version.latest_version,
        "force_update": version.force_update,
        "update_message": version.update_message,
        "download_link": version.download_link,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_projects_left(request):
    try:
        # Fetch the subscription info for the logged-in user
        subscription = UserSubscription.objects.get(user=request.user)

        # Calculate the number of projects left
        projects_left = subscription.project_limit - subscription.projects_created

        return JsonResponse({
            'projects_left': projects_left
        })

    except UserSubscription.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found.'}, status=404)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_manual_left(request):
    try:
        # Fetch the subscription info for the logged-in user
        subscription = UserSubscription.objects.get(user=request.user)

        # Calculate the number of projects left
        manual_estimate_left = subscription.manual_estimate_limit - subscription.manual_estimates_used

        return JsonResponse({
            'manual_estimate_left': manual_estimate_left
        })

    except UserSubscription.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found.'}, status=404)
    

class Room3DViewAccessAPIView(APIView):
    """
    API endpoint to check and record 3D Room View usage.
    If the user has remaining usage, it records the use and returns success.
    Otherwise, it blocks access with an upgrade prompt.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        usage_response = use_feature_if_allowed(request.user, 'room_view')

        if not usage_response["success"]:
            return Response(usage_response, status=status.HTTP_403_FORBIDDEN)

        return Response({
            "success": True,
            "message": "Access granted. 3D Room View usage recorded."
        }, status=status.HTTP_200_OK)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_rooms_left(request):
    try:
        # Fetch the subscription info for the logged-in user
        subscription = UserSubscription.objects.get(user=request.user)

        # Calculate the number of projects left
        rooms_left = subscription.three_d_views_limit - subscription.three_d_views_used

        return JsonResponse({
            'rooms_left': rooms_left
        })

    except UserSubscription.DoesNotExist:
        return JsonResponse({'error': 'Subscription not found.'}, status=404)


class VerifyNewUserOTPView(APIView):
    permission_classes = [AllowAny] # No authentication needed for OTP verification

    def post(self, request, *args, **kwargs):
        serializer = VerifyNewUserOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp_code = serializer.validated_data['otp']

            try:
                otp_instance = OTP.objects.filter(
                    phone_number=phone_number,
                    is_verified=False,
                    expires_at__gt=timezone.now()
                ).latest('created_at')

                if otp_instance.code == otp_code:
                    # Mark OTP as verified
                    otp_instance.is_verified = True
                    otp_instance.save()

                    # Find the user and activate/verify their account
                    try:
                        user = User.objects.get(phone_number=phone_number, is_active=False)
                        user.is_active = True # Or whatever field you use for 'is_verified'
                        user.save()
                        return Response(
                            {'message': 'Account verified successfully. You can now log in.'},
                            status=status.HTTP_200_OK
                        )
                    except User.DoesNotExist:
                        return Response(
                            {'message': 'No unverified user found with this phone number.'},
                            status=status.HTTP_404_NOT_FOUND
                        )
                else:
                    return Response(
                        {'message': 'Invalid OTP.'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except OTP.DoesNotExist:
                return Response(
                    {'message': 'Invalid or expired OTP. Please request a new one.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                print(f"Error during new user OTP verification: {e}")
                return Response(
                    {'message': 'An unexpected error occurred during verification.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# @api_view(['PUT'])
# @permission_classes([IsAuthenticated])
# def update_user_details(request):
#     user = request.user
#     data = request.data
#     print(request)

#     try:
#         user.username = data.get('username', user.username)
#         user.company_name = data.get('company', user.company_name)
#         user.city = data.get('city', user.city)
#         user.address = data.get('address', user.address)
#         user.save()

#         return Response({"message": "User details updated successfully."}, status=status.HTTP_200_OK)
#     except Exception as e:
#         return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

def generate_payment_reference(prefix='TXN', length=9):
    
    random_number = ''.join(random.choices('0123456789', k=length))
    
    return f"{prefix}{random_number}"

def split_full_name(full_name_str):
    names = full_name_str.strip().split(' ')
    first_name = names[0] if names else ''
    last_name = ' '.join(names[1:]) if len(names) > 1 else first_name
    return first_name, last_name


def Generate_referral_code():
    while True:
        # Generate a random 6-digit number between 345000 and 699999
        code = str(random.randint(345000, 699999))
        
        
        if not UserProfile.objects.filter(referral_code=code).exists():
            return code 
        
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    required_fields = ['full_name', 'email', 'password', 'phone_number', 'profile']
    missing_fields = [field for field in required_fields if field not in request.data]

    print(f"This is the data from the frontend: {request.data}")

    if missing_fields:
        return Response({"error": f"Missing fields: {', '.join(missing_fields)}"}, status=status.HTTP_400_BAD_REQUEST)

    profile_data = request.data.get('profile', {})
    subscription_plan_id = request.data.get('subscription_plan_id')
    phone_number_raw = request.data.get('phone_number')
   

    if not phone_number_raw:
        return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    if phone_number_raw[0] == 0 and len(phone_number_raw) == 10:
        phone_number_raw = phone_number_raw[-9:]

    formatted_phone_number = '+233' + phone_number_raw

    referrer = None
    referral_code = request.data.get('referral_code')
    if referral_code:
        try:
            referrer_profile = UserProfile.objects.get(referral_code=referral_code)
            referrer = referrer_profile.user
        except UserProfile.DoesNotExist:
            return Response({"error": "Invalid referral code."}, status=status.HTTP_400_BAD_REQUEST)

    print("Validation reached here")
    print('Beginning user creation')
    fullname = request.data['full_name']

    firstname , lastname = split_full_name(fullname)
    email = request.data.get('email')

    try:
        user_data = {
            'full_name': request.data['full_name'].replace(" ", "_"),
            'email': email.lower(),
            'password': request.data['password'],
            'phone_number': formatted_phone_number,
            'username': request.data['full_name'].replace(" ", ""),
            'first_name': firstname,
            'last_name':lastname,
            'profile': {
                'company_name': profile_data.get('company_name'),
                'address': profile_data.get('address'),
                'city': profile_data.get('city'),
            }
        }
        print(f"User data prepared: {user_data}")

        serializer = CustomUserSerializer(data=user_data)

        if serializer.is_valid():
            print("Passed serializer validation")
            user = serializer.save(is_active=True) # IMPORTANT: Mark user as inactive/unverified
            user_profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'company_name': profile_data.get('company_name', ''),
                    'address': profile_data.get('address', ''),
                    'city': profile_data.get('city', ''),
                    
                    # Set other default profile fields if necessary
                }
            )
            # If for some reason it wasn't created (e.g., already existed, though unlikely for new user), update it
            if not created:
                user_profile.company_name = profile_data.get('company_name', user_profile.company_name)
                user_profile.address = profile_data.get('address', user_profile.address)
                user_profile.city = profile_data.get('city', user_profile.city)


            # --- OTP GENERATION AND SMS SENDING ---
            # Delete any old OTPs for this number to avoid UniqueViolation
            # OTP.objects.filter(phone_number=formatted_phone_number).delete()
            # otp_instance = OTP.objects.create(user=user, phone_number=formatted_phone_number)
            # otp_code = otp_instance.code

            # sms_sent, sms_message = send_otp_sms(formatted_phone_number, otp_code)

            # if not sms_sent:
            #     # If SMS sending fails, you might want to delete the user or mark them for later re-sending OTP
            #     # For now, we'll return an error, as verification is mandatory.
            #     user.delete() # Clean up the user if SMS failed critical path
            #     return Response(
            #         {"error": f"Account creation failed: {sms_message}"},
            #         status=status.HTTP_500_INTERNAL_SERVER_ERROR
            #     )

            new_referral_code = Generate_referral_code()

            if hasattr(user, 'profile') and user.profile:
                user.profile.referral_code = new_referral_code
                user.profile.save()
            else:
                print("Warning: UserProfile not found for new user, cannot assign referral code.")

            if subscription_plan_id:
                try:
                    plan = SubscriptionPlan.objects.get(id=subscription_plan_id)
                    UserSubscription.objects.create(
                        user=user,
                        plan=plan,
                        start_date=now(),
                        end_date=now() + timedelta(days=plan.duration_in_days),
                        payment_status='Pending'
                    )
                except SubscriptionPlan.DoesNotExist:
                    return Response({"error": "Invalid subscription plan ID"}, status=status.HTTP_400_BAD_REQUEST)

            if referrer:
                Referral.objects.create(
                    referrer=referrer,
                    referee=user,
                    code=referral_code
                )

            try:
                free_plan = SubscriptionPlan.objects.get(name='Free Plan')
                UserSubscription.objects.create(
                    user=user,
                    plan=free_plan,
                    start_date=now(),
                    end_date=now() + timedelta(days=free_plan.duration_in_days),
                    is_active=True,
                    payment_status='Pending',
                    is_trial_active=True,
                )
            except SubscriptionPlan.DoesNotExist:
                return Response({"error": "Free plan does not exist. Please create a 'Free Plan' in the database."}, status=status.HTTP_400_BAD_REQUEST)

            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'message': "User registered successfully",
                'referral_code': new_referral_code,
                'user': {
                    'id': user.id,
                    'phone_number': user.phone_number,
                    'email': user.email
                }
            }, status=status.HTTP_201_CREATED)

        else:
            print(f"Serializer errors: {serializer.errors}")
            return Response({"error": "Invalid data", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
# views.py
def verify_payment(request):
    if request.method == 'GET':
        reference = request.GET.get('reference')  
        url = f"https://api.paystack.co/transaction/verify/{reference}"

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        }

        try:
            response = requests.get(url, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data['status']:
                return JsonResponse({
                    "status": "success",
                    "message": "Payment verified successfully",
                    "data": response_data['data'],
                })

            return JsonResponse({
                "status": "error",
                "message": response_data.get('message', 'Payment verification failed'),
            }, status=400)

        except Exception as e:
            return JsonResponse({
                "status": "error",
                "message": str(e),
            }, status=500)

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=405)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def GetReferralCodeView(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        return Response({'referral_code': user_profile.referral_code}, status=200)
    except UserProfile.DoesNotExist:
        return Response({'error': 'UserProfile not found'}, status=404)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_details(request):
    # Get the authenticated user
    user = request.user
    try:
        # Get the UserProfile for the authenticated user
        user_profile = get_object_or_404(UserProfile, user=user)
        
        # Prepare the response data
        data = {
            "username": user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "company_name": user_profile.company_name,
            "city": user_profile.city,
            "address": user_profile.address
        }
        return Response(data, status=200)
    except UserProfile.DoesNotExist:
        return Response({'error': 'User profile not found'}, status=404)
    
@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_details(request):
    user = request.user
    try:
        user_profile = get_object_or_404(UserProfile, user=user)

        # Get the updated fields from the request
        username = request.data.get('username', '').strip()
        company_name = request.data.get('company', '').strip()
        city = request.data.get('city', '').strip()
        address = request.data.get('address', '').strip()

        # Basic validation (you can expand this as needed)
        if not username or not company_name or not city or not address:
            return Response({'message': 'All fields are required.'}, status=400)

        # Update the user fields
        user.username = username
        user.save()

        # Update the user profile fields
        user_profile.company_name = company_name
        user_profile.city = city
        user_profile.address = address
        user_profile.save()

        return Response({'message': 'User details updated successfully.'}, status=200)

    except Exception as e:
        return Response({'message': 'An error occurred while updating user details.', 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    identifier = request.data.get('identifier')  # username, email, or phone number
    password = request.data.get('password')
    original_identifier = identifier  # keep for username/email check

    def normalize_phone(phone):
        digits = re.sub(r'\D', '', phone)
        if digits.startswith('0') and len(digits) == 10:
            return '+233' + digits[1:]
        elif digits.startswith('233') and len(digits) == 12:
            return '+' + digits
        elif len(digits) == 9:
            return '+233' + digits
        elif digits.startswith('020') and len(digits) == 12:
            return '+233' + digits[3:]  # handle +233020...
        return phone

    
    identifier = normalize_phone(identifier)
    print(identifier)


    user = User.objects.filter(
        models.Q(username=original_identifier) |
        models.Q(email=original_identifier.lower()) |
        models.Q(phone_number=identifier)
    ).first()
    

    if user and user.check_password(password):
        refresh = RefreshToken.for_user(user)
        return Response({'refresh': str(refresh), 'access': str(refresh.access_token),"user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
            }}, status=status.HTTP_200_OK)

    return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)


# Subscription Plans
@api_view(['GET'])
@permission_classes([AllowAny])
def list_subscription_plans(request):
    plans = SubscriptionPlan.objects.all()
    serializer = SubscriptionPlanSerializer(plans, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_plan_details(request):
    """
    API endpoint to get details of the selected subscription plan.
    This endpoint does not create any subscription, it's just for fetching plan details.
    """
    selected_plan_id = request.data.get('id')
    
    if not selected_plan_id:
        return Response({"error": "Plan ID is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        selected_plan = SubscriptionPlan.objects.get(id=selected_plan_id)
    except SubscriptionPlan.DoesNotExist:
        return Response({"error": "Invalid plan ID."}, status=status.HTTP_404_NOT_FOUND)

    # Serialize and return the selected plan details
    plan_details = SubscriptionPlanSerializer(selected_plan).data

    return Response({
        "message": "Plan details fetched successfully.",
        "plan_details": plan_details  # Returning plan details for the frontend to display
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_subscription(request):
    """
    API endpoint to create a subscription for the user after successful payment.
    """
    user = request.user
    selected_plan_id = request.data.get('id')
    
    if not selected_plan_id:
        return Response({"error": "Plan ID is required."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        selected_plan = SubscriptionPlan.objects.get(id=selected_plan_id)
    except SubscriptionPlan.DoesNotExist:
        return Response({"error": "Invalid plan ID."}, status=status.HTTP_404_NOT_FOUND)

    # You might want to check payment success before proceeding here
    # For example, this is where you integrate the payment gateway callback.

    # Calculate subscription end date
    end_date = now() + timedelta(days=selected_plan.duration_in_days)

    # Create or update the user's subscription
    subscription, created = UserSubscription.objects.update_or_create(
        user=user,
        defaults={"plan": selected_plan, "end_date": end_date}
    )

    # Serialize the subscription data and return it
    subscription_data = UserSubscriptionSerializer(subscription).data

    return Response({
        "message": "Subscription created successfully.",
        "subscription_data": subscription_data  # Return subscription details after successful payment
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_to_plan(request):
    """
    API endpoint to handle user subscription to a plan.
    """
    user = request.user
    selected_plan_id = request.data.get('id')

    if not selected_plan_id:
        return Response({"error": "Plan ID is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        selected_plan = SubscriptionPlan.objects.get(id=selected_plan_id)
    except SubscriptionPlan.DoesNotExist:
        return Response({"error": "Invalid plan ID."}, status=status.HTTP_404_NOT_FOUND)

    # Calculate subscription end date
    end_date = now() + timedelta(days=selected_plan.duration_in_days)

    # Create or update the user's subscription
    subscription, created = UserSubscription.objects.update_or_create(
        user=user,
        defaults={"plan": selected_plan, "end_date": end_date}
    )

    return Response({
        "message": "Subscription successful.",
        "plan": SubscriptionPlanSerializer(selected_plan).data,
        "start_date": subscription.start_date,
        "end_date": subscription.end_date
    }, status=status.HTTP_200_OK)

# User Subscription Management
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_subscription(request):
    plan_id = request.data.get('plan_id')
    if not plan_id:
        return Response({"error": "Plan ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        plan = SubscriptionPlan.objects.get(id=plan_id)
        subscription, created = UserSubscription.objects.get_or_create(user=request.user)
        subscription.plan = plan
        subscription.start_date = now()
        subscription.end_date = now() + timedelta(days=plan.duration_in_days)
        subscription.payment_status = 'Pending'
        subscription.save()
        return Response({"success": "Subscription updated successfully"}, status=status.HTTP_200_OK)
    except SubscriptionPlan.DoesNotExist:
        return Response({"error": "Invalid plan ID"}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def user_contact_info_view(request, username):
    """
    API endpoint to get user's first name and contact info (email or phone).
    Handles GET requests.
    """
    try:
        user = CustomUser.objects.get(username=username)
    except CustomUser.DoesNotExist:
        return Response(
            {"detail": "User not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    data = {
        'first_name': user.first_name,
        'contact': None,
        'contact_type': None,
    }

    # Check if email is available (not None and not empty string)
    if user.email: # Django EmailField returns '' for blank=True
        data['contact'] = user.email
        data['contact_type'] = 'email'
    # If email is not available, check phone number
    elif user.phone_number: # PhoneNumberField can be None
         # Convert PhoneNumber object to string for JSON
        data['contact'] = str(user.phone_number)
        data['contact_type'] = 'phone_number'
    # If neither email nor phone exists, contact and contact_type remain None.

    return Response(data, status=status.HTTP_200_OK)

# def process_payment_with_third_party(amount, reference):
#     # # The third-party API endpoint (this is a placeholder; you'll use the actual URL)
#     # payment_gateway_url = "https://thirdparty.com/api/payments"
    
#     # # Payment details to send to the third-party system
#     # payment_data = {
#     #     'amount': amount,
#     #     'reference': reference,
#     #     # Other data needed for the payment, e.g., user info, etc.
#     # }
    
#     # # Send the request to the third-party payment gateway
#     # try:
#     #     response = request.post(payment_gateway_url, data=payment_data)
        
#     #     # Handle response: check if payment is successful
#     #     if response.status_code == 200:
#     #         payment_response = response.json()
#     #         return payment_response['status']  # Return 'Paid' or 'Failed' status
#     #     else:
#     #         return 'Failed'
#     # except Exception as e:
#     #     # If the request fails, you can log the exception or return a 'Failed' status
#     #     print(f"Error contacting payment gateway: {e}")
#     #     return 'Failed'
#     return 'Paid'

# # Payment Handling
# @api_view(['POST'])
# @permission_classes([IsAuthenticated])
# def create_payment(request):
#     # Get payment data from the request
#     amount = request.data.get('amount')
#      # Default to 'Pending' for testing
#     Plan_name = request.data.get('selected_plan')
#     print(amount)
#     reference = generate_payment_reference()
#     # Validate input
#     if not amount or not reference:
#         return Response({"error": "Amount and reference are required"}, status=status.HTTP_400_BAD_REQUEST)

#     # Check if a payment with the same reference already exists
#     while Payment.objects.filter(reference=reference).exists():
#         reference = generate_payment_reference()

#     # Create a payment record with 'Pending' status initially
#     payment = Payment.objects.create(
#         user=request.user,
#         amount=amount,
#         reference=reference,
#         status='Pending'
#     )
    
#     payment_status = process_payment_with_third_party(amount, reference)

#     # Simulate a payment response based on the provided status
#     if payment_status == 'Paid':
#     # Update the payment status of the payment object
#         payment.status = 'Paid'
#         payment.save()

#         try:
#             # Check if the user already has an active subscription
#             subscription = UserSubscription.objects.get(user=request.user)

#             # Fetch the new plan the user is upgrading to
#             plan = SubscriptionPlan.objects.get(name=Plan_name)

#             # Check if the current plan is different from the new plan
#             if subscription.plan != plan:
#                 # User is upgrading, add the new limits to the current usage
#                 subscription.plan = plan
#                 subscription.start_date = now()
#                 subscription.end_date = now() + timedelta(days=plan.duration_in_days)
#                 subscription.is_active = True
#                 subscription.payment_status = 'Paid'
#                 subscription.is_trial_active = False

#                 # Add the new limits to the existing used limits
#                 subscription.project_limit += plan.project_limit
#                 subscription.three_d_views_limit += plan.three_d_view_limit

#                 subscription.save()

#             else:
#                 # If the plan is the same, just renew the subscription
#                 subscription.end_date = now() + timedelta(days=plan.duration_in_days)
#                 subscription.is_active = True
#                 subscription.payment_status = 'Paid'
#                 subscription.save()

#         except UserSubscription.DoesNotExist:
#             # Create a new subscription if none exists
#             plan = SubscriptionPlan.objects.get(name=Plan_name)
#             UserSubscription.objects.create(
#                 user=request.user,
#                 plan=plan,
#                 start_date=now(),
#                 end_date=now() + timedelta(days=plan.duration_in_days),
#                 is_active=True,
#                 payment_status='Paid',
#                 is_trial_active=False,
#                 project_limit=plan.project_limit,
#                 three_d_views_limit=plan.three_d_view_limit
#             )


#     elif payment_status == 'Failed':
#         # If the status is 'Failed', update the payment status accordingly
#         payment.status = 'Failed'
#         try:
#             subscription = UserSubscription.objects.get(user=request.user)
#             subscription.payment_status = 'Failed'
#             subscription.is_active = False  # Mark the subscription as inactive
#             subscription.save()
#         except UserSubscription.DoesNotExist:
#             pass

#     # Save the payment record with the updated status
#     payment.save()

#     # Return a success response
#     return Response({"success": "Payment recorded successfully", "payment_status": payment.status}, status=status.HTTP_201_CREATED)

@api_view(["POST"])
def upgrade_subscription(request):
    user = request.user
    plan_id = request.data.get("plan_id")

    try:
        # Fetch the new subscription plan
        new_plan = SubscriptionPlan.objects.get(id=plan_id)

        # Fetch the current user's subscription
        subscription, created = UserSubscription.objects.get_or_create(user=user)

        
        subscription.upgrade_subscription(new_plan)

        return Response({"message": "Subscription upgraded successfully."})

    except SubscriptionPlan.DoesNotExist:
        return Response({"error": "Invalid subscription plan."}, status=400)

    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
def send_message(request):
    if request.method == 'POST':
        serializer = ContactMessageSerializer(data=request.data)

        if serializer.is_valid():
            # Extract data from serializer
            name = serializer.validated_data['name']
            email = serializer.validated_data['email']
            message = serializer.validated_data['message']

            # Send the email
            subject = f'New Message from {name}'
            message_content = f'Name: {name}\nEmail: {email}\nMessage: {message}'
            recipient_email = 'your_email@gmail.com'  # The email where you want to receive messages

            try:
                send_mail(subject, message_content, email, [recipient_email])
                return Response({'message': 'Email sent successfully!'}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset(request):
    email = request.data.get('email')

    if not email:
        return JsonResponse({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    # Generate a 6-digit code
    reset_code = random.randint(100000, 999999)
    
    # Store the reset code temporarily (with an expiration time, e.g., 10 minutes)
    expiration_time = datetime.now() + timedelta(minutes=10)
    PasswordResetCode.objects.create(user=user, code=reset_code, expiration_time=expiration_time)
    

@api_view(['POST'])
@permission_classes([AllowAny])
def validate_reset_code(request):
    email = request.data.get('email')
    code = request.data.get('code')

    if not email or not code:
        return JsonResponse({'error': 'Email and code are required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

    # Check if the code exists for the user and is not expired
    try:
        reset_code = PasswordResetCode.objects.get(user=user, code=code)
        
        if reset_code.is_expired():
            return JsonResponse({'error': 'The code has expired'}, status=status.HTTP_400_BAD_REQUEST)

    except PasswordResetCode.DoesNotExist:
        return JsonResponse({'error': 'Invalid code'}, status=status.HTTP_400_BAD_REQUEST)

    # Code is valid
    return JsonResponse({'success': 'Code is valid. You can now reset your password.'}, status=status.HTTP_200_OK)



    # Send the code via email
    # send_mail(
    #     'Password Reset Request',
    #     f'Your password reset code is {reset_code}. It will expire in 10 minutes.',
    #     settings.DEFAULT_FROM_EMAIL,  # Use your email configuration from settings.py
    #     [email],
    #     fail_silently=False,
    # )

    return JsonResponse({'success': 'Password reset code has been sent to your email.'}, status=status.HTTP_200_OK)
def leaderboard(request):
    # Get the top 10 referrers ordered by the number of successful referrals
    top_referrers = User.objects.annotate(num_referrals=Count('referrals')).order_by('-num_referrals')[:10]
    
    # Create a leaderboard list with rank
    leaderboard_data = []
    for index, referrer in enumerate(top_referrers, start=1):
        leaderboard_data.append({
            'rank': index,
            'referrer_username': referrer.username,
            'num_referrals': referrer.num_referrals,
        })
    
    # Return the data as a JSON response
    return JsonResponse(leaderboard_data, safe=False)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_password(request):
    user = request.user
    current_password = request.data.get('current_password')
    new_password = request.data.get('new_password')

    if not user.check_password(current_password):
        return Response({'message': 'Current password is incorrect'}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 8:  # Example of additional validation
        return Response({'message': 'Password must be at least 8 characters long'}, status=status.HTTP_400_BAD_REQUEST)

    user.password = make_password(new_password)
    user.save()

    return Response({'message': 'Password updated successfully'}, status=status.HTTP_200_OK)

@api_view(['GET'])
def check_subscription(request):
    user = request.user  # Assumes user is authenticated
    try:
        subscription = UserSubscription.objects.get(user=user)
        return Response({"active": subscription.has_active_subscription})
    except UserSubscription.DoesNotExist:
        return Response({"active": False})

def handle_payment_success(request):
    # Extract payment details from the request (e.g., payment gateway data)
    payment_data = request.POST  # Or you can use request.body or request.data (if using DRF)

    # Extract the necessary information (e.g., user ID, chosen plan, payment status)
    user_id = payment_data.get('user_id')
    plan_id = payment_data.get('plan_id')
    payment_status = payment_data.get('payment_status')

    if payment_status == 'success':
        # Find the user and subscription plan
        user = get_object_or_404(User, id=user_id)
        plan = get_object_or_404(SubscriptionPlan, id=plan_id)
        
        # Update the user's subscription
        user_subscription, created = UserSubscription.objects.get_or_create(user=user)
        
        # Update the subscription with the new plan details
        user_subscription.plan = plan
        user_subscription.payment_status = 'Paid'  # Payment successful
        user_subscription.is_active = True  # Subscription is now active
        
        # Add new limits from the plan (without resetting usage)
        user_subscription.projects_created = min(user_subscription.projects_created, plan.project_limit)
        user_subscription.three_d_views_used = min(user_subscription.three_d_views_used, plan.three_d_view_limit)

        # Update the subscription end date (add the new duration)
        user_subscription.end_date = user_subscription.start_date + timedelta(days=plan.duration_in_days)

        # Save the updated subscription
        user_subscription.save()

        # Return success response
        return JsonResponse({'status': 'success', 'message': 'Subscription updated successfully.'})
    else:
        # Handle failed payment
        return JsonResponse({'status': 'failed', 'message': 'Payment failed.'})

# def create_project(request):
#     if request.method == 'POST':
#         user = request.user
#         subscription = user.subscription

#         # Check if the subscription is active and within the valid period
#         if not subscription.is_active or subscription.end_date < now():
#             return JsonResponse({"success": False, "error": "Your subscription has expired. Please renew to continue."})

#         # Check if the user has reached their project limit
#         if subscription.projects_created >= subscription.plan.project_limit:
#             return JsonResponse({"success": False, "error": "Project limit reached for your current subscription."})

#         # Proceed with project creation
#         project_name = request.POST.get('name')
#         project = Project.objects.create(user=user, name=project_name)

#         # Increment the projects_created count
#         subscription.projects_created += 1
#         subscription.save()

#         return JsonResponse({"success": True, "message": "Project created successfully.", "project_id": project.id})


# def renew_subscription(user, new_plan):
#     subscription = user.subscription
#     subscription.plan = new_plan
#     subscription.start_date = now()
#     subscription.end_date = now() + timedelta(days=new_plan.duration_days)
#     subscription.projects_created = 0  # Reset project count
#     subscription.is_active = True
#     subscription.save()


# def deactivate_expired_subscriptions():
#     expired_subscriptions = Subscription.objects.filter(is_active=True, end_date__lt=now())
#     expired_subscriptions.update(is_active=False)


# def get_subscription_status(request):
#     user = request.user
#     subscription = user.subscription
#     remaining_projects = subscription.plan.project_limit - subscription.projects_created

#     return JsonResponse({
#         "success": True,
#         "plan_name": subscription.plan.name,
#         "remaining_projects": remaining_projects,
#         "project_limit": subscription.plan.project_limit,
#         "end_date": subscription.end_date
#     })

@api_view(['POST'])
@permission_classes([AllowAny]) # Allow anyone to request a code initially
def send_verification_sms(request):
    """
    API endpoint to generate and send a phone number verification SMS using Africa's Talking.
    Expects 'phone_number' in the request data.
    """
    phone_number = request.data.get('phone_number')
    print(f"Received request to send SMS to: {phone_number}")

    if not phone_number:
        print("Error: Phone number not provided in request data.")
        return Response({"error": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

    if not phone_number.startswith('+') or not phone_number[1:].isdigit():
         print(f"Error: Invalid phone number format: {phone_number}")
         return Response({"error": "Invalid phone number format. Please include country code (e.g., +233...)."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Generate a new code
        code = VerificationCode.generate_code()
        # Expiry is set in the model's save method based on settings.VERIFICATION_CODE_EXPIRY_MINUTES

        # Invalidate any existing unused codes for this phone number
        # This prevents using an old code if a new one is requested
        expired_count = VerificationCode.objects.filter(
            phone_number=phone_number,
            is_used=False,
            expires_at__gt=timezone.now() # Only invalidate codes that are currently valid
        ).update(is_used=True)
        if expired_count > 0:
            print(f"Invalidated {expired_count} existing valid codes for {phone_number}.")


        # Save the new code instance
        # You can link this code to a user if you have the user object available
        # user = None # Get user object if needed (e.g., from authenticated request or user_id param)
        verification_code_instance = VerificationCode.objects.create(
            # user=user, # Link to user if applicable (e.g., after user registration)
            phone_number=phone_number,
            code=code,
            # expires_at is set automatically in the model's save method
        )
        print(f"Verification code instance created for {phone_number} with code {code}.")


        # --- Send SMS using Africa's Talking ---
        print(f"Attempting to send SMS via Africa's Talking to {phone_number}...")
        message_body = f"Your TILNET verification code is: {code}. It expires in {settings.VERIFICATION_CODE_EXPIRY_MINUTES} minutes."
        sms_response_data = send_sms_africastalking(to=phone_number, message=message_body)

        # Check the response from the Africa's Talking API call
        if sms_response_data and sms_response_data.get('SMSMessageData', {}).get('Recipients'):
             # Africa's Talking returns a list of recipients if submission was successful
             print(f"SMS successfully submitted to Africa's Talking for {phone_number}. Response: {sms_response_data}")
             return Response({"message": "Verification code sent successfully."}, status=status.HTTP_200_OK)
        else:
             # SMS submission failed or response format was unexpected
             error_message = sms_response_data.get('SMSMessageData', {}).get('Message') if sms_response_data else "Unknown error from AT"
             print(f"Failed to submit SMS to Africa's Talking for {phone_number}. Error: {error_message}")
             # Optionally mark the code instance as failed or log the error more permanently
             # verification_code_instance.is_used = True # Or add a 'status' field
             # verification_code_instance.save()
             return Response({"error": f"Failed to send verification SMS: {error_message}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    except Exception as e:
        # Catch any unexpected exceptions during the process
        print(f"!!! Unexpected Error occurred during SMS sending for {phone_number}: {str(e)} !!!")
        traceback.print_exc() # Print full traceback for debugging
        return Response({"error": "An internal error occurred while sending SMS."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny]) # Allow anyone to verify a code initially
def verify_phone_number(request):
    """
    API endpoint to verify a phone number using a received code.
    Expects 'phone_number' and 'code' in the request data.
    """
    phone_number = request.data.get('phone_number')
    code = request.data.get('code')

    print(f"Received verification request for phone: {phone_number}, code: {code}")

    if not phone_number or not code:
        print("Error: Phone number or code not provided.")
        return Response({"error": "Phone number and code are required."}, status=status.HTTP_400_BAD_REQUEST)

    # Optional: Basic phone number format validation (should match format used in send_verification_sms)
    if not phone_number.startswith('+') or not phone_number[1:].isdigit():
         print(f"Error: Invalid phone number format: {phone_number}")
         return Response({"error": "Invalid phone number format."}, status=status.HTTP_400_BAD_REQUEST)


    try:
        # Find the latest unused code for this phone number that is not expired
        # We use .latest('created_at') to get the most recently generated code
        verification_code_instance = VerificationCode.objects.filter(
            phone_number=phone_number,
            is_used=False, # Code must not have been used yet
            expires_at__gt=timezone.now() # Code must not be expired
        ).latest('created_at')

        print(f"Found latest valid code instance for {phone_number}. Code: {verification_code_instance.code}")

        # Compare the provided code with the stored code
        if verification_code_instance.code == code:
            print(f"Provided code matches stored code for {phone_number}.")
            # Code is valid! Mark it as used.
            verification_code_instance.is_used = True
            verification_code_instance.save()
            print(f"Verification code instance {verification_code_instance.id} marked as used.")

            # --- Optional: Mark the user's phone number as verified ---
            # Assuming your CustomUser model has an 'is_phone_verified' boolean field
            # and the VerificationCode is linked to the user (either directly or by phone_number lookup)
            # user = User.objects.filter(phone_number=phone_number).first() # Lookup user by phone number
            # if user:
            #     user.is_phone_verified = True
            #     user.save()
            #     print(f"User {user.id}'s phone number marked as verified.")
            # # If you linked the code to the user instance during registration:
            # # if verification_code_instance.user:
            # #     verification_code_instance.user.is_phone_verified = True
            # #     verification_code_instance.user.save()
            # #     print(f"User {verification_code_instance.user.id}'s phone number marked as verified.")


            # --- Return success response ---
            # If phone verification is the final step before login, you might generate
            # and return JWT tokens here instead of just a success message.
            # If tokens were already returned during registration, just confirm verification.
            return Response({"message": "Phone number verified successfully."}, status=status.HTTP_200_OK)

        else:
            # Code does not match
            print(f"Provided code '{code}' does not match stored code '{verification_code_instance.code}' for {phone_number}.")
            return Response({"error": "Invalid verification code."}, status=status.HTTP_400_BAD_REQUEST)

    except VerificationCode.DoesNotExist:
        # No valid, unused, non-expired code found for this phone number
        print(f"No valid, unused, non-expired code found for {phone_number}.")
        return Response({"error": "Invalid or expired verification code."}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        # Catch any unexpected exceptions during the process
        print(f"!!! Unexpected Error occurred during phone number verification for {phone_number}: {str(e)} !!!")
        traceback.print_exc() # Print full traceback for debugging
        return Response({"error": "An internal error occurred during verification."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

