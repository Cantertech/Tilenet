
import os
import tempfile
from io import BytesIO
from datetime import datetime
from decimal import Decimal

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.pdfgen import canvas
from django.conf import settings

def calculate_materials(area, project_type, wastage_factor=0.1):
    """Calculate required materials based on project type and area"""
    materials = {}
    
    # Define material requirements per square meter
    material_rates = {
        'tiles': {
            'Tile adhesive': 0.25,
            'Grout': 0.05,
            'Spacers': 20,
            'Cement': 0.2,
            'Sand': 0.4,
            'Strip': 0.33,
        },
        'pavement': {
            'Cement': 0.3,
            'Sand': 0.5,
            'Acid': 0.1,
        },
        'masonry': {
            'Cement': 0.4,
            'Sand': 0.6,
            'Blocks': 12,
            'Rebar': 0.1,
            'Binding wire': 0.05,
        },
        'carpentry': {
            'Timber': 0.2,
            'Nails': 0.1,
            'Wood glue': 0.05,
            'Screws': 20,
            'Wood finish': 0.3,
        }
    }
    
    # Get materials for this project type
    project_materials = material_rates.get(project_type, {})
    
    # Calculate quantities with wastage
    for material, rate in project_materials.items():
        quantity = area * rate * (1 + Decimal(wastage_factor))
        materials[material] = round(quantity, 2)
    
    return materials

def get_trade_specific_styles(project_type):
    """Get trade-specific styles for PDF generation"""
    trade_styles = {
        'tiles': {
            'primary_color': colors.blue,
            'secondary_color': colors.lightblue,
            'header_bg': colors.lightsteelblue,
        },
        'pavement': {
            'primary_color': colors.darkgreen,
            'secondary_color': colors.lightgreen,
            'header_bg': colors.palegreen,
        },
        'masonry': {
            'primary_color': colors.brown,
            'secondary_color': colors.sandybrown,
            'header_bg': colors.bisque,
        },
        'carpentry': {
            'primary_color': colors.saddlebrown,
            'secondary_color': colors.burlywood,
            'header_bg': colors.wheat,
        },
    }
    
    return trade_styles.get(project_type, trade_styles['tiles'])


