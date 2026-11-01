"""Local PBKDF2 accounts, process sessions, admin approval, and protected tokens."""

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from .crypto_store import SecretProtector, StorageError, WindowsDPAPI, atomic_write, local_app_root


RESET_RISK_WARNING = (
    "ID를 아는 사람은 누구나 비밀번호를 재설정할 수 있습니다. "
    "개인 Jira 토큰 삭제만으로 계정 침해·서비스 방해 위험이 없어지지 않습니다."
)
DEFAULT_ITERATIONS = 300_000


class AuthError(Exception):
    """A safe authentication failure with a machine-readable code."""

    def __init__(self, code: str, action: str) -> None:
        self.code = code
        self.action = action
        super().__init__(f"{code}: {action}")


@dataclass(frozen=True)
class Session:
    user_id: str
    credential_version: int
    session_id: str


@dataclass(frozen=True)
class ResetResult:
    user_id: str
    warning: str = RESET_RISK_WARNING


def _password_record(password: str, iterations: int) -> dict:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {
        "algorithm": "pbkdf2_hmac_sha256", "iterations": iterations, "version": 1,
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def _verify_password(password: str, saved: dict) -> bool:
    try:
        if saved["algorithm"] != "pbkdf2_hmac_sha256" or saved["version"] != 1:
            raise ValueError("unsupported password format")
        iterations = saved["iterations"]
        if type(iterations) is not int or not 100_000 <= iterations <= 2_000_000:
            raise ValueError("invalid iterations")
        salt = base64.b64decode(saved["salt"], validate=True)
        digest = base64.b64decode(saved["hash"], validate=True)
        if len(salt) < 16 or len(digest) != 32:
            raise ValueError("invalid hash shape")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(candidate, digest)
    except (KeyError, ValueError, TypeError) as exc:
        raise AuthError("HASH_FORMAT_INVALID", "계정 저장 파일을 확인하고 복구하세요.") from exc


class AuthManager:
    """Manage accounts and DPAPI token files within one Windows user profile."""

    def __init__(
        self, root: Path | None = None, protector: SecretProtector | None = None, *,
        iterations: int = DEFAULT_ITERATIONS,
    ) -> None:
        if not 100_000 <= iterations <= 2_000_000:
            raise ValueError("iterations must be between 100000 and 2000000")
        self.root = Path(root) if root is not None else local_app_root() / "config"
        self.accounts_path = self.root / "accounts.json"
        self.admin_path = self.root / "admin.json"
        self.token_dir = self.root / "tokens"
        self.protector = protector if protector is not None else WindowsDPAPI()
        self.iterations = iterations
        self._sessions: dict[str, Session] = {}

    def _read_accounts(self) -> dict:
        if not self.accounts_path.exists():
            return {}
        try:
            document = json.loads(self.accounts_path.read_text(encoding="utf-8"))
            if document["schema_version"] != 1 or not isinstance(document["accounts"], dict):
                raise ValueError("invalid account schema")
            return document["accounts"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise AuthError("ACCOUNTS_CORRUPT", "계정 파일의 백업을 확인하고 복구하세요.") from exc

    def _write_accounts(self, accounts: dict) -> None:
        document = {"schema_version": 1, "accounts": accounts}
        try:
            atomic_write(self.accounts_path, json.dumps(document, ensure_ascii=False).encode("utf-8"), backup=True)
        except OSError as exc:
            raise AuthError("ACCOUNT_WRITE_FAILED", "계정 저장 경로와 권한을 확인하세요.") from exc

    def _token_path(self, user_id: str) -> Path:
        return self.token_dir / (hashlib.sha256(user_id.encode("utf-8")).hexdigest() + ".dat")

    def register(self, user_id: str, password: str, name: str) -> None:
        if not user_id or not user_id.strip() or not password or not name or not name.strip():
            raise AuthError("INVALID_INPUT", "ID, 비밀번호, 이름을 모두 입력하세요.")
        accounts = self._read_accounts()
        if user_id in accounts:
            raise AuthError("DUPLICATE_ID", "다른 ID를 선택하세요.")
        accounts[user_id] = {
            "name": name, "password": _password_record(password, self.iterations),
            "credential_version": 1,
        }
        self._write_accounts(accounts)

    def login(self, user_id: str, password: str) -> Session:
        account = self._read_accounts().get(user_id)
        if account is None:
            raise AuthError("INVALID_CREDENTIALS", "ID 또는 비밀번호를 확인하세요.")
        try:
            password_record = account["password"]
            version = account["credential_version"]
            if type(version) is not int or version < 1:
                raise ValueError("invalid credential version")
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthError("ACCOUNTS_CORRUPT", "계정 파일의 백업을 확인하고 복구하세요.") from exc
        if not _verify_password(password, password_record):
            raise AuthError("INVALID_CREDENTIALS", "ID 또는 비밀번호를 확인하세요.")
        session = Session(user_id, version, secrets.token_urlsafe(32))
        self._sessions[session.session_id] = session
        return session

    def is_session_valid(self, session: Session) -> bool:
        if self._sessions.get(session.session_id) != session:
            return False
        account = self._read_accounts().get(session.user_id)
        return account is not None and account.get("credential_version") == session.credential_version

    def store_token(self, session: Session, token: str) -> None:
        if not self.is_session_valid(session):
            raise AuthError("SESSION_INVALID", "다시 로그인하세요.")
        if not token:
            raise AuthError("INVALID_INPUT", "토큰을 입력하세요.")
        try:
            protected = self.protector.protect(token.encode("utf-8"))
            atomic_write(self._token_path(session.user_id), protected)
        except (OSError, StorageError) as exc:
            raise AuthError("TOKEN_WRITE_FAILED", "현재 Windows 사용자 프로필과 저장 경로를 확인하세요.") from exc

    def get_token(self, session: Session) -> str | None:
        if not self.is_session_valid(session):
            raise AuthError("SESSION_INVALID", "다시 로그인하세요.")
        path = self._token_path(session.user_id)
        if not path.exists():
            return None
        try:
            return self.protector.unprotect(path.read_bytes()).decode("utf-8")
        except (OSError, StorageError, UnicodeDecodeError) as exc:
            raise AuthError("TOKEN_UNAVAILABLE", "현재 Windows 사용자 프로필에서 토큰을 다시 설정하세요.") from exc

    def reset_password(self, user_id: str, new_password: str) -> ResetResult:
        """Reset by ID; token deletion must succeed before credential replacement."""
        if not new_password:
            raise AuthError("INVALID_INPUT", "새 비밀번호를 입력하세요.")
        accounts = self._read_accounts()
        account = accounts.get(user_id)
        if account is None:
            raise AuthError("UNKNOWN_ID", "등록된 ID를 확인하세요.")
        try:
            old_version = account["credential_version"]
            if type(old_version) is not int or old_version < 1:
                raise ValueError("invalid credential version")
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthError("ACCOUNTS_CORRUPT", "계정 파일의 백업을 확인하고 복구하세요.") from exc
        path = self._token_path(user_id)
        previous_token: bytes | None = None
        try:
            if path.exists():
                previous_token = path.read_bytes()
                path.unlink()
        except OSError as exc:
            raise AuthError("TOKEN_DELETE_FAILED", "현재 Windows 사용자 프로필에서 토큰을 삭제한 뒤 재시도하세요.") from exc
        account["password"] = _password_record(new_password, self.iterations)
        account["credential_version"] = old_version + 1
        try:
            self._write_accounts(accounts)
        except AuthError:
            if previous_token is not None:
                try:
                    atomic_write(path, previous_token)
                except OSError:
                    raise AuthError("RESET_INCOMPLETE", "토큰 복원 실패. 관리자에게 계정 상태 확인을 요청하세요.")
            raise
        self._sessions = {key: value for key, value in self._sessions.items() if value.user_id != user_id}
        return ResetResult(user_id)

    def set_initial_admin_password(self, password: str) -> None:
        if self.admin_path.exists():
            raise AuthError("ADMIN_EXISTS", "관리자 비밀번호가 이미 설정되었습니다.")
        if not password:
            raise AuthError("INVALID_INPUT", "관리자 비밀번호를 입력하세요.")
        self._write_admin(_password_record(password, self.iterations))

    def _read_admin(self) -> dict:
        try:
            document = json.loads(self.admin_path.read_text(encoding="utf-8"))
            if document["schema_version"] != 1 or not isinstance(document["password"], dict):
                raise ValueError("invalid admin schema")
            return document["password"]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise AuthError("ADMIN_UNAVAILABLE", "관리자 비밀번호 또는 백업을 확인하세요. 자동 초기화하지 않습니다.") from exc

    def _write_admin(self, password: dict) -> None:
        try:
            atomic_write(self.admin_path, json.dumps({"schema_version": 1, "password": password}).encode("utf-8"), backup=True)
        except OSError as exc:
            raise AuthError("ADMIN_WRITE_FAILED", "관리자 설정 경로와 권한을 확인하세요.") from exc

    def verify_admin(self, password: str) -> bool:
        return _verify_password(password, self._read_admin())

    def change_admin_password(self, old_password: str, new_password: str) -> None:
        if not self.verify_admin(old_password):
            raise AuthError("INVALID_ADMIN_PASSWORD", "기존 관리자 비밀번호를 확인하세요.")
        if not new_password:
            raise AuthError("INVALID_INPUT", "새 관리자 비밀번호를 입력하세요.")
        self._write_admin(_password_record(new_password, self.iterations))
