"""
Tests for business logic - vendor matching, PO matching, validation, decisions.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apilot.models import (
    Vendor, PurchaseOrder, ExtractedInvoiceData, VendorMatch,
    POMatch, DuplicateCheck, POBalance, ValidationResult, POLineItem
)
from apilot.services.vendor_matcher import VendorMatcher
from apilot.services.po_matcher import POMatcher
from apilot.services.validation_engine import ValidationEngine
from apilot.services.decision_engine import DecisionEngine


class TestVendorMatcher:
    """Test vendor matching logic."""

    def test_no_vendor_data(self):
        """Test matching with no vendor information."""
        matcher = VendorMatcher()

        data = ExtractedInvoiceData(vendor_name=None, vendor_tax_id=None)
        result = matcher.match(data)

        assert result.requires_review is True
        assert "No vendor name" in result.explanation

    def test_exact_tax_id_match(self):
        """Test exact tax ID matching."""
        with patch('apilot.services.vendor_matcher.db') as mock_db:
            mock_vendor = Vendor(id=1, name="Test Vendor", normalized_name="testvendor", tax_id="12345", status="active")
            mock_db.get_vendor_by_tax_id.return_value = mock_vendor
            mock_db.get_all_vendors.return_value = [mock_vendor]

            matcher = VendorMatcher(mock_db)
            data = ExtractedInvoiceData(vendor_name="Test", vendor_tax_id="12345")
            result = matcher.match(data)

            assert result.vendor is not None
            assert result.match_type == "exact_tax_id"
            assert result.confidence == "high"

    def test_blocked_vendor_requires_review(self):
        """Test that blocked vendor triggers review."""
        with patch('apilot.services.vendor_matcher.db') as mock_db:
            mock_vendor = Vendor(id=1, name="Blocked Vendor", normalized_name="blockedvendor", tax_id="12345", status="blocked")
            mock_db.get_vendor_by_tax_id.return_value = mock_vendor
            mock_db.get_all_vendors.return_value = [mock_vendor]

            matcher = VendorMatcher(mock_db)
            data = ExtractedInvoiceData(vendor_name="Test", vendor_tax_id="12345")
            result = matcher.match(data)

            assert result.requires_review is True


class TestPOMatcher:
    """Test PO matching logic."""

    def test_no_vendor_match(self):
        """Test PO matching with no vendor."""
        with patch('apilot.services.po_matcher.db') as mock_db:
            matcher = POMatcher(mock_db)

            data = ExtractedInvoiceData(po_reference="PO-001")
            vendor_match = VendorMatch(requires_review=True)

            result = matcher.match(data, vendor_match)

            assert result.requires_review is True

    def test_explicit_po_match(self):
        """Test explicit PO reference matching."""
        with patch('apilot.services.po_matcher.db') as mock_db:
            mock_vendor = Vendor(id=1, name="Test Vendor", normalized_name="testvendor", status="active")
            mock_po = PurchaseOrder(
                id=1, po_number="PO-2024-001", vendor_id=1,
                approved_amount=Decimal("100000"), currency="INR", status="active",
                tolerance_percent=Decimal("2.0")
            )

            mock_db.get_po_by_number.return_value = mock_po
            mock_db.get_po_balance.return_value = POBalance(
                po_id=1, po_number="PO-2024-001",
                approved_amount=Decimal("100000"),
                recorded_amount=Decimal("0"),
                remaining_balance=Decimal("100000"),
                currency="INR"
            )

            matcher = POMatcher(mock_db)
            data = ExtractedInvoiceData(po_reference="PO-2024-001", currency="INR")
            vendor_match = VendorMatch(vendor=mock_vendor, confidence="high")

            result = matcher.match(data, vendor_match)

            assert result.po is not None
            assert result.match_type == "explicit"

    def test_po_not_found(self):
        """Test when PO reference doesn't exist."""
        with patch('apilot.services.po_matcher.db') as mock_db:
            mock_vendor = Vendor(id=1, name="Test Vendor", normalized_name="testvendor", status="active")
            mock_db.get_po_by_number.return_value = None

            matcher = POMatcher(mock_db)
            data = ExtractedInvoiceData(po_reference="PO-999-999")
            vendor_match = VendorMatch(vendor=mock_vendor, confidence="high")

            result = matcher.match(data, vendor_match)

            assert result.requires_review is True
            assert "not found" in result.explanation.lower()