def generate_project_pdf(project):
    """Generate a PDF for a project estimate"""
    # Create a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        temp_path = tmp_file.name
    
    # Get trade-specific styles
    trade_styles = get_trade_specific_styles(project.project_type)
    
    # Set up the document
    doc = SimpleDocTemplate(
        temp_path, 
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TradeTitle',
        parent=styles['Title'],
        textColor=trade_styles['primary_color'],
    )
    heading_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Create custom styles
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=trade_styles['primary_color'],
        spaceAfter=10
    )
    
    # Content elements
    elements = []
    
    # Add trade-specific header/logo
    trade_headers = {
        'tiles': "Tiling Project Estimate",
        'pavement': "Pavement Project Estimate",
        'masonry': "Masonry Project Estimate",
        'carpentry': "Carpentry Project Estimate"
    }
    
    # Company and project header
    header_data = [
        [Paragraph(f"<b>Company:</b> {project.user.company_name if hasattr(project.user, 'company_name') else 'Your Company'}", normal_style),
         Paragraph(f"<b>Estimate #:</b> {project.estimate_number}", normal_style)],
        [Paragraph(f"<b>Date:</b> {project.created_at.strftime('%d %b, %Y')}", normal_style),
         Paragraph(f"<b>Project Type:</b> {project.get_project_type_display()}", normal_style)]
    ]
    
    header_table = Table(header_data, colWidths=[doc.width/2.0]*2)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, -1), trade_styles['header_bg']),
    ]))
    
    elements.append(Paragraph(trade_headers.get(project.project_type, "Project Estimate"), title_style))
    elements.append(Spacer(1, 0.25*inch))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Customer information
    elements.append(Paragraph("Customer Information", section_style))
    customer_data = [
        ["Customer Name:", project.customer_name or "N/A"],
        ["Location:", project.customer_location or "N/A"],
        ["Estimate Date:", project.created_at.strftime("%d %b, %Y")]
    ]
    
    customer_table = Table(customer_data, colWidths=[doc.width*0.3, doc.width*0.7])
    customer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0, 0), (0, -1), trade_styles['secondary_color']),
    ]))
    
    elements.append(customer_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Room details
    if project.rooms.exists():
        elements.append(Paragraph("Room Details", section_style))
        
        room_header = ["Room", "Type", "Dimensions", "Floor Area", "Wall Area", "Total Area"]
        room_data = [room_header]
        
        for room in project.rooms.all():
            # Format dimensions based on room type
            if room.room_type == 'Staircase':
                dimensions = f"Steps: {room.total or 0}, Step size: {room.length1 or 0} x {room.breadth1 or 0}"
            else:
                dimensions = f"{room.length or 0} x {room.breadth or 0}"
                if room.height:
                    dimensions += f" x {room.height}"
            
            room_data.append([
                room.name,
                room.get_room_type_display(),
                dimensions,
                f"{room.floor_area:.2f} m²",
                f"{room.wall_area:.2f} m²",
                f"{room.total_area:.2f} m²"
            ])
            
        # Add total row
        total_floor_area = sum(room.floor_area for room in project.rooms.all())
        total_wall_area = sum(room.wall_area for room in project.rooms.all())
        total_area = sum(room.total_area for room in project.rooms.all())
        
        room_data.append([
            "Total", "", "", f"{total_floor_area:.2f} m²", f"{total_wall_area:.2f} m²", f"{total_area:.2f} m²"
        ])
        
        room_table = Table(room_data, colWidths=[doc.width*0.2, doc.width*0.15, doc.width*0.2, doc.width*0.15, doc.width*0.15, doc.width*0.15])
        room_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), trade_styles['secondary_color']),
            ('BACKGROUND', (0, -1), (-1, -1), trade_styles['secondary_color']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ]))
        
        elements.append(room_table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Materials
    if project.materials.exists():
        elements.append(Paragraph("Materials Estimate", section_style))
        
        material_header = ["Material", "Unit", "Quantity", "Unit Price", "Total Price"]
        material_data = [material_header]
        
        for material in project.materials.all():
            material_data.append([
                material.name,
                material.unit,
                f"{material.quantity:.2f}",
                f"${material.unit_price:.2f}",
                f"${material.total_price:.2f}"
            ])
        
        # Add total material cost
        material_data.append([
            "Total Material Cost", "", "", "", f"${project.total_material_cost:.2f}"
        ])
        
        material_table = Table(material_data, colWidths=[doc.width*0.3, doc.width*0.15, doc.width*0.15, doc.width*0.2, doc.width*0.2])
        material_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), trade_styles['secondary_color']),
            ('BACKGROUND', (0, -1), (-1, -1), trade_styles['secondary_color']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ]))
        
        elements.append(material_table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Labor details
    if project.workers.exists():
        elements.append(Paragraph("Labor Estimate", section_style))
        
        labor_header = ["Role", "Count", "Rate", "Coverage", "Days", "Total Cost"]
        labor_data = [labor_header]
        
        for worker in project.workers.all():
            rate_text = f"${worker.rate:.2f}/{worker.get_rate_type_display().lower()}"
            
            labor_data.append([
                worker.get_role_display(),
                str(worker.count),
                rate_text,
                f"{worker.coverage_area:.2f} m²/day",
                str(project.estimated_days),
                f"${worker.total_cost:.2f}"
            ])
        
        # Add total labor cost
        labor_data.append([
            "Total Labor Cost", "", "", "", "", f"${project.total_labor_cost:.2f}"
        ])
        
        labor_table = Table(labor_data, colWidths=[doc.width*0.2, doc.width*0.1, doc.width*0.2, doc.width*0.2, doc.width*0.1, doc.width*0.2])
        labor_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), trade_styles['secondary_color']),
            ('BACKGROUND', (0, -1), (-1, -1), trade_styles['secondary_color']),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ]))
        
        elements.append(labor_table)
        elements.append(Spacer(1, 0.3*inch))
    
    # Summary
    elements.append(Paragraph("Cost Summary", section_style))
    
    # Calculate profit
    profit_amount = 0
    if project.profit_type == 'percentage':
        base_cost = project.total_material_cost + project.total_labor_cost
        profit_amount = base_cost * (project.profit_value / 100)
        profit_text = f"{project.profit_value}% of base cost"
    elif project.profit_type == 'fixed':
        profit_amount = project.profit_value
        profit_text = "Fixed amount"
    elif project.profit_type == 'per_sqm':
        profit_amount = project.profit_value * project.total_area
        profit_text = f"${project.profit_value:.2f} per m²"
    
    summary_data = [
        ["Description", "Amount"],
        ["Material Cost", f"${project.total_material_cost:.2f}"],
        ["Labor Cost", f"${project.total_labor_cost:.2f}"],
        ["Base Cost", f"${(project.total_material_cost + project.total_labor_cost):.2f}"],
        [f"Profit ({profit_text})", f"${profit_amount:.2f}"],
        ["Wastage", f"{project.wastage_percentage}%"],
        ["Grand Total", f"${project.total_cost:.2f}"],
        ["Cost per m²", f"${project.cost_per_sqm:.2f}"],
        ["Estimated Days", f"{project.estimated_days} days"]
    ]
    
    summary_table = Table(summary_data, colWidths=[doc.width*0.6, doc.width*0.4])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, 0), trade_styles['secondary_color']),
        ('BACKGROUND', (0, -3), (-1, -3), trade_styles['secondary_color']),  # Grand Total row
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -3), (-1, -3), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Trade-specific terms and conditions
    elements.append(Paragraph("Terms & Conditions", section_style))
    
    # Different terms based on trade
    terms_text = {
        'tiles': """
        1. This estimate is valid for 30 days from the date of issue.
        2. A 50% deposit is required before work commences.
        3. The remaining balance is due upon completion of the project.
        4. Any additional work not specified in this estimate will be quoted separately.
        5. Materials may vary in color and texture from samples provided.
        6. Tiling work requires a flat, clean, and dry surface for proper installation.
        """,
        'pavement': """
        1. This estimate is valid for 30 days from the date of issue.
        2. A 50% deposit is required before work commences.
        3. The remaining balance is due upon completion of the project.
        4. Any additional work not specified in this estimate will be quoted separately.
        5. Ground preparation and excavation costs may vary depending on site conditions.
        6. Weather conditions may affect schedule and curing times for pavement work.
        """,
        'masonry': """
        1. This estimate is valid for 30 days from the date of issue.
        2. A 50% deposit is required before work commences.
        3. The remaining balance is due upon completion of the project.
        4. Any additional work not specified in this estimate will be quoted separately.
        5. Foundation work and soil conditions may require additional materials.
        6. Structural engineering approval may be required for load-bearing walls.
        """,
        'carpentry': """
        1. This estimate is valid for 30 days from the date of issue.
        2. A 50% deposit is required before work commences.
        3. The remaining balance is due upon completion of the project.
        4. Any additional work not specified in this estimate will be quoted separately.
        5. Wood type and finish may affect final appearance and cost.
        6. Humidity and environmental conditions may affect wood installation and finishing.
        """
    }
    
    elements.append(Paragraph(terms_text.get(project.project_type, terms_text['tiles']), normal_style))
    elements.append(Spacer(1, 0.5*inch))
    
    # Signature
    signature_data = [
        ["_________________________", "_________________________"],
        ["Customer Signature", "Company Representative"],
        ["Date: _________________", "Date: _________________"]
    ]
    
    signature_table = Table(signature_data, colWidths=[doc.width/2.0]*2)
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(signature_table)
    
    # Build PDF
    doc.build(elements)
    
    return temp_path
