# Telegram To-Do & Reminder Bot

**Last Updated:** December 1, 2025

## Overview
Production-ready Telegram bot that captures natural-language tasks, stores them in PostgreSQL, and sends daily summaries at 07:00 (Europe/Vienna timezone). Uses webhook mode for reliable operation on Replit.

## Current State
- **Status:** Running and operational (Webhook mode)
- **Mode:** Webhook (not polling) for better reliability
- **Database:** PostgreSQL (Replit managed)
- **Web Server:** FastAPI with Uvicorn on port 5000
- **Deployment:** Ready to use

## Features
- Natural language task parsing using OpenRouter AI
- Task management with due dates
- Daily summary notifications at 07:00
- Commands: /start, /help, /today, /all, /missed, /done, /delete
- Timezone: Europe/Vienna
- Webhook-based updates (more reliable than polling)
- Health check endpoint at `/`

## Architecture
- **Bot Framework:** python-telegram-bot 20.7
- **Web Server:** FastAPI + Uvicorn
- **Database:** SQLAlchemy 2.0.25 with PostgreSQL
- **Scheduler:** APScheduler 3.10.4
- **AI Processing:** OpenRouter API

## Project Structure
```
bot/
├── main.py          # Entry point, starts uvicorn server
├── server.py        # FastAPI webhook server
├── config.py        # Environment configuration
├── database.py      # SQLAlchemy setup and session management
├── models.py        # Database models
├── handlers.py      # Telegram command and message handlers
├── ai_client.py     # OpenRouter API integration
└── scheduler.py     # Daily summary scheduling
```

## Environment Variables
- `TELEGRAM_BOT_TOKEN` (secret): Bot token from @BotFather
- `OPENROUTER_API_KEY` (secret): API key from OpenRouter
- `OPENROUTER_MODEL`: AI model to use (default: openrouter/auto)
- `TIMEZONE`: Timezone for daily summaries (default: Europe/Vienna)
- `DATABASE_URL`: PostgreSQL connection (auto-configured by Replit)
- `REPLIT_DEV_DOMAIN`: Auto-set by Replit for webhook URL
- `WEBHOOK_PORT`: Server port (default: 5000)

## Dependencies
- python-telegram-bot==20.7
- SQLAlchemy==2.0.25
- APScheduler==3.10.4
- python-dotenv==1.0.0
- requests==2.31.0
- python-dateutil==2.8.2
- jdatetime==4.1.0
- psycopg2-binary==2.9.11
- fastapi
- uvicorn

## How to Use
1. Start a chat with your bot on Telegram
2. Send `/start` to see the welcome message
3. Send any text to create a task (e.g., "Buy groceries tomorrow at 3pm")
4. Use commands to manage tasks:
   - `/today` - View today's tasks
   - `/all` - View all pending tasks
   - `/missed` - View overdue tasks
   - `/done <id>` - Mark a task as complete
   - `/delete <id>` - Delete a task

## Recent Changes
- **2025-12-01:** Converted from polling to webhook mode
  - Added FastAPI server (server.py) for webhook handling
  - Health check endpoint at `/` keeps Replit awake
  - Webhook automatically configured using REPLIT_DEV_DOMAIN
  - Added uvicorn as ASGI server

- **2025-11-29:** Initial setup completed
  - Installed Python 3.11 and all dependencies
  - Configured environment variables
  - Added psycopg2-binary for PostgreSQL support
  - Bot is running and ready to use

## User Preferences
None documented yet.
