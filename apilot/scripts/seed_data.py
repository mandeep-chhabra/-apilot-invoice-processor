"""
Seed Data Script

Initializes the database with sample reference data for demo purposes.
"""
import sys
from pathlib import Path
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apilot.database import db
from apilot.models import Vendor, PurchaseOrder, POLineItem


def seed_vendors():
    """Create sample vendors."""
    vendors = [
        Vendor(name="Acme Supplies Ltd", tax_id="27AABCU9603R1ZM", status="active"),
        Vendor(name="Tech Solutions Inc", tax_id="29AABCT1234N1ZZ", status="active"),
        Vendor(name="Global Logistics", tax_id="27AAACG1234R1ZZ", status="active"),
        Vendor(name="Office Essentials", tax_id="27AABCF5678Q1ZZ", status="active"),
        Vendor(name="XYZ Corporation", tax_id="27XYZ12345678ZZ", status="blocked"),  # Blocked vendor
    ]

    for vendor in vendors:
        vendor_id = db.add_vendor(vendor)
        print(f"Added vendor: {vendor.name} (ID: {vendor_id}, Status: {vendor.status})")

    return vendors


def seed_purchase_orders():
    """Create sample purchase orders."""
    # Get vendor IDs
    all_vendors = db.get_all_vendors()
    acme = next((v for v in all_vendors if "Acme" in v.name), None)
    tech = next((v for v in all_vendors if "Tech" in v.name), None)
    global_log = next((v for v in all_vendors if "Global" in v.name), None)
    office = next((v for v in all_vendors if "Office" in v.name), None)

    pos = [
        PurchaseOrder(
            po_number="PO-2024-001",
            vendor_id=acme.id if acme else 1,
            currency="INR",
            approved_amount=Decimal("100000.00"),
            tolerance_percent=Decimal("2.0"),
            status="active",
            line_items=[
                POLineItem(po_id=0, description="Office Furniture Set", quantity=Decimal("10"), unit_price=Decimal("5000.00")),
                POLineItem(po_id=0, description="Executive Chairs", quantity=Decimal("5"), unit_price=Decimal("10000.00")),
            ]
        ),
        PurchaseOrder(
            po_number="PO-2024-002",
            vendor_id=tech.id if tech else 2,
            currency="INR",
            approved_amount=Decimal("250000.00"),
            tolerance_percent=Decimal("2.0"),
            status="active",
            line_items=[
                POLineItem(po_id=0, description="Laptop Computers", quantity=Decimal("25"), unit_price=Decimal("10000.00")),
            ]
        ),
        PurchaseOrder(
            po_number="PO-2024-003",
            vendor_id=global_log.id if global_log else 3,
            currency="INR",
            approved_amount=Decimal("50000.00"),
            tolerance_percent=Decimal("5.0"),
            status="active",
            line_items=[
                POLineItem(po_id=0, description="Shipping Services - Q1", quantity=Decimal("1"), unit_price=Decimal("50000.00")),
            ]
        ),
        PurchaseOrder(
            po_number="PO-2024-004",
            vendor_id=office.id if office else 4,
            currency="INR",
            approved_amount=Decimal("75000.00"),
            tolerance_percent=Decimal("2.0"),
            status="active",
            line_items=[
                POLineItem(po_id=0, description="Stationery Supplies", quantity=Decimal("100"), unit_price=Decimal("750.00")),
            ]
        ),
        PurchaseOrder(
            po_number="PO-2024-005",
            vendor_id=tech.id if tech else 2,
            currency="USD",
            approved_amount=Decimal("15000.00"),
            tolerance_percent=Decimal("2.0"),
            status="active",
            line_items=[
                POLineItem(po_id=0, description="Software Licenses", quantity=Decimal("50"), unit_price=Decimal("300.00")),
            ]
        ),
    ]

    for po in pos:
        po_id = db.add_po(po)
        print(f"Added PO: {po.po_number} (ID: {po_id}, Amount: {po.approved_amount} {po.currency})")

    return pos


