"""
Generate Sample Invoices

Creates PDF sample invoices for demo scenarios using reportlab.
"""
import sys
import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Try to import reportlab, install if not available
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors
except ImportError:
    print("Installing reportlab for PDF generation...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab"])
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors


def create_invoice_pdf(filename, vendor_name, vendor_tax_id, invoice_num, date_str,
                       po_ref, line_items, tax_rate=18, shipping=0, discount=0):
    """Create a sample invoice PDF."""
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 50, "INVOICE")

    # Vendor info
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 100, "From:")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 115, vendor_name)
    c.drawString(50, height - 130, f"Tax ID: {vendor_tax_id}")

    # Invoice details
    c.setFont("Helvetica-Bold", 12)
    c.drawString(400, height - 100, "Invoice Details:")
    c.setFont("Helvetica", 10)
    c.drawString(400, height - 115, f"Invoice #: {invoice_num}")
    c.drawString(400, height - 130, f"Date: {date_str}")
    c.drawString(400, height - 145, f"PO Reference: {po_ref or 'N/A'}")

    # Line items header
    y = height - 200
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Description")
    c.drawString(250, y, "Qty")
    c.drawString(300, y, "Unit Price")
    c.drawString(400, y, "Total")

    c.line(50, y - 5, 550, y - 5)

    # Line items
    y -= 25
    c.setFont("Helvetica", 10)
    subtotal = Decimal("0")

    for item in line_items:
        desc, qty, price = item
        total = Decimal(str(qty)) * Decimal(str(price))
        subtotal += total

        c.drawString(50, y, desc[:40])
        c.drawRightString(290, y, str(qty))
        c.drawRightString(390, y, f"{price:.2f}")
        c.drawRightString(540, y, f"{total:.2f}")
        y -= 20

    # Totals
    y -= 30
    c.drawRightString(450, y, "Subtotal:")
    c.drawRightString(540, y, f"{subtotal:.2f}")

    tax_amount = subtotal * Decimal(tax_rate) / Decimal("100")
    y -= 20
    c.drawRightString(450, y, f"Tax ({tax_rate}%):")
    c.drawRightString(540, y, f"{tax_amount:.2f}")

    if shipping > 0:
        y -= 20
        c.drawRightString(450, y, "Shipping:")
        c.drawRightString(540, y, f"{shipping:.2f}")

    if discount > 0:
        y -= 20
        c.drawRightString(450, y, "Discount:")
        c.drawRightString(540, y, f"-{discount:.2f}")

    total = subtotal + tax_amount + Decimal(str(shipping)) - Decimal(str(discount))
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(450, y, "TOTAL:")
    c.drawRightString(540, y, f"{total:.2f}")

    c.save()


def main():
    """Generate all sample invoice PDFs."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    fixtures_dir.mkdir(exist_ok=True)

    print("Generating sample invoice PDFs...")

    # Scenario 1: Clean invoice (APPROVE)
    create_invoice_pdf(
        str(fixtures_dir / "scenario1_clean_invoice.pdf"),
        vendor_name="Acme Supplies Ltd",
        vendor_tax_id="27AABCU9603R1ZM",
        invoice_num="INV-2024-1001",
        date_str="2024-01-15",
        po_ref="PO-2024-001",
        line_items=[
            ("Office Furniture Set", 10, 5000.00),
            ("Executive Chairs", 5, 10000.00),
        ]
    )
    print("Created: scenario1_clean_invoice.pdf")

    # Scenario 2: Missing PO reference (REVIEW)
    create_invoice_pdf(
        str(fixtures_dir / "scenario2_missing_po_ref.pdf"),
        vendor_name="Tech Solutions Inc",
        vendor_tax_id="29AABCT1234N1ZZ",
        invoice_num="INV-2024-2001",
        date_str="2024-01-20",
        po_ref="",  # Missing!
        line_items=[
            ("Laptop Computers", 10, 10000.00),
        ]
    )
    print("Created: scenario2_missing_po_ref.pdf")

    # Scenario 3: Duplicate (REJECT) - different amount
    create_invoice_pdf(
        str(fixtures_dir / "scenario3_duplicate.pdf"),
        vendor_name="Acme Supplies Ltd",
        vendor_tax_id="27AABCU9603R1ZM",
        invoice_num="INV-2024-1001",  # Same as scenario 1
        date_str="2024-01-15",
        po_ref="PO-2024-001",
        line_items=[
            ("Office Furniture Set", 10, 5000.00),
        ]
    )
    print("Created: scenario3_duplicate.pdf")

    # Scenario 4: Amount mismatch (REVIEW)
    create_invoice_pdf(
        str(fixtures_dir / "scenario4_amount_mismatch.pdf"),
        vendor_name="Acme Supplies Ltd",
        vendor_tax_id="27AABCU9603R1ZM",
        invoice_num="INV-2024-3001",
        date_str="2024-01-18",
        po_ref="PO-2024-001",
        line_items=[
            ("Office Furniture Set", 30, 5000.00),  # 150000 vs PO 100000
        ]
    )
    print("Created: scenario4_amount_mismatch.pdf")

    # Scenario 5: Blocked vendor (REJECT)
    create_invoice_pdf(
        str(fixtures_dir / "scenario5_blocked_vendor.pdf"),
        vendor_name="XYZ Corporation",
        vendor_tax_id="27XYZ12345678ZZ",
        invoice_num="INV-2024-4001",
        date_str="2024-01-22",
        po_ref="PO-2024-006",
        line_items=[
            ("Consulting Services", 1, 25000.00),
        ]
    )
    print("Created: scenario5_blocked_vendor.pdf")

    # Scenario 6: Split invoice (APPROVE)
    create_invoice_pdf(
        str(fixtures_dir / "scenario6_split_invoice.pdf"),
        vendor_name="Tech Solutions Inc",
        vendor_tax_id="29AABCT1234N1ZZ",
        invoice_num="INV-2024-5001",
        date_str="2024-01-25",
        po_ref="PO-2024-002",  # PO for 250000
        line_items=[
            ("Laptop Computers", 5, 10000.00),  # 50000 - within remaining
        ]
    )
    print("Created: scenario6_split_invoice.pdf")

    # Scenario 7: Missing information (REVIEW)
    create_invoice_pdf(
        str(fixtures_dir / "scenario7_missing_information.pdf"),
        vendor_name="Office Essentials",
        vendor_tax_id="27AABCF5678Q1ZZ",
        invoice_num="",  # Missing!
        date_str="2024-01-25",
        po_ref="PO-2024-004",
        line_items=[
            ("Stationery Supplies", 50, 750.00),
        ]
    )
    print("Created: scenario7_missing_information.pdf")

    print("\nAll sample invoices created successfully!")


if __name__ == "__main__":
    main()