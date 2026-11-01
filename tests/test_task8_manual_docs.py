"""TC-08A/B: offline manual structure, packaged assets and live GUI labels."""

import os
import re
from html.parser import HTMLParser
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src.application.workflow import Workflow
from src.core.matcher import DuplicateDetector
from src.ui.main_window import MainWindow


ROOT = Path(__file__).resolve().parents[1]
MANUAL = ROOT / "docs" / "manual"


class ManualParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sections = []
        self.ids = set()
        self.links = []
        self.assets = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "section" and "manual-section" in attrs.get("class", "").split():
            self.sections.append(attrs.get("id"))
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag == "link":
            self.assets.append(attrs.get("href", ""))
        if tag == "script":
            self.scripts.append(attrs.get("src", ""))


def test_tc08a_eight_local_sections_and_search_without_network():
    html = (MANUAL / "index.html").read_text(encoding="utf-8")
    parser = ManualParser()
    parser.feed(html)
    assert parser.sections == ["overview", "account", "parsing", "format", "workflow",
                               "mapping", "excel", "settings"]
    assert "manual-search" in parser.ids and "search-count" in parser.ids
    assert {f"#{section}" for section in parser.sections}.issubset(parser.links)
    assert parser.assets == ["assets/style.css"]
    assert parser.scripts == ["assets/manual.js"]
    for relative in parser.assets + parser.scripts:
        assert (MANUAL / relative).is_file()
    all_text = "\n".join((html, *(p.read_text(encoding="utf-8") for p in (MANUAL / "assets").iterdir())))
    assert not re.search(r"https?://|//[^/]|@import|fetch\s*\(|XMLHttpRequest", all_text, re.I)
    js = (MANUAL / "assets" / "manual.js").read_text(encoding="utf-8")
    assert 'search.addEventListener("input", filterSections)' in js
    assert "section.hidden = !match" in js and "empty.hidden = visible !== 0" in js


def test_tc08b_current_gui_labels_and_mock_limits_are_documented(tmp_path):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(Workflow(duplicate_detector=DuplicateDetector(tmp_path)))
    html = (MANUAL / "index.html").read_text(encoding="utf-8")
    for widget in (window.save_review, window.review_all, window.confirm_group,
                   window.register_one, window.register_all, window.individual,
                   window.bundle, window.input.parse_button):
        assert widget.text() in html
    assert all(label in html for label in ("Target", "장애현상", "Start At", "클러스터",
                                           "Jira accountId", "출처 태그", "NoData", "SCP",
                                           "UNKNOWN", "PARTIAL_FAILED", "MOCK-"))
    assert window.manual_path() == MANUAL / "index.html"
    help_menu = next(action.menu() for action in window.menuBar().actions() if action.text() == "도움말")
    assert [action.text() for action in help_menu.actions()] == ["사용설명서 열기"]
    window.close()


def test_packaging_includes_offline_manual_directory():
    spec = (ROOT / "packaging" / "noti-automation.spec").read_text(encoding="utf-8")
    assert 'project_root / "docs" / "manual"' in spec
    assert '"docs/manual"' in spec
