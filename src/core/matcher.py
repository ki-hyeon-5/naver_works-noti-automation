"""Resolve mapping candidates and same-day alarm duplicates without Jira I/O."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .crypto_store import CryptoStore, StorageError, atomic_write, local_app_root
from .excel_importer import mapping_key, normalize
from .formatter import clean_alert_name
from .models import ParsedAlarm


@dataclass(frozen=True)
class AssigneeIdentity:
    display_name: str
    jira_account_id: str | None = None


@dataclass(frozen=True)
class MappingCandidate:
    source_tag: str
    row_id: str
    assignee: AssigneeIdentity
    service: str | None = None


@dataclass(frozen=True)
class MatchResult:
    status: str
    candidates: tuple[MappingCandidate, ...]
    selected_tag: str | None
    selected_assignee: AssigneeIdentity | None
    can_approve: bool
    warnings: tuple[str, ...]


class MappingMatcher:
    """Return explicit choice gates when mappings or Jira identities are unclear."""

    def __init__(self, grafana_rows: list[dict], n3r_rows: list[dict]) -> None:
        self.grafana_index: dict[str, list[dict]] = {}
        self.n3r_index: dict[str, list[dict]] = {}
        for row in grafana_rows:
            name = normalize(row.get("alert_name"))
            self.grafana_index.setdefault(name, []).append(row)
        for row in n3r_rows:
            target = mapping_key("n3r", row)[0]
            self.n3r_index.setdefault(target, []).append(row)

    @classmethod
    def from_store(cls, store: CryptoStore) -> "MappingMatcher":
        rows = {}
        for kind in ("grafana", "n3r"):
            try:
                rows[kind] = store.load(kind)
            except StorageError as exc:
                if exc.code != "NOT_FOUND":
                    raise
                rows[kind] = []
        return cls(rows["grafana"], rows["n3r"])

    def match(
        self, alarm: ParsedAlarm, *, service_hint: str | None = None,
        default_assignee: AssigneeIdentity | None = None,
    ) -> MatchResult:
        if not alarm.can_register:
            return MatchResult("ALARM_REVIEW_REQUIRED", (), None, None, False, alarm.warnings)
        target = normalize(alarm.target)
        alert_name = normalize(clean_alert_name(alarm.alert_name))
        grafana_rows = self.grafana_index.get(alert_name, [])
        if service_hint:
            grafana_rows = [row for row in grafana_rows if normalize(row.get("service")) == normalize(service_hint)]
        n3r_rows = self.n3r_index.get(target, [])
        candidates = tuple(
            [self._candidate("GRAFANA", row) for row in grafana_rows] +
            [self._candidate("N3R", row) for row in n3r_rows]
        )
        if not candidates:
            if default_assignee is None or not default_assignee.jira_account_id:
                return MatchResult("UNMATCHED_BLOCKED", (), None, default_assignee, False,
                                   ("ASSIGNEE_UNMATCHED", "DEFAULT_ASSIGNEE_INVALID"))
            return MatchResult("DEFAULT_APPLIED", (), None, default_assignee, True,
                               ("ASSIGNEE_UNMATCHED", "DEFAULT_ASSIGNEE_APPLIED"))
        sources = {candidate.source_tag for candidate in candidates}
        if len(sources) > 1:
            names = {normalize(candidate.assignee.display_name) for candidate in candidates}
            status = "ASSIGNEE_AND_SOURCE_SELECTION_REQUIRED" if len(names) > 1 else "SOURCE_SELECTION_REQUIRED"
            return MatchResult(status, candidates, None, None, False, (status,))
        if len(candidates) > 1:
            return MatchResult("CANDIDATE_SELECTION_REQUIRED", candidates, None, None, False,
                               ("CANDIDATE_SELECTION_REQUIRED",))
        return self._selected(candidates[0], candidates)

    @staticmethod
    def _candidate(source: str, row: dict) -> MappingCandidate:
        return MappingCandidate(
            source, str(row["id"]),
            AssigneeIdentity(str(row.get("assignee", "")), row.get("jira_account_id")),
            str(row.get("service")) if source == "GRAFANA" else None,
        )

    @staticmethod
    def _selected(candidate: MappingCandidate, candidates: tuple[MappingCandidate, ...]) -> MatchResult:
        resolved = bool(candidate.assignee.jira_account_id)
        return MatchResult("MATCHED", candidates, candidate.source_tag, candidate.assignee,
                           resolved, () if resolved else ("JIRA_ACCOUNT_UNRESOLVED",))

    def select(self, result: MatchResult, source_tag: str, row_id: str) -> MatchResult:
        for candidate in result.candidates:
            if candidate.source_tag == source_tag and candidate.row_id == row_id:
                return self._selected(candidate, result.candidates)
        raise ValueError("candidate is not part of this match result")


class DuplicateCacheError(Exception):
    def __init__(self, code: str, action: str) -> None:
        self.code = code
        self.action = action
        super().__init__(f"{code}: {action}")


class DuplicateDetector:
    """Persist only hashes of same-day keys and keep a fast in-memory set."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = Path(cache_dir) if cache_dir is not None else local_app_root() / "cache"
        self._memory: dict[date, set[str]] = {}

    @staticmethod
    def _key(alarm: ParsedAlarm) -> str:
        if not alarm.can_register or alarm.start_at is None:
            raise ValueError("alarm must be corrected before duplicate checking")
        value = "\x1f".join((normalize(alarm.target), normalize(clean_alert_name(alarm.alert_name)),
                            alarm.start_at.isoformat(sep=" ")))
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _path(self, day: date) -> Path:
        return self.cache_dir / f"{day.isoformat()}.json"

    def _keys(self, day: date) -> set[str]:
        if day in self._memory:
            return self._memory[day]
        path = self._path(day)
        if not path.exists():
            self._memory[day] = set()
            return self._memory[day]
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document["schema_version"] != 1 or document["day"] != day.isoformat():
                raise ValueError("invalid cache header")
            keys = document["keys"]
            if not isinstance(keys, list) or any(not isinstance(key, str) or len(key) != 64 for key in keys):
                raise ValueError("invalid cache keys")
            self._memory[day] = set(keys)
            return self._memory[day]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DuplicateCacheError("CACHE_CORRUPT", "당일 중복 캐시를 확인하고 수동 대조하세요.") from exc

    def is_duplicate(self, alarm: ParsedAlarm, day: date) -> bool:
        return self._key(alarm) in self._keys(day)

    def mark(self, alarm: ParsedAlarm, day: date) -> bool:
        key = self._key(alarm)
        keys = self._keys(day)
        if key in keys:
            return False
        updated = keys | {key}
        document = {"schema_version": 1, "day": day.isoformat(), "keys": sorted(updated)}
        try:
            atomic_write(self._path(day), json.dumps(document).encode("utf-8"))
        except OSError as exc:
            raise DuplicateCacheError("CACHE_WRITE_FAILED", "당일 중복 캐시 저장 경로를 확인하세요.") from exc
        self._memory[day] = updated
        return True
