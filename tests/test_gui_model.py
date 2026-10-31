from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from storage_organizer.gui import FileResultsProxyModel, FileResultsTableModel
from storage_organizer.models import FileResult, PlannedFile


def planned(source, status="copy", reason="Ready"):
    return PlannedFile(
        source=source,
        destination=source.parent / "organized" / source.name,
        category="Documents",
        year=2025,
        month="March",
        sha256="abc",
        action=status,
        reason=reason,
    )


def test_virtualized_results_model_initializes_rows_and_updates_status(tmp_path):
    source = tmp_path / "document.txt"
    model = FileResultsTableModel()
    model.set_plan([planned(source)])

    assert model.rowCount() == 1
    assert model.columnCount() == 5
    assert model.data(model.index(0, 0)) == "document.txt"
    assert model.data(model.index(0, 3)) == "Pending"

    model.update_results([
        FileResult(
            source=source,
            destination=source.parent / "organized" / source.name,
            status="copied",
            reason="Copied and verified",
        )
    ])

    assert model.data(model.index(0, 3)) == "Copied"
    assert model.data(model.index(0, 4)) == "Copied and verified"


def test_results_proxy_filters_by_status_and_case_insensitive_text(tmp_path):
    copied = tmp_path / "Invoice.pdf"
    skipped = tmp_path / "archive.txt"
    model = FileResultsTableModel()
    model.set_plan([planned(copied), planned(skipped)])
    proxy = FileResultsProxyModel()
    proxy.setSourceModel(model)
    assert proxy.rowCount() == 2

    proxy.set_filters("INVOICE", "Copied")
    assert proxy.rowCount() == 0
    model.update_results([
        FileResult(copied, copied.parent / "out" / copied.name, status="copied"),
        FileResult(skipped, skipped.parent / "out" / skipped.name, status="skipped"),
    ])
    proxy.invalidateFilter()
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) == "Invoice.pdf"

    proxy.set_filters("", "Skipped")
    assert proxy.rowCount() == 1
    assert proxy.data(proxy.index(0, 0)) == "archive.txt"
