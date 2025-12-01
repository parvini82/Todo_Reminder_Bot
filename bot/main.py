"""Entry point for the Telegram To-Do & Reminder bot."""
from __future__ import annotations

import uvicorn

from .config import WEBHOOK_PORT


def main() -> None:
    """Start the webhook server."""
    uvicorn.run(
        "bot.server:app",
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
