"""Per-user log, Jira Mock options, watchers, and protected token settings."""

from PySide6.QtWidgets import (QCheckBox, QDialog, QFormLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from src.core.auth_manager import AuthError, AuthManager, Session
from src.core.settings_store import SettingsError, SettingsStore, UserSettings


def _csv(text: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in text.split(",") if part.strip())


class SettingsDialog(QDialog):
    def __init__(self, auth: AuthManager, session: Session, store: SettingsStore, parent=None):
        super().__init__(parent)
        self.auth, self.session, self.store = auth, session, store
        self.setWindowTitle("사용자 설정")
        self.resize(650, 630)
        outer = QVBoxLayout(self)
        form = QFormLayout()
        self.log_path = QLineEdit()
        self.year_month = QCheckBox("연/월 폴더 생성")
        self.assignee_name = QLineEdit()
        self.assignee_id = QLineEdit()
        self.epic_options = QLineEdit()
        self.default_epic = QLineEdit()
        self.watchers = QLineEdit()
        self.alarm_watchers = QPlainTextEdit()
        self.alarm_watchers.setPlaceholderText("알람 키 = accountId1, accountId2 (줄마다 하나)")
        self.reporter = QLineEdit()
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("변경할 때만 입력; 기존 토큰은 표시하지 않음")
        for label, widget in (("로그 경로", self.log_path), ("자동 폴더", self.year_month),
                              ("기본 담당자 이름", self.assignee_name), ("기본 Jira accountId", self.assignee_id),
                              ("에픽 목록 (쉼표 구분)", self.epic_options), ("기본 에픽", self.default_epic),
                              ("기본 참조자 accountId", self.watchers),
                              ("알람별 참조자", self.alarm_watchers), ("보고자 accountId", self.reporter),
                              ("개인 Jira 토큰", self.token)):
            form.addRow(label, widget)
        outer.addLayout(form)
        self.notice = QLabel("Jira 필드 스키마 미검증: 설정은 저장되지만 실서버 전송은 하지 않습니다.")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        self.save_button = QPushButton("설정 저장")
        outer.addWidget(self.save_button)
        self.save_button.clicked.connect(self.save)
        self.load()

    def load(self):
        try:
            settings = self.store.load(self.session)
        except SettingsError as exc:
            self.notice.setText(f"{exc.code}: {exc.action}")
            self.save_button.setEnabled(False)
            return
        self.log_path.setText(settings.log_base_path)
        self.year_month.setChecked(settings.auto_year_month_folder)
        self.assignee_name.setText(settings.default_assignee_name)
        self.assignee_id.setText(settings.default_assignee_account_id)
        self.epic_options.setText(", ".join(settings.epic_options))
        self.default_epic.setText(settings.default_epic)
        self.watchers.setText(", ".join(settings.default_watchers))
        self.alarm_watchers.setPlainText("\n".join(
            f"{key} = {', '.join(value)}" for key, value in settings.alarm_watchers.items()))
        self.reporter.setText(settings.reporter_account_id)

    def _overrides(self) -> dict[str, tuple[str, ...]]:
        overrides = {}
        for line in self.alarm_watchers.toPlainText().splitlines():
            if not line.strip():
                continue
            if "=" not in line:
                raise SettingsError("INVALID_WATCHERS", "알람별 참조자는 '알람 키 = accountId' 형식으로 입력하세요.")
            key, accounts = (part.strip() for part in line.split("=", 1))
            if not key or not _csv(accounts) or key in overrides:
                raise SettingsError("INVALID_WATCHERS", "알람 키와 참조자를 확인하고 중복 키를 제거하세요.")
            overrides[key] = _csv(accounts)
        return overrides

    def save(self):
        try:
            settings = UserSettings(
                log_base_path=self.log_path.text().strip(),
                auto_year_month_folder=self.year_month.isChecked(),
                default_assignee_name=self.assignee_name.text().strip(),
                default_assignee_account_id=self.assignee_id.text().strip(),
                epic_options=_csv(self.epic_options.text()),
                default_epic=self.default_epic.text().strip(),
                default_watchers=_csv(self.watchers.text()),
                alarm_watchers=self._overrides(),
                reporter_account_id=self.reporter.text().strip(),
            )
            self.store.save(self.session, settings)
        except SettingsError as exc:
            self.notice.setText(f"{exc.code}: {exc.action}")
            return
        if self.token.text():
            try:
                self.auth.store_token(self.session, self.token.text())
                self.token.clear()
            except AuthError as exc:
                self.notice.setText(f"설정은 저장되었지만 토큰 저장 실패 ({exc.code}): {exc.action}")
                return
        self.notice.setText("설정 저장 완료 · Jira 필드는 Mock 상태입니다.")
