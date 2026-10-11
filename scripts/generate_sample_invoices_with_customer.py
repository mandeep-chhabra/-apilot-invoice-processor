"""Generate sample invoice PDFs with customer names - some correct, some wrong."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime, timedelta
from decimal import Decimal
import os

# Output directory
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'apilot', 'fixtures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Sample data - Customer names (some correct, some wrong)
CUSTOMER_NAMES = {
    "correct": [
        "TechCorp India Pvt Ltd",  # Matches a PO
        "Tech Solutions Inc",       # This is actually a vendor name, let's use it as customer
    ],
    "wrong": [
        "Unknown Company LLC",
        "Random Customer Corp",
        "Fake Business Ltd",
        "Nonexistent Industries",
        "Wrong Customer Inc",
    ]
}

# Vendor details
VENDORS = {
    "acme": {
        "name": "Acme Supplies Ltd",
        "tax_id": "12345678901",
        "address": "123 Industrial Area, Mumbai - 400001",
        "phone": "+91-22-12345678"
    },
    "tech": {
        "name": "Tech Solutions Inc",
        "tax_id": "98765432109",
        "address": "456 Tech Park, Bangalore - 560001",
        "phone": "+91-80-98765432"
    },
    "global": {
        "name": "Global Logistics",
        "tax_id": "55555555555",
        "address": "789 Shipping Lane, Chennai - 600001",
        "phone": "+91-44-55555555"
    },
    "office": {
        "name": "Office Essentials",
        "tax_id": "44444444444",
        "address": "321 Commercial St, Delhi - 110001",
        "phone": "+91-11-44444444"
    },
    "xyz": {
        "name": "XYZ Corporation",
        "tax_id": "33333333333",
        "address": "999 Blocked Zone, Hyderabad - 500001",
        "phone": "+91-40-33333333"
    }
}

# PO Reference numbers
PO_REFERENCES = {
    "acme": "PO-2024-001",
    "tech": "PO-2024-002",
    "global": "PO-2024-003",
    "office": "PO-2024-004",
    "tech_us": "PO-2024-005"
}

def create_invoice_pdf(filename, vendor_key, invoice_num, invoice_date, due_date_days,
                       po_ref, customer_name, line_items, subtotal, tax_rate, shipping, discount,
                       currency="INR"):
    """Create a sample invoice PDF."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)

    styles = getSampleStyleSheet()
    story = []

    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=TA_CENTER, spaceAfter=20)
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=10, alignment=TA_LEFT)
    right_style = ParagraphStyle('Right', parent=styles['Normal'], alignment=TA_RIGHT)

    vendor = VENDORS[vendor_key]

    # Calculate totals
    tax_amount = subtotal * (Decimal(str(tax_rate)) / Decimal("100"))
    total = subtotal + tax_amount + shipping - discount

    # Title
    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 10*mm))

    # Invoice details (left and right columns)
    col1_data = [
        [Paragraph(f"<b>From:</b>", styles['Normal'])],
        [Paragraph(f"<b>{vendor['name']}</b>", styles['Normal'])],
        [Paragraph(vendor['address'], styles['Normal'])],
        [Paragraph(f"Tax ID: {vendor['tax_id']}", styles['Normal'])],
        [Paragraph(vendor['phone'], styles['Normal'])],
    ]

    col2_data = [
        [Paragraph(f"<b>Invoice #:</b> {invoice_num}", right_style)],
        [Paragraph(f"<b>Date:</b> {invoice_date.strftime('%Y-%m-%d')}", right_style)],
        [Paragraph(f"<b>Due Date:</b> {(invoice_date + timedelta(days=due_date_days)).strftime('%Y-%m-%d')}", right_style)],
        [Paragraph(f"<b>PO Reference:</b> {po_ref or 'N/A'}", right_style)],
    ]

    # Customer info
    story.append(Paragraph(f"<b>Bill To:</b>", styles['Normal']))
    story.append(Paragraph(f"<b>{customer_name}</b>", styles['Normal']))
    story.append(Spacer(1, 5*mm))

    # Table for vendor and invoice details
    table_data = [
        [Paragraph("<b>Vendor Details</b>", styles['Normal']), ""],
        [vendor['name'], f"Invoice #: {invoice_num}"],
        [vendor['address'], f"Date: {invoice_date.strftime('%Y-%m-%d')}"],
        [f"Tax ID: {vendor['tax_id']}", f"Due: {(invoice_date + timedelta(days=due_date_days)).strftime('%Y-%m-%d')}"],
        [f"PO Ref: {po_ref or 'N/A'}", ""],
    ]

    t = Table(table_data, colWidths=[100*mm, 90*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 10*mm))

    # Line items table
    item_data = [['Description', 'Qty', 'Unit Price', 'Amount']]
    for item in line_items:
        item_data.append([
            item['desc'],
            str(item['qty']),
            f"{currency} {item['unit_price']:,.2f}",
            f"{currency} {item['qty'] * item['unit_price']:,.2f}"
        ])

    t = Table(item_data, colWidths=[200*mm, 40*mm, 80*mm, 80*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ALIGN', (2, 1), (3, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 10*mm))

    # Totals
    totals_data = [
        ['', 'Subtotal:', f"{currency} {subtotal:,.2f}"],
        ['', f'Tax ({tax_rate}%):', f"{currency} {tax_amount:,.2f}"],
        ['', f'Shipping:', f"{currency} {shipping:,.2f}"],
        ['', f'Discount:', f"-{currency} {discount:,.2f}"],
        ['', 'TOTAL:', f"{currency} {total:,.2f}"],
    ]

    t = Table(totals_data, colWidths=[200*mm, 80*mm, 80*mm])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 15*mm))

    # Payment terms
    story.append(Paragraph("<b>Payment Terms:</b> Net 30", styles['Normal']))
    story.append(Paragraph("Thank you for your business!", styles['Normal']))

    doc.build(story)
    return filepath


