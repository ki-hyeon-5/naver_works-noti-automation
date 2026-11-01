"""Create the desktop application."""

import sys
from PySide6.QtWidgets import QApplication, QMessageBox
from src.application.workflow import Workflow
from src.core.auth_manager import AuthManager
from src.core.crypto_store import CryptoStore, StorageError
from src.core.matcher import AssigneeIdentity, MappingMatcher
from src.core.settings_store import SettingsError, SettingsStore
from src.core.jira_client import JiraClient, MockJiraAdapter, draft_from_submission
from src.core.registration_journal import RegistrationJournal
from src.ui.auth_dialog import AuthDialog
from src.ui.main_window import MainWindow


class MockSender:
    """Translate reviewed submissions into persistent Mock attempts."""

    def __init__(self, client: JiraClient, settings):
        self.client, self.settings = client, settings

    def blocking_reason(self, keys):
        return self.client.blocking_reason(keys)

    def __call__(self, request):
        result = self.client.register(draft_from_submission(request, self.settings))
        self.last_result = result
        return result.status, result.issue_key


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
    client = JiraClient(MockJiraAdapter(), RegistrationJournal())
    window = MainWindow(Workflow(matcher=matcher, default_assignee=default,
                                 sender=MockSender(client, settings)),
                        auth=auth, session=login.session, mapping_store=mapping_store,
                        settings_store=settings_store, async_submission=True)
    window.show()
    return app.exec()
