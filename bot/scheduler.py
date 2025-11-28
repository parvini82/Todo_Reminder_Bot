"""APScheduler setup for daily summaries."""
from __future__ import annotations

from datetime import datetime
from typing import List

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from .config import TIMEZONE
from .database import session_scope
from .models import Task

TIMEZONE_OBJ = ZoneInfo(TIMEZONE)
UTC = ZoneInfo("UTC")


def format_task_lines(tasks: List[Task]) -> str:
    if not tasks:
        return "None"
    lines = []
    for task in tasks:
        due = (
            task.due_datetime.astimezone(TIMEZONE_OBJ).strftime("%Y-%m-%d %H:%M")
            if task.due_datetime
            else "No due date"
        )
        lines.append(f"#{task.id} [{task.priority}] {task.title} - {due}")
    return "\n".join(lines)


def build_summary(now: datetime, user_id: str) -> str:
    today_start = datetime(now.year, now.month, now.day, tzinfo=TIMEZONE_OBJ)
    today_end = today_start.replace(hour=23, minute=59, second=59)
    today_start_utc = today_start.astimezone(UTC)
    today_end_utc = today_end.astimezone(UTC)
    now_utc = now.astimezone(UTC)

    with session_scope() as session:
        today_tasks = (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.due_datetime.isnot(None),
                Task.due_datetime >= today_start_utc,
                Task.due_datetime <= today_end_utc,
            )
            .order_by(Task.priority.desc(), Task.due_datetime.asc())
            .all()
        )

        overdue_tasks = (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.due_datetime.isnot(None),
                Task.due_datetime < now_utc,
            )
            .order_by(Task.due_datetime.asc())
            .all()
        )

        no_date_tasks = (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.due_datetime.is_(None),
            )
            .order_by(Task.created_at.asc())
            .all()
        )

    summary = [
        "Daily Summary",
        "Today's Tasks:",
        format_task_lines(today_tasks),
        "\nOverdue Tasks:",
        format_task_lines(overdue_tasks),
        "\nNo Due Date:",
        format_task_lines(no_date_tasks),
    ]
    return "\n".join(summary)


async def send_daily_summary(application) -> None:
    now = datetime.now(TIMEZONE_OBJ)
    with session_scope() as session:
        user_ids = [row[0] for row in session.query(Task.user_id).distinct().all()]

    for user_id in user_ids:
        summary = build_summary(now, user_id)
        await application.bot.send_message(chat_id=user_id, text=summary)


def start_scheduler(application) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE_OBJ)
    scheduler.add_job(
        send_daily_summary,
        CronTrigger(hour=7, minute=0, timezone=TIMEZONE_OBJ),
        args=[application],
        id="daily-summary",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
