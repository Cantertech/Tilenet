# payments/utils.py (or at the top of your views.py)
import re

def format_ghanaian_phone_number(phone_number_str):
    """
    Formats a Ghanaian phone number to the international E.164 format (without '+'),
    suitable for Paystack.
    e.g., '0241234567' -> '233241234567'
          '+233 241 234 567' -> '233241234567'

    Raises ValueError if the number is not a valid Ghanaian mobile format.
    """
    if not phone_number_str:
        raise ValueError("Phone number cannot be empty.")

    # 1. Remove all non-digit characters (spaces, hyphens, plus signs etc.)
    digits_only = re.sub(r'\D', '', phone_number_str)

    formatted_number = ''

    # 2. Handle known Ghanaian prefixes and formats
    if digits_only.startswith('233'):
        # Already in international format or starts with it
        formatted_number = digits_only
    elif digits_only.startswith('0'):
        # Local Ghanaian number, replace '0' with '233'
        formatted_number = '233' + digits_only[1:]
    else:
        # If it doesn't start with '0' or '233', it's an invalid format for Ghana
        raise ValueError(
            f"Invalid Ghanaian phone number format: '{phone_number_str}'. "
            "Must start with '0' (local) or '+233'/'233' (international)."
        )

    # 3. Final length validation
    # A Ghanaian mobile number (after '233') has 9 digits, so total 12 digits.
    if len(formatted_number) != 12:
        raise ValueError(
            f"Invalid Ghanaian phone number length: '{phone_number_str}'. "
            f"Expected 12 digits after conversion (e.g., 233xxxxxxxx)."
        )

    # Optional: More specific mobile network prefix validation (e.g., MTN, Vodafone, AirtelTigo)
    # This is more robust but also more brittle if prefixes change.
    # The 9-digit part of the number
    # gh_mobile_prefixes = ['20', '24', '26', '27', '50', '54', '55', '56', '57', '59']
    # if not formatted_number[3:5] in gh_mobile_prefixes:
    #     raise ValueError(f"Invalid Ghanaian mobile network prefix: {formatted_number[3:5]}.")

    return formatted_number