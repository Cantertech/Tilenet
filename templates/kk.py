from fpdf import FPDF
from datetime import datetime
from decimal import Decimal

# Sample data (you can load this from a database or external source)
estimate_data = {
    'customer': {'name': 'Customer name', 'phone': '0244284816', 'location': 'Weja'},
    'title': 'Manual Estimate',
    'transport_cost': Decimal('0.00'),
    'remarks': '',
    'profit': Decimal('500.00'),
    'materials': [
        
        {"name": "Red chippings", "unit_price": Decimal("40.00"), "quantity": Decimal("40.00")},
        {"name": "White chippings", "unit_price": Decimal("100.00"), "quantity": Decimal("20.00")},
        {"name": "Cement", "unit_price": Decimal("120.00"), "quantity": Decimal("46.00")},
        {"name": "Rubber Strips", "unit_price": Decimal("30.00"), "quantity": Decimal("80.00")},
        {"name": "Sea Pebbles", "unit_price": Decimal("25.00"), "quantity": Decimal("110.00")},
        {"name": "Acid liquid", "unit_price": Decimal("500.00"), "quantity": Decimal("1.00")},
        
        ],
    'labour': [{'role': 'Master', 'count': 5, 'rate': Decimal('3600.00'), 'rate_type': 'daily'}],
    'estimated_days': Decimal('0.00'),
    'user': {'phone': '0245702875'},
}

PRIMARY_COLOR = (30, 60, 150)
HEADER_FILL = (220, 230, 250)
ROW_FILL_1 = (245, 250, 255)
ROW_FILL_2 = (255, 255, 255)
HIGHLIGHT_FILL = (200, 220, 255)

current_date = datetime.now().strftime('%B %d, %Y')
estimate_number = "GH-0045334"

class ProfessionalEstimatePDF(FPDF):
    def header(self):
        self.set_fill_color(*PRIMARY_COLOR)
        self.set_text_color(255, 255, 255)
        self.set_font('Arial', 'B', 16)
        self.cell(0, 12, 'TONYKWART VENTURES', ln=True, align='C', fill=True)

        self.set_text_color(0)
        self.set_font('Arial', '', 11)
        self.cell(0, 8, f"Contact: {estimate_data['user']['phone']} | Location: {estimate_data['customer']['location']}", ln=True, align='C')
        self.cell(0, 8, f'Estimate No: {estimate_number} | Date: {current_date}', ln=True, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

pdf = ProfessionalEstimatePDF()
pdf.add_page()
pdf.set_auto_page_break(auto=True, margin=15)

# Customer Info Section
pdf.set_font('Arial', 'B', 12)
pdf.cell(0, 10, f"Customer: {estimate_data['customer']['name']} | Phone: {estimate_data['customer']['phone']}", ln=True)
pdf.ln(3)

# Materials Section
pdf.set_fill_color(*HEADER_FILL)
pdf.set_font('Arial', 'B', 12)
pdf.cell(0, 10, 'Materials & Equipment Costs', ln=True, fill=True)

pdf.set_font('Arial', 'B', 11)
pdf.set_fill_color(*PRIMARY_COLOR)
pdf.set_text_color(255, 255, 255)
headers = ['Item', 'Quantity', 'Unit Cost (Cedis)', 'Total Cost (Cedis)']
widths = [60, 40, 45, 45]
for header, width in zip(headers, widths):
    pdf.cell(width, 10, header, 1, 0, 'C', True)
pdf.ln()

pdf.set_font('Arial', '', 11)
pdf.set_text_color(0)

material_total = Decimal('0.00')
fill = False
for mat in estimate_data['materials']:
    quantity = mat['quantity']
    unit_price = mat['unit_price']
    total = quantity * unit_price
    material_total += total

    fill_color = ROW_FILL_1 if fill else ROW_FILL_2
    pdf.set_fill_color(*fill_color)
    row = [mat['name'], str(quantity), f"{unit_price:.2f}", f"{total:.2f}"]
    for i, value in enumerate(row):
        pdf.cell(widths[i], 10, value, 1, 0, 'C', True)
    pdf.ln()
    fill = not fill

# Subtotal
pdf.set_font('Arial', 'B', 11)
pdf.set_fill_color(*HIGHLIGHT_FILL)
pdf.cell(sum(widths[:3]), 10, 'Subtotal (Materials & Equipment):', 1, 0, 'R', True)
pdf.cell(widths[3], 10, f"{material_total:.2f}", 1, 1, 'C', True)

# Labour Section
pdf.ln(5)
pdf.set_fill_color(*HEADER_FILL)
pdf.set_font('Arial', 'B', 12)
pdf.cell(0, 10, 'Workmanship', ln=True, fill=True)

labour_total = Decimal('0.00')
pdf.set_font('Arial', '', 11)


# Transport & Profit
transport_cost = estimate_data['transport_cost']
profit = estimate_data['profit']
grand_total = 22970.00

def add_cost_row(label, amount,unit):
    pdf.set_font('Arial', '', 11)
    pdf.set_fill_color(*HIGHLIGHT_FILL)
    pdf.cell(sum(widths[:3]), 10, label, 1, 0, 'R', True)
    pdf.cell(widths[3], 10, f"{amount:.2f} {unit}", 1, 1, 'C', True)

add_cost_row("Transport", 0.00,'****')
add_cost_row("Total Area ", 185.00,'Meter Squared')
add_cost_row("Total Labour cost ", 8200.00,'')
add_cost_row("Subtotal (Materials + Labour):", 22970.00,'')

# Grand Total*

pdf.ln(5)
pdf.set_font('Arial', 'B', 12)
pdf.set_fill_color(180, 200, 255)
pdf.cell(sum(widths[:3]), 10, 'Grand Total Estimate:', 1, 0, 'R', True)
pdf.cell(widths[3], 10, f"{grand_total:.2f}", 1, 1, 'C', True)

# Remarks
pdf.ln(10)
pdf.set_font('Arial', 'B', 12)
pdf.cell(0, 10, 'Remarks:', ln=True)
pdf.set_font('Arial', '', 11)
remarks = estimate_data.get("remarks") or "- Thank you for doing business with us."
pdf.multi_cell(0, 8, remarks)

# Save the PDF
pdf.output("tonykwart ventures.pdf")
