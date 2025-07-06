from django.forms import ValidationError
from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from rest_framework.response import Response # Import Response
from rest_framework import status # Import status

from django.contrib.auth import get_user_model

User = get_user_model()

from .models import (
    Unit, Material, DynamicSetting, Project, Room, TilingRoomDetails, PaintingRoomDetails, ProjectMaterial, Worker, Tile
)

# Helper function to print serializer errors
def print_serializer_errors(serializer_name, errors):
    print(f"--- {serializer_name} Validation Errors ---")
    print(errors)
    print("-----------------------------------------")


class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = '__all__'


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = '__all__'
        read_only_fields = ['user']

class DynamicSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DynamicSetting
        fields = '__all__'
        read_only_fields = ['user']

class TilingRoomDetailsSerializer(serializers.ModelSerializer):
    # Define the ForeignKey back to Room explicitly and mark it as read_only=True
    # Assumes the ForeignKey field name in TilingRoomDetails model is 'room'.
    room = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TilingRoomDetails
        fields = [
            'id',
            'room',
            'stair_length',
            'stair_breadth',
            'number_of_steps',
            'landing_length',
            'landing_breadth',
            'number_of_landings',
            'has_metal_strip',
        ]
        read_only_fields = [
            'id',
            'room',
        ]

    def create(self, validated_data):
        print("--- TilingRoomDetailsSerializer create method called ---")
        print("Validated Data:", validated_data)

        room_instance = self.context.get('room_instance')
        if not room_instance:
            print("Error: Room context is missing for TilingRoomDetails creation.")
            raise serializers.ValidationError({'_detail': 'Room context is missing for TilingRoomDetails creation.'})
        print("Room Instance from context:", room_instance)

        instance = TilingRoomDetails(**validated_data)
        instance.room = room_instance
        instance.save()
        print("TilingRoomDetails instance created:", instance)

        return instance


class PaintingRoomDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaintingRoomDetails
        fields = [
            'id',
            'door_count',
            'door_area',
            'window_count',
            'window_area',
            'num_paint_coats',
            'surface_type',
        ]


class RoomSerializer(serializers.ModelSerializer):
    details_data = serializers.SerializerMethodField()
    project = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Room
        fields = [
            'id', 'project', 'name', 'room_type',
            'length', 'breadth', 'height',
            'floor_area', 'wall_area', 'total_area',
            'floor_area_with_waste', 'wall_area_with_waste', 'total_area_with_waste',
            'details_data',
        ]
        read_only_fields = [
            'floor_area', 'wall_area', 'total_area',
            'floor_area_with_waste', 'wall_area_with_waste', 'total_area_with_waste',
        ]

    def get_details_data(self, obj):
        if obj.details:
            if isinstance(obj.details, TilingRoomDetails):
                return TilingRoomDetailsSerializer(obj.details).data
            elif isinstance(obj.details, PaintingRoomDetails):
                 return PaintingRoomDetailsSerializer(obj.details).data
            else:
                return {"error": "Unknown details type"}
        return None

    def create(self, validated_data):
        print("--- RoomSerializer create method called ---")
        print("Validated Data:", validated_data)

        project_instance = self.context.get('project_instance')
        if not project_instance:
            print("Error: Project context is missing for Room creation.")
            raise serializers.ValidationError({'_detail': 'Project context is missing for Room creation.'})
        print("Project Instance from context:", project_instance)


        instance = Room(**validated_data)
        instance.project = project_instance
        instance.save()
        print("Room instance created:", instance)


        return instance
    
class MaterialDoesNotExist(Exception):
    pass
class MaterialMultipleObjectsReturned(Exception):
    pass


