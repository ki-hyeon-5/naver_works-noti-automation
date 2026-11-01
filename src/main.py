"""Create the desktop application."""

import sys
from PySide6.QtWidgets import QApplication
from src.application.workflow import Workflow
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
    window = MainWindow(Workflow(sender=MockSender()))
    window.show()
    return app.exec()
