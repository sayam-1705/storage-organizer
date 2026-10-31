from __future__ import annotations

import runpy
import sys
import types
from pathlib import Path

import pytest


def test_frozen_entrypoint_smoke_test_imports_qt_without_creating_application(
    monkeypatch, capsys
):
    entrypoint = Path(__file__).resolve().parents[1] / "packaging/entrypoints/gui.py"
    pyside = types.ModuleType("PySide6")
    pyside.__path__ = []
    pyside.__version__ = "6.12.0"
    qtcore = types.ModuleType("PySide6.QtCore")
    qtgui = types.ModuleType("PySide6.QtGui")
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtcore.QObject = object
    qtgui.QGuiApplication = object

    class ForbiddenApplication:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("The frozen smoke test must not construct QApplication.")

    qtwidgets.QApplication = ForbiddenApplication
    qtwidgets.QMainWindow = object
    pyside.QtCore = qtcore
    pyside.QtGui = qtgui
    pyside.QtWidgets = qtwidgets
    organizer = types.ModuleType("storage_organizer")
    organizer.__version__ = "1.0.1"

    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "storage_organizer", organizer)
    monkeypatch.setattr(sys, "argv", [str(entrypoint), "--smoke-test"])

    with pytest.raises(SystemExit) as raised:
        runpy.run_path(str(entrypoint), run_name="__main__")

    assert raised.value.code == 0
    assert "Frozen desktop runtime check passed" in capsys.readouterr().out
