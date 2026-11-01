"""Persist minimal Jira attempt states before and after issue creation."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .crypto_store import atomic_write, local_app_root


class JournalError(Exception):
    def __init__(self, code: str, action: str) -> None:
        self.code, self.action = code, action
        super().__init__(f"{code}: {action}")


class RegistrationJournal:
    """Store only hashes, state, issue key and safe diagnostic codes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else local_app_root() / "data" / "registration_journal.json"
        self._lock = threading.RLock()

    def load(self) -> dict[str, dict]:
        with self._lock:
            if not self.path.exists():
                return {}
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data["schema_version"] != 1 or not isinstance(data["attempts"], dict):
                    raise ValueError("schema")
                for attempt_id, record in data["attempts"].items():
                    if (not isinstance(attempt_id, str) or not isinstance(record, dict) or
                            record.get("state") not in {"REQUESTING", "CREATED", "DONE", "PARTIAL_FAILED", "UNKNOWN", "FAILED"} or
                            not isinstance(record.get("alarm_keys"), list) or
                            any(not isinstance(key, str) for key in record["alarm_keys"])):
                        raise ValueError("record")
                return data["attempts"]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise JournalError("JOURNAL_CORRUPT", "등록 장부를 복구하고 Jira와 수동 대조하세요.") from exc

    def write(self, attempt_id: str, alarm_keys: tuple[str, ...], state: str,
              *, issue_key: str | None = None, error_code: str = "") -> None:
        if state not in {"REQUESTING", "CREATED", "DONE", "PARTIAL_FAILED", "UNKNOWN", "FAILED"}:
            raise ValueError("invalid state")
        with self._lock:
            attempts = self.load()
            previous = attempts.get(attempt_id)
            if previous and (previous["alarm_keys"] != list(alarm_keys) or
                             previous["state"] in {"DONE", "PARTIAL_FAILED", "UNKNOWN", "FAILED"}):
                raise JournalError("ATTEMPT_LOCKED", "기존 요청을 Jira에서 수동 대조하세요.")
            attempts[attempt_id] = {
                "alarm_keys": list(alarm_keys), "state": state,
                "issue_key": issue_key, "error_code": error_code,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                atomic_write(self.path, json.dumps({"schema_version": 1, "attempts": attempts},
                                                   ensure_ascii=False).encode("utf-8"))
            except OSError as exc:
                raise JournalError("JOURNAL_WRITE_FAILED", "장부 저장 경로와 권한을 확인하세요. Jira 요청은 보내지 않았을 수 있습니다.") from exc

    def blocking_reason(self, alarm_keys: tuple[str, ...]) -> str | None:
        keys = set(alarm_keys)
        for record in self.load().values():
            if keys.intersection(record["alarm_keys"]) and record["state"] in {
                    "REQUESTING", "CREATED", "UNKNOWN", "PARTIAL_FAILED"}:
                return "MANUAL_RECONCILIATION_REQUIRED"
        return None
