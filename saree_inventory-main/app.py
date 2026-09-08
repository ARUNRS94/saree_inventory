"""Application entry point."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from database.database import init_db
from ui.dashboard.main_window import MainWindow


def main() -> int:
    """Initialize SQLite and start the PySide6 desktop application."""
    init_db()
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
