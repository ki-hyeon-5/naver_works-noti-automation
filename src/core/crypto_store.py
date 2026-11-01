"""DPAPI-protected local key and authenticated mapping-file storage."""

import base64
import ctypes
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class StorageError(Exception):
    """A storage failure with a safe user action and no secret details."""

    def __init__(self, code: str, action: str) -> None:
        self.code = code
        self.action = action
        super().__init__(f"{code}: {action}")


class SecretProtector(Protocol):
    def protect(self, data: bytes) -> bytes: ...
    def unprotect(self, data: bytes) -> bytes: ...


def local_app_root() -> Path:
    """Resolve the per-Windows-user persistent application directory."""
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "NotiAutomation"
    if os.name == "nt":
        return Path.home() / "AppData" / "Local" / "NotiAutomation"
    raise StorageError("WINDOWS_REQUIRED", "macOS 테스트에서는 저장 경로를 명시하세요.")


class WindowsDPAPI:
    """Bind secrets to the current Windows user profile with DPAPI."""

    def __init__(self) -> None:
        if os.name != "nt":
            raise StorageError("WINDOWS_REQUIRED", "DPAPI는 Windows 11에서만 사용할 수 있습니다.")

    @staticmethod
    def _call(data: bytes, protect: bool) -> bytes:
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        buffer = ctypes.create_string_buffer(data)
        source = DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        destination = DataBlob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        operation = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        operation.restype = wintypes.BOOL
        operation.argtypes = (
            [ctypes.POINTER(DataBlob), wintypes.LPCWSTR, ctypes.POINTER(DataBlob),
             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
            if protect else
            [ctypes.POINTER(DataBlob), ctypes.c_void_p, ctypes.POINTER(DataBlob),
             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DataBlob)]
        )
        arguments = (ctypes.byref(source), None, None, None, None, 1, ctypes.byref(destination))
        if not operation(*arguments):
            raise StorageError("DPAPI_FAILED", "현재 Windows 사용자 프로필에서 보호 데이터를 확인하세요.")
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            local_free = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
            local_free.argtypes = [ctypes.c_void_p]
            local_free.restype = ctypes.c_void_p
            local_free(destination.pbData)

    def protect(self, data: bytes) -> bytes:
        return self._call(data, True)

    def unprotect(self, data: bytes) -> bytes:
        return self._call(data, False)


def atomic_write(path: Path, data: bytes, *, backup: bool = False) -> None:
    """Write a private temporary file, optional encrypted backup, then replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    backup_temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as output:
            temporary = Path(output.name)
            os.chmod(temporary, 0o600)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        if backup and path.exists():
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.backup.", delete=False) as output:
                backup_temp = Path(output.name)
                os.chmod(backup_temp, 0o600)
                with path.open("rb") as original:
                    shutil.copyfileobj(original, output)
                output.flush()
                os.fsync(output.fileno())
            os.replace(backup_temp, path.with_suffix(path.suffix + ".bak"))
            backup_temp = None
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if backup_temp is not None:
            backup_temp.unlink(missing_ok=True)


def _encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


class CryptoStore:
    """Keep Grafana and N3R databases separate under one DPAPI-wrapped DEK."""

    FILES = {"grafana": "grafana_db.dat", "n3r": "n3r_db.dat"}

    def __init__(self, data_dir: Path | None = None, protector: SecretProtector | None = None) -> None:
        self.data_dir = Path(data_dir) if data_dir is not None else local_app_root() / "data"
        self.protector = protector if protector is not None else WindowsDPAPI()
        self.key_path = self.data_dir / "mapping_key.dat"

    def _key(self) -> bytes:
        if self.key_path.exists():
            try:
                key = self.protector.unprotect(self.key_path.read_bytes())
                if len(key) != 32:
                    raise ValueError("invalid key length")
                return key
            except (OSError, ValueError, StorageError) as exc:
                raise StorageError("KEY_UNAVAILABLE", "원래 Windows 프로필에서 열거나 원본 Excel을 재가져오세요.") from exc
        if any((self.data_dir / name).exists() for name in self.FILES.values()):
            raise StorageError("KEY_UNAVAILABLE", "암호화 키가 없습니다. 원본 Excel을 재가져오세요.")
        key = os.urandom(32)
        try:
            atomic_write(self.key_path, self.protector.protect(key))
        except (OSError, StorageError) as exc:
            raise StorageError("KEY_WRITE_FAILED", "데이터 폴더 권한을 확인하세요.") from exc
        return key

    def _path(self, kind: str) -> Path:
        if kind not in self.FILES:
            raise ValueError("kind must be grafana or n3r")
        return self.data_dir / self.FILES[kind]

    def save(self, kind: str, records: list[dict]) -> Path:
        path = self._path(kind)
        key = self._key()
        nonce = os.urandom(12)
        plaintext = json.dumps(records, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        sealed = AESGCM(key).encrypt(nonce, plaintext, kind.encode("ascii"))
        container = {
            "schema_version": 1,
            "key_id": hashlib.sha256(key).hexdigest()[:16],
            "nonce": _encode(nonce),
            "ciphertext": _encode(sealed[:-16]),
            "auth_tag": _encode(sealed[-16:]),
        }
        try:
            atomic_write(path, json.dumps(container, separators=(",", ":")).encode("utf-8"), backup=True)
        except OSError as exc:
            raise StorageError("WRITE_FAILED", "저장 경로와 권한을 확인하고 다시 시도하세요.") from exc
        return path

    def load(self, kind: str) -> list[dict]:
        path = self._path(kind)
        if not path.exists():
            raise StorageError("NOT_FOUND", "매핑 데이터를 가져오세요.")
        key = self._key()
        try:
            container = json.loads(path.read_bytes())
            if container["schema_version"] != 1 or container["key_id"] != hashlib.sha256(key).hexdigest()[:16]:
                raise ValueError("unsupported version or key")
            plaintext = AESGCM(key).decrypt(
                _decode(container["nonce"]),
                _decode(container["ciphertext"]) + _decode(container["auth_tag"]),
                kind.encode("ascii"),
            )
            records = json.loads(plaintext.decode("utf-8"))
            if not isinstance(records, list):
                raise ValueError("invalid payload")
            return records
        except (OSError, ValueError, KeyError, TypeError, InvalidTag) as exc:
            raise StorageError("DATA_CORRUPT", "원본·암호화 백업을 확인하고 관리자에게 복구를 요청하세요.") from exc
