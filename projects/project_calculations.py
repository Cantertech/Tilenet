import decimal
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
import math

from .models import (
    Material, Project, Room, ProjectMaterial, Worker, DynamicSetting, Unit,
    TilingRoomDetails, PaintingRoomDetails,
    # Assuming other models are imported here
)

DEFAULT_WALL_COVERAGE_RATE = decimal.Decimal(12.0)
DEFAULT_FLOOR_COVERAGE_RATE = decimal.Decimal(14.0)
DEFAULT_ADDITIONAL_DAYS = 0
HOURS_PER_WORKDAY = decimal.Decimal(8)

HARDCODED_DEFAULT_ROLE_COVERAGE = {
    'master': {
        'floor': decimal.Decimal(30),   # 25–35 m²/day realistic
        'wall': decimal.Decimal(20),    # 15–25 m²/day
    },
    'labourer': {
        'floor': decimal.Decimal(0),
        'wall': decimal.Decimal(0),
    },
    'supervisor': {
        'floor': decimal.Decimal(0),
        'wall': decimal.Decimal(0),
    },
    'painter': {
        'floor': decimal.Decimal(0),
        'wall': decimal.Decimal(120),   # Painters can cover 100–150 m²/day on good surfaces
    },
    'default': {
        'floor': decimal.Decimal(10),   # Conservative estimate
        'wall': decimal.Decimal(10),
    },
}


CONVERSION_FACTORS_TO_METERS = {
    'meters': decimal.Decimal(1),
    'feet': decimal.Decimal(0.3048),
    'inches': decimal.Decimal(0.0254),
    'centimeters': decimal.Decimal(0.01),
}

# --- Material Coverage/Usage Rates ---
# This dictionary defines how much of a material is needed per unit of area/volume/length
# for different project types.
# The values here should represent the QUANTITY of material needed per:
# - square meter (for area-based materials like grout, adhesive, tiles)
# - linear meter (for linear materials like strip)
# - cubic meter (for volume-based materials like cement, sand in screed/concrete)
#
# NOTE: The current payload only provides room dimensions. Calculating quantity for
# volume-based materials (cement, sand) accurately requires screed/concrete thickness,
# and for linear materials (strip) requires perimeter or linear features.
# The current logic will use total_area, which is likely incorrect for these.
# This is a limitation based on available input data and current logic structure.
# You might need to adjust input payload or calculation logic for accuracy.
COVERAGE_RATES_PER_UNIT = {
    'tiling': {
        'cement': decimal.Decimal(1) / decimal.Decimal(6),    
        'sand': decimal.Decimal(1) /decimal.Decimal(3),        
        'chemical': decimal.Decimal(1) / decimal.Decimal(41),      
        'tile cement': decimal.Decimal(1) / decimal.Decimal(4),    
        'grout': decimal.Decimal(1) / decimal.Decimal(14),         
        
    },
# 2 wheel barrow  of sand for 1 bag cement , 8 headpans 
# //300 wheel barrows  == 150 bags  for tipa large cina bucket 
# //175 whell barrow  == for small tipa 
# //for 6 m^2 = 1 cement , 2 wheel barrow 
# //for eveery 1 bag cement , 1 tile cent , 4 m^2
# //6.25 kg of chemical = 14 m^2 x 3
# //3kg of grout = 14 m^2, ,   

    'pavement': {
        'cement': decimal.Decimal(1) / decimal.Decimal(5),         # ≈ 0.2 bags per m²
        'sand': decimal.Decimal(1) / decimal.Decimal(1.5),         # ≈ 0.6667 m³ per m²
        'tiles': lambda tile_area_sq_m: decimal.Decimal(1) / tile_area_sq_m if tile_area_sq_m else decimal.Decimal(0),
        'acid': decimal.Decimal(1) / decimal.Decimal(450),         # ≈ 0.0022 liters per m²
        'stone base': decimal.Decimal(0.1),                        # e.g. crushed stone (m³ per m²)
        'edge restraint': decimal.Decimal(0.2),                    # e.g. concrete/metal borders (linear meters per m²)
        'geotextile': decimal.Decimal(1),                          # 1 m² of geotextile underlay per m²
        'water': decimal.Decimal(0.01),                            # Water for curing/binding (m³ per m²)
    },

    'mason': {
        'cement': decimal.Decimal(1) / decimal.Decimal(7),         # ≈ 0.1429 bags per m²
        'sand': decimal.Decimal(1) / decimal.Decimal(3.5),         # ≈ 0.2857 m³ per m²
        'tiles': lambda tile_area_sq_m: decimal.Decimal(1) / tile_area_sq_m if tile_area_sq_m else decimal.Decimal(0),
        'chemical': decimal.Decimal(1) / decimal.Decimal(12),      # ≈ 0.0833 liters per m²
        'plaster': decimal.Decimal(0.02),                          # ≈ 0.02 bags per m²
        'water': decimal.Decimal(0.015),                           # ≈ 0.015 m³ per m²
        'blocks': decimal.Decimal(12),                             # ≈ 12 blocks per m² of wall (6" blocks)
        'binding wire': decimal.Decimal(0.1),                      # ≈ 0.1 kg per m² for tying reinforcements
        'reinforcement bar': decimal.Decimal(0.5),                 # ≈ 0.5 kg per m² (if reinforced wall)
    },

}

