"""TC-01A through TC-01E for daily audit logging and failure isolation."""

from datetime import datetime

import pytest

from src.core.constants import LogEvent, LogLevel
from src.core.logger import FileLogger
from src.core.models import LogActor, LogRecord, LogWriteStatus


ACTOR = LogActor("테스트 사용자", "tester")
STAMP = datetime(2026, 11, 2, 9, 4, 5)


def record(**changes):
    values = dict(level=LogLevel.INFO, actor=ACTOR, module="parser", event=LogEvent.NODATA_EXCLUDED)
    values.update(changes)
    return LogRecord(**values)


def logger(base, tmp_path, **changes):
    values = dict(log_base_path=base, default_base_path=tmp_path / "default", local_appdata=tmp_path / "local", clock=lambda: STAMP)
    values.update(changes)
    return FileLogger(**values)


def test_tc01a_year_month_path_and_append(tmp_path):
    log = logger(tmp_path / "custom", tmp_path)
    first = log.write(record(count=2, reason_code="NoData"))
    second = log.write(record(event=LogEvent.ISSUE_CREATED))

    expected = tmp_path / "custom" / "2026" / "11" / "2026-11-02.txt"
    assert first.status is second.status is LogWriteStatus.WRITTEN
    assert first.path == second.path == expected
    assert expected.read_text(encoding="utf-8").splitlines() == [
        "[2026-11-02 09:04:05] [INFO] [User: 테스트 사용자(tester)] [parser] NoData 제외 count=2 reason=NoData",
        "[2026-11-02 09:04:05] [INFO] [User: 테스트 사용자(tester)] [parser] Jira 생성성공",
    ]


def test_tc01b_flat_daily_path_and_date_rollover(tmp_path):
    current = [STAMP]
    log = logger(tmp_path / "custom", tmp_path, auto_year_month_folder=False, clock=lambda: current[0])
    assert log.write(record()).path == tmp_path / "custom" / "2026-11-02.txt"
    current[0] = datetime(2027, 1, 1)
    assert log.write(record()).path == tmp_path / "custom" / "2027-01-01.txt"


def test_tc01c_fallback_to_local_appdata_and_warning(tmp_path):
    blocked_custom = tmp_path / "custom"
    blocked_default = tmp_path / "default"
    blocked_custom.write_text("file", encoding="utf-8")
    blocked_default.write_text("file", encoding="utf-8")

    result = logger(blocked_custom, tmp_path).write(record())
    assert result.status is LogWriteStatus.FALLBACK_WRITTEN
    assert result.warning
    assert result.path == tmp_path / "local" / "NotiAutomation" / "logs" / "2026" / "11" / "2026-11-02.txt"
    assert result.path.read_text(encoding="utf-8").count("NoData 제외") == 1


def test_tc01c_duplicate_candidate_attempted_once(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("file", encoding="utf-8")
    log = logger(blocked, tmp_path, default_base_path=blocked)
    assert log._candidates() == [blocked, tmp_path / "local" / "NotiAutomation" / "logs"]
    assert log.write(record()).status is LogWriteStatus.FALLBACK_WRITTEN


def test_first_fallback_uses_default_path(tmp_path):
    blocked = tmp_path / "custom"
    blocked.write_text("file", encoding="utf-8")
    result = logger(blocked, tmp_path).write(record())
    assert result.status is LogWriteStatus.FALLBACK_WRITTEN
    assert result.path == tmp_path / "default" / "2026" / "11" / "2026-11-02.txt"


def test_existing_directory_at_daily_file_triggers_fallback(tmp_path):
    daily = tmp_path / "custom" / "2026" / "11" / "2026-11-02.txt"
    daily.mkdir(parents=True)
    result = logger(tmp_path / "custom", tmp_path).write(record())
    assert result.status is LogWriteStatus.FALLBACK_WRITTEN
    assert result.path.is_file()


def test_tc01d_all_paths_fail_without_changing_business_result(tmp_path, capsys):
    for name in ("custom", "default", "local"):
        (tmp_path / name).write_text("file", encoding="utf-8")
    jira_result = {"status": "CREATED", "key": "TEST-1"}
    result = logger(tmp_path / "custom", tmp_path).write(record(event=LogEvent.ISSUE_CREATED))
    assert result.status is LogWriteStatus.LOG_WRITE_FAILURE
    assert result.path is None and not result.persisted and result.warning
    assert jira_result == {"status": "CREATED", "key": "TEST-1"}
    assert "로그 기록 실패" in capsys.readouterr().err


def test_tc01e_secret_bearing_error_is_not_logged(tmp_path):
    secret = "synthetic-token-12345"
    log = logger(tmp_path / "custom", tmp_path)
    result = log.write(record(level=LogLevel.ERROR, event=LogEvent.OPERATION_FAILED,
                              error=RuntimeError(f"Authorization: Bearer {secret}; password={secret}")))
    content = result.path.read_text(encoding="utf-8")
    assert secret not in content
    assert "error_type=RuntimeError" in content
    assert "Authorization" not in content


def test_final_redaction_filters_identity_fields(tmp_path):
    secret = "synthetic-cookie-secret"
    bad_actor = LogActor(f"Cookie: session={secret}; other={secret}", "tester")
    result = logger(tmp_path / "custom", tmp_path).write(record(actor=bad_actor))
    assert secret not in result.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("field,value", [("count", -1), ("reason_code", "password=secret")])
def test_unstructured_detail_is_rejected(tmp_path, field, value):
    with pytest.raises(ValueError):
        logger(tmp_path / "custom", tmp_path).write(record(**{field: value}))
