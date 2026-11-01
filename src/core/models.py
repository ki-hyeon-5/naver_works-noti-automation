"""Typed input and outcomes for the Task 1 audit logger."""

from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True)
class ParseIssue:
    """A parse failure or unsupported source with a source character span."""

    code: str
    raw_span: tuple[int, int]
    action: str


@dataclass(frozen=True)
class ParsedAlarm:
    """A Grafana alarm candidate; review flags block registration until corrected."""

    raw_span: tuple[int, int]
    raw_fields: dict[str, str]
    start_at: datetime | None
    target: str
    alert_name: str
    detail: str
    cluster: str | None
    cluster_candidate: str | None
    needs_review: bool
    warnings: tuple[str, ...]
    fingerprint: str

    @property
    def can_register(self) -> bool:
        return not self.needs_review


@dataclass(frozen=True)
class ParseBatchResult:
    """Only reviewable alarms appear in alarms; NoData is counted separately."""

    alarms: tuple[ParsedAlarm, ...]
    no_data_count: int
    errors: tuple[ParseIssue, ...]
    total_records: int
    no_data_reasons: dict[str, int]
