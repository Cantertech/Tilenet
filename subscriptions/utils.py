# payments/utils.py (or at the top of your views.py)
import re

def format_phone_for_paystack_local(phone_number_str):
    """
    Format phone to local Ghanaian number with leading 0, as Paystack expects for mobile_money.phone
    e.g., '+233551234987' or '233551234987' -> '0551234987'
          '0551234987' -> '0551234987' (unchanged)
    """
    import re
    if not phone_number_str:
        raise ValueError("Phone number cannot be empty.")
    digits_only = re.sub(r'\D', '', phone_number_str.strip())
    if digits_only.startswith('233'):
        # Remove '233' and add '0'
        digits_only = '0' + digits_only[3:]
    elif digits_only.startswith('0'):
        pass  # already local format
    else:
        raise ValueError("Invalid phone format for Ghanaian number.")
    
    if len(digits_only) != 10:
        raise ValueError("Phone number length invalid. Expect 10 digits local number starting with 0.")
    
    return digits_only
