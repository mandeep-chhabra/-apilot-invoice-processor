"""Generate properly formatted sample invoice PDFs - 5 correct, 5 wrong customer names."""
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime
from decimal import Decimal
import os

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'apilot', 'fixtures')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Styles
styles = getSampleStyleSheet()
title_style = styles['Heading1']
title_style.fontSize = 18
title_style.alignment = 1  # Center

normal_style = styles['Normal']
normal_style.fontSize = 10

# Vendor data (short addresses to avoid overflow)
VENDORS = {
    "acme": ("Acme Supplies Ltd", "123 Industrial Area, Mumbai", "Tax: 12345678901"),
    "tech": ("Tech Solutions Inc", "456 Tech Park, Bangalore", "Tax: 98765432109"),
    "global": ("Global Logistics", "789 Shipping Lane, Chennai", "Tax: 55555555555"),
    "office": ("Office Essentials", "321 Commercial St, Delhi", "Tax: 44444444444"),
    "xyz": ("XYZ Corporation", "999 Blocked Zone, Hyderabad", "Tax: 33333333333"),
}

CUSTOMERS = {
    "correct1": "TechCorp India Pvt Ltd",
    "correct2": "TechCorp India Pvt Ltd",
    "correct3": "TechCorp India Pvt Ltd",
    "correct4": "TechCorp India Pvt Ltd",
    "correct5": "TechCorp India Pvt Ltd",
    "wrong1": "Wrong Customer Corp",
    "wrong2": "Unknown Company LLC",
    "wrong3": "Random Customer Corp",
    "wrong4": "Fake Business Ltd",
    "wrong5": "Nonexistent Inc",
}


