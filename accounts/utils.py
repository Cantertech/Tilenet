
import random
import string
import requests
import json
from django.conf import settings

def send_sms_africastalking(to, message, sender_id=None):
    """
    Sends an SMS message using the Africa's Talking API.

    Args:
        to (str or list): The recipient phone number(s) in international format (e.g., +23324XXXXXXX).
                         Can be a single string or a list of strings.
        message (str): The body of the SMS message.
        sender_id (str, optional): The sender ID to use. Defaults to AFRICASTALKING_SENDER_ID from settings.

    Returns:
        dict: The JSON response from the Africa's Talking API if the request was successful (status code 201).
        dict: The JSON error response from the Africa's Talking API if the request failed.
        None: If there was an exception making the request or a configuration error.
    """
    # Check if API key and username are configured
    if not settings.AFRICASTALKING_API_KEY or not settings.AFRICASTALKING_USERNAME:
        print("Africa's Talking API key or username not configured in settings.")
        return None

    # Africa's Talking SMS API endpoint
    url = "https://api.africastalking.com/version1/messaging"

    # Ensure 'to' is a comma-separated string of recipients
    if isinstance(to, str):
        recipients_string = to
    elif isinstance(to, list):
        recipients_string = ','.join(to)
    else:
        print("Invalid 'to' argument. Must be a string or a list of strings.")
        return None

    payload = {
        'username': settings.AFRICASTALKING_USERNAME,
        'to': recipients_string,
        'message': message,
    }

    # Add senderId if explicitly provided or configured in settings
    if sender_id is not None:
        payload['from'] = sender_id
    elif settings.AFRICASTALKING_SENDER_ID:
         payload['from'] = settings.AFRICASTALKING_SENDER_ID


    headers = {
        'apiKey': settings.AFRICASTALKING_API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded', # Required Content-Type for this endpoint
        'Accept': 'application/json',
    }

    try:
        # Use data=payload for x-www-form-urlencoded
        response = requests.post(url, data=payload, headers=headers)
        response_data = response.json()

        # Africa's Talking returns 201 on successful submission
        if response.status_code == 201:
            print(f"SMS successfully submitted to Africa's Talking for recipients: {recipients_string}. Response: {response_data}")
            return response_data
        else:
            # Handle API-specific errors returned by Africa's Talking
            print(f"Failed to submit SMS to Africa's Talking for recipients: {recipients_string}. Status Code: {response.status_code}, Response: {response_data}")
            return response_data # Return the error response from the API

    except requests.exceptions.RequestException as e:
        # Handle network errors or other request issues
        print(f"Error making request to Africa's Talking API: {e}")
        return None
    except json.JSONDecodeError:
        # Handle cases where the response is not valid JSON
        print("Error decoding JSON response from Africa's Talking API.")
        # print(f"Raw response: {response.text}") # Uncomment for debugging raw response
        return None
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred in send_sms_africastalking: {e}")
        return None
    
def generate_verification_code(length=6):
    return ''.join(random.choices(string.digits, k=length))