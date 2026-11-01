"""TC-06A through TC-06C: admin gates, encrypted CRUD, import, and settings."""

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from openpyxl import Workbook

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QMessageBox

from src.core.auth_manager import AuthManager, RESET_RISK_WARNING
from src.core.crypto_store import CryptoStore, StorageError
from src.core.excel_importer import ExcelImporter
from src.core.mapping_admin import MappingAdmin, MappingAdminError
from src.core.settings_store import SettingsError, SettingsStore, UserSettings
from src.ui.admin_dialog import AdminDialog
from src.ui.auth_dialog import AuthDialog
from src.ui.settings_dialog import SettingsDialog


class FakeProtector:
    def __init__(self):
        self.key = AESGCM.generate_key(bit_length=128)

    def protect(self, data):
        nonce = os.urandom(12)
        return nonce + AESGCM(self.key).encrypt(nonce, data, None)

    def unprotect(self, data):
        return AESGCM(self.key).decrypt(data[:12], data[12:], None)


def setup(tmp_path):
    protector = FakeProtector()
    auth = AuthManager(tmp_path / "config", protector, iterations=100_000)
    store = CryptoStore(tmp_path / "data", protector)
    auth.register("tester", "password", "Tester")
    session = auth.login("tester", "password")
    return auth, store, session


def fields(kind, key="server-01", assignee="Tester"):
    if kind == "grafana":
        return dict(service="Billing", assignee=assignee, alert_name=key,
                    description="synthetic", jira_account_id="jira-A")
    return dict(server_name=key, service_name="Billing", purpose="synthetic",
                assignee=assignee, jira_account_id="jira-A")


def app():
    return QApplication.instance() or QApplication([])


def test_tc06a_unapproved_changes_leave_encrypted_files_unchanged(tmp_path):
    auth, store, _ = setup(tmp_path)
    auth.set_initial_admin_password("admin-secret")
    admin = MappingAdmin(auth, store)
    with pytest.raises(MappingAdminError, match="ADMIN_REQUIRED"):
        admin.save_row("n3r", fields("n3r"))
    assert not (tmp_path / "data" / "n3r_db.dat").exists()
    assert not admin.approve("wrong")
    with pytest.raises(MappingAdminError, match="ADMIN_REQUIRED"):
        admin.rows("grafana")
    app()
    dialog = AdminDialog(admin, ExcelImporter(store))
    assert not dialog.tabs.isEnabled()
    dialog.close()


def test_tc06b_admin_crud_survives_restart_and_password_change(tmp_path):
    auth, store, _ = setup(tmp_path)
    auth.set_initial_admin_password("admin-secret")
    admin = MappingAdmin(auth, store)
    assert admin.approve("admin-secret")
    grafana_id = admin.save_row("grafana", fields("grafana", "CPU high"))
    n3r_id = admin.save_row("n3r", fields("n3r"))
    assert store._path("grafana").read_bytes().find(b"CPU high") == -1
    assert store._path("n3r").read_bytes().find(b"server-01") == -1
    with pytest.raises(MappingAdminError, match="DUPLICATE_KEY"):
        admin.save_row("n3r", fields("n3r", assignee="Other"))
    admin.save_row("grafana", fields("grafana", "CPU high", "Other"), grafana_id)
    admin.delete_row("n3r", n3r_id)
    auth.change_admin_password("admin-secret", "new-admin")
    admin.lock()
    with pytest.raises(MappingAdminError, match="ADMIN_REQUIRED"):
        admin.delete_row("grafana", grafana_id)
    restarted = MappingAdmin(AuthManager(tmp_path / "config", auth.protector, iterations=100_000),
                             CryptoStore(tmp_path / "data", auth.protector))
    assert restarted.approve("new-admin")
    assert restarted.rows("grafana")[0]["assignee"] == "Other"
    assert restarted.rows("n3r") == []


def test_tc06b_save_failure_keeps_original_ciphertext(tmp_path, monkeypatch):
    auth, store, _ = setup(tmp_path)
    auth.set_initial_admin_password("admin-secret")
    admin = MappingAdmin(auth, store)
    admin.approve("admin-secret")
    identity = admin.save_row("n3r", fields("n3r"))
    before = store._path("n3r").read_bytes()
    monkeypatch.setattr("src.core.crypto_store.atomic_write", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(StorageError, match="WRITE_FAILED"):
        admin.save_row("n3r", fields("n3r", assignee="Other"), identity)
    assert store._path("n3r").read_bytes() == before


def test_tc06c_excel_append_conflict_and_settings_without_token_plaintext(tmp_path):
    auth, store, session = setup(tmp_path)
    auth.set_initial_admin_password("admin-secret")
    admin = MappingAdmin(auth, store)
    admin.approve("admin-secret")
    admin.save_row("n3r", fields("n3r"))
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["server_name", "service_name", "purpose", "assignee"])
    sheet.append(["server-01", "Billing", "synthetic", "Other"])
    sheet.append(["server-02", "Billing", "synthetic", "Tester"])
    source = tmp_path / "synthetic.xlsx"
    workbook.save(source)
    with ThreadPoolExecutor(max_workers=1) as executor:
        result = ExcelImporter(store).submit_import(executor, source, "n3r").result(timeout=5)
    assert result.status == "PARTIAL" and result.added == 1 and len(result.conflicts) == 1
    assert next(row for row in store.load("n3r") if row["server_name"] == "server-01")["assignee"] == "Tester"
    assert ExcelImporter(store).resolve_conflict("n3r", result.conflicts[0], "USE_INCOMING") == "USE_INCOMING"
    assert next(row for row in store.load("n3r") if row["server_name"] == "server-01")["assignee"] == "Other"

    settings = SettingsStore(auth, tmp_path / "settings")
    value = UserSettings(log_base_path=str(tmp_path / "logs"), auto_year_month_folder=False,
                         default_assignee_name="Tester", default_assignee_account_id="jira-A",
                         epic_options=("EPIC-1", "EPIC-2"), default_epic="EPIC-2",
                         default_watchers=("watcher-A",), alarm_watchers={"server-01": ("watcher-B",)},
                         reporter_account_id="reporter-A")
    settings.save(session, value)
    auth.store_token(session, "synthetic-secret-token")
    saved_file = next((tmp_path / "settings").glob("*.json"))
    content = saved_file.read_text(encoding="utf-8")
    assert "synthetic-secret-token" not in content and "token" not in json.loads(content)
    assert SettingsStore(auth, tmp_path / "settings").load(session) == value
    assert auth.get_token(session) == "synthetic-secret-token"


