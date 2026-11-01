"""Parse unlabeled Grafana clipboard rows using field and anchor boundaries."""

import re
from dataclasses import dataclass
from datetime import datetime

from ..models import ParseBatchResult, ParsedAlarm, ParseIssue
from .base_parser import BaseParser


FIELDS = (
    "status", "resolved", "no_data", "start_at", "duration", "target",
    "alert_name", "detail", "init_value", "last_value", "severity",
    "last_actor", "fingerprint",
)
DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\Z")
DURATION_PATTERN = re.compile(r"(?:(?:\d+d)\s*)?(?:(?:\d+h)\s*)?(?:(?:\d+m)\s*)?(?:\d+s)\Z", re.I)
DATEISH_PATTERN = re.compile(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}")
SEVERITIES = {"CRITICAL", "WARNING", "WARN", "INFO", "ERROR", "FATAL", "LOW", "MEDIUM", "HIGH", "OK"}
CLUSTER_PATTERN = re.compile(r"^([A-Za-z0-9_-]{2,64})\s*\|\s*(\S[\s\S]*)\Z")


@dataclass(frozen=True)
class _Cell:
    value: str
    start: int
    end: int


def _cells(text: str) -> list[_Cell]:
    cells: list[_Cell] = []
    offset = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        parts = content.split("\t")
        if not any(part.strip() for part in parts):
            offset += len(line)
            continue
        part_start = offset
        for index, part in enumerate(parts):
            value = part.strip()
            if value or 0 < index < len(parts) - 1:
                left = len(part) - len(part.lstrip())
                right = len(part.rstrip())
                if not value:
                    right = left
                cells.append(_Cell(value, part_start + left, part_start + right))
            part_start += len(part) + 1
        offset += len(line)
    return cells


def _anchor_at(cells: list[_Cell], index: int) -> bool:
    if cells[index].value.casefold() != "firing" or index + 4 >= len(cells):
        return False
    date = cells[index + 3].value
    return bool(DATEISH_PATTERN.match(date) and DURATION_PATTERN.fullmatch(cells[index + 4].value))


def _cluster(detail: str) -> tuple[str | None, str | None, str, tuple[str, ...]]:
    match = CLUSTER_PATTERN.fullmatch(detail)
    if not match:
        return None, None, detail, ()
    candidate, remainder = match.groups()
    # Plain English words can precede a pipe in a sentence. Keep uncertain text.
    if not any(character.isdigit() or character in "_-" for character in candidate):
        return None, candidate, detail, ("CLUSTER_CONFIRM_REQUIRED",)
    return candidate, None, remainder.strip(), ()


class GrafanaParser(BaseParser):
    """Return explicit ambiguity instead of guessing glued field boundaries."""

    def parse(self, text: str) -> ParseBatchResult:
        cells = _cells(text)
        starts = [index for index in range(len(cells)) if _anchor_at(cells, index)]
        if not starts:
            return ParseBatchResult((), 0, (ParseIssue("PARSE_AMBIGUOUS", (0, len(text)), "필드 경계를 확인하고 수동 수정하세요."),), 0, {})

        alarms: list[ParsedAlarm] = []
        errors: list[ParseIssue] = []
        reasons: dict[str, int] = {}
        if cells[0].start < cells[starts[0]].start:
            errors.append(ParseIssue("PARSE_AMBIGUOUS", (0, cells[starts[0]].start), "앞부분의 필드 경계를 확인하세요."))
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(cells)
            segment = cells[start:end]
            span = (segment[0].start, segment[-1].end)
            parsed = self._parse_segment(text, segment, span)
            if isinstance(parsed, ParseIssue):
                errors.append(parsed)
            elif isinstance(parsed, str):
                reasons[parsed] = reasons.get(parsed, 0) + 1
            else:
                alarms.append(parsed)
        return ParseBatchResult(tuple(alarms), sum(reasons.values()), tuple(errors), len(starts), reasons)

    def _parse_segment(self, source: str, cells: list[_Cell], span: tuple[int, int]) -> ParsedAlarm | ParseIssue | str:
        if len(cells) < 13:
            return ParseIssue("PARSE_AMBIGUOUS", span, "13개 필드와 Detail 경계를 확인하세요.")
        if cells[0].value.casefold() != "firing" or not DURATION_PATTERN.fullmatch(cells[4].value):
            return ParseIssue("PARSE_AMBIGUOUS", span, "상태와 Duration 앵커를 확인하세요.")
        tail = cells[-5:]
        if tail[2].value.upper() not in SEVERITIES:
            return ParseIssue("PARSE_AMBIGUOUS", span, "Detail 끝과 Severity 필드 경계를 확인하세요.")
        detail_cells = cells[7:-5]
        if not detail_cells:
            return ParseIssue("PARSE_AMBIGUOUS", span, "Detail 필드를 확인하세요.")
        detail = source[detail_cells[0].start:detail_cells[-1].end].strip()
        values = [cell.value for cell in cells[:7]] + [detail] + [cell.value for cell in tail]
        raw_fields = dict(zip(FIELDS, values))
        no_data_reasons = []
        if raw_fields["no_data"].casefold() == "nodata":
            no_data_reasons.append("NO_DATA_FIELD")
        if raw_fields["alert_name"].casefold() == "datasourcenodata":
            no_data_reasons.append("ALERT_NAME")
        if no_data_reasons:
            return "+".join(no_data_reasons)

        warnings: list[str] = []
        target = raw_fields["target"]
        if target == "-" or not target:
            warnings.append("TARGET_MISSING")
        start_at = None
        if DATE_PATTERN.fullmatch(raw_fields["start_at"]):
            try:
                start_at = datetime.strptime(raw_fields["start_at"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                pass
        if start_at is None:
            warnings.append("TIME_INVALID")
        cluster, candidate, clean_detail, cluster_warnings = _cluster(detail)
        warnings.extend(cluster_warnings)
        return ParsedAlarm(
            raw_span=span, raw_fields=raw_fields, start_at=start_at, target=target,
            alert_name=raw_fields["alert_name"], detail=clean_detail,
            cluster=cluster, cluster_candidate=candidate,
            needs_review=bool(warnings), warnings=tuple(warnings),
            fingerprint=raw_fields["fingerprint"],
        )
