"""Administrator-gated Grafana and N3R mapping tables and Excel imports."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QTabWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from src.core.auth_manager import AuthError
from src.core.crypto_store import StorageError
from src.core.excel_importer import DATA_FIELDS, ExcelImporter
from src.core.mapping_admin import MappingAdmin, MappingAdminError


class MappingTab(QWidget):
    def __init__(self, kind: str, admin: MappingAdmin, importer: ExcelImporter):
        super().__init__()
        self.kind, self.admin, self.importer = kind, admin, importer
        self.rows_data: list[dict] = []
        self.future = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("매핑 행 검색")
        layout.addWidget(self.search)
        self.table = QTableWidget(0, len(DATA_FIELDS[kind]) + 1)
        self.columns = (*DATA_FIELDS[kind], "jira_account_id")
        self.table.setHorizontalHeaderLabels(self.columns)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)
        form = QFormLayout()
        self.fields = {key: QLineEdit() for key in self.columns}
        for key, field in self.fields.items():
            form.addRow(key, field)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.add_button = QPushButton("행 추가")
        self.update_button = QPushButton("선택 행 수정")
        self.delete_button = QPushButton("선택 행 삭제")
        self.import_button = QPushButton("Excel 가져오기")
        for button in (self.add_button, self.update_button, self.delete_button, self.import_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.result = QLabel()
        self.result.setWordWrap(True)
        layout.addWidget(self.result)
        self.search.textChanged.connect(self.filter_rows)
        self.table.itemSelectionChanged.connect(self.show_selected)
        self.add_button.clicked.connect(lambda: self.save_row(False))
        self.update_button.clicked.connect(lambda: self.save_row(True))
        self.delete_button.clicked.connect(self.delete_row)
        self.import_button.clicked.connect(self.start_import)
        self.poll = QTimer(self)
        self.poll.timeout.connect(self.finish_import)

    def refresh(self):
        try:
            self.rows_data = self.admin.rows(self.kind)
        except (MappingAdminError, StorageError) as exc:
            self.result.setText(f"{exc.code}: {exc.action}")
            return
        self.filter_rows()

    def filter_rows(self):
        term = self.search.text().casefold()
        visible = [row for row in self.rows_data if term in " ".join(str(row.get(key, "")) for key in self.columns).casefold()]
        self.table.setRowCount(len(visible))
        for index, row in enumerate(visible):
            for column, key in enumerate(self.columns):
                cell = QTableWidgetItem(str(row.get(key) or ""))
                cell.setData(256, row["id"])
                self.table.setItem(index, column, cell)

    def selected_id(self) -> str | None:
        row = self.table.currentRow()
        cell = self.table.item(row, 0) if row >= 0 else None
        return cell.data(256) if cell else None

    def show_selected(self):
        row_id = self.selected_id()
        row = next((item for item in self.rows_data if item["id"] == row_id), None)
        if row:
            for key, field in self.fields.items():
                field.setText(str(row.get(key) or ""))

    def save_row(self, editing: bool):
        try:
            row_id = self.selected_id() if editing else None
            if editing and not row_id:
                raise MappingAdminError("ROW_NOT_SELECTED", "수정할 행을 선택하세요.")
            self.admin.save_row(self.kind, {key: field.text() for key, field in self.fields.items()}, row_id)
            self.result.setText("암호화 저장 완료")
            self.refresh()
        except (MappingAdminError, StorageError) as exc:
            self.result.setText(f"{exc.code}: {exc.action}")

    def delete_row(self):
        try:
            row_id = self.selected_id()
            if not row_id:
                raise MappingAdminError("ROW_NOT_SELECTED", "삭제할 행을 선택하세요.")
            if QMessageBox.question(self, "삭제 확인", "선택한 매핑 행을 삭제할까요?") != QMessageBox.Yes:
                return
            self.admin.delete_row(self.kind, row_id)
            self.result.setText("암호화 저장 완료")
            self.refresh()
        except (MappingAdminError, StorageError) as exc:
            self.result.setText(f"{exc.code}: {exc.action}")

    def start_import(self):
        try:
            self.admin._require()
        except MappingAdminError as exc:
            self.result.setText(f"{exc.code}: {exc.action}")
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Excel 선택", "", "Excel (*.xlsx *.xlsm)")
        if not filename:
            return
        self.import_button.setEnabled(False)
        self.result.setText("Excel 가져오기 진행 중")
        self.future = self.importer.submit_import(self.executor, Path(filename), self.kind)
        self.poll.start(50)

    def finish_import(self):
        if not self.future or not self.future.done():
            return
        self.poll.stop()
        self.import_button.setEnabled(True)
        try:
            result = self.future.result()
        except Exception:
            self.result.setText("EXCEL_IMPORT_FAILED: 파일과 저장 경로를 확인하세요.")
            return
        self.result.setText(f"{result.status}: 추가 {result.added}, 중복 {result.skipped}, "
                            f"충돌 {len(result.conflicts)}, 오류 {len(result.errors)} " +
                            ", ".join(issue.code for issue in result.errors))
        self.refresh()
        for conflict in result.conflicts:
            answer = QMessageBox.question(
                self, "매핑 충돌", f"{conflict.key}: 신규 행을 반영할까요?\n아니오: 기존 유지, 취소: 행별 결정 보류",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
            choice = {QMessageBox.Yes: "USE_INCOMING", QMessageBox.No: "KEEP_EXISTING"}.get(answer, "CANCEL")
            try:
                self.importer.resolve_conflict(self.kind, conflict, choice)
            except StorageError as exc:
                self.result.setText(f"{exc.code}: {exc.action}")
                break
        self.refresh()

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
        super().close()


class AdminDialog(QDialog):
    def __init__(self, admin: MappingAdmin, importer: ExcelImporter, parent=None):
        super().__init__(parent)
        self.admin = admin
        self.setWindowTitle("관리자 매핑 관리")
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("관리자 비밀번호")
        self.setup_button = QPushButton("최초 관리자 비밀번호 설정")
        self.unlock_button = QPushButton("관리자 승인")
        header.addWidget(self.password)
        header.addWidget(self.setup_button)
        header.addWidget(self.unlock_button)
        layout.addLayout(header)
        self.status = QLabel("관리자 승인 전에는 매핑을 수정할 수 없습니다.")
        layout.addWidget(self.status)
        self.tabs = QTabWidget()
        self.grafana = MappingTab("grafana", admin, importer)
        self.n3r = MappingTab("n3r", admin, importer)
        self.tabs.addTab(self.grafana, "Grafana")
        self.tabs.addTab(self.n3r, "N3R")
        self.tabs.setEnabled(False)
        layout.addWidget(self.tabs)
        self.setup_button.clicked.connect(self.setup_admin)
        self.unlock_button.clicked.connect(self.unlock)

    def setup_admin(self):
        try:
            self.admin.auth.set_initial_admin_password(self.password.text())
            self.status.setText("초기 관리자 비밀번호 저장 완료. 승인 버튼을 누르세요.")
        except AuthError as exc:
            self.status.setText(f"{exc.code}: {exc.action}")

    def unlock(self):
        try:
            approved = self.admin.approve(self.password.text())
        except AuthError as exc:
            self.status.setText(f"{exc.code}: {exc.action}")
            return
        self.tabs.setEnabled(approved)
        self.status.setText("관리자 승인됨" if approved else "관리자 비밀번호가 올바르지 않습니다.")
        if approved:
            self.grafana.refresh()
            self.n3r.refresh()

    def closeEvent(self, event):
        self.admin.lock()
        self.grafana.executor.shutdown(wait=False, cancel_futures=True)
        self.n3r.executor.shutdown(wait=False, cancel_futures=True)
        super().closeEvent(event)
