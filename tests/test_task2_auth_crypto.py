"""TC-02A through TC-02E and atomic failure checks for local security."""

import hashlib
import hmac
import json
from pathlib import Path

import pytest

from src.core.auth_manager import AuthError, AuthManager, RESET_RISK_WARNING
from src.core.crypto_store import CryptoStore, StorageError


class ProfileProtector:
    """A test-only stand-in for a Windows user-bound DPAPI protector."""

    def __init__(self, profile: bytes = b"profile-A") -> None:
        self.profile = profile

    def protect(self, data: bytes) -> bytes:
        return hmac.new(self.profile, data, hashlib.sha256).digest() + data

    def unprotect(self, data: bytes) -> bytes:
        digest, content = data[:32], data[32:]
        if not hmac.compare_digest(digest, hmac.new(self.profile, content, hashlib.sha256).digest()):
            raise StorageError("DPAPI_FAILED", "Different Windows profile")
        return content


def manager(tmp_path, protector=None):
    return AuthManager(tmp_path / "account", protector or ProfileProtector(), iterations=100_000)


def test_tc02a_signup_login_salted_hash_and_duplicate(tmp_path):
    auth = manager(tmp_path)
    auth.register("alice", "synthetic-password", "합성 사용자")
    auth.register("bob", "synthetic-password", "합성 사용자2")
    content = auth.accounts_path.read_text(encoding="utf-8")
    saved = json.loads(content)["accounts"]
    assert "synthetic-password" not in content
    assert saved["alice"]["password"]["salt"] != saved["bob"]["password"]["salt"]
    assert saved["alice"]["password"]["iterations"] == 100_000
    assert auth.is_session_valid(auth.login("alice", "synthetic-password"))
    with pytest.raises(AuthError, match="INVALID_CREDENTIALS"):
        auth.login("alice", "wrong")
    with pytest.raises(AuthError, match="DUPLICATE_ID"):
        auth.register("alice", "another", "Again")
    with pytest.raises(AuthError, match="INVALID_INPUT"):
        auth.register("", "password", "Name")


def test_tc02b_id_only_reset_removes_token_and_invalidates_sessions(tmp_path):
    auth = manager(tmp_path)
    auth.register("alice", "old-password", "Alice")
    old_session = auth.login("alice", "old-password")
    auth.store_token(old_session, "synthetic-jira-token")
    token_path = auth._token_path("alice")
    assert b"synthetic-jira-token" != token_path.read_bytes()
    assert auth.get_token(old_session) == "synthetic-jira-token"
    second_process = manager(tmp_path)
    other_session = second_process.login("alice", "old-password")

    result = auth.reset_password("alice", "new-password")
    assert result.warning == RESET_RISK_WARNING
    assert "계정 침해" in result.warning
    assert not token_path.exists()
    assert not auth.is_session_valid(old_session)
    with pytest.raises(AuthError, match="INVALID_CREDENTIALS"):
        auth.login("alice", "old-password")
    assert auth.get_token(auth.login("alice", "new-password")) is None

    assert not second_process.is_session_valid(other_session)
    assert second_process.login("alice", "new-password").credential_version == 2


