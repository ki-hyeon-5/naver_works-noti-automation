"""Structured corrections and editable Noti review controls."""

from PySide6.QtWidgets import (QCheckBox, QFormLayout, QGroupBox, QLabel,
                               QLineEdit, QPlainTextEdit, QVBoxLayout)


class NotiReviewPane(QGroupBox):
    def __init__(self):
        super().__init__("노티 검토")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.target = QLineEdit()
        self.detail = QLineEdit()
        self.start_at = QLineEdit()
        self.start_at.setPlaceholderText("YYYY-MM-DD HH:MM:SS")
        self.cluster = QLineEdit()
        self.account_id = QLineEdit()
        self.account_id.setPlaceholderText("확인된 Jira accountId")
        self.source = QLineEdit()
        self.source.setPlaceholderText("GRAFANA / N3R / 빈 값")
        for label, widget in (("Target", self.target), ("장애현상", self.detail),
                              ("Start At", self.start_at), ("클러스터", self.cluster),
                              ("Jira accountId", self.account_id), ("출처 태그", self.source)):
            form.addRow(label, widget)
        layout.addLayout(form)
        self.body = QPlainTextEdit()
        self.body.setPlaceholderText("노티 본문을 확인하고 수정하세요. Enter는 줄바꿈입니다.")
        layout.addWidget(self.body)
        self.reviewed = QCheckBox("이 알람 검토 완료")
        self.reason = QLabel()
        self.reason.setWordWrap(True)
        layout.addWidget(self.reviewed)
        layout.addWidget(self.reason)

    def show_item(self, item):
        self.target.setText(item.alarm.target)
        self.detail.setText(item.alarm.detail)
        self.start_at.setText(item.alarm.start_at.strftime("%Y-%m-%d %H:%M:%S") if item.alarm.start_at else item.alarm.raw_fields.get("start_at", ""))
        self.cluster.setText(item.alarm.cluster or "")
        self.account_id.setText(item.assignee.jira_account_id if item.assignee else "")
        self.source.setText(item.source_tag or "")
        self.body.setPlainText(item.body)
        self.reviewed.setChecked(item.reviewed)
