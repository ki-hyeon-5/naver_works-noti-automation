"""Build deterministic, pairwise-compatible Jira issue groups for preview."""

import hashlib
import json
from dataclasses import dataclass
from collections.abc import Sequence

from .excel_importer import normalize
from .formatter import clean_alert_name
from .models import ParsedAlarm


@dataclass(frozen=True)
class ReviewSelection:
    alarm: ParsedAlarm
    jira_account_id: str | None
    source_tag: str | None


@dataclass(frozen=True)
class BundleGroup:
    members: tuple[ReviewSelection, ...]
    split_reason: str | None = None


@dataclass(frozen=True)
class BundlePlan:
    groups: tuple[BundleGroup, ...]
    input_order_hash: str
    requires_confirmation: bool


def _compatible(first: ReviewSelection, second: ReviewSelection) -> bool:
    if not first.alarm.can_register or not second.alarm.can_register:
        return False
    if not first.jira_account_id or first.jira_account_id != second.jira_account_id:
        return False
    if first.source_tag not in ("N3R", "GRAFANA") or first.source_tag != second.source_tag:
        return False
    return (
        normalize(first.alarm.target) == normalize(second.alarm.target)
        or normalize(clean_alert_name(first.alarm.alert_name)) == normalize(clean_alert_name(second.alarm.alert_name))
    )


class BundlePlanner:
    """Greedily group by input order, requiring compatibility with every member."""

    def plan(self, selections: Sequence[ReviewSelection], *, bundled: bool) -> BundlePlan:
        order = [
            (item.alarm.fingerprint, item.alarm.target, item.alarm.alert_name,
             item.jira_account_id, item.source_tag)
            for item in selections
        ]
        order_hash = hashlib.sha256(json.dumps(order, ensure_ascii=False).encode("utf-8")).hexdigest()
        if not bundled:
            groups = tuple(BundleGroup((item,), "INDIVIDUAL_MODE") for item in selections)
            return BundlePlan(groups, order_hash, False)

        remaining = list(selections)
        groups: list[BundleGroup] = []
        while remaining:
            first = remaining.pop(0)
            members = [first]
            still_remaining = []
            for candidate in remaining:
                if all(_compatible(candidate, member) for member in members):
                    members.append(candidate)
                else:
                    still_remaining.append(candidate)
            remaining = still_remaining
            reason = "GROUP_CONDITIONS_NOT_MET" if len(members) == 1 else None
            groups.append(BundleGroup(tuple(members), reason))
        return BundlePlan(tuple(groups), order_hash, True)