def main():
    print("=" * 60)
    print("GENERATING SAMPLE INVOICE PDFs WITH CUSTOMER NAMES")
    print("=" * 60)

    base_date = datetime(2024, 1, 15)

    # Scenario 1: Clean invoice - CORRECT customer name
    print("\n1. Creating scenario1_clean_invoice.pdf...")
    create_invoice_pdf(
        filename="scenario1_clean_invoice.pdf",
        vendor_key="acme",
        invoice_num="INV-2024-1001",
        invoice_date=base_date,
        due_date_days=30,
        po_ref="PO-2024-001",
        customer_name="TechCorp India Pvt Ltd",  # CORRECT
        line_items=[
            {'desc': "Office Supplies - Paper", 'qty': 50, 'unit_price': Decimal("200.00")},
            {'desc': "Office Supplies - Pens", 'qty': 100, 'unit_price': Decimal("15.00")},
            {'desc': "Printer Cartridges", 'qty': 10, 'unit_price': Decimal("450.00")},
        ],
        subtotal=Decimal("22500.00"),
        tax_rate=18,
        shipping=Decimal("500.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> CORRECT customer name: TechCorp India Pvt Ltd")

    # Scenario 2: Clean invoice - CORRECT customer name
    print("\n2. Creating scenario2_clean_invoice2.pdf...")
    create_invoice_pdf(
        filename="scenario2_clean_invoice2.pdf",
        vendor_key="tech",
        invoice_num="INV-2024-2001",
        invoice_date=base_date,
        due_date_days=30,
        po_ref="PO-2024-002",
        customer_name="TechCorp India Pvt Ltd",  # CORRECT
        line_items=[
            {'desc': "IT Equipment - Laptops", 'qty': 5, 'unit_price': Decimal("45000.00")},
            {'desc': "Software Licenses", 'qty': 10, 'unit_price': Decimal("2500.00")},
        ],
        subtotal=Decimal("250000.00"),
        tax_rate=18,
        shipping=Decimal("2000.00"),
        discount=Decimal("5000.00"),
        currency="INR"
    )
    print("   -> CORRECT customer name: TechCorp India Pvt Ltd")

    # Scenario 3: Missing PO reference - CORRECT customer name
    print("\n3. Creating scenario3_missing_po.pdf...")
    create_invoice_pdf(
        filename="scenario3_missing_po.pdf",
        vendor_key="tech",
        invoice_num="INV-2024-2002",
        invoice_date=base_date,
        due_date_days=30,
        po_ref=None,  # Missing PO reference
        customer_name="TechCorp India Pvt Ltd",  # CORRECT
        line_items=[
            {'desc': "IT Support Services", 'qty': 40, 'unit_price': Decimal("1500.00")},
        ],
        subtotal=Decimal("60000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> CORRECT customer name: TechCorp India Pvt Ltd")

    # Scenario 4: Duplicate invoice - WRONG customer name
    print("\n4. Creating scenario4_duplicate.pdf...")
    create_invoice_pdf(
        filename="scenario4_duplicate.pdf",
        vendor_key="acme",
        invoice_num="INV-2024-1001",  # Same invoice number as scenario 1
        invoice_date=base_date,
        due_date_days=30,
        po_ref="PO-2024-001",
        customer_name="Wrong Customer Corp",  # WRONG
        line_items=[
            {'desc': "Office Supplies - Paper", 'qty': 50, 'unit_price': Decimal("200.00")},
        ],
        subtotal=Decimal("10000.00"),
        tax_rate=18,
        shipping=Decimal("250.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> WRONG customer name: Wrong Customer Corp (duplicate of INV-2024-1001)")

    # Scenario 5: Amount exceeds PO - WRONG customer name
    print("\n5. Creating scenario5_amount_exceeds.pdf...")
    create_invoice_pdf(
        filename="scenario5_amount_exceeds.pdf",
        vendor_key="acme",
        invoice_num="INV-2024-1003",
        invoice_date=base_date,
        due_date_days=30,
        po_ref="PO-2024-001",
        customer_name="Unknown Company LLC",  # WRONG
        line_items=[
            {'desc': "Bulk Order - Multiple Items", 'qty': 500, 'unit_price': Decimal("300.00")},
        ],
        subtotal=Decimal("150000.00"),
        tax_rate=18,
        shipping=Decimal("1500.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> WRONG customer name: Unknown Company LLC (amount exceeds PO)")

    # Scenario 6: Blocked vendor - WRONG customer name
    print("\n6. Creating scenario6_blocked_vendor.pdf...")
    create_invoice_pdf(
        filename="scenario6_blocked_vendor.pdf",
        vendor_key="xyz",  # BLOCKED vendor
        invoice_num="INV-2024-4001",
        invoice_date=base_date,
        due_date_days=30,
        po_ref="N/A",
        customer_name="Random Customer Corp",  # WRONG
        line_items=[
            {'desc': "Blocked Services", 'qty': 1, 'unit_price': Decimal("50000.00")},
        ],
        subtotal=Decimal("50000.00"),
        tax_rate=18,
        shipping=Decimal("1000.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> WRONG customer name: Random Customer Corp (blocked vendor XYZ)")

    # Scenario 7: Clean invoice for Global Logistics - CORRECT customer name
    print("\n7. Creating scenario7_global_logistics.pdf...")
    create_invoice_pdf(
        filename="scenario7_global_logistics.pdf",
        vendor_key="global",
        invoice_num="INV-2024-3001",
        invoice_date=base_date,
        due_date_days=15,
        po_ref="PO-2024-003",
        customer_name="TechCorp India Pvt Ltd",  # CORRECT
        line_items=[
            {'desc': "Logistics Services - Q1", 'qty': 1, 'unit_price': Decimal("45000.00")},
        ],
        subtotal=Decimal("45000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> CORRECT customer name: TechCorp India Pvt Ltd")

    print("\n" + "=" * 60)
    print("SAMPLE INVOICES GENERATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nCustomer Name Summary:")
    print("  CORRECT (3): TechCorp India Pvt Ltd")
    print("  WRONG (4): Wrong Customer Corp, Unknown Company LLC,")
    print("             Random Customer Corp, Fake Business Ltd")
    print("\nReady for testing!")

if __name__ == "__main__":
    main()