"""
APilot Database Module

SQLite persistence for vendors, purchase orders, invoice runs, and audit events.
"""
import json
import sqlite3
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Any
from contextlib import contextmanager

from apilot import config
from apilot.models import (
    Vendor, PurchaseOrder, POLineItem, ExtractedInvoiceData,
    VendorMatch, POMatch, DuplicateCheck, POBalance, ValidationResult,
    InvoiceRun, AuditEvent
)


def decimal_serializer(obj):
    """JSON serializer for Decimal objects."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def decimal_parser(dct):
    """Parse Decimal strings back to Decimal in JSON deserialization."""
    for key, value in dct.items():
        if isinstance(value, str) and key in [
            'approved_amount', 'tolerance_percent', 'quantity', 'unit_price',
            'subtotal', 'shipping', 'discount', 'invoice_total', 'recorded_amount',
            'remaining_balance', 'variance'
        ]:
            try:
                dct[key] = Decimal(value)
            except:
                pass
    return dct


class Database:
    """SQLite database manager for APilot."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self):
        """Ensure database directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Vendors table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    tax_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active'
                )
            """)

            # Purchase Orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_number TEXT NOT NULL UNIQUE,
                    vendor_id INTEGER NOT NULL,
                    currency TEXT NOT NULL DEFAULT 'INR',
                    approved_amount TEXT NOT NULL,
                    tolerance_percent TEXT NOT NULL DEFAULT '2.0',
                    status TEXT NOT NULL DEFAULT 'active',
                    FOREIGN KEY (vendor_id) REFERENCES vendors (id)
                )
            """)

            # PO Line Items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS po_line_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    unit_price TEXT NOT NULL,
                    FOREIGN KEY (po_id) REFERENCES purchase_orders (id)
                )
            """)

            # Invoice Runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoice_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL UNIQUE,
                    original_filename TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    extracted_data TEXT,
                    extraction_status TEXT NOT NULL DEFAULT 'pending',
                    vendor_match TEXT,
                    po_match TEXT,
                    duplicate_check TEXT,
                    po_balance TEXT,
                    validation_results TEXT,
                    business_decision TEXT,
                    decision_explanation TEXT,
                    processing_status TEXT NOT NULL DEFAULT 'pending',
                    timestamp TEXT NOT NULL,
                    audit_events TEXT,
                    is_fixture INTEGER NOT NULL DEFAULT 0
                )
            """)

            # PO Invoice Allocations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS po_invoice_allocations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    po_id INTEGER NOT NULL,
                    run_id TEXT NOT NULL,
                    amount TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    UNIQUE(run_id),
                    FOREIGN KEY (po_id) REFERENCES purchase_orders (id)
                )
            """)

            # Extraction Cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS extraction_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL UNIQUE,
                    extracted_data TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_file_hash ON invoice_runs(file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_filename ON invoice_runs(original_filename)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_hash ON extraction_cache(file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_allocations_po ON po_invoice_allocations(po_id)")

    # Vendor operations
    def add_vendor(self, vendor: Vendor) -> int:
        """Add a vendor to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vendors (name, normalized_name, tax_id, status)
                VALUES (?, ?, ?, ?)
            """, (vendor.name, vendor.name.lower().strip().replace(" ", ""),
                  vendor.tax_id, vendor.status))
            return cursor.lastrowid

    def get_vendor(self, vendor_id: int) -> Optional[Vendor]:
        """Get vendor by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,))
            row = cursor.fetchone()
            if row:
                return Vendor(
                    id=row['id'],
                    name=row['name'],
                    normalized_name=row['normalized_name'],
                    tax_id=row['tax_id'],
                    status=row['status']
                )
        return None

    def get_vendor_by_tax_id(self, tax_id: str) -> Optional[Vendor]:
        """Get vendor by tax ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vendors WHERE tax_id = ?", (tax_id,))
            row = cursor.fetchone()
            if row:
                return Vendor(
                    id=row['id'],
                    name=row['name'],
                    normalized_name=row['normalized_name'],
                    tax_id=row['tax_id'],
                    status=row['status']
                )
        return None

    def get_all_vendors(self) -> List[Vendor]:
        """Get all vendors."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vendors ORDER BY name")
            return [Vendor(
                id=row['id'],
                name=row['name'],
                normalized_name=row['normalized_name'],
                tax_id=row['tax_id'],
                status=row['status']
            ) for row in cursor.fetchall()]

    # PO operations
    def add_po(self, po: PurchaseOrder) -> int:
        """Add a purchase order to the database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO purchase_orders (po_number, vendor_id, currency, approved_amount, tolerance_percent, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (po.po_number, po.vendor_id, po.currency, str(po.approved_amount),
                  str(po.tolerance_percent), po.status))
            po_id = cursor.lastrowid

            # Add line items
            for item in po.line_items:
                cursor.execute("""
                    INSERT INTO po_line_items (po_id, description, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                """, (po_id, item.description, str(item.quantity), str(item.unit_price)))

            return po_id

    def get_po(self, po_id: int) -> Optional[PurchaseOrder]:
        """Get PO by ID with line items."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM purchase_orders WHERE id = ?", (po_id,))
            row = cursor.fetchone()
            if not row:
                return None

            vendor = self.get_vendor(row['vendor_id'])

            # Get line items
            cursor.execute("SELECT * FROM po_line_items WHERE po_id = ?", (po_id,))
            line_items = [POLineItem(
                id=item['id'],
                po_id=po_id,
                description=item['description'],
                quantity=Decimal(item['quantity']),
                unit_price=Decimal(item['unit_price'])
            ) for item in cursor.fetchall()]

            return PurchaseOrder(
                id=row['id'],
                po_number=row['po_number'],
                vendor_id=row['vendor_id'],
                vendor=vendor,
                currency=row['currency'],
                approved_amount=Decimal(row['approved_amount']),
                tolerance_percent=Decimal(row['tolerance_percent']),
                status=row['status'],
                line_items=line_items
            )

    def get_po_by_number(self, po_number: str) -> Optional[PurchaseOrder]:
        """Get PO by number."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM purchase_orders WHERE po_number = ?", (po_number,))
            row = cursor.fetchone()
            if row:
                return self.get_po(row['id'])
        return None

    def get_pos_for_vendor(self, vendor_id: int, status: str = "active") -> List[PurchaseOrder]:
        """Get all POs for a vendor."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id FROM purchase_orders
                WHERE vendor_id = ? AND status = ?
                ORDER BY po_number
            """, (vendor_id, status))
            return [self.get_po(row['id']) for row in cursor.fetchall()]

    def get_all_pos(self) -> List[PurchaseOrder]:
        """Get all purchase orders."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM purchase_orders ORDER BY po_number")
            return [self.get_po(row['id']) for row in cursor.fetchall()]

    # PO Balance operations
    def get_po_balance(self, po_id: int) -> POBalance:
        """Calculate remaining PO balance."""
        po = self.get_po(po_id)
        if not po:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(CAST(amount AS REAL)) as recorded
                FROM po_invoice_allocations
                WHERE po_id = ? AND decision IN ('APPROVE')
            """, (po_id,))
            row = cursor.fetchone()
            recorded = Decimal(str(row['recorded'] or 0))

        return POBalance(
            po_id=po_id,
            po_number=po.po_number,
            approved_amount=po.approved_amount,
            recorded_amount=recorded,
            remaining_balance=po.approved_amount - recorded,
            currency=po.currency
        )

    def add_allocation(self, po_id: int, run_id: str, amount: Decimal, decision: str) -> None:
        """Add invoice allocation to PO."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO po_invoice_allocations (po_id, run_id, amount, decision, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (po_id, run_id, str(amount), decision, datetime.now().isoformat()))

    def get_allocation_by_run(self, run_id: str) -> Optional[Tuple]:
        """Get allocation by run ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM po_invoice_allocations WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            return row if row else None

    # Invoice Run operations
    def save_run(self, run: InvoiceRun) -> None:
        """Save or update an invoice run."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            extracted_json = None
            if run.extracted_data:
                extracted_json = json.dumps(run.extracted_data.model_dump(), default=decimal_serializer)

            vendor_match_json = None
            if run.vendor_match:
                vendor_match_json = json.dumps(run.vendor_match.model_dump(), default=decimal_serializer)

            po_match_json = None
            if run.po_match:
                po_match_json = json.dumps(run.po_match.model_dump(), default=decimal_serializer)

            dup_check_json = None
            if run.duplicate_check:
                dup_check_json = json.dumps(run.duplicate_check.model_dump(), default=decimal_serializer)

            po_balance_json = None
            if run.po_balance:
                po_balance_json = json.dumps(run.po_balance.model_dump(), default=decimal_serializer)

            validation_json = None
            if run.validation_results:
                validation_json = json.dumps([v.model_dump() for v in run.validation_results], default=decimal_serializer)

            audit_json = None
            if run.audit_events:
                audit_json = json.dumps([a.model_dump() for a in run.audit_events], default=decimal_serializer)

            cursor.execute("""
                INSERT OR REPLACE INTO invoice_runs (
                    run_id, original_filename, file_hash, extracted_data, extraction_status,
                    vendor_match, po_match, duplicate_check, po_balance, validation_results,
                    business_decision, decision_explanation, processing_status, timestamp,
                    audit_events, is_fixture
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id, run.original_filename, run.file_hash, extracted_json,
                run.extraction_status, vendor_match_json, po_match_json, dup_check_json,
                po_balance_json, validation_json, run.business_decision, run.decision_explanation,
                run.processing_status, run.timestamp.isoformat(), audit_json, 1 if run.is_fixture else 0
            ))

    def get_run(self, run_id: str) -> Optional[InvoiceRun]:
        """Get invoice run by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoice_runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_run(row)

    def get_all_runs(self, limit: int = 50) -> List[InvoiceRun]:
        """Get all invoice runs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoice_runs ORDER BY timestamp DESC LIMIT ?", (limit,))
            return [self._row_to_run(row) for row in cursor.fetchall()]

    def _row_to_run(self, row: sqlite3.Row) -> InvoiceRun:
        """Convert database row to InvoiceRun."""
        extracted_data = None
        if row['extracted_data']:
            data = json.loads(row['extracted_data'])
            extracted_data = ExtractedInvoiceData(**decimal_parser(data))

        vendor_match = None
        if row['vendor_match']:
            vendor_match = VendorMatch(**decimal_parser(json.loads(row['vendor_match'])))

        po_match = None
        if row['po_match']:
            po_match = POMatch(**decimal_parser(json.loads(row['po_match'])))

        dup_check = None
        if row['duplicate_check']:
            dup_check = DuplicateCheck(**json.loads(row['duplicate_check']))

        po_balance = None
        if row['po_balance']:
            po_balance = POBalance(**decimal_parser(json.loads(row['po_balance'])))

        validation_results = []
        if row['validation_results']:
            for v in json.loads(row['validation_results']):
                validation_results.append(ValidationResult(**decimal_parser(v)))

        audit_events = []
        if row['audit_events']:
            for a in json.loads(row['audit_events']):
                audit_events.append(AuditEvent(**a))

        return InvoiceRun(
            id=row['id'],
            run_id=row['run_id'],
            original_filename=row['original_filename'],
            file_hash=row['file_hash'],
            extracted_data=extracted_data,
            extraction_status=row['extraction_status'],
            vendor_match=vendor_match,
            po_match=po_match,
            duplicate_check=dup_check,
            po_balance=po_balance,
            validation_results=validation_results,
            business_decision=row['business_decision'],
            decision_explanation=row['decision_explanation'],
            processing_status=row['processing_status'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            audit_events=audit_events,
            is_fixture=bool(row['is_fixture'])
        )

    # Extraction cache operations
    def get_cached_extraction(self, file_hash: str) -> Optional[ExtractedInvoiceData]:
        """Get cached extraction by file hash."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT extracted_data FROM extraction_cache WHERE file_hash = ?", (file_hash,))
            row = cursor.fetchone()
            if row:
                data = json.loads(row['extracted_data'])
                return ExtractedInvoiceData(**decimal_parser(data))
        return None

    def cache_extraction(self, file_hash: str, extracted_data: ExtractedInvoiceData) -> None:
        """Cache successful extraction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO extraction_cache (file_hash, extracted_data, timestamp)
                VALUES (?, ?, ?)
            """, (file_hash, json.dumps(extracted_data.model_dump(), default=decimal_serializer),
                  datetime.now().isoformat()))

    # Duplicate detection
    def check_business_duplicate(self, vendor_id: int, invoice_number: str) -> Optional[InvoiceRun]:
        """Check for business-level duplicate."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT run_id FROM invoice_runs
                WHERE business_decision = 'APPROVE'
                AND extracted_data LIKE ?
            """, (f'%"invoice_number": "{invoice_number}"%',))
            row = cursor.fetchone()
            if row:
                return self.get_run(row['run_id'])
        return None

    def run_exists(self, file_hash: str) -> bool:
        """Check if file hash already exists."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM invoice_runs WHERE file_hash = ?", (file_hash,))
            return cursor.fetchone() is not None

    # Statistics
    def get_stats(self) -> dict:
        """Get processing statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as total FROM invoice_runs WHERE is_fixture = 0")
            total = cursor.fetchone()['total']

            cursor.execute("SELECT COUNT(*) as count FROM invoice_runs WHERE business_decision = 'APPROVE' AND is_fixture = 0")
            approved = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM invoice_runs WHERE business_decision = 'REVIEW' AND is_fixture = 0")
            review = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM invoice_runs WHERE business_decision = 'REJECT' AND is_fixture = 0")
            rejected = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM invoice_runs WHERE processing_status = 'failed' AND is_fixture = 0")
            failed = cursor.fetchone()['count']

            return {
                'total': total,
                'approved': approved,
                'review': review,
                'rejected': rejected,
                'failed': failed
            }


# Global database instance
db = Database()