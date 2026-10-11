# APilot - AI-Powered Invoice Processing

An AI-powered accounts payable invoice processing application that uses Google Gemini 3.8 Flash to extract structured data from PDF invoices and make intelligent approval decisions.

## Features

- **PDF Text Extraction**: Native PDF text extraction with OCR fallback for scanned documents
- **AI-Powered Extraction**: Uses Gemini 3.8 Flash for structured invoice data extraction
- **Vendor Matching**: Matches invoice vendors against reference data with fuzzy matching
- **PO Matching**: Intelligent purchase order matching with candidate suggestions
- **Duplicate Detection**: Exact-file and business-level duplicate detection
- **Financial Validation**: Deterministic validation of arithmetic, tolerance, and balance
- **Split Invoice Support**: Multiple invoices against one PO with remaining balance tracking
- **Missing Information Handling**: Explicit detection of missing critical fields
- **Audit Trail**: Complete processing history and decision explanation

## Technology Stack

- **Python 3.11+**
- **Streamlit** - Web UI
- **Google Gemini 3.8 Flash** - AI extraction
- **PyMuPDF** - PDF text extraction
- **Tesseract OCR** - Scanned document processing
- **SQLite** - Persistent storage
- **Pydantic** - Data validation

## Installation

### 1. Create Virtual Environment

```bash
python -m venv venv
```

### 2. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env.example` to `.env` and add your Gemini API key:

```bash
copy .env.example .env
```

Edit `.env`:
```
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-3.8-flash
```

### 5. Install Tesseract OCR (Windows)

Download and install Tesseract OCR from:
https://github.com/UB-Mannheim/tesseract/wiki

Update `.env` with the path:
```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### 6. Initialize Database and Seed Data

```bash
python -m apilot.scripts.seed_data
```

### 7. Run the Application

```bash
streamlit run apilot/app.py
```

The application will open at http://localhost:8501

## Demo Scenarios

The application includes pre-seeded demo scenarios:

| Scenario | Description | Expected Decision |
|----------|-------------|-------------------|
| Clean Invoice | Valid vendor, PO match, complete data | APPROVE |
| Missing PO Reference | Vendor identified, no PO reference | REVIEW |
| Duplicate | Same invoice number already processed | REJECT |
| Amount Mismatch | Invoice exceeds remaining PO balance | REVIEW |
| Blocked Vendor | Vendor marked as blocked | REJECT |
| Missing Information | Critical fields missing | REVIEW |

## Project Structure

```
apilot/
├── app.py                 # Main Streamlit application
├── config.py              # Configuration settings
├── models.py              # Pydantic data models
├── database.py            # SQLite database management
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variables template
├── services/
│   ├── pdf_extractor.py   # PDF text extraction & OCR
│   ├── gemini_extractor.py # Gemini AI extraction
│   ├── vendor_matcher.py  # Vendor matching logic
│   ├── po_matcher.py      # PO matching logic
│   ├── duplicate_detector.py # Duplicate detection
│   ├── validation_engine.py # Financial validation
│   ├── decision_engine.py # Decision making
│   └── audit_service.py   # Audit event logging
├── scripts/
│   └── seed_data.py       # Database seeding script
└── tests/
    ├── test_extraction.py
    ├── test_business_logic.py
    ├── test_split_invoices.py
    └── test_missing_information.py
```

## Running Tests

```bash
pytest -v
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| GEMINI_API_KEY | Google Gemini API key | (required) |
| GEMINI_MODEL | Gemini model to use | gemini-3.8-flash |
| DATABASE_PATH | SQLite database path | data/apilot.db |
| UPLOAD_DIR | Upload directory | data/uploads |
| TOLERANCE_DEFAULT | Default tolerance % | 2.0 |
| TESSERACT_CMD | Tesseract executable path | tesseract |

## Business Logic

### Approval Criteria

An invoice is automatically **APPROVED** when:
- All required fields are present (invoice number, date, total, vendor)
- Vendor is active and not blocked
- PO is matched and active
- Currency matches PO
- Amount is within tolerance and remaining balance
- No duplicates detected
- No extraction warnings

### Review Triggers

An invoice requires **REVIEW** when:
- Required fields are missing
- Multiple candidate POs exist
- Amount differs from PO beyond tolerance
- Invoice exceeds remaining PO balance
- Extraction has warnings or ambiguous data

### Rejection Triggers

An invoice is **REJECTED** when:
- Vendor is blocked
- Confirmed duplicate detected
- Critical validation failures

## License

MIT License