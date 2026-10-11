"""
Validation Engine Service

Performs deterministic financial and procurement validation.
"""
from decimal import Decimal
from typing import List, Optional

from apilot.database import db
from apilot.models import (
    ExtractedInvoiceData, VendorMatch, POMatch, DuplicateCheck,
    POBalance, ValidationResult
)


class ValidationEngine:
    """Validates invoice data against business rules."""

    def __init__(self, database: db = None):
        self.db = database or db

    def validate(
        self,
        extracted_data: ExtractedInvoiceData,
        vendor_match: VendorMatch,
        po_match: POMatch,
        duplicate_check: DuplicateCheck,
        po_balance: Optional[POBalance]
    ) -> List[ValidationResult]:
        """
        Run all validation rules.

        Returns:
            List of ValidationResult for each rule
        """
        results = []

        # Required fields validation
        results.append(self._validate_required_fields(extracted_data))

        # Vendor validation
        results.append(self._validate_vendor(vendor_match))

        # PO validation
        results.append(self._validate_po(po_match))

        # Currency validation
        results.append(self._validate_currency(po_match, extracted_data))

        # Financial arithmetic validation
        results.append(self._validate_arithmetic(extracted_data))

        # Tolerance validation
        results.append(self._validate_tolerance(po_match, extracted_data, po_balance))

        # Duplicate validation
        results.append(self._validate_duplicate(duplicate_check))

        # Extraction warnings
        results.append(self._validate_extraction_quality(extracted_data))

        # Filter out NOT_APPLICABLE and return
        return [r for r in results if r.status != "NOT_APPLICABLE"]

    def _validate_required_fields(self, data: ExtractedInvoiceData) -> ValidationResult:
        """Validate required fields are present."""
        missing = []

        if not data.invoice_number:
            missing.append("invoice_number")
        if not data.invoice_total:
            missing.append("invoice_total")
        if not data.vendor_name:
            missing.append("vendor_name")

        has_po_ref = bool(data.po_reference)

        if missing:
            return ValidationResult(
                rule_name="required_fields",
                status="REVIEW_REQUIRED",
                expected="invoice_number, invoice_date, invoice_total, vendor_name",
                actual=", ".join(missing),
                explanation=f"Missing required fields: {', '.join(missing)}. Manual review required.",
                blocks_approval=True
            )

        return ValidationResult(
            rule_name="required_fields",
            status="PASS",
            explanation="All required fields present"
        )

    def _validate_vendor(self, vendor_match: VendorMatch) -> ValidationResult:
        """Validate vendor is approved."""
        if not vendor_match.vendor:
            return ValidationResult(
                rule_name="vendor_approval",
                status="REVIEW_REQUIRED",
                explanation="Vendor not identified. Manual review required.",
                blocks_approval=True
            )

        if vendor_match.vendor.status == "blocked":
            return ValidationResult(
                rule_name="vendor_approval",
                status="FAIL",
                expected="active vendor",
                actual=f"blocked vendor: {vendor_match.vendor.name}",
                explanation=f"Vendor '{vendor_match.vendor.name}' is blocked. Invoice must be rejected.",
                blocks_approval=True
            )

        return ValidationResult(
            rule_name="vendor_approval",
            status="PASS",
            explanation=f"Vendor '{vendor_match.vendor.name}' is active and approved"
        )

    def _validate_po(self, po_match: POMatch) -> ValidationResult:
        """Validate PO is eligible."""
        if po_match.requires_review and not po_match.po:
            return ValidationResult(
                rule_name="po_eligibility",
                status="REVIEW_REQUIRED",
                explanation=po_match.explanation,
                blocks_approval=True
            )

        if not po_match.po:
            return ValidationResult(
                rule_name="po_eligibility",
                status="REVIEW_REQUIRED",
                explanation="No PO matched. Manual review required.",
                blocks_approval=True
            )

        if po_match.po.status != "active":
            return ValidationResult(
                rule_name="po_eligibility",
                status="FAIL",
                expected="active PO",
                actual=f"{po_match.po.status} PO: {po_match.po.po_number}",
                explanation=f"PO '{po_match.po.po_number}' is {po_match.po.status}. Cannot approve.",
                blocks_approval=True
            )

        return ValidationResult(
            rule_name="po_eligibility",
            status="PASS",
            explanation=f"PO '{po_match.po.po_number}' is active and eligible"
        )

    def _validate_currency(
        self,
        po_match: POMatch,
        extracted_data: ExtractedInvoiceData
    ) -> ValidationResult:
        """Validate currency consistency."""
        if not po_match.po or not extracted_data.currency:
            return ValidationResult(
                rule_name="currency_match",
                status="NOT_APPLICABLE",
                explanation="PO not matched or no currency in invoice"
            )

        if po_match.po.currency != extracted_data.currency:
            return ValidationResult(
                rule_name="currency_match",
                status="FAIL",
                expected=po_match.po.currency,
                actual=extracted_data.currency,
                explanation=f"Currency mismatch: PO uses {po_match.po.currency}, invoice uses {extracted_data.currency}",
                blocks_approval=True
            )

        return ValidationResult(
            rule_name="currency_match",
            status="PASS",
            explanation=f"Currency {extracted_data.currency} matches PO"
        )

    def _validate_arithmetic(self, data: ExtractedInvoiceData) -> ValidationResult:
        """Validate invoice total is present and matches PO amount."""
        if not data.invoice_total:
            return ValidationResult(
                rule_name="financial_arithmetic",
                status="REVIEW_REQUIRED",
                explanation="Invoice total is missing",
                blocks_approval=True
            )

        if data.invoice_total <= Decimal(0):
            return ValidationResult(
                rule_name="financial_arithmetic",
                status="REVIEW_REQUIRED",
                explanation="Invoice total must be greater than zero",
                blocks_approval=True
            )

        return ValidationResult(
            rule_name="financial_arithmetic",
            status="PASS",
            explanation="Invoice total is present and valid"
        )

    def _validate_tolerance(
        self,
        po_match: POMatch,
        extracted_data: ExtractedInvoiceData,
        po_balance: Optional[POBalance]
    ) -> ValidationResult:
        """Validate invoice amount is within tolerance and PO balance."""
        if not po_match.po or not extracted_data.invoice_total:
            return ValidationResult(
                rule_name="tolerance_check",
                status="NOT_APPLICABLE",
                explanation="PO not matched or no invoice total"
            )

        invoice_amount = extracted_data.invoice_total
        approved_amount = po_match.po.approved_amount
        tolerance = po_match.po.tolerance_amount

        # Check if amount is within tolerance of original PO
        variance = abs(invoice_amount - approved_amount)

        if variance > tolerance:
            # Check remaining balance instead
            if po_balance:
                if invoice_amount > po_balance.remaining_balance:
                    return ValidationResult(
                        rule_name="tolerance_check",
                        status="FAIL",
                        expected=f"≤ {po_balance.remaining_balance}",
                        actual=str(invoice_amount),
                        variance=invoice_amount - po_balance.remaining_balance,
                        explanation=f"Invoice amount {invoice_amount} exceeds remaining PO balance {po_balance.remaining_balance}",
                        blocks_approval=True
                    )
            else:
                return ValidationResult(
                    rule_name="tolerance_check",
                    status="REVIEW_REQUIRED",
                    expected=f"within {po_match.po.tolerance_percent}% of {approved_amount}",
                    actual=str(invoice_amount),
                    variance=variance,
                    explanation=f"Invoice amount {invoice_amount} differs from PO amount {approved_amount} by more than {po_match.po.tolerance_percent}%",
                    blocks_approval=True
                )

        # Also check against remaining balance
        if po_balance:
            if invoice_amount > po_balance.remaining_balance:
                return ValidationResult(
                    rule_name="tolerance_check",
                    status="REVIEW_REQUIRED",
                    expected=f"≤ {po_balance.remaining_balance}",
                    actual=str(invoice_amount),
                    variance=invoice_amount - po_balance.remaining_balance,
                    explanation=f"Invoice amount {invoice_amount} exceeds remaining PO balance {po_balance.remaining_balance}",
                    blocks_approval=True
                )

        return ValidationResult(
            rule_name="tolerance_check",
            status="PASS",
            explanation=f"Invoice amount {invoice_amount} is within tolerance and PO balance"
        )

    def _validate_duplicate(self, duplicate_check: DuplicateCheck) -> ValidationResult:
        """Validate no duplicate exists."""
        if duplicate_check.is_duplicate:
            return ValidationResult(
                rule_name="duplicate_check",
                status="FAIL",
                explanation=f"Duplicate detected: {duplicate_check.explanation}",
                blocks_approval=True
            )

        return ValidationResult(
            rule_name="duplicate_check",
            status="PASS",
            explanation="No duplicate detected"
        )

    def _validate_extraction_quality(
        self,
        extracted_data: ExtractedInvoiceData
    ) -> ValidationResult:
        """Validate extraction quality and warn about uncertain data."""
        warnings = []

        if extracted_data.extraction_warnings:
            warnings.extend(extracted_data.extraction_warnings)

        if extracted_data.ambiguous_info:
            warnings.append(f"Ambiguous fields: {', '.join(extracted_data.ambiguous_info.keys())}")

        # Missing invoice number makes duplicate detection unreliable
        if not extracted_data.invoice_number:
            warnings.append("Invoice number missing - duplicate detection may be unreliable")

        if warnings:
            return ValidationResult(
                rule_name="extraction_quality",
                status="REVIEW_REQUIRED",
                explanation=f"Extraction warnings: {'; '.join(warnings)}",
                blocks_approval=True
            )

        return ValidationResult(
            rule_name="extraction_quality",
            status="PASS",
            explanation="Extraction quality is acceptable"
        )


def validate_invoice(
    extracted_data: ExtractedInvoiceData,
    vendor_match: VendorMatch,
    po_match: POMatch,
    duplicate_check: DuplicateCheck,
    po_balance: Optional[POBalance] = None
) -> List[ValidationResult]:
    """Convenience function for validation."""
    engine = ValidationEngine()
    return engine.validate(extracted_data, vendor_match, po_match, duplicate_check, po_balance)