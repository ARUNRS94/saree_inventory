"""Reusable PySide6 widgets and helpers for ERP pages."""
from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtWidgets import QComboBox, QLabel, QMessageBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class Page(QWidget):
    """Base page with a standard title and message helpers."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.layout = QVBoxLayout(self)
        heading = QLabel(title)
        heading.setStyleSheet("font-size: 24px; font-weight: 600; margin: 8px;")
        self.layout.addWidget(heading)

    def info(self, message: str) -> None:
        QMessageBox.information(self, "Saved", message)

    def error(self, message: str) -> None:
        QMessageBox.critical(self, "Validation Error", message)


def populate_combo(combo: QComboBox, rows: Iterable[tuple[int, str]]) -> None:
    combo.clear()
    for row_id, label in rows:
        combo.addItem(label, row_id)


def fill_table(table: QTableWidget, rows: Iterable[Iterable[object]]) -> None:
    """Populate a table without allowing active sorting to move half-filled rows.

    QTableWidget re-sorts immediately when sorting is enabled. Inserting cells while
    sorting is active can move the current row before every column is populated,
    which leaves apparent blank cells in tables such as Vendor Process Types.
    """
    was_sorting_enabled = table.isSortingEnabled()
    table.setSortingEnabled(False)
    table.setRowCount(0)
    for row_index, row_values in enumerate(rows):
        table.insertRow(row_index)
        for column_index, value in enumerate(row_values):
            table.setItem(row_index, column_index, QTableWidgetItem("" if value is None else str(value)))
    table.setSortingEnabled(was_sorting_enabled)
