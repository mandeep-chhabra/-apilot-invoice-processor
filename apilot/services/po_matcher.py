"""
Purchase Order Matching Service

Matches invoices to purchase orders based on various criteria.
"""
from typing import Optional, List
from decimal import Decimal

from apilot.database import db
from apilot.models import (
    PurchaseOrder, ExtractedInvoiceData, VendorMatch, POMatch, POBalance
)


class POMatcher:
    """Matches invoices to purchase orders."""

    def __init__(self, database: db = None):
        self.db = database or db

    def match(
        self,
        extracted_data: ExtractedInvoiceData,
        vendor_match: VendorMatch
    ) -> POMatch:
        """
        Match invoice to PO based on extracted data and vendor match.

        Returns:
            POMatch with match results
        """
        # No vendor match - can't match PO
        if not vendor_match.vendor:
            return POMatch(
                requires_review=True,
                explanation="Cannot match PO without a known vendor"
            )

        vendor = vendor_match.vendor

        # Check for blocked vendor
        if vendor.status == "blocked":
            return POMatch(
                requires_review=True,
                explanation=f"Vendor '{vendor.name}' is blocked. PO matching skipped."
            )

        # Explicit PO reference from invoice
        if extracted_data.po_reference:
            return self._match_explicit_po(
                extracted_data.po_reference,
                vendor,
                extracted_data
            )

        # No explicit PO reference - search for candidates
        return self._search_candidate_pos(vendor, extracted_data)

    def _match_explicit_po(
        self,
        po_reference: str,
        vendor,
        extracted_data: ExtractedInvoiceData
    ) -> POMatch:
        """Match based on explicit PO reference."""
        po = self.db.get_po_by_number(po_reference)

        if not po:
            return POMatch(
                requires_review=True,
                explanation=f"PO '{po_reference}' not found in reference data"
            )

        # Check vendor matches
        if po.vendor_id != vendor.id:
            return POMatch(
                po=po,
                match_type="explicit",
                confidence="low",
                requires_review=True,
                explanation=f"PO '{po_reference}' exists but belongs to different vendor. Invoice vendor: {vendor.name}"
            )

        # Check PO status
        if po.status != "active":
            return POMatch(
                po=po,
                match_type="explicit",
                confidence="high",
                requires_review=True,
                explanation=f"PO '{po_reference}' is {po.status}"
            )

        # Check currency match
        if extracted_data.currency and extracted_data.currency != po.currency:
            return POMatch(
                po=po,
                match_type="explicit",
                confidence="medium",
                requires_review=True,
                explanation=f"PO currency '{po.currency}' does not match invoice currency '{extracted_data.currency}'"
            )

        # Check amount compatibility
        invoice_amount = extracted_data.invoice_total or Decimal("0")
        tolerance = po.tolerance_amount

        if invoice_amount > 0:
            variance = abs(invoice_amount - po.approved_amount)
            if variance > tolerance:
                balance = self.db.get_po_balance(po.id)
                remaining = balance.remaining_balance if balance else Decimal("0")

                if invoice_amount > remaining:
                    return POMatch(
                        po=po,
                        match_type="explicit",
                        confidence="high",
                        requires_review=True,
                        explanation=f"Invoice amount {invoice_amount} exceeds remaining PO balance {remaining} (PO approved: {po.approved_amount})"
                    )
                else:
                    return POMatch(
                        po=po,
                        match_type="explicit",
                        confidence="medium",
                        requires_review=True,
                        explanation=f"Invoice amount {invoice_amount} differs from PO amount {po.approved_amount} by more than {po.tolerance_percent}% tolerance"
                    )

        # Good match
        return POMatch(
            po=po,
            match_type="explicit",
            confidence="high",
            requires_review=False,
            explanation=f"PO '{po_reference}' matched successfully. Vendor verified, PO active."
        )

    def _search_candidate_pos(
        self,
        vendor,
        extracted_data: ExtractedInvoiceData
    ) -> POMatch:
        """Search for candidate POs when no explicit reference."""
        # Get active POs for vendor
        pos = self.db.get_pos_for_vendor(vendor.id, status="active")

        if not pos:
            return POMatch(
                requires_review=True,
                explanation=f"No active POs found for vendor '{vendor.name}'"
            )

        # Filter by currency
        if extracted_data.currency:
            pos = [po for po in pos if po.currency == extracted_data.currency]

        if not pos:
            return POMatch(
                candidate_pos=[],
                requires_review=True,
                explanation=f"No POs found for vendor '{vendor.name}' matching currency '{extracted_data.currency}'"
            )

        # Filter by amount compatibility
        invoice_amount = extracted_data.invoice_total or Decimal("0")
        if invoice_amount > 0:
            candidates = []
            for po in pos:
                balance = self.db.get_po_balance(po.id)
                remaining = balance.remaining_balance if balance else Decimal("0")

                if invoice_amount <= remaining:
                    candidates.append(po)

            if candidates:
                return POMatch(
                    candidate_pos=candidates[:5],  # Limit to 5 candidates
                    confidence="medium",
                    requires_review=True,
                    explanation=f"Multiple candidate POs found for vendor. Please select the correct PO."
                )
            else:
                return POMatch(
                    candidate_pos=pos[:5],
                    confidence="low",
                    requires_review=True,
                    explanation=f"Invoice amount {invoice_amount} exceeds remaining balance on all vendor POs"
                )

        # No invoice amount to compare - return all candidates
        return POMatch(
            candidate_pos=pos[:5],
            confidence="low",
            requires_review=True,
            explanation=f"Multiple candidate POs found for vendor. Please select the correct PO."
        )


def match_po(
    extracted_data: ExtractedInvoiceData,
    vendor_match: VendorMatch
) -> POMatch:
    """Convenience function for PO matching."""
    matcher = POMatcher()
    return matcher.match(extracted_data, vendor_match)