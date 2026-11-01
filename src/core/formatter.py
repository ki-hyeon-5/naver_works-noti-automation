"""Build fixed Noti bodies and Jira summaries from parsed alarms."""

import re
from collections.abc import Sequence

from .models import ParsedAlarm


LEADING_TAGS = re.compile(r"^(?:\[[^\]]*\]\s*)+")
TRAILING_SEVERITY = re.compile(r"\s*\((?:critical|warning|info|error|fatal|warn|crit)\)\s*$", re.I)
ALLOWED_TAGS = {None, "GRAFANA", "N3R"}


def clean_alert_name(value: str) -> str:
    """Remove only the specified leading brackets and trailing severity."""
    return TRAILING_SEVERITY.sub("", LEADING_TAGS.sub("", value)).strip()


def noti_body(alarm: ParsedAlarm) -> str:
    """Create a single block; unresolved fields remain visible for correction."""
    target = "[확인필요: 대상없음]" if "TARGET_MISSING" in alarm.warnings else alarm.target
    occurred = "[확인필요: 시간오류]" if alarm.start_at is None else alarm.start_at.strftime("%y-%m-%d %H:%M")
    lines = []
    if alarm.cluster:
        lines.extend((f"클러스터 : {alarm.cluster}", ""))
    lines.extend((f"서비스명 : {target}", "", f"장애현상 : {alarm.detail}", "", f"발생시간 : {occurred}"))
    return "\n".join(lines)


def bundle_body(alarms: Sequence[ParsedAlarm]) -> str:
    if not alarms:
        raise ValueError("at least one alarm is required")
    return "\n\n".join(noti_body(alarm) for alarm in alarms)


def _prefix(tag: str | None) -> str:
    if tag not in ALLOWED_TAGS:
        raise ValueError("source tag must be GRAFANA, N3R, or None")
    return "[247]" + (f"[{tag}]" if tag else "")


def jira_summary(alarm: ParsedAlarm, tag: str | None = None) -> str:
    return f"{_prefix(tag)} {alarm.target}, {clean_alert_name(alarm.alert_name)}"


def bundle_summary(alarms: Sequence[ParsedAlarm], tag: str) -> str:
    if len(alarms) < 2:
        raise ValueError("at least two alarms are required")
    if tag not in ("GRAFANA", "N3R"):
        raise ValueError("a nonempty source tag is required for a bundle")
    first = alarms[0]
    first_name = clean_alert_name(first.alert_name)
    if all(clean_alert_name(alarm.alert_name) == first_name for alarm in alarms):
        return f"{_prefix(tag)} {first.target} 외 {len(alarms) - 1}건, {first_name}"
    return f"{_prefix(tag)} {first.target}, {first_name} 외 {len(alarms) - 1}건"
