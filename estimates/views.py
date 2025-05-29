
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import F, Sum
from .models import Material, QuickEstimate, EstimateMaterial
from .serializers import MaterialSerializer, QuickEstimateSerializer, QuickEstimateCreateSerializer, EstimateMaterialSerializer
from .utils import calculate_materials, calculate_wastage_factor, convert_to_meters

class MaterialViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Material.objects.all()
    serializer_class = MaterialSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['project_type']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        project_type = self.request.query_params.get('project_type')
        if project_type:
            queryset = queryset.filter(project_type=project_type)
        return queryset

class QuickEstimateViewSet(viewsets.ModelViewSet):
    serializer_class = QuickEstimateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return QuickEstimate.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return QuickEstimateCreateSerializer
        return QuickEstimateSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Extract data for material calculations
        project_type = serializer.validated_data.get('project_type')
        room_type = serializer.validated_data.get('room_type')
        length = serializer.validated_data.get('length')
        breadth = serializer.validated_data.get('breadth')
        height = serializer.validated_data.get('height')
        measurement_unit = serializer.validated_data.get('measurement_unit')
        floor_thickness = serializer.validated_data.get('floor_thickness')
        auto_wastage = serializer.validated_data.get('auto_wastage', True)
        manual_wastage_factor = serializer.validated_data.get('manual_wastage_factor')
        
        # Convert dimensions to meters for calculation
        length_m = convert_to_meters(length, measurement_unit)
        breadth_m = convert_to_meters(breadth, measurement_unit)
        height_m = convert_to_meters(height, measurement_unit) if height else None
        floor_thickness_m = convert_to_meters(floor_thickness, measurement_unit)
        
        # Calculate total area (in square meters)
        if project_type == 'masonry' and height_m:
            total_area = length_m * height_m  # Wall area
        else:
            total_area = length_m * breadth_m  # Floor/surface area
        
        # Calculate wastage factor
        if auto_wastage:
            wastage_factor = calculate_wastage_factor(total_area)
        else:
            wastage_factor = manual_wastage_factor if manual_wastage_factor else 0.1  # Default 10%
            
        # Create the estimate
        estimate = QuickEstimate.objects.create(
            user=request.user,
            name=serializer.validated_data.get('name', f"Quick Estimate {request.user.quick_estimates.count() + 1}"),
            project_type=project_type,
            room_type=room_type,
            measurement_unit=measurement_unit,
            length=length,
            breadth=breadth,
            height=height,
            floor_thickness=floor_thickness,
            auto_wastage=auto_wastage,
            manual_wastage_factor=manual_wastage_factor,
            total_area=total_area
        )
        
        # Calculate material requirements
        material_requirements = calculate_materials(
            project_type=project_type,
            area=total_area,
            wastage_factor=wastage_factor,
            floor_thickness=floor_thickness_m
        )
        
        # Add materials to the estimate
        total_cost = 0
        for material_name, quantity in material_requirements.items():
            try:
                material = Material.objects.get(name=material_name, project_type=project_type)
                
                # Calculate cost
                material_cost = quantity * material.unit_price
                total_cost += material_cost
                
                # Create estimate material entry
                EstimateMaterial.objects.create(
                    estimate=estimate,
                    material=material,
                    quantity=quantity,
                    unit_price=material.unit_price,
                    total_price=material_cost
                )
            except Material.DoesNotExist:
                # Skip if material not found
                continue
        
        # Update total cost
        estimate.estimated_cost = total_cost
        estimate.save()
        
        # Return the complete estimate
        return Response(
            QuickEstimateSerializer(estimate).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def materials(self, request, pk=None):
        estimate = self.get_object()
        materials = estimate.materials.all()
        serializer = EstimateMaterialSerializer(materials, many=True)
        return Response(serializer.data)
