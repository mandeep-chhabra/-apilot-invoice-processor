"""
Vendor Matching Service

Matches extracted invoice vendors against reference data.
"""
from typing import Optional, List
from difflib import SequenceMatcher

from apilot.database import db
from apilot.models import Vendor, VendorMatch, ExtractedInvoiceData


class VendorMatcher:
    """Matches extracted vendor information to reference data."""

    def __init__(self, database: db = None):
        self.db = database or db

    def match(self, extracted_data: ExtractedInvoiceData) -> VendorMatch:
        """
        Match extracted vendor to reference data.

        Returns:
            VendorMatch with match results
        """
        if not extracted_data.vendor_name and not extracted_data.vendor_tax_id:
            return VendorMatch(
                requires_review=True,
                explanation="No vendor name or tax ID available for matching"
            )

        # Try exact tax ID match first (highest confidence)
        if extracted_data.vendor_tax_id:
            vendor = self.db.get_vendor_by_tax_id(extracted_data.vendor_tax_id)
            if vendor:
                return VendorMatch(
                    vendor=vendor,
                    match_type="exact_tax_id",
                    confidence="high",
                    requires_review=vendor.status == "blocked",
                    explanation=f"Exact match on tax ID '{extracted_data.vendor_tax_id}'. Vendor status: {vendor.status}."
                )

        # Try exact name match
        if extracted_data.vendor_name:
            normalized = extracted_data.vendor_name.lower().strip().replace(" ", "")
            all_vendors = self.db.get_all_vendors()

            for vendor in all_vendors:
                if vendor.normalized_name == normalized:
                    return VendorMatch(
                        vendor=vendor,
                        match_type="exact_name",
                        confidence="high",
                        requires_review=vendor.status == "blocked",
                        explanation=f"Exact match on vendor name '{extracted_data.vendor_name}'. Vendor status: {vendor.status}."
                    )

            # Try fuzzy matching
            best_match = self._find_best_fuzzy_match(extracted_data.vendor_name, all_vendors)

            if best_match:
                vendor, score = best_match
                if score >= 0.85:
                    return VendorMatch(
                        vendor=vendor,
                        match_type="fuzzy_name",
                        confidence="high" if score >= 0.9 else "medium",
                        requires_review=vendor.status == "blocked",
                        explanation=f"Fuzzy match on vendor name '{extracted_data.vendor_name}' (similarity: {score:.0%}). Vendor status: {vendor.status}."
                    )
                elif score >= 0.7:
                    return VendorMatch(
                        vendor=vendor,
                        match_type="fuzzy_name",
                        confidence="medium",
                        requires_review=True,
                        explanation=f"Low-confidence fuzzy match on vendor name '{extracted_data.vendor_name}' (similarity: {score:.0%}). Manual review recommended."
                    )

        # Check for conflicting evidence
        if extracted_data.vendor_name and extracted_data.vendor_tax_id:
            name_vendor = self._find_by_name(extracted_data.vendor_name)
            tax_vendor = self.db.get_vendor_by_tax_id(extracted_data.vendor_tax_id) if extracted_data.vendor_tax_id else None

            if name_vendor and tax_vendor and name_vendor.id != tax_vendor.id:
                return VendorMatch(
                    vendor=tax_vendor,
                    match_type="none",
                    confidence="low",
                    requires_review=True,
                    explanation=f"Conflicting evidence: name matches '{name_vendor.name}' but tax ID matches '{tax_vendor.name}'. Manual review required."
                )

        # No match found
        return VendorMatch(
            requires_review=True,
            explanation=f"Vendor '{extracted_data.vendor_name or 'unknown'}' (tax ID: {extracted_data.vendor_tax_id or 'none'}) not found in reference data. Manual review required."
        )

    def _find_best_fuzzy_match(self, name: str, vendors: List[Vendor]) -> Optional[tuple]:
        """Find best fuzzy match for vendor name."""
        best_score = 0
        best_vendor = None

        normalized_input = name.lower().strip().replace(" ", "")

        for vendor in vendors:
            score = SequenceMatcher(None, normalized_input, vendor.normalized_name).ratio()
            if score > best_score:
                best_score = score
                best_vendor = vendor

        return (best_vendor, best_score) if best_vendor and best_score >= 0.6 else None

    def _find_by_name(self, name: str) -> Optional[Vendor]:
        """Find vendor by name."""
        normalized = name.lower().strip().replace(" ", "")
        all_vendors = self.db.get_all_vendors()

        for vendor in all_vendors:
            if vendor.normalized_name == normalized:
                return vendor
        return None


def match_vendor(extracted_data: ExtractedInvoiceData) -> VendorMatch:
    """Convenience function for vendor matching."""
    matcher = VendorMatcher()
    return matcher.match(extracted_data)