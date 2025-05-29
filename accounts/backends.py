
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import CustomUser

class CustomAuthBackend(ModelBackend):
    """
    Authenticates against settings.AUTH_USER_MODEL using either username, email, or phone number.
    """
    
    def authenticate(self, request, username=None, password=None, email=None, phone_number=None, **kwargs):
        # Try to fetch the user based on the provided credentials
        try:
            # Build a query to find the user by either username, email, or phone number
            query = Q()
            if username:
                query |= Q(username=username)
            if email:
                query |= Q(email=email)
            if phone_number:
                query |= Q(phone_number=phone_number)
                
            # If no valid login credential was provided, return None
            if not query:
                return None
                
            user = CustomUser.objects.get(query)
            
            # Check the password
            if user.check_password(password):
                return user
                
        except CustomUser.DoesNotExist:
            return None
