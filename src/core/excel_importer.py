"""Read two mapping spreadsheet shapes and append safe rows to encrypted storage."""

import re
from concurrent.futures import Executor, Future
from xml.etree.ElementTree import ParseError
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from .crypto_store import CryptoStore, StorageError


DATA_FIELDS = {
    "grafana": ("service", "assignee", "alert_name", "description"),
    "n3r": ("server_name", "service_name", "purpose", "assignee"),
}
ALIASES = {
    "grafana": {
        "service": ("service", "서비스"),
        "assignee": ("assignee", "담당자"),
        "alert_name": ("alertname", "알람명"),
        "description": ("description", "descripton", "desciption", "설명"),
    },
    "n3r": {
        "server_name": ("servername", "서버명"),
        "service_name": ("servicename", "서비스명"),
        "purpose": ("purpose", "용도"),
        "assignee": ("assignee", "담당자"),
    },
}


def normalize(value: object) -> str:
    """Normalize only for comparisons; stored display values stay intact."""
    return " ".join(str(value or "").split()).casefold()


def mapping_key(kind: str, row: dict) -> tuple[str, ...]:
    if kind == "grafana":
        return normalize(row.get("service")), normalize(row.get("alert_name"))
    if kind == "n3r":
        return (normalize(row.get("server_name")),)
    raise ValueError("kind must be grafana or n3r")


def same_content(kind: str, first: dict, second: dict) -> bool:
    return all(normalize(first.get(field)) == normalize(second.get(field)) for field in DATA_FIELDS[kind])


@dataclass(frozen=True)
class ImportIssue:
    code: str
    row_number: int | None
    action: str


@dataclass(frozen=True)
class ImportConflict:
    row_number: int
    key: tuple[str, ...]
    existing: dict
    incoming: dict


@dataclass(frozen=True)
class ImportResult:
    status: str
    added: int
    skipped: int
    conflicts: tuple[ImportConflict, ...]
    errors: tuple[ImportIssue, ...]
    saved: bool


