"""
PDF Extraction Service

Handles native PDF text extraction and OCR fallback for scanned documents.
"""
import hashlib
import io
from pathlib import Path
from typing import Tuple, Optional, Literal

import fitz  # PyMuPDF
from PIL import Image
import pytesseract

from apilot import config


class PDFExtractor:
    """Extracts text from PDFs using native extraction or OCR."""

    def __init__(self):
        self.extraction_method: Optional[Literal["native", "ocr", "none"]] = None
        self._text: Optional[str] = None

    def extract(self, pdf_path: str) -> Tuple[str, Literal["native", "ocr", "none"]]:
        """
        Extract text from PDF file.

        Returns:
            Tuple of (extracted_text, extraction_method)
        """
        # Try native extraction first
        text = self._extract_native(pdf_path)

        if text and len(text.strip()) > 50:  # Reasonable text threshold
            self.extraction_method = "native"
            self._text = text
            return text, "native"

        # Fall back to OCR
        text = self._extract_ocr(pdf_path)

        if text and len(text.strip()) > 50:
            self.extraction_method = "ocr"
            self._text = text
            return text, "ocr"

        # No text extracted
        self.extraction_method = "none"
        self._text = ""
        return "", "none"

    def _extract_native(self, pdf_path: str) -> str:
        """Extract text using PyMuPDF's native extraction."""
        try:
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                text_parts.append(text)

            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            return ""

    def _extract_ocr(self, pdf_path: str) -> str:
        """Extract text using Tesseract OCR."""
        try:
            doc = fitz.open(pdf_path)
            text_parts = []

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Convert page to image
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x resolution for better OCR
                img_data = pix.tobytes("png")

                # Open as PIL image
                image = Image.open(io.BytesIO(img_data))

                # Perform OCR
                text = pytesseract.image_to_string(image)
                text_parts.append(text)

            doc.close()
            return "\n".join(text_parts)
        except Exception as e:
            return ""

    @property
    def text(self) -> str:
        """Get extracted text."""
        return self._text or ""

    def calculate_hash(self, pdf_path: str) -> str:
        """Calculate SHA-256 hash of PDF file."""
        sha256_hash = hashlib.sha256()

        try:
            with open(pdf_path, "rb") as f:
                # Read in chunks to handle large files
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return ""


def extract_text(pdf_path: str) -> Tuple[str, Literal["native", "ocr", "none"], str]:
    """
    Convenience function to extract text and calculate hash.

    Returns:
        Tuple of (text, method, file_hash)
    """
    extractor = PDFExtractor()
    text, method = extractor.extract(pdf_path)
    file_hash = extractor.calculate_hash(pdf_path)

    return text, method, file_hash


def validate_pdf(pdf_path: str) -> Tuple[bool, str]:
    """
    Validate PDF file.

    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(pdf_path)

    # Check file exists
    if not path.exists():
        return False, "File does not exist"

    # Check extension
    if path.suffix.lower() != ".pdf":
        return False, "File is not a PDF"

    # Check file size
    if path.stat().st_size == 0:
        return False, "File is empty"

    # Check if it's a valid PDF
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return False, "PDF has no pages"
        doc.close()
    except Exception as e:
        return False, f"Invalid PDF: {str(e)}"

    return True, ""