def test_tc02c_token_delete_failure_blocks_password_change(tmp_path, monkeypatch):
    auth = manager(tmp_path)
    auth.register("alice", "old-password", "Alice")
    session = auth.login("alice", "old-password")
    auth.store_token(session, "synthetic-jira-token")
    token_path = auth._token_path("alice")
    original_unlink = Path.unlink

    def fail_token_unlink(path, *args, **kwargs):
        if path == token_path:
            raise PermissionError("synthetic deletion failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_token_unlink)
    with pytest.raises(AuthError, match="TOKEN_DELETE_FAILED"):
        auth.reset_password("alice", "new-password")
    assert auth.is_session_valid(session)
    assert auth.login("alice", "old-password")
    assert token_path.exists()


def test_tc02d_authenticated_mapping_and_corruption(tmp_path):
    store = CryptoStore(tmp_path / "data", ProfileProtector())
    grafana = [{"service": "synthetic-service", "assignee": "A"}]
    n3r = [{"server_name": "synthetic-server", "assignee": "B"}]
    grafana_path = store.save("grafana", grafana)
    n3r_path = store.save("n3r", n3r)
    assert store.load("grafana") == grafana
    assert store.load("n3r") == n3r
    assert b"synthetic-service" not in grafana_path.read_bytes()
    assert b"synthetic-server" not in n3r_path.read_bytes()
    assert set(json.loads(grafana_path.read_bytes())) == {"schema_version", "key_id", "nonce", "ciphertext", "auth_tag"}

    store.save("grafana", [{"service": "new"}])
    backup = grafana_path.with_suffix(".dat.bak")
    assert backup.exists() and b"synthetic-service" not in backup.read_bytes()
    container = json.loads(grafana_path.read_bytes())
    encoded = container["ciphertext"]
    container["ciphertext"] = ("A" if encoded[0] != "A" else "B") + encoded[1:]
    grafana_path.write_bytes(json.dumps(container).encode("utf-8"))
    with pytest.raises(StorageError) as error:
        store.load("grafana")
    assert error.value.code == "DATA_CORRUPT"
    assert "백업" in error.value.action
    assert store.load("n3r") == n3r


def test_tc02e_admin_password_change_keeps_mapping_key_and_profile_boundary(tmp_path):
    protector = ProfileProtector()
    auth = manager(tmp_path, protector)
    store = CryptoStore(tmp_path / "data", protector)
    auth.set_initial_admin_password("first-admin")
    store.save("grafana", [{"service": "synthetic"}])
    key_before = store.key_path.read_bytes()
    auth.change_admin_password("first-admin", "second-admin")
    assert not auth.verify_admin("first-admin")
    assert auth.verify_admin("second-admin")
    assert store.key_path.read_bytes() == key_before
    assert store.load("grafana") == [{"service": "synthetic"}]
    with pytest.raises(AuthError, match="ADMIN_EXISTS"):
        auth.set_initial_admin_password("reset")

    other_profile = CryptoStore(tmp_path / "data", ProfileProtector(b"profile-B"))
    with pytest.raises(StorageError) as error:
        other_profile.load("grafana")
    assert error.value.code == "KEY_UNAVAILABLE"
    assert "Excel" in error.value.action


def test_mapping_replace_failure_preserves_original(tmp_path, monkeypatch):
    import src.core.crypto_store as crypto_module

    store = CryptoStore(tmp_path / "data", ProfileProtector())
    path = store.save("grafana", [{"service": "original"}])
    before = path.read_bytes()
    real_replace = crypto_module.os.replace

    def fail_final_replace(source, destination):
        if destination == path:
            raise OSError("synthetic replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(crypto_module.os, "replace", fail_final_replace)
    with pytest.raises(StorageError, match="WRITE_FAILED"):
        store.save("grafana", [{"service": "replacement"}])
    assert path.read_bytes() == before
    assert store.load("grafana") == [{"service": "original"}]


def test_password_reset_account_write_failure_restores_token(tmp_path, monkeypatch):
    auth = manager(tmp_path)
    auth.register("alice", "old-password", "Alice")
    session = auth.login("alice", "old-password")
    auth.store_token(session, "synthetic-jira-token")
    original_write = auth._write_accounts

    def fail_write(accounts):
        raise AuthError("ACCOUNT_WRITE_FAILED", "Synthetic write failure")

    monkeypatch.setattr(auth, "_write_accounts", fail_write)
    with pytest.raises(AuthError, match="ACCOUNT_WRITE_FAILED"):
        auth.reset_password("alice", "new-password")
    monkeypatch.setattr(auth, "_write_accounts", original_write)
    assert auth.get_token(session) == "synthetic-jira-token"
    assert auth.login("alice", "old-password")


def test_hash_format_error_is_explicit(tmp_path):
    auth = manager(tmp_path)
    auth.register("alice", "old-password", "Alice")
    document = json.loads(auth.accounts_path.read_text(encoding="utf-8"))
    document["accounts"]["alice"]["password"]["algorithm"] = "unknown"
    auth.accounts_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(AuthError, match="HASH_FORMAT_INVALID"):
        auth.login("alice", "old-password")


def test_default_paths_use_localappdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    protector = ProfileProtector()
    assert AuthManager(protector=protector).root == tmp_path / "NotiAutomation" / "config"
    assert CryptoStore(protector=protector).data_dir == tmp_path / "NotiAutomation" / "data"
