
# your_project/estimates/views.py
import traceback
import io
import os
# Using Decimal for calculations to avoid floating point issues
from decimal import Decimal
from django.db.models import Sum # Only needed if doing sums in view, not serializer
from django.http import HttpResponse # To return the PDF as a response (if not Base64)
from django.template.loader import render_to_string # To render the HTML template
from django.conf import settings # To access template settings
from weasyprint import HTML # Import WeasyPrint
import base64 # For Base64 encoding/decoding
from django.shortcuts import get_object_or_404 # Helper function
from django.contrib.auth import get_user_model # To get the user model
import traceback
# --- Import DRF Modules ---
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from accounts.models import use_feature_if_allowed

# --- Import Your Models ---
from .models import Estimate, Customer, MaterialItem, RoomArea
from .services import create_estimate_and_nested_items

# --- Import Your Serializers ---
# Ensure you import all the necessary serializers, including the nested ones
from .serializers import (
    EstimateSerializer,
    CustomerSerializer,
  # Needed if you use the nested item views
   
)

# --- Import Reusable PDF Function ---
# Make sure this file exists and contains the generate_estimate_pdf_base64 function
from .utils import generate_estimate_pdf_base64 # Assuming you put it in estimates/utils.py


# --- Get the active user model (your CustomUser) ---
User = get_user_model()


# --- Custom permission to only allow owners of an object to edit it. ---
class IsOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to access/edit it.
    Assumes the object instance has a 'user' attribute linked to the User model.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions (GET, HEAD, OPTIONS) are allowed to any authenticated user
        # because the queryset is already filtered by the owner.
        # The IsOwner permission is primarily for object-level write checks (PUT, PATCH, DELETE).
        if request.method in permissions.SAFE_METHODS:
            # Even for safe methods, we'll add an extra check that the object belongs
            # to the user, though get_queryset should handle this. It's good practice.
             return obj.user == request.user


        # Write permissions are only allowed to the owner of the object.
        return obj.user == request.user


# --- Estimate (Project) Views ---

class EstimateListCreateView(generics.ListCreateAPIView):
    """
    API endpoint that allows Estimates (Projects) to be viewed (GET) or created (POST)
    by the authenticated user.
    GET: Lists all Estimates for the authenticated user with full details.
    POST: Creates a new Estimate, including nested items, generates a PDF,
          and returns the created Estimate data along with the Base64 PDF string.
    Requires the user to be authenticated.
    """
    queryset = Estimate.objects.all() # Base queryset
    serializer_class = EstimateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Override get_queryset to filter Estimates to only include those
        belonging to the authenticated user (`request.user`).
        Use select_related/prefetch_related to optimize fetching related data
        for the serializer to avoid N+1 queries when listing.
        """
        user = self.request.user
        # Ensure 'labour' is prefetch_related for the new model setup
        return Estimate.objects.filter(user=user).select_related('customer').prefetch_related('rooms', 'materials').order_by('-estimate_date')


    def create(self, request, *args, **kwargs):
        """
        Handles POST requests to create an Estimate (Project), save nested items,
        and generate a Base64 encoded PDF.
        """
        usage_check = use_feature_if_allowed(request.user, 'manual_estimate')

        if not usage_check["success"]:
            return Response(usage_check, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Call perform_create which will now use the service layer
        self.perform_create(serializer)
        instance = serializer.instance # Get the newly created Estimate instance from perform_create

        # --- Generate PDF and Encode to Base64 ---
        pdf_base64 = None
        try:
            pdf_base64 = generate_estimate_pdf_base64(instance, request.user, request=request)
            print(f"PDF generated successfully for new estimate {instance.id}")
        except Exception as e:
            print(f"Error generating PDF after creating estimate {instance.id}: {e}")
            traceback.print_exc()

            # Decide how to handle PDF generation failure.
            # Option 1: Still return 201 Created but with a warning.
            response_data = serializer.data # Use the serializer.data of the successfully created instance
            response_data['pdf_error'] = f"Estimate saved, but failed to generate PDF: {e}"
            # return Response(response_data, status=status.HTTP_201_CREATED) # Still success, but with error
            # Option 2: Consider PDF generation critical and return 500.
            return Response(
                {"estimate": serializer.data, "pdf_error": f"Estimate saved, but failed to generate PDF: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # --- Prepare the DRF Response ---
        response_data = serializer.data
        response_data['pdf_base64'] = pdf_base64

        headers = self.get_success_headers(serializer.data)
        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)


    def perform_create(self, serializer):
        """
        Hook to save the serializer instance, now delegating to a service function.
        """
        print("--- EstimateListCreateView perform_create started (calling service) ---")
        try:
            # Call the service function to handle the full creation process.
            # Pass the request.user and the validated data from the serializer.
            # The service will handle customer linking/creation and nested items.
            estimate = create_estimate_and_nested_items(
                user=self.request.user,
                validated_data=serializer.validated_data # This data already has nested items popped by serializer's create
            )
            # Update the serializer instance with the fully created estimate object
            # so serializer.data contains all related and calculated fields for the response.
            serializer.instance = estimate
            print(f"Estimate {estimate.id} and nested items successfully created via service.")
        except ValueError as e: # Catch custom errors from service layer (e.g., customer not found)
            print(f"!!! Error in create_estimate_and_nested_items service: {e} !!!")
            raise serializer.ValidationError({'detail': str(e)}) # Raise as a DRF validation error
        except Exception as e:
            print(f"!!! Unexpected error during estimate creation in perform_create: {e} !!!")
            raise # Re-raise unexpected errors, DRF will catch it and return 500



# class EstimateListCreateView(generics.ListCreateAPIView):
#     """
#     API endpoint that allows Estimates (Projects) to be viewed (GET) or created (POST)
#     by the authenticated user.
#     GET: Lists all Estimates for the authenticated user with full details.
#     POST: Creates a new Estimate, including nested items, generates a PDF,
#           and returns the created Estimate data along with the Base64 PDF string.
#     Requires the user to be authenticated.
#     """
#     queryset = Estimate.objects.all() # Base queryset
#     serializer_class = EstimateSerializer
#     permission_classes = [permissions.IsAuthenticated] # Requires authenticated user for access

