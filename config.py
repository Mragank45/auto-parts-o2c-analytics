"""Central configuration for the O2C analytics project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "o2c.db"
REPORT_DIR = ROOT / "reports"

# Synthetic data settings
SEED = 42
N_CUSTOMERS = 60
N_MATERIALS = 150
N_ORDERS = 4000
START_DATE = "2025-01-01"
END_DATE = "2026-10-31"

# "Today" used for ageing calculations (fixed so results are reproducible)
AS_OF_DATE = "2026-11-21"

# Business thresholds
OTIF_TARGET = 0.95
DSO_TARGET_DAYS = 45
OVERDUE_ALERT_DAYS = 30
