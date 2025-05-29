# estimates/services.py

from decimal import Decimal
from django.db import transaction
from django.db.models import Sum # If you need aggregates for calculations

from .models import Estimate, Customer, MaterialItem, RoomArea
from django.conf import settings # For SQ_YARD_TO_SQ_METER_CONVERSION if defined there

# Assuming SQ_YARD_TO_SQ_METER_CONVERSION is defined in your settings or a constants file
try:
    SQ_YARD_TO_SQ_METER_CONVERSION = settings.SQ_YARD_TO_SQ_METER_CONVERSION
except AttributeError:
    # Fallback or define directly if not in settings
    SQ_YARD_TO_SQ_METER_CONVERSION = Decimal('0.836127')


def calculate_and_update_estimate_fields(estimate_instance: Estimate):
    """
    Calculates derived fields for an Estimate instance (total_area_sq_m, profit_per_sq_meter)
    and saves them back to the model.
    This should be called *after* nested RoomArea objects have been updated.
    """
    print(f"--- Calculating and updating fields for Estimate ID: {estimate_instance.id} ---")

    # 1. Recalculate total_area_sq_m
    total_floor_area_sq_m = sum(room.floor_area for room in estimate_instance.rooms.all())
    total_wall_area_sq_m = sum(room.wall_area for room in estimate_instance.rooms.all())
    # Assuming total_area_sq_m only accounts for floor_area for profit calc, adjust if wall_area is included
    estimate_instance.total_area_sq_m = total_floor_area_sq_m + total_wall_area_sq_m
    print(f"Calculated total_area_sq_m: {estimate_instance.total_area_sq_m}")


    # 2. Recalculate profit_per_sq_meter
    total_labour_c = Decimal(0)
    calculated_profit_per_sq_m = Decimal(0)
    profit_type_input = estimate_instance.profit_type
    profit_value_input = estimate_instance.profit_value
    total_floor_area = sum(room.floor_area for room in estimate_instance.rooms.all()) if estimate_instance.rooms.exists() else Decimal('0.00')
    total_wall_area = sum(room.wall_area for room in estimate_instance.rooms.all()) if estimate_instance.rooms.exists() else Decimal('0.00')
    total_area = total_wall_area + total_floor_area
    if profit_type_input == 'fixed_amount':
        if estimate_instance.total_area_sq_m > 0:
            total_labour_c = profit_value_input
            calculated_profit_per_sq_m = profit_value_input / estimate_instance.total_area_sq_m
        else:
            # If total_area_sq_m is 0 for a fixed_amount profit, profit_per_sq_meter should be 0
            calculated_profit_per_sq_m = Decimal(0)
    elif profit_type_input == 'per_sq_meter':
        
        calculated_profit_per_sq_m = profit_value_input
        total_labour_c = total_area * calculated_profit_per_sq_m
    elif profit_type_input == 'per_sq_yard':
        calculated_profit_per_sq_m = profit_value_input / SQ_YARD_TO_SQ_METER_CONVERSION
        total_labour_c = total_area * calculated_profit_per_sq_m

    estimate_instance.labour_per_sq_meter = calculated_profit_per_sq_m
    print(f"Calculated profit_per_sq_meter: {estimate_instance.labour_per_sq_meter}")
    estimate_instance.total_labour_cost = total_labour_c
    # 3. Save the updated estimate instance
    estimate_instance.save(update_fields=[
        'total_area_sq_m',
        'labour_per_sq_meter',
        'total_labour_cost',
        # Include any other fields that are modified by this function if they were not explicitly updated earlier
    ])
    print("Estimate instance fields updated and saved.")


