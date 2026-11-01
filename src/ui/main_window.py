"""Single review mode GUI with explicit registration and offline help controls."""

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl
from PySide6.QtGui import QAction, QShortcut, QKeySequence, QDesktopServices
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QMessageBox, QPushButton, QRadioButton,
                               QSplitter, QVBoxLayout, QWidget)

from src.application.workflow import Workflow
from src.core.formatter import noti_body
from src.core.matcher import AssigneeIdentity
from src.core.crypto_store import StorageError
from src.core.excel_importer import ExcelImporter
from src.core.mapping_admin import MappingAdmin
from src.core.matcher import MappingMatcher
from src.core.settings_store import SettingsError
from .admin_dialog import AdminDialog
from .settings_dialog import SettingsDialog
from .widgets.alarm_input_pane import AlarmInputPane
from .widgets.noti_review_pane import NotiReviewPane
from .workers import SubmissionWorker


class MainWindow(QMainWindow):
    def __init__(self, workflow: Workflow | None = None, *, auth=None, session=None,
                 mapping_store=None, settings_store=None, async_submission=False):
        super().__init__()
        self.workflow = workflow or Workflow()
        self.auth, self.session = auth, session
        self.mapping_store, self.settings_store = mapping_store, settings_store
        self.async_submission = async_submission
        self._submit_thread = None
        self.setWindowTitle("Noti Automation — 확인 후 등록")
        self.resize(1100, 740)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        self.input = AlarmInputPane()
        outer.addWidget(self.input)
        split = QSplitter(Qt.Horizontal)
        self.list = QListWidget()
        self.review = NotiReviewPane()
        split.addWidget(self.list)
        split.addWidget(self.review)
        outer.addWidget(split, 1)
        controls = QHBoxLayout()
        self.individual = QRadioButton("개별 등록")
        self.bundle = QRadioButton("묶음 등록")
        self.individual.setChecked(True)
        self.save_review = QPushButton("수정·검토 저장")
        self.review_all = QPushButton("전체 검토")
        self.confirm_group = QPushButton("묶음 구성 확인")
        self.register_one = QPushButton("선택 등록")
        self.register_all = QPushButton("전체 등록")
        for button in (self.individual, self.bundle, self.save_review, self.review_all,
                       self.confirm_group, self.register_one, self.register_all):
            controls.addWidget(button)
        outer.addLayout(controls)
        self.notice = QLabel("Mock Jira 검토 화면입니다. 실서버 연결은 제공하지 않습니다." if self.workflow.sender else
                             "Jira 연결은 아직 설정되지 않았습니다. 실서버 등록은 Task 7에서 연결합니다.")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        help_menu = self.menuBar().addMenu("도움말")
        manual_action = QAction("사용설명서 열기", self)
        help_menu.addAction(manual_action)
        manual_action.triggered.connect(self.open_manual)
        self.input.parse_button.clicked.connect(self.parse)
        self.list.currentRowChanged.connect(self.select)
        self.save_review.clicked.connect(self.save_current)
        self.review_all.clicked.connect(self.mark_all)
        self.individual.toggled.connect(lambda checked: self.change_mode(False) if checked else None)
        self.bundle.toggled.connect(lambda checked: self.change_mode(True) if checked else None)
        self.confirm_group.clicked.connect(self.confirm_groups)
        self.register_one.clicked.connect(lambda: self.register(False))
        self.register_all.clicked.connect(lambda: self.register(True))
        self.shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        self.shortcut.activated.connect(lambda: self.register(False))
        if auth and session and mapping_store and settings_store:
            menu = self.menuBar().addMenu("관리")
            admin_action = QAction("관리자 매핑", self)
            settings_action = QAction("사용자 설정", self)
            menu.addAction(admin_action)
            menu.addAction(settings_action)
            admin_action.triggered.connect(self.open_admin)
            settings_action.triggered.connect(self.open_settings)

    @staticmethod
    def manual_path() -> Path:
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        return root / "docs" / "manual" / "index.html"

    def open_manual(self):
        path = self.manual_path()
        if not path.is_file() or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "사용설명서 열기 실패", f"로컬 매뉴얼을 열 수 없습니다: {path}")

    def open_admin(self):
        dialog = AdminDialog(MappingAdmin(self.auth, self.mapping_store),
                             ExcelImporter(self.mapping_store), self)
        dialog.exec()
        try:
            self.workflow.matcher = MappingMatcher.from_store(self.mapping_store)
            self.notice.setText("매핑을 다시 읽었습니다. 기존 입력은 알람 분석을 다시 실행해 매칭하세요.")
        except StorageError as exc:
            self.notice.setText(f"{exc.code}: {exc.action}")

    def open_settings(self):
        dialog = SettingsDialog(self.auth, self.session, self.settings_store, self)
        dialog.exec()
        try:
            saved = self.settings_store.load(self.session)
            self.workflow.default_assignee = (AssigneeIdentity(saved.default_assignee_name,
                                                       saved.default_assignee_account_id)
                                              if saved.default_assignee_account_id else None)
            if hasattr(self.workflow.sender, "settings"):
                self.workflow.sender.settings = saved
        except SettingsError as exc:
            self.notice.setText(f"{exc.code}: {exc.action}")

    def parse(self):
        batch = self.workflow.load(self.input.raw.toPlainText())
        self.input.show_batch(batch)
        self.list.clear()
        for index, item in enumerate(self.workflow.items):
            self.list.addItem(f"{index + 1}. {item.alarm.target} · {item.alarm.alert_name}")
        if self.workflow.items:
            self.list.setCurrentRow(0)
        parts = []
        if batch.no_data_count:
            parts.append(f"NoData {batch.no_data_count}건 제외: {batch.no_data_reasons}")
        if batch.errors:
            parts.append(f"파싱 실패 {len(batch.errors)}건: 필드 경계를 확인하세요.")
        self.notice.setText(" / ".join(parts) or "분석 완료")

    def select(self, index):
        if 0 <= index < len(self.workflow.items):
            self.review.show_item(self.workflow.items[index])
            self.show_reasons(index)

    def save_current(self):
        index = self.list.currentRow()
        if index < 0:
            return
        pane = self.review
        item = self.workflow.items[index]
        old_values = (item.alarm.target, item.alarm.detail,
                      item.alarm.start_at.strftime("%Y-%m-%d %H:%M:%S") if item.alarm.start_at else item.alarm.raw_fields.get("start_at", ""),
                      item.alarm.cluster or "")
        values = (pane.target.text(), pane.detail.text(), pane.start_at.text(), pane.cluster.text())
        body_before = pane.body.toPlainText()
        old_generated_body = noti_body(item.alarm)
        if values != old_values:
            self.workflow.correct(index, target=values[0], detail=values[1], start_at=values[2], cluster=values[3])
        item = self.workflow.items[index]
        tag = pane.source.text().strip().upper() or None
        account = pane.account_id.text().strip()
        if account and (not item.assignee or account != item.assignee.jira_account_id or tag != item.source_tag):
            try:
                self.workflow.select_assignee(index, AssigneeIdentity(account, account), tag)
            except ValueError as exc:
                self.notice.setText(str(exc))
                return
        item.body = item.body if values != old_values and body_before == old_generated_body else body_before
        self.workflow.set_reviewed(index, pane.reviewed.isChecked())
        self.show_reasons(index)

    def mark_all(self):
        self.save_current()
        for index in range(len(self.workflow.items)):
            if not any(reason for reason in self.workflow.reasons(index) if reason not in ("REVIEW_REQUIRED", "JIRA_CONNECTION_UNAVAILABLE")):
                self.workflow.set_reviewed(index, True)
        self.select(self.list.currentRow())

    def change_mode(self, bundled):
        self.workflow.set_bundled(bundled)
        self.notice.setText("묶음 구성 변경: 미리보기 후 다시 확인하세요." if bundled else "개별 등록 모드")

    def confirm_groups(self):
        plan = self.workflow.groups()
        self.workflow.group_confirmed = True
        self.notice.setText("묶음 구성 확인: " + ", ".join(
            "+".join(str(self.workflow.items.index(next(item for item in self.workflow.items if item.alarm is member.alarm)) + 1)
                     for member in group.members) for group in plan.groups))

    def show_reasons(self, index):
        item = self.workflow.items[index]
        reasons = self.workflow.reasons(index)
        self.review.reason.setText(("등록 차단: " + ", ".join(reasons) if reasons else "등록 가능") +
                                   ("\n" + item.action if item.action else ""))

    def register(self, all_items):
        if self._submit_thread is not None:
            return
        self.save_current()
        index = self.list.currentRow()
        if not all_items and index < 0:
            return
        indices = list(range(len(self.workflow.items))) if all_items else [index]
        for i in indices:
            if "DUPLICATE_CONFIRM_REQUIRED" in self.workflow.reasons(i):
                answer = QMessageBox.question(self, "중복 재등록 확인", f"{i + 1}번 알람을 다시 등록할까요?")
                if answer == QMessageBox.Yes:
                    self.workflow.items[i].duplicate_confirmed = True
        if self.async_submission:
            self._submit_thread = QThread(self)
            self._submit_worker = SubmissionWorker(self.workflow, indices)
            self._submit_worker.moveToThread(self._submit_thread)
            self._submit_thread.started.connect(self._submit_worker.run)
            self._submit_worker.finished.connect(lambda result: self._submission_finished(result, index))
            self._submit_worker.failed.connect(self.notice.setText)
            self._submit_worker.finished.connect(self._submit_thread.quit)
            self._submit_worker.failed.connect(self._submit_thread.quit)
            self._submit_thread.finished.connect(self._submit_worker.deleteLater)
            self._submit_thread.finished.connect(self._submission_thread_done)
            for button in (self.register_one, self.register_all, self.input.parse_button,
                           self.save_review, self.review_all):
                button.setEnabled(False)
            self.notice.setText("Mock Jira 요청 중…")
            self._submit_thread.start()
            return
        self._submission_finished(self.workflow.submit(indices), index)

    def _submission_finished(self, result, index):
        for i, item in enumerate(self.workflow.items):
            self.list.item(i).setText(f"{i + 1}. {item.alarm.target} · {item.status} · {item.jira_key or '-'}")
        self.notice.setText(f"Mock 요청 {len(result.submitted)}건 · 차단 {len(result.blocked)}건: {result.blocked}")
        self.select(index)

    def _submission_thread_done(self):
        self._submit_thread.deleteLater()
        self._submit_thread = None
        self._submit_worker = None
        for button in (self.register_one, self.register_all, self.input.parse_button,
                       self.save_review, self.review_all):
            button.setEnabled(True)
