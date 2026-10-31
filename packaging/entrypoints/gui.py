"""PyInstaller entry point for the desktop application."""
from __future__ import annotations

import sys


def main() -> int:
    if sys.argv[1:] == ["--smoke-test"]:
        # Verify the frozen bootloader and native Qt modules without creating a
        # QApplication. Headless QApplication startup is unstable in some
        # PyInstaller/Qt hosted-runner combinations (SIGSEGV / STATUS_STACK_BUFFER_OVERRUN).
        # The normal CI matrix separately constructs MainWindow with system Python.
        import PySide6
        from PySide6 import QtCore, QtGui, QtWidgets
        from storage_organizer import __version__

        required_symbols = (
            QtCore.QObject,
            QtGui.QGuiApplication,
            QtWidgets.QApplication,
            QtWidgets.QMainWindow,
        )
        if not all(required_symbols):
            raise RuntimeError("The frozen Qt runtime is missing required GUI symbols.")
        print(
            "Frozen desktop runtime check passed: "
            f"Storage Organizer {__version__}, PySide6 {PySide6.__version__}"
        )
        return 0

    from storage_organizer.gui import main as launch_gui

    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
