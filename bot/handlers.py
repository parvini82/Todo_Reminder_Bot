"""Telegram bot handlers."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import jdatetime
from jdatetime import date as jdate
import pytz
from dateutil import parser as date_parser
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
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

# Store pending tasks in memory: {user_id: {title, due_datetime, priority, raw_text, waiting_for_edit}}
pending_tasks: Dict[str, Dict] = {}


def _to_local_tehran(dt_str: Optional[str]):
    """Parse datetime string and return timezone-aware datetime in Asia/Tehran timezone."""
    if dt_str is None:
        return None
    dt = date_parser.isoparse(dt_str)
    if dt.tzinfo is None:
        tz = pytz.timezone("Asia/Tehran")
        dt = tz.localize(dt)
    return dt


def _format_tasks(tasks: List[Task], label: str = "Tasks", show_due: bool = True) -> str:
    if not tasks:
        return f"<b>کارهای {label}:</b>\n\nهیچ کاری پیدا نشد."
    lines = [f"<b>کارهای {label}:</b>\n"]
    for task in tasks:
        priority_emoji = "🔴" if task.priority == "high" else "🟡"
        if show_due:
            if task.due_datetime:
                due_str = _to_jalali(task.due_datetime)
            else:
                due_str = "بدون ساعت"
            lines.append(
                f"• <b>{task.title}</b>\n"
                f"   ⏰ {due_str}\n"
                f"   📌 Priority: {priority_emoji} {task.priority} (#{task.id})"
            )
        else:
            lines.append(
                f"• <b>{task.title}</b>\n"
                f"   📌 {priority_emoji} {task.priority} (#{task.id})"
            )
    return "\n".join(lines)


def _format_general_tasks(tasks: List[Task]) -> str:
    if not tasks:
        return "<b>کارهای کلی:</b>\n\nهیچ کاری پیدا نشد."
    lines = ["<b>کارهای کلی:</b>\n"]
    for task in tasks:
        priority_emoji = "🔴" if task.priority == "high" else "🟡"
        lines.append(f"• <b>{task.title}</b> (#{task.id})\n   📌 {priority_emoji} {task.priority}")
    return "\n".join(lines)


def _today_bounds() -> tuple:
    """Get start and end of today in Asia/Tehran timezone."""
    tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tz)
    start = tz.localize(datetime(now.year, now.month, now.day, 0, 0, 0))
    end = tz.localize(datetime(now.year, now.month, now.day, 23, 59, 59))
    return start, end


def _get_user_id(update: Update) -> str:
    return str(update.effective_user.id)


def to_jalali_date_str(dt_str: str) -> str:
    """
    Convert an ISO date string (YYYY-MM-DD) to a Jalali date string (YYYY/MM/DD)
    """
    y, m, d = map(int, dt_str.split("-"))
    j = jdate.fromgregorian(year=y, month=m, day=d)
    return j.strftime("%Y/%m/%d")


def _to_jalali(dt: datetime) -> str:
    """Convert Gregorian datetime to Jalali for display."""
    # Convert to Asia/Tehran timezone for display
    tz = pytz.timezone("Asia/Tehran")
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    # Convert to naive datetime for jdatetime conversion
    naive_dt = dt.replace(tzinfo=None)
    jdt = jdatetime.datetime.fromgregorian(datetime=naive_dt)
    return jdt.strftime("%Y/%m/%d %H:%M")


def _format_due_datetime(due_dt_str: Optional[str]) -> str:
    """Format due datetime for display in Persian context (Jalali format)."""
    if not due_dt_str:
        return "بدون زمان"
    try:
        dt = date_parser.isoparse(due_dt_str)
        return _to_jalali(dt)
    except (ValueError, TypeError):
        return "بدون زمان"


def _format_priority(priority: str) -> str:
    """Format priority for display."""
    priority_map = {"high": "بالا", "normal": "عادی"}
    return priority_map.get(priority, "عادی")


def _create_preview_message(task_data: Dict) -> str:
    """Create HTML formatted preview message for task confirmation."""
    title = task_data.get("title", "")
    due_str = _format_due_datetime(task_data.get("due_datetime"))
    priority = _format_priority(task_data.get("priority", "normal"))
    category = task_data.get("category", "scheduled")
    category_str = "کلی (بدون زمان)" if category == "general" else "زمان‌دار"
    
    if category == "general":
        return (
            "<b>Task detected:</b>\n\n"
            f"عنوان: <b>{title}</b>\n"
            f"دسته: <i>{category_str}</i>\n"
            f"اولویت: {priority}\n\n"
            "آیا این کار را اضافه کنم؟"
        )
    
    return (
        "<b>Task detected:</b>\n\n"
        f"عنوان: <b>{title}</b>\n"
        f"تاریخ/زمان: <i>{due_str}</i>\n"
        f"اولویت: {priority}\n\n"
        "آیا این کار را اضافه کنم؟"
    )


def _create_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Create inline keyboard with confirmation buttons."""
    keyboard = [
        [
            InlineKeyboardButton("✔ تایید", callback_data="confirm_task"),
            InlineKeyboardButton("✖ لغو", callback_data="cancel_task"),
        ],
        [
            InlineKeyboardButton("✏ تغییر عنوان", callback_data="edit_title"),
            InlineKeyboardButton("⏰ تغییر زمان", callback_data="edit_time"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def send_tasks_for_date(update: Update, context: ContextTypes.DEFAULT_TYPE, date_str: Optional[str]) -> None:
    """Fetch and send tasks for a specific local date."""
    _ = context
    if not date_str:
        await update.message.reply_text("نتوانستم تاریخ را تشخیص دهم.", parse_mode=ParseMode.HTML)
        return
    try:
        parsed_date = date_parser.isoparse(date_str)
    except (ValueError, TypeError):
        await update.message.reply_text("تاریخ معتبر نبود. لطفاً دوباره تلاش کنید.", parse_mode=ParseMode.HTML)
        return
    tz = pytz.timezone("Asia/Tehran")
    if parsed_date.tzinfo is None:
        parsed_date = tz.localize(parsed_date)
    else:
        parsed_date = parsed_date.astimezone(tz)
    current_year = datetime.now(tz).year
    if parsed_date.year < current_year:
        parsed_date = parsed_date.replace(year=current_year)
    local_date = parsed_date
    date_label = to_jalali_date_str(local_date.strftime("%Y-%m-%d"))
    start = tz.localize(datetime(local_date.year, local_date.month, local_date.day))
    end = start.replace(hour=23, minute=59, second=59)
    user_id = _get_user_id(update)

    with session_scope() as session:
        tasks = (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.due_datetime.isnot(None),
                Task.due_datetime >= start,
                Task.due_datetime <= end,
            )
            .order_by(Task.priority.desc(), Task.due_datetime.asc())
            .all()
        )
        formatted = _format_tasks(tasks, date_label)

    await update.message.reply_text(formatted, parse_mode=ParseMode.HTML)


async def create_task_from_parsed(
    update: Update, context: ContextTypes.DEFAULT_TYPE, parsed: dict, raw_text: str
) -> None:
    """Create a task using parsed AI fields."""
    _ = context
    user_id = _get_user_id(update)
    due_dt = _to_local_tehran(parsed.get("due_datetime"))
    priority = parsed.get("priority", "normal")
    if priority not in {"normal", "high"}:
        priority = "normal"
    category = parsed.get("category", "scheduled")
    if category not in {"scheduled", "general"}:
        category = "general" if due_dt is None else "scheduled"
    if due_dt is None:
        category = "general"

    with session_scope() as session:
        task = Task(
            user_id=user_id,
            raw_text=raw_text,
            title=parsed.get("title") or raw_text,
            due_datetime=due_dt,
            priority=priority,
            category=category,
        )
        session.add(task)
        session.flush()
        message = f"کار با موفقیت اضافه شد ✔"
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>خوش آمدید به ربات مدیریت کارها! 🗂</b>\n\n"
        "کارهای خود را به زبان طبیعی برای من بفرستید و من آن‌ها را ثبت می‌کنم.",
        parse_mode=ParseMode.HTML
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>دستورات ربات:</b>\n\n"
        "/today - کارهای امروز 📅\n"
        "/all - همه کارهای در انتظار 🗂\n"
        "/missed - کارهای از دست رفته ⏰\n"
        "/general - کارهای کلی (بدون زمان) 📋\n"
        "/done <id> - علامت زدن کار به عنوان انجام شده ✔\n"
        "/delete <id> - حذف یک کار ✖\n\n"
        "هر متن دیگری را برای ساخت کار ارسال کنید.\n"
        "کارهای بدون تاریخ به صورت کلی ثبت می‌شوند.",
        parse_mode=ParseMode.HTML
    )


def _fetch_tasks(filter_query) -> List[Task]:
    with session_scope() as session:
        tasks = filter_query(session).all()
        for task in tasks:
            session.expunge(task)
        return tasks


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)

    def query(session):
        start, end = _today_bounds()
        return (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.category == "scheduled",
                Task.due_datetime.isnot(None),
                Task.due_datetime >= start,
                Task.due_datetime <= end,
            )
            .order_by(Task.priority.desc(), Task.due_datetime.asc())
        )

    tasks = _fetch_tasks(query)
    await update.message.reply_text(
        _format_tasks(tasks, "امروز"),
        parse_mode=ParseMode.HTML,
    )


