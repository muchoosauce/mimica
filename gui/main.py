from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget
)

from . import core
from . import theme as t
from .pages import (
    AdaptPage, BatchFixPage, BrandsPage, BRollPage, DashboardPage, FunnelAdsPage,
    GeneratePage, HistoryPage, RunDetailPage, SettingsPage
)
from .widgets import icon_label, svg_icon, ICONS


class SidebarItem(QPushButton):
    def __init__(self, icon_name: str, label: str):
        super().__init__()
        self.icon_name = icon_name
        self.label_text = label
        self.setObjectName("SidebarItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.setCheckable(True)
        self._build()

    def _build(self):
        self.setText("")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(12)
        color = t.ACCENT_STRONG if self.isChecked() else t.TEXT
        self._icon = icon_label(self.icon_name, 16, color)
        self._text = QLabel(self.label_text)
        self._text.setStyleSheet(
            f"color: {color}; font-size: 13px; "
            f"font-weight: {'600' if self.isChecked() else '500'};"
        )
        lay.addWidget(self._icon)
        lay.addWidget(self._text)
        lay.addStretch()

    def set_active(self, active: bool):
        self.setChecked(active)
        self.setObjectName("SidebarItemActive" if active else "SidebarItem")
        color = t.ACCENT_STRONG if active else t.TEXT
        self._icon.setPixmap(svg_icon(ICONS[self.icon_name], 16, color))
        self._text.setStyleSheet(
            f"color: {color}; font-size: 13px; "
            f"font-weight: {'600' if active else '500'};"
        )
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
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(4)

        # Logo + name
        logo_row = QHBoxLayout(); logo_row.setSpacing(10); logo_row.setContentsMargins(0, 0, 0, 0)
        logo_box = QFrame()
        logo_box.setFixedSize(28, 28)
        logo_box.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {t.ACCENT_SOFT}, stop:1 {t.ACCENT_STRONG});"
            f"border-radius: 8px;"
        )
        ll = QVBoxLayout(logo_box); ll.setContentsMargins(0, 0, 0, 0)
        m = QLabel("M"); m.setAlignment(Qt.AlignCenter)
        m.setStyleSheet("color: white; font-size: 14px; font-weight: 700; letter-spacing: -0.02em; background: transparent;")
        ll.addWidget(m)
        logo_row.addWidget(logo_box)
        name = QLabel("Mimica")
        name.setStyleSheet("font-size: 16px; font-weight: 600; letter-spacing: -0.01em; color: " + t.TEXT + ";")
        logo_row.addWidget(name); logo_row.addStretch()
        root.addLayout(logo_row)
        root.addSpacing(24)

        # Primary nav
        for key, icon, label in [
            ("dashboard", "dashboard", "Dashboard"),
            ("funnel", "funnel", "Funnel Ads"),
            ("generate", "generate", "Generate"),
            ("adapt", "adapt", "Adapt"),
            ("fix", "wrench", "Fix"),
            ("broll", "broll", "B-Roll"),
            ("history", "history", "History"),
        ]:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda _=None, k=key: self.nav.emit(k))
            root.addWidget(item)
            self.items[key] = item

        root.addSpacing(16)
        sect = QLabel("LIBRARY")
        sect.setStyleSheet(
            f"color: {t.TEXT_DIM}; font-size: 11px; "
            f"font-weight: 600; letter-spacing: 0.08em; padding: 0 14px;"
        )
        root.addWidget(sect)
        root.addSpacing(6)

        for key, icon, label in [
            ("brands", "brand", "Brands"),
            ("settings", "settings", "Settings"),
        ]:
            item = SidebarItem(icon, label)
            item.clicked.connect(lambda _=None, k=key: self.nav.emit(k))
            root.addWidget(item)
            self.items[key] = item

        root.addStretch()

        # Provider status card (white card on grey sidebar)
        self.status_card = QFrame()
        self.status_card.setObjectName("ProviderStatusCard")
        sc = QVBoxLayout(self.status_card)
        sc.setContentsMargins(14, 12, 14, 12)
        sc.setSpacing(6)

        title_row = QHBoxLayout(); title_row.setSpacing(8); title_row.setContentsMargins(0, 0, 0, 0)
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(8, 8)
        self.status_dot.setStyleSheet(
            f"background: {t.SUCCESS}; border-radius: 4px;"
        )
        self.status_title = QLabel("MuAPI")
        self.status_title.setStyleSheet(f"color: {t.TEXT}; font-size: 12px; font-weight: 600;")
        title_row.addWidget(self.status_dot, alignment=Qt.AlignVCenter)
        title_row.addWidget(self.status_title); title_row.addStretch()
        sc.addLayout(title_row)

        self.status_sub = QLabel("No key configured")
        self.status_sub.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px;")
        sc.addWidget(self.status_sub)

        self.status_btn = QPushButton("Manage")
        self.status_btn.setObjectName("GhostBtn")
        self.status_btn.setCursor(Qt.PointingHandCursor)
        self.status_btn.setFixedHeight(28)
        self.status_btn.clicked.connect(lambda: self.nav.emit("settings"))
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 4, 0, 0); btn_row.setSpacing(0)
        btn_row.addWidget(self.status_btn); btn_row.addStretch()
        sc.addLayout(btn_row)

        root.addWidget(self.status_card)

        self.update_status()

    def update_status(self):
        name = core.get_active_provider_name()
        label = core.PROVIDER_LABELS.get(name, name.title())
        if core.get_provider_key(name):
            self.status_title.setText(f"{label} · Connected")
            self.status_sub.setText("Your key is saved locally.")
            self.status_dot.setStyleSheet(f"background: {t.SUCCESS}; border-radius: 4px;")
            self.status_btn.setText("Manage")
        else:
            self.status_title.setText(label)
            self.status_sub.setText("Add your API key to start.")
            self.status_dot.setStyleSheet(f"background: {t.TEXT_DIM}; border-radius: 4px;")
            self.status_btn.setText("Set key")

    def set_active(self, key: str):
        for k, it in self.items.items():
            it.set_active(k == key)


