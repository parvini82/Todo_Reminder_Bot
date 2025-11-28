# Telegram To-Do & Reminder Bot

Production-ready Telegram bot that captures natural-language tasks, stores them in SQLite, and sends daily summaries.

## Setup

1. Create a `.env` file (you can copy `.env.example`):
   ```
   TELEGRAM_BOT_TOKEN=...
   OPENROUTER_API_KEY=...
   OPENROUTER_MODEL=openrouter/auto
   TIMEZONE=Europe/Vienna
   ```
2. Create a Telegram bot via BotFather and paste the token.
3. Generate an OpenRouter API key at https://openrouter.ai/ and paste it.

## Run on Replit

1. Import this repo into Replit.
2. Open the shell and run:
   ```
   ./run.sh
   ```
   The script installs dependencies and starts long polling.

## Daily Summary

- APScheduler triggers at 07:00 (configured timezone) to send summaries for:
  - Today's tasks
  - Overdue tasks
  - No-date tasks

## Commands

- `/start` welcome text
- `/help` usage guide
- `/today` tasks due today
- `/all` pending tasks
- `/missed` overdue tasks
- `/done <id>` mark task done
- `/delete <id>` soft delete task
- Sending any other text creates a task using OpenRouter parsing.
