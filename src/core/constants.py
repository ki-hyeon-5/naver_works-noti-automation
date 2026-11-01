"""Domain constants for structured audit logging."""

from enum import Enum


DEFAULT_LOG_BASE = r"C:\noti-log"
LOCAL_LOG_SUBPATH = ("NotiAutomation", "logs")


class LogLevel(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class LogEvent(str, Enum):
    LOG_PATH_FALLBACK = "LOG_PATH_FALLBACK"
    NODATA_EXCLUDED = "NODATA_EXCLUDED"
    ASSIGNEE_UNMATCHED = "ASSIGNEE_UNMATCHED"
    DUPLICATE_WARNING = "DUPLICATE_WARNING"
    ISSUE_CREATED = "ISSUE_CREATED"
    ISSUE_PARTIAL_FAILED = "ISSUE_PARTIAL_FAILED"
    ISSUE_UNKNOWN = "ISSUE_UNKNOWN"
    OPERATION_FAILED = "OPERATION_FAILED"


EVENT_TEXT = {
    LogEvent.LOG_PATH_FALLBACK: "로그 경로 대체 사용",
    LogEvent.NODATA_EXCLUDED: "NoData 제외",
    LogEvent.ASSIGNEE_UNMATCHED: "담당자 미매칭",
    LogEvent.DUPLICATE_WARNING: "중복 알람 경고",
    LogEvent.ISSUE_CREATED: "Jira 생성성공",
    LogEvent.ISSUE_PARTIAL_FAILED: "Jira 부분실패",
    LogEvent.ISSUE_UNKNOWN: "Jira 생성여부불명",
    LogEvent.OPERATION_FAILED: "작업 실패",
}
