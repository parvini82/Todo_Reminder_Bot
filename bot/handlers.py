"""Telegram bot handlers."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from dateutil import parser as date_parser
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from zoneinfo import ZoneInfo

from .ai_client import safe_parse_task
from .database import session_scope
from .models import Task
from .config import TIMEZONE

LOCAL_TZ = ZoneInfo(TIMEZONE)
UTC = ZoneInfo("UTC")


def _to_utc(dt_str: Optional[str]):
    if not dt_str:
        return None
    dt = date_parser.isoparse(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC)


def _format_tasks(tasks: List[Task]) -> str:
    if not tasks:
        return "No tasks found."
    lines = []
    for task in tasks:
        due = (
            task.due_datetime.astimezone(LOCAL_TZ).strftime("%Y-%m-%d %H:%M")
            if task.due_datetime
            else "No due date"
        )
        lines.append(f"#{task.id} [{task.priority}] <b>{task.title}</b> - {due}")
    return "\n".join(lines)


def _today_bounds() -> tuple:
    now = datetime.now(LOCAL_TZ)
    start = datetime(now.year, now.month, now.day, tzinfo=LOCAL_TZ)
    end = start.replace(hour=23, minute=59, second=59)
    return start.astimezone(UTC), end.astimezone(UTC)


def _get_user_id(update: Update) -> str:
    return str(update.effective_user.id)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to your To-Do & Reminder Bot!\n"
        "Send me tasks in natural language and I'll keep track."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/today - Tasks due today\n"
        "/all - All pending tasks\n"
        "/missed - Overdue tasks\n"
        "/done <id> - Mark task done\n"
        "/delete <id> - Delete a task\n"
        "Send any other text to create a task."
    )


def _fetch_tasks(filter_query) -> List[Task]:
    with session_scope() as session:
        return filter_query(session).all()


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)

    def query(session):
        start, end = _today_bounds()
        return (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.due_datetime.isnot(None),
                Task.due_datetime >= start,
                Task.due_datetime <= end,
            )
            .order_by(Task.priority.desc(), Task.due_datetime.asc())
        )

    tasks = _fetch_tasks(query)
    await update.message.reply_text(
        _format_tasks(tasks),
        parse_mode=ParseMode.HTML,
    )


async def all_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)

    def query(session):
        return (
            session.query(Task)
            .filter(Task.user_id == user_id, Task.status == "pending")
            .order_by(Task.created_at.asc())
        )

    tasks = _fetch_tasks(query)
    await update.message.reply_text(
        _format_tasks(tasks),
        parse_mode=ParseMode.HTML,
    )


async def missed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)

    def query(session):
        now_utc = datetime.now(LOCAL_TZ).astimezone(UTC)
        return (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.due_datetime.isnot(None),
                Task.due_datetime < now_utc,
            )
            .order_by(Task.due_datetime.asc())
        )

    tasks = _fetch_tasks(query)
    await update.message.reply_text(
        _format_tasks(tasks),
        parse_mode=ParseMode.HTML,
    )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /done <task_id>")
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Task ID must be a number.")
        return
    user_id = _get_user_id(update)
    with session_scope() as session:
        task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text("Task not found.")
            return
        task.status = "done"
        message = f"Marked task #{task.id} as done."
    await update.message.reply_text(message)


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /delete <task_id>")
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Task ID must be a number.")
        return
    user_id = _get_user_id(update)
    with session_scope() as session:
        task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text("Task not found.")
            return
        task.status = "deleted"
        message = f"Deleted task #{task.id}."
    await update.message.reply_text(message)


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Please send a task description.")
        return
    user_id = _get_user_id(update)
    parsed = safe_parse_task(text)
    due_dt = _to_utc(parsed.get("due_datetime"))

    with session_scope() as session:
        task = Task(
            user_id=user_id,
            raw_text=text,
            title=parsed.get("title") or text,
            due_datetime=due_dt,
            priority=parsed.get("priority", "normal"),
        )
        session.add(task)
        session.flush()
        message = f"Created task #{task.id}: {task.title}"
    await update.message.reply_text(message)


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("all", all_pending))
    application.add_handler(CommandHandler("missed", missed))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("delete", delete))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_task))