def convert_to_meters(value, unit_name):
    """Converts a value from a given unit to meters."""
    try:
        value = decimal.Decimal(value)
        factor = CONVERSION_FACTORS_TO_METERS.get(unit_name.lower(), decimal.Decimal(1))
        return value * factor
    except (decimal.InvalidOperation, TypeError):
        return decimal.Decimal(0)

def get_dynamic_settings(user):
    """Fetches or creates DynamicSetting for a user."""
    settings, created = DynamicSetting.objects.get_or_create(user=user)
    return settings

def calculate_default_worker_coverage(user, worker_role, project_type):
    """
    Determines the default floor and wall coverage rates for a worker role
    based on user's DynamicSetting JSONField, falling back to hardcoded defaults.
    Returns a tuple (default_floor, default_wall).
    """
    user_settings = get_dynamic_settings(user)
    worker_role_lower = worker_role.lower()

    user_role_coverage_data = user_settings.role_coverage_defaults or {}
    user_specific_defaults = user_role_coverage_data.get(worker_role_lower, {})

    hardcoded_specific_defaults = HARDCODED_DEFAULT_ROLE_COVERAGE.get(worker_role_lower, HARDCODED_DEFAULT_ROLE_COVERAGE.get('default', {}))
    default_floor_float = decimal.Decimal(str(user_specific_defaults.get('floor', hardcoded_specific_defaults.get('floor', 0.0))))
    default_wall_float = decimal.Decimal(str(user_specific_defaults.get('wall', hardcoded_specific_defaults.get('wall', 0.0))))

    return default_floor_float, default_wall_float

