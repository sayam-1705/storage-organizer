"""PyInstaller entry point for the desktop application."""
from __future__ import annotations

import os
import sys


def main() -> int:
    if sys.argv[1:] == ["--smoke-test"]:
        # Exercise the frozen Qt imports and full MainWindow construction without
        # opening a visible window or entering the event loop.
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from storage_organizer.gui import MainWindow

        app = QApplication([])
        window = MainWindow()
        window.close()
        app.processEvents()
        app.quit()
        return 0

    from storage_organizer.gui import main as launch_gui

    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
