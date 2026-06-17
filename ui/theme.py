"""Application light and dark themes."""
from __future__ import annotations

LIGHT_THEME = """
QMainWindow, QWidget { background: #f6f8fb; color: #1f2937; font-size: 13px; }
QToolBar { background: #ffffff; border-right: 1px solid #d9e2ec; spacing: 8px; padding: 8px; }
QToolButton { padding: 10px 14px; border-radius: 8px; text-align: left; }
QToolButton:hover { background: #e8f1ff; color: #0f4c81; }
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px; }
QPushButton { background: #2563eb; color: white; border: 0; border-radius: 8px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #1d4ed8; }
QTableWidget { background: #ffffff; color: #1f2937; gridline-color: #e5e7eb; border: 1px solid #d9e2ec; border-radius: 8px; }
QHeaderView::section { background: #edf2f7; color: #111827; padding: 8px; border: 0; font-weight: 600; }
QTabWidget::pane { border: 1px solid #d9e2ec; background: #ffffff; border-radius: 8px; margin-top: -1px; }
QTabBar::tab { background: #e5e7eb; color: #111827; padding: 9px 16px; border: 1px solid #cbd5e1; border-bottom: 0; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px; font-weight: 600; }
QTabBar::tab:selected { background: #ffffff; color: #1d4ed8; }
QTabBar::tab:hover { background: #eff6ff; color: #0f4c81; }
QLabel[card="true"] { background: #ffffff; border: 1px solid #d9e2ec; border-radius: 12px; padding: 18px; font-size: 16px; }
"""

DARK_THEME = """
QMainWindow, QWidget { background: #111827; color: #e5e7eb; font-size: 13px; }
QToolBar { background: #0f172a; border-right: 1px solid #334155; spacing: 8px; padding: 8px; }
QToolButton { color: #e5e7eb; padding: 10px 14px; border-radius: 8px; text-align: left; }
QToolButton:hover { background: #1e293b; color: #93c5fd; }
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox { background: #1f2937; color: #f9fafb; border: 1px solid #475569; border-radius: 6px; padding: 6px; }
QPushButton { background: #3b82f6; color: white; border: 0; border-radius: 8px; padding: 8px 14px; font-weight: 600; }
QPushButton:hover { background: #60a5fa; }
QTableWidget { background: #1f2937; color: #f9fafb; gridline-color: #334155; border: 1px solid #475569; border-radius: 8px; }
QHeaderView::section { background: #334155; color: #f9fafb; padding: 8px; border: 0; font-weight: 600; }
QTabWidget::pane { border: 1px solid #475569; background: #1f2937; border-radius: 8px; margin-top: -1px; }
QTabBar::tab { background: #0f172a; color: #e5e7eb; padding: 9px 16px; border: 1px solid #475569; border-bottom: 0; border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 3px; font-weight: 600; }
QTabBar::tab:selected { background: #1f2937; color: #93c5fd; }
QTabBar::tab:hover { background: #1e293b; color: #bfdbfe; }
QLabel[card="true"] { background: #1f2937; border: 1px solid #475569; border-radius: 12px; padding: 18px; font-size: 16px; }
"""