def calculate_room_areas_and_save(room_instance):
    """
    Calculates floor, wall, and total area for a room.
    Uses details object calculation if available, otherwise uses basic dimensions.
    Converts dimensions to meters before calculation.
    Saves the updated area fields to the room instance.
    """
    print(f"Calculating areas for Room ID {room_instance.id} (Name: {room_instance.name}).")
    calculated_floor_area = decimal.Decimal(0)
    calculated_wall_area = decimal.Decimal(0)
    calculated_total_area = decimal.Decimal(0)

    project_instance = room_instance.project
    measurement_unit = project_instance.measurement_unit.lower() if project_instance.measurement_unit else 'meters'
    print(f"Project measurement unit: {measurement_unit}")

    length_m = convert_to_meters(room_instance.length or 0, measurement_unit)
    breadth_m = convert_to_meters(room_instance.breadth or 0, measurement_unit)
    height_m = convert_to_meters(room_instance.height or 0, measurement_unit) # Assuming height exists

    print(f"Dimensions in meters: L={length_m}, B={breadth_m}, H={height_m}")

    if room_instance.details:
        print(f"Calculating areas using details object ({type(room_instance.details).__name__}).")
        calculated_floor_area, calculated_wall_area, calculated_total_area = room_instance.details.calculate_area_details(
            length_m, breadth_m, height_m, room_instance # Pass dimensions in meters and room instance
        )
        print(f"Areas calculated by details object: Floor={calculated_floor_area}, Wall={calculated_wall_area}, Total={calculated_total_area}")

    else:
        print(f"Calculating basic areas using dimensions in meters (L={length_m}, B={breadth_m}, H={height_m}).")
        if length_m > 0 and breadth_m > 0:
            calculated_floor_area = length_m * breadth_m
            if height_m > 0:
                 calculated_wall_area = (2 * length_m + 2 * breadth_m) * height_m
        calculated_total_area = calculated_floor_area + calculated_wall_area # Sum floor and wall for total area
        print(f"Basic areas calculated: Floor={calculated_floor_area}, Wall={calculated_wall_area}, Total={calculated_total_area}")

    room_instance.floor_area = decimal.Decimal(calculated_floor_area)
    room_instance.wall_area = decimal.Decimal(calculated_wall_area)
    room_instance.total_area = decimal.Decimal(calculated_total_area)
    room_instance.save(update_fields=['floor_area', 'wall_area', 'total_area'])
    print(f"Saved areas for Room ID {room_instance.id}: Floor={room_instance.floor_area}, Wall={room_instance.wall_area}, Total={room_instance.total_area}")

def calculate_project_areas_and_save(project_instance):
    """
    Calculates the total floor, wall, and combined area for a project
    by summing up the areas of its associated rooms.
    Saves the updated total area fields to the project instance.
    """
    print(f"Calculating total project areas for Project ID {project_instance.id}.")
    rooms = project_instance.rooms.all()

    total_floor = decimal.Decimal(0)
    total_wall = decimal.Decimal(0)

    for room in rooms:
        total_floor += decimal.Decimal(room.floor_area or 0)
        total_wall += decimal.Decimal(room.wall_area or 0)

    project_instance.total_floor_area = total_floor
    project_instance.total_wall_area = total_wall
    project_instance.total_area = total_floor + total_wall 
    project_instance.save(update_fields=['total_floor_area', 'total_wall_area', 'total_area'])
    print(f"Saved total areas for Project ID {project_instance.id}: Total Floor={project_instance.total_floor_area}, Total Wall={project_instance.total_wall_area}, Total Area={project_instance.total_area}")


