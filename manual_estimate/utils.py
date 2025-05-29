# your_project/estimates/utils.py (Create this file)
import traceback
import io
import os
from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML
import random
import base64
from decimal import Decimal
from django.db.models import Sum
from django.http import HttpRequest # Import HttpRequest for build_absolute_uri
from django.shortcuts import get_object_or_404 # Used if fetching instance inside

# Import your models if needed (or ensure the Estimate instance is passed in)
# from .models import Estimate, Customer, MaterialItem, RoomArea, LabourItem
# from accounts.models import UserProfile # Assuming UserProfile is in accounts

def generate_estimate_pdf_base64(estimate_instance, request_user, request=None):
    """
    Generates an estimate PDF from an Estimate instance and returns it as a Base64 string.
    Requires the request_user to fetch related UserProfile.
    Optionally takes the full request object to build absolute URIs for static/media.
    """
    try:
        print(f"--- Starting PDF Generation for Estimate ID: {estimate_instance.id} ---")

        # Define your primary color (get from user profile or settings)
        # Assuming request_user has a related 'userprofile'
        user_profile = None
        try:
            user_profile = request_user.userprofile
        except AttributeError: # Catch the case if user_profile is not linked or doesn't exist
             print("User profile not found for the request user.")
             pass

        primary_color_for_pdf = getattr(user_profile, 'primary_color', '#004a7c') if user_profile else '#004a7c'
        print(f"Using primary color for PDF: {primary_color_for_pdf}")


        # --- Calculate costs for PDF context (ensure using Decimal) ---
        # Replicate the calculation logic from your original view
        total_material_cost = sum(item.total_price for item in estimate_instance.materials.all()) if estimate_instance.materials.exists() else Decimal('0.00')
        total_material_cost = round(total_material_cost, 2)

        total_labour_cost = round(estimate_instance.total_labour_cost, 2) # Assuming profit is added to labour cost

        transport_cost = estimate_instance.transport_cost if estimate_instance.transport_cost is not None else Decimal('0.00')

        grand_total = round(total_material_cost + total_labour_cost + transport_cost, 2)

        total_floor_area = sum(room.floor_area for room in estimate_instance.rooms.all()) if estimate_instance.rooms.exists() else Decimal('0.00')
        total_wall_area = sum(room.wall_area for room in estimate_instance.rooms.all()) if estimate_instance.rooms.exists() else Decimal('0.00')
        total_tiled_surface_area = round(total_floor_area + total_wall_area, 2)

        per_square_meter_cost = estimate_instance.labour_per_sq_meter
        

        subtotal_cost = round(total_material_cost + total_labour_cost, 2) # materials + labour
        wastage_percentage = estimate_instance.wastage_percentage if hasattr(estimate_instance, 'wastage_percentage') and estimate_instance.wastage_percentage is not None else 0 # Assuming Estimate has wastage_percentage field
        

        random_suffix = random.randint(100, 999)  # 3-digit random number
        estimate_number = f"EST-{estimate_instance.id:06d}-{random_suffix}"


        # --- Construct the context dictionary for the HTML template ---
        template_context = {
            'estimate': estimate_instance, # Pass the instance directly
            'estimate_number': estimate_number,
            'project_name': estimate_instance.title,
            'project_date': estimate_instance.estimate_date,
            'project_type': 'Construction', # Static or from model
            'description': estimate_instance.remarks,
            'validity_days': 30, # Static or from settings/model
            'primary_color': primary_color_for_pdf,
            'estimated_days': estimate_instance.estimated_days if hasattr(estimate_instance, 'estimated_days') and estimate_instance.estimated_days is not None else 0,


            'user_profile': user_profile, # Pass user_profile object
            'user_info': request_user,
            'company_name': user_profile.company_name if user_profile else "[Company Name]",
            'company_address': user_profile.address if user_profile else "[Company Address]",
            'company_phone': user_profile.phone_number if user_profile else "[Company Phone]",
            'company_email': request_user.email if request_user and request_user.email else "[Company Email]",
            'company_location': user_profile.city if user_profile else "[Company Location]",
            'company_website': user_profile.website if user_profile else None,


            'customer_name': estimate_instance.customer.name if estimate_instance.customer else "[Client Name]",
            'location': estimate_instance.customer.location if estimate_instance.customer else "[Client Location]",
            'contact': estimate_instance.customer.phone if estimate_instance.customer else "[Client Contact]",

            'rooms': estimate_instance.rooms.all(),
            'materials': estimate_instance.materials.all(),


            'total_material_cost': total_material_cost,
            'total_labor_cost': total_labour_cost, # Use total_labor_cost to match template or adjust template
            'transport': transport_cost,
            'grand_total': grand_total,

            'subtotal_cost': subtotal_cost,
            'wastage_percentage': wastage_percentage,

            'cost_per_area': per_square_meter_cost,
            'total_area': total_tiled_surface_area,
            'measurement_unit': 'm', # Hardcode or make configurable

            # Base URL for resolving static/media files in the template
            # Crucial for WeasyPrint to find CSS/images
            'base_url': request.build_absolute_uri('/') if request else settings.SITE_URL, # Use request if available, otherwise a setting

        }

        print("Attempting to render HTML template 'manual_estimate_template.html'...")
        # Render the HTML template
        html_string = render_to_string('manual_estimate_template.html', template_context)
        print("HTML template rendered successfully.")

        # --- TEMPORARY DEBUGGING STEP: Save HTML to a file (Conditional) ---
        if settings.DEBUG and request: # Only save HTML file if DEBUG is True AND request is available
            debug_html_path = os.path.join(settings.BASE_DIR, f'debug_estimate_{estimate_instance.id}_updated.html') # Use a different name for updated PDFs
            with open(debug_html_path, 'w', encoding='utf-8') as f:
                 f.write(html_string)
            print(f"Saved generated HTML to: {debug_html_path}")
        # --- END DEBUGGING STEP ---


        print("Attempting to generate PDF from HTML using WeasyPrint...")
        # Generate PDF from HTML using WeasyPrint
        pdf_file = HTML(string=html_string, base_url=template_context['base_url']).write_pdf()
        print("PDF file generated successfully.")

        print("Encoding PDF to Base64...")
        # Encode PDF byte stream as base64
        pdf_base64 = base64.b64encode(pdf_file).decode('utf-8')
        print("PDF encoded to Base64 successfully.")

        return pdf_base64 # Return the base64 string

    except Exception as e:
        print(f"!!! Error during PDF generation or encoding for estimate {estimate_instance.id}: {e} !!!")
        traceback.print_exc() # Print the detailed traceback
        # Re-raise the exception or return None/error indicator
        raise e # Re-raise to be caught by the view