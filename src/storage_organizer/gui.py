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
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:
    if exc.name == "PySide6" or (
        exc.name and exc.name.startswith("PySide6.")
    ):
        raise SystemExit(
            "The GUI requires PySide6. Install it with: "
            "python -m pip install 'storage-organizer[gui]'"
        ) from exc
    raise

from .organizer import create_plan, organize
from .logging_setup import setup_logging
from .preferences import load_preferences, save_preferences


class Worker(QObject):
    plan_ready = Signal(object)
    file_updated = Signal(object, int, int)
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
                self.plan_ready.emit(plan)
                self.finished.emit(None, plan)
            else:
                logger = setup_logging()
                summary, plan = organize(
                    self.sources,
                    self.destination,
                    logger=logger,
                    cancel_event=self.cancel_event,
                    plan_ready=self.plan_ready.emit,
                    file_progress=lambda result, done, total, _summary: self.file_updated.emit(
                        result, done, total
                    ),
                )
                self.finished.emit(summary, plan)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Storage Organizer")
        self.resize(1100, 720)
        self.sources: list[Path] = []
        self._file_rows: dict[str, int] = {}
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
        source_row = QHBoxLayout()
        source_row.addWidget(self.source_label, 1)
        source_row.addWidget(source_button)
        form.addRow("Source", source_row)

        self.destination_edit = QLineEdit(self.destination_initial)
        dest_button = QPushButton("Browse…")
        dest_button.clicked.connect(self.select_destination)
        dest_row = QHBoxLayout()
        dest_row.addWidget(self.destination_edit, 1)
        dest_row.addWidget(dest_button)
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
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.organize_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["File", "Source", "Destination", "Status", "Details"]
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setWordWrap(False)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setColumnWidth(0, 180)
        self.results_table.setColumnWidth(1, 260)
        self.results_table.setColumnWidth(2, 300)
        self.results_table.setColumnWidth(3, 100)
        layout.addWidget(self.results_table, 1)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(110)
        layout.addWidget(self.output)
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
            answer = QMessageBox.question(
                self,
                "Confirm copy",
                "Copy files to the selected destination? Original files will remain untouched.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.preview_button.setEnabled(False)
        self.organize_button.setEnabled(False)
        self.cancel_button.setEnabled(not preview)
        self.output.clear()
        self.results_table.setRowCount(0)
        self._file_rows.clear()
        self.progress.setValue(0)
        self.cancel_event.clear()

        self.thread = QThread(self)
        self.worker = Worker(
            self.sources,
            Path(self.destination_edit.text().strip()),
            preview,
            self.cancel_event,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.plan_ready.connect(self.on_plan_ready)
        self.worker.file_updated.connect(self.on_file_updated)
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

    def on_plan_ready(self, plan):
        self.results_table.setRowCount(len(plan))
        self._file_rows.clear()
        for row, planned_file in enumerate(plan):
            if planned_file.action == "copy":
                status = "Pending"
            elif planned_file.action == "error":
                status = "Error"
            elif planned_file.skip_reason == "source_duplicate":
                status = "Duplicate"
            else:
                status = "Skipped"

            values = (
                planned_file.source.name,
                str(planned_file.source),
                str(planned_file.destination),
                status,
                planned_file.reason,
            )
            for column, value in enumerate(values):
                self.results_table.setItem(row, column, QTableWidgetItem(value))
            self._file_rows[str(planned_file.source)] = row
        self.results_table.resizeRowsToContents()

    def on_file_updated(self, file_result, done: int, total: int):
        self.progress.setValue(int(done * 100 / max(total, 1)))
        row = self._file_rows.get(str(file_result.source))
        if row is None:
            return
        status_item = self.results_table.item(row, 3)
        details_item = self.results_table.item(row, 4)
        if status_item is not None:
            status_item.setText(file_result.status.capitalize())
        if details_item is not None:
            details_item.setText(file_result.reason)

    def on_finished(self, summary, plan):
        if summary is None:
            copy_count = sum(item.action == "copy" for item in plan)
            skipped_count = sum(
                item.action == "skip_identical" and item.skip_reason != "source_duplicate"
                for item in plan
            )
            duplicate_count = sum(item.skip_reason == "source_duplicate" for item in plan)
            self.output.append(
                f"Preview: {len(plan)} files — {copy_count} to copy, "
                f"{skipped_count} already in destination, {duplicate_count} duplicates"
            )
        else:
            status = "Cancelled" if summary.cancelled else "Complete"
            self.output.append(
                f"{status} — copied {summary.copied}, skipped {summary.skipped_identical}, "
                f"duplicates {summary.duplicates}, failed {summary.failed}, "
                f"not processed {summary.cancelled_files}"
            )
            for error in summary.errors:
                self.output.append(error)
        self.progress.setValue(100)

    def on_failed(self, message: str):
        self.output.append(f"ERROR: {message}")
        QMessageBox.critical(self, "Operation failed", message)

    def restore_buttons(self):
        self.preview_button.setEnabled(True)
        self.organize_button.setEnabled(True)
        self.cancel_button.setEnabled(False)


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