def calculate_project_material_item_totals_and_save(project_material_instance):
    """
    Calculates quantity with wastage and total price for a ProjectMaterial item
    based on project details and material coverage rates, and saves the updated fields.
    """
    print(f"Calculating material totals for ProjectMaterial ID {project_material_instance.id}.")
    project_instance = project_material_instance.project
    material_instance = project_material_instance.material

    if not project_instance or not material_instance:
        print(f"Warning: Cannot calculate material totals for ProjectMaterial ID {project_material_instance.id if project_material_instance else 'N/A'} - missing project or material instance.")
        if project_material_instance:
             project_material_instance.quantity = decimal.Decimal(0)
             project_material_instance.quantity_with_wastage = decimal.Decimal(0)

             project_material_instance.save(update_fields=['quantity', 'quantity_with_wastage',])
        return
    relevant_area_dec = decimal.Decimal(project_instance.total_area or 0) # Default to total area
    project_type = project_instance.project_type
    material_name = material_instance.name.lower() # Use lower case for consistent lookup
    wastage_percentage_dec = decimal.Decimal(project_instance.wastage_percentage or 0)
    mortar_thickness_dec = decimal.Decimal(project_instance.mortar_thickness or 0)
    calculated_quantity_raw = decimal.Decimal(0)
    coverage_rate_per_unit = decimal.Decimal(0) # This is the quantity of material per unit area/length/volume

    project_coverage_rates = COVERAGE_RATES_PER_UNIT.get(project_type)
    selected_material_names_lower = list(
        project_instance.materials.all().values_list('material__name', flat=True)
    )
    selected_material_names_lower = [name.lower() for name in selected_material_names_lower] # Ensure all are lowercase


    # --- SPECIAL LOGIC FOR CEMENT BASED ON OTHER SELECTED MATERIALS ---
    if material_name == 'cement':
        has_sand_selected = 'sand' in selected_material_names_lower
        has_tile_cement_selected = 'tile cement' in selected_material_names_lower # Check if 'tile cement' itself is selected

        if has_sand_selected:
            # Priority 1: If sand is selected, use cement rate for sand-cement mix (1/6)
            coverage_rate_per_unit = project_coverage_rates.get('cement', decimal.Decimal(0))
            print(f"DEBUG: Cement coverage for '{project_type}' set by 'sand' presence: {coverage_rate_per_unit}")
        elif has_tile_cement_selected:
            # Priority 2: If no sand, but 'tile cement' is selected, use 'tile cement' rate for cement (1/4)
            # This assumes 'tile cement' entry *in the coverage rates* defines the cement portion needed
            # for this scenario. If 'tile cement' is just a flag, you might point to 'cement' directly.
            # Based on your COVERAGE_RATES_PER_UNIT, 'tile cement' is a direct material entry.
            coverage_rate_per_unit = project_coverage_rates.get('tile cement', decimal.Decimal(0))
            print(f"DEBUG: Cement coverage for '{project_type}' set by 'tile cement' presence (no sand): {coverage_rate_per_unit}")
        else:
            # Default: If neither sand nor tile cement dictate it, use the generic 'cement' rate
            coverage_rate_per_unit = project_coverage_rates.get('cement', decimal.Decimal(0))
            print(f"DEBUG: Cement coverage for '{project_type}' set by default: {coverage_rate_per_unit}")

    # --- GENERAL LOGIC for all other materials (and for cement if none of the above applied) ---
    else:
        # General logic for all other materials (not 'cement')
        coverage_value = project_coverage_rates[material_name]

        if coverage_value is None:
            print(f"Warning: Coverage rate for material '{material_name}' (ID {material_instance.id}) "
                  f"not defined for project type '{project_type}' (Project ID {project_instance.id}). Setting coverage to 0.")
            coverage_rate_per_unit = decimal.Decimal(0)
        else:
            try:
                # Handle callable coverage rates (e.g., lambda functions)
                if callable(coverage_value):
                    # Passing the relevant_area_dec to the callable rate
                    coverage_rate_per_unit = decimal.Decimal(coverage_value(relevant_area_dec))
                    print(f"Calculated coverage rate via callable for '{material_name}': {coverage_rate_per_unit}")
                else:
                    coverage_rate_per_unit = decimal.Decimal(coverage_value)
                    print(f"Using fixed coverage rate for '{material_name}': {coverage_rate_per_unit}")

            except (decimal.InvalidOperation, TypeError, AttributeError) as e:
                print(f"ERROR: Problem determining coverage rate for material '{material_name}' (ID {material_instance.id}) "
                      f"in project type '{project_type}' (Project ID {project_instance.id}): {e}. "
                      f"Check material item data or coverage definition. Setting coverage to 0.")
                coverage_rate_per_unit = decimal.Decimal(0)

        coverage_rate_per_unit = decimal.Decimal(coverage_rate_per_unit) # Redundant but safe if previous logic was flawed

    if relevant_area_dec == 0 or coverage_rate_per_unit == 0:
        calculated_quantity_raw = decimal.Decimal(0)
        print(f"Calculated raw quantity for '{material_name}' is 0 due to zero area or coverage.")
    else:
        calculated_quantity_raw = relevant_area_dec * coverage_rate_per_unit
        print(f"Calculated raw quantity for '{material_name}': {relevant_area_dec} (area) * {coverage_rate_per_unit} (coverage) = {calculated_quantity_raw}")
    wastage_perrc = 0
    if wastage_percentage_dec <= 3.01 :
        if relevant_area_dec <= 55:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(5) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(5)
        elif relevant_area_dec <= 200:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(3) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(3)
        else:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(2) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(2)
    elif wastage_percentage_dec <=5.01:
        if relevant_area_dec <= 55:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(10) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(10)
        elif relevant_area_dec <= 200:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(7) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(7)
        else:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(5) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(5)
    else:
        if relevant_area_dec <= 55:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(15) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(15)
        elif relevant_area_dec <= 200:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(12) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(12)
        else:
            wastage_multiplier = decimal.Decimal(1) + (decimal.Decimal(10) / decimal.Decimal(100))
            wastage_perrc = decimal.Decimal(10)

    quantity_with_wastage = calculated_quantity_raw * wastage_multiplier
    print(f"Quantity with wastage: {calculated_quantity_raw} * {wastage_multiplier} = {quantity_with_wastage}")
    if mortar_thickness_dec >= 9.88 :
        if material_name in ['cement','sand','tile cement','chemical']:
            quantity_with_wastage = quantity_with_wastage * (decimal.Decimal(1) + (decimal.Decimal(7) / decimal.Decimal(100)))
    final_quantity = quantity_with_wastage

    project_instance.wastage_percentage =  wastage_perrc
    print(f'wastage percentage :{wastage_perrc}')
    project_material_instance.quantity = calculated_quantity_raw
    project_material_instance.quantity_with_wastage = final_quantity

    project_material_instance.save(update_fields=['quantity', 'quantity_with_wastage'])
    project_instance.save(update_fields=['wastage_percentage'])

    print(f"Calculated totals for ProjectMaterial ID {project_material_instance.id} (Material: {material_name}, Project: {project_instance.id}): Quantity={project_material_instance.quantity}, Quantity w/ Wastage={project_material_instance.quantity_with_wastage}")


