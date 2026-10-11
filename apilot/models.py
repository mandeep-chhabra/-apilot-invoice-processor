"""
APilot Data Models

Pydantic models for structured data validation.
"""
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator


class Vendor(BaseModel):
    """Vendor reference data."""
    id: Optional[int] = None
    name: str
    normalized_name: str = ""
    tax_id: Optional[str] = None
    status: Literal["active", "blocked"] = "active"

    def normalize_name(self) -> str:
        """Normalize vendor name for matching."""
        return self.name.lower().strip().replace(" ", "")


class POLineItem(BaseModel):
    """Purchase order line item."""
    id: Optional[int] = None
    po_id: int
    description: str
    quantity: Decimal = Field(..., decimal_places=2)
    unit_price: Decimal = Field(..., decimal_places=2)

    @field_validator("quantity", "unit_price", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    @property
    def line_total(self) -> Decimal:
        return self.quantity * self.unit_price


class PurchaseOrder(BaseModel):
    """Purchase order reference data."""
    id: Optional[int] = None
    po_number: str
    vendor_id: int
    vendor: Optional[Vendor] = None
    currency: str = "INR"
    approved_amount: Decimal = Field(..., decimal_places=2)
    tolerance_percent: Decimal = Field(default=Decimal("2.0"), decimal_places=2)
    status: Literal["active", "closed", "cancelled"] = "active"
    line_items: List[POLineItem] = []

    @field_validator("approved_amount", "tolerance_percent", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v

    @property
    def tolerance_amount(self) -> Decimal:
        """Calculate tolerance amount."""
        return self.approved_amount * (self.tolerance_percent / Decimal("100"))


class InvoiceLineItem(BaseModel):
    """Invoice line item extracted from PDF."""
    description: Optional[str] = None
    quantity: Optional[Decimal] = None
    unit_price: Optional[Decimal] = None

    @field_validator("quantity", "unit_price", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        if isinstance(v, str) and v.strip():
            try:
                return Decimal(v)
            except:
                return None
        return v

    @property
    def line_total(self) -> Optional[Decimal]:
        if self.quantity is None or self.unit_price is None:
            return None
        return self.quantity * self.unit_price


class ExtractedInvoiceData(BaseModel):
    """Structured invoice data extracted from PDF via Gemini."""
    vendor_name: Optional[str] = None
    vendor_tax_id: Optional[str] = None
    customer_name: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    po_reference: Optional[str] = None
    currency: Optional[str] = "INR"
    line_items: List[InvoiceLineItem] = []
    subtotal: Optional[Decimal] = None
    tax_components: List[dict] = []  # [{"name": "CGST", "rate": 9, "amount": 100}]
    shipping: Optional[Decimal] = None
    discount: Optional[Decimal] = None
    invoice_total: Optional[Decimal] = None
    payment_terms: Optional[str] = None
    missing_fields: List[str] = []
    extraction_warnings: List[str] = []
    ambiguous_info: dict = {}

    @field_validator("currency", mode="before")
    @classmethod
    def set_default_currency(cls, v):
        if v is None:
            return "INR"
        return v

    @field_validator("subtotal", "shipping", "discount", "invoice_total", mode="before")
    @classmethod
    def parse_decimal(cls, v):
        if isinstance(v, (int, float)):
            return Decimal(str(v))
        return v


class VendorMatch(BaseModel):
    """Result of vendor matching."""
    vendor: Optional[Vendor] = None
    match_type: Optional[Literal["exact_tax_id", "exact_name", "fuzzy_name", "none"]] = None
    confidence: Literal["high", "medium", "low"] = "low"
    requires_review: bool = False
    explanation: str = ""


class POMatch(BaseModel):
    """Result of PO matching."""
    po: Optional[PurchaseOrder] = None
    match_type: Optional[Literal["explicit", "vendor_search", "none"]] = None
    candidate_pos: List[PurchaseOrder] = []
    confidence: Literal["high", "medium", "low"] = "low"
    requires_review: bool = False
    explanation: str = ""


class DuplicateCheck(BaseModel):
    """Result of duplicate detection."""
    is_duplicate: bool = False
    duplicate_type: Optional[Literal["exact_file", "business"]] = None
    existing_run_id: Optional[int] = None
    conflicting_amount: bool = False
    explanation: str = ""


class POBalance(BaseModel):
    """PO balance information."""
    po_id: int
    po_number: str
    approved_amount: Decimal
    recorded_amount: Decimal = Decimal("0")
    remaining_balance: Decimal
    currency: str = "INR"


class ValidationResult(BaseModel):
    """Result of a single validation rule."""
    rule_name: str
    status: Literal["PASS", "FAIL", "REVIEW_REQUIRED", "NOT_APPLICABLE"]
    expected: Optional[str] = None
    actual: Optional[str] = None
    variance: Optional[Decimal] = None
    explanation: str
    blocks_approval: bool = False


class ProcessingStatus(BaseModel):
    """Current processing status."""
    stage: str = ""
    status: Literal["pending", "running", "completed", "failed", "review_required"] = "pending"
    message: str = ""
    timestamp: Optional[datetime] = None


class AuditEvent(BaseModel):
    """Audit event for processing trail."""
    id: Optional[int] = None
    run_id: str
    stage: str
    status: Literal["info", "success", "warning", "error"] = "info"
    timestamp: datetime = Field(default_factory=datetime.now)
    explanation: str = ""


class InvoiceRun(BaseModel):
    """Complete invoice processing run."""
    id: Optional[int] = None
    run_id: str
    original_filename: str
    file_hash: str
    extracted_data: Optional[ExtractedInvoiceData] = None
    extraction_status: Literal["pending", "success", "failed", "cached"] = "pending"
    vendor_match: Optional[VendorMatch] = None
    po_match: Optional[POMatch] = None
    duplicate_check: Optional[DuplicateCheck] = None
    po_balance: Optional[POBalance] = None
    validation_results: List[ValidationResult] = []
    business_decision: Optional[Literal["APPROVE", "REVIEW", "REJECT"]] = None
    decision_explanation: str = ""
    processing_status: Literal["pending", "processing", "completed", "failed"] = "pending"
    timestamp: datetime = Field(default_factory=datetime.now)
    audit_events: List[AuditEvent] = []
    is_fixture: bool = False  # Mark fixture-based results


class ProcessingResult(BaseModel):
    """Final processing result returned to UI."""
    run: InvoiceRun
    stages_completed: List[str] = []
    total_stages: int = 10
    gemini_calls: int = 0
    error: Optional[str] = None