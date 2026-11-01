"""Keep alarm review, grouping, and explicit registration gates in one place."""

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Callable

from src.core.bundle_planner import BundlePlanner, ReviewSelection
from src.core.formatter import bundle_body, bundle_summary, jira_summary, noti_body
from src.core.matcher import AssigneeIdentity, DuplicateCacheError, DuplicateDetector, MappingMatcher
from src.core.models import ParsedAlarm, ParseBatchResult
from src.core.parsers.grafana_parser import GrafanaParser
from src.core.registration_journal import JournalError


@dataclass
class ReviewItem:
    alarm: ParsedAlarm
    assignee: AssigneeIdentity | None
    source_tag: str | None
    candidates: tuple = ()
    match_status: str = ""
    reviewed: bool = False
    body: str = ""
    status: str = "PENDING"
    jira_key: str | None = None
    action: str = ""
    duplicate_confirmed: bool = False


@dataclass(frozen=True)
class Submission:
    indices: tuple[int, ...]
    summary: str
    body: str
    jira_account_id: str
    source_tag: str | None
    alarm_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class SubmitResult:
    submitted: tuple[Submission, ...]
    blocked: dict[int, tuple[str, ...]]


class Workflow:
    """A transport is injected only after connection validation by the caller."""

    def __init__(self, matcher: MappingMatcher | None = None,
                 duplicate_detector: DuplicateDetector | None = None,
                 default_assignee: AssigneeIdentity | None = None,
                 sender: Callable[[Submission], tuple[str, str | None]] | None = None,
                 today: Callable[[], date] = date.today) -> None:
        self.parser = GrafanaParser()
        self.matcher = matcher or MappingMatcher([], [])
        self.detector = duplicate_detector or DuplicateDetector()
        self.default_assignee = default_assignee
        self.sender = sender
        self.today = today
        self.items: list[ReviewItem] = []
        self.batch: ParseBatchResult | None = None
        self.bundled = False
        self.group_confirmed = False

    def load(self, text: str) -> ParseBatchResult:
        self.batch = self.parser.parse(text)
        self.items = []
        for alarm in self.batch.alarms:
            match = self.matcher.match(alarm, default_assignee=self.default_assignee)
            self.items.append(ReviewItem(alarm, match.selected_assignee, match.selected_tag,
                                         match.candidates, match.status, body=noti_body(alarm)))
        self.group_confirmed = False
        return self.batch

    def correct(self, index: int, *, target: str, detail: str, start_at: str,
                cluster: str = "") -> None:
        item = self.items[index]
        warnings = []
        if not target.strip() or target.strip() == "-":
            warnings.append("TARGET_MISSING")
        try:
            timestamp = datetime.strptime(start_at.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            timestamp = None
            warnings.append("TIME_INVALID")
        if not detail.strip():
            warnings.append("DETAIL_MISSING")
        corrected = replace(item.alarm, target=target.strip(), detail=detail.strip(),
                            start_at=timestamp, cluster=cluster.strip() or None,
                            warnings=tuple(warnings), needs_review=bool(warnings))
        item.alarm = corrected
        item.body = noti_body(corrected)
        item.reviewed = False
        item.duplicate_confirmed = False
        self.group_confirmed = False
        match = self.matcher.match(corrected, default_assignee=self.default_assignee)
        item.candidates, item.match_status = match.candidates, match.status
        item.assignee, item.source_tag = match.selected_assignee, match.selected_tag

    def select_assignee(self, index: int, assignee: AssigneeIdentity,
                        source_tag: str | None) -> None:
        if source_tag not in (None, "GRAFANA", "N3R") or not assignee.jira_account_id:
            raise ValueError("a resolved Jira account and valid source are required")
        item = self.items[index]
        if item.candidates and not any(c.source_tag == source_tag and
                                       c.assignee.jira_account_id == assignee.jira_account_id
                                       for c in item.candidates):
            raise ValueError("select a matching source candidate")
        item.assignee, item.source_tag = assignee, source_tag
        item.reviewed = False
        self.group_confirmed = False

    def set_reviewed(self, index: int, reviewed: bool) -> None:
        self.items[index].reviewed = reviewed

    def set_bundled(self, bundled: bool) -> None:
        if self.bundled != bundled:
            self.bundled = bundled
            self.group_confirmed = False

    def groups(self):
        return BundlePlanner().plan([
            ReviewSelection(item.alarm, item.assignee.jira_account_id if item.assignee else None,
                            item.source_tag) for item in self.items
        ], bundled=self.bundled)

    def reasons(self, index: int) -> tuple[str, ...]:
        item = self.items[index]
        reasons = list(item.alarm.warnings)
        if not item.alarm.target.strip() or item.alarm.start_at is None or not item.alarm.detail.strip():
            reasons.append("REQUIRED_FIELD_INVALID")
        if not item.assignee or not item.assignee.jira_account_id:
            reasons.append("JIRA_ACCOUNT_UNRESOLVED")
        if item.candidates and (item.source_tag is None or
                                not any(c.source_tag == item.source_tag and
                                        c.assignee.jira_account_id == item.assignee.jira_account_id
                                        for c in item.candidates if item.assignee)):
            reasons.append("SOURCE_CONFLICT")
        if not item.reviewed:
            reasons.append("REVIEW_REQUIRED")
        if self.sender is None:
            reasons.append("JIRA_CONNECTION_UNAVAILABLE")
        if item.status in ("REQUESTING", "DONE", "FAILED"):
            reasons.append(f"STATUS_{item.status}")
        if item.status in ("UNKNOWN", "PARTIAL_FAILED"):
            reasons.append("MANUAL_RECONCILIATION_REQUIRED")
        if self.sender is not None and hasattr(self.sender, "blocking_reason") and item.alarm.can_register:
            try:
                reason = self.sender.blocking_reason((self.detector._key(item.alarm),))
                if reason:
                    reasons.append(reason)
            except JournalError as exc:
                reasons.append(exc.code)
        try:
            if item.alarm.can_register and self.detector.is_duplicate(item.alarm, self.today()) and not item.duplicate_confirmed:
                reasons.append("DUPLICATE_CONFIRM_REQUIRED")
        except DuplicateCacheError as exc:
            reasons.append(exc.code)
        return tuple(dict.fromkeys(reasons))

    def submit(self, indices: list[int] | None = None) -> SubmitResult:
        selected = list(range(len(self.items))) if indices is None else list(dict.fromkeys(indices))
        blocked = {i: self.reasons(i) for i in selected if self.reasons(i)}
        eligible = [i for i in selected if i not in blocked]
        seen = set()
        for i in tuple(eligible):
            key = self.detector._key(self.items[i].alarm)
            if key in seen and not self.items[i].duplicate_confirmed:
                blocked[i] = ("DUPLICATE_CONFIRM_REQUIRED",)
                eligible.remove(i)
            else:
                seen.add(key)
        if self.bundled and eligible and not self.group_confirmed:
            blocked.update({i: ("GROUP_CONFIRM_REQUIRED",) for i in eligible})
            eligible = []
        selections = [ReviewSelection(self.items[i].alarm, self.items[i].assignee.jira_account_id,
                                      self.items[i].source_tag) for i in eligible]
        plan = BundlePlanner().plan(selections, bundled=self.bundled)
        index_by_selection = {id(selection): index for selection, index in zip(selections, eligible)}
        submitted = []
        for group in plan.groups:
            group_indices = tuple(index_by_selection[id(member)] for member in group.members)
            alarms = [self.items[i].alarm for i in group_indices]
            first = self.items[group_indices[0]]
            request = Submission(group_indices,
                                 bundle_summary(alarms, first.source_tag) if len(alarms) > 1 else jira_summary(alarms[0], first.source_tag),
                                 bundle_body(alarms) if len(alarms) > 1 else first.body,
                                 first.assignee.jira_account_id, first.source_tag,
                                 tuple(self.detector._key(alarm) for alarm in alarms))
            for i in group_indices:
                self.items[i].status = "REQUESTING"
            try:
                status, key = self.sender(request)
                if status not in ("DONE", "PARTIAL_FAILED", "UNKNOWN", "FAILED"):
                    raise ValueError("invalid sender status")
            except Exception:
                status, key = "UNKNOWN", None
            for i in group_indices:
                item = self.items[i]
                item.status, item.jira_key = status, key
                code = getattr(getattr(self.sender, "last_result", None), "code", "")
                if status in ("UNKNOWN", "PARTIAL_FAILED"):
                    item.action = f"{code}: Jira에서 생성 여부와 기존 이슈를 수동 대조하세요."
                elif status == "FAILED":
                    item.action = f"{code}: Jira 설정·권한·필드를 확인하세요."
                else:
                    item.action = ""
                if status in ("DONE", "PARTIAL_FAILED"):
                    try:
                        self.detector.mark(item.alarm, self.today())
                    except DuplicateCacheError as exc:
                        item.action = f"{exc.code}: 당일 중복 캐시를 확인하세요."
            submitted.append(request)
        return SubmitResult(tuple(submitted), blocked)
