"""Setup configuration for APilot package."""
from setuptools import setup, find_packages

setup(
    name="apilot",
    version="1.0.0",
    description="AI-Powered Invoice Processing & Decision Engine",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "streamlit>=1.40.0",
        "google-genai>=0.8.0",
        "pymupdf>=1.24.0",
        "pytesseract>=0.3.10",
        "Pillow>=10.4.0",
        "pydantic>=2.9.0",
        "pandas>=2.2.0",
        "python-dotenv>=1.0.0",
        "pytest>=8.3.0",
        "pytest-mock>=3.14.0",
    ],
)