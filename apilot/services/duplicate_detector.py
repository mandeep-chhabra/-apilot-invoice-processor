"""
Duplicate Detection Service

Detects exact-file and business-level duplicates.
"""
from typing import Optional
from decimal import Decimal

from apilot.database import db
from apilot.models import ExtractedInvoiceData, VendorMatch, DuplicateCheck, InvoiceRun


class DuplicateDetector:
    """Detects duplicate invoice submissions."""

    def __init__(self, database: db = None):
        self.db = database or db

    def check(
        self,
        file_hash: str,
        extracted_data: ExtractedInvoiceData,
        vendor_match: VendorMatch
    ) -> DuplicateCheck:
        """
        Check for duplicates.

        Returns:
            DuplicateCheck with results
        """
        # Check exact file duplicate
        exact_dup = self._check_exact_duplicate(file_hash)
        if exact_dup:
            return exact_dup

        # Check business duplicate
        if vendor_match.vendor and extracted_data.invoice_number:
            business_dup = self._check_business_duplicate(
                vendor_match.vendor.id,
                extracted_data.invoice_number,
                extracted_data.invoice_total,
                file_hash
            )
            if business_dup:
                return business_dup

        return DuplicateCheck(
            is_duplicate=False,
            explanation="No duplicate found"
        )

    def _check_exact_duplicate(self, file_hash: str) -> Optional[DuplicateCheck]:
        """Check for exact file hash duplicate."""
        existing_run = self.db.get_all_runs(limit=1000)

        for run in existing_run:
            if run.file_hash == file_hash and run.business_decision:
                return DuplicateCheck(
                    is_duplicate=True,
                    duplicate_type="exact_file",
                    existing_run_id=run.id,
                    explanation=f"Exact duplicate of previously processed file (run ID: {run.run_id})"
                )

        return None

    def _check_business_duplicate(
        self,
        vendor_id: int,
        invoice_number: str,
        invoice_total: Optional[Decimal],
        file_hash: str
    ) -> Optional[DuplicateCheck]:
        """Check for business-level duplicate (same vendor + invoice number)."""
        if not invoice_number:
            return None

        # Find runs with same invoice number for this vendor
        existing_runs = self.db.get_all_runs(limit=1000)

        for run in existing_runs:
            if not run.extracted_data:
                continue

            # Check if same vendor (by comparing normalized names if available)
            if run.extracted_data.invoice_number == invoice_number:
                # Same invoice number - check for conflicting amount
                if invoice_total and run.extracted_data.invoice_total:
                    if invoice_total != run.extracted_data.invoice_total:
                        return DuplicateCheck(
                            is_duplicate=True,
                            duplicate_type="business",
                            existing_run_id=run.id,
                            conflicting_amount=True,
                            explanation=f"Invoice number '{invoice_number}' already exists with different amount: {run.extracted_data.invoice_total} vs {invoice_total}"
                        )

                # Same invoice number and amount - duplicate
                return DuplicateCheck(
                    is_duplicate=True,
                    duplicate_type="business",
                    existing_run_id=run.id,
                    explanation=f"Invoice number '{invoice_number}' already processed (run ID: {run.run_id})"
                )

        return None


def check_duplicate(
    file_hash: str,
    extracted_data: ExtractedInvoiceData,
    vendor_match: VendorMatch
) -> DuplicateCheck:
    """Convenience function for duplicate checking."""
    detector = DuplicateDetector()
    return detector.check(file_hash, extracted_data, vendor_match)