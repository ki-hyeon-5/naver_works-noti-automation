"""TC-07A through G: durable Mock registration, errors and package contract."""

from dataclasses import replace
from pathlib import Path

import pytest

from src.core.jira_client import (IssueDraft, JiraClient, JiraFailure,
                                  MockJiraAdapter, draft_from_submission)
from src.core.registration_journal import JournalError, RegistrationJournal
from src.core.settings_store import UserSettings
from src.application.workflow import Submission


def draft(key="alarm-hash", attempt="attempt-1"):
    return IssueDraft(attempt, (key,), "summary", "body", "MOCK", "Task", None,
                      "account-1", None, (), ())


def client(tmp_path, adapter=None):
    adapter = adapter or MockJiraAdapter()
    return JiraClient(adapter, RegistrationJournal(tmp_path / "journal.json")), adapter


def test_tc07a_done_and_single_create(tmp_path):
    service, adapter = client(tmp_path)
    result = service.register(draft())
    assert (result.status, result.issue_key, adapter.count) == ("DONE", "MOCK-attempt-1", 1)
    assert service.journal.load()["attempt-1"]["state"] == "DONE"


def test_tc07b_watcher_failure_never_recreates(tmp_path):
    class WatcherFails(MockJiraAdapter):
        def attach_references(self, key, users):
            raise JiraFailure(403)
    service, adapter = client(tmp_path, WatcherFails())
    result = service.register(replace(draft(), default_references=("watcher",)))
    assert (result.status, result.issue_key, result.code) == ("PARTIAL_FAILED", "MOCK-attempt-1", "JIRA_FORBIDDEN")
    assert adapter.count == 1
    assert service.register(draft(attempt="attempt-2")).status == "UNKNOWN"
    assert adapter.count == 1


@pytest.mark.parametrize("failure", [TimeoutError(), JiraFailure(500), JiraFailure(429)])
def test_tc07c_uncertain_create_is_durable_and_blocked(tmp_path, failure):
    class Uncertain(MockJiraAdapter):
        def create_issue(self, issue):
            self.count += 1
            raise failure
    service, adapter = client(tmp_path, Uncertain())
    assert service.register(draft()).status == "UNKNOWN"
    restarted = JiraClient(adapter, RegistrationJournal(tmp_path / "journal.json"))
    assert restarted.blocking_reason(("alarm-hash",)) == "MANUAL_RECONCILIATION_REQUIRED"
    assert restarted.register(draft(attempt="another")).status == "UNKNOWN"
    assert adapter.count == 1


@pytest.mark.parametrize("http,code", [(400, "JIRA_BAD_REQUEST"), (401, "JIRA_UNAUTHORIZED"),
                                        (403, "JIRA_FORBIDDEN")])
def test_tc07d_definite_rejection(tmp_path, http, code):
    class Reject(MockJiraAdapter):
        def create_issue(self, issue):
            raise JiraFailure(http)
    service, _ = client(tmp_path, Reject())
    result = service.register(draft())
    assert (result.status, result.code) == ("FAILED", code)
    assert service.journal.load()["attempt-1"]["state"] == "FAILED"


def test_tc07e_requesting_survives_process_restart(tmp_path):
    journal = RegistrationJournal(tmp_path / "journal.json")
    journal.write("attempt-1", ("alarm-hash",), "REQUESTING")
    service, adapter = client(tmp_path)
    assert service.blocking_reason(("alarm-hash",)) == "MANUAL_RECONCILIATION_REQUIRED"
    assert service.register(draft(attempt="attempt-2")).status == "UNKNOWN"
    assert adapter.count == 0


def test_tc07f_settings_payload_and_deduplicated_references(tmp_path):
    settings = UserSettings(epic_options=("EPIC-1", "EPIC-2"), default_epic="EPIC-2",
                            default_watchers=("a", "b"), alarm_watchers={"alarm-hash": ("b", "c")},
                            reporter_account_id="reporter")
    submission = Submission((0,), "summary", "body", "assignee", "N3R", ("alarm-hash",))
    issue = draft_from_submission(submission, settings)
    service, adapter = client(tmp_path)
    assert service.register(issue).status == "DONE"
    assert adapter.drafts[0].epic_key == "EPIC-2"
    assert adapter.drafts[0].reporter_identity == "reporter"
    assert adapter.drafts[0].references == ("a", "b", "c")


def test_journal_write_failure_prevents_create(tmp_path, monkeypatch):
    service, adapter = client(tmp_path)
    def fail(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr("src.core.registration_journal.atomic_write", fail)
    with pytest.raises(JournalError, match="JOURNAL_WRITE_FAILED"):
        service.register(draft())
    assert adapter.count == 0


def test_tc07g_onedir_spec_keeps_data_outside_bundle():
    spec = (Path(__file__).resolve().parents[1] / "packaging" / "noti-automation.spec").read_text(encoding="utf-8")
    assert "COLLECT(" in spec and "exclude_binaries=True" in spec
    assert "datas=[]" in spec
