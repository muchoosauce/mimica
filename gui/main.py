from __future__ import annotations

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton,
    QSizePolicy, QStackedWidget, QVBoxLayout, QWidget
)

from . import core
from . import theme as t
from .pages import (
    AdaptPage, BatchFixPage, BrandsPage, DashboardPage, GeneratePage, HistoryPage,
    RunDetailPage, SettingsPage
)
from .widgets import icon_button, icon_label, svg_icon, ICONS
from PySide6.QtGui import QPixmap


class SidebarItem(QPushButton):
    def __init__(self, icon_name: str, label: str, badge: str = ""):
        super().__init__()
        self.icon_name = icon_name
        self.label_text = label
        self.badge_text = badge
        self.setObjectName("SidebarItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(40)
        self.setCheckable(True)
        self._build()

    def _build(self):
        self.setText("")
        lay = QHBoxLayout(self); lay.setContentsMargins(12, 0, 12, 0); lay.setSpacing(10)
        color = t.TEXT if self.isChecked() else t.TEXT_DIM
        self._icon = icon_label(self.icon_name, 16, color)
        self._text = QLabel(self.label_text)
        self._text.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: {'600' if self.isChecked() else '500'};")
        lay.addWidget(self._icon)
        lay.addWidget(self._text)
        lay.addStretch()
        if self.badge_text:
            self._badge = QLabel(self.badge_text)
            self._badge.setStyleSheet(
                f"background: {t.BORDER}; color: {t.TEXT_DIM}; "
                f"padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600;"
            )
            lay.addWidget(self._badge)
        else:
            self._badge = None

    def set_badge(self, text: str):
        self.badge_text = text
        if self._badge:
            self._badge.setText(text)
            self._badge.setVisible(bool(text))
        elif text:
            self._badge = QLabel(text)
            self._badge.setStyleSheet(
                f"background: {t.BORDER}; color: {t.TEXT_DIM}; "
                f"padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600;"
            )
            self.layout().addWidget(self._badge)

    def set_active(self, active: bool):
        self.setChecked(active)
        self.setObjectName("SidebarItemActive" if active else "SidebarItem")
        color = t.TEXT if active else t.TEXT_DIM
        self._icon.setPixmap(svg_icon(ICONS[self.icon_name], 16, color))
        self._text.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: {'600' if active else '500'};")
        self.style().unpolish(self); self.style().polish(self)


class Sidebar(QWidget):
    nav = Signal(str)

    def __init__(self, initial: str = "dashboard"):
        super().__init__()
        self.setObjectName("Sidebar")
        self.setFixedWidth(240)
        self.items: dict[str, SidebarItem] = {}
        self._build()
        self.set_active(initial)

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 20)
        root.setSpacing(8)

        # Logo
        logo_row = QHBoxLayout(); logo_row.setSpacing(10)
        logo_box = QFrame()
        logo_box.setFixedSize(34, 34)
        logo_box.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {t.ACCENT_DEEP}, stop:1 {t.ACCENT_LIGHT});"
            f"border-radius: 8px;"
        )
        ll = QVBoxLayout(logo_box); ll.setContentsMargins(0, 0, 0, 0)
        ic = icon_label("logo", 20, "white"); ic.setAlignment(Qt.AlignCenter)
        ll.addWidget(ic, alignment=Qt.AlignCenter)
        logo_row.addWidget(logo_box)
        name = QLabel("Ad Variator")
        name.setStyleSheet("font-size: 16px; font-weight: 700; letter-spacing: -0.2px;")
        logo_row.addWidget(name); logo_row.addStretch()
        root.addLayout(logo_row)
        root.addSpacing(18)

        # Search
        search_wrap = QFrame()
        sl = QHBoxLayout(search_wrap); sl.setContentsMargins(10, 0, 10, 0); sl.setSpacing(8)
        sicon = icon_label("search", 14, t.TEXT_MUTED)
        self.search = QLineEdit()
        self.search.setObjectName("Search")
        self.search.setPlaceholderText("Search")
        self.search.setStyleSheet(
            f"QLineEdit {{ background: {t.BG_CARD}; border: 1px solid {t.BORDER}; "
            f"border-radius: 10px; padding: 8px 10px 8px 10px; color: {t.TEXT}; font-size: 12px; }}"
            f"QLineEdit:focus {{ border: 1px solid {t.ACCENT}; }}"
        )
        shortcut = QLabel("⌘K")
        shortcut.setStyleSheet(
            f"background: {t.BG_INPUT}; color: {t.TEXT_MUTED}; "
            f"padding: 2px 6px; border-radius: 4px; font-size: 10px;"
        )
        sl.addWidget(sicon); sl.addWidget(self.search); sl.addWidget(shortcut)
        search_wrap.setFixedHeight(38)
        root.addWidget(search_wrap)
        root.addSpacing(14)

        # Primary nav
        for key, icon, label in [
            ("dashboard", "dashboard", "Dashboard"),
            ("generate", "generate", "Generate"),
            ("adapt", "adapt", "Adapt"),
            ("fix", "wrench", "Fix"),
            ("history", "history", "History"),
        ]:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda _=None, k=key: self.nav.emit(k))
            root.addWidget(item)
            self.items[key] = item

        root.addSpacing(14)
        sect = QLabel("LIBRARY"); sect.setObjectName("SectionLabel")
        root.addWidget(sect)

        for key, icon, label in [
            ("brands", "brand", "Brands"),
            ("settings", "settings", "Settings"),
        ]:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda _=None, k=key: self.nav.emit(k))
            root.addWidget(item)
            self.items[key] = item

        root.addStretch()

        # Upgrade / status card
        self.status_card = QFrame()
        self.status_card.setObjectName("CardFlat")
        self.status_card.setStyleSheet(
            f"background: {t.BG_CARD}; border: 1px solid {t.BORDER}; border-radius: 14px;"
        )
        sc = QVBoxLayout(self.status_card); sc.setContentsMargins(14, 14, 14, 14); sc.setSpacing(6)
        self.status_title = QLabel("MuAPI")
        self.status_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.status_sub = QLabel("No key configured")
        self.status_sub.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        sc.addWidget(self.status_title); sc.addWidget(self.status_sub)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self.status_btn = QPushButton("Set key")
        self.status_btn.setObjectName("PrimaryBtn")
        self.status_btn.setCursor(Qt.PointingHandCursor)
        self.status_btn.setFixedHeight(30)
        self.status_btn.clicked.connect(lambda: self.nav.emit("settings"))
        btn_row.addWidget(self.status_btn)
        btn_row.addStretch()
        sc.addLayout(btn_row)
        root.addWidget(self.status_card)

        self.update_status()

    def update_status(self):
        name = core.get_active_provider_name()
        label = core.PROVIDER_LABELS.get(name, name.title())
        if core.get_provider_key(name):
            self.status_title.setText(f"{label} · Connected")
            self.status_sub.setText("Your key is saved locally.")
            self.status_btn.setText("Manage")
        else:
            self.status_title.setText(label)
            self.status_sub.setText("Add your API key to start.")
            self.status_btn.setText("Set key")

    def set_active(self, key: str):
        for k, it in self.items.items():
            it.set_active(k == key)


class TopBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(56)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self); lay.setContentsMargins(28, 10, 28, 10); lay.setSpacing(10)

        self.crumb_left = QLabel("Ad Variator")
        self.crumb_left.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 13px;")
        chev = icon_label("chevron_right", 12, t.TEXT_MUTED)
        self.crumb_page = QLabel("Dashboard")
        self.crumb_page.setStyleSheet(f"color: {t.TEXT}; font-size: 13px; font-weight: 600;")
        lay.addWidget(self.crumb_left)
        lay.addWidget(chev)
        lay.addWidget(self.crumb_page)
        lay.addStretch()

        help_btn = icon_button("alert", 14, t.TEXT_DIM, "Help")
        lay.addWidget(help_btn)
        self.new_btn = QPushButton("  + New Generation")
        self.new_btn.setObjectName("PrimaryBtn")
        self.new_btn.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.new_btn)

    def set_crumb(self, page: str):
        self.crumb_page.setText(page)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ad Variator")
        self.resize(1280, 820)
        self.setMinimumSize(1100, 720)

        central = QWidget(); central.setObjectName("Root")
        root = QHBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.sidebar = Sidebar("dashboard")
        root.addWidget(self.sidebar)

        right = QVBoxLayout(); right.setContentsMargins(0, 0, 0, 0); right.setSpacing(0)
        self.topbar = TopBar()
        right.addWidget(self.topbar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage()
        self.generate = GeneratePage()
        self.adapt = AdaptPage()
        self.fix = BatchFixPage()
        self.history = HistoryPage()
        self.brands = BrandsPage()
        self.detail = RunDetailPage()
        self.settings = SettingsPage()
        for p in (self.dashboard, self.generate, self.adapt, self.fix,
                  self.history, self.brands, self.detail, self.settings):
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)

        right_w = QWidget(); right_w.setLayout(right)
        root.addWidget(right_w, 1)

        self.setCentralWidget(central)

        self.sidebar.nav.connect(self._on_nav)
        self.topbar.new_btn.clicked.connect(lambda: self._on_nav("generate"))
        self.dashboard.open_generate.connect(lambda: self._on_nav("generate"))
        self.dashboard.open_history.connect(lambda: self._on_nav("history"))
        self.dashboard.open_run.connect(self._open_run)
        self.history.open_run.connect(self._open_run)
        self.detail.back.connect(lambda: self._on_nav("history"))
        self.adapt.open_brands.connect(lambda: self._on_nav("brands"))
        self.settings.provider_changed.connect(self._on_provider_changed)

        self._on_nav("dashboard")

    def _on_provider_changed(self, _name: str):
        self.sidebar.update_status()
        self.generate._update_cost()
        self.adapt._update_cost()
        self.fix._update_cost()

    def _on_nav(self, key: str):
        mapping = {
            "dashboard": (self.dashboard, "Dashboard"),
            "generate":  (self.generate,  "Generate"),
            "adapt":     (self.adapt,     "Adapt"),
            "fix":       (self.fix,       "Fix"),
            "history":   (self.history,   "History"),
            "brands":    (self.brands,    "Brands"),
            "settings":  (self.settings,  "Settings"),
        }
        page, crumb = mapping.get(key, (self.dashboard, "Dashboard"))
        if page is self.history:
            self.history.refresh()
        if page is self.dashboard:
            self.dashboard.refresh()
        if page is self.brands:
            self.brands.refresh()
        if page is self.fix:
            self.fix.refresh_brands()
        if page is self.adapt:
            self.adapt.refresh_brands()
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        self.topbar.set_crumb(crumb)
        self.sidebar.update_status()

    def _open_run(self, run: dict):
        self.detail.set_run(run)
        self.stack.setCurrentWidget(self.detail)
        self.sidebar.set_active("history")
        self.topbar.set_crumb(f"History · {run['timestamp']}")
