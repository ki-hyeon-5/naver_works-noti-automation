"""TC-05A through TC-05E: review gates, mixed batches, and GUI focus."""

import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.application.workflow import Workflow
from src.core.matcher import AssigneeIdentity, DuplicateDetector, MappingMatcher
from src.ui.main_window import MainWindow


def raw(target="server-01", name="[Linux] CPU high (WARNING)", nodata="-", fingerprint="fp"):
    return "\n".join(("Firing", "Resolved", nodata, "2026-10-11 01:57:20", "4h 30m 29s",
                      target, name, "CPU high", "90", "95", "WARNING", "tester", fingerprint))


def workflow(tmp_path, sender=None):
    return Workflow(MappingMatcher([], []), DuplicateDetector(tmp_path),
                    AssigneeIdentity("tester", "jira-A"), sender, today=lambda: date(2026, 10, 11))


def app():
    return QApplication.instance() or QApplication([])


def test_tc05a_enter_in_body_is_newline_and_never_submits(tmp_path):
    app()
    calls = []
    state = workflow(tmp_path, lambda request: (calls.append(request) or ("DONE", "MOCK-1")))
    window = MainWindow(state)
    window.input.raw.setPlainText(raw())
    window.parse()
    window.review.body.setFocus()
    window.review.body.moveCursor(QTextCursor.End)
    original = window.review.body.toPlainText()
    QTest.keyClick(window.review.body, Qt.Key_Return)
    assert window.review.body.toPlainText() == original + "\n"
    assert not calls
    window.close()


def test_tc05b_unreviewed_shortcut_is_blocked(tmp_path):
    app()
    calls = []
    state = workflow(tmp_path, lambda request: (calls.append(request) or ("DONE", "MOCK-1")))
    window = MainWindow(state)
    window.input.raw.setPlainText(raw())
    window.parse()
    QTest.keyClick(window.review.body, Qt.Key_Return, Qt.ControlModifier)
    assert not calls
    assert "REVIEW_REQUIRED" in state.reasons(0)
    window.close()


def test_tc05c_nodata_mixed_batch_excludes_only_nodata(tmp_path):
    calls = []
    state = workflow(tmp_path, lambda request: (calls.append(request) or ("DONE", "MOCK-1")))
    batch = state.load(raw(nodata="NoData", fingerprint="first") + "\n" + raw(fingerprint="second"))
    assert batch.total_records == 2 and batch.no_data_count == 1 and len(state.items) == 1
    state.set_reviewed(0, True)
    result = state.submit()
    assert len(result.submitted) == 1 and len(calls) == 1
    assert "NoData" not in calls[0].body


def test_tc05d_all_submits_only_two_eligible_individual_issues(tmp_path):
    calls = []
    state = workflow(tmp_path, lambda request: (calls.append(request) or ("DONE", f"MOCK-{len(calls)}")))
    state.load("\n".join((raw("server-01", fingerprint="one"),
                            raw("server-02", fingerprint="two"),
                            raw("-", fingerprint="three"))))
    for i in range(3):
        state.set_reviewed(i, True)
    result = state.submit()
    assert len(result.submitted) == 2 and len(calls) == 2
    assert all(len(request.indices) == 1 for request in calls)
    assert "TARGET_MISSING" in result.blocked[2]


def test_tc05e_duplicate_confirmation_and_uncertain_reconciliation(tmp_path):
    calls = []
    state = workflow(tmp_path, lambda request: (calls.append(request) or ("DONE", "MOCK-1")))
    state.load(raw())
    state.set_reviewed(0, True)
    assert len(state.submit().submitted) == 1
    state.load(raw(fingerprint="different"))
    state.set_reviewed(0, True)
    assert "DUPLICATE_CONFIRM_REQUIRED" in state.submit().blocked[0]
    assert len(calls) == 1
    state.items[0].duplicate_confirmed = True
    assert len(state.submit().submitted) == 1 and len(calls) == 2
    state.items[0].status = "UNKNOWN"
    assert "MANUAL_RECONCILIATION_REQUIRED" in state.submit().blocked[0]
    state.items[0].status = "PARTIAL_FAILED"
    assert "MANUAL_RECONCILIATION_REQUIRED" in state.submit().blocked[0]


def test_structured_correction_and_pairwise_bundle_split(tmp_path):
    calls = []
    state = workflow(tmp_path, lambda request: (calls.append(request) or ("DONE", f"MOCK-{len(calls)}")))
    state.load("\n".join((raw("server-01", "CPU high", fingerprint="a"),
                            raw("server-01", "Disk high", fingerprint="b"),
                            raw("server-02", "Disk high", fingerprint="c"))))
    state.correct(0, target="server-01", detail="CPU high", start_at="2026-10-11 01:57:20")
    for i in range(3):
        state.set_reviewed(i, True)
    state.set_bundled(True)
    assert [len(group.members) for group in state.groups().groups] == [1, 1, 1]  # no source tag
    assert "GROUP_CONFIRM_REQUIRED" in state.submit().blocked[0]
    for i in range(3):
        state.select_assignee(i, AssigneeIdentity("tester", "jira-A"), "N3R")
        state.set_reviewed(i, True)
    assert [len(group.members) for group in state.groups().groups] == [2, 1]
    state.group_confirmed = True
    result = state.submit()
    assert len(result.submitted) == 2
    assert result.submitted[0].indices == (0, 1)
    assert result.submitted[1].indices == (2,)


def test_same_batch_duplicate_needs_separate_confirmation(tmp_path):
    calls = []
    state = workflow(tmp_path, lambda request: (calls.append(request) or ("DONE", "MOCK-1")))
    state.load(raw(fingerprint="one") + "\n" + raw(fingerprint="two"))
    state.set_reviewed(0, True)
    state.set_reviewed(1, True)
    result = state.submit()
    assert len(calls) == 1
    assert result.blocked[1] == ("DUPLICATE_CONFIRM_REQUIRED",)
