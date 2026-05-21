from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget
)

from . import core
from . import theme as t
from .pages import (
    AdaptPage, AnimationPage, BatchFixPage, BrandsPage, BRollPage, DashboardPage,
    FunnelAdsPage, GeneratePage, HistoryPage, IterationPage, ReshootPage, RunDetailPage,
    SettingsPage, TwinHubPage
)
from .swap_page import SwapPage
from .image_generator_page import ImageGeneratorPage
from pathlib import Path as _PathForAssets

from .widgets import GradientLogo, GradientText, icon_label, svg_icon, ICONS

_ASSETS_DIR = _PathForAssets(__file__).resolve().parent / "assets"


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

        # Logo: cursive "Mimica" wordmark in a violet → pink gradient,
        # painted directly on the dark sidebar (no chrome around it).
        # Same energy as the "today" mark in the C2 mockup.
        logo_row = QHBoxLayout()
        logo_row.setSpacing(0)
        logo_row.setContentsMargins(0, 0, 0, 0)

        # Custom-designed mimica wordmark (rounded geometric lowercase) painted
        # with the same violet → pink gradient as the previous Caveat fallback.
        wordmark = GradientLogo(
            _ASSETS_DIR / "mimica-logo.png",
            height=30,
            color_start=t.ACCENT_SOFT,
            color_end=t.ACCENT_PINK,
        )
        wordmark.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        logo_row.addWidget(wordmark, alignment=Qt.AlignLeft)
        logo_row.addStretch()
        root.addLayout(logo_row)
        root.addSpacing(24)

        # Primary nav
        for key, icon, label in [
            ("dashboard", "dashboard", "Dashboard"),
            # Create = free-form image generation with optional @imageN refs.
            # Sits at the top of "make stuff" because it's the most fundamental
            # blank-canvas entry — no source ad, no brand required.
            ("create", "generate", "Create"),
            ("animation", "animation", "Animation"),
            ("funnel", "funnel", "Funnel Ads"),
            ("twin", "twin", "Twin"),
            ("swap", "adapt", "Swap product"),
            ("generate", "generate", "Variation"),
            ("iteration", "generate", "Iteration"),
            ("reshoot", "generate", "Reshoot"),
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
        "Dashboard":    "dashboard",
        "Create":       "generate",
        "Animation":    "animation",
        "Funnel Ads":   "funnel",
        "Twin":         "twin",
        "Swap product": "adapt",
        "Generate":     "generate",
        "Adapt":        "adapt",
        "Fix":          "wrench",
        "B-Roll":       "broll",
        "History":      "history",
        "Brands":       "brand",
        "Settings":     "settings",
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
        self.create = ImageGeneratorPage()
        self.animation = AnimationPage()
        self.funnel = FunnelAdsPage()
        self.twin = TwinHubPage()
        self.swap = SwapPage()
        self.generate = GeneratePage()
        self.adapt = AdaptPage()
        self.fix = BatchFixPage()
        self.broll = BRollPage()
        self.iteration = IterationPage()
        self.reshoot = ReshootPage()
        self.history = HistoryPage()
        self.brands = BrandsPage()
        self.detail = RunDetailPage()
        self.settings = SettingsPage()
        for p in (self.dashboard, self.create, self.animation, self.funnel, self.twin, self.swap, self.generate, self.adapt, self.fix, self.broll,
                  self.iteration, self.reshoot, self.history, self.brands, self.detail, self.settings):
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
        self.detail.resume_broll.connect(self._resume_broll)
        self.detail.resume_twin_video.connect(self._resume_twin_video)
        self.adapt.open_brands.connect(lambda: self._on_nav("brands"))
        self.broll.open_brands.connect(lambda: self._on_nav("brands"))
        self.funnel.open_brands.connect(lambda: self._on_nav("brands"))
        self.animation.open_brands.connect(lambda: self._on_nav("brands"))
        self.twin.open_brands.connect(lambda: self._on_nav("brands"))
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
            "create":    (self.create,    "Create"),
            "animation": (self.animation, "Animation"),
            "funnel":    (self.funnel,    "Funnel Ads"),
            "twin":      (self.twin,      "Twin"),
            "swap":      (self.swap,      "Swap product"),
            "generate":  (self.generate,  "Variation"),
            "adapt":     (self.adapt,     "Adapt"),
            "fix":       (self.fix,       "Fix"),
            "broll":     (self.broll,     "B-Roll"),
            "iteration": (self.iteration, "Iteration"),
            "reshoot":   (self.reshoot,   "Reshoot"),
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
        if page is self.animation:
            self.animation.refresh_brands()
        if page is self.reshoot:
            self.reshoot.refresh_brands()
        self.stack.setCurrentWidget(page)
        self.sidebar.set_active(key)
        self.topbar.set_crumb(crumb)
        self.sidebar.update_status()

    def _open_run(self, run: dict):
        self.detail.set_run(run)
        self.stack.setCurrentWidget(self.detail)
        self.sidebar.set_active("history")
        self.topbar.set_crumb(f"History · {run['timestamp']}")

    def _resume_broll(self, run: dict):
        if self.broll.load_run(run):
            self._on_nav("broll")

    def _resume_twin_video(self, run: dict):
        if self.twin.load_twin_video_run(run):
            self._on_nav("twin")
