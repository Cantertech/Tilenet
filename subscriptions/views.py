
from datetime import timedelta
from decimal import Decimal
import traceback
import uuid
from rest_framework import viewsets, generics, status,permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.utils import timezone
import requests
import json
import time
import hashlib
import hmac
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from .models import  PaymentTransaction
from .serializers import (
    SubscriptionPlanSerializer, UserSubscriptionSerializer,
    PaymentTransactionSerializer, InitiatePaymentSerializer
)
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.urls import reverse
# your_app_name/views.py
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from django.core.cache import cache
import africastalking
from .models import OTP
from .serializers import PhoneNumberSerializer, VerifyOTPAndSetPasswordSerializer
from .utils import format_ghanaian_phone_number
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
import logging # Import logging

User = get_user_model()

from accounts.models import  SubscriptionPlan, UserSubscription # Import your models

# --- Helper function for subscription logic ---
from datetime import timedelta
from django.utils import timezone

def activate_user_subscription(user_instance, subscription_plan, reference):
    """
    Activates or updates a user's subscription based on the selected plan.
    Respects unused limits unless the subscription has expired.
    """
    print(f"[{reference}] Activating subscription for user {user_instance.id} with plan '{subscription_plan.name}'...")

    try:
        user_sub, created = UserSubscription.objects.get_or_create(user=user_instance)
        now = timezone.now()

        # Common updates
        user_sub.plan = subscription_plan
        user_sub.payment_status = 'Paid'
        user_sub.is_active = True
        user_sub.is_trial_active = False

        if subscription_plan.duration_in_days > 0:
            # Time-based plan (e.g., Free, Basic, Contractor)
            if user_sub.end_date and user_sub.end_date > now:
                # Extend current subscription from end_date, usage remains untouched
                user_sub.end_date += timedelta(days=subscription_plan.duration_in_days)
                print(f"[{reference}] Subscription extended. Usage preserved.")
            else:
                # Plan expired or no end_date – reset usage and start fresh
                user_sub.start_date = now
                user_sub.end_date = now + timedelta(days=subscription_plan.duration_in_days)
                user_sub.projects_created = 0
                user_sub.three_d_views_used = 0
                user_sub.manual_estimates_used = 0
                print(f"[{reference}] Subscription renewed. Usage counters reset.")

            user_sub.project_limit = subscription_plan.project_limit
            user_sub.three_d_views_limit = subscription_plan.three_d_view_limit
            user_sub.manual_estimate_limit = subscription_plan.manual_estimate_limit

        elif subscription_plan.name == 'Pay-Per-Use':
            user_sub.project_limit += subscription_plan.project_limit
            user_sub.three_d_views_limit += subscription_plan.three_d_view_limit
            user_sub.manual_estimate_limit += subscription_plan.manual_estimate_limit
            print(f"[{reference}] Pay-Per-Use plan purchased. Limits incremented.")

        elif subscription_plan.name == 'Add-On Pack':
            user_sub.three_d_views_limit += subscription_plan.three_d_view_limit
            user_sub.manual_estimate_limit += subscription_plan.manual_estimate_limit
            print(f"[{reference}] Add-On Pack applied. Extra features added.")

        else:
            print(f"[{reference}] Unrecognized plan: {subscription_plan.name} (ID: {subscription_plan.id})")

        user_sub.save()
        print(f"[{reference}] Subscription for user {user_instance.email} saved.")
        return True

    except Exception as e:
        print(f"[{reference}] Error activating subscription for user {user_instance.email}: {e}")
        return False
    
def activate_user_subscription(user_instance, subscription_plan, received_amount_ghs, reference):
    """
    Activates or updates a user's subscription based on the selected plan.
    Respects unused limits unless the subscription has expired.
    """
    print(f"[{reference}] Activating subscription for user {user_instance.id} with plan '{subscription_plan.name}'...")

    try:
        user_sub, created = UserSubscription.objects.get_or_create(user=user_instance)
        now = timezone.now()

        # Common updates
        user_sub.plan = subscription_plan
        user_sub.payment_status = 'Paid'
        user_sub.is_active = True
        user_sub.is_trial_active = False

        if subscription_plan.duration_in_days > 0:
            # Time-based plan (e.g., Free, Basic, Contractor)
            if user_sub.end_date and user_sub.end_date > now:
                # Extend current subscription from end_date, usage remains untouched
                user_sub.end_date += timedelta(days=subscription_plan.duration_in_days)
                print(f"[{reference}] Subscription extended. Usage preserved.")
            else:
                # Plan expired or no end_date – reset usage and start fresh
                if not created: # Only update start_date if it's a new subscription or explicitly needs resetting
                    user_sub.start_date = now
                user_sub.end_date = now + timedelta(days=subscription_plan.duration_in_days)
                user_sub.projects_created = 0
                user_sub.three_d_views_used = 0
                user_sub.manual_estimates_used = 0
                print(f"[{reference}] Subscription renewed. Usage counters reset.")

            user_sub.project_limit = subscription_plan.project_limit
            user_sub.three_d_views_limit = subscription_plan.three_d_view_limit
            user_sub.manual_estimate_limit = subscription_plan.manual_estimate_limit

        elif subscription_plan.name == 'Pay-Per-Use':
            user_sub.project_limit += subscription_plan.project_limit
            user_sub.three_d_views_limit += subscription_plan.three_d_view_limit
            user_sub.manual_estimate_limit += subscription_plan.manual_estimate_limit
            print(f"[{reference}] Pay-Per-Use plan purchased. Limits incremented.")

        elif subscription_plan.name == 'Add-On Pack':
            user_sub.three_d_views_limit += subscription_plan.three_d_view_limit
            user_sub.manual_estimate_limit += subscription_plan.manual_estimate_limit
            print(f"[{reference}] Add-On Pack applied. Extra features added.")

        else:
            print(f"[{reference}] Unrecognized plan: {subscription_plan.name} (ID: {subscription_plan.id})")

        user_sub.save()
        print(f"[{reference}] Subscription for user {user_instance.email} saved.")
        return True

    except Exception as e:
        print(f"[{reference}] Error activating subscription for user {user_instance.email}: {e}")
        return False


# New function to process successful payments
def process_successful_payment(payment_record: PaymentTransaction, paystack_data: dict) -> bool:
    """
    Handles the business logic for a successful payment.
    Updates the payment record, performs idempotency checks,
    verifies amount, and activates the user's subscription.
    """
    reference = payment_record.reference
    print(f"[{reference}] Processing successful payment...")

    try:
        # --- Idempotency Check ---
        if payment_record.status == 'completed':
            print(f"[{reference}] Payment already completed. Ignoring duplicate processing.")
            return True # Already processed, so consider it a success

        # 2. Verify important details (optional but recommended for security)
        paystack_amount_pesewas = paystack_data.get('amount')
        if paystack_amount_pesewas is None:
            print(f"[{reference}] Paystack data missing 'amount'. Cannot verify.")
            return False

        received_amount_ghs = paystack_amount_pesewas / 100

        # Compare with the amount you stored (which is in GHS)
        if received_amount_ghs != float(payment_record.amount):
            print(f"[{reference}] Amount mismatch! Expected {payment_record.amount} GHS, received {received_amount_ghs} GHS.")
            payment_record.status = 'amount_mismatch' # Or 'failed_fraud_attempt'
            payment_record.gateway_response = f"Amount mismatch: Expected {payment_record.amount}, Received {received_amount_ghs}"
            payment_record.save()
            # While it's an error, we return True to acknowledge Paystack and prevent retries for this reference
            return True

        # 3. Update the PaymentTransaction status
        payment_record.status = 'completed'
        payment_record.completed_at = timezone.now() # Record completion time
        payment_record.paystack_response_status = paystack_data.get('status')
        payment_record.gateway_response = paystack_data.get('gateway_response')
        payment_record.save()
        print(f"[{reference}] PaymentTransaction status updated to 'completed'.")

        # 4. Activate user's subscription
        user_instance = payment_record.user # Assuming payment_record has a ForeignKey to User

        if not user_instance:
            print(f"[{reference}] No user associated with this payment record.")
            return False

        try:
            matched_plan = SubscriptionPlan.objects.get(price=received_amount_ghs)
        except SubscriptionPlan.DoesNotExist:
            print(f"[{reference}] No active subscription plan found with price {received_amount_ghs} GHS.")
            # Depending on business logic, this might be a critical error or just a log
            return False

        if activate_user_subscription(user_instance, matched_plan, received_amount_ghs, reference):
            print(f"[{reference}] User {user_instance.email} subscription for '{matched_plan.name}' successfully processed.")
            return True
        else:
            print(f"[{reference}] Failed to activate subscription for user {user_instance.email}.")
            return False

    except PaymentTransaction.DoesNotExist:
        print(f"[{reference}] PaymentTransaction not found in DB during successful payment processing. This should not happen if called from existing record.")
        return False
    except Exception as e:
        print(f"[{reference}] Unexpected error during successful payment processing: {e}")
        return False

