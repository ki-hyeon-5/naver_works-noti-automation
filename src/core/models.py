"""Typed input and outcomes for the Task 1 audit logger."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .constants import LogEvent, LogLevel


@dataclass(frozen=True)
class LogActor:
    name: str
    user_id: str


@dataclass(frozen=True)
class LogRecord:
    level: LogLevel
    actor: LogActor
    module: str
    event: LogEvent
    count: int | None = None
    reason_code: str | None = None
    error: Exception | None = None


class LogWriteStatus(str, Enum):
    WRITTEN = "WRITTEN"
    FALLBACK_WRITTEN = "FALLBACK_WRITTEN"
    LOG_WRITE_FAILURE = "LogWriteFailure"


@dataclass(frozen=True)
class LogWriteResult:
    status: LogWriteStatus
    path: Path | None = None
    warning: str | None = None

    @property
    def persisted(self) -> bool:
        return self.status is not LogWriteStatus.LOG_WRITE_FAILURE
