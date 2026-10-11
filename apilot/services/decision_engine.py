"""
Decision Engine Service

Determines APPROVE, REVIEW, or REJECT based on validation results.
"""
from typing import List, Optional

from apilot.models import (
    ValidationResult, VendorMatch, POMatch, DuplicateCheck,
    POBalance, InvoiceRun
)


class DecisionEngine:
    """Determines business decision based on validation results."""

    def decide(
        self,
        validation_results: List[ValidationResult],
        vendor_match: VendorMatch,
        po_match: POMatch,
        duplicate_check: DuplicateCheck,
        po_balance: Optional[POBalance],
        extracted_data
    ) -> tuple[str, str]:
        """
        Determine business decision.

        Returns:
            Tuple of (decision, explanation)
        """
        # Check for blocking failures first
        blocking_failures = [r for r in validation_results if r.status == "FAIL" and r.blocks_approval]

        if blocking_failures:
            # Determine if it's a hard reject or review required
            for failure in blocking_failures:
                # Duplicate is a hard reject
                if failure.rule_name == "duplicate_check":
                    return "REJECT", self._generate_reject_explanation(
                        blocking_failures, vendor_match, duplicate_check
                    )

                # Blocked vendor is a hard reject
                if failure.rule_name == "vendor_approval" and "blocked" in failure.explanation.lower():
                    return "REJECT", self._generate_reject_explanation(
                        blocking_failures, vendor_match, duplicate_check
                    )

            # Other failures = REVIEW
            return "REVIEW", self._generate_review_explanation(
                blocking_failures, validation_results, vendor_match, po_match
            )

        # Check for review-required validations
        review_required = [r for r in validation_results if r.status == "REVIEW_REQUIRED" and r.blocks_approval]

        if review_required:
            return "REVIEW", self._generate_review_explanation(
                review_required, validation_results, vendor_match, po_match
            )

        # Check if all required validations passed
        required_rules = ["required_fields", "vendor_approval", "po_eligibility",
                         "currency_match", "tolerance_check", "duplicate_check"]

        all_passed = True
        for rule in required_rules:
            result = next((r for r in validation_results if r.rule_name == rule), None)
            if not result or result.status != "PASS":
                all_passed = False
                break

        if all_passed:
            return "APPROVE", self._generate_approve_explanation(
                validation_results, vendor_match, po_match, po_balance, extracted_data
            )

        # Default to review
        return "REVIEW", "Insufficient validation results to approve automatically"

    def _generate_reject_explanation(
        self,
        failures: List[ValidationResult],
        vendor_match: VendorMatch,
        duplicate_check: DuplicateCheck
    ) -> str:
        """Generate rejection explanation."""
        if duplicate_check.is_duplicate:
            return f"REJECTED: {duplicate_check.explanation}"

        if vendor_match.vendor and vendor_match.vendor.status == "blocked":
            return f"REJECTED: Vendor '{vendor_match.vendor.name}' is blocked"

        reasons = [f.explanation for f in failures]
        return "REJECTED: " + "; ".join(reasons[:2])

    def _generate_review_explanation(
        self,
        review_items: List[ValidationResult],
        all_results: List[ValidationResult],
        vendor_match: VendorMatch,
        po_match: POMatch
    ) -> str:
        """Generate review explanation."""
        explanations = []

        for item in review_items[:3]:  # Limit to 3 key issues
            explanations.append(item.explanation)

        # Add vendor/PO context
        if vendor_match.requires_review:
            explanations.append(f"Vendor match: {vendor_match.explanation}")

        if po_match.requires_review:
            if po_match.candidate_pos:
                pos = [p.po_number for p in po_match.candidate_pos[:3]]
                explanations.append(f"Multiple candidate POs: {', '.join(pos)}")
            else:
                explanations.append(f"PO match: {po_match.explanation}")

        return "REVIEW REQUIRED: " + "; ".join(explanations[:3])

    def _generate_approve_explanation(
        self,
        validation_results: List[ValidationResult],
        vendor_match: VendorMatch,
        po_match: POMatch,
        po_balance: Optional[POBalance],
        extracted_data
    ) -> str:
        """Generate approval explanation."""
        parts = []

        # Vendor
        if vendor_match.vendor:
            parts.append(f"Vendor '{vendor_match.vendor.name}' verified")

        # PO
        if po_match.po:
            parts.append(f"PO '{po_match.po.po_number}' matched")
            if po_balance:
                parts.append(f"Balance: {po_balance.remaining_balance} {po_balance.currency} remaining")

        # Amount
        if extracted_data.invoice_total:
            parts.append(f"Invoice amount: {extracted_data.invoice_total}")

        return "APPROVED: " + ". ".join(parts)


def make_decision(
    validation_results: List[ValidationResult],
    vendor_match: VendorMatch,
    po_match: POMatch,
    duplicate_check: DuplicateCheck,
    po_balance: Optional[POBalance] = None,
    extracted_data = None
) -> tuple[str, str]:
    """Convenience function for decision making."""
    engine = DecisionEngine()
    return engine.decide(validation_results, vendor_match, po_match, duplicate_check, po_balance, extracted_data)