# New function to process failed payments
def process_failed_payment(payment_record: PaymentTransaction, paystack_data: dict) -> bool:
    """
    Handles the business logic for a failed payment.
    Updates the payment record status.
    """
    reference = payment_record.reference
    print(f"[{reference}] Processing failed payment...")

    try:
        # Only update if the payment hasn't already been marked as completed
        if payment_record.status != 'completed':
            payment_record.status = 'failed'
            payment_record.gateway_response = paystack_data.get('gateway_response', paystack_data.get('message', 'Payment failed.'))
            payment_record.save()
            print(f"[{reference}] PaymentTransaction status updated to 'failed'.")
            return True
        else:
            print(f"[{reference}] Received 'charge.failed' but payment was already 'completed'. Ignoring status update.")
            return True # Already completed, no need to change
    except PaymentTransaction.DoesNotExist:
        print(f"[{reference}] PaymentTransaction not found for failed reference.")
        return False
    except Exception as e:
        print(f"[{reference}] Error processing failed payment: {e}")
        return False

from .serializers import InitiatePaymentSerializer

# <-- Import your PaymentTransaction model

class InitiatePaymentAPIView(APIView):
    permission_classes = [IsAuthenticated] # Requires user to be logged in and send a token

    def post(self, request, *args, **kwargs):
        serializer = InitiatePaymentSerializer(data=request.data)

        if not serializer.is_valid():
            # If validation fails, return 400 Bad Request with serializer errors
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Data is valid, proceed
        validated_data = serializer.validated_data
        user = request.user

        customer_name_from_request = validated_data.get('customerName')

        if customer_name_from_request:
            customer_name = customer_name_from_request
        elif user.full_name: # Directly use user.full_name as confirmed by your schema
            customer_name = user.full_name.strip()
        elif user.username:
            customer_name = user.username
        else:
            customer_name = 'Guest'

        user_email = user.email
        if not user_email:
            user_fullname = user.full_name 
            if not user_fullname:
                user_fullname = "user_name"
            user_email = user_fullname + "@gmail.com"


        amount_ghs = validated_data['amount'] # Store original GHS amount
        amount_pesewas = int(amount_ghs * 100) # Paystack expects amount in pesewas
        email = user_email
        phone_number = validated_data['phoneNumber']
        mobile_operator = validated_data['mobileOperator']
        customer_name = customer_name 
        plan_name = validated_data.get('plan_name') # Get plan name if added to serializer

        user = request.user # Authenticated user is available here

        reference = f"TXN_{uuid.uuid4().hex}" # Generate unique reference
        try:
            # This will raise a ValueError if formatting fails
            phone_number_for_paystack = format_ghanaian_phone_number(phone_number)
        except ValueError as e:
            # Return a bad request response with a specific error message for phone number
            return Response(
                {'phoneNumber': [str(e)]},
                status=status.HTTP_400_BAD_REQUEST
            )
         
        # --- STEP 1: Create a pending payment record in your database ---
        if mobile_operator == 'telecel':
            mobile_operator = 'vod'
        try:
            payment_record = PaymentTransaction.objects.create(
                user=user,
                reference=reference,
                amount=amount_ghs,
                paystack_amount_pesewas=amount_pesewas,
                email=email,
                phone_number=phone_number_for_paystack,
                mobile_operator=mobile_operator,
                customer_name=customer_name,
                plan_name=plan_name, 
                status='pending'
            )
            print(f"[{reference}] Payment record created in DB (status: pending).")
        except Exception as e:
            print(f"Error creating payment record for {reference}: {e}")
            return Response(
                {'status': 'error', 'message': 'Failed to create payment record in database.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # --- STEP 2: Initiate payment with Paystack ---
        print("calling the endpoint")
        url = "https://api.paystack.co/charge"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        # The callback_url for mobile money is less critical for *redirecting* the user's browser,
        # as the auth happens on the phone. But Paystack requires it, and it's good practice
        # to point to a success page that users can land on.what is the main difference between the fish in the pond and the fish in
        # Ensure 'payment_success_page' is defined in your urls.py
        callback_url = "https://example.com/success/"

        payload = {
            "email": email,
            "amount": amount_pesewas,  # Amount in pesewas (1 GHS = 100 pesewas)
            "currency": "GHS",
            "reference": reference,
            "mobile_money": {
                "phone": phone_number,
                "provider": mobile_operator  # Must be one of: "mtn", "vodafone", "airtel_tigo"
            },
            "pay_offline": False, 
            "callback_url": callback_url,
            "metadata": {
                "customer_name": customer_name,
                "phone_number": phone_number,
                "mobile_operator": mobile_operator,
                "user_id": user.id,
                "plan_name": plan_name
            }
        }

        try:
            paystack_response = requests.post(url, headers=headers, json=payload)
            paystack_response.raise_for_status()  # Raise error for HTTP 4xx/5xx
            paystack_data = paystack_response.json()
            print("Payment initialized")

            data = paystack_data.get('data', {}) or {}
            api_status = paystack_data.get('status')  # True/False
            api_message = paystack_data.get('message', 'No message from Paystack.')
            charge_status = data.get('status')  # e.g. send_otp, success, pending
            gateway_response = data.get('gateway_response', '')
            next_action = data.get('next_action', '')
            display_text = data.get('display_text') or api_message

            payment_record.paystack_response_message = api_message
            payment_record.paystack_response_status = api_status
            payment_record.gateway_response = gateway_response
            payment_record.user = request.user
            payment_record.save()

            print(f"[{reference}] Paystack response: API status={api_status}, charge_status={charge_status}, next_action={next_action}, gateway_response={gateway_response}")

            if api_status and data:
                if next_action == 'send_otp' or charge_status == 'send_otp' or 'otp' in gateway_response.lower():
                    return Response({
                        'status': 'otp_required',
                        'message': display_text or 'OTP has been sent. Prompt user to enter it.',
                        'data': {
                            'reference': reference
                        }
                    }, status=status.HTTP_200_OK)

                elif charge_status in ['pending', 'success','pay_offline']:
                    return Response({
                        'status': 'success',
                        'message': 'Payment initiated. Await confirmation on phone.',
                        'data': {
                            'reference': reference
                        }
                    }, status=status.HTTP_200_OK)

                else:
                    return Response({
                        'status': 'unknown',
                        'message': f'Unhandled Paystack charge status: {charge_status}',
                        'data': {
                            'reference': reference,
                            'raw_status': charge_status
                        }
                    }, status=status.HTTP_200_OK)

            else:
                # Paystack returned false or bad data
                payment_record.status = 'failed'
                payment_record.gateway_response = api_message
                payment_record.save()
                print(f"[{reference}] Paystack initialization failed: {api_message}")
                return Response({
                    'status': 'error',
                    'message': api_message or 'Failed to initialize payment with Paystack.',
                    'paystack_errors': paystack_data.get('errors')
                }, status=status.HTTP_400_BAD_REQUEST)

        except requests.exceptions.RequestException as e:
            print(f"[{reference}] Error communicating with Paystack API: {e}")
            payment_record.status = 'failed'
            payment_record.paystack_response_message = f"Network/API error with Paystack: {e}"
            payment_record.save()
            return Response({
                'status': 'error',
                'message': 'Could not connect to Paystack service. Please try again later.',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            print(f"[{reference}] Unexpected error during payment initiation: {e}")
            payment_record.status = 'failed'
            payment_record.paystack_response_message = f"Unexpected backend error: {e}"
            payment_record.save()
            return Response({
                'status': 'error',
                'message': 'An unexpected error occurred during payment processing.',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Webhook view remains largely the same, but you could still use APIView if preferred
# @csrf_exempt
# def paystack_webhook(request):
#     ... (previous logic)

# Assuming you have `requests` imported already
import requests # Make sure this is imported

# class VerifyPaystackPaymentAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, *args, **kwargs):
#         reference = request.data.get("reference")

#         if not reference:
#             return Response({'message': 'Reference is required.'}, status=400)

#         try:
#             payment_record = PaymentTransaction.objects.get(reference=reference, user=request.user)
#         except PaymentTransaction.DoesNotExist:
#             return Response({'message': 'Payment record not found.'}, status=404)

#         headers = {
#             "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
#             "Content-Type": "application/json"
#         }

#         verify_url = f"https://api.paystack.co/transaction/verify/{reference}"

#         try:
#             response = requests.get(verify_url, headers=headers)
#             response.raise_for_status()
#             result = response.json()
#         except requests.RequestException:
#             return Response({'message': 'Failed to connect to Paystack.'}, status=503)
#         except ValueError:
#             return Response({'message': 'Invalid response from Paystack.'}, status=502)

#         if result.get("status") is True and "data" in result:
#             data = result["data"]
#             status_from_paystack = data.get("status")

#             if status_from_paystack == "success":
#                 payment_record.status = 'completed'
#                 payment_record.completed_at = timezone.now()
#                 payment_record.paystack_response_status = status_from_paystack
#                 payment_record.gateway_response = data.get('gateway_response')
#                 payment_record.save()
#                 paystack_amount_kobo = data.get('amount')
                
#                 received_amount_ghs = paystack_amount_kobo / 100.0 
                

#                 # user_instance = payment_record.user
#                 try:
#                     # Find the subscription plan based on the received amount
#                     # Consider if multiple plans can have the same price or if you need a specific plan ID
#                     matched_plan = SubscriptionPlan.objects.get(price=received_amount_ghs)
#                 except SubscriptionPlan.DoesNotExist:
#                     return Response({
#                         "payment_status": "success_but_no_plan",
#                         "message": "Payment successful, but no matching subscription plan found for this amount.",
#                         "data": data
#                     }, status=200) # Still 200, as Paystack payment was success, but internal issue
          

#                 return Response({
#                     "message": "Payment verified successfully.",
#                     "status": "success",
#                     "data": data
#                 }, status=200)

#             elif status_from_paystack == "failed":
#                 return Response({
#                     "message": "Payment failed.",
#                     "status": "failed",
#                     "data": data
#                 }, status=400)

#             elif status_from_paystack == "abandoned":
#                 return Response({
#                     "message": "Payment was abandoned.",
#                     "status": "abandoned",
#                     "data": data
#                 }, status=408)

#             else:
#                 return Response({
#                     "message": f"Payment is currently {status_from_paystack}.",
#                     "status": status_from_paystack,
#                     "data": data
#                 }, status=202)

#         else:
#             return Response({
#                 "message": result.get("message", "Verification failed."),
#                 "status": "error",
#                 "data": result
#             }, status=500)


class VerifyPaystackPaymentAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        reference = request.data.get("reference")

        if not reference:
            return Response({'message': 'Reference is required.'}, status=400)

        try:
            # Ensure the payment record belongs to the authenticated user
            payment_record = PaymentTransaction.objects.get(reference=reference, user=request.user)
        except PaymentTransaction.DoesNotExist:
            return Response({'message': 'Payment record not found for this user.'}, status=404)

        # Prevent re-verification of already completed payments if your logic requires it
        if payment_record.status == 'completed':
            return Response({
                'message': 'Payment has already been verified and completed.',
                'status': 'success',
                'data': {'reference': reference, 'status': 'completed'}
            }, status=200)

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        verify_url = f"https://api.paystack.co/transaction/verify/{reference}"

        try:
            response = requests.get(verify_url, headers=headers)
            response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
            result = response.json()
        except requests.exceptions.RequestException as e:
            # More specific error handling for network issues, DNS, etc.
            return Response({'message': f'Failed to connect to Paystack: {e}'}, status=503)
        except ValueError:
            # Handles cases where response.json() fails (e.g., non-JSON response)
            return Response({'message': 'Invalid JSON response from Paystack.'}, status=502)

        # Check if the Paystack API call itself was successful
        if result.get("status") is True and "data" in result:
            data = result["data"]
            status_from_paystack = data.get("status")
            paystack_amount_kobo = data.get('amount')

            # Important: Verify currency and amount match
            # Paystack amount is in kobo/pesewas, convert to GHS for comparison
            received_amount_ghs = paystack_amount_kobo / 100.0

            # Use a database transaction to ensure atomicity
            # If any step fails, all changes are rolled back.
            with transaction.atomic():
                if status_from_paystack == "success"  :
                    # Update the payment record details
                    payment_record.status = 'completed'
                    payment_record.completed_at = timezone.now()
                    payment_record.paystack_response_status = status_from_paystack
                    payment_record.paystack_response_message = result.get('message', '')
                    payment_record.gateway_response = data.get('gateway_response')
                    payment_record.save()

                    # Find the subscription plan
                    # It's safer to store the plan ID or name in your initial PaymentTransaction
                    # if the amount alone isn't unique for plans.
                    # For this example, we'll continue using amount.
                    try:
                        # You might need to adjust this to match the exact plan based on price
                        # For example, if you have plans with the same price but different features,
                        # you might need to pass `plan_id` or `plan_name` in the initial payment request metadata.
                        matched_plan = SubscriptionPlan.objects.get(price=received_amount_ghs)
                    except SubscriptionPlan.DoesNotExist:
                        # Payment was successful but no matching plan found in your system.
                        # This indicates a data discrepancy or an invalid payment amount.
                        # You might want to refund or manually assign a plan.
                        return Response({
                            "message": "Payment successful, but no matching subscription plan found for this amount. Please contact support.",
                            "payment_status": "success_no_plan_match",
                            "data": data
                        }, status=200) # Still 200, as Paystack payment was success.

                    # Upgrade or renew the subscription based on the matched plan
                    activation_successful = activate_user_subscription(
                        user_instance=request.user,
                        subscription_plan=matched_plan,
                        payment_transaction=payment_record
                    )

                    if activation_successful:
                        return Response({
                            "message": "Payment verified and subscription activated/updated successfully.",
                            "status": "success",
                            "data": data
                        }, status=200)
                    else:
                        # Handle cases where subscription activation failed for an internal reason
                        # after successful payment. This is critical.
                        return Response({
                            "message": "Payment successful, but subscription activation failed. Please contact support.",
                            "status": "internal_subscription_error",
                            "data": data
                        }, status=500)

                elif status_from_paystack == "failed":
                    payment_record.status = 'failed'
                    payment_record.paystack_response_status = status_from_paystack
                    payment_record.paystack_response_message = result.get('message', '')
                    payment_record.gateway_response = data.get('gateway_response')
                    payment_record.save()
                    return Response({
                        "message": "Payment failed.",
                        "status": "failed",
                        "data": data
                    }, status=400)

                elif status_from_paystack == "abandoned":
                    payment_record.status = 'abandoned'
                    payment_record.paystack_response_status = status_from_paystack
                    payment_record.paystack_response_message = result.get('message', '')
                    payment_record.gateway_response = data.get('gateway_response')
                    payment_record.save()
                    return Response({
                        "message": "Payment was abandoned.",
                        "status": "abandoned",
                        "data": data
                    }, status=408)

                else:
                    # For other statuses like "pending", "reversed", etc.
                    # Update the record with the latest status from Paystack
                    payment_record.status = status_from_paystack
                    payment_record.paystack_response_status = status_from_paystack
                    payment_record.paystack_response_message = result.get('message', '')
                    payment_record.gateway_response = data.get('gateway_response')
                    payment_record.save()
                    return Response({
                        "message": f"Payment is currently {status_from_paystack}.",
                        "status": status_from_paystack,
                        "data": data
                    }, status=202) # 202 Accepted for processing, not yet final

        else:
            # This block handles cases where Paystack API call itself failed (e.g., invalid reference)
            error_message = result.get("message", "Verification failed due to an unknown Paystack error.")
            return Response({
                "message": error_message,
                "status": "paystack_api_error",
                "data": result
            }, status=500)
# logger = logging.getLogger(__name__)
# class VerifyPaystackPaymentAPIView(APIView):
#     permission_classes = [IsAuthenticated]

#     def post(self, request, *args, **kwargs):
#         reference = request.data.get("reference")

#         if not reference:
#             return Response({'error': 'Missing reference.'}, status=400)

#         try:
#             payment_record = PaymentTransaction.objects.get(reference=reference, user=request.user)
#         except PaymentTransaction.DoesNotExist:
#             return Response({'error': 'Payment record not found.'}, status=404)

#         headers = {
#             "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
#             "Content-Type": "application/json"
#         }

#         verify_url = f"https://api.paystack.co/transaction/verify/{reference}"

#         try:
#             response = requests.get(verify_url, headers=headers)
#             response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
#             result = response.json()
#         except requests.exceptions.RequestException as e:
#             print(f"Paystack API request failed: {e}")
#             return Response({'error': 'Failed to connect to Paystack or Paystack returned an error.', 'details': str(e)}, status=503)
#         except ValueError as e:
#             print(f"Invalid JSON response from Paystack: {e}")
#             return Response({'error': f'Invalid response from Paystack: {e}'}, status=502)

#         if result.get("status") is True and "data" in result:
#             data = result["data"]
#             charge_status = data.get("status")
#             paystack_reference = data.get('reference') # Get Paystack's own reference for logging/storage

#             if charge_status == "success":
#                 # Use a database transaction to ensure atomicity
#                 with transaction.atomic():
#                     # --- Idempotency Check ---
#                     # Check if the payment was already completed to prevent double processing
#                     if payment_record.status == 'completed':
#                         logger.info(f"[{reference}] Payment already completed. Ignoring duplicate processing.")
#                         return Response({
#                             "payment_status": "success",
#                             "message": "Payment was already successful and processed.",
#                             "data": data
#                         }, status=200)

#                     # 2. Verify important details (optional but recommended for security)
#                     paystack_amount_kobo = data.get('amount') # Paystack amount is in kobo/pesewas
#                     if paystack_amount_kobo is None:
#                         logger.error(f"[{reference}] Paystack data missing 'amount'. Cannot verify.")
#                         # It's better to return an error response here if critical data is missing
#                         return Response({'error': 'Paystack response missing amount data.'}, status=500)

#                     # Convert Paystack amount (in kobo/pesewas) to GHS
#                     # Assuming 100 pesewas = 1 GHS (similar to 100 kobo = 1 Naira)
#                     received_amount_ghs = paystack_amount_kobo / 100.0 

#                     # Compare with the amount you stored (which is in GHS)
#                     # Use a small tolerance for floating point comparisons if necessary
#                     if abs(received_amount_ghs - float(payment_record.amount)) > 0.01: # Check for tolerance, e.g., 1 pesewa
#                         logger.warning(f"[{reference}] Amount mismatch! Expected {payment_record.amount} GHS, received {received_amount_ghs} GHS.")
#                         payment_record.status = 'amount_mismatch'
#                         payment_record.gateway_response = f"Amount mismatch: Expected {payment_record.amount}, Received {received_amount_ghs}"
#                         payment_record.paystack_response_status = charge_status # Still record the status from Paystack
#                         payment_record.save()
#                         # Return an error to the client, as the amount didn't match what was expected
#                         return Response({
#                             "payment_status": "failed",
#                             "message": "Amount mismatch. Payment verification failed.",
#                             "expected_amount": payment_record.amount,
#                             "received_amount": received_amount_ghs
#                         }, status=400) # Bad Request or Conflict

#                     # 3. Update the PaymentTransaction status
#                     payment_record.status = 'completed'
#                     payment_record.completed_at = timezone.now()
#                     payment_record.paystack_response_status = charge_status
#                     payment_record.gateway_response = data.get('gateway_response')
#                     payment_record.reference = paystack_reference # Store Paystack's reference again if different from yours
#                     payment_record.save()
#                     logger.info(f"[{reference}] PaymentTransaction status updated to 'completed'.")

#                     # 4. Activate user's subscription
#                     user_instance = payment_record.user 

#                     if not user_instance:
#                         logger.error(f"[{reference}] No user associated with this payment record. This should not happen.")
#                         # This is a critical internal error, log and potentially alert
#                         return Response({'error': 'Internal server error: User not found for payment record.'}, status=500)

#                     try:
#                         # Find the subscription plan based on the received amount
#                         # Consider if multiple plans can have the same price or if you need a specific plan ID
#                         matched_plan = SubscriptionPlan.objects.get(price=received_amount_ghs)
#                     except SubscriptionPlan.DoesNotExist:
#                         logger.error(f"[{reference}] No active subscription plan found with price {received_amount_ghs} GHS.")
#                         # This is a business logic error. The payment was successful but for an unknown plan.
#                         # You might want to refund or manually review this.
#                         return Response({
#                             "payment_status": "success_but_no_plan",
#                             "message": "Payment successful, but no matching subscription plan found for this amount.",
#                             "data": data
#                         }, status=200) # Still 200, as Paystack payment was success, but internal issue

#                     # --- Subscription Activation Logic ---
#                     # Check if the user already has an active subscription of this type
#                     # You might have a UserSubscription model
                    
#                 # If all steps within the transaction are successful
#                 return Response({
#                     "payment_status": "success",
#                     "message": "Payment was successful and subscription activated.",
#                     "data": data
#                 }, status=200)

#             elif charge_status == "failed":
#                 # Update payment record status
#                 payment_record.status = 'failed'
#                 payment_record.gateway_response = data.get('gateway_response')
#                 payment_record.paystack_response_status = charge_status
#                 payment_record.save()
#                 logger.info(f"[{reference}] Payment failed. Status updated for record.")
#                 return Response({
#                     "payment_status": "failed",
#                     "message": "Payment failed. Please try again or contact support.",
#                     "data": data
#                 }, status=400)

#             elif charge_status == "abandoned":
#                 payment_record.status = 'abandoned'
#                 payment_record.gateway_response = data.get('gateway_response')
#                 payment_record.paystack_response_status = charge_status
#                 payment_record.save()
#                 logger.info(f"[{reference}] User abandoned the payment. Status updated for record.")
#                 return Response({
#                     "payment_status": "abandoned",
#                     "message": "User abandoned the payment. Please complete the payment.",
#                     "data": data
#                 }, status=408) # 408 Request Timeout is appropriate for abandoned
#             else:
#                 # Any other status from Paystack (e.g., 'pending', 'reversed', etc.)
#                 payment_record.status = charge_status
#                 payment_record.gateway_response = data.get('gateway_response')
#                 payment_record.paystack_response_status = charge_status
#                 payment_record.save()
#                 logger.info(f"[{reference}] Payment status from Paystack: {charge_status}. Record updated.")
#                 return Response({
#                     "payment_status": charge_status,
#                     "message": f"Payment is currently {charge_status}. Please wait or try again later.",
#                     "data": data
#                 }, status=202) # 202 Accepted for processing

#         else:
#             # Paystack verification failed (e.g., status is False or data is missing)
#             error_message = result.get("message", "Unknown error from Paystack during verification.")
#             logger.error(f"Paystack verification failed for reference {reference}: {error_message}. Full result: {result}")
#             # Update payment record status to reflect verification failure if it's not already
#             if payment_record.status not in ['completed', 'failed', 'abandoned', 'amount_mismatch']:
#                  payment_record.status = 'verification_failed'
#                  payment_record.gateway_response = error_message
#                  payment_record.save()
#             return Response({
#                 "payment_status": "error",
#                 "message": f"Paystack verification failed: {error_message}",
#                 "data": result
#             }, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_paystack_otp(request):
    user = request.user
    otp = request.data.get('otp')
    reference = request.data.get('reference')

    if not otp or not reference:
        return Response(
            {'error': 'OTP and reference are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        payment = PaymentTransaction.objects.get(reference=reference, user=user)
    except PaymentTransaction.DoesNotExist:
        return Response(
            {'error': 'No matching transaction found for this user and reference.'},
            status=status.HTTP_404_NOT_FOUND
        )

    url = "https://api.paystack.co/charge/submit_otp"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "otp": otp,
        "reference": reference
    }

    try:
        paystack_response = requests.post(url, headers=headers, json=payload)
        paystack_response.raise_for_status()
        data = paystack_response.json()

        # Optional: update transaction status
        payment.status = 'otp_submitted'
        payment.paystack_response_message = data.get('message', '')
        payment.save()

        return Response({
            'status': 'success',
            'message': 'OTP submitted successfully.',
            'paystack_response': data
        }, status=status.HTTP_200_OK)

    except requests.exceptions.RequestException as e:
        return Response({
            'status': 'error',
            'message': 'Failed to submit OTP to Paystack.',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
# You could also turn this into an APIView, but for a webhook, direct @csrf_exempt and HttpResponse is common.
# Example if you wanted webhook as APIView:
# @method_decorator(csrf_exempt, name='dispatch')
# class PaystackWebhookAPIView(APIView):
#     permission_classes = [AllowAny]

#     def post(self, request, *args, **kwargs):
#         payload = request.body
#         paystack_signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')

#         if not paystack_signature:
#             print("Webhook: No X-Paystack-Signature header.")
#             return Response({'message': 'No X-Paystack-Signature header'}, status=status.HTTP_400_BAD_REQUEST)

#         # Verify the webhook signature
#         calculated_signature = hmac.new(
#             settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
#             payload,
#             hashlib.sha512
#         ).hexdigest()

#         if not hmac.compare_digest(calculated_signature, paystack_signature):
#             print("Webhook: Invalid X-Paystack-Signature.")
#             return Response({'message': 'Invalid X-Paystack-Signature'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             event = json.loads(payload)
#         except json.JSONDecodeError:
#             print("Webhook: Invalid JSON payload.")
#             return Response({'message': 'Invalid JSON payload'}, status=status.HTTP_400_BAD_REQUEST)

#         event_type = event.get('event')
#         data = event.get('data')
#         reference = data.get('reference')

#         print(f"Webhook Received: Event '{event_type}' for reference '{reference}'.")

#         try:
#             # Retrieve the payment record once
#             payment = PaymentTransaction.objects.get(reference=reference)
#         except PaymentTransaction.DoesNotExist:
#             print(f"[{reference}] Webhook: PaymentTransaction not found in DB. Could be a timing issue or an invalid reference.")
#             return Response({'message': 'Payment record not found'}, status=status.HTTP_404_NOT_FOUND) # Return 404 if record not found

#         if event_type == 'charge.success':
#             # Delegate to the new processing function
#             if process_successful_payment(payment, data):
#                 print(f"[{reference}] Webhook: Successfully processed 'charge.success'.")
#                 return Response(status=status.HTTP_200_OK)
#             else:
#                 print(f"[{reference}] Webhook: Failed to process 'charge.success' internally.")
#                 # You might want to return a 500 here if the internal processing failed critically
#                 # But for webhooks, it's often safer to return 200 OK to prevent Paystack retries
#                 return Response({'message': 'Internal processing failed for success event'}, status=status.HTTP_200_OK)

#         elif event_type == 'charge.failed':
#             # Delegate to the new processing function
#             if process_failed_payment(payment, data):
#                 print(f"[{reference}] Webhook: Successfully processed 'charge.failed'.")
#                 return Response(status=status.HTTP_200_OK)
#             else:
#                 print(f"[{reference}] Webhook: Failed to process 'charge.failed' internally.")
#                 return Response({'message': 'Internal processing failed for failed event'}, status=status.HTTP_200_OK)

#         elif event_type == 'charge.abandoned':
#             # You might just log or update status here if needed,
#             # but usually the client-side polling handles showing abandoned status
#             print(f"[{reference}] Webhook: Received 'charge.abandoned' event. No further action taken.")
#             return Response(status=status.HTTP_200_OK)

#         else:
#             print(f"[{reference}] Webhook: Unhandled event type: {event_type}")
#             return Response({'message': 'Event type not handled'}, status=status.HTTP_200_OK) # Always return 200 for unhandled events

# A simple placeholder view for the redirect URL
from django.shortcuts import render

def payment_success_page(request):
    reference = request.GET.get('trxref') or request.GET.get('reference')
    context = {
        'reference': reference,
        'message': 'Your payment is being processed. Please check your transaction status.'
    }
    # You would typically have a dedicated HTML template for this page
    return render(request, 'payments/success.html', context)
    # Or, if it's purely an API-driven application without traditional templates:
    # return Response({'status': 'success', 'message': f'Payment for reference {reference} might be successful. Please check transaction status via webhook.'})

class AppVersionCheckAPIView(APIView):
    """
    API endpoint to provide the latest app version and APK download URL.
    This endpoint does NOT require authentication.
    """
    permission_classes = [AllowAny] # Allow anyone to access this endpoint (no login required)

    def get(self, request, *args, **kwargs):
        # --- IMPORTANT: Configure these values ---
        # 1. LATEST_APP_VERSION:
        #    This should be the version number of the *newest* APK you want users to download.
        #    You MUST update this string in your backend code whenever you release a new APK.
        LATEST_APP_VERSION = "1.0.0" # Example: If your current app is 1.0.0, and this is the new version

        # 2. APK_DOWNLOAD_URL:
        #    This is the direct URL where your APK file is hosted.
        #    This URL MUST be updated whenever you release a new APK with a new version number.
        #    Replace 'https://your-server.com/downloads/tilnet_v1.0.1.apk' with your actual hosting URL.
        #    Examples:
        #    - A link to your own server: "https://yourdomain.com/downloads/tilnet_v1.0.1.apk"
        #    - A link to a cloud storage bucket: "https://s3.amazonaws.com/your-bucket/tilnet_v1.0.1.apk"
        #    - A link to a public GitHub release: "https://github.com/your-repo/releases/download/v1.0.1/tilnet_v1.0.1.apk"
        APK_DOWNLOAD_URL = "https://your-server.com/downloads/tilnet_v1.0.1.apk" 

        # You might also want to include instructions or release notes
        RELEASE_NOTES = "New features: Improved 3D viewer, faster calculations, bug fixes."

        return Response({
            'latest_version': LATEST_APP_VERSION,
            'apk_download_url': APK_DOWNLOAD_URL,
            'release_notes': RELEASE_NOTES,
            'message': 'Latest app version information.'
        }, status=status.HTTP_200_OK)
    
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_payment_status(request, reference):
    """
    API endpoint to check the status of a payment transaction.
    """
    try:
        payment = PaymentTransaction.objects.get(reference=reference, user=request.user)
        # Return relevant details, especially the status
        return Response({
            'status': payment.status,
            'reference': payment.reference,
            'amount': str(payment.amount), # Convert Decimal to string
            'plan_name': payment.plan_name,
            'mobile_operator': payment.mobile_operator,
            'completed_at': payment.completed_at.isoformat() if payment.completed_at else None,
            # Add other fields you might need on the frontend
        }, status=status.HTTP_200_OK)
    except PaymentTransaction.DoesNotExist:
        return Response({'message': 'Transaction not found or not associated with user.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        print(f"Error checking payment status: {e}")
        return Response({'message': 'An error occurred while checking status.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Initialize Africa's Talking
africastalking.initialize(settings.AFRICASTALKING_USERNAME, settings.AFRICASTALKING_API_KEY)
sms = africastalking.SMS

class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = PhoneNumberSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']

            # Check if a user with this phone number exists (for password reset flow)
            # If this is for new user registration, you might remove this check
            if not User.objects.filter(phone_number=phone_number).exists():
                return Response(
                    {'message': 'No user found with this phone number.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Invalidate any existing unverified OTP for this phone number
            OTP.objects.filter(phone_number=phone_number).delete()

            # Generate a new OTP
            otp_instance = OTP.objects.create(phone_number=phone_number)
            otp_code = otp_instance.code

            message = f"Your verification code is: {otp_code}. It is valid for 5 minutes."
            print(message)
            try:
                # Send SMS via Africa's Talking
                # Ensure the phone number format is correct for AT (+CountryCodeNumber)
                response = sms.send(message, [phone_number])
                print(f"Africa's Talking SMS response: {response}") # For debugging

                # Check AT response for success
                if response['SMSMessageData']['Recipients'][0]['status'] == 'Success':
                    return Response(
                        {'message': 'OTP sent successfully.'},
                        status=status.HTTP_200_OK
                    )
                else:
                    # Log the failure for debugging
                    print(f"Africa's Talking SMS sending failed: {response['SMSMessageData']['Recipients'][0]['status']}")
                    return Response(
                        {'message': 'Failed to send OTP via SMS. Please try again.'},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            except Exception as e:
                print(f"Error sending SMS: {e}")
                return Response(
                    {'message': 'An error occurred while trying to send SMS.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyOTPAndSetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = VerifyOTPAndSetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            otp_code = serializer.validated_data['otp']
            new_password = serializer.validated_data['new_password']

            try:
                # Get the latest unverified OTP for this phone number
                otp_instance = OTP.objects.filter(
                    phone_number=phone_number,
                    is_verified=False,
                    expires_at__gt=timezone.now() # Ensure it's not expired
                ).latest('created_at') # Get the most recent one

                if otp_instance.code == otp_code:
                    otp_instance.is_verified = True
                    otp_instance.save()

                    # Find the user and update their password
                    try:
                        user = User.objects.get(phone_number=phone_number)
                        user.set_password(new_password)
                        user.save()
                        return Response(
                            {'message': 'Password reset successfully.'},
                            status=status.HTTP_200_OK
                        )
                    except User.DoesNotExist:
                        # This should ideally not happen if validate_phone_number is strict
                        return Response(
                            {'message': 'User not found.'},
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
                print(f"Error during OTP verification or password reset: {e}")
                return Response(
                    {'message': 'An error occurred during password reset.'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """View for listing subscription plans"""
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated]

class UserSubscriptionViewSet(viewsets.ModelViewSet):
    """View for managing user subscriptions"""
    serializer_class = UserSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserSubscription.objects.filter(user=self.request.user).order_by('-start_date')
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get the user's active subscription if any"""
        subscription = UserSubscription.objects.filter(
            user=request.user,
            is_active=True,
            end_date__gt=timezone.now()
        ).order_by('-start_date').first()
        
        if subscription:
            serializer = self.get_serializer(subscription)
            return Response(serializer.data)
        else:
            return Response(
                {"detail": "No active subscription found."},
                status=status.HTTP_404_NOT_FOUND
            )
        

class PaymentViewSet(viewsets.ModelViewSet):
    """View for managing payment transactions"""
    serializer_class = PaymentTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentTransaction.objects.filter(user=self.request.user).order_by('-created_at')

    @action(detail=False, methods=['post'])
    def initiate(self, request):
        """
        Initiate payment for a subscription plan using Paystack's standard initialization.
        This typically leads to a redirect to Paystack's hosted payment page.
        """
        serializer = InitiatePaymentSerializer(data=request.data)
        if serializer.is_valid():
            plan_id = serializer.validated_data['plan_id']
            email = serializer.validated_data['email']
            # Use a specific callback URL for standard web payments if needed,
            # or let Paystack use the default webhook URL configured in your dashboard.
            # For this example, we'll use a generic verify endpoint.
            callback_url = serializer.validated_data.get('callback_url', f"{settings.FRONTEND_URL}/payment/verify")

            # Get the plan
            try:
                plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            except SubscriptionPlan.DoesNotExist:
                return Response(
                    {"detail": "Subscription plan not found or inactive."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Prepare data for Paystack initialization
            amount_kobo = int(plan.price * 100)  # Convert to kobo (smallest currency unit)
            metadata = {
                "plan_id": plan.id,
                "user_id": request.user.id,
                "plan_name": plan.name,
                "custom_fields": [
                    {
                        "display_name": "Subscription Plan",
                        "variable_name": "plan_name",
                        "value": plan.name
                    }
                ]
            }

            # Create Paystack payment initialization request
            url = "https://api.paystack.co/transaction/initialize"
            headers = {
                "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "email": email,
                "amount": amount_kobo,
                "metadata": json.dumps(metadata),
                "callback_url": callback_url, # This is where Paystack redirects the user after payment
                "reference": f"sub_{request.user.id}_{plan.id}_{int(timezone.now().timestamp())}"
            }

            try:
                response = requests.post(url, headers=headers, data=json.dumps(payload))
                response_data = response.json()

                if response.status_code == 200 and response_data.get('status'):
                    # Return the authorization_url to the frontend for redirection
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    print(f"Paystack Initialization Error: {response_data}")
                    return Response(
                        {"detail": "Payment initialization failed", "paystack_response": response_data},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except requests.exceptions.RequestException as e:
                 print(f"Request Exception during Paystack Initialization: {e}")
                 return Response(
                     {"detail": f"Network error during payment initialization: {e}"},
                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
                 )
            except Exception as e:
                print(f"Unexpected error during Paystack Initialization: {e}")
                return Response(
                    {"detail": f"An unexpected error occurred: {e}"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def initiate_mobile_money(self, request):
        """
        Initiate a direct mobile money charge using Paystack's Charge API.
        This should trigger a PIN prompt on the user's phone.
        Requires mobile_number and network in the request data.
        """
        # Assuming you have a serializer for this, like InitiateMobileMoneySerializer
        # For demonstration, let's use a simple check for required fields
        required_fields = ['plan_id', 'email', 'mobile_number', 'network']
        if not all(field in request.data for field in required_fields):
             return Response(
                 {"detail": f"Missing required fields: {', '.join(required_fields)}"},
                 status=status.HTTP_400_BAD_REQUEST
             )

        plan_id = request.data.get('plan_id')
        email = request.data.get('email')
        mobile_number = request.data.get('mobile_number')
        network = request.data.get('network').upper() # Ensure uppercase for network

        # Get the plan
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response(
                {"detail": "Subscription plan not found or inactive."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Map network to Paystack bank code for mobile money (Ghana)
        # These codes are crucial and might change. Always refer to Paystack docs.
        network_bank_codes = {
            'MTN': 'MTN', # Paystack uses network code directly for MTN Ghana
            'VODAFONE': 'VOD',
            'AIRTELTIGO': 'ATL', # Or 'TGO' depending on specific integration details/updates
            # Note: Double-check these codes with the latest Paystack documentation for Ghana Mobile Money
        }
        bank_code = network_bank_codes.get(network)

        if not bank_code:
            return Response(
                {"detail": f"Unsupported mobile money network: {network}. Supported networks: {', '.join(network_bank_codes.keys())}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Prepare data for Paystack Charge API
        amount_kobo = int(plan.price * 100)  # Convert to kobo
        reference = f"sub_momo_{request.user.id}_{plan.id}_{int(timezone.now().timestamp())}"

        # Metadata for tracking
        metadata = {
            "plan_id": plan.id,
            "user_id": request.user.id,
            "plan_name": plan.name,
            "mobile_number": mobile_number, # Include mobile number in metadata for verification
            "network": network, # Include network in metadata
        }

        # Paystack Charge API endpoint for mobile money
        url = "https://api.paystack.co/charge"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        # Payload for Mobile Money Charge
        payload = {
            "email": email,
            "amount": amount_kobo,
            "reference": reference,
            "metadata": json.dumps(metadata),
            "mobile_money": {
                "phone": mobile_number,
                "provider": bank_code, # Use the mapped bank code
            },
            # For direct charge, callback_url is often not used for user redirection,
            # but ensure you have a webhook configured in your Paystack dashboard
            # to receive asynchronous payment status updates.
            # If you need a client-side callback after the prompt is sent,
            # you might use a different parameter or handle it frontend-side.
            # The recommended approach for final status is webhooks.
        }

        try:
            print(f"Initiating Paystack Mobile Money Charge with payload: {payload}")
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            response_data = response.json()
            print(f"Paystack Charge API Response: {response_data}")

            # Check the response status and message
            if response.status_code == 200 and response_data.get('status'):
                # Paystack has successfully initiated the charge and likely sent the PIN prompt
                # The status might be 'send_otp' or similar initially,
                # the final status will be confirmed via webhook.
                # You can return a success response to the frontend indicating the prompt was sent.
                return Response(
                    {"detail": "Mobile Money charge initiated. Please check your phone for a PIN prompt.", "paystack_response": response_data},
                    status=status.HTTP_200_OK
                )
            else:
                # Handle cases where Paystack returns an error (e.g., invalid number, network issues)
                error_message = response_data.get('message', 'Payment initiation failed')
                print(f"Paystack Mobile Money Charge Error: {response_data}")
                return Response(
                    {"detail": f"Mobile Money charge failed: {error_message}", "paystack_response": response_data},
                    status=status.HTTP_400_BAD_REQUEST # Or 500 depending on the error nature
                )

        except requests.exceptions.RequestException as e:
             print(f"Request Exception during Paystack Mobile Money Charge: {e}")
             return Response(
                 {"detail": f"Network error during mobile money initiation: {e}"},
                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
             )
        except Exception as e:
            print(f"Unexpected error during Paystack Mobile Money Charge: {e}")
            return Response(
                {"detail": f"An unexpected error occurred: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify payment with Paystack using the transaction reference.
        This endpoint is typically called by your frontend after a redirect
        from Paystack's hosted page (for standard initialization) or could be
        used manually for polling (though webhooks are preferred for final status).
        """
        reference = request.data.get('reference')
        if not reference:
            return Response(
                {"detail": "Reference is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify payment with Paystack
        url = f"https://api.paystack.co/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data.get('status'):
                transaction_data = response_data.get('data', {})
                metadata = transaction_data.get('metadata', {})

                # Paystack might return metadata as a string, try to parse it
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        print("Warning: Could not parse metadata string as JSON.")
                        metadata = {} # Default to empty dict if parsing fails

                plan_id = metadata.get('plan_id')
                user_id = metadata.get('user_id')

                # Validate user (important security check)
                if str(user_id) != str(request.user.id):
                    print(f"Security Alert: User ID mismatch during verification. Request user: {request.user.id}, Metadata user: {user_id}, Reference: {reference}")
                    return Response(
                        {"detail": "User mismatch in payment verification."},
                        status=status.HTTP_400_BAD_REQUEST # Or 403 Forbidden
                    )

                # Check if a transaction with this reference already exists to prevent double processing
                if PaymentTransaction.objects.filter(reference=reference).exists():
                     print(f"Warning: Transaction with reference {reference} already exists. Skipping creation.")
                     # You might want to return the existing transaction details
                     existing_transaction = PaymentTransaction.objects.get(reference=reference)
                     return Response(
                         {"detail": "Transaction already processed.", "transaction": PaymentTransactionSerializer(existing_transaction).data},
                         status=status.HTTP_200_OK # Indicate success as it was already handled
                     )

                # Get the plan
                try:
                    plan = SubscriptionPlan.objects.get(id=plan_id)
                except SubscriptionPlan.DoesNotExist:
                    print(f"Error: Subscription plan with ID {plan_id} not found during verification.")
                    return Response(
                        {"detail": "Subscription plan not found."},
                        status=status.HTTP_404_NOT_FOUND
                    )

                # Check if the payment was successful based on Paystack's status
                paystack_transaction_status = transaction_data.get('status')
                if paystack_transaction_status != 'success':
                     print(f"Payment not successful according to Paystack. Status: {paystack_transaction_status}, Reference: {reference}")
                     return Response(
                         {"detail": f"Payment was not successful. Status: {paystack_transaction_status}", "paystack_response": response_data},
                         status=status.HTTP_400_BAD_REQUEST # Indicate payment failure
                     )


                # Record payment transaction
                transaction = PaymentTransaction.objects.create(
                    user=request.user,
                    amount=Decimal(str(transaction_data.get('amount', 0))) / 100,  # Convert from kobo to GHS, use Decimal
                    currency=transaction_data.get('currency', 'GHS'),
                    provider='paystack',
                    transaction_id=transaction_data.get('id'), # Paystack's internal transaction ID
                    status=paystack_transaction_status, # Use the verified status
                    reference=reference,
                    metadata=transaction_data # Store full Paystack response for debugging/auditing
                )
                print(f"PaymentTransaction recorded with ID: {transaction.id}, Status: {transaction.status}")


                # Create or update subscription ONLY if payment was successful
                start_date = timezone.now()
                end_date = start_date + timezone.timedelta(days=plan.duration_days)

                # Check for existing active subscription
                existing_subscription = UserSubscription.objects.filter(
                    user=request.user,
                    is_active=True,
                    end_date__gt=timezone.now()
                ).first()

                if existing_subscription:
                    # Extend existing subscription
                    print(f"Extending existing subscription {existing_subscription.id}")
                    existing_subscription.end_date = existing_subscription.end_date + timezone.timedelta(days=plan.duration_days)
                    # Add the new payment amount to the total amount paid
                    existing_subscription.amount_paid = (existing_subscription.amount_paid or Decimal('0.00')) + Decimal(str(transaction.amount))
                    existing_subscription.payment_status = 'paid' # Assuming 'paid' is your internal status
                    existing_subscription.payment_id = reference # Update with the latest reference
                    existing_subscription.save()
                    subscription = existing_subscription
                    print("Existing subscription extended.")
                else:
                    # Create new subscription
                    print("Creating new subscription")
                    subscription = UserSubscription.objects.create(
                        user=request.user,
                        plan=plan,
                        start_date=start_date,
                        end_date=end_date,
                        is_active=True,
                        payment_id=reference,
                        payment_status='paid', # Assuming 'paid' is your internal status
                        amount_paid=Decimal(str(transaction.amount)), # Use the amount from the transaction
                        projects_used=0, # Reset or handle based on your logic
                        room_views_used=0 # Reset or handle based on your logic
                    )
                    print(f"New subscription created with ID: {subscription.id}")

                # Link transaction to subscription
                transaction.subscription = subscription
                transaction.save()
                print(f"Transaction {transaction.id} linked to subscription {subscription.id}")


                return Response({
                    "detail": "Payment verified and subscription activated.",
                    "subscription": UserSubscriptionSerializer(subscription).data,
                    "transaction": PaymentTransactionSerializer(transaction).data
                }, status=status.HTTP_200_OK)

            else:
                # Paystack verification failed (e.g., invalid reference, transaction not found)
                error_message = response_data.get('message', 'Payment verification failed')
                print(f"Paystack Verification Failed: {response_data}")
                return Response(
                    {"detail": f"Payment verification failed: {error_message}", "paystack_response": response_data},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except requests.exceptions.RequestException as e:
             print(f"Request Exception during Paystack Verification: {e}")
             return Response(
                 {"detail": f"Network error during payment verification: {e}"},
                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
             )
        except Exception as e:
            print(f"Unexpected error during Paystack Verification: {e}")
            traceback.print_exc() # Print traceback for unexpected errors
            return Response(
                {"detail": f"An unexpected error occurred during verification: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# class PaymentViewSet(viewsets.ModelViewSet):
#     """View for managing payment transactions"""
#     serializer_class = PaymentTransactionSerializer
#     permission_classes = [IsAuthenticated]
    
#     def get_queryset(self):
#         return PaymentTransaction.objects.filter(user=self.request.user).order_by('-created_at')
    
#     @action(detail=False, methods=['post'])
#     def initiate(self, request):
#         """Initiate payment for a subscription plan using Paystack"""
#         serializer = InitiatePaymentSerializer(data=request.data)
#         if serializer.is_valid():
#             plan_id = serializer.validated_data['plan_id']
#             email = serializer.validated_data['email']
#             callback_url = serializer.validated_data.get('callback_url', f"{settings.FRONTEND_URL}/payment/verify")
            
#             # Get the plan
#             try:
#                 plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
#             except SubscriptionPlan.DoesNotExist:
#                 return Response(
#                     {"detail": "Subscription plan not found or inactive."},
#                     status=status.HTTP_404_NOT_FOUND
#                 )
            
#             # Prepare data for Paystack
#             amount_kobo = int(plan.price * 100)  # Convert to kobo (smallest currency unit)
#             metadata = {
#                 "plan_id": plan.id,
#                 "user_id": request.user.id,
#                 "plan_name": plan.name,
#                 "custom_fields": [
#                     {
#                         "display_name": "Subscription Plan",
#                         "variable_name": "plan_name",
#                         "value": plan.name
#                     }
#                 ]
#             }
            
#             # Create Paystack payment request
#             url = "https://api.paystack.co/transaction/initialize"
#             headers = {
#                 "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
#                 "Content-Type": "application/json"
#             }
#             payload = {
#                 "email": email,
#                 "amount": amount_kobo,
#                 "metadata": json.dumps(metadata),
#                 "callback_url": callback_url,
#                 "reference": f"sub_{request.user.id}_{plan.id}_{int(timezone.now().timestamp())}"
#             }
            
#             try:
#                 response = requests.post(url, headers=headers, data=json.dumps(payload))
#                 response_data = response.json()
                
#                 if response.status_code == 200 and response_data.get('status'):
#                     return Response(response_data, status=status.HTTP_200_OK)
#                 else:
#                     return Response(
#                         {"detail": "Payment initialization failed", "paystack_response": response_data},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
#             except Exception as e:
#                 return Response(
#                     {"detail": str(e)},
#                     status=status.HTTP_500_INTERNAL_SERVER_ERROR
#                 )
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
#     @action(detail=False, methods=['post'])
#     def verify(self, request):
#         """Verify payment and activate subscription"""
#         reference = request.data.get('reference')
#         if not reference:
#             return Response(
#                 {"detail": "Reference is required."},
#                 status=status.HTTP_400_BAD_REQUEST
#             )
        
#         # Verify payment with Paystack
#         url = f"https://api.paystack.co/transaction/verify/{reference}"
#         headers = {
#             "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
#             "Content-Type": "application/json"
#         }
        
#         try:
#             response = requests.get(url, headers=headers)
#             response_data = response.json()
            
#             if response.status_code == 200 and response_data.get('status'):
#                 transaction_data = response_data.get('data', {})
#                 metadata = transaction_data.get('metadata', {})
                
#                 if isinstance(metadata, str):
#                     try:
#                         metadata = json.loads(metadata)
#                     except:
#                         metadata = {}
                
#                 plan_id = metadata.get('plan_id')
#                 user_id = metadata.get('user_id')
                
#                 # Validate user
#                 if str(user_id) != str(request.user.id):
#                     return Response(
#                         {"detail": "User mismatch in payment verification."},
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
                
#                 # Get the plan
#                 try:
#                     plan = SubscriptionPlan.objects.get(id=plan_id)
#                 except SubscriptionPlan.DoesNotExist:
#                     return Response(
#                         {"detail": "Subscription plan not found."},
#                         status=status.HTTP_404_NOT_FOUND
#                     )
                
#                 # Record payment transaction
#                 transaction = PaymentTransaction.objects.create(
#                     user=request.user,
#                     amount=transaction_data.get('amount', 0) / 100,  # Convert from kobo to GHS
#                     currency=transaction_data.get('currency', 'GHS'),
#                     provider='paystack',
#                     transaction_id=transaction_data.get('id'),
#                     status=transaction_data.get('status'),
#                     reference=reference,
#                     metadata=transaction_data
#                 )
                
#                 # Create or update subscription
#                 start_date = timezone.now()
#                 end_date = start_date + timezone.timedelta(days=plan.duration_days)
                
#                 # Check for existing active subscription
#                 existing_subscription = UserSubscription.objects.filter(
#                     user=request.user,
#                     is_active=True,
#                     end_date__gt=timezone.now()
#                 ).first()
                
#                 if existing_subscription:
#                     # Extend existing subscription
#                     existing_subscription.end_date = existing_subscription.end_date + timezone.timedelta(days=plan.duration_days)
#                     existing_subscription.amount_paid = existing_subscription.amount_paid + plan.price
#                     existing_subscription.payment_status = 'paid'
#                     existing_subscription.payment_id = reference
#                     existing_subscription.save()
#                     subscription = existing_subscription
#                 else:
#                     # Create new subscription
#                     subscription = UserSubscription.objects.create(
#                         user=request.user,
#                         plan=plan,
#                         start_date=start_date,
#                         end_date=end_date,
#                         is_active=True,
#                         payment_id=reference,
#                         payment_status='paid',
#                         amount_paid=plan.price,
#                         projects_used=0,
#                         room_views_used=0
#                     )
                
#                 # Link transaction to subscription
#                 transaction.subscription = subscription
#                 transaction.save()
                
#                 return Response({
#                     "detail": "Payment verified and subscription activated.",
#                     "subscription": UserSubscriptionSerializer(subscription).data,
#                     "transaction": PaymentTransactionSerializer(transaction).data
#                 })
#             else:
#                 return Response(
#                     {"detail": "Payment verification failed", "paystack_response": response_data},
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#         except Exception as e:
#             return Response(
#                 {"detail": str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
