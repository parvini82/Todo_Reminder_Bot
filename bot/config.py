"""Load environment configuration for the bot."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Vienna")
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'tasks.db'}")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN is required. Set it in the .env file.")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is required. Set it in the .env file.")