def create_invoice(filename, vendor_name, vendor_addr, invoice_num, invoice_date, due_date,
                   po_ref, customer_name, items, subtotal, tax_rate, shipping, discount):
    """Create a properly formatted invoice PDF without text overflow."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(filepath, pagesize=A4, leftMargin=20, rightMargin=20, topMargin=30, bottomMargin=30)

    story = []

    # Calculate totals
    tax_amount = subtotal * (Decimal(str(tax_rate)) / Decimal("100"))
    total = subtotal + tax_amount + shipping - discount

    # Title
    story.append(Paragraph("INVOICE", title_style))
    story.append(Paragraph("<br/><br/>", normal_style))

    # Header table - compact layout
    header_data = [
        ["FROM:", invoice_num, "DATE:", invoice_date],
        [vendor_name, "", "DUE:", due_date],
        [vendor_addr, "", "PO:", po_ref or "N/A"],
        ["", "", "TAX:", f"{tax_rate}%"],
    ]

    t = Table(header_data, colWidths=[60, 150, 40, 150])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Paragraph("<br/>", normal_style))

    # Bill To
    story.append(Paragraph("BILL TO:", normal_style))
    story.append(Paragraph(f"<b>{customer_name}</b>", normal_style))
    story.append(Paragraph("<br/>", normal_style))

    # Line items
    item_data = [["Description", "Qty", "Rate", "Amount"]]
    for item in items:
        amount = item['qty'] * item['rate']
        item_data.append([
            item['desc'][:40],  # Truncate to prevent overflow
            str(item['qty']),
            f"{item['rate']:.2f}",
            f"{amount:.2f}"
        ])

    t = Table(item_data, colWidths=[200, 30, 60, 60])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Paragraph("<br/>", normal_style))

    # Totals
    totals_data = [
        ["Subtotal:", f"{subtotal:.2f}"],
        [f"Tax ({tax_rate}%):", f"{tax_amount:.2f}"],
        ["Shipping:", f"{shipping:.2f}"],
        ["Discount:", f"-{discount:.2f}"],
        ["TOTAL:", f"{total:.2f}"],
    ]

    t = Table(totals_data, colWidths=[250, 100])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Paragraph("<br/><br/>", normal_style))

    # Payment terms
    story.append(Paragraph("Payment Terms: Net 30", normal_style))
    story.append(Paragraph("Thank you for your business!", normal_style))

    doc.build(story)
    return filepath


def main():
    print("=" * 60)
    print("GENERATING 10 SAMPLE INVOICES")
    print("5 Correct Customer Names + 5 Wrong Customer Names")
    print("=" * 60)

    invoice_date = "2024-01-15"
    due_date = "2024-02-14"

    # 5 CORRECT customer names
    print("\n--- 5 CORRECT Customer Names ---")

    # 1. Clean invoice
    create_invoice(
        filename="01_correct_clean_invoice.pdf",
        vendor_name=VENDORS["acme"][0],
        vendor_addr=VENDORS["acme"][1],
        invoice_num="INV-2024-1001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-001",
        customer_name=CUSTOMERS["correct1"],
        items=[{'desc': "Office Paper A4", 'qty': 50, 'rate': Decimal("200.00")},
               {'desc': "Ball Point Pens Blue", 'qty': 100, 'rate': Decimal("15.00")}],
        subtotal=Decimal("11500.00"),
        tax_rate=18,
        shipping=Decimal("500.00"),
        discount=Decimal("0.00")
    )
    print("  01_correct_clean_invoice.pdf -> CORRECT: Clean invoice")

    # 2. Missing PO reference
    create_invoice(
        filename="02_correct_missing_po.pdf",
        vendor_name=VENDORS["tech"][0],
        vendor_addr=VENDORS["tech"][1],
        invoice_num="INV-2024-2001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref=None,  # Missing PO
        customer_name=CUSTOMERS["correct2"],
        items=[{'desc': "IT Support Services", 'qty': 40, 'rate': Decimal("1500.00")}],
        subtotal=Decimal("60000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("0.00")
    )
    print("  02_correct_missing_po.pdf -> CORRECT: Missing PO reference")

    # 3. Split invoice (partial)
    create_invoice(
        filename="03_correct_split_invoice.pdf",
        vendor_name=VENDORS["tech"][0],
        vendor_addr=VENDORS["tech"][1],
        invoice_num="INV-2024-2002",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-002",
        customer_name=CUSTOMERS["correct3"],
        items=[{'desc': "IT Laptops Partial", 'qty': 2, 'rate': Decimal("25000.00")}],
        subtotal=Decimal("50000.00"),
        tax_rate=18,
        shipping=Decimal("500.00"),
        discount=Decimal("0.00")
    )
    print("  03_correct_split_invoice.pdf -> CORRECT: Split invoice (partial PO)")

    # 4. With discount
    create_invoice(
        filename="04_correct_with_discount.pdf",
        vendor_name=VENDORS["global"][0],
        vendor_addr=VENDORS["global"][1],
        invoice_num="INV-2024-3001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-003",
        customer_name=CUSTOMERS["correct4"],
        items=[{'desc': "Logistics Services Q1", 'qty': 1, 'rate': Decimal("45000.00")}],
        subtotal=Decimal("45000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("5000.00")
    )
    print("  04_correct_with_discount.pdf -> CORRECT: With discount")

    # 5. Multiple line items
    create_invoice(
        filename="05_correct_multiple_items.pdf",
        vendor_name=VENDORS["office"][0],
        vendor_addr=VENDORS["office"][1],
        invoice_num="INV-2024-4001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-004",
        customer_name=CUSTOMERS["correct5"],
        items=[{'desc': "Office Chairs", 'qty': 10, 'rate': Decimal("2500.00")},
               {'desc': "Office Desks", 'qty': 5, 'rate': Decimal("4000.00")}],
        subtotal=Decimal("45000.00"),
        tax_rate=18,
        shipping=Decimal("1000.00"),
        discount=Decimal("0.00")
    )
    print("  05_correct_multiple_items.pdf -> CORRECT: Multiple line items")

    # 5 WRONG customer names
    print("\n--- 5 WRONG Customer Names ---")

    # 1. Duplicate invoice
    create_invoice(
        filename="06_wrong_duplicate.pdf",
        vendor_name=VENDORS["acme"][0],
        vendor_addr=VENDORS["acme"][1],
        invoice_num="INV-2024-1001",  # Same as scenario 1
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-001",
        customer_name=CUSTOMERS["wrong1"],
        items=[{'desc': "Office Paper A4", 'qty': 50, 'rate': Decimal("200.00")}],
        subtotal=Decimal("10000.00"),
        tax_rate=18,
        shipping=Decimal("250.00"),
        discount=Decimal("0.00")
    )
    print("  06_wrong_duplicate.pdf -> WRONG: Duplicate invoice number")

    # 2. Amount exceeds PO
    create_invoice(
        filename="07_wrong_amount_exceeds.pdf",
        vendor_name=VENDORS["acme"][0],
        vendor_addr=VENDORS["acme"][1],
        invoice_num="INV-2024-1003",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-001",
        customer_name=CUSTOMERS["wrong2"],
        items=[{'desc': "Bulk Order Large Qty", 'qty': 400, 'rate': Decimal("300.00")}],
        subtotal=Decimal("120000.00"),
        tax_rate=18,
        shipping=Decimal("1500.00"),
        discount=Decimal("0.00")
    )
    print("  07_wrong_amount_exceeds.pdf -> WRONG: Amount exceeds PO balance")

    # 3. Blocked vendor
    create_invoice(
        filename="08_wrong_blocked_vendor.pdf",
        vendor_name=VENDORS["xyz"][0],  # BLOCKED
        vendor_addr=VENDORS["xyz"][1],
        invoice_num="INV-2024-4001",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="N/A",
        customer_name=CUSTOMERS["wrong3"],
        items=[{'desc': "Blocked Vendor Svc", 'qty': 1, 'rate': Decimal("50000.00")}],
        subtotal=Decimal("50000.00"),
        tax_rate=18,
        shipping=Decimal("1000.00"),
        discount=Decimal("0.00")
    )
    print("  08_wrong_blocked_vendor.pdf -> WRONG: Blocked vendor")

    # 4. Missing invoice number
    create_invoice(
        filename="09_wrong_missing_invnum.pdf",
        vendor_name=VENDORS["office"][0],
        vendor_addr=VENDORS["office"][1],
        invoice_num="",  # Missing invoice number
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-004",
        customer_name=CUSTOMERS["wrong4"],
        items=[{'desc': "Office Supplies", 'qty': 20, 'rate': Decimal("500.00")}],
        subtotal=Decimal("10000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("0.00")
    )
    print("  09_wrong_missing_invnum.pdf -> WRONG: Missing invoice number")

    # 5. Wrong customer name
    create_invoice(
        filename="10_wrong_customer.pdf",
        vendor_name=VENDORS["global"][0],
        vendor_addr=VENDORS["global"][1],
        invoice_num="INV-2024-3002",
        invoice_date=invoice_date,
        due_date=due_date,
        po_ref="PO-2024-003",
        customer_name=CUSTOMERS["wrong5"],
        items=[{'desc': "Logistics Extra Svc", 'qty': 1, 'rate': Decimal("25000.00")}],
        subtotal=Decimal("25000.00"),
        tax_rate=18,
        shipping=Decimal("0.00"),
        discount=Decimal("0.00")
    )
    print("  10_wrong_customer.pdf -> WRONG: Wrong customer name")

    print("\n" + "=" * 60)
    print("ALL 10 INVOICES GENERATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\nLocation: {OUTPUT_DIR}")
    print("\nCorrect Customer (5):")
    print("  01 - Clean invoice")
    print("  02 - Missing PO reference")
    print("  03 - Split invoice (partial)")
    print("  04 - With discount")
    print("  05 - Multiple line items")
    print("\nWrong Customer (5):")
    print("  06 - Duplicate invoice number")
    print("  07 - Amount exceeds PO balance")
    print("  08 - Blocked vendor")
    print("  09 - Missing invoice number")
    print("  10 - Wrong customer name")
    print("\nAll PDFs properly formatted without text overflow!")
    print("=" * 60)

if __name__ == "__main__":
    main()