def calculate_worker_total_cost_and_save(worker_instance, estimated_days):
    """
    Calculates the total labor cost for a worker group based on their rate, count,
    rate type, and the estimated project days. Saves the updated total_cost field.
    """
    print(f"Calculating total cost for Worker ID {worker_instance.id} (Role: {worker_instance.role}).")
    rate_dec = decimal.Decimal(worker_instance.rate or 0)
    count_int = worker_instance.count or 0
    rate_type = worker_instance.rate_type
    estimated_days_dec = decimal.Decimal(estimated_days or 0)

    total_cost = decimal.Decimal(0)

    if count_int > 0 and rate_dec > 0 and estimated_days_dec > 0:
        if rate_type == 'daily':
            total_cost = rate_dec * count_int * estimated_days_dec
            print(f"Daily rate calculation: {rate_dec} * {count_int} * {estimated_days_dec} = {total_cost}")
        elif rate_type == 'hourly':
            # Assuming an 8-hour workday for hourly rates
            total_cost = rate_dec * count_int * estimated_days_dec * HOURS_PER_WORKDAY
            print(f"Hourly rate calculation: {rate_dec} * {count_int} * {estimated_days_dec} * {HOURS_PER_WORKDAY} = {total_cost}")
        # Add other rate types if needed
    else:
         print(f"Worker count ({count_int}), rate ({rate_dec}), or estimated days ({estimated_days_dec}) is zero or less. Worker cost is zero.")

    special_equipment_cost_dec = decimal.Decimal(worker_instance.special_equipment_cost_per_day or 0)
    if special_equipment_cost_dec > 0 and estimated_days_dec > 0:
         equipment_cost = special_equipment_cost_dec * estimated_days_dec
         total_cost += equipment_cost
         print(f"Added special equipment cost: {special_equipment_cost_dec} * {estimated_days_dec} = {equipment_cost}. New total cost: {total_cost}")
    elif special_equipment_cost_dec > 0:
         print(f"Special equipment cost per day ({special_equipment_cost_dec}) is positive, but estimated days ({estimated_days_dec}) is zero. Special equipment cost is zero.")


    worker_instance.total_cost = total_cost
    worker_instance.save(update_fields=['total_cost'])
    
    print(f"Calculated total cost for Worker ID {worker_instance.id} (Role: {worker_instance.role}, Project: {worker_instance.project.id}): Total Cost={worker_instance.total_cost}")


