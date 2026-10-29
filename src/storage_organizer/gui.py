"""Optional PySide6 desktop interface. Install with: pip install .[gui]."""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

# On some GNOME/Wayland installations, Qt's auto-selected desktop theme plugin
# crashes when a legacy xsettings schema key is missing. Use Qt's generic theme
# by default on Linux; respect an explicit user override.
if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORMTHEME", "generic")

try:
    from PySide6.QtCore import QObject, QThread, Signal
    from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QFormLayout, QHBoxLayout,
        QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QProgressBar, QTextEdit,
        QVBoxLayout, QWidget)
except ImportError as exc:  # pragma: no cover - exercised only without optional GUI dependency
    raise SystemExit("The GUI requires PySide6. Install it with: python -m pip install 'storage-organizer[gui]'") from exc

from .organizer import create_plan, organize
from .logging_setup import setup_logging
from .preferences import load_preferences, save_preferences


class Worker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(self, sources: list[Path], destination: Path, preview: bool, cancel_event: threading.Event):
        super().__init__()
        self.sources, self.destination, self.preview = sources, destination, preview
        self.cancel_event = cancel_event

    def run(self):
        try:
            if self.preview:
                plan, _, _, _ = create_plan(self.sources, self.destination)
                self.finished.emit(None, plan)
            else:
                logger = setup_logging()
                summary, plan = organize(self.sources, self.destination, logger=logger, cancel_event=self.cancel_event,
                    progress=lambda done, total, item, summary: self.progress.emit(done, total, item.source.name))
                self.finished.emit(summary, plan)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Storage Organizer")
        self.resize(850, 620)
        self.sources: list[Path] = []
        preferences = load_preferences()
        if preferences.get("source") and Path(preferences["source"]).is_dir():
            self.sources = [Path(preferences["source"])]
        if preferences.get("destination"):
            self.destination_initial = preferences["destination"]
        else:
            self.destination_initial = ""
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self.cancel_event = threading.Event()
        central = QWidget()
        layout = QVBoxLayout(central)
        form = QFormLayout()
        self.source_label = QLabel(str(self.sources[0]) if self.sources else "No source selected")
        source_button = QPushButton("Select drive/folder(s)…")
        source_button.clicked.connect(self.select_sources)
        source_row = QHBoxLayout(); source_row.addWidget(self.source_label, 1); source_row.addWidget(source_button)
        form.addRow("Source", source_row)
        self.destination_edit = QLineEdit(self.destination_initial)
        dest_button = QPushButton("Browse…")
        dest_button.clicked.connect(self.select_destination)
        dest_row = QHBoxLayout(); dest_row.addWidget(self.destination_edit, 1); dest_row.addWidget(dest_button)
        form.addRow("Destination root", dest_row)
        layout.addLayout(form)
        self.verify_checkbox = QCheckBox("Verify copied files using SHA-256")
        self.verify_checkbox.setChecked(True)
        self.verify_checkbox.setEnabled(False)  # verification is intentionally mandatory in v1
        layout.addWidget(self.verify_checkbox)
        buttons = QHBoxLayout()
        self.preview_button = QPushButton("Preview plan")
        self.preview_button.clicked.connect(lambda: self.start_job(True))
        self.organize_button = QPushButton("Copy and organize")
        self.organize_button.clicked.connect(lambda: self.start_job(False))
        self.cancel_button = QPushButton("Cancel after current file")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_job)
        buttons.addWidget(self.preview_button); buttons.addWidget(self.organize_button); buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.progress = QProgressBar(); self.progress.setRange(0, 100)
        layout.addWidget(self.progress)
        self.output = QTextEdit(); self.output.setReadOnly(True)
        layout.addWidget(self.output, 1)
        self.setCentralWidget(central)

    def select_sources(self):
        folder = QFileDialog.getExistingDirectory(self, "Select source folder or mounted drive")
        if folder:
            self.sources = [Path(folder)]
            self.source_label.setText(folder)
            save_preferences(source=folder)

    def select_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select destination root")
        if folder:
            self.destination_edit.setText(folder)
            save_preferences(destination=folder)

    def start_job(self, preview: bool):
        if not self.sources or not self.destination_edit.text().strip():
            QMessageBox.warning(self, "Missing paths", "Select a source and destination first.")
            return
        if not preview:
            answer = QMessageBox.question(self, "Confirm copy", "Copy files to the selected destination? Original files will remain untouched.")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.preview_button.setEnabled(False); self.organize_button.setEnabled(False)
        self.cancel_button.setEnabled(not preview)
        self.output.clear(); self.progress.setValue(0)
        self.cancel_event.clear()
        self.thread = QThread(self)
        self.worker = Worker(self.sources, Path(self.destination_edit.text().strip()), preview, self.cancel_event)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.restore_buttons)
        self.thread.start()

    def cancel_job(self):
        self.cancel_event.set()
        self.output.append("Cancellation requested; the current file will finish safely.")
        self.cancel_button.setEnabled(False)

    def on_progress(self, done: int, total: int, filename: str):
        self.progress.setValue(int(done * 100 / max(total, 1)))
        self.output.append(f"[{done}/{total}] {filename}")

    def on_finished(self, summary, plan):
        if summary is None:
            self.output.append(f"Preview: {len(plan)} files")
            for item in plan:
                self.output.append(f"[{item.action}] {item.source} → {item.destination} — {item.reason}")
        else:
            status = "Cancelled" if summary.cancelled else "Complete"
            self.output.append(f"{status} — copied {summary.copied}, skipped {summary.skipped_identical}, failed {summary.failed}")
            for error in summary.errors or []:
                self.output.append(error)
        self.progress.setValue(100)

    def on_failed(self, message: str):
        self.output.append(f"ERROR: {message}")
        QMessageBox.critical(self, "Operation failed", message)

    def restore_buttons(self):
        self.preview_button.setEnabled(True); self.organize_button.setEnabled(True); self.cancel_button.setEnabled(False)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(); window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
