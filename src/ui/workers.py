"""Run Jira submissions off the Qt event loop and report results by signal."""

from PySide6.QtCore import QObject, Signal, Slot


class SubmissionWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, workflow, indices: list[int]) -> None:
        super().__init__()
        self.workflow, self.indices = workflow, indices

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self.workflow.submit(self.indices))
        except Exception:
            self.failed.emit("등록 상태를 확인할 수 없습니다. 장부와 Jira를 수동 대조하세요.")