class ProjectMaterialSerializer(serializers.ModelSerializer):
    material = MaterialSerializer(read_only=True)

    material_name = serializers.CharField(write_only=True, max_length=255)

    # Changed to read_only as per previous discussion, calculated in view
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    unit = serializers.CharField(max_length=50, required=False, allow_null=True)

    # Changed to read_only as per previous discussion, calculated in view
    quantity_with_wastage = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    # Removed total_cost from fields and read_only_fields as it's not on ProjectMaterial model

    class Meta:
        model = ProjectMaterial
        fields = [
            'id', 'project', 'material',
            'material_name',
            'unit', # Now a CharField
            'quantity', 'quantity_with_wastage', # Read-only
        ]
        read_only_fields = [
            'id', 'project', 'material','name',
            'quantity', # Explicitly mark calculated fields as read-only
            'quantity_with_wastage',
        ]

    def create(self, validated_data):
        print("--- ProjectMaterialSerializer create method called ---")
        print("Validated Data (before pop):", validated_data)

        # Pop the material_name and unit string from validated_data
        material_name = validated_data.pop('material_name')
        unit_string = validated_data.pop('unit', '') # Get unit string, default to empty

        print("Material Name from payload:", material_name)
        print("Unit String from payload:", unit_string)
        print("Validated Data (after pop):", validated_data)


        # Look up the Material object based on the provided name
        try:
            print(f"Attempting to get Material with name: '{material_name}'") # <-- Added print
            # Use case-insensitive lookup for flexibility
            material = Material.objects.get(name__iexact=material_name)
            print("Material found:", material)
        except MaterialDoesNotExist: # Changed to MaterialDoesNotExist for explicit mock
            print(f"Error: Material with name '{material_name}' does not exist.")
            raise ValidationError({'material_name': [f"Material with name '{material_name}' does not exist."]})
        except MaterialMultipleObjectsReturned: # Changed for explicit mock
            print(f"Error: Multiple materials found with name '{material_name}'.")
            raise ValidationError({'material_name': [f"Multiple materials found with name '{material_name}'."]})
        except Exception as e: # Catch any other unexpected errors during material lookup
            print(f"An unexpected error occurred during material lookup: {e}")
            raise ValidationError({'_detail': f"An unexpected error occurred finding material: {e}"})


        # Set the material ForeignKey on the ProjectMaterial instance
        validated_data['material'] = material
        print("Material object added to validated_data:", validated_data['material'])


        # Set the 'name' and 'unit' fields on the ProjectMaterial instance
        validated_data.setdefault('name', material.name) # Use material name as default
        validated_data['unit'] = unit_string # Set the unit string from the payload
        print("Name and Unit set in validated_data:", validated_data['name'], validated_data['unit'])


        # Get project instance from context
        project_instance = self.context.get('project_instance')
        if not project_instance:
            print("Error: Project context is missing for ProjectMaterial creation.")
            raise serializers.ValidationError({'_detail': 'Project context is missing for ProjectMaterial creation.'})
        print("Project Instance from context:", project_instance)

        # Set the project ForeignKey on the ProjectMaterial instance
        validated_data['project'] = project_instance
        print("Project object added to validated_data:", validated_data['project'])


        # The quantity and quantity_with_wastage fields are NOT set here.
        # They will be calculated and set in the backend view logic AFTER the instance is created.

        # Create the ProjectMaterial instance
        print("Creating ProjectMaterial instance with data:", validated_data)
        instance = ProjectMaterial.objects.create(**validated_data)
        print("ProjectMaterial instance created:", instance)


        # NOTE: Calculations for quantity and quantity_with_wastage happen in the view AFTER this creation.
        # The view will need to retrieve this instance, perform calculations, and save it again.

        return instance

class WorkerSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Worker
        fields = '__all__'
        read_only_fields = ['total_cost']

    def create(self, validated_data):
        print("--- WorkerSerializer create method called ---")
        print("Validated Data:", validated_data)

        project_instance = self.context.get('project_instance')
        if not project_instance:
            print("Error: Project context is missing for Worker creation.")
            raise serializers.ValidationError({'_detail': 'Project context is missing for Worker creation.'})
        print("Project Instance from context:", project_instance)


        instance = Worker(**validated_data)
        instance.project = project_instance
        instance.save()
        print("Worker instance created:", instance)


        # Return the created instance
        return instance


class ProjectSerializer(serializers.ModelSerializer):
    rooms = RoomSerializer(many=True, read_only=True)
    materials = ProjectMaterialSerializer(many=True, read_only=True)
    workers = WorkerSerializer(many=True, read_only=True)

    user = serializers.PrimaryKeyRelatedField( read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = [
            'user',
            'estimate_number',
            'created_at', 'updated_at',
            'total_area', 'total_labor_cost',
             'cost_per_area', 'estimated_days',
        ]

    # Optional: Add a validate method to print data before validation
    def validate(self, data):
        print("--- ProjectSerializer validate method called ---")
        print("Data being validated:", data)
        print("----------------------------------------------")
        return data # Always return data from validate

class TileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tile
        fields = '__all__'
        read_only_fields = ['uploaded_at']

class ProjectStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ['status']
