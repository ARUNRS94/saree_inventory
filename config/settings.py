"""Application configuration."""
from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "inventory.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
APP_NAME = "Saree Inventory & Job Work Management"
