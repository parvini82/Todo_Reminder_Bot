# Telegram To-Do & Reminder Bot

**Last Updated:** November 29, 2025

## Overview
Production-ready Telegram bot that captures natural-language tasks, stores them in PostgreSQL, and sends daily summaries at 07:00 (Europe/Vienna timezone).

## Current State
- **Status:** Running and operational
- **Database:** PostgreSQL (Replit managed)
- **Deployment:** Ready to use

## Features
- Natural language task parsing using OpenRouter AI
- Task management with due dates
- Daily summary notifications at 07:00
- Commands: /start, /help, /today, /all, /missed, /done, /delete
- Timezone: Europe/Vienna

## Architecture
- **Bot Framework:** python-telegram-bot 20.7
- **Database:** SQLAlchemy 2.0.25 with PostgreSQL
- **Scheduler:** APScheduler 3.10.4
- **AI Processing:** OpenRouter API

## Project Structure
```
bot/
├── main.py          # Entry point, starts bot and scheduler
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

## Dependencies
- python-telegram-bot==20.7
- SQLAlchemy==2.0.25
- APScheduler==3.10.4
- python-dotenv==1.0.0
- requests==2.31.0
- python-dateutil==2.8.2
- jdatetime==4.1.0
- psycopg2-binary==2.9.11

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
- **2025-11-29:** Initial setup completed
  - Installed Python 3.11 and all dependencies
  - Configured environment variables
  - Added psycopg2-binary for PostgreSQL support
  - Bot is running and ready to use

## User Preferences
None documented yet.