def seed_invoice_runs():
    """Create sample invoice runs for demo scenarios."""
    from datetime import datetime, timedelta
    from apilot.models import (
        ExtractedInvoiceData, VendorMatch, POMatch, DuplicateCheck,
        POBalance, ValidationResult, InvoiceRun, InvoiceLineItem
    )
    import uuid

    # Scenario 1: Clean invoice - APPROVE
    run1 = InvoiceRun(
        run_id=str(uuid.uuid4()),
        original_filename="scenario1_clean_invoice.pdf",
        file_hash="abc123def456",
        extraction_status="success",
        business_decision="APPROVE",
        decision_explanation="APPROVED: Vendor 'Acme Supplies Ltd' verified. PO 'PO-2024-001' matched. Balance: 70000.00 INR remaining.",
        processing_status="completed",
        timestamp=datetime.now() - timedelta(hours=2),
        is_fixture=True,
        extracted_data=ExtractedInvoiceData(
            vendor_name="Acme Supplies Ltd",
            vendor_tax_id="27AABCU9603R1ZM",
            invoice_number="INV-2024-1001",
            invoice_date="2024-01-15",
            due_date="2024-02-14",
            po_reference="PO-2024-001",
            currency="INR",
            line_items=[
                InvoiceLineItem(description="Office Furniture Set", quantity=Decimal("10"), unit_price=Decimal("5000.00")),
            ],
            subtotal=Decimal("50000.00"),
            tax_components=[{"name": "CGST", "rate": 9, "amount": Decimal("4500.00")}, {"name": "SGST", "rate": 9, "amount": Decimal("4500.00")}],
            invoice_total=Decimal("59000.00")
        )
    )

    # Scenario 2: Missing PO - REVIEW
    run2 = InvoiceRun(
        run_id=str(uuid.uuid4()),
        original_filename="scenario2_missing_po.pdf",
        file_hash="def456ghi789",
        extraction_status="success",
        business_decision="REVIEW",
        decision_explanation="REVIEW REQUIRED: Multiple candidate POs found for vendor. Please select the correct PO.",
        processing_status="completed",
        timestamp=datetime.now() - timedelta(hours=1),
        is_fixture=True,
        extracted_data=ExtractedInvoiceData(
            vendor_name="Tech Solutions Inc",
            vendor_tax_id="29AABCT1234N1ZZ",
            invoice_number="INV-2024-2001",
            invoice_date="2024-01-20",
            due_date="2024-02-19",
            po_reference=None,  # Missing PO reference
            currency="INR",
            line_items=[
                InvoiceLineItem(description="Laptop Computers", quantity=Decimal("10"), unit_price=Decimal("10000.00")),
            ],
            subtotal=Decimal("100000.00"),
            tax_components=[{"name": "CGST", "rate": 9, "amount": Decimal("9000.00")}],
            invoice_total=Decimal("109000.00")
        )
    )

    # Scenario 3: Duplicate - REJECT
    run3 = InvoiceRun(
        run_id=str(uuid.uuid4()),
        original_filename="scenario3_duplicate.pdf",
        file_hash="ghi789jkl012",
        extraction_status="success",
        business_decision="REJECT",
        decision_explanation="REJECTED: Invoice number 'INV-2024-1001' already processed",
        processing_status="completed",
        timestamp=datetime.now() - timedelta(minutes=45),
        is_fixture=True,
        extracted_data=ExtractedInvoiceData(
            vendor_name="Acme Supplies Ltd",
            vendor_tax_id="27AABCU9603R1ZM",
            invoice_number="INV-2024-1001",  # Same as run1
            invoice_date="2024-01-15",
            po_reference="PO-2024-001",
            currency="INR",
            invoice_total=Decimal("59000.00")
        )
    )

    # Scenario 4: Amount mismatch - REVIEW
    run4 = InvoiceRun(
        run_id=str(uuid.uuid4()),
        original_filename="scenario4_mismatch.pdf",
        file_hash="jkl012mno345",
        extraction_status="success",
        business_decision="REVIEW",
        decision_explanation="REVIEW REQUIRED: Invoice amount 150000.00 exceeds remaining PO balance 70000.00 (PO approved: 100000.00)",
        processing_status="completed",
        timestamp=datetime.now() - timedelta(minutes=30),
        is_fixture=True,
        extracted_data=ExtractedInvoiceData(
            vendor_name="Acme Supplies Ltd",
            vendor_tax_id="27AABCU9603R1ZM",
            invoice_number="INV-2024-3001",
            invoice_date="2024-01-18",
            po_reference="PO-2024-001",
            currency="INR",
            invoice_total=Decimal("150000.00")  # Exceeds remaining balance
        )
    )

    # Scenario 5: Blocked vendor - REJECT
    run5 = InvoiceRun(
        run_id=str(uuid.uuid4()),
        original_filename="scenario5_blocked.pdf",
        file_hash="mno345pqr678",
        extraction_status="success",
        business_decision="REJECT",
        decision_explanation="REJECTED: Vendor 'XYZ Corporation' is blocked",
        processing_status="completed",
        timestamp=datetime.now() - timedelta(minutes=15),
        is_fixture=True,
        extracted_data=ExtractedInvoiceData(
            vendor_name="XYZ Corporation",
            vendor_tax_id="27XYZ12345678ZZ",
            invoice_number="INV-2024-4001",
            invoice_date="2024-01-22",
            po_reference="PO-2024-006",
            currency="INR",
            invoice_total=Decimal("25000.00")
        )
    )

    # Scenario 6: Missing information - REVIEW
    run6 = InvoiceRun(
        run_id=str(uuid.uuid4()),
        original_filename="scenario7_missing_info.pdf",
        file_hash="pqr678stu901",
        extraction_status="success",
        business_decision="REVIEW",
        decision_explanation="REVIEW REQUIRED: Missing required fields: invoice_number, invoice_total. Manual review required.",
        processing_status="completed",
        timestamp=datetime.now() - timedelta(minutes=5),
        is_fixture=True,
        extracted_data=ExtractedInvoiceData(
            vendor_name="Office Essentials",
            vendor_tax_id="27AABCF5678Q1ZZ",
            invoice_number=None,  # Missing!
            invoice_date="2024-01-25",
            po_reference="PO-2024-004",
            currency="INR",
            invoice_total=None,  # Missing!
            missing_fields=["invoice_number", "invoice_total"]
        )
    )

    for run in [run1, run2, run3, run4, run5, run6]:
        db.save_run(run)
        print(f"Added fixture run: {run.original_filename} -> {run.business_decision}")


def main():
    """Main seeding function."""
    print("=" * 50)
    print("APilot Database Seeding")
    print("=" * 50)

    print("\n1. Seeding vendors...")
    vendors = seed_vendors()

    print("\n2. Seeding purchase orders...")
    pos = seed_purchase_orders()

    print("\n3. Seeding invoice runs (fixtures)...")
    seed_invoice_runs()

    print("\n" + "=" * 50)
    print("Database seeding complete!")
    print("=" * 50)
    print(f"\nVendors: {len(vendors)}")
    print(f"Purchase Orders: {len(pos)}")


if __name__ == "__main__":
    main()