class ExcelImporter:
    """Keep row errors and conflicts visible while saving valid additions atomically."""

    def __init__(self, store: CryptoStore, clock=datetime.now) -> None:
        self.store = store
        self.clock = clock

    def submit_import(self, executor: Executor, path: Path, kind: str) -> Future[ImportResult]:
        """Run file I/O on a caller-owned worker so the UI thread stays free."""
        return executor.submit(self.import_file, path, kind)

    @staticmethod
    def _headers(values: tuple, kind: str) -> tuple[dict[str, int], bool]:
        positions: dict[str, int] = {}
        collision = False
        for index, value in enumerate(values):
            normalized = re.sub(r"[\s_]+", "", str(value or "").casefold())
            for field, names in ALIASES[kind].items():
                if normalized in names:
                    if field in positions:
                        collision = True
                    else:
                        positions[field] = index
        return positions, collision

    def import_file(self, path: Path, kind: str) -> ImportResult:
        if kind not in DATA_FIELDS:
            raise ValueError("kind must be grafana or n3r")
        path = Path(path)
        if path.suffix.casefold() not in {".xlsx", ".xlsm"}:
            return ImportResult("FAILED", 0, 0, (), (ImportIssue("UNSUPPORTED_FILE", None, "지원되는 Excel 파일을 선택하세요."),), False)
        try:
            existing = self.store.load(kind)
        except StorageError as exc:
            if exc.code == "NOT_FOUND":
                existing = []
            else:
                return ImportResult("FAILED", 0, 0, (), (ImportIssue(exc.code, None, exc.action),), False)
        try:
            workbook = load_workbook(path, read_only=True, data_only=True, keep_vba=False)
        except (OSError, ValueError, KeyError, BadZipFile, InvalidFileException, ParseError):
            # openpyxl raises several zip/XML exceptions for malformed files.
            return ImportResult("FAILED", 0, 0, (), (ImportIssue("EXCEL_READ_FAILED", None, "Excel 파일 형식과 읽기 권한을 확인하세요."),), False)
        try:
            return self._read_workbook(workbook, path, kind, existing)
        except (OSError, ValueError, KeyError, BadZipFile, InvalidFileException, ParseError):
            return ImportResult("FAILED", 0, 0, (),
                                (ImportIssue("EXCEL_READ_FAILED", None, "Excel 파일 형식과 읽기 권한을 확인하세요."),), False)
        finally:
            workbook.close()

    def _read_workbook(self, workbook, path: Path, kind: str, existing: list[dict]) -> ImportResult:
        errors: list[ImportIssue] = []
        conflicts: list[ImportConflict] = []
        index = {mapping_key(kind, row): row for row in existing}
        additions: list[dict] = []
        skipped = 0
        found_header = False
        for sheet in workbook.worksheets:
            rows = sheet.iter_rows(values_only=True)
            header_positions = None
            for row_number, values in enumerate(rows, 1):
                if header_positions is None:
                    positions, collision = self._headers(values, kind)
                    if len(positions) < 2 and row_number < 20:
                        continue
                    if collision:
                        errors.append(ImportIssue("HEADER_COLLISION", row_number, "중복 헤더 별칭을 정리하세요."))
                        break
                    if set(positions) != set(DATA_FIELDS[kind]):
                        errors.append(ImportIssue("HEADER_MISSING", row_number, "필수 4개 열의 헤더를 확인하세요."))
                        break
                    header_positions = positions
                    found_header = True
                    continue
                if not any(value is not None and str(value).strip() for value in values):
                    continue
                row = {field: str(values[index]).strip() if index < len(values) and values[index] is not None else ""
                       for field, index in header_positions.items()}
                key = mapping_key(kind, row)
                if not all(key) or not normalize(row["assignee"]):
                    errors.append(ImportIssue("ROW_REQUIRED_FIELD", row_number, "기본키와 담당자를 입력하세요."))
                    continue
                row.update({
                    "id": uuid4().hex, "schema_version": 1,
                    "updated_at": self.clock().isoformat(timespec="seconds"),
                    "source_file": path.name, "source": "excel", "jira_account_id": None,
                })
                current = index.get(key)
                if current is None:
                    index[key] = row
                    additions.append(row)
                elif same_content(kind, current, row):
                    skipped += 1
                else:
                    conflicts.append(ImportConflict(row_number, key, current.copy(), row))
            if found_header or errors:
                break
        if not found_header and not errors:
            errors.append(ImportIssue("HEADER_NOT_FOUND", None, "헤더 행을 첫 20행 안에 배치하세요."))
        if errors and not found_header:
            return ImportResult("FAILED", 0, 0, (), tuple(errors), False)
        if additions:
            try:
                self.store.save(kind, existing + additions)
            except StorageError as exc:
                return ImportResult("FAILED", 0, skipped, tuple(conflicts),
                                    tuple(errors + [ImportIssue(exc.code, None, exc.action)]), False)
        status = "PARTIAL" if errors or conflicts else "IMPORTED" if additions else "UNCHANGED"
        return ImportResult(status, len(additions), skipped, tuple(conflicts), tuple(errors), bool(additions))

    def resolve_conflict(self, kind: str, conflict: ImportConflict, choice: str) -> str:
        """Apply an explicit admin decision against the latest encrypted data."""
        if choice not in {"KEEP_EXISTING", "USE_INCOMING", "CANCEL"}:
            raise ValueError("unknown conflict choice")
        if choice != "USE_INCOMING":
            return choice
        records = self.store.load(kind)
        for index, current in enumerate(records):
            if mapping_key(kind, current) == conflict.key:
                if not same_content(kind, current, conflict.existing):
                    raise StorageError("STALE_CONFLICT", "매핑을 다시 읽고 충돌을 재검토하세요.")
                incoming = conflict.incoming.copy()
                incoming["id"] = current["id"]
                records[index] = incoming
                self.store.save(kind, records)
                return "USE_INCOMING"
        raise StorageError("STALE_CONFLICT", "매핑을 다시 읽고 충돌을 재검토하세요.")
