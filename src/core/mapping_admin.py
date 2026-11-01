"""Authorize and validate atomic edits to encrypted mapping rows."""

from datetime import datetime
from uuid import uuid4

from .auth_manager import AuthManager
from .crypto_store import CryptoStore, StorageError
from .excel_importer import DATA_FIELDS, mapping_key, normalize


class MappingAdminError(Exception):
    def __init__(self, code: str, action: str) -> None:
        self.code, self.action = code, action
        super().__init__(f"{code}: {action}")


class MappingAdmin:
    """Hold only a process-local administrator approval; never persist it."""

    def __init__(self, auth: AuthManager, store: CryptoStore) -> None:
        self.auth, self.store = auth, store
        self.approved = False

    def approve(self, password: str) -> bool:
        self.approved = self.auth.verify_admin(password)
        return self.approved

    def lock(self) -> None:
        self.approved = False

    def _require(self) -> None:
        if not self.approved:
            raise MappingAdminError("ADMIN_REQUIRED", "관리자 비밀번호로 승인하세요.")

    def rows(self, kind: str) -> list[dict]:
        self._require()
        try:
            return self.store.load(kind)
        except StorageError as exc:
            if exc.code == "NOT_FOUND":
                return []
            raise

    def save_row(self, kind: str, fields: dict[str, str], row_id: str | None = None) -> str:
        self._require()
        if kind not in DATA_FIELDS:
            raise ValueError("kind must be grafana or n3r")
        if set(fields) != set(DATA_FIELDS[kind]) | {"jira_account_id"}:
            raise MappingAdminError("INVALID_ROW", "필수 매핑 열을 모두 입력하세요.")
        cleaned = {key: str(value).strip() for key, value in fields.items()}
        if not all(mapping_key(kind, cleaned)) or not normalize(cleaned["assignee"]):
            raise MappingAdminError("REQUIRED_FIELD", "기본키와 담당자를 입력하세요.")
        rows = self.rows(kind)
        position = next((i for i, row in enumerate(rows) if row["id"] == row_id), None) if row_id else None
        if row_id and position is None:
            raise MappingAdminError("ROW_NOT_FOUND", "목록을 새로고침하고 다시 선택하세요.")
        key = mapping_key(kind, cleaned)
        if any(mapping_key(kind, row) == key and i != position for i, row in enumerate(rows)):
            raise MappingAdminError("DUPLICATE_KEY", "같은 키의 행이 이미 있습니다.")
        identity = row_id or uuid4().hex
        record = {**cleaned, "id": identity, "schema_version": 1,
                  "updated_at": datetime.now().isoformat(timespec="seconds"),
                  "source": "manual", "source_file": ""}
        if position is None:
            rows.append(record)
        else:
            rows[position] = record
        self.store.save(kind, rows)
        return identity

    def delete_row(self, kind: str, row_id: str) -> None:
        self._require()
        rows = self.rows(kind)
        remaining = [row for row in rows if row.get("id") != row_id]
        if len(remaining) == len(rows):
            raise MappingAdminError("ROW_NOT_FOUND", "목록을 새로고침하고 다시 선택하세요.")
        self.store.save(kind, remaining)
