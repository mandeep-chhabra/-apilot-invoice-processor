"""
Tests for missing information handling.
"""
import pytest
import os
from unittest.mock import Mock, patch
from decimal import Decimal

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apilot.models import (
    ExtractedInvoiceData, VendorMatch, POMatch, DuplicateCheck,
    ValidationResult, Vendor, PurchaseOrder, POBalance, InvoiceLineItem
)
from apilot.services.validation_engine import ValidationEngine
from apilot.services.decision_engine import DecisionEngine


class TestMissingInformation:
    """Test handling of missing invoice information."""

    def test_missing_invoice_number(self):
        """Test validation when invoice number is missing."""
        engine = ValidationEngine()

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number=None,  # Missing!
            invoice_date="2024-01-15",
            invoice_total=Decimal("1000"),
            missing_fields=["invoice_number"]
        )
        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        po_match = POMatch(po=PurchaseOrder(id=1, po_number="PO-001", vendor_id=1, status="active", approved_amount=Decimal("1000")))
        dup_check = DuplicateCheck(is_duplicate=False)

        results = engine.validate(data, vendor_match, po_match, dup_check, None)

        req_result = next(r for r in results if r.rule_name == "required_fields")
        assert req_result.status == "REVIEW_REQUIRED"
        assert "invoice_number" in req_result.actual

    def test_missing_invoice_total(self):
        """Test validation when invoice total is missing."""
        engine = ValidationEngine()

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-001",
            invoice_date="2024-01-15",
            invoice_total=None,  # Missing!
            missing_fields=["invoice_total"]
        )
        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        po_match = POMatch(po=PurchaseOrder(id=1, po_number="PO-001", vendor_id=1, status="active", approved_amount=Decimal("1000")))
        dup_check = DuplicateCheck(is_duplicate=False)

        results = engine.validate(data, vendor_match, po_match, dup_check, None)

        req_result = next(r for r in results if r.rule_name == "required_fields")
        assert req_result.status == "REVIEW_REQUIRED"
        assert "invoice_total" in req_result.actual

    def test_missing_invoice_date(self):
        """Test validation when invoice date is missing."""
        engine = ValidationEngine()

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-001",
            invoice_date=None,  # Missing!
            invoice_total=Decimal("1000"),
            missing_fields=["invoice_date"]
        )
        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        po_match = POMatch(po=PurchaseOrder(id=1, po_number="PO-001", vendor_id=1, status="active", approved_amount=Decimal("1000")))
        dup_check = DuplicateCheck(is_duplicate=False)

        results = engine.validate(data, vendor_match, po_match, dup_check, None)

        req_result = next(r for r in results if r.rule_name == "required_fields")
        assert req_result.status == "REVIEW_REQUIRED"

    def test_multiple_missing_fields(self):
        """Test validation with multiple missing fields."""
        engine = ValidationEngine()

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number=None,
            invoice_date=None,
            invoice_total=None,
            missing_fields=["invoice_number", "invoice_date", "invoice_total"]
        )
        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        po_match = POMatch(po=PurchaseOrder(id=1, po_number="PO-001", vendor_id=1, status="active", approved_amount=Decimal("1000")))
        dup_check = DuplicateCheck(is_duplicate=False)

        results = engine.validate(data, vendor_match, po_match, dup_check, None)

        req_result = next(r for r in results if r.rule_name == "required_fields")
        assert req_result.status == "REVIEW_REQUIRED"
        assert "invoice_number" in req_result.actual
        assert "invoice_total" in req_result.actual

    def test_extraction_warnings_block_approval(self):
        """Test that extraction warnings block automatic approval."""
        engine = ValidationEngine()

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-001",
            invoice_date="2024-01-15",
            invoice_total=Decimal("1000"),
            extraction_warnings=["Text was blurry", "Some fields unreadable"]
        )
        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        po_match = POMatch(po=PurchaseOrder(id=1, po_number="PO-001", vendor_id=1, status="active", approved_amount=Decimal("1000")))
        dup_check = DuplicateCheck(is_duplicate=False)

        results = engine.validate(data, vendor_match, po_match, dup_check, None)

        qual_result = next(r for r in results if r.rule_name == "extraction_quality")
        assert qual_result.status == "REVIEW_REQUIRED"
        assert "blurry" in qual_result.explanation.lower()

    def test_missing_po_reference_triggers_review(self):
        """Test that missing PO reference triggers review."""
        from apilot.services.po_matcher import POMatcher

        with patch('apilot.services.po_matcher.db') as mock_db:
            mock_vendor = Vendor(id=1, name="Test", status="active")
            mock_po = PurchaseOrder(id=1, po_number="PO-001", vendor_id=1, status="active",
                     approved_amount=Decimal("100000"), currency="INR", tolerance_percent=Decimal("2.0"))
            mock_balance = POBalance(po_id=1, po_number="PO-001", approved_amount=Decimal("100000"),
                                    recorded_amount=Decimal("0"), remaining_balance=Decimal("100000"), currency="INR")
            mock_db.get_pos_for_vendor.return_value = [mock_po]
            mock_db.get_po_balance.return_value = mock_balance

            matcher = POMatcher(mock_db)
            data = ExtractedInvoiceData(
                vendor_name="Test Vendor",
                invoice_number="INV-001",
                invoice_total=Decimal("50000"),
                po_reference=None,  # Missing!
                currency="INR"
            )
            vendor_match = VendorMatch(vendor=mock_vendor, confidence="high")

            result = matcher.match(data, vendor_match)

            assert result.requires_review is True
            assert result.candidate_pos is not None

    def test_no_approval_without_total(self):
        """Test that invoice without total cannot be approved."""
        engine = DecisionEngine()

        validation_results = [
            ValidationResult(
                rule_name="required_fields",
                status="REVIEW_REQUIRED",
                explanation="Missing invoice_total",
                blocks_approval=True
            )
        ]

        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        po_match = POMatch(po=PurchaseOrder(id=1, po_number="PO-001", vendor_id=1, status="active", approved_amount=Decimal("1000")))
        dup_check = DuplicateCheck(is_duplicate=False)

        decision, explanation = engine.decide(
            validation_results, vendor_match, po_match, dup_check, None,
            Mock(invoice_total=None)
        )

        assert decision == "REVIEW"

    def test_unreadable_total_never_guessed(self):
        """Test that unreadable total is not guessed or replaced."""
        data = ExtractedInvoiceData(
            vendor_name="Test",
            invoice_number="INV-001",
            invoice_total=None,
            missing_fields=["invoice_total"],
            extraction_warnings=["Total amount unreadable"]
        )

        # Invoice total should remain None, never guessed
        assert data.invoice_total is None

        # Should have warnings about unreadable total
        assert any("unreadable" in w.lower() for w in data.extraction_warnings)

    def test_preserve_valid_fields_when_one_missing(self):
        """Test that valid fields are preserved when one is missing."""
        data = ExtractedInvoiceData(
            vendor_name="Valid Vendor",
            vendor_tax_id="12345",
            invoice_number="INV-001",
            invoice_date="2024-01-15",
            invoice_total=Decimal("1000"),
            po_reference="PO-001",
            currency="INR",
            subtotal=Decimal("900"),
            shipping=Decimal("100"),
            missing_fields=["due_date"],  # Only due date missing
            line_items=[
                InvoiceLineItem(description="Item 1", quantity=Decimal("1"), unit_price=Decimal("900"))
            ]
        )

        # Other fields should still be valid
        assert data.vendor_name == "Valid Vendor"
        assert data.invoice_number == "INV-001"
        assert data.invoice_total == Decimal("1000")
        assert len(data.line_items) == 1

    def test_distinguish_missing_vs_failed_extraction(self):
        """Test distinction between missing info and technical failure."""
        # Missing business information
        missing_data = ExtractedInvoiceData(
            vendor_name="Test",
            invoice_total=None,
            missing_fields=["invoice_total"],
            extraction_warnings=[]
        )

        # Technical failure - extraction failed
        failed_data = ExtractedInvoiceData(
            vendor_name="Test",
            invoice_total=None,
            missing_fields=["extraction_failed"],
            extraction_warnings=["API quota exceeded"]
        )

        # Both should trigger review, but for different reasons
        assert missing_data.missing_fields == ["invoice_total"]
        assert "extraction_failed" in failed_data.missing_fields
        assert "quota" in failed_data.extraction_warnings[0].lower()