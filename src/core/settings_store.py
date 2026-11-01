"""Persist per-user UI settings atomically without storing Jira tokens."""

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .auth_manager import AuthManager, Session
from .crypto_store import atomic_write, local_app_root


class SettingsError(Exception):
    def __init__(self, code: str, action: str) -> None:
        self.code, self.action = code, action
        super().__init__(f"{code}: {action}")


@dataclass(frozen=True)
class UserSettings:
    log_base_path: str = "C:/noti-log"
    auto_year_month_folder: bool = True
    default_assignee_name: str = ""
    default_assignee_account_id: str = ""
    epic_options: tuple[str, ...] = ()
    default_epic: str = ""
    default_watchers: tuple[str, ...] = ()
    alarm_watchers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    reporter_account_id: str = ""
    jira_environment_status: str = "MOCK"


class SettingsStore:
    """Require a valid process session for every per-user settings operation."""

    def __init__(self, auth: AuthManager, root: Path | None = None) -> None:
        self.auth = auth
        self.root = Path(root) if root is not None else local_app_root() / "config" / "settings"

    def _path(self, session: Session) -> Path:
        if not self.auth.is_session_valid(session):
            raise SettingsError("SESSION_INVALID", "다시 로그인하세요.")
        digest = hashlib.sha256(session.user_id.encode("utf-8")).hexdigest()
        return self.root / f"{digest}.json"

    @staticmethod
    def _validate(settings: UserSettings) -> None:
        if not settings.log_base_path.strip():
            raise SettingsError("INVALID_LOG_PATH", "로그 경로를 입력하세요.")
        if settings.jira_environment_status not in ("MOCK", "UNVERIFIED"):
            raise SettingsError("JIRA_NOT_VERIFIED", "실 Jira 연결은 검증 전까지 MOCK으로 유지하세요.")
        if settings.default_epic and settings.default_epic not in settings.epic_options:
            raise SettingsError("INVALID_EPIC", "기본 에픽을 에픽 목록에 포함하세요.")
        if bool(settings.default_assignee_name) != bool(settings.default_assignee_account_id):
            raise SettingsError("INVALID_ASSIGNEE", "기본 담당자 이름과 Jira 계정 ID를 함께 입력하세요.")
        for values in (settings.epic_options, settings.default_watchers, *settings.alarm_watchers.values()):
            if any(not value.strip() for value in values):
                raise SettingsError("INVALID_LIST", "빈 에픽·참조자 값을 제거하세요.")

    def load(self, session: Session) -> UserSettings:
        path = self._path(session)
        if not path.exists():
            return UserSettings()
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            if document.pop("schema_version") != 1 or set(document) != set(UserSettings.__dataclass_fields__):
                raise ValueError("settings schema")
            if any(key in document for key in ("token", "password", "api_token")):
                raise ValueError("secret in settings")
            for key in ("epic_options", "default_watchers"):
                if not isinstance(document[key], list) or any(not isinstance(v, str) for v in document[key]):
                    raise ValueError("invalid list")
                document[key] = tuple(document[key])
            overrides = document["alarm_watchers"]
            if not isinstance(overrides, dict) or any(not isinstance(k, str) or not isinstance(v, list) or
                                                      any(not isinstance(member, str) for member in v)
                                                      for k, v in overrides.items()):
                raise ValueError("invalid overrides")
            document["alarm_watchers"] = {key: tuple(value) for key, value in overrides.items()}
            if (any(not isinstance(document[key], str) for key in (
                    "log_base_path", "default_assignee_name", "default_assignee_account_id",
                    "default_epic", "reporter_account_id", "jira_environment_status")) or
                    type(document["auto_year_month_folder"]) is not bool):
                raise ValueError("invalid settings types")
            settings = UserSettings(**document)
            self._validate(settings)
            return settings
        except (OSError, ValueError, KeyError, TypeError, SettingsError) as exc:
            raise SettingsError("SETTINGS_CORRUPT", "설정 백업을 확인하고 복구하세요.") from exc

    def save(self, session: Session, settings: UserSettings) -> None:
        path = self._path(session)
        if type(settings) is not UserSettings:
            raise SettingsError("INVALID_SETTINGS", "설정 형식을 확인하세요.")
        self._validate(settings)
        document = dict(settings.__dict__)
        document["schema_version"] = 1
        try:
            atomic_write(path, json.dumps(document, ensure_ascii=False).encode("utf-8"), backup=True)
        except OSError as exc:
            raise SettingsError("SETTINGS_WRITE_FAILED", "설정 저장 경로와 권한을 확인하세요.") from exc