def calculate_combined_worker_coverage(project_instance):

    print(f"Calculating combined worker coverage for Project ID {project_instance.id}.")
    total_floor_coverage_per_day = decimal.Decimal(0)
    total_wall_coverage_per_day = decimal.Decimal(0)

    user_settings = get_dynamic_settings(project_instance.user)
    project_type = project_instance.project_type

    for worker in project_instance.workers.all():
        worker_count = decimal.Decimal(worker.count or 0)

        if worker_count <= 0:
             print(f"Worker {worker.role} (ID {worker.id}) has zero or negative count. Skipping coverage calculation for this worker.")
             continue

        effective_floor_coverage_rate, effective_wall_coverage_rate = calculate_default_worker_coverage(
            project_instance.user,
            worker.role,
            project_type
        )
        print(f"Worker {worker.role} (ID {worker.id}) coverage rates: Floor={effective_floor_coverage_rate}/day, Wall={effective_wall_coverage_rate}/day.")


        total_floor_coverage_per_day += effective_floor_coverage_rate * worker_count
        total_wall_coverage_per_day += effective_wall_coverage_rate * worker_count
        print(f"Cumulative coverage: Floor={total_floor_coverage_per_day}/day, Wall={total_wall_coverage_per_day}/day.")


    print(f"Total combined worker coverage per day: Floor={total_floor_coverage_per_day}, Wall={total_wall_coverage_per_day}.")
    return total_floor_coverage_per_day, total_wall_coverage_per_day

def calculate_project_estimated_days_and_save(project_instance):
    print(f"Calculating estimated days for Project ID {project_instance.id}.")
    total_floor_area_dec = decimal.Decimal(project_instance.total_floor_area or 0)
    total_wall_area_dec = decimal.Decimal(project_instance.total_wall_area or 0)
    print(f"Total project areas: Floor={total_floor_area_dec}, Wall={total_wall_area_dec}.")


    total_combined_floor_coverage_per_day, total_combined_wall_coverage_per_day = calculate_combined_worker_coverage(project_instance)

    estimated_floor_days_raw = decimal.Decimal(0)
    estimated_wall_days_raw = decimal.Decimal(0)

    if total_floor_area_dec > 0 and total_combined_floor_coverage_per_day > 0:
         estimated_floor_days_raw = total_floor_area_dec / total_combined_floor_coverage_per_day
         print(f"Estimated floor days raw: {total_floor_area_dec} / {total_combined_floor_coverage_per_day} = {estimated_floor_days_raw}.")
    elif total_floor_area_dec > 0:
         print(f"Warning: Total floor area ({total_floor_area_dec}) is positive but combined floor coverage is zero for Project {project_instance.id}. Floor days calculation may be inaccurate.")
         pass # estimated_floor_days_raw remains 0

    if total_wall_area_dec > 0 and total_combined_wall_coverage_per_day > 0:
         estimated_wall_days_raw = total_wall_area_dec / total_combined_wall_coverage_per_day
         print(f"Estimated wall days raw: {total_wall_area_dec} / {total_combined_wall_coverage_per_day} = {estimated_wall_days_raw}.")
    elif total_wall_area_dec > 0:
         print(f"Warning: Total wall area ({total_wall_area_dec}) is positive but combined wall coverage is zero for Project {project_instance.id}. Wall days calculation may be inaccurate.")
         # Decide how to handle this - maybe assume a very high number of days or a default?
         pass # estimated_wall_days_raw remains 0

    estimated_days_raw = estimated_floor_days_raw + estimated_wall_days_raw
    print(f"Maximum raw estimated days (Floor vs Wall): {estimated_days_raw}.")


    user_settings = get_dynamic_settings(project_instance.user)
    additional_days = decimal.Decimal(user_settings.default_additional_days or DEFAULT_ADDITIONAL_DAYS or 0)
    print(f"Additional days from settings: {additional_days}.")

    estimated_days_final = additional_days # Start with additional days

    if estimated_days_raw > 0:
        estimated_days_final += decimal.Decimal(math.ceil(estimated_days_raw))
        estimated_days_final = max(decimal.Decimal(1), estimated_days_final) # Ensure at least 1 day if there's work

    estimated_days_final = int(estimated_days_final) # Convert to integer for the model field
    project_instance.estimated_days = estimated_days_final
    print(f"Calculated estimated days for Project {project_instance.id}: Floor Days Raw={estimated_floor_days_raw}, Wall Days Raw={estimated_wall_days_raw}, Total Estimated Days={project_instance.estimated_days}")



    
