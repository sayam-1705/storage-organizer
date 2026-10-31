"""Optional PySide6 desktop interface. Install with: pip install .[gui]."""
from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime, timezone
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
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QProgressBar,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ModuleNotFoundError as exc:
    if exc.name == "PySide6" or (exc.name and exc.name.startswith("PySide6.")):
        raise SystemExit(
            "The GUI requires PySide6. Install it with: "
            "python -m pip install 'storage-organizer[gui]'"
        ) from exc
    raise

from .config import load_config, save_config
from .logging_setup import setup_logging
from .organizer import create_plan, organize
from .preferences import (
    load_preferences,
    load_recent_runs,
    save_preferences,
    save_recent_run,
)


class Worker(QObject):
    """Run scanning and transfers off the GUI thread."""

    scan_progress = Signal(int, str)
    plan_ready = Signal(object)
    file_updated = Signal(object, int, int)
    transfer_updated = Signal(int, int, float, int, int)
    finished = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        sources: list[Path],
        destination: Path,
        preview: bool,
        cancel_event: threading.Event,
    ):
        super().__init__()
        self.sources = sources
        self.destination = destination
        self.preview = preview
        self.cancel_event = cancel_event

    def run(self) -> None:
        try:
            last_scan_emit = 0.0

            def scan_callback(count: int, path: Path) -> None:
                nonlocal last_scan_emit
                now = time.monotonic()
                # Avoid flooding Qt's event queue for drives with very large file
                # counts. Emit the first item, then at most ~10 times per second or
                # every 250 files, whichever provides the next useful update.
                if count == 1 or count % 250 == 0 or now - last_scan_emit >= 0.1:
                    self.scan_progress.emit(count, str(path))
                    last_scan_emit = now
            if self.preview:
                plan, _, _, _ = create_plan(
                    self.sources,
                    self.destination,
                    scan_progress=scan_callback,
                )
                self.plan_ready.emit(plan)
                self.finished.emit(None, plan)
                return

            logger = setup_logging()
            summary, plan = organize(
                self.sources,
                self.destination,
                logger=logger,
                cancel_event=self.cancel_event,
                plan_ready=self.plan_ready.emit,
                scan_progress=scan_callback,
                file_progress=lambda result, done, total, _summary: self.file_updated.emit(
                    result, done, total
                ),
                transfer_progress=lambda copied, total_bytes, elapsed, done, total: (
                    self.transfer_updated.emit(copied, total_bytes, elapsed, done, total)
                ),
            )
            self.finished.emit(summary, plan)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Storage Organizer")
        self.resize(1180, 800)
        self._file_rows: dict[str, int] = {}
        self._operation_started = 0.0
        self._last_transfer_metrics = (0, 0, 0.0, 0, 0)

        preferences = load_preferences()
        saved_sources = preferences.get("sources")
        if not isinstance(saved_sources, list) or not saved_sources:
            legacy_source = preferences.get("source")
            saved_sources = [legacy_source] if legacy_source else []
        self.sources = [Path(value) for value in saved_sources if Path(value).is_dir()]
        self.destination_initial = preferences.get("destination", "")

        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self.cancel_event = threading.Event()

        central = QWidget()
        layout = QVBoxLayout(central)

        source_form = QFormLayout()
        self.source_list = QListWidget()
        self.source_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.source_list.setMaximumHeight(105)
        source_buttons = QHBoxLayout()
        add_source_button = QPushButton("Add folder…")
        add_source_button.clicked.connect(self.add_source)
        remove_source_button = QPushButton("Remove selected")
        remove_source_button.clicked.connect(self.remove_selected_sources)
        clear_sources_button = QPushButton("Clear")
        clear_sources_button.clicked.connect(self.clear_sources)
        source_buttons.addWidget(add_source_button)
        source_buttons.addWidget(remove_source_button)
        source_buttons.addWidget(clear_sources_button)
        source_buttons.addStretch(1)
        source_box = QVBoxLayout()
        source_box.addWidget(self.source_list)
        source_box.addLayout(source_buttons)
        source_form.addRow("Source folders", source_box)
        self._refresh_sources()

        self.destination_edit = QLineEdit(self.destination_initial)
        destination_button = QPushButton("Browse…")
        destination_button.clicked.connect(self.select_destination)
        destination_row = QHBoxLayout()
        destination_row.addWidget(self.destination_edit, 1)
        destination_row.addWidget(destination_button)
        source_form.addRow("Destination root", destination_row)
        layout.addLayout(source_form)

        action_row = QHBoxLayout()
        self.preview_button = QPushButton("Preview plan")
        self.preview_button.clicked.connect(lambda: self.start_job(True))
        self.organize_button = QPushButton("Copy and organize")
        self.organize_button.clicked.connect(lambda: self.start_job(False))
        self.cancel_button = QPushButton("Cancel after current file")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_job)
        self.settings_button = QPushButton("Settings…")
        self.settings_button.clicked.connect(self.open_settings)
        action_row.addWidget(self.preview_button)
        action_row.addWidget(self.organize_button)
        action_row.addWidget(self.cancel_button)
        action_row.addStretch(1)
        action_row.addWidget(self.settings_button)
        layout.addLayout(action_row)

        self.status_label = QLabel("Ready")
        self.metrics_label = QLabel("Choose one or more source folders and a destination.")
        layout.addWidget(self.status_label)
        layout.addWidget(self.metrics_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.tabs = QTabWidget()
        current_tab = QWidget()
        current_layout = QVBoxLayout(current_tab)
        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter files by name, path, or details…")
        self.search_edit.textChanged.connect(self.apply_results_filter)
        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["All statuses", "Pending", "Copying", "Copied", "Skipped", "Duplicate", "Error", "Cancelled"]
        )
        self.status_filter.currentTextChanged.connect(self.apply_results_filter)
        filter_row.addWidget(self.search_edit, 1)
        filter_row.addWidget(self.status_filter)
        current_layout.addLayout(filter_row)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["File", "Source", "Destination", "Status", "Details"]
        )
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setWordWrap(False)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSortingEnabled(False)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.verticalHeader().setDefaultSectionSize(24)
        self.results_table.setColumnWidth(0, 175)
        self.results_table.setColumnWidth(1, 260)
        self.results_table.setColumnWidth(2, 300)
        self.results_table.setColumnWidth(3, 100)
        current_layout.addWidget(self.results_table, 1)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setMaximumHeight(90)
        current_layout.addWidget(self.output)
        self.tabs.addTab(current_tab, "Current operation")

        history_tab = QWidget()
        history_layout = QVBoxLayout(history_tab)
        history_layout.addWidget(QLabel("The 10 most recent copy operations are kept locally on this computer."))
        self.history_table = QTableWidget(0, 8)
        self.history_table.setHorizontalHeaderLabels(
            ["Date", "Result", "Files", "Copied", "Skipped", "Duplicates", "Errors", "Destination"]
        )
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        history_layout.addWidget(self.history_table, 1)
        self.tabs.addTab(history_tab, "Recent activity")
        layout.addWidget(self.tabs, 1)

        self.setCentralWidget(central)
        self.refresh_recent_history()

    def _refresh_sources(self) -> None:
        self.source_list.clear()
        for source in self.sources:
            self.source_list.addItem(QListWidgetItem(str(source)))

    def _save_source_preferences(self) -> None:
        save_preferences(sources=[str(source) for source in self.sources])

    def add_source(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add source folder or mounted drive")
        if not folder:
            return
        # Keep the selected path itself intact so the shared path validator can
        # reject symlinked source paths instead of silently resolving through them.
        source = Path(folder)
        if source not in self.sources:
            self.sources.append(source)
            self._refresh_sources()
            self._save_source_preferences()

    def remove_selected_sources(self) -> None:
        selected = {item.text() for item in self.source_list.selectedItems()}
        if not selected:
            return
        self.sources = [source for source in self.sources if str(source) not in selected]
        self._refresh_sources()
        self._save_source_preferences()

    def clear_sources(self) -> None:
        self.sources.clear()
        self._refresh_sources()
        self._save_source_preferences()

    def select_destination(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select destination root")
        if folder:
            self.destination_edit.setText(folder)
            save_preferences(destination=folder)

    def open_settings(self) -> None:
        config = load_config()
        dialog = QDialog(self)
        dialog.setWindowTitle("Storage Organizer settings")
        dialog.setMinimumWidth(430)
        form = QFormLayout(dialog)

        include_hidden = QCheckBox("Include hidden files and folders")
        include_hidden.setChecked(config["organization"]["include_hidden"])
        form.addRow("Scanning", include_hidden)

        date_policy = QComboBox()
        date_policy.addItem("Use embedded metadata, then modified date", "metadata_then_modified")
        date_policy.addItem("Use modified date only", "modified")
        selected_index = date_policy.findData(config["organization"]["date_policy"])
        date_policy.setCurrentIndex(max(0, selected_index))
        form.addRow("Date selection", date_policy)

        unknown_folder = QLineEdit(config["organization"]["unknown_date_folder"])
        form.addRow("Unknown-date folder", unknown_folder)
        note = QLabel("SHA-256 verification remains enabled to protect copied files.")
        form.addRow("Transfer safety", note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        config["organization"]["include_hidden"] = include_hidden.isChecked()
        config["organization"]["date_policy"] = date_policy.currentData()
        config["organization"]["unknown_date_folder"] = unknown_folder.text().strip()
        try:
            saved_path = save_config(config)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Settings not saved", str(exc))
            return
        self.output.append(f"Settings saved to {saved_path}")

    def start_job(self, preview: bool) -> None:
        if not self.sources or not self.destination_edit.text().strip():
            QMessageBox.warning(
                self,
                "Missing paths",
                "Add at least one source folder and select a destination first.",
            )
            return
        if not preview:
            answer = QMessageBox.question(
                self,
                "Confirm copy",
                "Copy files from all selected source folders to the destination? "
                "Original files will remain untouched.",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self._save_source_preferences()
        save_preferences(destination=self.destination_edit.text().strip())
        self._operation_started = time.monotonic()
        self._last_transfer_metrics = (0, 0, 0.0, 0, 0)
        self.preview_button.setEnabled(False)
        self.organize_button.setEnabled(False)
        self.cancel_button.setEnabled(not preview)
        self.settings_button.setEnabled(False)
        self.output.clear()
        self.results_table.setRowCount(0)
        self._file_rows.clear()
        self.search_edit.clear()
        self.status_filter.setCurrentIndex(0)
        self.progress.setRange(0, 0)
        self.status_label.setText("Scanning and planning files…")
        self.metrics_label.setText("Discovered 0 files")
        self.tabs.setCurrentIndex(0)
        self.cancel_event.clear()

        self.thread = QThread(self)
        self.worker = Worker(
            self.sources.copy(),
            Path(self.destination_edit.text().strip()),
            preview,
            self.cancel_event,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.scan_progress.connect(self.on_scan_progress)
        self.worker.plan_ready.connect(self.on_plan_ready)
        self.worker.file_updated.connect(self.on_file_updated)
        self.worker.transfer_updated.connect(self.on_transfer_updated)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.restore_buttons)
        self.thread.start()

    def on_scan_progress(self, count: int, path: str) -> None:
        self.status_label.setText("Scanning and planning files…")
        self.metrics_label.setText(f"Discovered {count:,} files · Latest: {path}")

    def on_plan_ready(self, plan) -> None:
        self.progress.setRange(0, max(1, len(plan)))
        self.progress.setValue(0)
        self.results_table.setUpdatesEnabled(False)
        self.results_table.setRowCount(len(plan))
        self._file_rows.clear()
        copy_count = 0
        copy_bytes = 0
        skip_count = 0
        duplicate_count = 0
        error_count = 0

        for row, planned_file in enumerate(plan):
            if planned_file.action == "copy":
                status = "Pending"
                copy_count += 1
                try:
                    copy_bytes += planned_file.source.stat().st_size
                except OSError:
                    pass
            elif planned_file.action == "error":
                status = "Error"
                error_count += 1
            elif planned_file.skip_reason == "source_duplicate":
                status = "Duplicate"
                duplicate_count += 1
            else:
                status = "Skipped"
                skip_count += 1

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

        self.results_table.setUpdatesEnabled(True)
        self.status_label.setText(f"Plan ready · {len(plan):,} files")
        self.metrics_label.setText(
            f"To copy: {copy_count:,} · Already present: {skip_count:,} · "
            f"Duplicates: {duplicate_count:,} · Planning errors: {error_count:,} · "
            f"Copy size: {self._format_bytes(copy_bytes)}"
        )

    def on_file_updated(self, file_result, done: int, total: int) -> None:
        row = self._file_rows.get(str(file_result.source))
        if row is not None:
            status_item = self.results_table.item(row, 3)
            details_item = self.results_table.item(row, 4)
            if status_item is not None:
                status_item.setText(file_result.status.capitalize())
            if details_item is not None:
                details_item.setText(file_result.reason)
        if total and self._last_transfer_metrics[1] == 0:
            self.progress.setValue(min(done, total))
        if row is not None:
            self.results_table.setRowHidden(row, not self._row_matches_filter(row))

    def on_transfer_updated(
        self,
        bytes_copied: int,
        total_bytes: int,
        elapsed: float,
        done: int,
        total: int,
    ) -> None:
        self._last_transfer_metrics = (bytes_copied, total_bytes, elapsed, done, total)
        if total_bytes > 0:
            percent = int(min(100, bytes_copied * 100 / total_bytes))
            self.progress.setRange(0, 100)
            self.progress.setValue(percent)
        else:
            self.progress.setRange(0, max(1, total))
            self.progress.setValue(min(done, total))

        speed = bytes_copied / elapsed if elapsed > 0 else 0.0
        if total_bytes > 0 and speed > 0:
            eta_seconds = max(0, total_bytes - bytes_copied) / speed
            eta = self._format_duration(eta_seconds)
        elif total_bytes == 0:
            eta = "—"
        else:
            eta = "calculating…"
        self.status_label.setText(f"Processing files · {done:,}/{total:,} file outcomes")
        self.metrics_label.setText(
            f"Transferred {self._format_bytes(bytes_copied)} / {self._format_bytes(total_bytes)}"
            f" · Speed {self._format_bytes(speed)}/s · ETA {eta}"
        )

    def on_finished(self, summary, plan) -> None:
        if summary is None:
            copy_count = sum(item.action == "copy" for item in plan)
            skipped_count = sum(
                item.action == "skip_identical" and item.skip_reason != "source_duplicate"
                for item in plan
            )
            duplicate_count = sum(item.skip_reason == "source_duplicate" for item in plan)
            error_count = sum(item.action == "error" for item in plan)
            self.status_label.setText("Preview complete")
            self.metrics_label.setText(
                f"{len(plan):,} files · {copy_count:,} to copy · {skipped_count:,} skipped · "
                f"{duplicate_count:,} duplicates · {error_count:,} planning errors"
            )
            self.output.append("Preview only — no files were copied.")
        else:
            status = "Cancelled" if summary.cancelled else ("Completed with errors" if summary.failed else "Complete")
            duration = max(0.0, time.monotonic() - self._operation_started)
            self.status_label.setText(f"{status} · {self._format_duration(duration)}")
            self.metrics_label.setText(
                f"Copied {summary.copied:,} · Skipped {summary.skipped_identical:,} · "
                f"Duplicates {summary.duplicates:,} · Errors {summary.failed:,} · "
                f"Cancelled {summary.cancelled_files:,}"
            )
            self.output.append(
                f"{status} — scanned {summary.scanned}, copied {summary.copied}, "
                f"skipped {summary.skipped_identical}, duplicates {summary.duplicates}, "
                f"failed {summary.failed}, not processed {summary.cancelled_files}."
            )
            for error in summary.errors:
                self.output.append(error)
            self._record_recent_run(summary, duration)
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self.apply_results_filter()

    def _record_recent_run(self, summary, duration: float) -> None:
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "cancelled" if summary.cancelled else ("failed" if summary.failed else "completed"),
            "sources": [str(source) for source in self.sources],
            "destination": self.destination_edit.text().strip(),
            "scanned": summary.scanned,
            "copied": summary.copied,
            "skipped": summary.skipped_identical,
            "duplicates": summary.duplicates,
            "errors": summary.failed,
            "cancelled_files": summary.cancelled_files,
            "duration_seconds": round(duration, 2),
        }
        try:
            save_recent_run(result)
            self.refresh_recent_history()
        except OSError as exc:
            self.output.append(f"Could not save recent operation history: {exc}")

    def refresh_recent_history(self) -> None:
        runs = load_recent_runs()
        self.history_table.setRowCount(len(runs))
        for row, result in enumerate(runs):
            timestamp = str(result.get("timestamp", ""))
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone().strftime(
                    "%Y-%m-%d %H:%M"
                )
            except ValueError:
                pass
            values = (
                timestamp,
                str(result.get("status", "unknown")).capitalize(),
                str(result.get("scanned", 0)),
                str(result.get("copied", 0)),
                str(result.get("skipped", 0)),
                str(result.get("duplicates", 0)),
                str(result.get("errors", 0)),
                str(result.get("destination", "")),
            )
            for column, value in enumerate(values):
                self.history_table.setItem(row, column, QTableWidgetItem(value))
        self.history_table.resizeRowsToContents()

    def apply_results_filter(self) -> None:
        for row in range(self.results_table.rowCount()):
            self.results_table.setRowHidden(row, not self._row_matches_filter(row))

    def _row_matches_filter(self, row: int) -> bool:
        query = self.search_edit.text().strip().casefold()
        selected_status = self.status_filter.currentText()
        values = [
            self.results_table.item(row, column).text()
            if self.results_table.item(row, column) is not None
            else ""
            for column in range(self.results_table.columnCount())
        ]
        status_matches = selected_status == "All statuses" or values[3] == selected_status
        query_matches = not query or any(query in value.casefold() for value in values)
        return status_matches and query_matches

    def on_failed(self, message: str) -> None:
        self.status_label.setText("Operation failed")
        self.metrics_label.setText(message)
        self.output.append(f"ERROR: {message}")
        self.progress.setRange(0, 100)
        QMessageBox.critical(self, "Operation failed", message)

    def cancel_job(self) -> None:
        self.cancel_event.set()
        self.status_label.setText("Cancellation requested")
        self.output.append("Cancellation requested; the current file will finish safely.")
        self.cancel_button.setEnabled(False)

    def restore_buttons(self) -> None:
        self.preview_button.setEnabled(True)
        self.organize_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.settings_button.setEnabled(True)

    @staticmethod
    def _format_bytes(value: float | int) -> str:
        amount = float(max(0, value))
        units = ("B", "KB", "MB", "GB", "TB")
        for unit in units:
            if amount < 1024 or unit == units[-1]:
                return f"{amount:.1f} {unit}"
            amount /= 1024
        return f"{amount:.1f} TB"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        if seconds < 60:
            return f"{seconds}s"
        minutes, remainder = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {remainder}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m"


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