class TestValidationEngine:
    """Test financial validation."""

    def test_missing_required_fields(self):
        """Test validation fails with missing required fields."""
        engine = ValidationEngine()

        data = ExtractedInvoiceData(
            vendor_name="Test",  # Missing invoice_number, invoice_date, invoice_total
        )
        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        po_match = POMatch(confidence="high")
        dup_check = DuplicateCheck(is_duplicate=False)

        results = engine.validate(data, vendor_match, po_match, dup_check, None)

        req_result = next(r for r in results if r.rule_name == "required_fields")
        assert req_result.status == "REVIEW_REQUIRED"
        assert req_result.blocks_approval is True

    def test_valid_invoice_passes(self):
        """Test valid invoice passes all validations."""
        mock_po = PurchaseOrder(
            id=1, po_number="PO-001", vendor_id=1,
            approved_amount=Decimal("100000"),
            tolerance_percent=Decimal("2.0"),
            currency="INR", status="active"
        )

        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            invoice_number="INV-001",
            invoice_date="2024-01-15",
            invoice_total=Decimal("50000"),
            po_reference="PO-001",
            currency="INR",
            subtotal=Decimal("50000")
        )
        vendor_match = VendorMatch(
            vendor=Vendor(id=1, name="Test", status="active"),
            confidence="high"
        )
        po_match = POMatch(po=mock_po, confidence="high")
        po_balance = POBalance(
            po_id=1, po_number="PO-001",
            approved_amount=Decimal("100000"),
            recorded_amount=Decimal("0"),
            remaining_balance=Decimal("100000"),
            currency="INR"
        )
        dup_check = DuplicateCheck(is_duplicate=False)

        results = ValidationEngine().validate(data, vendor_match, po_match, dup_check, po_balance)

        # Check required fields pass
        req_result = next((r for r in results if r.rule_name == "required_fields"), None)
        assert req_result.status == "PASS"

    def test_blocked_vendor_fails(self):
        """Test blocked vendor fails validation."""
        engine = ValidationEngine()

        data = ExtractedInvoiceData(
            vendor_name="Blocked Vendor",
            invoice_number="INV-001",
            invoice_date="2024-01-15",
            invoice_total=Decimal("1000")
        )
        vendor_match = VendorMatch(
            vendor=Vendor(id=1, name="Blocked", status="blocked"),
            confidence="high"
        )
        po_match = POMatch(confidence="high")
        dup_check = DuplicateCheck(is_duplicate=False)

        results = engine.validate(data, vendor_match, po_match, dup_check, None)

        vendor_result = next(r for r in results if r.rule_name == "vendor_approval")
        assert vendor_result.status == "FAIL"
        assert vendor_result.blocks_approval is True


class TestDecisionEngine:
    """Test decision making logic."""

    def test_approve_all_pass(self):
        """Test APPROVE when all validations pass."""
        engine = DecisionEngine()

        validation_results = [
            ValidationResult(rule_name="required_fields", status="PASS", explanation="OK"),
            ValidationResult(rule_name="vendor_approval", status="PASS", explanation="OK"),
            ValidationResult(rule_name="po_eligibility", status="PASS", explanation="OK"),
            ValidationResult(rule_name="currency_match", status="PASS", explanation="OK"),
            ValidationResult(rule_name="tolerance_check", status="PASS", explanation="OK"),
            ValidationResult(rule_name="duplicate_check", status="PASS", explanation="OK"),
            ValidationResult(rule_name="extraction_quality", status="PASS", explanation="OK"),
        ]

        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Test", status="active"))
        mock_po = PurchaseOrder(id=1, po_number="PO-001", vendor_id=1,
                       approved_amount=Decimal("1000"), status="active", tolerance_percent=Decimal("2.0"), currency="INR")
        po_match = POMatch(po=mock_po, confidence="high")
        po_balance = POBalance(po_id=1, po_number="PO-001", approved_amount=Decimal("1000"),
                              recorded_amount=Decimal("0"), remaining_balance=Decimal("1000"), currency="INR")
        dup_check = DuplicateCheck(is_duplicate=False)

        decision, explanation = engine.decide(
            validation_results, vendor_match, po_match, dup_check, po_balance,
            Mock(invoice_total=Decimal("1000"))
        )

        assert decision == "APPROVE"

    def test_reject_blocked_vendor(self):
        """Test REJECT for blocked vendor."""
        engine = DecisionEngine()

        validation_results = [
            ValidationResult(
                rule_name="vendor_approval", status="FAIL",
                explanation="Vendor is blocked", blocks_approval=True
            )
        ]

        vendor_match = VendorMatch(vendor=Vendor(id=1, name="Blocked", status="blocked"))
        po_match = POMatch()
        dup_check = DuplicateCheck(is_duplicate=False)

        decision, explanation = engine.decide(
            validation_results, vendor_match, po_match, dup_check, None, None
        )

        assert decision == "REJECT"

    def test_review_missing_fields(self):
        """Test REVIEW for missing required fields."""
        engine = DecisionEngine()

        validation_results = [
            ValidationResult(
                rule_name="required_fields", status="REVIEW_REQUIRED",
                explanation="Missing invoice_number", blocks_approval=True
            )
        ]

        vendor_match = VendorMatch()
        po_match = POMatch()
        dup_check = DuplicateCheck(is_duplicate=False)

        decision, explanation = engine.decide(
            validation_results, vendor_match, po_match, dup_check, None, None
        )

        assert decision == "REVIEW"

    def test_reject_duplicate(self):
        """Test REJECT for duplicate."""
        engine = DecisionEngine()

        validation_results = [
            ValidationResult(
                rule_name="duplicate_check", status="FAIL",
                explanation="Duplicate detected", blocks_approval=True
            )
        ]

        vendor_match = VendorMatch()
        po_match = POMatch()
        dup_check = DuplicateCheck(is_duplicate=True, duplicate_type="business")

        decision, explanation = engine.decide(
            validation_results, vendor_match, po_match, dup_check, None, None
        )

        assert decision == "REJECT"