async def all_pending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)

    with session_scope() as session:
        scheduled_tasks = (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.category == "scheduled",
            )
            .order_by(Task.due_datetime.asc().nullslast(), Task.priority.desc())
            .all()
        )
        general_tasks = (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.category == "general",
            )
            .order_by(Task.priority.desc(), Task.created_at.asc())
            .all()
        )

    sections = []
    if scheduled_tasks:
        sections.append(_format_tasks(scheduled_tasks, "زمان‌دار"))
    else:
        sections.append("<b>کارهای زمان‌دار:</b>\n\nهیچ کاری پیدا نشد.")
    
    if general_tasks:
        sections.append(_format_general_tasks(general_tasks))
    else:
        sections.append("<b>کارهای کلی:</b>\n\nهیچ کاری پیدا نشد.")

    await update.message.reply_text(
        "\n\n".join(sections),
        parse_mode=ParseMode.HTML,
    )


async def missed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)

    def query(session):
        tz = pytz.timezone("Asia/Tehran")
        now_tehran = datetime.now(tz)
        return (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.category == "scheduled",
                Task.due_datetime.isnot(None),
                Task.due_datetime < now_tehran,
            )
            .order_by(Task.due_datetime.asc())
        )

    tasks = _fetch_tasks(query)
    await update.message.reply_text(
        _format_tasks(tasks, "از دست رفته"),
        parse_mode=ParseMode.HTML,
    )


