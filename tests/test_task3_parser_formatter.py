"""TC-03A through TC-03F for Grafana parsing and fixed text templates."""

import json
from pathlib import Path

import pytest

from src.core.formatter import bundle_body, bundle_summary, clean_alert_name, jira_summary, noti_body
from src.core.parsers.grafana_parser import GrafanaParser
from src.core.parsers.scp_parser import ScpParser


SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def alarm_text(
    *, target="server-01", start="2026-10-11 01:57:20", name="[Linux] CPU high (WARNING)",
    detail="CPU exceeds 90%", no_data="-", status="Firing", fingerprint="fp_synthetic",
):
    return "\n".join((
        status, "Resolved", no_data, start, "4h 30m 29s", target, name,
        detail, "90", "95", "WARNING", "tester", fingerprint,
    ))


def test_tc03a_synthetic_batch_excludes_nodata_and_matches_expected_text():
    source = (SAMPLES / "grafana-synthetic-input.txt").read_text(encoding="utf-8")
    expected = json.loads((SAMPLES / "expected-results.json").read_text(encoding="utf-8"))
    result = GrafanaParser().parse(source)
    assert result.total_records == expected["expected_input_records"]
    assert result.no_data_count == expected["expected_no_data_excluded"]
    assert result.no_data_reasons == {"NO_DATA_FIELD+ALERT_NAME": 1}
    assert len(result.alarms) == expected["expected_review_records"]
    assert result.errors == ()
    for alarm, item in zip(result.alarms, (expected["records"][0], expected["records"][2])):
        assert alarm.target == item["target"]
        assert alarm.cluster == item["cluster"]
        assert clean_alert_name(alarm.alert_name) == item["clean_alert_name"]
        assert alarm.start_at.strftime("%y-%m-%d %H:%M") == item["occurred_time"]
        assert noti_body(alarm) == item["noti_text"]
        assert jira_summary(alarm, "N3R") == item["jira_summary_single"]
        assert alarm.can_register
    assert "NoData" not in bundle_body(result.alarms)


def test_tc03b_dollar_detail_is_not_nodata():
    result = GrafanaParser().parse(alarm_text(detail="value $unknown still firing"))
    assert len(result.alarms) == 1
    assert result.no_data_count == 0
    assert "$unknown" in result.alarms[0].detail


def test_tc03c_missing_target_and_invalid_calendar_date_block_registration():
    source = alarm_text(target="-", fingerprint="fp_one") + "\n" + alarm_text(
        start="2026-02-30 01:57:20", fingerprint="fp_two",
    )
    result = GrafanaParser().parse(source)
    assert len(result.alarms) == 2
    assert "TARGET_MISSING" in result.alarms[0].warnings
    assert "[확인필요: 대상없음]" in noti_body(result.alarms[0])
    assert "TIME_INVALID" in result.alarms[1].warnings
    assert "[확인필요: 시간오류]" in noti_body(result.alarms[1])
    assert all(not alarm.can_register for alarm in result.alarms)


def test_explicit_empty_tab_target_is_marked_for_review():
    source = alarm_text().replace("4h 30m 29s\nserver-01\n[Linux]", "4h 30m 29s\t\t[Linux]")
    result = GrafanaParser().parse(source)
    assert len(result.alarms) == 1 and not result.errors
    assert result.alarms[0].target == ""
    assert "TARGET_MISSING" in result.alarms[0].warnings
    assert "[확인필요: 대상없음]" in noti_body(result.alarms[0])


def test_tc03d_cluster_prefix_only_when_trustworthy_and_body_pipe_preserved():
    source = alarm_text(detail="prod-billing-ns | disk full", fingerprint="fp_one") + "\n" + alarm_text(
        detail="Disk use is high | check node", fingerprint="fp_two",
    )
    result = GrafanaParser().parse(source)
    assert result.alarms[0].cluster == "prod-billing-ns"
    assert result.alarms[0].detail == "disk full"
    assert result.alarms[1].cluster is None
    assert result.alarms[1].detail == "Disk use is high | check node"
    assert "클러스터" not in noti_body(result.alarms[1])


def test_uncertain_cluster_keeps_original_and_requests_confirmation():
    alarm = GrafanaParser().parse(alarm_text(detail="plainword | possible detail")).alarms[0]
    assert alarm.cluster is None and alarm.cluster_candidate == "plainword"
    assert alarm.detail == "plainword | possible detail"
    assert alarm.needs_review and not alarm.can_register


def test_tc03e_title_removes_only_outer_tags_and_severity():
    alarm = GrafanaParser().parse(alarm_text(name="[Linux][CRITICAL] CPU [billing] high (WARNING)")).alarms[0]
    assert clean_alert_name(alarm.alert_name) == "CPU [billing] high"
    assert jira_summary(alarm, "GRAFANA") == "[247][GRAFANA] server-01, CPU [billing] high"
    assert jira_summary(alarm) == "[247] server-01, CPU [billing] high"
    assert clean_alert_name("CPU (something)") == "CPU (something)"


def test_tc03f_irregular_tabs_blank_lines_and_multiline_detail():
    text = "\n\n" + alarm_text(detail="first detail\nsecond detail | preserved").replace(
        "Firing\nResolved\n-\n", "Firing\tResolved\t-\n\n",
    ) + "\n\n"
    result = GrafanaParser().parse(text)
    assert len(result.alarms) == 1 and result.errors == ()
    assert result.alarms[0].detail == "first detail\nsecond detail | preserved"
    assert result.alarms[0].raw_span == (2, len(text.rstrip()))


def test_tc03f_glued_input_and_missing_field_are_ambiguous_not_nodata():
    glued = alarm_text().replace("\n", "")
    result = GrafanaParser().parse(glued)
    assert not result.alarms and result.no_data_count == 0
    assert result.errors[0].code == "PARSE_AMBIGUOUS"
    assert result.errors[0].raw_span == (0, len(glued))

    incomplete = alarm_text().replace("\n90\n95\nWARNING", "\n90\nWARNING")
    result = GrafanaParser().parse(incomplete)
    assert result.no_data_count == 0
    assert result.errors[0].code == "PARSE_AMBIGUOUS"


def test_partial_batch_keeps_clear_alarm_and_reports_ambiguous_one():
    source = alarm_text(fingerprint="fp_one") + "\n" + alarm_text(fingerprint="fp_two").replace(
        "\n90\n95\nWARNING", "\n90\nWARNING",
    )
    result = GrafanaParser().parse(source)
    assert result.total_records == 2
    assert len(result.alarms) == 1
    assert len(result.errors) == 1 and result.errors[0].code == "PARSE_AMBIGUOUS"


def test_bundle_templates_preserve_each_block_and_summary_cases():
    source = alarm_text(target="server-01", fingerprint="fp_one") + "\n" + alarm_text(
        target="server-02", fingerprint="fp_two",
    )
    first, second = GrafanaParser().parse(source).alarms
    assert bundle_body((first, second)) == noti_body(first) + "\n\n" + noti_body(second)
    assert bundle_summary((first, second), "N3R") == "[247][N3R] server-01 외 1건, CPU high"

    different = GrafanaParser().parse(alarm_text(name="[Linux] Disk full", fingerprint="fp_three")).alarms[0]
    assert bundle_summary((first, different), "N3R") == "[247][N3R] server-01, CPU high 외 1건"
    with pytest.raises(ValueError):
        bundle_summary((first, second), "")


def test_scp_is_explicitly_unsupported():
    result = ScpParser().parse("synthetic SCP text")
    assert result.alarms == () and result.errors[0].code == "UNSUPPORTED_SOURCE"
