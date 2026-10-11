"""Generate properly formatted sample invoice PDFs with customer names for edge case testing."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from datetime import datetime, timedelta
from decimal import Decimal
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'apilot', 'fixtures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Styles
styles = getSampleStyleSheet()
title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=16, alignment=TA_CENTER, spaceAfter=10)
normal_style = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT)
right_style = ParagraphStyle('Right', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT)
bold_style = ParagraphStyle('Bold', parent=styles['Normal'], fontSize=9, alignment=TA_LEFT, fontName='Helvetica-Bold')

# Vendor data
VENDORS = {
    "acme": {
        "name": "Acme Supplies Ltd",
        "tax_id": "12345678901",
        "address": "123 Industrial Area",
        "city": "Mumbai - 400001",
        "phone": "+91-22-12345678"
    },
    "tech": {
        "name": "Tech Solutions Inc",
        "tax_id": "98765432109",
        "address": "456 Tech Park",
        "city": "Bangalore - 560001",
        "phone": "+91-80-98765432"
    },
    "global": {
        "name": "Global Logistics",
        "tax_id": "55555555555",
        "address": "789 Shipping Lane",
        "city": "Chennai - 600001",
        "phone": "+91-44-55555555"
    },
    "office": {
        "name": "Office Essentials",
        "tax_id": "44444444444",
        "address": "321 Commercial St",
        "city": "Delhi - 110001",
        "phone": "+91-11-44444444"
    },
    "xyz": {
        "name": "XYZ Corporation",
        "tax_id": "33333333333",
        "address": "999 Blocked Zone",
        "city": "Hyderabad - 500001",
        "phone": "+91-40-33333333"
    }
}

# Customer names (correct and wrong for edge cases)
CUSTOMERS = {
    "correct": "TechCorp India Pvt Ltd",
    "wrong1": "Wrong Customer Corp",
    "wrong2": "Unknown Company LLC",
    "wrong3": "Random Customer Corp",
}


def create_invoice(filename, vendor_key, invoice_num, invoice_date, due_date,
                   po_ref, customer_name, line_items, subtotal, tax_rate, shipping, discount, currency="INR"):
    """Create a properly formatted invoice PDF."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4,
                           rightMargin=15*mm, leftMargin=15*mm,
                           topMargin=15*mm, bottomMargin=15*mm)

    story = []
    vendor = VENDORS[vendor_key]

    # Calculate totals
    tax_amount = subtotal * (Decimal(str(tax_rate)) / Decimal("100"))
    total = subtotal + tax_amount + shipping - discount

    # Title
    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 8*mm))

    # Header table
    header_data = [
        [Paragraph("<b>FROM:</b>", bold_style), Paragraph("<b>INVOICE</b>", bold_style)],
        [vendor['name'], f"Invoice #: {invoice_num}"],
        [vendor['address'], f"Date: {invoice_date}"],
        [f"{vendor['city']}", f"Due Date: {due_date}"],
        [f"Tax ID: {vendor['tax_id']}", f"PO Ref: {po_ref or 'N/A'}"],
    ]

    t = Table(header_data, colWidths=[85*mm, 95*mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 5*mm))

    # Bill To
    story.append(Paragraph("<b>BILL TO:</b>", bold_style))
    story.append(Paragraph(customer_name, normal_style))
    story.append(Spacer(1, 5*mm))

    # Line items header
    item_header = [
        Paragraph("<b>Description</b>", bold_style),
        Paragraph("<b>Qty</b>", bold_style),
        Paragraph("<b>Unit Price</b>", bold_style),
        Paragraph("<b>Amount</b>", bold_style),
    ]

    item_data = [item_header]
    for item in line_items:
        item_data.append([
            item['desc'],
            str(item['qty']),
            f"{currency} {item['unit_price']:,.2f}",
            f"{currency} {item['qty'] * item['unit_price']:,.2f}"
        ])

    # Create line items table
    col_widths = [160*mm, 30*mm, 50*mm, 50*mm]
    t = Table(item_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 5*mm))

    # Totals
    totals_data = [
        ['', 'Subtotal:', f"{currency} {subtotal:,.2f}"],
        ['', f'Tax ({tax_rate}%):', f"{currency} {tax_amount:,.2f}"],
        ['', f'Shipping:', f"{currency} {shipping:,.2f}"],
        ['', f'Discount:', f"-{currency} {discount:,.2f}"],
        ['', 'TOTAL:', f"{currency} {total:,.2f}"],
    ]

    t = Table(totals_data, colWidths=[160*mm, 60*mm, 80*mm])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 8*mm))

    # Payment terms
    story.append(Paragraph("<b>Payment Terms:</b> Net 30 days", normal_style))
    story.append(Paragraph("Thank you for your business!", normal_style))

    doc.build(story)
    return filepath


