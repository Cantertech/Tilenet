import json
import random
import datetime
import base64
import os
import decimal

from django.shortcuts import get_object_or_404, render
from django.http import Http404, HttpResponse, JsonResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from rest_framework import status, viewsets, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.views import APIView
from weasyprint import HTML

from accounts.models import UserProfile, get_projects_left, use_feature_if_allowed

from .models import (
    DynamicSetting, Material, Project, Room, ProjectMaterial, Worker, Tile,
    Unit,
    TilingRoomDetails, PaintingRoomDetails,
)

from .serializers import (
    ProjectMaterialSerializer, ProjectSerializer, MaterialSerializer, ProjectStatusSerializer, WorkerSerializer, RoomSerializer,
    UnitSerializer, DynamicSettingSerializer, TileSerializer,
    TilingRoomDetailsSerializer, PaintingRoomDetailsSerializer,
)

from . import project_calculations

room_detail_serializers_map = {
    'tiling': TilingRoomDetailsSerializer,
    'painting': PaintingRoomDetailsSerializer,
}

User = get_user_model()

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(user=self.request.user).prefetch_related(
            Prefetch('rooms', queryset=Room.objects.prefetch_related('details')),
            'materials__material__unit',
            'workers',
        )

    def perform_create(self, serializer):
        instance = serializer.save(user=self.request.user)
        project_calculations.calculate_project_totals(instance.id)

    def perform_update(self, serializer):
        instance = serializer.save()
        project_calculations.calculate_project_totals(instance.id)

    def perform_destroy(self, instance):
        project_id = instance.id
        instance.delete()
        project_calculations.calculate_project_totals(project_id)


class UnitViewSet(viewsets.ModelViewSet):
    queryset = Unit.objects.all()
    serializer_class = UnitSerializer
    permission_classes = [IsAdminUser]


