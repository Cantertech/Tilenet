
def convert_to_meters(value, unit):
    """Convert a measurement from the given unit to meters"""
    if value is None:
        return None
        
    if unit == 'meters':
        return value
    elif unit == 'centimeters':
        return value / 100
    elif unit == 'feet':
        return value * 0.3048
    elif unit == 'inches':
        return value * 0.0254
    return value  # Default case

def calculate_wastage_factor(area):
    """Calculate wastage factor based on area size
    
    The larger the area, the smaller the wastage factor
    """
    if area < 5:  # Very small area (less than 5 sq meters)
        return 0.15  # 15% wastage
    elif area < 20:  # Small area
        return 0.12  # 12% wastage
    elif area < 50:  # Medium area
        return 0.10  # 10% wastage
    elif area < 100:  # Large area
        return 0.08  # 8% wastage
    else:  # Very large area
        return 0.05  # 5% wastage

def calculate_materials(project_type, area, wastage_factor=0.1, floor_thickness=0.05):
    """Calculate required materials based on project type and area"""
    materials = {}
    
    # Define coverage areas for different materials
    coverage_areas = {
        'tiles': {
            'cement': 6,
            'sand': 3.75,
            'chemical': 13,
            'tile cement': 6,
            'grout': 19,
            'spacers': 80,
            'strip': 30,
            'tile adhesive': 10,
        },
        'pavement': {
            'cement': 5,
            'sand': 3,
            'gravel': 2.5,
            'paving stones': 10,
        },
        'masonry': {
            'cement': 7,
            'sand': 3.5,
            'blocks': 10,
            'rebar': 15,
            'binding wire': 50,
            'formwork': 8,
        },
        'carpentry': {
            'timber': 2.5,
            'nails': 30,
            'wood glue': 20,
            'screws': 40,
            'sandpaper': 15,
            'wood finish': 10,
            'wood filler': 25,
        }
    }
    
    # Get coverage areas for the selected project type
    project_materials = coverage_areas.get(project_type, {})
    
    # Calculate material quantities with wastage factor
    for material, coverage in project_materials.items():
        quantity = (area / coverage) * (1 + wastage_factor)
        
        # Adjust cement and sand quantity based on floor thickness for tiles and pavement
        if project_type in ['tiles', 'pavement'] and material in ['cement', 'sand'] and floor_thickness:
            thickness_factor = floor_thickness / 0.05  # 0.05m (5cm) is the standard thickness
            quantity *= thickness_factor
        
        # Special calculation for masonry based on wall height
        if project_type == 'masonry' and material in ['blocks', 'mortar']:
            # This is a placeholder for masonry-specific calculations
            pass
            
        # Special calculation for carpentry based on wood type
        if project_type == 'carpentry' and material == 'timber':
            # This is a placeholder for carpentry-specific calculations
            pass
            
        materials[material] = round(quantity, 2)
    
    return materials
