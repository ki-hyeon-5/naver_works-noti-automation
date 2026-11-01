"""Run the Mock Jira registration state machine behind a future adapter contract."""

from dataclasses import dataclass
from threading import Lock
from typing import Protocol
from uuid import uuid4

from .registration_journal import RegistrationJournal
from .settings_store import UserSettings


@dataclass(frozen=True)
class IssueDraft:
    local_attempt_id: str
    alarm_keys: tuple[str, ...]
    summary: str
    description: str
    project_key: str
    issue_type: str
    epic_key: str | None
    assignee_identity: str | None
    reporter_identity: str | None
    default_references: tuple[str, ...]
    per_alarm_references: tuple[str, ...]

    @property
    def references(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(self.default_references + self.per_alarm_references))


class JiraFailure(Exception):
    def __init__(self, status: int | None, code: str = "JIRA_ERROR") -> None:
        self.status, self.code = status, code
        super().__init__(code)


class JiraAdapter(Protocol):
    def validate_environment(self) -> dict: ...
    def create_issue(self, draft: IssueDraft) -> dict: ...
    def assign_issue(self, issue_key: str, user_identity: str) -> dict: ...
    def attach_references(self, issue_key: str, user_identities: tuple[str, ...]) -> dict: ...
    def query_existing(self, local_attempt_id: str, alarm_keys: tuple[str, ...]) -> list[dict]: ...


class MockJiraAdapter:
    """Issue keys and responses are local simulations, never network traffic."""

    def __init__(self) -> None:
        self.count = 0
        self.drafts: list[IssueDraft] = []

    def validate_environment(self) -> dict:
        return {"status": "MOCK"}

    def create_issue(self, draft: IssueDraft) -> dict:
        self.count += 1
        self.drafts.append(draft)
        return {"key": f"MOCK-{draft.local_attempt_id}"}

    def assign_issue(self, issue_key: str, user_identity: str) -> dict:
        return {"ok": True}

    def attach_references(self, issue_key: str, user_identities: tuple[str, ...]) -> dict:
        return {"ok": True}

    def query_existing(self, local_attempt_id: str, alarm_keys: tuple[str, ...]) -> list[dict]:
        return []


@dataclass(frozen=True)
class RegistrationResult:
    status: str
    issue_key: str | None
    code: str = ""


def draft_from_submission(submission, settings: UserSettings, *, project_key: str = "MOCK",
                          issue_type: str = "Task") -> IssueDraft:
    keys = submission.alarm_keys
    references = tuple(dict.fromkeys(
        watcher for key in keys for watcher in settings.alarm_watchers.get(key, ())))
    return IssueDraft(str(uuid4()), keys, submission.summary, submission.body,
                      project_key, issue_type, settings.default_epic or None,
                      submission.jira_account_id, settings.reporter_account_id or None,
                      settings.default_watchers, references)


class JiraClient:
    """Persist each transition; classify uncertain create results conservatively."""

    def __init__(self, adapter: JiraAdapter, journal: RegistrationJournal) -> None:
        self.adapter, self.journal = adapter, journal
        self._submit_lock = Lock()

    def blocking_reason(self, keys: tuple[str, ...]) -> str | None:
        return self.journal.blocking_reason(keys)

    def register(self, draft: IssueDraft) -> RegistrationResult:
        if not self._submit_lock.acquire(blocking=False):
            return RegistrationResult("UNKNOWN", None, "REQUEST_IN_PROGRESS")
        try:
            return self._register(draft)
        finally:
            self._submit_lock.release()

    def _register(self, draft: IssueDraft) -> RegistrationResult:
        if self.adapter.validate_environment().get("status") != "MOCK":
            return RegistrationResult("FAILED", None, "JIRA_ENVIRONMENT_UNVERIFIED")
        if self.blocking_reason(draft.alarm_keys):
            return RegistrationResult("UNKNOWN", None, "MANUAL_RECONCILIATION_REQUIRED")
        self.journal.write(draft.local_attempt_id, draft.alarm_keys, "REQUESTING")
        try:
            response = self.adapter.create_issue(draft)
            key = response.get("key")
            if not isinstance(key, str) or not key:
                raise JiraFailure(None, "CREATE_RESPONSE_UNCERTAIN")
        except JiraFailure as exc:
            definite = exc.status in (400, 401, 403)
            status = "FAILED" if definite else "UNKNOWN"
            code = {400: "JIRA_BAD_REQUEST", 401: "JIRA_UNAUTHORIZED", 403: "JIRA_FORBIDDEN",
                    429: "JIRA_RATE_LIMITED"}.get(exc.status, exc.code)
            self.journal.write(draft.local_attempt_id, draft.alarm_keys, status, error_code=code)
            return RegistrationResult(status, None, code)
        except Exception:
            self.journal.write(draft.local_attempt_id, draft.alarm_keys, "UNKNOWN", error_code="CREATE_UNCERTAIN")
            return RegistrationResult("UNKNOWN", None, "CREATE_UNCERTAIN")
        self.journal.write(draft.local_attempt_id, draft.alarm_keys, "CREATED", issue_key=key)
        try:
            if draft.assignee_identity:
                if self.adapter.assign_issue(key, draft.assignee_identity).get("ok") is not True:
                    raise JiraFailure(400, "ASSIGN_FAILED")
            if draft.references:
                if self.adapter.attach_references(key, draft.references).get("ok") is not True:
                    raise JiraFailure(400, "REFERENCES_FAILED")
        except JiraFailure as exc:
            code = {400: "JIRA_BAD_REQUEST", 401: "JIRA_UNAUTHORIZED", 403: "JIRA_FORBIDDEN",
                    429: "JIRA_RATE_LIMITED"}.get(exc.status, exc.code)
            self.journal.write(draft.local_attempt_id, draft.alarm_keys, "PARTIAL_FAILED", issue_key=key, error_code=code)
            return RegistrationResult("PARTIAL_FAILED", key, code)
        except Exception:
            self.journal.write(draft.local_attempt_id, draft.alarm_keys, "PARTIAL_FAILED", issue_key=key,
                               error_code="FOLLOWUP_FAILED")
            return RegistrationResult("PARTIAL_FAILED", key, "FOLLOWUP_FAILED")
        self.journal.write(draft.local_attempt_id, draft.alarm_keys, "DONE", issue_key=key)
        return RegistrationResult("DONE", key)
