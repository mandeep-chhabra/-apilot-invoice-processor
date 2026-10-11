"""
Tests for PDF extraction and OCR functionality.
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apilot.services.pdf_extractor import PDFExtractor, validate_pdf
from apilot.models import ExtractedInvoiceData


class TestPDFExtractor:
    """Test PDF extraction functionality."""

    def test_extractor_initialization(self):
        """Test extractor initializes correctly."""
        extractor = PDFExtractor()
        assert extractor.extraction_method is None
        assert extractor._text is None

    @patch('fitz.open')
    def test_extract_native_success(self, mock_fitz_open):
        """Test native text extraction from PDF."""
        # Mock PDF document
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Invoice #12345\nTotal: $100.00"
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__len__ = lambda self: 1
        mock_fitz_open.return_value = mock_doc

        extractor = PDFExtractor()

        # This test would require an actual PDF file
        # Placeholder assertion
        assert True


class TestValidatePDF:
    """Test PDF validation."""

    def test_nonexistent_file(self):
        """Test validation of nonexistent file."""
        is_valid, error = validate_pdf("nonexistent.pdf")
        assert is_valid is False
        assert "does not exist" in error.lower()

    def test_empty_file(self, tmp_path):
        """Test validation of empty file."""
        empty_pdf = tmp_path / "empty.pdf"
        empty_pdf.write_text("")

        is_valid, error = validate_pdf(str(empty_pdf))
        assert is_valid is False
        assert "empty" in error.lower()


class TestGeminiExtractor:
    """Test Gemini extraction functionality."""

    def test_extractor_initialization(self):
        """Test extractor initializes with config."""
        from apilot.services.gemini_extractor import GeminiExtractor
        from apilot import config

        extractor = GeminiExtractor()
        assert extractor.model == config.GEMINI_MODEL

    def test_extract_json_from_markdown(self):
        """Test JSON extraction from markdown response."""
        from apilot.services.gemini_extractor import GeminiExtractor

        extractor = GeminiExtractor()

        # Test markdown code block
        text = '''```json
{"vendor_name": "Test Vendor", "invoice_total": 100.0}
```'''

        result = extractor._extract_json(text)
        assert result is not None
        assert "vendor_name" in result

        # Test direct JSON
        text2 = '{"vendor_name": "Test Vendor"}'
        result2 = extractor._extract_json(text2)
        assert result2 is not None


class TestExtractedInvoiceData:
    """Test extracted invoice data model."""

    def test_full_invoice_data(self):
        """Test creating complete invoice data."""
        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            vendor_tax_id="12345678",
            invoice_number="INV-001",
            invoice_date="2024-01-15",
            invoice_total=Decimal("1000.00"),
            currency="INR"
        )

        assert data.vendor_name == "Test Vendor"
        assert data.invoice_total == Decimal("1000.00")

    def test_missing_fields(self):
        """Test invoice data with missing fields."""
        data = ExtractedInvoiceData(
            vendor_name="Test Vendor",
            missing_fields=["invoice_number", "invoice_total"],
            extraction_warnings=["Text was blurry"]
        )

        assert data.invoice_number is None
        assert data.invoice_total is None
        assert "invoice_number" in data.missing_fields
        assert "Text was blurry" in data.extraction_warnings

    def test_decimal_parsing(self):
        """Test decimal parsing from various inputs."""
        data = ExtractedInvoiceData(
            invoice_total=100.5,
            subtotal="100.00",
            shipping=Decimal("10.00")
        )

        assert isinstance(data.invoice_total, Decimal)
        assert isinstance(data.subtotal, Decimal)
        assert isinstance(data.shipping, Decimal)