def calculate_project_financial_totals_and_save(project_instance):
    """Calculates and sets the financial total fields for the project."""
    print(f"Calculating project financial totals for Project ID {project_instance.id}.")
    # Ensure project instance is up-to-date with latest costs and areas
    profit_amount = decimal.Decimal(0)
    profit_type = project_instance.profit_type
    profit_value = decimal.Decimal(project_instance.profit_value or 0)
    total_area_dec = decimal.Decimal(project_instance.total_area or 0) # Use total_area for per_area profit
    total_labour_cost = decimal.Decimal(0)
    print(f"Calculating total labour costs for Project {project_instance.id}.")
    if not project_instance:
        print(f"Warning: Cannot calculate total labour costs - missing project instance.")
        return
    total_project_labor_cost = Worker.objects.filter(project=project_instance).aggregate(Sum('total_cost'))['total_cost__sum']

    if profit_value > 0:
       
        if profit_type == 'fixed':
            total_labour_cost = profit_value
            profit_amount = profit_value - total_project_labor_cost
            print(f"Calculated Profit (Fixed): {profit_amount}")
        elif profit_type == 'per_area' and total_area_dec > 0:
            total_labour_cost = profit_value * total_area_dec
            profit_amount = total_labour_cost - total_project_labor_cost
            print(f"Calculated Profit (Per Area): {profit_value} * {total_area_dec} = {profit_amount}")
        else:
             print(f"Warning: Profit type '{profit_type}' is 'per_area' but total area is zero ({total_area_dec}) for Project {project_instance.id}. Profit set to zero.")
    else:
         print(f"Profit value ({profit_value}) is zero or less. Profit set to zero.")

    project_instance.profit = profit_amount
    project_instance.total_labor_cost = total_labour_cost
    print(f"Calculated Profit: {project_instance.profit}")
    print(f"Calculated total labour costs for Project {project_instance.id}: {project_instance.total_labor_cost}")

    if total_area_dec > 0:
        if profit_type == 'fixed':
            project_instance.cost_per_area = (project_instance.total_labor_cost + profit_amount) / total_area_dec
        else:
            project_instance.cost_per_area = profit_value
    else:
        project_instance.cost_per_area = decimal.Decimal(0)
        print(f"Total area is zero. Cost per area set to zero.")

    print(f"Finished calculating financial totals for Project ID {project_instance.id}.")

