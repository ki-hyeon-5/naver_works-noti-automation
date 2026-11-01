"""Single review mode GUI with explicit registration controls."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QListWidget,
                               QMainWindow, QMessageBox, QPushButton, QRadioButton,
                               QSplitter, QVBoxLayout, QWidget)

from src.application.workflow import Workflow
from src.core.formatter import noti_body
from src.core.matcher import AssigneeIdentity
from .widgets.alarm_input_pane import AlarmInputPane
from .widgets.noti_review_pane import NotiReviewPane


class MainWindow(QMainWindow):
    def __init__(self, workflow: Workflow | None = None):
        super().__init__()
        self.workflow = workflow or Workflow()
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
        self.review.reason.setText("등록 차단: " + ", ".join(self.workflow.reasons(index)) if self.workflow.reasons(index) else "등록 가능")

    def register(self, all_items):
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
        result = self.workflow.submit(indices)
        for i, item in enumerate(self.workflow.items):
            self.list.item(i).setText(f"{i + 1}. {item.alarm.target} · {item.status} · {item.jira_key or '-'}")
        self.notice.setText(f"Mock 요청 {len(result.submitted)}건 · 차단 {len(result.blocked)}건: {result.blocked}")
        self.select(index)