def test_tc06c_settings_corruption_and_write_failure_are_explicit(tmp_path, monkeypatch):
    auth, _, session = setup(tmp_path)
    settings = SettingsStore(auth, tmp_path / "settings")
    path = settings._path(session)
    path.parent.mkdir()
    path.write_text("broken", encoding="utf-8")
    with pytest.raises(SettingsError, match="SETTINGS_CORRUPT"):
        settings.load(session)
    path.unlink()
    monkeypatch.setattr("src.core.settings_store.atomic_write", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(SettingsError, match="SETTINGS_WRITE_FAILED"):
        settings.save(session, UserSettings())
    assert not path.exists()
    with pytest.raises(SettingsError, match="JIRA_NOT_VERIFIED"):
        settings.save(session, UserSettings(jira_environment_status="LIVE"))


def test_task6_dialogs_show_reset_risk_and_do_not_preload_token(tmp_path):
    app()
    auth, _, session = setup(tmp_path)
    auth.store_token(session, "synthetic-secret-token")
    login = AuthDialog(auth)
    assert any(RESET_RISK_WARNING in label.text() for label in login.findChildren(QLabel))
    settings = SettingsDialog(auth, session, SettingsStore(auth, tmp_path / "settings"))
    assert settings.token.text() == ""
    settings.close()
    login.close()


def test_admin_dialog_buttons_require_approval_and_persist_rows(tmp_path):
    app()
    auth, store, _ = setup(tmp_path)
    auth.set_initial_admin_password("admin-secret")
    dialog = AdminDialog(MappingAdmin(auth, store), ExcelImporter(store))
    dialog.n3r.fields["server_name"].setText("server-01")
    dialog.n3r.save_row(False)
    assert not store._path("n3r").exists()
    assert "ADMIN_REQUIRED" in dialog.n3r.result.text()
    dialog.password.setText("admin-secret")
    dialog.unlock()
    assert dialog.tabs.isEnabled()
    for key, value in fields("n3r").items():
        dialog.n3r.fields[key].setText(value)
    dialog.n3r.save_row(False)
    assert dialog.n3r.table.rowCount() == 1
    dialog.n3r.search.setText("missing")
    assert dialog.n3r.table.rowCount() == 0
    dialog.n3r.search.setText("server-01")
    dialog.n3r.table.selectRow(0)
    dialog.n3r.fields["assignee"].setText("Other")
    dialog.n3r.save_row(True)
    assert store.load("n3r")[0]["assignee"] == "Other"
    dialog.close()


def test_admin_dialog_excel_import_runs_on_worker_and_reports_conflict(tmp_path, monkeypatch):
    app()
    auth, store, _ = setup(tmp_path)
    auth.set_initial_admin_password("admin-secret")
    admin = MappingAdmin(auth, store)
    dialog = AdminDialog(admin, ExcelImporter(store))
    dialog.password.setText("admin-secret")
    dialog.unlock()
    admin.save_row("n3r", fields("n3r"))
    workbook = Workbook()
    workbook.active.append(["server_name", "service_name", "purpose", "assignee"])
    workbook.active.append(["server-01", "Billing", "synthetic", "Other"])
    source = tmp_path / "import.xlsx"
    workbook.save(source)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(source), ""))
    monkeypatch.setattr(QMessageBox, "question", lambda *args: QMessageBox.No)
    dialog.n3r.start_import()
    assert not dialog.n3r.import_button.isEnabled()
    for _ in range(100):
        QTest.qWait(10)
        if dialog.n3r.import_button.isEnabled():
            break
    assert dialog.n3r.import_button.isEnabled()
    assert "충돌 1" in dialog.n3r.result.text()
    assert store.load("n3r")[0]["assignee"] == "Tester"
    dialog.close()


def test_settings_dialog_saves_fields_and_protected_token(tmp_path):
    app()
    auth, _, session = setup(tmp_path)
    settings = SettingsStore(auth, tmp_path / "settings")
    dialog = SettingsDialog(auth, session, settings)
    dialog.log_path.setText(str(tmp_path / "logs"))
    dialog.year_month.setChecked(False)
    dialog.assignee_name.setText("Tester")
    dialog.assignee_id.setText("jira-A")
    dialog.epic_options.setText("EPIC-1, EPIC-2")
    dialog.default_epic.setText("EPIC-2")
    dialog.watchers.setText("watcher-A")
    dialog.alarm_watchers.setPlainText("server-01 = watcher-B")
    dialog.reporter.setText("reporter-A")
    dialog.token.setText("synthetic-secret-token")
    dialog.save()
    assert "설정 저장 완료" in dialog.notice.text()
    assert settings.load(session).alarm_watchers == {"server-01": ("watcher-B",)}
    assert auth.get_token(session) == "synthetic-secret-token"
    assert "synthetic-secret-token" not in next((tmp_path / "settings").glob("*.json")).read_text(encoding="utf-8")
    dialog.close()