class TopBar(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("TopBar")
        self.setFixedHeight(56)
        self._current_icon = "dashboard"
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(40, 10, 40, 10)
        lay.setSpacing(10)

        self.crumb_icon = icon_label(self._current_icon, 14, t.TEXT_MUTED)
        self.crumb_page = QLabel("Dashboard")
        self.crumb_page.setStyleSheet(
            f"color: {t.TEXT}; font-size: 13px; font-weight: 600;"
        )
        lay.addWidget(self.crumb_icon)
        lay.addWidget(self.crumb_page)
        lay.addStretch()

        # Search pill (search icon + label)
        self.search_btn = QPushButton("  Search")
        self.search_btn.setObjectName("SearchBtn")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        # Inject SVG icon onto the button via QPainter — keep it simple: prefix label
        lay.addWidget(self.search_btn)

        self.new_btn = QPushButton("  + New Run")
        self.new_btn.setObjectName("PrimaryBtn")
        self.new_btn.setCursor(Qt.PointingHandCursor)
        lay.addWidget(self.new_btn)

    _ICON_MAP = {
        "Dashboard":  "dashboard",
        "Funnel Ads": "funnel",
        "Generate":   "generate",
        "Adapt":      "adapt",
        "Fix":        "wrench",
        "B-Roll":     "broll",
        "History":    "history",
        "Brands":     "brand",
        "Settings":   "settings",
    }

    def set_crumb(self, page: str):
        self.crumb_page.setText(page)
        icon_key = next((self._ICON_MAP.get(part.strip()) for part in page.split("·")
                         if self._ICON_MAP.get(part.strip())), "dashboard")
        self.crumb_icon.setPixmap(svg_icon(ICONS.get(icon_key, ICONS["dashboard"]), 14, t.TEXT_MUTED))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mimica")
        self.resize(1280, 820)
        self.setMinimumSize(1200, 720)

        central = QWidget(); central.setObjectName("Root")
        root = QHBoxLayout(central); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)

        self.sidebar = Sidebar("dashboard")
        root.addWidget(self.sidebar)

        right_w = QWidget(); right_w.setObjectName("PageHost")
        right = QVBoxLayout(right_w); right.setContentsMargins(0, 0, 0, 0); right.setSpacing(0)
        self.topbar = TopBar()
        right.addWidget(self.topbar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPage()
        self.funnel = FunnelAdsPage()
        self.generate = GeneratePage()
        self.adapt = AdaptPage()
        self.fix = BatchFixPage()
        self.broll = BRollPage()
        self.history = HistoryPage()
        self.brands = BrandsPage()
        self.detail = RunDetailPage()
        self.settings = SettingsPage()
        for p in (self.dashboard, self.funnel, self.generate, self.adapt, self.fix, self.broll,
                  self.history, self.brands, self.detail, self.settings):
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)

        root.addWidget(right_w, 1)

        self.setCentralWidget(central)

        self.sidebar.nav.connect(self._on_nav)
        self.topbar.new_btn.clicked.connect(lambda: self._on_nav("generate"))
        self.dashboard.open_generate.connect(lambda: self._on_nav("generate"))
        self.dashboard.open_adapt.connect(lambda: self._on_nav("adapt"))
        self.dashboard.open_fix.connect(lambda: self._on_nav("fix"))
        self.dashboard.open_history.connect(lambda: self._on_nav("history"))
        self.dashboard.open_brands.connect(lambda: self._on_nav("brands"))
        self.dashboard.open_settings.connect(lambda: self._on_nav("settings"))
        self.dashboard.open_run.connect(self._open_run)
        self.history.open_run.connect(self._open_run)
        self.detail.back.connect(lambda: self._on_nav("history"))
        self.adapt.open_brands.connect(lambda: self._on_nav("brands"))
        self.broll.open_brands.connect(lambda: self._on_nav("brands"))
        self.funnel.open_brands.connect(lambda: self._on_nav("brands"))
        self.settings.provider_changed.connect(self._on_provider_changed)

        self._on_nav("dashboard")

    def _on_provider_changed(self, _name: str):
        self.sidebar.update_status()
        self.generate._update_cost()
        self.adapt._update_cost()
        self.fix._update_cost()
        if hasattr(self.dashboard, "refresh"):
            self.dashboard.refresh()

    def _on_nav(self, key: str):
        mapping = {
            "dashboard": (self.dashboard, "Dashboard"),
            "funnel":    (self.funnel,    "Funnel Ads"),
            "generate":  (self.generate,  "Generate"),
            "adapt":     (self.adapt,     "Adapt"),
            "fix":       (self.fix,       "Fix"),
            "broll":     (self.broll,     "B-Roll"),
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
        if page is self.broll:
            self.broll.refresh_brands()
        if page is self.funnel:
            self.funnel.refresh_brands()
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        self.topbar.set_crumb(crumb)
        self.sidebar.update_status()

    def _open_run(self, run: dict):
        self.detail.set_run(run)
        self.stack.setCurrentWidget(self.detail)
        self.sidebar.set_active("history")
        self.topbar.set_crumb(f"History · {run['timestamp']}")