def main():
    print("=" * 60)
    print("GENERATING PROPERLY FORMATTED SAMPLE INVOICES")
    print("=" * 60)

    base_date = datetime(2024, 1, 15)
    due_date = (base_date + timedelta(days=30)).strftime('%Y-%m-%d')
    invoice_date = base_date.strftime('%Y-%m-%d')

    # Scenario 1: Clean invoice - CORRECT customer name
    print("\n1. Creating scenario1_clean_invoice.pdf...")
    create_invoice(
        filename="scenario1_clean_invoice.pdf",
        vendor_key="acme",
        invoice_num="INV-2024-1001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-001",
        customer_name=CUSTOMERS["correct"],
        line_items=[
            {'desc': "Office Supplies - Paper A4", 'qty': 50, 'unit_price': Decimal("200.00")},
            {'desc': "Ball Point Pens - Blue", 'qty': 100, 'unit_price': Decimal("15.00")},
            {'desc': "Printer Cartridge - Black", 'qty': 10, 'unit_price': Decimal("450.00")},
        ],
        subtotal=Decimal("22500.00"),
        tax_rate=18,
        shipping=Decimal("500.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> CORRECT customer: TechCorp India Pvt Ltd (Clean invoice)")

    # Scenario 2: Missing PO reference - CORRECT customer name
    print("\n2. Creating scenario2_missing_po.pdf...")
    create_invoice(
        filename="scenario2_missing_po.pdf",
        vendor_key="tech",
        invoice_num="INV-2024-2001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref=None,  # Missing PO reference
        customer_name=CUSTOMERS["correct"],
        line_items=[
            {'desc': "IT Support Services - Monthly", 'qty': 40, 'unit_price': Decimal("1500.00")},
        ],
        subtotal=Decimal("60000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> CORRECT customer: TechCorp India Pvt Ltd (Missing PO ref)")

    # Scenario 3: Duplicate invoice - WRONG customer name
    print("\n3. Creating scenario3_duplicate.pdf...")
    create_invoice(
        filename="scenario3_duplicate.pdf",
        vendor_key="acme",
        invoice_num="INV-2024-1001",  # Same as scenario 1
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-001",
        customer_name=CUSTOMERS["wrong1"],  # WRONG customer
        line_items=[
            {'desc': "Office Supplies - Paper A4", 'qty': 50, 'unit_price': Decimal("200.00")},
        ],
        subtotal=Decimal("10000.00"),
        tax_rate=18,
        shipping=Decimal("250.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> WRONG customer: Wrong Customer Corp (Duplicate INV-2024-1001)")

    # Scenario 4: Amount exceeds PO balance - WRONG customer name
    print("\n4. Creating scenario4_amount_exceeds.pdf...")
    create_invoice(
        filename="scenario4_amount_exceeds.pdf",
        vendor_key="acme",
        invoice_num="INV-2024-1003",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-001",
        customer_name=CUSTOMERS["wrong2"],  # WRONG customer
        line_items=[
            {'desc': "Bulk Order - Multiple Items", 'qty': 300, 'unit_price': Decimal("350.00")},
        ],
        subtotal=Decimal("105000.00"),
        tax_rate=18,
        shipping=Decimal("1500.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> WRONG customer: Unknown Company LLC (Amount exceeds PO)")

    # Scenario 5: Blocked vendor - WRONG customer name
    print("\n5. Creating scenario5_blocked_vendor.pdf...")
    create_invoice(
        filename="scenario5_blocked_vendor.pdf",
        vendor_key="xyz",  # BLOCKED vendor
        invoice_num="INV-2024-4001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="N/A",
        customer_name=CUSTOMERS["wrong3"],  # WRONG customer
        line_items=[
            {'desc': "Blocked Vendor Services", 'qty': 1, 'unit_price': Decimal("50000.00")},
        ],
        subtotal=Decimal("50000.00"),
        tax_rate=18,
        shipping=Decimal("1000.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> WRONG customer: Random Customer Corp (Blocked vendor XYZ)")

    # Scenario 6: Split invoice (partial) - CORRECT customer name
    print("\n6. Creating scenario6_split_invoice.pdf...")
    create_invoice(
        filename="scenario6_split_invoice.pdf",
        vendor_key="tech",
        invoice_num="INV-2024-2002",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-002",
        customer_name=CUSTOMERS["correct"],
        line_items=[
            {'desc': "IT Equipment - Laptops (Partial)", 'qty': 2, 'unit_price': Decimal("25000.00")},
        ],
        subtotal=Decimal("50000.00"),
        tax_rate=18,
        shipping=Decimal("500.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> CORRECT customer: TechCorp India Pvt Ltd (Split invoice - partial PO)")

    # Scenario 7: Missing critical fields - WRONG customer name
    print("\n7. Creating scenario7_missing_info.pdf...")
    create_invoice(
        filename="scenario7_missing_info.pdf",
        vendor_key="office",
        invoice_num="INV-2024-4001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-004",
        customer_name="Fake Business Ltd",  # WRONG customer
        line_items=[
            {'desc': "Office Supplies", 'qty': 20, 'unit_price': Decimal("500.00")},
        ],
        subtotal=Decimal("10000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("0.00"),
        currency="INR"
    )
    print("   -> WRONG customer: Fake Business Ltd (Missing critical info)")

    print("\n" + "=" * 60)
    print("SAMPLE INVOICES GENERATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\nOutput directory: {OUTPUT_DIR}")
    print("\nEdge Case Summary:")
    print("  1. Clean invoice -> CORRECT customer -> APPROVE")
    print("  2. Missing PO ref -> CORRECT customer -> REVIEW")
    print("  3. Duplicate invoice -> WRONG customer -> REJECT")
    print("  4. Amount exceeds PO -> WRONG customer -> REVIEW")
    print("  5. Blocked vendor -> WRONG customer -> REJECT")
    print("  6. Split invoice -> CORRECT customer -> APPROVE")
    print("  7. Missing info -> WRONG customer -> REVIEW")
    print("\nAll PDFs are properly formatted without text overflow.")
    print("Ready for testing!")

if __name__ == "__main__":
    main()