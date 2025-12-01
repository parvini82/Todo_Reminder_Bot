"""FastAPI webhook server for the Telegram bot."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request, Response
from telegram import Update

from .config import TELEGRAM_BOT_TOKEN, PUBLIC_URL, WEBHOOK_PORT
from .database import init_db
from .handlers import register_handlers
from .scheduler import start_scheduler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram To-Do Bot")

application = None
scheduler = None


def get_application():
    """Get or create the Telegram application instance."""
    global application, scheduler
    if application is None:
        from telegram.ext import Application
        init_db()
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        register_handlers(application)
        scheduler = start_scheduler(application)
    return application


@app.get("/")
async def health_check():
    """Health check endpoint to keep Replit awake."""
    return {"status": "Bot is running", "webhook_configured": bool(PUBLIC_URL)}


@app.post(f"/webhook/{TELEGRAM_BOT_TOKEN}")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates via webhook."""
    try:
        app_instance = get_application()
        json_data = await request.json()
        update = Update.de_json(json_data, app_instance.bot)
        await app_instance.process_update(update)
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return Response(status_code=500)


@app.on_event("startup")
async def on_startup():
    """Initialize bot and set webhook on startup."""
    app_instance = get_application()
    await app_instance.initialize()
    
    if PUBLIC_URL:
        webhook_url = f"{PUBLIC_URL}/webhook/{TELEGRAM_BOT_TOKEN}"
        await app_instance.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    else:
        logger.warning("PUBLIC_URL not set, webhook not configured")


@app.on_event("shutdown")
async def on_shutdown():
    """Clean up on shutdown."""
    if application:
        await application.bot.delete_webhook()
        await application.shutdown()
    if scheduler:
        scheduler.shutdown(wait=False)
