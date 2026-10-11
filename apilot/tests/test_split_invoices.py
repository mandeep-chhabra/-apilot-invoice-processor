"""
Tests for split invoice functionality - multiple invoices against one PO.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apilot.models import (
    PurchaseOrder, POBalance, ValidationResult, ExtractedInvoiceData,
    VendorMatch, POMatch, DuplicateCheck, Vendor, InvoiceRun
)
from apilot.services.validation_engine import ValidationEngine


class TestPOBalance:
    """Test PO balance calculations."""

    def test_initial_balance(self):
        """Test balance when no invoices recorded."""
        balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("0"),
            remaining_balance=Decimal("100000"),
            currency="INR"
        )

        assert balance.remaining_balance == Decimal("100000")
        assert balance.recorded_amount == Decimal("0")

    def test_balance_after_partial_invoice(self):
        """Test balance after one invoice recorded."""
        balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("30000"),
            remaining_balance=Decimal("70000"),
            currency="INR"
        )

        assert balance.remaining_balance == Decimal("70000")
        assert balance.recorded_amount == Decimal("30000")

    def test_balance_after_multiple_invoices(self):
        """Test balance after multiple invoices."""
        balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("55000"),  # 30000 + 25000
            remaining_balance=Decimal("45000"),
            currency="INR"
        )

        assert balance.remaining_balance == Decimal("45000")

    def test_balance_exhausted(self):
        """Test when PO balance is fully used."""
        balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("100000"),
            remaining_balance=Decimal("0"),
            currency="INR"
        )

        assert balance.remaining_balance == Decimal("0")


class TestSplitInvoiceValidation:
    """Test validation for split invoices."""

    def test_invoice_within_remaining_balance(self):
        """Test invoice amount within remaining balance passes."""
        mock_po = PurchaseOrder(
            id=1, po_number="PO-2024-001", vendor_id=1,
            approved_amount=Decimal("100000"),
            tolerance_percent=Decimal("2.0"),
            currency="INR", status="active"
        )

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-002",
            invoice_date="2024-01-15",
            invoice_total=Decimal("25000"),  # Within remaining 45000
            po_reference="PO-2024-001",
            currency="INR"
        )
        vendor_match = VendorMatch(
            vendor=Vendor(id=1, name="Test", status="active"),
            confidence="high"
        )
        po_match = POMatch(po=mock_po, confidence="high")
        po_balance = POBalance(
            po_id=1, po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("55000"),
            remaining_balance=Decimal("45000"),
            currency="INR"
        )
        dup_check = DuplicateCheck(is_duplicate=False)

        results = ValidationEngine().validate(data, vendor_match, po_match, dup_check, po_balance)

        tol_result = next((r for r in results if r.rule_name == "tolerance_check"), None)
        assert tol_result.status == "PASS"

    def test_invoice_exceeds_remaining_balance(self):
        """Test invoice exceeding remaining balance triggers review."""
        mock_po = PurchaseOrder(
            id=1, po_number="PO-2024-001", vendor_id=1,
            approved_amount=Decimal("100000"),
            tolerance_percent=Decimal("2.0"),
            currency="INR", status="active"
        )

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-003",
            invoice_date="2024-01-15",
            invoice_total=Decimal("50000"),  # Exceeds remaining 45000
            po_reference="PO-2024-001",
            currency="INR"
        )
        vendor_match = VendorMatch(
            vendor=Vendor(id=1, name="Test", status="active"),
            confidence="high"
        )
        po_match = POMatch(po=mock_po, confidence="high")
        po_balance = POBalance(
            po_id=1, po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("55000"),
            remaining_balance=Decimal("45000"),
            currency="INR"
        )
        dup_check = DuplicateCheck(is_duplicate=False)

        results = ValidationEngine().validate(data, vendor_match, po_match, dup_check, po_balance)

        tol_result = next((r for r in results if r.rule_name == "tolerance_check"), None)
        assert tol_result.status in ["FAIL", "REVIEW_REQUIRED"]
        assert tol_result.blocks_approval is True

    def test_tolerance_applies_to_remaining_balance(self):
        """Test tolerance checking against remaining balance."""
        mock_po = PurchaseOrder(
            id=1, po_number="PO-2024-001", vendor_id=1,
            approved_amount=Decimal("100000"),
            tolerance_percent=Decimal("2.0"),
            currency="INR", status="active"
        )

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-004",
            invoice_date="2024-01-15",
            invoice_total=Decimal("40000"),
            po_reference="PO-2024-001",
            currency="INR"
        )
        vendor_match = VendorMatch(
            vendor=Vendor(id=1, name="Test", status="active"),
            confidence="high"
        )
        po_match = POMatch(po=mock_po, confidence="high")
        # Use real POBalance instead of Mock
        po_balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("55000"),
            remaining_balance=Decimal("45000"),
            currency="INR"
        )
        dup_check = DuplicateCheck(is_duplicate=False)

        results = ValidationEngine().validate(data, vendor_match, po_match, dup_check, po_balance)

        # Should pass - within remaining balance
        tol_result = next((r for r in results if r.rule_name == "tolerance_check"), None)
        assert tol_result.status == "PASS"


class TestMultipleInvoicesScenarios:
    """Test scenarios with multiple invoices against one PO."""

    def test_first_invoice_full_approval(self):
        """Test first invoice gets full approval."""
        balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("0"),
            remaining_balance=Decimal("100000"),
            currency="INR"
        )

        invoice_amount = Decimal("30000")
        assert invoice_amount <= balance.remaining_balance

        new_recorded = balance.recorded_amount + invoice_amount
        new_remaining = balance.approved_amount - new_recorded

        assert new_recorded == Decimal("30000")
        assert new_remaining == Decimal("70000")

    def test_second_partial_invoice(self):
        """Test second invoice against same PO."""
        balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("30000"),
            remaining_balance=Decimal("70000"),
            currency="INR"
        )

        invoice_amount = Decimal("25000")
        assert invoice_amount <= balance.remaining_balance

        new_recorded = balance.recorded_amount + invoice_amount
        new_remaining = balance.approved_amount - new_recorded

        assert new_recorded == Decimal("55000")
        assert new_remaining == Decimal("45000")

    def test_third_invoice_exceeds_balance(self):
        """Test third invoice that exceeds remaining balance."""
        balance = POBalance(
            po_id=1,
            po_number="PO-2024-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("55000"),
            remaining_balance=Decimal("45000"),
            currency="INR"
        )

        invoice_amount = Decimal("50000")
        assert invoice_amount > balance.remaining_balance

    def test_duplicate_invoice_not_counted_twice(self):
        """Test duplicate submission doesn't consume balance twice."""
        from apilot.services.duplicate_detector import DuplicateDetector

        with patch('apilot.services.duplicate_detector.db') as mock_db:
            detector = DuplicateDetector(mock_db)

            # First check - not a duplicate
            data = ExtractedInvoiceData(
                vendor_name="Test",
                invoice_number="INV-001",
                invoice_total=Decimal("30000")
            )
            vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))

            result = detector.check("hash123", data, vendor_match)
            assert result.is_duplicate is False

            # Create a mock run with proper fields
            mock_run = InvoiceRun(
                run_id="run-123",
                original_filename="test.pdf",
                file_hash="different_hash",
                extracted_data=ExtractedInvoiceData(
                    vendor_name="Test",
                    invoice_number="INV-001",
                    invoice_total=Decimal("30000")
                ),
                business_decision="APPROVE",
                processing_status="completed"
            )
            mock_db.get_all_runs.return_value = [mock_run]

            result2 = detector.check("hash456", data, vendor_match)
            # Should detect as potential duplicate
            assert result2.is_duplicate is True or "INV-001" in result2.explanation