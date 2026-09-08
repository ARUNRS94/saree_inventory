"""Main PySide6 window with working module-based navigation."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QToolBar, QWidget

from ui.dashboard import DashboardPage
from ui.grn import GrnPage
from ui.purchase import PurchaseOrderPage
from ui.reports import ReportsPage
from ui.saree import SareePage
from ui.supplier import SupplierPage
from ui.customer_issue import CustomerIssuePage
from ui.theme import DARK_THEME, LIGHT_THEME


class MainWindow(QMainWindow):
    """Application shell that routes left-menu actions to real module pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Saree Inventory Management")
        self.resize(1280, 800)
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        self._page_loaders: list[Callable[[], QWidget]] = [
            DashboardPage,
            SupplierPage,
            SareePage,
            PurchaseOrderPage,
            GrnPage,
            CustomerIssuePage,
            ReportsPage,
        ]
        for loader in self._page_loaders:
            self.pages.addWidget(loader())
        self._build_toolbar()
        self.apply_light_theme()
        self._show_page(0)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Navigation")
        toolbar.setMovable(False)
        labels = ["Dashboard", "Contacts", "Items", "Purchase", "GRN", "Customer Issue", "Reports"]
        for index, label in enumerate(labels):
            action = toolbar.addAction(label)
            action.triggered.connect(lambda _checked=False, page=index: self._show_page(page))
        toolbar.addSeparator()
        light = toolbar.addAction("☀")
        light.setToolTip("Light Theme")
        light.triggered.connect(self.apply_light_theme)
        dark = toolbar.addAction("🌙")
        dark.setToolTip("Dark Theme")
        dark.triggered.connect(self.apply_dark_theme)
        self.addToolBar(Qt.ToolBarArea.LeftToolBarArea, toolbar)

    def apply_light_theme(self) -> None:
        self.setStyleSheet(LIGHT_THEME)

    def apply_dark_theme(self) -> None:
        self.setStyleSheet(DARK_THEME)

    def _show_page(self, index: int) -> None:
        old_widget = self.pages.widget(index)
        self.pages.removeWidget(old_widget)
        old_widget.deleteLater()
        self.pages.insertWidget(index, self._page_loaders[index]())
        self.pages.setCurrentIndex(index)