@transaction.atomic
def create_estimate_and_nested_items(user, validated_data):
    """
    Service function to create an Estimate and all its nested related items.
    Handles customer linking/creation and calculation of derived fields.
    """
    print("--- create_estimate_and_nested_items service started ---")

    materials_data = validated_data.pop('materials', [])
    rooms_data = validated_data.pop('rooms', [])

    customer_data = validated_data.pop('customer', None)

    # --- Handle Customer creation or association ---
    customer_instance = None
    if customer_data:
        if 'id' in customer_data and customer_data['id'] is not None:
            # Link to existing customer
            try:
                # Ensure the existing customer belongs to the current user
                customer_instance = Customer.objects.get(id=customer_data['id'], user=user)
                # Optional: Update existing customer details if needed
                # for attr, value in customer_data.items():
                #     setattr(customer_instance, attr, value)
                # customer_instance.save()
            except Customer.DoesNotExist:
                raise ValueError(f"Customer with ID '{customer_data['id']}' not found or does not belong to this user.")
        else:
            # Create a new customer
            customer_instance = Customer.objects.create(user=user, **customer_data)
    validated_data['customer'] = customer_instance # Set the customer for the estimate

    # Set the user for the estimate
    validated_data['user'] = user

    # Create the Estimate instance (scalar fields first)
    estimate = Estimate.objects.create(**validated_data)
    print(f"Estimate instance {estimate.id} created.")

    # Create related MaterialItems
    for material_data in materials_data:
        MaterialItem.objects.create(estimate=estimate, **material_data)
    print(f"{len(materials_data)} MaterialItem(s) created.")

    # Create related RoomAreas
    for room_data in rooms_data:
        RoomArea.objects.create(estimate=estimate, **room_data)
    print(f"{len(rooms_data)} RoomArea(s) created.")

    # Create related LabourItems

    # Calculate and update derived fields (total_area_sq_m, profit_per_sq_meter)
    calculate_and_update_estimate_fields(estimate)

    print("--- create_estimate_and_nested_items service finished ---")
    return estimate


@transaction.atomic
def update_estimate_and_nested_items(estimate_instance: Estimate, validated_data):
    """
    Service function to update an Estimate and all its nested related items.
    Handles customer linking/creation/update and recalculation of derived fields.
    Implements a delete-and-recreate strategy for nested lists.
    """
    print(f"--- update_estimate_and_nested_items service started for Estimate ID: {estimate_instance.id} ---")

    materials_data = validated_data.pop('materials', None) # Use None to distinguish between empty list and not sent
    rooms_data = validated_data.pop('rooms', None)
    customer_data = validated_data.pop('customer', None)

    # --- Handle Customer update or linking ---
    if customer_data is not None:
        if 'id' in customer_data and customer_data['id'] is not None:
            # Link to existing customer OR update existing linked customer
            try:
                customer_instance = Customer.objects.get(id=customer_data['id'], user=estimate_instance.user)
                # Update details of the existing linked customer if fields are provided
                for attr, value in customer_data.items():
                    if attr != 'id': # Don't try to set ID
                        setattr(customer_instance, attr, value)
                customer_instance.save()
                estimate_instance.customer = customer_instance # Link the estimate to this customer
            except Customer.DoesNotExist:
                raise ValueError(f"Customer with ID '{customer_data['id']}' not found or does not belong to this user.")
        else:
            # Create a new customer and link it
            new_customer = Customer.objects.create(user=estimate_instance.user, **customer_data)
            estimate_instance.customer = new_customer
    elif customer_data is None and 'customer' in validated_data: # Explicitly sent as null
        estimate_instance.customer = None # Unlink customer


    # Update scalar fields on the Estimate instance
    for attr, value in validated_data.items():
        setattr(estimate_instance, attr, value)
    estimate_instance.save()
    print("Estimate scalar fields and customer link updated.")

    # --- Update Nested Items (Delete and Recreate) ---
    # Only process if the nested list was actually sent in the request
    if materials_data is not None:
        estimate_instance.materials.all().delete()
        for material_data in materials_data:
            MaterialItem.objects.create(estimate=estimate_instance, **material_data)
        print(f"Materials updated ({len(materials_data)} items).")

    if rooms_data is not None:
        estimate_instance.rooms.all().delete()
        for room_data in rooms_data:
            RoomArea.objects.create(estimate=estimate_instance, **room_data)
        print(f"Rooms updated ({len(rooms_data)} items).")


    # Recalculate derived fields after nested items are updated
    calculate_and_update_estimate_fields(estimate_instance)

    print("--- update_estimate_and_nested_items service finished ---")
    return estimate_instance