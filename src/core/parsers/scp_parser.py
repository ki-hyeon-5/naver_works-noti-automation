"""Explicitly report that SCP alarm parsing is outside the initial scope."""

from ..models import ParseBatchResult, ParseIssue
from .base_parser import BaseParser


class ScpParser(BaseParser):
    def parse(self, text: str) -> ParseBatchResult:
        return ParseBatchResult(
            (), 0,
            (ParseIssue("UNSUPPORTED_SOURCE", (0, len(text)), "SCP 알람은 현재 지원하지 않습니다."),),
            0, {},
        )
