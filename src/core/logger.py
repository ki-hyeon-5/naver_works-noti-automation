"""Append structured events to daily TXT files with path fallback."""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from .constants import DEFAULT_LOG_BASE, EVENT_TEXT, LOCAL_LOG_SUBPATH, LogEvent, LogLevel
from .models import LogRecord, LogWriteResult, LogWriteStatus


_SAFE_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_SECRET_PATTERNS = (
    re.compile(r"(?i)(\b(?:api[_-]?token|password|passwd|secret|encryption[_-]?key)\b\s*[:=]\s*)\S+"),
    re.compile(r"(?i)(\bAuthorization\s*[:=]\s*(?:Bearer|Basic)\s+)\S+"),
    re.compile(r"(?i)(\bCookie\s*[:=]\s*)[^\]\r\n]+"),
    re.compile(r"(?i)\bBearer\s+\S+"),
)


def _redact(value: str) -> str:
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(lambda match: match.group(1) + "[REDACTED]" if match.lastindex else "Bearer [REDACTED]", value)
    return value.replace("\r", " ").replace("\n", " ").replace("\t", " ")


class FileLogger:
    """Write one record per call, returning persistence status independently of business results."""

    def __init__(
        self,
        log_base_path: Path | str | None = None,
        auto_year_month_folder: bool = True,
        *,
        default_base_path: Path | str | None = None,
        local_appdata: Path | str | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self.log_base_path = Path(log_base_path) if log_base_path else None
        self.auto_year_month_folder = auto_year_month_folder
        # A Windows drive path is relative on macOS. Tests can inject a temporary default.
        self.default_base_path = Path(default_base_path) if default_base_path else (
            Path(DEFAULT_LOG_BASE) if os.name == "nt" else None
        )
        local_root = local_appdata or os.environ.get("LOCALAPPDATA")
        if local_root is None and os.name == "nt":
            local_root = Path.home() / "AppData" / "Local"
        self.local_appdata = Path(local_root) if local_root else None
        self.clock = clock

    def _candidates(self) -> list[Path]:
        candidates = [self.log_base_path, self.default_base_path]
        if self.local_appdata is not None:
            candidates.append(self.local_appdata.joinpath(*LOCAL_LOG_SUBPATH))
        unique: list[Path] = []
        for path in candidates:
            if path is not None and path not in unique:
                unique.append(path)
        return unique

    def _daily_path(self, base: Path, now: datetime) -> Path:
        if self.auto_year_month_folder:
            base = base / now.strftime("%Y") / now.strftime("%m")
        return base / f"{now:%Y-%m-%d}.txt"

    def write(self, record: LogRecord) -> LogWriteResult:
        """Try each distinct candidate and never propagate path errors to the caller."""
        if not isinstance(record.level, LogLevel) or not isinstance(record.event, LogEvent):
            raise ValueError("A known level and event are required")
        if record.count is not None and (type(record.count) is not int or record.count < 0):
            raise ValueError("count must be a nonnegative integer")
        if record.reason_code is not None and not _SAFE_CODE.fullmatch(record.reason_code):
            raise ValueError("reason_code must be a safe code")

        now = self.clock()
        details = []
        if record.count is not None:
            details.append(f"count={record.count}")
        if record.reason_code is not None:
            details.append(f"reason={record.reason_code}")
        if record.error is not None:
            # Exception messages can contain credentials or raw alarm input.
            details.append(f"error_type={type(record.error).__name__}")
        message = " ".join((EVENT_TEXT[record.event], *details))
        line = _redact(
            f"[{now:%Y-%m-%d %H:%M:%S}] [{record.level.value}] "
            f"[User: {record.actor.name}({record.actor.user_id})] "
            f"[{record.module}] {message}"
        ) + "\n"

        failures = 0
        for base in self._candidates():
            path = self._daily_path(base, now)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as output:
                    output.write(line)
                if failures:
                    return LogWriteResult(
                        LogWriteStatus.FALLBACK_WRITTEN, path,
                        "기본 로그 경로에 기록할 수 없어 대체 경로에 저장했습니다.",
                    )
                return LogWriteResult(LogWriteStatus.WRITTEN, path)
            except OSError:
                failures += 1

        print("로그 기록 실패: 영구 기록이 남지 않았습니다.", file=sys.stderr)
        return LogWriteResult(
            LogWriteStatus.LOG_WRITE_FAILURE,
            warning="로그 기록 실패: 영구 기록이 남지 않았습니다.",
        )
