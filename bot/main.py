"""Entry point for the Telegram To-Do & Reminder bot."""
from __future__ import annotations

import logging

from telegram.ext import Application

from .config import TELEGRAM_BOT_TOKEN
from .database import init_db
from .handlers import register_handlers
from .scheduler import start_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def main() -> None:
    init_db()
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    register_handlers(application)
    start_scheduler(application)
    application.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
