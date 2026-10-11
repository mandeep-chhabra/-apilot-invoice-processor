"""
APilot Configuration Module

Loads environment variables and provides application configuration.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"

# Ensure data directories exist
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# Database configuration
DATABASE_PATH = os.getenv("DATABASE_PATH", str(DATA_DIR / "apilot.db"))

# Gemini API configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# Financial configuration
TOLERANCE_DEFAULT = float(os.getenv("TOLERANCE_DEFAULT", "2.0"))

# Tesseract OCR configuration
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")

# Upload configuration
MAX_UPLOAD_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".pdf"}

# Application settings
APP_TITLE = "APilot - AI Invoice Processing"
APP_ICON = "📄"