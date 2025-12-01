"""Client for parsing natural language tasks via OpenRouter."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict

import jdatetime
import pytz
import requests

from .config import OPENROUTER_API_KEY, OPENROUTER_MODEL, TIMEZONE

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_SYSTEM_PROMPT_TEMPLATE = """

You are an AI assistant for a Persian task manager.

TODAY_GREGORIAN: {today_gregorian}
TODAY_JALALI: {today_jalali}
CURRENT_TIME_TEHRAN: {current_time}
TIMEZONE: {timezone}

You MUST use TODAY_JALALI for all Persian temporal expressions.

Examples:
- "فردا" = TODAY_JALALI + 1 day (then convert back to Gregorian final datetime)
- "پس فردا" = TODAY_JALALI + 2 days
- "هفته بعد" = next week in Jalali
- "شنبه آینده" = next Saturday in Jalali
- "دو روز دیگه" = TODAY_JALALI + 2

After calculating date/time in Jalali, convert back to a complete ISO8601 Gregorian datetime.

====================================================
INTENT RULES
====================================================

TASK CREATION LOGIC:

For messages describing a new task:
- "فردا …"
- "پس فردا …"
- "دو روز دیگه …"
- "شنبه آینده"
- "آخر هفته"
- "امشب"
→ intent = "add_task"
→ You MUST compute the **absolute ISO8601 datetime** based on Jalali date calculations.

TASK QUERY LOGIC:

For messages requesting information:
- "کارای فردامو بگو"
- "کارای امروز چیه؟"
- "کارای هفته بعدمو بگو"
- "فقط کارای مهم فردا"
- "کارای بدون ساعت امروز"
→ intent = "query_tasks"

TASK UPDATE / DELETE LOGIC:

If user references a task by number:
- "کار 5"
- "تسک 3"
- "task 12"
→ extract the number and put it in target_task_reference.

If user says:
- "کار 5 رو حذف کن"
- "کار شماره 3 پاک شود"
→ intent = delete_task  
→ target_task_reference = "<id>"

If user says:
- "عنوان کار 7 را عوض کن به ..."
- "کار 4 رو کن جلسه با علی"
→ intent = update_task  
→ title = "<new title>"

If user says:
- "زمان کار 10 رو بذار فردا ۶"
- "کار 3 رو بنداز شنبه"
→ intent = update_task  
→ due_datetime = "<new absolute ISO datetime>"

If user says:
- "اولویت کار 2 رو بالا کن"
→ intent = update_task  
→ priority = "high"

You MUST fill:
- query_date → specific date (ISO Gregorian) when applicable  
- query_range → "day" | "week" | "month" when user asks about a period

====================================================
IGNORE LOGIC
====================================================

If message is greeting, small talk, etc. → intent = "ignore"

====================================================
GENERAL TASKS (NO DUE DATE)
====================================================

If user provides a task with NO date/time information:
- "یه روز باید لباسا رو مرتب کنم"
- "کتاب خریدن"
- "ورزش بیشتر"
- "یادم باشه به مامان زنگ بزنم"
→ intent = "add_task"
→ due_datetime = null
→ category = "general"

If user asks to see general/undated tasks:
- "کارای کلی رو نشون بده"
- "کارهای بدون زمان"
- "چیزایی که فقط نوشتم رو بفرست"
→ intent = "query_general"

====================================================
JSON OUTPUT (STRICT)
====================================================

STRICT JSON ONLY. No explanation.
{{
  "intent": "add_task" | "query_tasks" | "query_general" | "update_task" | "move_task" | "delete_task" | "complete_task" | "ignore",
  "title": "<short title>",
  "due_datetime": "<ISO8601 or null>",
  "priority": "normal" | "high",
  "category": "scheduled" | "general",
  "query_date": "<ISO date or null>",
  "query_range": "<day|week|month|null>",
  "target_task_reference": "<string or null>"
}}
"""



class OpenRouterError(Exception):
    """Raised when the OpenRouter API cannot return a valid response."""


def _default_payload(text: str) -> Dict[str, Any]:
    return {
        "intent": "add_task",
        "title": text.strip() or "Task",
        "due_datetime": None,
        "priority": "normal",
        "category": "general",
        "query_date": None,
        "query_range": None,
        "target_task_reference": None,
    }


def parse_task(text: str) -> Dict[str, Any]:
    """Parse a task description using OpenRouter and return structured data."""
    # Use Asia/Tehran timezone for Persian date calculations
    tz = pytz.timezone("Asia/Tehran")
    now = datetime.now(tz)
    
    # Get Gregorian date
    today_gregorian = now.strftime("%Y-%m-%d")
    
    # Get Jalali date
    today_jalali = jdatetime.date.fromgregorian(year=now.year, month=now.month, day=now.day).strftime("%Y-%m-%d")
    
    # Get current time in Tehran
    current_time = now.strftime("%H:%M")
    
    # Format the prompt with all date information
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        today_gregorian=today_gregorian,
        today_jalali=today_jalali,
        current_time=current_time,
        timezone="Asia/Tehran"
    )
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Respond with JSON only. Parse the following task: " + text.strip()
                ),
            },
        ],
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        print(data)
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        intent = parsed.get("intent", "ignore")
        title = parsed.get("title") or text.strip()
        due_datetime = parsed.get("due_datetime")
        priority = parsed.get("priority", "normal")
        if priority not in {"normal", "high"}:
            priority = "normal"
        category = parsed.get("category", "scheduled")
        if category not in {"scheduled", "general"}:
            category = "general" if due_datetime is None else "scheduled"
        if due_datetime is None and category == "scheduled":
            category = "general"
        return {
            "intent": intent,
            "title": title,
            "due_datetime": due_datetime,
            "priority": priority,
            "category": category,
            "query_date": parsed.get("query_date"),
            "query_range": parsed.get("query_range"),
            "target_task_reference": parsed.get("target_task_reference"),
        }
    except Exception as exc:  # pragma: no cover - network failure fallback
        raise OpenRouterError("Failed to parse task") from exc


def safe_parse_task(text: str) -> Dict[str, Any]:
    """Parse task data with graceful fallback."""
    try:
        return parse_task(text)
    except OpenRouterError:
        return _default_payload(text)
