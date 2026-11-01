"""Login, registration, and accepted-risk password reset dialog."""

from PySide6.QtWidgets import (QDialog, QFormLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from src.core.auth_manager import AuthError, AuthManager, RESET_RISK_WARNING


def _password() -> QLineEdit:
    field = QLineEdit()
    field.setEchoMode(QLineEdit.Password)
    return field


class AuthDialog(QDialog):
    def __init__(self, auth: AuthManager, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.session = None
        self.setWindowTitle("Noti Automation 계정")
        self.resize(470, 320)
        outer = QVBoxLayout(self)
        tabs = QTabWidget()
        outer.addWidget(tabs)
        login = QWidget()
        form = QFormLayout(login)
        self.login_id, self.login_password = QLineEdit(), _password()
        form.addRow("ID", self.login_id)
        form.addRow("비밀번호", self.login_password)
        login_button = QPushButton("로그인")
        login_button.clicked.connect(self.login)
        form.addRow(login_button)
        tabs.addTab(login, "로그인")

        signup = QWidget()
        form = QFormLayout(signup)
        self.signup_id, self.signup_name, self.signup_password = QLineEdit(), QLineEdit(), _password()
        for label, field in (("ID", self.signup_id), ("이름", self.signup_name),
                             ("비밀번호", self.signup_password)):
            form.addRow(label, field)
        signup_button = QPushButton("회원가입")
        signup_button.clicked.connect(self.signup)
        form.addRow(signup_button)
        tabs.addTab(signup, "회원가입")

        reset = QWidget()
        form = QFormLayout(reset)
        self.reset_id, self.reset_password = QLineEdit(), _password()
        form.addRow("ID", self.reset_id)
        form.addRow("새 비밀번호", self.reset_password)
        warning = QLabel(RESET_RISK_WARNING)
        warning.setWordWrap(True)
        form.addRow(warning)
        reset_button = QPushButton("ID로 비밀번호 재설정")
        reset_button.clicked.connect(self.reset)
        form.addRow(reset_button)
        tabs.addTab(reset, "비밀번호 재설정")

    def login(self):
        try:
            self.session = self.auth.login(self.login_id.text().strip(), self.login_password.text())
        except AuthError as exc:
            QMessageBox.warning(self, exc.code, exc.action)
            return
        self.accept()

    def signup(self):
        try:
            self.auth.register(self.signup_id.text().strip(), self.signup_password.text(),
                               self.signup_name.text().strip())
        except AuthError as exc:
            QMessageBox.warning(self, exc.code, exc.action)
            return
        QMessageBox.information(self, "가입 완료", "로그인 탭에서 새 계정으로 로그인하세요.")

    def reset(self):
        if QMessageBox.question(self, "위험 확인", RESET_RISK_WARNING + " 계속할까요?") != QMessageBox.Yes:
            return
        try:
            self.auth.reset_password(self.reset_id.text().strip(), self.reset_password.text())
        except AuthError as exc:
            QMessageBox.warning(self, exc.code, exc.action)
            return
        QMessageBox.information(self, "재설정 완료", "개인 Jira 토큰이 삭제되었습니다. 다시 로그인하세요.")
