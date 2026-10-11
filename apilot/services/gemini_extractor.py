"""
Gemini Extraction Service

Uses Gemini 3.8 Flash to extract structured invoice data from extracted text.
"""
import json
from typing import Optional
from google import genai

from apilot import config
from apilot.models import ExtractedInvoiceData


GEMINI_EXTRACTION_PROMPT = """You are an AI assistant that extracts structured invoice data from text.

Extract the following fields from the invoice text. If a field is missing or unreadable, set it to null.
If you're uncertain about a value, note it in extraction_warnings.

Fields to extract:
- vendor_name: The vendor/supplier name
- vendor_tax_id: Vendor's tax identification number
- customer_name: The buyer/customer name
- invoice_number: Unique invoice identifier
- invoice_date: Invoice date (YYYY-MM-DD format)
- due_date: Payment due date (YYYY-MM-DD format)
- po_reference: Purchase order reference number
- currency: Currency code (e.g., INR, USD)
- line_items: Array of {description, quantity, unit_price}
- subtotal: Subtotal amount before tax
- tax_components: Array of {name, rate, amount} (e.g., CGST, SGST)
- shipping: Shipping/handling charges
- discount: Discount applied
- invoice_total: Total amount due
- payment_terms: Payment terms (e.g., "Net 30")
- missing_fields: List of fields that are missing or unreadable
- extraction_warnings: List of warnings about ambiguous or uncertain data
- ambiguous_info: Object noting which fields have ambiguous values

Return ONLY valid JSON in this exact format:
{
  "vendor_name": "...",
  "vendor_tax_id": "...",
  "customer_name": "...",
  "invoice_number": "...",
  "invoice_date": "...",
  "due_date": "...",
  "po_reference": "...",
  "currency": "INR",
  "line_items": [{"description": "...", "quantity": 1.0, "unit_price": 100.0}],
  "subtotal": 100.0,
  "tax_components": [{"name": "CGST", "rate": 9.0, "amount": 9.0}],
  "shipping": 0.0,
  "discount": 0.0,
  "invoice_total": 109.0,
  "payment_terms": "...",
  "missing_fields": [],
  "extraction_warnings": [],
  "ambiguous_info": {}
}

If text extraction was unsuccessful or insufficient, set most fields to null and note in extraction_warnings.
"""


class GeminiExtractor:
    """Extracts structured invoice data using Gemini 3.8 Flash."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        self.model = model or config.GEMINI_MODEL
        self.client = None
        self.last_error: Optional[str] = None

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                self.last_error = f"Failed to initialize Gemini client: {str(e)}"

    def is_available(self) -> bool:
        """Check if Gemini API is available."""
        return self.client is not None

    def extract(self, text: str) -> ExtractedInvoiceData:
        """
        Extract structured data from invoice text using Gemini.

        Returns:
            ExtractedInvoiceData or None if extraction fails
        """
        if not self.client:
            return self._create_error_result(self.last_error or "Gemini client not initialized")

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=GEMINI_EXTRACTION_PROMPT + "\n\nInvoice text:\n" + text[:8000]
            )

            if not response.text:
                return self._create_error_result("Empty response from Gemini")

            # Parse JSON from response
            json_str = self._extract_json(response.text)

            if not json_str:
                return self._create_error_result("No valid JSON in Gemini response")

            data = json.loads(json_str)
            return ExtractedInvoiceData(**data)

        except Exception as e:
            error_msg = str(e)
            # Check for quota or API errors
            if "429" in error_msg or "quota" in error_msg.lower():
                return self._create_error_result("API quota exceeded. Please try again later.")
            if "api_key" in error_msg.lower() or "authentication" in error_msg.lower():
                return self._create_error_result("Gemini API key not configured or invalid. Please set GEMINI_API_KEY in .env")
            if "json" in error_msg.lower() or "decode" in error_msg.lower():
                return self._create_error_result(f"Failed to parse Gemini response: {error_msg}")
            return self._create_error_result(f"Gemini extraction failed: {error_msg}")

    def _extract_json(self, text: str) -> Optional[str]:
        """Extract JSON from text that may contain markdown code blocks."""
        # Handle markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return text[start:end].strip()

        # Try to find JSON directly
        start = text.find("{")
        end = text.rfind("}")

        if start >= 0 and end > start:
            return text[start:end+1]

        return None

    def _create_error_result(self, error: str) -> ExtractedInvoiceData:
        """Create an error result with warnings."""
        self.last_error = error
        return ExtractedInvoiceData(
            extraction_warnings=[error],
            missing_fields=["extraction_failed"]
        )


def extract_invoice_data(text: str, api_key: str = None) -> ExtractedInvoiceData:
    """
    Convenience function for invoice extraction.

    Returns:
        ExtractedInvoiceData object
    """
    extractor = GeminiExtractor(api_key=api_key)
    return extractor.extract(text)


# Global extractor instance
_extractor: Optional[GeminiExtractor] = None


def get_extractor() -> GeminiExtractor:
    """Get or create global extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = GeminiExtractor()
    return _extractor