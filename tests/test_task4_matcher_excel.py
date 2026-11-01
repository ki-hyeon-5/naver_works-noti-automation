"""TC-04A through TC-04G for Excel append, matching, grouping, and duplicates."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from openpyxl import Workbook

from src.core.bundle_planner import BundlePlanner, ReviewSelection
from src.core.crypto_store import CryptoStore, StorageError
from src.core.excel_importer import ExcelImporter
from src.core.formatter import jira_summary
from src.core.matcher import AssigneeIdentity, DuplicateDetector, MappingMatcher
from src.core.parsers.grafana_parser import GrafanaParser


SAMPLES = Path(__file__).resolve().parents[1] / "samples"


class FakeProtector:
    def __init__(self):
        self.key = AESGCM.generate_key(bit_length=128)

    def protect(self, data):
        nonce = os.urandom(12)
        return nonce + AESGCM(self.key).encrypt(nonce, data, None)

    def unprotect(self, data):
        return AESGCM(self.key).decrypt(data[:12], data[12:], None)


def store(tmp_path):
    return CryptoStore(tmp_path / "data", FakeProtector())


def workbook(tmp_path, name, headers, rows, *, preamble=None):
    file = tmp_path / name
    book = Workbook()
    sheet = book.active
    if preamble:
        sheet.append(preamble)
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    book.save(file)
    return file


def alarm(target="server-01", name="[Linux] CPU high (WARNING)", fingerprint="fp-one"):
    text = "\n".join((
        "Firing", "Resolved", "-", "2026-10-11 01:57:20", "4h 30m 29s", target,
        name, "CPU high", "90", "95", "WARNING", "tester", fingerprint,
    ))
    return GrafanaParser().parse(text).alarms[0]


def selection(target, name, *, account="jira-A", tag="N3R", fingerprint=None):
    return ReviewSelection(alarm(target, name, fingerprint or target + name), account, tag)


def test_tc04a_synthetic_n3r_excel_maps_expected_alarms(tmp_path):
    source = json.loads((SAMPLES / "n3r-mapping-synthetic.json").read_text(encoding="utf-8"))
    excel = workbook(tmp_path, "n3r.xlsx", ["server_name", "SERVICE NAME", "purpose", "ASSIGNEE"], [
        [row["server_name"], row["service_name"], row["purpose"], row["assignee"]]
        for row in source["rows"]
    ], preamble=["synthetic N3R mapping"])
    crypto = store(tmp_path)
    with ThreadPoolExecutor(max_workers=1) as worker:
        result = ExcelImporter(crypto).submit_import(worker, excel, "n3r").result(timeout=5)
    assert result.status == "IMPORTED" and result.added == 2 and result.saved
    saved = crypto.load("n3r")
    assert len(saved) == 2
    assert {"server_name", "service_name", "purpose", "assignee"} <= saved[0].keys()
    assert saved[0]["source_file"] == "n3r.xlsx"
    assert "/" not in saved[0]["source_file"]

    matcher = MappingMatcher.from_store(crypto)
    parsed = GrafanaParser().parse((SAMPLES / "grafana-synthetic-input.txt").read_text(encoding="utf-8"))
    expected = json.loads((SAMPLES / "expected-results.json").read_text(encoding="utf-8"))
    for item, expected_item in zip(parsed.alarms, (expected["records"][0], expected["records"][2])):
        matched = matcher.match(item)
        assert matched.status == "MATCHED" and matched.selected_tag == "N3R"
        assert matched.selected_assignee.display_name == "담당자A"
        assert not matched.can_approve  # a display name is not a Jira account ID
        assert jira_summary(item, matched.selected_tag) == expected_item["jira_summary_single"]


def test_tc04b_same_key_same_content_skips_duplicate(tmp_path):
    excel = workbook(tmp_path, "mapping.xlsx", ["Service", "Assignee", "Alert_Name", "Descripton"], [
        [" Billing ", "담당자A", "CPU high", "synthetic"],
    ])
    crypto = store(tmp_path)
    importer = ExcelImporter(crypto)
    assert importer.import_file(excel, "grafana").added == 1
    repeated = importer.import_file(excel, "grafana")
    assert repeated.status == "UNCHANGED" and repeated.skipped == 1 and repeated.added == 0
    assert len(crypto.load("grafana")) == 1


def test_tc04c_conflict_is_not_overwritten_until_admin_choice(tmp_path):
    first = workbook(tmp_path, "first.xlsx", ["service", "assignee", "alert_name", "description"], [
        ["Billing", "담당자A", "CPU high", "synthetic"],
    ])
    second = workbook(tmp_path, "second.xlsx", ["service", "assignee", "alert_name", "description"], [
        ["Billing", "담당자B", "CPU high", "synthetic"],
    ])
    crypto = store(tmp_path)
    importer = ExcelImporter(crypto)
    importer.import_file(first, "grafana")
    prior = crypto.load("grafana")[0]
    result = importer.import_file(second, "grafana")
    assert result.status == "PARTIAL" and result.added == 0 and len(result.conflicts) == 1
    assert crypto.load("grafana")[0]["assignee"] == "담당자A"
    conflict = result.conflicts[0]
    assert importer.resolve_conflict("grafana", conflict, "KEEP_EXISTING") == "KEEP_EXISTING"
    assert crypto.load("grafana")[0]["assignee"] == "담당자A"
    assert importer.resolve_conflict("grafana", conflict, "USE_INCOMING") == "USE_INCOMING"
    updated = crypto.load("grafana")[0]
    assert updated["assignee"] == "담당자B" and updated["id"] == prior["id"]
    with pytest.raises(StorageError, match="STALE_CONFLICT"):
        importer.resolve_conflict("grafana", conflict, "USE_INCOMING")


def test_header_collision_and_bad_rows_report_errors_without_losing_good_rows(tmp_path):
    crypto = store(tmp_path)
    importer = ExcelImporter(crypto)
    collision = workbook(tmp_path, "collision.xlsx", ["service", "Service_", "assignee", "alert_name", "description"], [
        ["A", "A", "B", "C", "D"],
    ])
    result = importer.import_file(collision, "grafana")
    assert result.status == "FAILED" and result.errors[0].code == "HEADER_COLLISION"
    assert not (tmp_path / "data" / "grafana_db.dat").exists()

    partial = workbook(tmp_path, "partial.xlsx", ["service", "assignee", "alert_name", "description"], [
        ["Billing", "담당자A", "CPU high", "desc"],
        ["Billing", "", "Disk high", "desc"],
        ["", "담당자B", "Memory high", "desc"],
    ])
    result = importer.import_file(partial, "grafana")
    assert result.status == "PARTIAL" and result.added == 1
    assert [issue.code for issue in result.errors] == ["ROW_REQUIRED_FIELD", "ROW_REQUIRED_FIELD"]
    assert len(crypto.load("grafana")) == 1


def test_missing_header_and_corrupt_workbook_are_explicit_failures(tmp_path):
    importer = ExcelImporter(store(tmp_path))
    missing = workbook(tmp_path, "missing.xlsx", ["service", "assignee", "alert_name"], [
        ["Billing", "A", "CPU"],
    ])
    result = importer.import_file(missing, "grafana")
    assert result.status == "FAILED" and result.errors[0].code == "HEADER_MISSING"
    broken = tmp_path / "broken.xlsx"
    broken.write_bytes(b"not a real workbook")
    result = importer.import_file(broken, "grafana")
    assert result.status == "FAILED" and result.errors[0].code == "EXCEL_READ_FAILED"


def test_save_failure_does_not_report_success_or_modify_existing(tmp_path, monkeypatch):
    crypto = store(tmp_path)
    importer = ExcelImporter(crypto)
    first = workbook(tmp_path, "first.xlsx", ["service", "assignee", "alert_name", "description"], [
        ["Billing", "A", "CPU", "desc"],
    ])
    importer.import_file(first, "grafana")
    original = crypto.load("grafana")
    next_file = workbook(tmp_path, "next.xlsx", ["service", "assignee", "alert_name", "description"], [
        ["Payments", "B", "Disk", "desc"],
    ])
    def fail_save(kind, rows):
        raise StorageError("WRITE_FAILED", "synthetic storage failure")
    monkeypatch.setattr(crypto, "save", fail_save)
    result = importer.import_file(next_file, "grafana")
    assert result.status == "FAILED" and not result.saved and result.added == 0
    assert result.errors[0].code == "WRITE_FAILED"
    assert crypto.load("grafana") == original


def test_tc04d_both_sources_require_explicit_selection(tmp_path):
    grafana = [{"id": "g1", "service": "Billing", "alert_name": "CPU high", "assignee": "A", "jira_account_id": "jira-A"}]
    n3r = [{"id": "n1", "server_name": "server-01", "assignee": "B", "jira_account_id": "jira-B"}]
    item = alarm()
    matcher = MappingMatcher(grafana, n3r)
    differing = matcher.match(item)
    assert differing.status == "ASSIGNEE_AND_SOURCE_SELECTION_REQUIRED" and not differing.can_approve
    chosen = matcher.select(differing, "N3R", "n1")
    assert chosen.selected_assignee.display_name == "B" and chosen.can_approve
    n3r[0]["assignee"] = "A"
    same = MappingMatcher(grafana, n3r).match(item)
    assert same.status == "SOURCE_SELECTION_REQUIRED" and not same.can_approve


def test_grafana_multiple_services_do_not_autoselect(tmp_path):
    rows = [
        {"id": "g1", "service": "Billing", "alert_name": "CPU high", "assignee": "A", "jira_account_id": "jira-A"},
        {"id": "g2", "service": "Payments", "alert_name": "CPU high", "assignee": "B", "jira_account_id": "jira-B"},
    ]
    matcher = MappingMatcher(rows, [])
    assert matcher.match(alarm()).status == "CANDIDATE_SELECTION_REQUIRED"
    selected = matcher.match(alarm(), service_hint="Billing")
    assert selected.status == "MATCHED" and selected.selected_assignee.display_name == "A"


def test_tc04e_unmatched_default_assignee_gate():
    matcher = MappingMatcher([], [])
    item = alarm()
    missing = matcher.match(item)
    assert missing.status == "UNMATCHED_BLOCKED" and not missing.can_approve
    invalid = matcher.match(item, default_assignee=AssigneeIdentity("Fallback"))
    assert invalid.status == "UNMATCHED_BLOCKED" and not invalid.can_approve
    valid = matcher.match(item, default_assignee=AssigneeIdentity("Fallback", "jira-F"))
    assert valid.status == "DEFAULT_APPLIED" and valid.can_approve
    assert valid.selected_tag is None and valid.selected_assignee.display_name == "Fallback"
    assert "ASSIGNEE_UNMATCHED" in valid.warnings


def test_tc04f_group_only_when_four_conditions_hold():
    planner = BundlePlanner()
    first = selection("server-01", "[Linux] CPU high", fingerprint="a")
    same_target = selection("server-01", "[Linux] Disk high", fingerprint="b")
    same_name = selection("server-02", "[Linux] CPU high", fingerprint="c")
    different_assignee = selection("server-01", "[Linux] CPU high", account="jira-B", fingerprint="d")
    different_tag = selection("server-01", "[Linux] CPU high", tag="GRAFANA", fingerprint="e")
    no_tag = selection("server-01", "[Linux] CPU high", tag=None, fingerprint="f")

    assert len(planner.plan((first, same_target), bundled=True).groups[0].members) == 2
    assert len(planner.plan((first, same_name), bundled=True).groups[0].members) == 2
    for other in (different_assignee, different_tag, no_tag):
        result = planner.plan((first, other), bundled=True)
        assert len(result.groups) == 2 and all(len(group.members) == 1 for group in result.groups)
    individual = planner.plan((first, same_target), bundled=False)
    assert len(individual.groups) == 2 and not individual.requires_confirmation


def test_tc04g_nontransitive_pairs_are_split_deterministically():
    a = selection("server-01", "[Linux] CPU high", fingerprint="a")
    b = selection("server-01", "[Linux] Disk high", fingerprint="b")
    c = selection("server-02", "[Linux] Disk high", fingerprint="c")
    planner = BundlePlanner()
    result = planner.plan((a, b, c), bundled=True)
    assert [tuple(item.alarm.fingerprint for item in group.members) for group in result.groups] == [("a", "b"), ("c",)]
    assert result.groups[1].split_reason == "GROUP_CONDITIONS_NOT_MET"
    assert result.requires_confirmation
    reordered = planner.plan((c, b, a), bundled=True)
    assert reordered.input_order_hash != result.input_order_hash


def test_same_day_duplicate_cache_uses_hashes_and_survives_restart(tmp_path):
    day = date(2026, 10, 11)
    item = alarm()
    detector = DuplicateDetector(tmp_path / "cache")
    assert not detector.is_duplicate(item, day)
    assert detector.mark(item, day)
    assert detector.is_duplicate(item, day)
    assert not detector.mark(item, day)
    assert DuplicateDetector(tmp_path / "cache").is_duplicate(item, day)
    assert not detector.is_duplicate(item, date(2026, 10, 12))
    cache = (tmp_path / "cache" / "2026-10-11.json").read_text(encoding="utf-8")
    assert "server-01" not in cache and "CPU high" not in cache


def test_corrupt_duplicate_cache_requires_manual_review(tmp_path):
    from src.core.matcher import DuplicateCacheError

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    (cache_dir / "2026-10-11.json").write_text("broken", encoding="utf-8")
    with pytest.raises(DuplicateCacheError, match="CACHE_CORRUPT"):
        DuplicateDetector(cache_dir).is_duplicate(alarm(), date(2026, 10, 11))
