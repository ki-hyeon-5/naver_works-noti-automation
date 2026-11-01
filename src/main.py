"""Create the desktop application."""

import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from src.application.workflow import Workflow
from src.core.auth_manager import AuthManager
from src.core.crypto_store import CryptoStore, StorageError
from src.core.matcher import AssigneeIdentity, MappingMatcher
from src.core.settings_store import SettingsError, SettingsStore
from src.ui.auth_dialog import AuthDialog
from src.ui.main_window import MainWindow


class MockSender:
    """Local demonstration sender; it never contacts Jira."""

    def __init__(self):
        self.count = 0

    def __call__(self, request):
        self.count += 1
        return "DONE", f"MOCK-{self.count}"


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    auth = AuthManager()
    login = AuthDialog(auth)
    if login.exec() != AuthDialog.Accepted:
        return 0
    mapping_store = CryptoStore()
    settings_store = SettingsStore(auth)
    try:
        settings = settings_store.load(login.session)
        matcher = MappingMatcher.from_store(mapping_store)
    except (StorageError, SettingsError) as exc:
        QMessageBox.critical(None, exc.code, exc.action)
        return 1
    default = (AssigneeIdentity(settings.default_assignee_name, settings.default_assignee_account_id)
               if settings.default_assignee_account_id else None)
    window = MainWindow(Workflow(matcher=matcher, default_assignee=default, sender=MockSender()),
                        auth=auth, session=login.session, mapping_store=mapping_store,
                        settings_store=settings_store)
    window.show()
    return app.exec()
