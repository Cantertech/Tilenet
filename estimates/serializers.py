
from rest_framework import serializers
from .models import Material, QuickEstimate, EstimateMaterial

class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = '__all__'

class EstimateMaterialSerializer(serializers.ModelSerializer):
    material_name = serializers.ReadOnlyField(source='material.name')
    material_unit = serializers.ReadOnlyField(source='material.unit')
    
    class Meta:
        model = EstimateMaterial
        fields = ('id', 'material', 'material_name', 'material_unit', 'quantity', 'unit_price', 'total_price')
        read_only_fields = ('total_price',)

class QuickEstimateSerializer(serializers.ModelSerializer):
    materials = EstimateMaterialSerializer(many=True, read_only=True)
    
    class Meta:
        model = QuickEstimate
        fields = '__all__'
        read_only_fields = ('user', 'total_area', 'estimated_cost', 'created_at', 'updated_at')
    
    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['user'] = user
        
        # Calculate total area based on dimensions
        length = validated_data.get('length', 0)
        breadth = validated_data.get('breadth', 0)
        height = validated_data.get('height', None)
        
        # Calculate area (for tiles and pavement it's just length * breadth)
        total_area = length * breadth
        
        # For walls, include height calculation if provided
        if validated_data.get('project_type') == 'masonry' and height:
            total_area = length * height
        
        validated_data['total_area'] = total_area
        
        # Default estimated cost to 0, will be updated by the materials calculation
        validated_data['estimated_cost'] = 0
        
        estimate = QuickEstimate.objects.create(**validated_data)
        return estimate

class QuickEstimateCreateSerializer(serializers.ModelSerializer):
    materials = serializers.ListSerializer(
        child=serializers.PrimaryKeyRelatedField(queryset=Material.objects.all()),
        required=False
    )
    
    class Meta:
        model = QuickEstimate
        fields = ('name', 'project_type', 'room_type', 'measurement_unit', 
                 'length', 'breadth', 'height', 'floor_thickness', 
                 'auto_wastage', 'manual_wastage_factor', 'materials')