async def general(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = _get_user_id(update)

    def query(session):
        return (
            session.query(Task)
            .filter(
                Task.user_id == user_id,
                Task.status == "pending",
                Task.category == "general",
            )
            .order_by(Task.priority.desc(), Task.created_at.asc())
        )

    tasks = _fetch_tasks(query)
    await update.message.reply_text(
        _format_general_tasks(tasks),
        parse_mode=ParseMode.HTML,
    )


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("استفاده: /done <task_id>", parse_mode=ParseMode.HTML)
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شناسه کار باید عدد باشد.", parse_mode=ParseMode.HTML)
        return
    user_id = _get_user_id(update)
    with session_scope() as session:
        task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text("کار پیدا نشد.", parse_mode=ParseMode.HTML)
            return
        task.status = "done"
        message = f"کار #{task.id} <b>{task.title}</b> به عنوان انجام شده علامت زده شد ✔"
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("استفاده: /delete <task_id>", parse_mode=ParseMode.HTML)
        return
    try:
        task_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("شناسه کار باید عدد باشد.", parse_mode=ParseMode.HTML)
        return
    user_id = _get_user_id(update)
    with session_scope() as session:
        task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
        if not task:
            await update.message.reply_text("کار پیدا نشد.", parse_mode=ParseMode.HTML)
            return
        task.status = "deleted"
        message = f"کار #{task.id} <b>{task.title}</b> حذف شد ✖"
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


def _save_pending_task(user_id: str, pending: Dict) -> str:
    """Save a pending task to database and return success message."""
    due_dt = _to_local_tehran(pending.get("due_datetime"))
    priority = pending.get("priority", "normal")
    if priority not in {"normal", "high"}:
        priority = "normal"
    # Category is determined by whether there's a due date
    if due_dt is None:
        category = "general"
    else:
        category = "scheduled"
    
    with session_scope() as session:
        task = Task(
            user_id=user_id,
            raw_text=pending["raw_text"],
            title=pending["title"],
            due_datetime=due_dt,
            priority=priority,
            category=category,
        )
        session.add(task)
        session.flush()
        if category == "general":
            return f"کار کلی با موفقیت اضافه شد ✔"
        return f"کار با موفقیت اضافه شد ✔"


async def handle_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button callbacks for task confirmation."""
    query = update.callback_query
    await query.answer()
    
    user_id = _get_user_id(update)
    
    if user_id not in pending_tasks:
        await query.edit_message_text("این درخواست دیگر معتبر نیست.", parse_mode=ParseMode.HTML)
        return
    
    pending = pending_tasks[user_id]
    callback_data = query.data
    
    if callback_data == "confirm_task":
        # Save the task
        message = _save_pending_task(user_id, pending)
        # Clean up pending task
        del pending_tasks[user_id]
        await query.edit_message_text(message, parse_mode=ParseMode.HTML)
        
    elif callback_data == "cancel_task":
        # Cancel and remove pending task
        del pending_tasks[user_id]
        await query.edit_message_text("عملیات لغو شد.", parse_mode=ParseMode.HTML)
        
    elif callback_data == "edit_title":
        # Ask user for new title
        pending["waiting_for_edit"] = "title"
        await query.edit_message_text("عنوان جدید را بفرست", parse_mode=ParseMode.HTML)
        
    elif callback_data == "edit_time":
        # Ask user for new time
        pending["waiting_for_edit"] = "time"
        await query.edit_message_text("زمان جدید را بفرست (مثال: فردا ۶ عصر)", parse_mode=ParseMode.HTML)


async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("لطفاً توضیح کار را ارسال کنید.", parse_mode=ParseMode.HTML)
        return
    
    user_id = _get_user_id(update)
    
    # Check if user is in edit mode
    if user_id in pending_tasks:
        pending = pending_tasks[user_id]
        waiting_for = pending.get("waiting_for_edit")
        
        if waiting_for == "title":
            # User is editing title
            pending["title"] = text
            pending["waiting_for_edit"] = None
            preview_text = _create_preview_message(pending)
            keyboard = _create_confirmation_keyboard()
            await update.message.reply_text(preview_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            return
        elif waiting_for == "time":
            # User is editing time - re-parse only the time part
            try:
                time_parsed = safe_parse_task(text)
                new_due = time_parsed.get("due_datetime")
                # Always update (allows clearing time by setting to None)
                pending["due_datetime"] = new_due
                # Update category based on whether due date is provided
                pending["category"] = "general" if new_due is None else "scheduled"
                pending["waiting_for_edit"] = None
                preview_text = _create_preview_message(pending)
                keyboard = _create_confirmation_keyboard()
                await update.message.reply_text(preview_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
                return
            except Exception:
                await update.message.reply_text("نتوانستم زمان را تشخیص دهم. لطفاً دوباره تلاش کنید.", parse_mode=ParseMode.HTML)
                return
    
    # Normal flow: parse the message
    parsed = safe_parse_task(text)
    intent = parsed.get("intent", "ignore")

    if intent == "ignore":
        return
    if intent == "query_tasks":
        await send_tasks_for_date(update, context, parsed.get("query_date"))
        return
    if intent == "query_general":
        await general(update, context)
        return
    if intent == "add_task":
        # Store pending task and show preview
        pending_tasks[user_id] = {
            "title": parsed.get("title") or text,
            "due_datetime": parsed.get("due_datetime"),
            "priority": parsed.get("priority", "normal"),
            "category": parsed.get("category", "general" if parsed.get("due_datetime") is None else "scheduled"),
            "raw_text": text,
            "waiting_for_edit": None,
        }
        preview_text = _create_preview_message(pending_tasks[user_id])
        keyboard = _create_confirmation_keyboard()
        await update.message.reply_text(preview_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        return
        # DELETE TASK
    if intent == "delete_task":
        task_id = parsed.get("target_task_reference")
        if not task_id:
            await update.message.reply_text("شناسه کار مشخص نیست.", parse_mode=ParseMode.HTML)
            return
        try:
            task_id = int(task_id)
        except ValueError:
            await update.message.reply_text("شناسه کار نامعتبر است.", parse_mode=ParseMode.HTML)
            return

        user_id = _get_user_id(update)
        with session_scope() as session:
            task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
            if not task:
                await update.message.reply_text("کار پیدا نشد.", parse_mode=ParseMode.HTML)
                return
            task.status = "deleted"
            await update.message.reply_text(
                f"کار #{task.id} <b>{task.title}</b> حذف شد ✖",
                parse_mode=ParseMode.HTML
            )
        return

    # UPDATE TASK
    if intent == "update_task":
        task_id = parsed.get("target_task_reference")
        if not task_id:
            await update.message.reply_text("شناسه کار مشخص نیست.", parse_mode=ParseMode.HTML)
            return
        try:
            task_id = int(task_id)
        except ValueError:
            await update.message.reply_text("شناسه کار نامعتبر است.", parse_mode=ParseMode.HTML)
            return

        user_id = _get_user_id(update)
        new_title = parsed.get("title")
        new_due = parsed.get("due_datetime")
        new_priority = parsed.get("priority")

        with session_scope() as session:
            task = session.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
            if not task:
                await update.message.reply_text("کار پیدا نشد.", parse_mode=ParseMode.HTML)
                return

            if new_title:
                task.title = new_title
            if new_due:
                task.due_datetime = _to_local_tehran(new_due)
            if new_priority in ("high", "normal"):
                task.priority = new_priority

            await update.message.reply_text(
                f"کار #{task.id} بروز شد ✔",
                parse_mode=ParseMode.HTML
            )
        return

    # For other intents, process normally (shouldn't reach here for add_task)
    await create_task_from_parsed(update, context, parsed, text)


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("all", all_pending))
    application.add_handler(CommandHandler("missed", missed))
    application.add_handler(CommandHandler("general", general))
    application.add_handler(CommandHandler("done", done))
    application.add_handler(CommandHandler("delete", delete))
    application.add_handler(CallbackQueryHandler(handle_task_callback, pattern="^(confirm_task|cancel_task|edit_title|edit_time)$"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_task))
