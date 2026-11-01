"""Raw Grafana input and batch statistics widget."""

from PySide6.QtWidgets import QGroupBox, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout


class AlarmInputPane(QGroupBox):
    def __init__(self):
        super().__init__("Grafana 알람 입력")
        layout = QVBoxLayout(self)
        self.raw = QPlainTextEdit()
        self.raw.setPlaceholderText("Grafana 테이블에서 복사한 원문을 붙여넣으세요.")
        self.parse_button = QPushButton("알람 분석")
        self.stats = QLabel("입력 0건 · 검토 0건 · NoData 제외 0건 · 파싱 실패 0건")
        layout.addWidget(self.raw)
        layout.addWidget(self.parse_button)
        layout.addWidget(self.stats)

    def show_batch(self, batch):
        self.stats.setText(
            f"입력 {batch.total_records}건 · 검토 {len(batch.alarms)}건 · "
            f"NoData 제외 {batch.no_data_count}건 · 파싱 실패 {len(batch.errors)}건"
        )