class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Material.objects.filter(is_global=True) | self.queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        if serializer.validated_data.get('is_global', False):
            if self.request.user.is_staff:
                serializer.save(user=None)
            else:
                return Response({'detail': 'You do not have permission to create global materials.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            serializer.save(user=self.request.user)


class ProjectMaterialViewSet(viewsets.ModelViewSet):
    queryset = ProjectMaterial.objects.all()
    serializer_class = ProjectMaterialSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(project__user=self.request.user)

    def perform_create(self, serializer):
        instance = serializer.save()
        project_calculations.calculate_project_totals(instance.project_id)

    def perform_update(self, serializer):
        instance = serializer.save()
        project_calculations.calculate_project_totals(instance.project_id)

    def perform_destroy(self, instance):
        project_id = instance.project_id
        instance.delete()
        project_calculations.calculate_project_totals(project_id)


class WorkerViewSet(viewsets.ModelViewSet):
    queryset = Worker.objects.all()
    serializer_class = WorkerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(project__user=self.request.user)

    def perform_create(self, serializer):
        instance = serializer.save()
        project_calculations.calculate_project_totals(instance.project_id)

    def perform_update(self, serializer):
        instance = serializer.save()
        project_calculations.calculate_project_totals(instance.project_id)

    def perform_destroy(self, instance):
        project_id = instance.project_id
        instance.delete()
        project_calculations.calculate_project_totals(project_id)


class RoomViewSet(viewsets.ModelViewSet):
    queryset = Room.objects.all()
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(project__user=self.request.user).prefetch_related('details')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            room_instance = serializer.save()

            project_type = room_instance.project.project_type
            details_model = None
            detail_serializer_class = None

            if project_type == 'tiling':
                details_model = TilingRoomDetails
                detail_serializer_class = TilingRoomDetailsSerializer
            elif project_type == 'painting':
                details_model = PaintingRoomDetails
                detail_serializer_class = PaintingRoomDetailsSerializer

            if details_model and detail_serializer_class:
                detail_data = request.data.copy()
                detail_serializer = detail_serializer_class(data=detail_data)
                detail_serializer.is_valid(raise_exception=True)

                details_instance = details_model.objects.create(
                    room_content_type=ContentType.objects.get_for_model(room_instance),
                    room_object_id=room_instance.pk,
                    **detail_serializer.validated_data
                )

                room_instance.details_content_type = ContentType.objects.get_for_for_model(details_instance)
                room_instance.details_object_id = details_instance.pk
                room_instance.save(update_fields=['details_content_type', 'details_object_id'])

            elif details_model and not detail_serializer_class:
                raise Exception(f"Configuration Error: Missing serializer for {details_model.__name__}")
            elif not details_model and project_type != 'others':
                raise Exception(f"Configuration Error: Missing Room Details model mapping for type '{project_type}'")

            project_calculations.calculate_project_totals(room_instance.project_id)

        response_room = Room.objects.filter(id=room_instance.id).prefetch_related('details').first()

        return Response(RoomSerializer(response_room).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            self.perform_update(serializer)

            if instance.details:
                detail_serializer_class = None
                if isinstance(instance.details, TilingRoomDetails):
                    detail_serializer_class = TilingRoomDetailsSerializer
                elif isinstance(instance.details, PaintingRoomDetails):
                    detail_serializer_class = PaintingRoomDetailsSerializer

                if detail_serializer_class:
                    detail_data = request.data.copy()
                    detail_serializer = detail_serializer_class(instance.details, data=detail_data, partial=partial)

                    if detail_serializer.is_valid(raise_exception=True):
                        detail_serializer.save()
                    else:
                        return Response(detail_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            project_calculations.calculate_project_totals(instance.project_id)

        response_room = Room.objects.filter(id=instance.id).prefetch_related('details').first()

        return Response(RoomSerializer(response_room).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        project_id = instance.project_id

        with transaction.atomic():
            self.perform_destroy(instance)

        project_calculations.calculate_project_totals(project_id)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CreateProjectEstimateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Print the raw incoming payload for debugging
        print("--- Incoming Payload ---")
        print(json.dumps(request.data, indent=2))
        print("------------------------")
        usage_check = use_feature_if_allowed(request.user, 'estimate')

        if not usage_check["success"]:
           return Response(usage_check, status=status.HTTP_403_FORBIDDEN)


        with transaction.atomic():
            request_data = request.data.copy()

            # Pop nested data before validating the main project data
            rooms_data = request_data.pop('room_info', [])
            materials_data = request_data.pop('materials', [])
            workers_data = request_data.pop('workers', [])

            # The remaining data should only contain Project model fields
            project_data = request_data

            print("--- Validating Project Data ---")
            print("Project Data:", project_data)
            project_serializer = ProjectSerializer(data=project_data)

            if not project_serializer.is_valid():
                print("Project Serializer Errors:", project_serializer.errors)
                return Response(project_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            print("Project Data Validated Successfully.")

            # Generate estimate number and increment user counter within the atomic transaction
            user_profile, created = UserProfile.objects.get_or_create(user=user)
            user_profile.estimate_counter += 1
            user_profile.save()
            random_suffix = random.randint(100, 999)
            generated_estimate_number = f"#{random_suffix}{user_profile.estimate_counter:04d}"

            # Save the project instance
            project_instance = project_serializer.save(user=user, estimate_number=generated_estimate_number)
            print("Project Instance Created:", project_instance)

            # --- Process Rooms and Room Details ---
            if rooms_data and isinstance(rooms_data, list):
                print("--- Processing Room Data ---")
                for room_data in rooms_data:
                    print("Processing Room Data Item:", room_data)

                    # Separate basic room data from nested detail data
                    # Assuming nested detail data is under a key like 'tiling_details', 'painting_details', etc.
                    # based on the project type.
                    project_type = project_instance.project_type # Get project type from the created project
                    detail_data_key = f'{project_type}_details' # e.g., 'tiling_details'

                    # Extract the nested detail data, pop it from room_data so RoomSerializer only sees basic fields
                    nested_detail_data = room_data.pop(detail_data_key, None)
                    print(f"Extracted Nested Detail Data ('{detail_data_key}'):", nested_detail_data)

                    # Validate and save the basic Room data
                    basic_room_serializer = RoomSerializer(data=room_data, context={'project_instance': project_instance})

                    if not basic_room_serializer.is_valid():
                        print("Basic Room Serializer Errors:", basic_room_serializer.errors)
                        return Response(basic_room_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                    room_instance = basic_room_serializer.save()
                    print("Basic Room Instance Created:", room_instance)

                    # Process and save Room Details if data and serializer exist
                    detail_serializer_class = room_detail_serializers_map.get(project_type)

                    # --- FIX: Only attempt to validate details if serializer exists AND data is not None ---
                    details_instance = None # Initialize details_instance to None
                    if detail_serializer_class and nested_detail_data is not None:
                        print(f"--- Validating {detail_serializer_class.__name__} ---")
                        print("Data passed to detail serializer:", nested_detail_data)

                        detail_serializer = detail_serializer_class(data=nested_detail_data, context={'room_instance': room_instance, 'project_type': project_type})

                        if not detail_serializer.is_valid():
                            print(f"{detail_serializer_class.__name__} Errors:", detail_serializer.errors)
                            return Response(detail_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                        details_instance = detail_serializer.save()
                        print(f"{detail_serializer_class.__name__} instance created:", details_instance)

                    elif detail_serializer_class and nested_detail_data is None:
                         print(f"Warning: No nested '{detail_data_key}' data provided for room '{room_instance.name}' for project type '{project_type}'. Skipping detail creation.")


                    elif project_type != 'others':
                        # If project type is not 'others' and no specific detail serializer is mapped
                        raise Exception(f"Configuration Error: Missing Room Details serializer mapping for project type '{project_type}'")

                    # Link the details instance to the room instance using GenericForeignKey
                    # This now correctly handles details_instance being None if no details were provided/created
                    if details_instance:
                        room_instance.details_content_type = ContentType.objects.get_for_model(details_instance)
                        room_instance.details_object_id = details_instance.pk
                        room_instance.save(update_fields=['details_content_type', 'details_object_id'])
                        print(f"Linked {type(details_instance).__name__} to Room instance.")
                    else:
                         # If no details instance was created, ensure details fields are cleared on the room
                         room_instance.details_content_type = None
                         room_instance.details_object_id = None
                         room_instance.save(update_fields=['details_content_type', 'details_object_id'])
                         print("No details instance to link or existing details cleared.")


            # --- Process Materials ---
            # NOTE: Quantity calculations are NOT done here.
            # ProjectMaterialSerializer's create method links Material and sets name/unit.
            # Quantity calculations happen AFTER all ProjectMaterials are created, in project_calculations.calculate_project_totals.
            if materials_data and isinstance(materials_data, list):
                print("--- Processing Material Data ---")
                for material_data in materials_data:
                    print("Processing Material Data Item:", material_data)
                    item_serializer = ProjectMaterialSerializer(data=material_data, context={'project_instance': project_instance})

                    if not item_serializer.is_valid():
                        print("ProjectMaterial Serializer Errors:", item_serializer.errors)
                        # Use the helper function to print errors in a structured way
                        # print_serializer_errors("ProjectMaterialSerializer", item_serializer.errors)
                        return Response(item_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                    project_material_instance = item_serializer.save()
                    print("ProjectMaterial instance created:", project_material_instance)


            # --- Process Workers ---
            # NOTE: Worker total cost calculations are NOT done here.
            # WorkerSerializer's create method saves the Worker instance.
            # Total cost calculations happen AFTER all Workers are created, in project_calculations.calculate_project_totals.
            if workers_data and isinstance(workers_data, list):
                print("--- Processing Worker Data ---")
                for worker_data in workers_data:
                    print("Processing Worker Data Item:", worker_data)
                    worker_item_serializer = WorkerSerializer(data=worker_data, context={'project_instance': project_instance})

                    if not worker_item_serializer.is_valid():
                        print("Worker Serializer Errors:", worker_item_serializer.errors)
                        # Use the helper function to print errors in a structured way
                        # print_serializer_errors("WorkerSerializer", worker_item_serializer.errors)
                        return Response(worker_item_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

                    worker_instance = worker_item_serializer.save()
                    print("Worker instance created:", worker_instance)


            # --- Perform Calculations ---
            # This is where quantities, costs, and totals are calculated
            print("--- Performing Project Calculations ---")
            try:
                # Pass the project instance or its ID to the calculation function
                project_calculations.calculate_project_totals(project_instance.id)
                print("Project calculations completed successfully.")

            except Exception as e:
                # Handle calculation errors appropriately, maybe log and return a specific error response
                print(f"An error occurred during project calculation for project {project_instance.id}: {e}")
                import traceback
                traceback.print_exc()
                return Response({"detail": f"An error occurred during calculation: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


            # --- Prepare Response ---
            # Fetch the project again with all related data for the response
            response_project = Project.objects.filter(id=project_instance.id).prefetch_related(
                Prefetch('rooms', queryset=Room.objects.prefetch_related('details')), # Fetch rooms and their details
                'materials__material__unit', # Fetch materials and their default units if needed for display
                'workers', # Fetch workers
            ).first()

            response_serializer = ProjectSerializer(response_project)
            print("--- Sending Response ---")
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def projects_left(request):
     user = request.user
     # Assuming get_projects_left is defined elsewhere
     result = get_projects_left(user)

     if result["success"]:
         return Response({"projects_left": result["projects_left"]}, status=status.HTTP_200_OK)
     else:
         return Response({"error": result["message"]}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_3d_room(request):
     user = request.user
     # Assuming check_and_use_feature is defined elsewhere
     result = use_feature_if_allowed(user, "room_view")

     if not result["success"]:
         return Response({"error": result["message"]}, status=status.HTTP_400_BAD_REQUEST)

     return Response({"message": "3D room view updated successfully."}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_3d_room_view(request):
    user = request.user
    # Assuming check_and_use_feature is defined elsewhere
    result = use_feature_if_allowed(user, "room_view")

    if not result["success"]:
        return Response({"error": result["message"]}, status=status.HTTP_400_BAD_REQUEST)

    return Response({"message": "3D room view generation triggered."})

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_project_status(request, pk):
    try:
        project = Project.objects.get(pk=pk, user=request.user)
    except Project.DoesNotExist:
        return Response({'detail': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ProjectStatusSerializer(project, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Project status updated.', 'data': serializer.data})
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_settings(request):
    try:
        settings, created = DynamicSetting.objects.get_or_create(user=request.user)
        serializer = DynamicSettingSerializer(settings, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_estimatepdf(request):
    if request.method == 'POST':
        # Get data from the frontend payload
        project_id = request.data.get('project_id')
        customer_name_payload = request.data.get('customer_name')
        contact_payload = request.data.get('contact')
        location_payload = request.data.get('Location') # Note: Frontend sends 'Location'
        transport_payload = request.data.get('transport')

        if not project_id:
            return Response({"error": "Project ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Fetch the project instance efficiently with related data
            # Use get_object_or_404 for cleaner error handling if project doesn't exist or user has no permission
            project_instance = get_object_or_404(
                Project.objects.prefetch_related(
                    # Prefetch Rooms and their details
                    # Assuming 'details' is the related_name from Room to its detail model (TilingRoomDetails, PaintingRoomDetails, etc.)
                    Prefetch('rooms', queryset=Room.objects.prefetch_related('details')),
                    # Prefetch ProjectMaterials, their related Material, and the Material's related Unit
                    # Assuming 'material' is the ForeignKey from ProjectMaterial to Material
                    # Assuming 'unit' is the ForeignKey from Material to Unit
                    Prefetch('materials', queryset=ProjectMaterial.objects.select_related('material__unit')),
                    # Prefetch Workers
                    'workers',
                ),
                id=project_id,
                user=request.user # Ensure project belongs to the authenticated user
            )

            # --- Apply updates from payload and save ---
            # We only save the specific fields that can be updated via this endpoint
            update_fields = []
            if customer_name_payload is not None:
                project_instance.customer_name = customer_name_payload
                update_fields.append('customer_name')
            if contact_payload is not None:
                project_instance.customer_phone = contact_payload
                update_fields.append('customer_phone')
            if location_payload is not None:
                project_instance.customer_location = location_payload
                update_fields.append('customer_location')

            # Handle transport conversion and update
            current_transport = decimal.Decimal('0') # Default to 0 if payload transport is invalid or None
            if transport_payload is not None:
                try:
                    current_transport = decimal.Decimal(str(transport_payload or '0')) # Ensure it's a string for Decimal conversion
                    project_instance.transport = current_transport # Save transport value
                    update_fields.append('transport')
                    # IMPORTANT: Do NOT add transport to total_cost and save it here.
                    # The grand_total will be calculated in the context data using the components.
                except (decimal.InvalidOperation, TypeError):
                    # Handle cases where transport is not a valid number
                    return Response({"error": "Invalid transport value."}, status=status.HTTP_400_BAD_REQUEST)

            if update_fields:
                project_instance.save(update_fields=update_fields)

            # --- Prepare Context Data for Template ---
            # Fetch the user profile - assuming one exists or gets created
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)
            user = request.user
            project_data = ProjectSerializer(project_instance).data
            subtotal = decimal.Decimal(project_data.get('subtotal_cost', '0'))
            profit_amount = decimal.Decimal(project_data.get('profit', '0'))
            calculated_grand_total = subtotal + profit_amount + current_transport

            context_data = {
                # Company/User Profile Info
                'user_profile': user_profile, # Pass the UserProfile object/dictionary
                # Settings/Theme
                'primary_color': settings.PRIMARY_COLOR if hasattr(settings, 'PRIMARY_COLOR') else '#007bff', # Get primary color from settings
                'base_url': request.build_absolute_uri('/')[:-1] + settings.STATIC_URL, # Base URL for static files
                'validity_days': 30, # Or get from settings or UserProfile
                'project_date': project_data.get('date', 'N/A'),
                # Project & Estimate Details
                'estimate_number': project_data.get('estimate_number', 'N/A'),
                'project_name': project_data.get('name', 'N/A'),
                'project_date': project_data.get('date', 'N/A'), # Should be a date object or string
                'location': project_data.get('location', 'N/A'), # Project location
                'project_type': project_instance.project_type, # Assuming project_type is direct field
                'status': project_data.get('status', 'N/A'),
                'measurement_unit': project_data.get('measurement_unit', 'meters'),
                'estimated_days': project_data.get('estimated_days', 0),
                'description': project_data.get('description', ''), # Project description

                # Customer Information (from payload, fallback to project instance/data)
                'customer_name': customer_name_payload if customer_name_payload is not None else project_instance.customer_name or 'N/A',
                'contact': contact_payload if contact_payload is not None else project_instance.customer_phone or 'N/A',
                'customer_location': location_payload if location_payload is not None else project_instance.customer_location or project_instance.location or 'N/A', # Use location from payload, fallback to customer_location, then project location

                # Area Details
                'total_area': decimal.Decimal(project_data.get('total_area', '0')),
                'total_floor_area': decimal.Decimal(project_data.get('total_floor_area', '0')),
                'total_wall_area': decimal.Decimal(project_data.get('total_wall_area', '0')),
                'cost_per_area': decimal.Decimal(project_data.get('cost_per_area', '0')),

                # Lists of related items (prefetched data should be available through serializer data)
                'rooms': project_data.get('rooms', []),
                'materials': project_data.get('materials', []),
                'workers': project_data.get('workers', []),

                # Financial Summary & Totals (Calculated in view context)
                'total_material_cost': decimal.Decimal(project_data.get('total_material_cost', '0')),
                'total_labor_cost': decimal.Decimal(project_data.get('total_labor_cost', '0')),
                'subtotal_cost': subtotal, # Use the calculated subtotal
                'wastage_percentage': decimal.Decimal(project_data.get('wastage_percentage', '0')),
                'profit_type': project_data.get('profit_type'),
                'profit_value': decimal.Decimal(project_data.get('profit_value', '0') or '0'), # Ensure profit_value is Decimal
                'profit': profit_amount, # Use the calculated profit amount
                'transport': current_transport, # Use the validated and potentially updated transport from payload
                'grand_total': calculated_grand_total, # Use the calculated grand total

            }
            # Ensure decimal values are converted to strings with correct precision for template if needed,
            # but floatformat should handle Decimal objects directly, so passing Decimals is usually fine.

            # Render the HTML template with the context data
            # Ensure template is found, e.g., 'yourapp/pdf_template.html' or just 'pdf_template.html'
            pdf_html_content = render_to_string('pdf_template.html', context_data)

            # Generate the PDF using WeasyPrint
            # base_url is crucial for WeasyPrint to load static files (like the logo)
            # Make sure your static files are configured correctly and accessible by WeasyPrint
            pdf_file = HTML(string=pdf_html_content, base_url=context_data['base_url']).write_pdf()

            # Encode the PDF to base64 and return
            pdf_base64 = base64.b64encode(pdf_file).decode('utf-8')
            return Response(pdf_base64, status=status.HTTP_200_OK)

        except Project.DoesNotExist:
            return Response({"error": "Project not found or you do not have permission."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            # Catch any other errors during the process (rendering, PDF generation, etc.)
            print(f"Error generating PDF: {e}")
            import traceback
            traceback.print_exc() # Print traceback to console for debugging
            return Response({"error": "Error generating PDF: " + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    else:
        return Response({"error": "Only POST method is allowed."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_tile_image(request):
    return Response({"message": "Image processing endpoint - Implementation needed."})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_manual_estimate_pdf(request):
    """
    Generates a PDF estimate from manually entered data received from the frontend.
    """
    if request.method == 'POST':
        try:
            # Get the structured data from the frontend payload
            estimate_data = request.data

            # Basic validation: Check if required sections exist
            company_info = estimate_data.get('companyInfo')
            customer_info = estimate_data.get('customerInfo')
            tables_data = estimate_data.get('tables')
            summary_data = estimate_data.get('summary')

            if not all([company_info, customer_info, tables_data, summary_data]):
                 return Response({"error": "Invalid data structure. Missing required sections."}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch the user profile for additional company details or custom template logic
            user_profile, created = UserProfile.objects.get_or_create(user=request.user)

            # --- Determine Template ---
            # For now, we'll use a single generic template.
            # In the future, you could add logic here to select a template
            # based on user_profile settings (e.g., user_profile.pdf_template_name)
            template_name = 'manual_estimate_template.html' # You will create this template

            # --- Prepare Context Data for Template ---
            # Map the received JSON data to template variables
            context_data = {
                'user_profile': user_profile, # Pass the full user profile
                'company_info': company_info,
                'customer_info': customer_info,
                'tables': tables_data, # Contains materials, rooms, labour arrays
                'summary': summary_data,
                'date_generated': datetime.date.today().strftime('%Y-%m-%d'), # Add current date
                # You could add estimate number generation here if not done on frontend
                # 'estimate_number': generate_unique_estimate_number(request.user),
                # Pass a primary color if the template uses it
                # 'primary_color': user_profile.theme_color or '#007bff', # Example: get color from profile
            }

            # Convert Decimal strings in summary data to Decimal objects for calculations in template (optional but recommended)
            try:
                context_data['summary']['grandTotal'] = decimal.Decimal(summary_data.get('grandTotal', '0') or '0')
                context_data['summary']['totalMaterialCost'] = decimal.Decimal(summary_data.get('totalMaterialCost', '0') or '0')
                context_data['summary']['totalLabourCost'] = decimal.Decimal(summary_data.get('totalLabourCost', '0') or '0')
                context_data['summary']['totalRoomArea'] = decimal.Decimal(summary_data.get('totalRoomArea', '0') or '0')

                # Convert Decimal strings in table data to Decimal objects
                for table_type in ['materials', 'rooms', 'labour']:
                    if table_type in context_data['tables']:
                        for item in context_data['tables'][table_type]:
                            for field in item:
                                if isinstance(item[field], str) and item[field].replace('.', '', 1).isdigit():
                                    try:
                                        item[field] = decimal.Decimal(item[field] or '0')
                                    except decimal.InvalidOperation:
                                        pass # Keep as string if invalid decimal

            except Exception as e:
                print(f"Warning: Could not convert some numeric values to Decimal: {e}")
                # Continue, template might handle strings, but calculations will fail


            # Render the HTML template
            # Ensure your template directory is configured in settings.py
            pdf_html_content = render_to_string(template_name, context_data)

            # Generate the PDF using WeasyPrint
            # base_url is important for finding static files (like the logo)
            base_url = request.build_absolute_uri('/')
            pdf_file = HTML(string=pdf_html_content, base_url=base_url).write_pdf()

            # Encode the PDF to base64 and return
            pdf_base64 = base64.b64encode(pdf_file).decode('utf-8')
            return Response(pdf_base64, status=status.HTTP_200_OK)

        except Exception as e:
            # Log the error and return a 500 response
            print(f"Error generating manual estimate PDF: {e}")
            import traceback
            traceback.print_exc()
            return Response({"error": "An internal error occurred while generating the PDF."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    else:
        # Return 405 Method Not Allowed for non-POST requests
        return Response({"error": "Only POST method is allowed."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