#     def get_queryset(self):
#         """
#         Override get_queryset to filter Estimates to only include those
#         belonging to the authenticated user (`request.user`).
#         Use select_related/prefetch_related to optimize fetching related data
#         for the serializer to avoid N+1 queries when listing.
#         """
#         user = self.request.user
#         # Fetch related customer (ForeignKey - select_related) and nested items
#         # (ManyToOne/Many Many - prefetch_related) efficiently.
#         return Estimate.objects.filter(user=user).select_related('customer').prefetch_related('rooms', 'materials', 'labour').order_by('-estimate_date') # Order by newest first


#     def create(self, request, *args, **kwargs):
#         """
#         Handles POST requests to create an Estimate (Project), save nested items,
#         and generate a Base64 encoded PDF.
#         """
#         # Use the serializer to validate and deserialize the incoming data (including nested data)
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         # Save the Estimate instance and its nested objects.
#         # The serializer's custom create method handles the nested logic and linking to the user.
#         self.perform_create(serializer)
#         instance = serializer.instance # Get the newly created Estimate instance

#         # --- Generate PDF and Encode to Base64 ---
#         pdf_base64 = None
#         try:
#              # Call the reusable PDF generation function from estimates.utils
#              # Pass the created instance, the request user, and the request object
#              pdf_base64 = generate_estimate_pdf_base64(instance, request.user, request=request)
#              print(f"PDF generated successfully for new estimate {instance.id}")
#         except Exception as e:
#              # Log the error and decide how to respond.
#              # Returning a 500 error here indicates that the estimate was saved,
#              # but PDF generation failed. You might adjust the status code or response
#              # based on whether PDF generation is critical for creation success.
#              print(f"Error generating PDF after creating estimate {instance.id}: {e}")
#              traceback.print_exc() # Print full traceback for debugging

#              return Response(
#                  {"estimate": serializer.data, "pdf_error": f"Estimate saved, but failed to generate PDF: {e}"},
#                  status=status.HTTP_500_INTERNAL_SERVER_ERROR # Or HTTP_201_CREATED with a warning
#              )


#         # --- Prepare the DRF Response ---
#         # Return the created Estimate data (from the serializer's representation)
#         # AND the Base64 PDF string in a single response.
#         response_data = serializer.data # Get the serialized representation of the created instance
#         response_data['pdf_base64'] = pdf_base64 # Add the base64 PDF string to the response data

#         # Use get_success_headers to include Location header (optional but good practice)
#         headers = self.get_success_headers(serializer.data)
#         # Return 201 Created status code
#         return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)


#     def perform_create(self, serializer):
#         """
#         Hook to save the serializer instance.
#         Associates the current authenticated user with the Estimate before saving.
#         The serializer's custom create method will then handle nested items.
#         """
#         # Pass the request user to the serializer's create method
#         serializer.save(user=self.request.user)
#         print("Serializer save called in perform_create.")


class EstimateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint that allows a specific Estimate (Project) to be retrieved,
    updated, or deleted by its owner.
    GET: Retrieves details for a specific Estimate with full nested information.
    PUT/PATCH: Updates a specific Estimate, including nested items, regenerates the PDF,
               and returns the updated Estimate data along with the new Base64 PDF string.
    DELETE: Deletes a specific Estimate.
    Requires the user to be authenticated and the owner of the Estimate.
    """
    queryset = Estimate.objects.all() # Base queryset
    serializer_class = EstimateSerializer
    # Apply both authentication and the custom owner permission
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        """
        Override get_queryset to filter Estimates to only include those
        belonging to the authenticated user. The IsOwner permission will
        then enforce object-level ownership.
        Optimize fetching related data for the serializer.
        """
        user = self.request.user
        # Fetch related data to avoid N+1 queries
        return Estimate.objects.filter(user=user).select_related('customer').prefetch_related('rooms', 'materials', 'labour')


    def update(self, request, *args, **kwargs):
        """
        Handles PUT/PATCH requests to update an Estimate (Project), save nested items,
        and regenerate a Base64 encoded PDF.
        """
        # Determine if it's a partial update (PATCH)
        partial = kwargs.pop('partial', False)
        # Get the Estimate instance to update (get_object handles the pk lookup,
        # get_queryset filters by user, and IsOwner checks ownership)
        instance = self.get_object()

        # Use the serializer to validate and update the instance (including nested data)
        # Pass the existing instance and the incoming data.
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        # Save the updated Estimate instance and its nested objects.
        # The serializer's custom update method handles the nested logic.
        self.perform_update(serializer) # Calls serializer.save() which triggers the serializer's update method
        updated_instance = serializer.instance # Get the updated Estimate instance

        # --- Regenerate PDF and Encode to Base64 ---
        pdf_base64 = None
        try:
             # Call the reusable PDF generation function with the updated instance
             pdf_base64 = generate_estimate_pdf_base64(updated_instance, request.user, request=request)
             print(f"PDF regenerated successfully for updated estimate {updated_instance.id}")
        except Exception as e:
             # Log the error and decide how to respond.
             # It's common to return the updated data but indicate the PDF failure.
             print(f"Error regenerating PDF after updating estimate {updated_instance.id}: {e}")
             traceback.print_exc() # Print full traceback for debugging
             return Response(
                 {"estimate": serializer.data, "pdf_error": f"Estimate updated, but failed to regenerate PDF: {e}"},
                 status=status.HTTP_500_INTERNAL_SERVER_ERROR # Or HTTP_200_OK with a warning
             )


        # --- Prepare the DRF Response ---
        # Return the updated Estimate data (from the serializer's representation)
        # AND the Base64 PDF string in a single response.
        response_data = serializer.data # Get the serialized representation of the updated instance
        response_data['pdf_base64'] = pdf_base64 # Add the base64 PDF string

        # Return 200 OK status code for a successful update
        return Response(response_data, status=status.HTTP_200_OK)


    def perform_update(self, serializer):
        """
        Hook to save the updated serializer instance.
        The serializer's custom update method handles nested item updates.
        """
        serializer.save() # The serializer's update method is called here
        print("Serializer save called in perform_update.")

    # destroy method (for DELETE requests) is provided by RetrieveUpdateDestroyAPIView by default.
    # It uses get_object() (which is filtered by get_queryset and checked by IsOwner)
    # and then calls instance.delete(). This is sufficient for basic deletion.


# --- Customer Views ---
# These views are for managing Customer objects themselves, separate from Estimates.
# If Customer objects are *only* created/managed nested within Estimates, you might
# not need these standalone views, but they are included based on your initial snippet.

class CustomerListCreateView(generics.ListCreateAPIView):
    """
    API endpoint that allows Customers to be viewed (GET) or created (POST)
    by the authenticated user.
    Requires the user to be authenticated.
    """
    queryset = Customer.objects.all() # Base queryset
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Filter Customers to only include those belonging to the authenticated user.
        """
        user = self.request.user
        print(f"Authenticated user: {user} (ID: {user.id})")
        queryset = Customer.objects.filter(user=user).order_by('name') 
        print(f"Queryset returned by filter: {queryset}")
        for customer in queryset:
            print(f"- Customer ID: {customer.id}, Name: {customer.name}")
        
        return Customer.objects.filter(user=user).order_by('name') # Order by name


    def perform_create(self, serializer):
        """
        Associates the current authenticated user with the Customer before saving.
        """
        serializer.save(user=self.request.user)
        print("Customer created and linked to user.")


class CustomerDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint that allows a specific Customer to be retrieved, updated, or deleted
    by its owner.
    Requires the user to be authenticated and the owner of the Customer.
    """
    queryset = Customer.objects.all() # Base queryset
    serializer_class = CustomerSerializer
    # Apply both authentication and the custom owner permission
    permission_classes = [permissions.IsAuthenticated, IsOwner] # Assuming Customer model also has a 'user' field

    def get_queryset(self):
        """
        Filter Customers to only include those belonging to the authenticated user.
        IsOwner permission will enforce object-level ownership.
        """
        user = self.request.user
        return Customer.objects.filter(user=user)


# --- Endpoint for Listing User's Customers (Simplified) ---
# This view lists customers specifically for the 'contacts' page scenario,
# fetching customers linked to the user's Estimates.

class UserCustomerListView(generics.ListAPIView):
    """
    API endpoint that lists all unique Customers associated with the authenticated
    user's Estimates. Returns specific fields (id, name, location, phone).
    Useful for a contacts list page.
    Requires the user to be authenticated.
    """
    # Use the CustomerSerializer defined above which includes id, name, location, phone.
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated] # Requires authenticated user

    def get_queryset(self):
        """
        Return only unique Customers that are linked to the authenticated user's Estimates.
        Assumes Estimate has a ForeignKey to Customer.
        """
        user = self.request.user
        # Get the IDs of all unique customers linked to the user's estimates
        customer_ids = Estimate.objects.filter(user=user).values_list('customer', flat=True).distinct()
        queryset = Customer.objects.filter(id__in=customer_ids).exclude(id__isnull=True).order_by('name')
        # Filter the Customer model by these IDs and exclude any None/null customer_ids
        # Ensure only customers that have a valid link are returned
        print(queryset)
        return queryset


# --- Optional Nested Item Views ---
# These views allow managing MaterialItem, RoomArea, LabourItem instances
# via endpoints specific to the Estimate they belong to (e.g., /estimates/123/materials/).
# These are optional if you primarily manage these items nested within the Estimate
# creation/update via the EstimateSerializer.

# class MaterialItemListCreateView(generics.ListCreateAPIView):
#      serializer_class = MaterialItemSerializer
#      permission_classes = [permissions.IsAuthenticated, IsOwner] # Apply owner permission to the Estimate

#      def get_queryset(self):
#          # Get the estimate ID from the URL kwargs
#          estimate_id = self.kwargs['estimate_id']
#          # Get the Estimate instance, ensuring it belongs to the current user
#          estimate = get_object_or_404(Estimate.objects.filter(user=self.request.user), id=estimate_id)
#          # Return material items linked to this estimate
#          return MaterialItem.objects.filter(estimate=estimate)

#      def perform_create(self, serializer):
#          # Get the estimate ID from the URL kwargs
#          estimate_id = self.kwargs['estimate_id']
#          # Get the Estimate instance, ensuring it belongs to the current user
#          estimate = get_object_or_404(Estimate.objects.filter(user=self.request.user), id=estimate_id)
#          # Link the new material item to this estimate before saving
#          serializer.save(estimate=estimate)

# # Add similar views for RoomArea and LabourItem if needed following the pattern above.
# class RoomAreaItemListCreateView(generics.ListCreateAPIView):
#     serializer_class = RoomAreaSerializer
#     permission_classes = [permissions.IsAuthenticated, IsOwner] # Apply owner permission to the Estimate

#     def get_queryset(self):
#         estimate_id = self.kwargs['estimate_id']
#         estimate = get_object_or_404(Estimate.objects.filter(user=self.request.user), id=estimate_id)
#         return RoomArea.objects.filter(estimate=estimate)

#     def perform_create(self, serializer):
#         estimate_id = self.kwargs['estimate_id']
#         estimate = get_object_or_404(Estimate.objects.filter(user=self.request.user), id=estimate_id)
#         serializer.save(estimate=estimate)

# class LabourItemListCreateView(generics.ListCreateAPIView):
#     serializer_class = LabourItemSerializer
#     permission_classes = [permissions.IsAuthenticated, IsOwner] # Apply owner permission to the Estimate

#     def get_queryset(self):
#         estimate_id = self.kwargs['estimate_id']
#         estimate = get_object_or_404(Estimate.objects.filter(user=self.request.user), id=estimate_id)
#         return LabourItem.objects.filter(estimate=estimate)

#     def perform_create(self, serializer):
#         estimate_id = self.kwargs['estimate_id']
#         estimate = get_object_or_404(Estimate.objects.filter(user=self.request.user), id=estimate_id)
#         serializer.save(estimate=estimate)