@transaction.atomic
def calculate_project_totals(project_id):
    print(f"Starting project total calculations for Project ID: {project_id}")
    try:
        project_instance = Project.objects.select_related('user').prefetch_related(
            'rooms__details', # Prefetch rooms and their details
            'materials__material', # Prefetch project materials and their linked Material objects
            'workers', # Prefetch workers
        ).get(id=project_id)

        print(f"Fetched Project instance: {project_instance.name} ({project_instance.estimate_number})")
        print("--- Calculating Room Areas ---")
        rooms = list(project_instance.rooms.all()) # Convert to list to avoid issues with iteration and saving
        if not rooms:
            print(f"No rooms found for Project ID {project_id}. Skipping room area calculations.")
        else:
            for room in rooms:
                calculate_room_areas_and_save(room)
        print("--- Calculating Total Project Areas ---")
        area_aggregates = project_instance.rooms.aggregate(
            total_floor_area_sum=Sum('floor_area'),
            total_wall_area_sum=Sum('wall_area'),
            total_area_sum=Sum('total_area') # Sum of individual room total_area
        )
        project_instance.total_floor_area = area_aggregates.get('total_floor_area_sum') or decimal.Decimal(0)
        project_instance.total_wall_area = area_aggregates.get('total_wall_area_sum') or decimal.Decimal(0)
        project_instance.total_area = project_instance.total_floor_area + project_instance.total_wall_area
        print(f"Aggregated Project Areas: Total Floor={project_instance.total_floor_area}, Total Wall={project_instance.total_wall_area}, Total Area={project_instance.total_area}")
        project_instance.save(update_fields=['total_floor_area', 'total_wall_area', 'total_area'])
        print(f"Saved total project areas for Project ID {project_instance.id}.")

        print("--- Calculating Estimated Days ---")
        calculate_project_estimated_days_and_save(project_instance)
        print("--- Calculating Worker Costs ---")
        workers = list(project_instance.workers.all()) # Convert to list
        if not workers:
             print(f"No workers found for Project ID {project_id}. Skipping worker cost calculations.")
        else:
            estimated_days = project_instance.estimated_days
            for worker in workers:
                calculate_worker_total_cost_and_save(worker, estimated_days)
 
        print("--- Calculating Material Quantities and Costs ---")
        project_materials = list(project_instance.materials.all()) 
        if not project_materials:
             print(f"No materials found for Project ID {project_id}. Skipping material quantity/cost calculations.")
        else:
            for project_material in project_materials:
                 calculate_project_material_item_totals_and_save(project_material)

        print("--- Calculating Project Financial Totals ---")
        calculate_project_financial_totals_and_save(project_instance)
        print("--- Final Project Save ---")
        final_update_fields = [
            'total_floor_area', 'total_wall_area', 'total_area',
            'estimated_days','total_labor_cost','profit','cost_per_area', 
            'updated_at' ,'wastage_percentage'
        ]
        print("Final Project Save update_fields:", final_update_fields)

        # --- Added Print Statements Before Save ---
        print("\n--- Data being saved to Project instance ---")
        print(f"total_floor_area: {project_instance.total_floor_area}")
        print(f"total_wall_area: {project_instance.total_wall_area}")
        print(f"total_area: {project_instance.total_area}")
        print(f"estimated_days okay: {project_instance.estimated_days}")
        print(f"total_labor_cost: {project_instance.total_labor_cost}")
        print(f"profit: {project_instance.profit}")
        print(f"cost_per_area: {project_instance.cost_per_area}")
        print(f"updated_at: {project_instance.updated_at}") # Note: updated_at is often set automatically on save
        print("-----------------------------------------")
        project_instance.save(update_fields=final_update_fields)
        print(f"Final save for Project ID {project_instance.id}.")
        print(f"Finished project calculations for Project ID: {project_id}")
    except Project.DoesNotExist:
        print(f"Error: Project with ID {project_id} not found during recalculation.")
        raise
    except Exception as e:
        print(f"An unexpected error occurred in calculate_project_totals for Project ID {project_id}: {e}")

        raise
