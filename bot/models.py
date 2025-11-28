"""Database models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    raw_text = Column(String, nullable=False)
    title = Column(String, nullable=False)
    due_datetime = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String, default="pending", nullable=False)
    priority = Column(String, default="normal", nullable=False)

    def to_line(self) -> str:
        due = self.due_datetime.isoformat(timespec="minutes") if self.due_datetime else "No due date"
        return f"#{self.id} [{self.priority}] {self.title} - {due}"
