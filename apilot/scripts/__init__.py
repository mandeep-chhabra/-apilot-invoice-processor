"""APilot scripts package."""
from apilot.scripts.seed_data import main as seed_data
from apilot.scripts.generate_sample_invoices import main as generate_invoices

__all__ = ["seed_data", "generate_invoices"]