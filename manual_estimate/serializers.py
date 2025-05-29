
# estimates/serializers.py

from rest_framework import serializers
from decimal import Decimal
from django.db.models import Sum # Keep this if you want to use it for aggregate calculations in serializer methods
from django.contrib.auth import get_user_model

# Import your models (assuming they are in the same app's models.py)
from .models import Customer, Estimate, MaterialItem, RoomArea # Assuming LabourItem is your model for 'labour'

# Get the active user model
User = get_user_model()

# --- Serializers for Nested Objects (remain mostly the same) ---

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'location', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        # 'id' is intentionally writable here for linking existing customers in the view


class MaterialItemSerializer(serializers.ModelSerializer):
    calculated_total_cost = serializers.SerializerMethodField()

    class Meta:
        model = MaterialItem
        fields = ['id', 'name', 'unit_price', 'quantity', 'total_price', 'calculated_total_cost', 'created_at', 'updated_at']
        read_only_fields = ['id', 'total_price', 'calculated_total_cost', 'created_at', 'updated_at']

    def get_calculated_total_cost(self, obj: MaterialItem) -> Decimal:
        unit_price = obj.unit_price if obj.unit_price is not None else Decimal('0.00')
        quantity = obj.quantity if obj.quantity is not None else Decimal('0.00')
        return round(unit_price * quantity, 2)


class RoomAreaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomArea
        fields = ['id', 'name', 'type', 'floor_area', 'wall_area', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# --- Main Estimate Serializer (Simplified create/update) ---

class EstimateSerializer(serializers.ModelSerializer):
    """
    Serializer for the Estimate model, including nested serializers for related items
    and handling creation/update of nested data.
    The complex saving logic is now handled in the view.
    """
    # Nested serializers for related items.
    # We still define them here because the serializer needs to know how to validate
    # the incoming nested data and how to serialize it for output.
    materials = MaterialItemSerializer(many=True, required=False)
    rooms = RoomAreaSerializer(many=True, required=False)
    customer = CustomerSerializer(required=False, allow_null=True)
    # Correctly map 'labour' (frontend) to 'labour_items' (model related_name)

    # Add calculated fields for total costs and grand total (still in serializer)
    total_material_cost = serializers.SerializerMethodField()
    total_labour_cost = serializers.SerializerMethodField()
    subtotal_cost = serializers.SerializerMethodField()
    grand_total = serializers.SerializerMethodField()
    total_area = serializers.SerializerMethodField()
    cost_per_area = serializers.SerializerMethodField()
    calculated_total_price = serializers.SerializerMethodField(method_name='get_grand_total') # Alias for grand_total


    class Meta:
        model = Estimate
        fields = [
            'id', 'user', 'customer', 'title', 'estimate_date', 'remarks',
            'transport_cost', 'estimated_days', 'wastage_percentage',
             # This is a model field for output, calculated in view
            'profit_type', # Model field for input/output
            'profit_value', # Model field for input/output
            'labour_cost_per_day', # Model field for input/output
            'total_area_sq_m',     # Model field for output, calculated in view

            'materials', # Nested items for input/output
            'rooms',
               # Frontend expects 'labour', mapped to 'labour_items'

            # Calculated fields (read-only, output only)
            'total_material_cost', 'total_labour_cost', 'subtotal_cost',
            'grand_total', 'total_area', 'cost_per_area', 'calculated_total_price',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'estimate_date', # auto_now_add/foreign key set by view
            'profit_per_sq_meter', # Calculated in view
            'total_area_sq_m',     # Calculated in view
            'total_material_cost', 'total_labour_cost', 'subtotal_cost', # SerializerMethodFields are read-only
            'grand_total', 'total_area', 'cost_per_area', 'calculated_total_price',
            'created_at', 'updated_at',
        ]

    # --- Methods to Calculate Read-Only Fields (remain in serializer) ---
    def get_total_material_cost(self, obj: Estimate) -> Decimal:
        total = sum((item.total_price if item.total_price is not None else Decimal('0.00')) for item in obj.materials.all()) if obj.materials.exists() else Decimal('0.00')
        return round(total, 2)

    def get_total_labour_cost(self, obj: Estimate) -> Decimal:
        # Access the property from the model, assuming it exists
        # or calculate here if not a model property:
        # return round(obj.labour_cost_per_day * obj.estimated_days, 2) if obj.labour_cost_per_day and obj.estimated_days else Decimal('0.00')
        return round(obj.total_labour_cost, 2) # Access model's @property


    def get_subtotal_cost(self, obj: Estimate) -> Decimal:
        return round(self.get_total_material_cost(obj) + self.get_total_labour_cost(obj), 2)

    def get_grand_total(self, obj: Estimate) -> Decimal:
        subtotal = self.get_subtotal_cost(obj)
        transport = obj.transport_cost if obj.transport_cost is not None else Decimal('0.00')
        # Access model's @property for profit if it exists
        
        return round(subtotal + transport , 2)

    def get_total_area(self, obj: Estimate) -> Decimal:
        # Access the concrete field on the model, as it's updated by the view/service
        return round(obj.total_area_sq_m, 2)

    def get_cost_per_area(self, obj: Estimate) -> Decimal:
        total_area = self.get_total_area(obj)
        grand_total = self.get_grand_total(obj)
        if total_area > Decimal('0.00'):
            return round(grand_total / total_area, 2)
        return Decimal('0.00')

    # --- SIMPLIFIED create and update methods ---
    # These methods now ONLY handle the immediate creation/update of the Estimate instance
    # and pop nested data for the view to handle.
    def create(self, validated_data):
        # We pop nested data here so it's not passed to Estimate.objects.create()
        # The view will handle saving these related items.
        validated_data.pop('materials', [])
        validated_data.pop('rooms', [])
        validated_data.pop('customer', None) # Pop, the view will handle customer linking

        # Ensure user is associated
        if 'user' not in validated_data:
             raise serializers.ValidationError({"user": "User must be provided to create an estimate."})

        # Create the Estimate instance
        estimate = Estimate.objects.create(**validated_data)
        return estimate

    def update(self, instance: Estimate, validated_data):
        # We pop nested data here so it's not passed to the instance update
        # The view will handle saving these related items.
        validated_data.pop('materials', None)
        validated_data.pop('rooms', None)
        validated_data.pop('customer', None) # Pop, the view will handle customer linking

        # Update scalar fields on the Estimate instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save() # Save the estimate instance

        return instance
# from rest_framework import serializers
# # Import transaction for atomic operations when saving nested data
# from django.db import transaction
# from django.db.models import Sum # Not strictly needed if calculating in methods, but useful for context
# from decimal import Decimal


# from .models import Customer, Estimate, MaterialItem, RoomArea
# from django.contrib.auth import get_user_model

# # Get the active user model (your CustomUser)
# User = get_user_model()

# # --- Serializers for Nested Objects ---

# class CustomerSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Customer
#         # Include the fields you want to expose for customers
#         # Include 'id' so frontend can send it to link to an existing customer
#         fields = ['id', 'name', 'phone', 'location', 'created_at', 'updated_at']
#         # User is set by the view or the parent serializer's create method
#         # id is read-only when creating a NEW customer, but allowed for update/lookup
#         read_only_fields = ['created_at', 'updated_at'] # Make id writable if needed for linking


# class MaterialItemSerializer(serializers.ModelSerializer):
#     # total_price is a model field, calculated in the model's save method or similar
#     # Add a calculated field for total_cost (unit_price * quantity) if not already in model
#     # Based on your original view code, total_price seems to be calculated already.
#     # If total_cost is intended to be the same as total_price, you can remove one.
#     # Assuming total_cost is the calculated field for display
#     calculated_total_cost = serializers.SerializerMethodField()

#     class Meta:
#         model = MaterialItem
#         # Ensure fields match your MaterialItem model
#         fields = ['id', 'name', 'unit_price', 'quantity','total_price', 'calculated_total_cost', 'created_at', 'updated_at'] # Added notes, unit to match model
#         # total_price is likely set by model's save or a custom create in this serializer if quantity/price change
#         # calculated_total_cost is calculated here
#         read_only_fields = ['id', 'total_price', 'calculated_total_cost', 'created_at', 'updated_at']

#     def get_calculated_total_cost(self, obj: MaterialItem) -> Decimal:
#         """Calculates total cost for the material item (unit_price * quantity)."""
#         # Use Decimal for calculation to avoid floating point issues
#         unit_price = obj.unit_price if obj.unit_price is not None else Decimal('0.00')
#         quantity = obj.quantity if obj.quantity is not None else Decimal('0.00') # Assuming quantity can be Decimal too
#         # If quantity is int, cast it: quantity = Decimal(obj.quantity) if obj.quantity is not None else Decimal('0.00')
#         return round(unit_price * quantity, 2)
#         # If obj.total_price in the model is already correct, you could just return obj.total_price


# class RoomAreaSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = RoomArea
#         # Ensure fields match your RoomArea model
#         fields = ['id', 'name', 'type', 'floor_area', 'wall_area', 'created_at', 'updated_at'] # Added notes to match model
#         read_only_fields = ['id', 'created_at', 'updated_at']



# # --- Main Estimate Serializer (Handles Nested Data) ---

# class EstimateSerializer(serializers.ModelSerializer):
#     """
#     Serializer for the Estimate model, including nested serializers for related items
#     and handling creation/update of nested data.
#     """
#     # Nested serializers for related items.
#     # required=False allows omitting the field in POST/PUT.
#     # allow_null=True allows explicitly setting the customer relation to null.
#     materials = MaterialItemSerializer(many=True, required=False)
#     rooms = RoomAreaSerializer(many=True, required=False)
#     # Use a nested serializer for reading customer data
#     # For writing, we'll handle the customer ID or nested data manually in create/update
#     customer = CustomerSerializer(required=False, allow_null=True)

#     # Add calculated fields for total costs and grand total
#     # These match the calculations done in your original view/PDF logic
#     total_material_cost = serializers.SerializerMethodField()
#     total_labour_cost = serializers.SerializerMethodField()
#     subtotal_cost = serializers.SerializerMethodField() # Materials + Labour
#     grand_total = serializers.SerializerMethodField() # Subtotal + Transport + Profit (Matching your view's apparent logic)
#     total_area = serializers.SerializerMethodField() # Total tiled surface area (floor + wall)
#     cost_per_area = serializers.SerializerMethodField() # Grand Total / Total Area
#     # calculated_total_price - Seems redundant if grand_total exists and means the same.
#     # Let's implement it as grand_total or remove if it's not needed.
#     # Assuming it's the same as grand_total for now, you can remove one.
#     calculated_total_price = serializers.SerializerMethodField(method_name='get_grand_total')


#     class Meta:
#         model = Estimate
#         # Include all fields from the Estimate model AND the nested/calculated fields
#         fields = [
#             'id', 'user', 'customer', 'title', 'estimate_date', 'remarks','profit_type',
#             'transport_cost', 'estimated_days', 'wastage_percentage', # Fields from Estimate model
#             'materials', 'rooms', 'labour', # Nested fields
#             # Calculated fields (read-only)
#             'total_material_cost', 'total_labour_cost', 'subtotal_cost',
#             'grand_total', 'total_area', 'cost_per_area', 'calculated_total_price', # Added calculated fields
#             'created_at', 'updated_at', # Timestamp fields
#         ]
#         # 'user' is set by the view's perform_create/update
#         # Calculated fields are read-only
#         # Timestamps are usually read-only
#         read_only_fields = [
#             'id', 'user', 'estimate_date', # estimate_date might be auto_now_add
#             'total_material_cost', 'total_labour_cost', 'subtotal_cost',
#             'grand_total', 'total_area', 'cost_per_area', 'calculated_total_price',
#             'created_at', 'updated_at',
#         ]


#     # --- Methods to Calculate Read-Only Fields ---
#     # Ensure these use Decimal for accuracy and match your view/PDF calculations

#     def get_total_material_cost(self, obj: Estimate) -> Decimal:
#         """Calculates the total cost of all material items for the estimate."""
#         # Access related materials via the 'materials' related_name
#         # Use MaterialItem's total_price field (assuming it's accurate or calculated by the model)
#         total = sum((item.total_price if item.total_price is not None else Decimal('0.00')) for item in obj.materials.all()) if obj.materials.exists() else Decimal('0.00')
#         return round(total, 2)




#     def get_subtotal_cost(self, obj: Estimate) -> Decimal:
#         """Calculates the subtotal cost (Materials + Labour)."""
#         return round(self.get_total_material_cost(obj) + self.get_total_labour_cost(obj), 2)

#     def get_grand_total(self, obj: Estimate) -> Decimal:
#         """Calculates the grand total including materials, labour, transport, and profit."""
#         # Match the logic from your view/PDF generation context
#         subtotal = self.get_subtotal_cost(obj)
#         transport = obj.transport_cost if obj.transport_cost is not None else Decimal('0.00')
#         profit = obj.profit if obj.profit is not None else Decimal('0.00')
#         # NOTE: Your view/PDF calculation was a bit unclear on where profit fits exactly,
#         # sometimes adding to labour, sometimes seemingly separate before grand total.
#         # A common approach is Subtotal (Materials + Labour) + Transport + Profit.
#         return round(subtotal + transport + profit, 2)

#     # If calculated_total_price is distinct from grand_total, define its logic here.
#     # Otherwise, the method_name='get_grand_total' makes them the same read-only field.
#     def get_calculated_total_price(self, obj: Estimate) -> Decimal:
#         """Define custom logic if different from grand_total."""
#         # Example: return self.get_subtotal_cost(obj) # Or some other calculation
#         pass # If method_name is used, this method body is not executed


#     def get_total_area(self, obj: Estimate) -> Decimal:
#         """Calculates the total tiled surface area (floor + wall) for the estimate."""
#         total_floor = sum((room.floor_area if room.floor_area is not None else Decimal('0.00')) for room in obj.rooms.all()) if obj.rooms.exists() else Decimal('0.00')
#         total_wall = sum((room.wall_area if room.wall_area is not None else Decimal('0.00')) for room in obj.rooms.all()) if obj.rooms.exists() else Decimal('0.00')
#         return round(total_floor + total_wall, 2)

#     def get_cost_per_area(self, obj: Estimate) -> Decimal:
#         """Calculates the grand total cost per total tiled surface area."""
#         total_area = self.get_total_area(obj)
#         grand_total = self.get_grand_total(obj)
#         if total_area > Decimal('0.00'): 
#             return round(grand_total / total_area, 2)
#         return Decimal('0.00')


#     # --- Custom Create Method to Handle Nested Data ---
#     # Use transaction.atomic to ensure all changes are saved or rolled back together
#     @transaction.atomic
#     def create(self, validated_data):
#         """
#         Handle creation of Estimate and its related items (Customer, Materials, Rooms, Labour).
#         The 'user' is expected to be in validated_data because it's passed from the view's serializer.save(user=...).
#         """
#         print("--- EstimateSerializer create method started ---")

#         # Pop nested data lists and customer data
#         materials_data = validated_data.pop('materials', [])
#         rooms_data = validated_data.pop('rooms', [])
#         customer_data = validated_data.pop('customer', None) # Pop nested customer data if sent

#         print("Materials data popped:", materials_data)
#         print("Rooms data popped:", rooms_data)
#         print("Customer data popped:", customer_data)
#         print("Remaining validated_data for Estimate:", validated_data)

#         # --- Handle Customer creation or association ---
#         customer_instance = None
#         if customer_data:
#             print("Customer data provided. Attempting to create or link customer...")
#             user = validated_data.get('user') # Get user from validated_data

#             if 'id' in customer_data and customer_data['id'] is not None:
#                  # If customer data includes an ID, try to link to an existing customer
#                  customer_id = customer_data['id']
#                  try:
#                      # Ensure the existing customer belongs to the current user
#                      customer_instance = Customer.objects.get(id=customer_id, user=user)
#                      print(f"Linked to existing customer with ID: {customer_instance.id}")
#                      # Optional: Update the existing customer's details if other fields were sent
#                      # customer_serializer = CustomerSerializer(instance=customer_instance, data=customer_data, partial=True)
#                      # customer_serializer.is_valid(raise_exception=True)
#                      # customer_serializer.save()
#                      # print(f"Existing customer {customer_instance.id} details updated.")

#                  except Customer.DoesNotExist:
#                      raise serializers.ValidationError({"customer": f"Invalid customer ID '{customer_id}' or customer does not belong to this user."})
#             else:
#                 # If no customer ID is provided, create a new customer
#                 print("No customer ID provided in data. Creating a new customer.")
#                 try:
#                     # Ensure the new customer is associated with the user
#                     customer_serializer = CustomerSerializer(data=customer_data)
#                     customer_serializer.is_valid(raise_exception=True)
#                     customer_instance = customer_serializer.save(user=user) # Associate new customer with user
#                     print(f"New customer created with ID: {customer_instance.id}")
#                 except Exception as e:
#                      print(f"!!! Error creating new Customer: {e} !!!")
#                      raise serializers.ValidationError({"customer": f"Could not create new customer: {e}"})


#         # Create the parent Estimate instance
#         # Pass the customer_instance and remaining validated_data (including user)
#         try:
#             # Pass customer_instance=customer_instance explicitly if it was found/created
#             estimate = Estimate.objects.create(customer=customer_instance, **validated_data)
#             print(f"Estimate instance created with ID: {estimate.id}")
#         except Exception as e:
#             print(f"!!! Error creating Estimate instance: {e} !!!")
#             # If estimate creation fails, the transaction will roll back the customer creation too
#             raise serializers.ValidationError({"detail": f"Could not create estimate: {e}"})


#         # --- Create related nested items ---
#         # Ensure each nested item is linked to the created estimate instance
#         if materials_data:
#             print("Materials data provided. Creating MaterialItem objects...")
#             for material_data in materials_data:
#                 try:
#                     # Use the nested serializer for validation if needed, or create directly
#                     # material_serializer = MaterialItemSerializer(data=material_data)
#                     # material_serializer.is_valid(raise_exception=True)
#                     # MaterialItem.objects.create(estimate=estimate, **material_serializer.validated_data) # Link to estimate
#                      MaterialItem.objects.create(estimate=estimate, **material_data)
#                 except Exception as e:
#                      print(f"!!! Error creating MaterialItem: {e} !!! Data: {material_data}")
#                      raise serializers.ValidationError({"materials": f"Could not create MaterialItem: {e}"})


#         if rooms_data:
#             print("Rooms data provided. Creating RoomArea objects...")
#             for room_data in rooms_data:
#                  try:
#                      RoomArea.objects.create(estimate=estimate, **room_data) # Link to estimate
#                  except Exception as e:
#                      print(f"!!! Error creating RoomArea: {e} !!! Data: {room_data}")
#                      raise serializers.ValidationError({"rooms": f"Could not create RoomArea: {e}"})


       
#         print("--- EstimateSerializer create method finished ---")
#         return estimate

#     # --- Custom Update Method to Handle Nested Data ---
#     @transaction.atomic # Use atomic transaction for update as well
#     def update(self, instance: Estimate, validated_data):
#         """
#         Handle update of Estimate and its related items (Customer, Materials, Rooms, Labour).
#         This method implements a delete-and-recreate strategy for nested items for simplicity.
#         Handles linking/updating the customer.
#         """
#         print(f"--- EstimateSerializer update method started for Estimate ID: {instance.id} ---")
#         print("Received validated_data for update:", validated_data)

#         # Pop nested lists and customer data
#         materials_data = validated_data.pop('materials', None)
#         rooms_data = validated_data.pop('rooms', None)
#         customer_data = validated_data.pop('customer', None)

#         # --- Handle Customer update or linking ---
#         if customer_data is not None: # Process only if customer data was sent in the request
#              print("Customer data provided for update.")
#              user = instance.user # Get user from the estimate instance

#              if 'id' in customer_data and customer_data['id'] is not None:
#                  # If customer data includes an ID, try to link to an existing customer
#                  customer_id = customer_data['id']
#                  try:
#                      # Ensure the existing customer belongs to the current user
#                      customer_instance = Customer.objects.get(id=customer_id, user=user)
#                      print(f"Linking Estimate {instance.id} to existing customer with ID: {customer_instance.id}")
#                      instance.customer = customer_instance # Update the Estimate's customer field
#                      # Optional: Update the existing customer's details if other fields were sent
#                      # update_customer_serializer = CustomerSerializer(instance=customer_instance, data=customer_data, partial=True)
#                      # update_customer_serializer.is_valid(raise_exception=True)
#                      # update_customer_serializer.save() # Save updates to the customer instance
#                      # print(f"Existing customer {customer_instance.id} details updated.")

#                  except Customer.DoesNotExist:
#                      raise serializers.ValidationError({"customer": f"Invalid customer ID '{customer_id}' or customer does not belong to this user."})
#              else:
#                  # If no customer ID is provided, assume they want to update the *currently linked* customer's details
#                  # or create a new one if none was linked.
#                  if instance.customer:
#                      print(f"No customer ID provided. Updating current customer with ID: {instance.customer.id}")
#                       # Update existing linked customer
#                      try:
#                          update_customer_serializer = CustomerSerializer(instance=instance.customer, data=customer_data, partial=True) # Use partial=True for partial updates
#                          update_customer_serializer.is_valid(raise_exception=True)
#                          update_customer_serializer.save() # Save updates to the customer instance
#                          print("Existing linked customer updated.")
#                      except Exception as e:
#                           print(f"!!! Error updating existing linked Customer: {e} !!!")
#                           raise serializers.ValidationError({"customer": f"Could not update linked customer: {e}"})

#                  else:
#                      print("No customer ID provided and no existing customer linked. Creating a new customer...")
#                      # Create a new customer and link it
#                      try:
#                          new_customer_serializer = CustomerSerializer(data=customer_data)
#                          new_customer_serializer.is_valid(raise_exception=True)
#                          customer_instance = new_customer_serializer.save(user=user) # Associate new customer with user
#                          instance.customer = customer_instance # Link the new customer to the estimate
#                          print(f"New customer created/linked with ID: {customer_instance.id}")
#                      except Exception as e:
#                          print(f"!!! Error creating new Customer during update: {e} !!!")
#                          raise serializers.ValidationError({"customer": f"Could not create new customer: {e}"})
#         # If customer_data is None, it means the customer field was omitted in the request,
#         # the current customer link remains unchanged. If you want to unlink the customer,
#         # the frontend must send customer: null. This is handled by allow_null=True on the field.


#         # Update parent Estimate fields (excluding nested fields already popped)
#         # Ensure 'user' is not updated here.
#         # If user is explicitly passed in validated_data despite being read-only,
#         # you might need to pop it here: validated_data.pop('user', None)
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         print("Estimate instance fields updated.")

#         # Save the parent instance to apply its own field changes and customer link update
#         instance.save()
#         print("Estimate instance saved after field and customer updates.")


#         # --- Update Nested Items (Delete and Recreate Strategy) ---
#         # This is a common strategy for nested lists unless you need granular updates by ID.
#         # Only process if the nested list was actually sent in the request (data is not None).

#         # Update Material Items
#         if materials_data is not None:
#             print("Materials data provided for update. Deleting existing and recreating...")
#             try:
#                 instance.materials.all().delete() # Delete all existing materials for this estimate
#                 print("Existing MaterialItems deleted.")
#                 for material_data in materials_data:
#                     # You could validate data here using the nested serializer if needed
#                     # material_serializer = MaterialItemSerializer(data=material_data)
#                     # material_serializer.is_valid(raise_exception=True)
#                     MaterialItem.objects.create(estimate=instance, **material_data) # Create new ones linked to estimate
#                 print("All new MaterialItems created.")
#             except Exception as e:
#                 print(f"!!! Error updating MaterialItems: {e} !!!")
#                 raise serializers.ValidationError({"materials": f"Could not update MaterialItems: {e}"}) # Raise validation error


#         # Update Room Areas
#         if rooms_data is not None:
#             print("Rooms data provided for update. Deleting existing and recreating...")
#             try:
#                 instance.rooms.all().delete() # Delete all existing rooms for this estimate
#                 print("Existing RoomAreas deleted.")
#                 for room_data in rooms_data:
#                     RoomArea.objects.create(estimate=instance, **room_data) # Create new ones linked to estimate
#                 print("All new RoomAreas created.")
#             except Exception as e:
#                 print(f"!!! Error updating RoomAreas: {e} !!!")
#                 raise serializers.ValidationError({"rooms": f"Could not update RoomAreas: {e}"}) # Raise validation error

#         # Update Labour Items
        
#         return instance
    


    # # serializers.py in your Django app (e.g., 'estimates')

# from rest_framework import serializers
# from .models import Customer, Estimate, MaterialItem, RoomArea, LabourItem
# from django.contrib.auth import get_user_model

# User = get_user_model()

# class CustomerSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Customer
#         fields = ['id', 'name', 'phone', 'location', 'created_at', 'updated_at']
#         # User will be set by the view or the parent serializer's create method
#         read_only_fields = ['id', 'created_at', 'updated_at']


# class MaterialItemSerializer(serializers.ModelSerializer):
#     # Add a calculated field for total_cost
#     total_cost = serializers.SerializerMethodField()

#     class Meta:
#         model = MaterialItem
#         fields = ['id', 'name', 'unit_price', 'quantity','total_price', 'total_cost', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at'] # total_cost is calculated

    


# class RoomAreaSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = RoomArea
#         fields = ['id', 'name', 'type', 'floor_area', 'wall_area', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'created_at', 'updated_at']


# class LabourItemSerializer(serializers.ModelSerializer):
#     # Add a calculated field for total_cost
#     total_cost = serializers.SerializerMethodField()

#     class Meta:
#         model = LabourItem
#         fields = ['id', 'role', 'count', 'rate', 'rate_type', 'total_cost', 'created_at', 'updated_at']
#         read_only_fields = ['id', 'total_cost', 'created_at', 'updated_at'] # total_cost is calculated

#     def get_total_cost(self, obj):
#         """Calculates the total cost for the labour item."""
#         try:
#             # Ensure count and rate are treated as numbers
#             count = int(obj.count) if obj.count is not None else 0
#             rate = float(obj.rate) if obj.rate is not None else 0
#             return round(count * rate, 2) # Round to 2 decimal places
#         except (ValueError, TypeError):
#             return 0.00 # Return 0 if calculation is not possible


# class EstimateSerializer(serializers.ModelSerializer):
#     """
#     Serializer for the Estimate model, including nested serializers for related items.
#     """
#     # Use nested serializers to include related items in the Estimate representation
#     materials = MaterialItemSerializer(many=True, required=False)
#     rooms = RoomAreaSerializer(many=True, required=False)
#     labour = LabourItemSerializer(many=True, required=False)
#     customer = CustomerSerializer(required=False, allow_null=True) # Include customer details

#     # Add calculated fields for total costs and grand total
#     total_material_cost = serializers.SerializerMethodField()
#     total_labour_cost = serializers.SerializerMethodField()
#     grand_total = serializers.SerializerMethodField()
#     per_square_meter_cost = serializers.SerializerMethodField()
#     calculated_total_price = serializers.SerializerMethodField()

#     class Meta:
#         model = Estimate
#         fields = [
#             'id', 'user', 'customer', 'title', 'estimate_date',
#             'transport_cost', 'remarks','profit',
#             'materials', 'rooms', 'labour','per_square_meter_cost', 
#             'total_material_cost', 'total_labour_cost', 'grand_total',
#             'created_at', 'updated_at','estimated_days','calculated_total_price'
#         ]
#         # 'user' is set by the view's perform_create, so it's read-only here
#         read_only_fields = [
#             'id', 'user', 'estimate_date',
#             'total_material_cost', 'total_labour_cost', 'grand_total',
#             'created_at', 'updated_at','per_square_meter_cost',
#         ]


#     def get_total_material_cost(self, obj):
#         """Calculates the total cost of all material items for the estimate."""
#         # Access related materials via the 'materials' related_name
#         total = sum(item.unit_price * item.quantity for item in obj.materials.all())
#         return round(total, 2) if total is not None else 0.00

#     def get_total_labour_cost(self, obj):
#         """Calculates the total cost of all labour items for the estimate."""
#          # Access related labour via the 'labour' related_name
#         total = sum((item.count if item.count is not None else 0) * (item.rate if item.rate is not None else 0) for item in obj.labour.all())
#         return round(total, 2) if total is not None else 0.00

#     def get_grand_total(self, obj):
#         """Calculates the grand total including materials, labour, and transport."""
#         total_materials = self.get_total_material_cost(obj)
#         total_labour = self.get_total_labour_cost(obj)
#         transport = float(obj.transport_cost) if obj.transport_cost is not None else 0
#         profit = float(obj.profit) if obj.profit is not None else 0 
#         return round(total_materials + total_labour + transport,profit, 2) if total_materials is not None and total_labour is not None else 0.00


#     def create(self, validated_data):
#         """
#         Handle creation of Estimate and its related items.
#         The 'user' is expected to be in validated_data because it's passed from the view.
#         """
#         print("--- EstimateSerializer create method started ---")
#         print("Received validated_data:", validated_data)

#         # Pop nested data lists and customer data
#         materials_data = validated_data.pop('materials', [])
#         rooms_data = validated_data.pop('rooms', [])
#         labour_data = validated_data.pop('labour', [])
#         customer_data = validated_data.pop('customer', None)

#         print("Materials data popped:", materials_data)
#         print("Rooms data popped:", rooms_data)
#         print("Labour data popped:", labour_data)
#         print("Customer data popped:", customer_data)
#         print("Remaining validated_data for Estimate:", validated_data)


#         # Create the Estimate instance using validated_data (which includes the user)
#         # The user is automatically in validated_data from the view's serializer.save(user=...)
#         try:
#             estimate = Estimate.objects.create(**validated_data)
#             print(f"Estimate instance created with ID: {estimate.id}")
#         except Exception as e:
#             print(f"!!! Error creating Estimate instance: {e} !!!")
#             raise # Re-raise the exception after printing


#         # Handle customer creation or association
#         if customer_data:
#             print("Customer data provided. Attempting to create or link customer...")
#             try:
#                 # Get the user from the estimate instance (which was set from validated_data)
#                 user = estimate.user
#                 # You might want to check if a customer with this name/phone already exists for this user
#                 # and either link to the existing one or create a new one.
#                 # For simplicity here, we'll create a new customer if data is provided.
#                 # FIX: Ensure user is associated with the Customer object
#                 customer = Customer.objects.create(user=user, **customer_data)
#                 estimate.customer = customer
#                 estimate.save() # Save estimate to link the customer
#                 print(f"Customer created/linked with ID: {customer.id}")
#             except Exception as e:
#                  print(f"!!! Error creating or linking Customer: {e} !!!")
#                  # Optionally delete the estimate if customer creation failed
#                  # estimate.delete()
#                  raise # Re-raise the exception


#         # Create related MaterialItems
#         if materials_data:
#             print("Materials data provided. Creating MaterialItem objects...")
#             for material_data in materials_data:
#                 try:
#                     print("Creating MaterialItem with data:", material_data)
#                     MaterialItem.objects.create(estimate=estimate, **material_data)
#                     print("MaterialItem created successfully.")
#                 except Exception as e:
#                     print(f"!!! Error creating MaterialItem: {e} !!! Data: {material_data}")
#                     # Decide how to handle errors here - continue or stop?
#                     # For now, we'll print and continue, but you might want to raise an exception
#                     # raise

#         # Create related RoomAreas
#         if rooms_data:
#             print("Rooms data provided. Creating RoomArea objects...")
#             for room_data in rooms_data:
#                  try:
#                     print("Creating RoomArea with data:", room_data)
#                     RoomArea.objects.create(estimate=estimate, **room_data)
#                     print("RoomArea created successfully.")
#                  except Exception as e:
#                     print(f"!!! Error creating RoomArea: {e} !!! Data: {room_data}")
#                     # raise

#         # Create related LabourItems
#         if labour_data:
#             print("Labour data provided. Creating LabourItem objects...")
#             for labour_data in labour_data:
#                  try:
#                     print("Creating LabourItem with data:", labour_data)
#                     LabourItem.objects.create(estimate=estimate, **labour_data)
#                     print("LabourItem created successfully.")
#                  except Exception as e:
#                     print(f"!!! Error creating LabourItem: {e} !!! Data: {labour_data}")
#                     # raise

#         print("--- EstimateSerializer create method finished ---")
#         return estimate

#     def update(self, instance, validated_data):
#         """
#         Handle update of Estimate and its related items.
#         This is more complex as it involves deleting/creating/updating nested items.
#         A common strategy is to delete existing items and recreate them,
#         or implement more granular update logic.
#         For simplicity, this example shows deleting and recreating nested items.
#         A production app might need more sophisticated update logic to avoid data loss or performance issues.
#         """
#         print("--- EstimateSerializer update method started ---")
#         print("Received validated_data for update:", validated_data)

#         materials_data = validated_data.pop('materials', None)
#         rooms_data = validated_data.pop('rooms', None)
#         labour_data = validated_data.pop('labour', None)
#         customer_data = validated_data.pop('customer', None)

#         # Update Estimate fields
#         # Ensure 'user' is not updated here if it's in validated_data,
#         # though it should be read-only in the serializer Meta class.
#         # If user is explicitly passed in validated_data despite being read-only,
#         # you might need to pop it here: validated_data.pop('user', None)
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         print("Estimate instance fields updated.")

#         # Handle customer update or creation
#         if customer_data is not None:
#              print("Customer data provided for update.")
#              if instance.customer:
#                  print(f"Updating existing customer with ID: {instance.customer.id}")
#                  # Update existing customer (simple update, might need more logic)
#                  try:
#                      for attr, value in customer_data.items():
#                          setattr(instance.customer, attr, value)
#                      instance.customer.save()
#                      print("Existing customer updated.")
#                  except Exception as e:
#                      print(f"!!! Error updating existing Customer: {e} !!!")
#                      raise
#              else:
#                  print("No existing customer linked. Creating a new customer...")
#                  # Create a new customer and link it
#                  try:
#                      user = instance.user # Get user from the estimate instance
#                      customer = Customer.objects.create(user=user, **customer_data)
#                      instance.customer = customer
#                      print(f"New customer created/linked with ID: {customer.id}")
#                  except Exception as e:
#                      print(f"!!! Error creating new Customer during update: {e} !!!")
#                      raise

#         instance.save() # Save the estimate instance after updating its fields and customer link
#         print("Estimate instance saved after potential customer update.")

#         # Update related MaterialItems (delete and recreate strategy)
#         if materials_data is not None: # Only update if materials data is provided in the request
#             print("Materials data provided for update. Deleting existing and recreating...")
#             try:
#                 instance.materials.all().delete() # Delete all existing materials
#                 print("Existing MaterialItems deleted.")
#                 for material_data in materials_data:
#                     print("Creating new MaterialItem with data:", material_data)
#                     MaterialItem.objects.create(estimate=instance, **material_data)
#                     print("New MaterialItem created.")
#                 print("All new MaterialItems created.")
#             except Exception as e:
#                 print(f"!!! Error updating MaterialItems: {e} !!!")
#                 raise


#         # Update related RoomAreas (delete and recreate strategy)
#         if rooms_data is not None: # Only update if rooms data is provided in the request
#             print("Rooms data provided for update. Deleting existing and recreating...")
#             try:
#                 instance.rooms.all().delete() # Delete all existing rooms
#                 print("Existing RoomAreas deleted.")
#                 for room_data in rooms_data:
#                     print("Creating new RoomArea with data:", room_data)
#                     RoomArea.objects.create(estimate=instance, **room_data)
#                     print("New RoomArea created.")
#                 print("All new RoomAreas created.")
#             except Exception as e:
#                 print(f"!!! Error updating RoomAreas: {e} !!!")
#                 raise

#         # Update related LabourItems (delete and recreate strategy)
#         if labour_data is not None: # Only update if labour data is provided in the request
#             print("Labour data provided for update. Deleting existing and recreating...")
#             try:
#                 instance.labour.all().delete() # Delete all existing labour items
#                 print("Existing LabourItems deleted.")
#                 for labour_data in labour_data:
#                     print("Creating new LabourItem with data:", labour_data)
#                     LabourItem.objects.create(estimate=instance, **labour_data)
#                     print("New LabourItem created.")
#                 print("All new LabourItems created.")
#             except Exception as e:
#                 print(f"!!! Error updating LabourItems: {e} !!!")
#                 raise

#         print("--- EstimateSerializer update method finished ---")
#         return instance



# your_project/estimates/serializers.py