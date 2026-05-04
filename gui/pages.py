from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QScrollArea, QSizePolicy,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout,
    QWidget
)

from . import core
from . import theme as t
from .widgets import (
    BarChart, Card, ChipGroup, DropZone, FolderDropZone, OutputFolderRow,
    ProductImagesEditor, StatCard, StatusPill, ThumbLabel, icon_button, icon_label,
    open_path
)


MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class _VerticalOnlyScrollArea(QScrollArea):
    """QScrollArea that ignores horizontal wheel/trackpad scrolling.

    macOS trackpads emit horizontal wheel events alongside vertical ones;
    even with the horizontal scrollbar policy set to AlwaysOff, the
    underlying QAbstractScrollArea still consumes those deltas and shifts
    the viewport. We intercept them and forward only the vertical part.
    """
    def wheelEvent(self, event):
        if event.angleDelta().x() and not event.angleDelta().y():
            event.ignore()
            return
        super().wheelEvent(event)


# ─── Dashboard ──────────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    open_generate = Signal()
    open_adapt = Signal()
    open_fix = Signal()
    open_history = Signal()
    open_brands = Signal()
    open_settings = Signal()
    open_run = Signal(object)

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._spend_period = "1M"
        self._build()
        self.refresh()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(40, 16, 40, 32)
        outer.setSpacing(0)

        scroll = _VerticalOnlyScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        inner = QWidget()
        inner.setObjectName("Root")
        root = QVBoxLayout(inner)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(32)

        root.addLayout(self._build_hero())
        root.addLayout(self._build_workflows())
        root.addLayout(self._build_recent_runs())
        root.addLayout(self._build_brands_strip())
        root.addStretch()

        scroll.setWidget(inner)
        outer.addWidget(scroll)

    # ── Section: hero greeting + balances stat card ─────────────────────────

    def _build_hero(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(24)

        # Left 60%: greeting
        left = QVBoxLayout(); left.setSpacing(0); left.setContentsMargins(0, 0, 0, 0)
        eyebrow = QLabel("GOOD AFTERNOON"); eyebrow.setObjectName("Muted")
        left.addWidget(eyebrow)
        left.addSpacing(12)

        self.welcome = QLabel("Welcome back, Sofiane")
        self.welcome.setObjectName("H1")
        self.welcome.setWordWrap(True)
        left.addWidget(self.welcome)
        left.addSpacing(2)

        cursive = QLabel("ready when you are")
        cursive.setObjectName("Cursive")
        cursive.setWordWrap(True)
        left.addWidget(cursive)
        left.addSpacing(14)

        body = QLabel(
            "Generate, adapt, or fix ads — pick a workflow to start. "
            "Your last run finished a few minutes ago."
        )
        body.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 13px; line-height: 1.5;")
        body.setWordWrap(True)
        body.setMaximumWidth(460)
        left.addWidget(body)
        left.addSpacing(20)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10); btn_row.setContentsMargins(0, 0, 0, 0)
        start_btn = QPushButton("  Start Generating  ›")
        start_btn.setObjectName("PrimaryBtn")
        start_btn.setCursor(Qt.PointingHandCursor)
        start_btn.clicked.connect(self.open_generate.emit)
        cont_btn = QPushButton("  ▸  Continue last run")
        cont_btn.setObjectName("GhostBtn")
        cont_btn.setCursor(Qt.PointingHandCursor)
        cont_btn.clicked.connect(self.open_history.emit)
        btn_row.addWidget(start_btn); btn_row.addWidget(cont_btn); btn_row.addStretch()
        left.addLayout(btn_row)
        left.addStretch()

        left_w = QWidget(); left_w.setLayout(left)

        row.addWidget(left_w, 6)
        row.addWidget(self._build_stat_card(), 4)
        return row

    def _build_stat_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("StatCard")
        card.setMinimumWidth(320)
        card.setMaximumWidth(440)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(16)

        # Row 1 — Active provider balance
        prov_block = QVBoxLayout(); prov_block.setSpacing(10)
        prov_head = QHBoxLayout(); prov_head.setSpacing(8); prov_head.setContentsMargins(0, 0, 0, 0)
        prov_eyebrow = QLabel("ACTIVE PROVIDER BALANCE"); prov_eyebrow.setObjectName("Muted")
        prov_head.addWidget(prov_eyebrow); prov_head.addStretch()
        topup1 = QPushButton("Top up  ↗")
        topup1.setStyleSheet(
            f"background: transparent; border: none; color: {t.TEXT_MUTED}; "
            f"font-size: 11px; font-weight: 500;"
        )
        topup1.setCursor(Qt.PointingHandCursor)
        topup1.clicked.connect(self.open_settings.emit)
        prov_head.addWidget(topup1)
        prov_block.addLayout(prov_head)

        prov_row = QHBoxLayout(); prov_row.setSpacing(8); prov_row.setContentsMargins(0, 0, 0, 0)
        self.provider_chip = QLabel("MuAPI")
        self.provider_chip.setStyleSheet(
            f"background: {t.ACCENT_BG}; color: {t.ACCENT_STRONG}; "
            f"padding: 4px 10px; border-radius: 9999px; "
            f"font-size: 11px; font-weight: 600;"
        )
        self.provider_chip.setFixedHeight(22)
        self.provider_balance = QLabel("$24.15")
        self.provider_balance.setStyleSheet(
            f"color: {t.TEXT}; font-size: 24px; font-weight: 700; letter-spacing: -0.02em;"
        )
        prov_remaining = QLabel("remaining")
        prov_remaining.setStyleSheet(
            f"color: {t.TEXT_MUTED}; font-size: 12px; font-weight: 500;"
        )
        prov_row.addWidget(self.provider_chip, alignment=Qt.AlignVCenter)
        prov_row.addWidget(self.provider_balance, alignment=Qt.AlignVCenter)
        prov_row.addWidget(prov_remaining, alignment=Qt.AlignVCenter)
        prov_row.addStretch()
        prov_block.addLayout(prov_row)
        lay.addLayout(prov_block)

        lay.addWidget(self._divider())

        # Row 2 — Anthropic balance
        anth_block = QVBoxLayout(); anth_block.setSpacing(10)
        anth_head = QHBoxLayout(); anth_head.setSpacing(8); anth_head.setContentsMargins(0, 0, 0, 0)
        anth_eyebrow = QLabel("ANTHROPIC BALANCE"); anth_eyebrow.setObjectName("Muted")
        anth_head.addWidget(anth_eyebrow); anth_head.addStretch()
        topup2 = QPushButton("Top up  ↗")
        topup2.setStyleSheet(
            f"background: transparent; border: none; color: {t.TEXT_MUTED}; "
            f"font-size: 11px; font-weight: 500;"
        )
        topup2.setCursor(Qt.PointingHandCursor)
        topup2.clicked.connect(self.open_settings.emit)
        anth_head.addWidget(topup2)
        anth_block.addLayout(anth_head)

        anth_row = QHBoxLayout(); anth_row.setSpacing(8); anth_row.setContentsMargins(0, 0, 0, 0)
        self.anthropic_chip = QLabel("Anthropic")
        self.anthropic_chip.setStyleSheet(
            f"background: {t.ACCENT_BG}; color: {t.ACCENT_STRONG}; "
            f"padding: 4px 10px; border-radius: 9999px; "
            f"font-size: 11px; font-weight: 600;"
        )
        self.anthropic_chip.setFixedHeight(22)
        self.anthropic_balance = QLabel("$11.80")
        self.anthropic_balance.setStyleSheet(
            f"color: {t.TEXT}; font-size: 24px; font-weight: 700; letter-spacing: -0.02em;"
        )
        anth_remaining = QLabel("remaining")
        anth_remaining.setStyleSheet(
            f"color: {t.TEXT_MUTED}; font-size: 12px; font-weight: 500;"
        )
        anth_row.addWidget(self.anthropic_chip, alignment=Qt.AlignVCenter)
        anth_row.addWidget(self.anthropic_balance, alignment=Qt.AlignVCenter)
        anth_row.addWidget(anth_remaining, alignment=Qt.AlignVCenter)
        anth_row.addStretch()
        anth_block.addLayout(anth_row)
        lay.addLayout(anth_block)

        lay.addWidget(self._divider())

        # Row 3 — Estimated spend with period segmented control
        spend_block = QVBoxLayout(); spend_block.setSpacing(10)
        spend_head = QHBoxLayout(); spend_head.setSpacing(8); spend_head.setContentsMargins(0, 0, 0, 0)
        spend_eyebrow = QLabel("ESTIMATED SPEND"); spend_eyebrow.setObjectName("Muted")
        spend_head.addWidget(spend_eyebrow); spend_head.addStretch()

        # Segmented control container
        seg_wrap = QFrame()
        seg_wrap.setStyleSheet(
            f"background: {t.BG_CANVAS}; border: 1px solid {t.BORDER_MUTED}; "
            f"border-radius: 9999px;"
        )
        seg_layout = QHBoxLayout(seg_wrap)
        seg_layout.setContentsMargins(2, 2, 2, 2); seg_layout.setSpacing(0)
        self._seg_buttons: dict[str, QPushButton] = {}
        for period in ("1D", "1W", "1M", "1Y"):
            b = QPushButton(period)
            b.setObjectName("ChipOn" if period == self._spend_period else "ChipOff")
            b.setFixedHeight(22)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton { padding: 0 10px; font-size: 10px; font-weight: 600; "
                "letter-spacing: 0.04em; border: none; border-radius: 9999px; background: transparent; }"
                f"QPushButton[active='1'] {{ background: {t.ACCENT_BG}; color: {t.ACCENT_STRONG}; }}"
                f"QPushButton[active='0'] {{ color: {t.TEXT_MUTED}; }}"
                f"QPushButton[active='0']:hover {{ background: {t.BG_HOVER}; }}"
            )
            b.setProperty("active", "1" if period == self._spend_period else "0")
            b.clicked.connect(lambda _=None, p=period: self._on_period_change(p))
            seg_layout.addWidget(b)
            self._seg_buttons[period] = b

        spend_head.addWidget(seg_wrap)
        spend_block.addLayout(spend_head)

        self.spend_amount = QLabel("$32.40")
        self.spend_amount.setObjectName("BigNumber")
        spend_block.addWidget(self.spend_amount)

        # Usage bar
        track = QFrame()
        track.setFixedHeight(6)
        track.setStyleSheet(
            f"background: {t.BG_HOVER}; border-radius: 3px;"
        )
        tl = QHBoxLayout(track); tl.setContentsMargins(0, 0, 0, 0); tl.setSpacing(0)
        self.usage_fill = QFrame()
        self.usage_fill.setStyleSheet(f"background: {t.ACCENT}; border-radius: 3px;")
        self.usage_fill.setFixedHeight(6)
        tl.addWidget(self.usage_fill, 65)
        tl.addStretch(35)
        spend_block.addWidget(track)
        spend_block.addSpacing(2)

        self.usage_label = QLabel("65% of $50 budget")
        self.usage_label.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px;")
        spend_block.addWidget(self.usage_label)
        lay.addLayout(spend_block)

        return card

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background: {t.BORDER_MUTED};")
        return line

    def _on_period_change(self, period: str):
        self._spend_period = period
        for p, btn in self._seg_buttons.items():
            btn.setProperty("active", "1" if p == period else "0")
            btn.style().unpolish(btn); btn.style().polish(btn)
        self._refresh_spend()

    # ── Section: What are we making today? (3 tinted cards) ─────────────────

    def _build_workflows(self) -> QVBoxLayout:
        block = QVBoxLayout(); block.setContentsMargins(0, 0, 0, 0); block.setSpacing(0)
        head = QHBoxLayout(); head.setContentsMargins(0, 0, 0, 0)
        title = QLabel("What are we making today?"); title.setObjectName("H2")
        sub = QLabel("Pick a workflow")
        sub.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px; font-weight: 500;")
        head.addWidget(title); head.addStretch(); head.addWidget(sub, alignment=Qt.AlignBottom)
        block.addLayout(head)
        block.addSpacing(16)

        grid = QHBoxLayout(); grid.setSpacing(16)
        grid.addWidget(self._workflow_card(
            "01", "CardLavender", "generate", "Generate variations",
            "Drop a reference ad, get N variations in your style.",
            self.open_generate.emit,
        ), 1)
        grid.addWidget(self._workflow_card(
            "02", "CardRose", "adapt", "Adapt to a brand",
            "Re-render any ad for one of your brand DNAs.",
            self.open_adapt.emit,
        ), 1)
        grid.addWidget(self._workflow_card(
            "03", "CardViolet", "wrench", "Fix creatives",
            "Surgical fix on existing ads — wrong size, wrong color.",
            self.open_fix.emit,
        ), 1)
        block.addLayout(grid)
        return block

    def _workflow_card(self, number: str, frame_obj_name: str, icon: str,
                       title: str, body: str, on_click) -> QFrame:
        card = QFrame()
        card.setObjectName(frame_obj_name)
        card.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 28, 28, 28)
        lay.setSpacing(0)

        # Top row: number badge + icon halo
        top = QHBoxLayout(); top.setContentsMargins(0, 0, 0, 0)
        badge = QLabel(number)
        badge.setFixedSize(32, 32)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background: {t.BG_CANVAS}; color: {t.TEXT}; "
            f"border-radius: 16px; font-size: 12px; font-weight: 600;"
        )
        top.addWidget(badge); top.addStretch()

        halo = QFrame()
        halo.setFixedSize(56, 56)
        halo.setStyleSheet(
            f"background: rgba(255,255,255,0.7); border-radius: 28px;"
        )
        hl = QVBoxLayout(halo); hl.setContentsMargins(0, 0, 0, 0)
        ic = icon_label(icon, 24, t.ACCENT_STRONG); ic.setAlignment(Qt.AlignCenter)
        hl.addWidget(ic, alignment=Qt.AlignCenter)
        top.addWidget(halo)
        lay.addLayout(top)
        lay.addSpacing(36)

        h2 = QLabel(title); h2.setObjectName("H2")
        lay.addWidget(h2)
        lay.addSpacing(8)
        b = QLabel(body)
        b.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 13px; line-height: 1.5;")
        b.setWordWrap(True)
        lay.addWidget(b)
        lay.addSpacing(20)

        btn_row = QHBoxLayout(); btn_row.setSpacing(0); btn_row.setContentsMargins(0, 0, 0, 0)
        new_btn = QPushButton("  New  ›")
        new_btn.setObjectName("OnCardBtn")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(on_click)
        btn_row.addWidget(new_btn); btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()

        # Whole card click also triggers the workflow
        card.mousePressEvent = lambda _ev, fn=on_click: fn()
        return card

    # ── Section: recent runs (4 cards) ──────────────────────────────────────

    def _build_recent_runs(self) -> QVBoxLayout:
        block = QVBoxLayout(); block.setContentsMargins(0, 0, 0, 0); block.setSpacing(0)
        head = QHBoxLayout(); head.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Recent runs"); title.setObjectName("H2")
        view_all = QPushButton("View all  →")
        view_all.setStyleSheet(
            f"background: transparent; border: none; color: {t.TEXT_MUTED}; "
            f"font-size: 12px; font-weight: 500;"
        )
        view_all.setCursor(Qt.PointingHandCursor)
        view_all.clicked.connect(self.open_history.emit)
        head.addWidget(title); head.addStretch(); head.addWidget(view_all)
        block.addLayout(head)
        block.addSpacing(16)

        self.runs_grid = QHBoxLayout(); self.runs_grid.setSpacing(16); self.runs_grid.setContentsMargins(0, 0, 0, 0)
        block.addLayout(self.runs_grid)
        return block

    def _run_card(self, run: dict) -> QFrame:
        card = QFrame()
        card.setObjectName("RunCard")
        card.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(card); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(12)

        thumb_path = run.get("images", [None])[0] if run.get("images") else None
        thumb = QFrame()
        thumb.setMinimumHeight(140)
        if thumb_path and Path(str(thumb_path)).exists():
            from .widgets import round_pixmap
            tlbl = QLabel()
            tlbl.setPixmap(round_pixmap(Path(str(thumb_path)), 220, 180, 14))
            tlbl.setAlignment(Qt.AlignCenter)
            tl = QVBoxLayout(thumb); tl.setContentsMargins(0, 0, 0, 0)
            tl.addWidget(tlbl, alignment=Qt.AlignCenter)
        else:
            thumb.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {t.CARD_LAVENDER}, stop:1 {t.ACCENT_BG});"
                f"border-radius: 14px;"
            )
        lay.addWidget(thumb)

        header = QHBoxLayout(); header.setContentsMargins(0, 0, 0, 0)
        name = run.get("brand") or Path(run.get("reference") or "Run").stem
        n_lbl = QLabel(name[:18])
        n_lbl.setStyleSheet(f"color: {t.TEXT}; font-size: 14px; font-weight: 600;")
        run_type = (run.get("type") or "Generate").capitalize()
        type_pill = QLabel(run_type)
        type_pill.setStyleSheet(
            f"background: {t.ACCENT_BG}; color: {t.ACCENT_STRONG}; "
            f"padding: 4px 10px; border-radius: 9999px; font-size: 10px; font-weight: 600;"
        )
        header.addWidget(n_lbl); header.addStretch(); header.addWidget(type_pill)
        lay.addLayout(header)

        meta = QHBoxLayout(); meta.setContentsMargins(0, 0, 0, 0)
        dt = core.parse_run_dt(run.get("timestamp", ""))
        date_txt = dt.strftime("%d %b %Y") if dt else (run.get("timestamp", "")[:8])
        date = QLabel(date_txt)
        date.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px;")
        results = run.get("results", [])
        ok = sum(1 for r in results if r.get("status") == "ok")
        ratio = QLabel(f"{ok} of {len(results)}")
        ratio.setStyleSheet(f"color: {t.SUCCESS}; font-size: 11px; font-weight: 600;")
        meta.addWidget(date); meta.addStretch(); meta.addWidget(ratio)
        lay.addLayout(meta)

        card.mousePressEvent = lambda _ev, r=run: self.open_run.emit(r)
        return card

    # ── Section: brands quickstrip ──────────────────────────────────────────

    def _build_brands_strip(self) -> QVBoxLayout:
        block = QVBoxLayout(); block.setContentsMargins(0, 0, 0, 0); block.setSpacing(0)
        head = QHBoxLayout(); head.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Your brands"); title.setObjectName("H2")
        manage = QPushButton("Manage  →")
        manage.setStyleSheet(
            f"background: transparent; border: none; color: {t.TEXT_MUTED}; "
            f"font-size: 12px; font-weight: 500;"
        )
        manage.setCursor(Qt.PointingHandCursor)
        manage.clicked.connect(self.open_brands.emit)
        head.addWidget(title); head.addStretch(); head.addWidget(manage)
        block.addLayout(head)
        block.addSpacing(16)

        self.brands_strip = QHBoxLayout(); self.brands_strip.setSpacing(24); self.brands_strip.setContentsMargins(0, 0, 0, 0)
        self.brands_strip.addStretch()
        block.addLayout(self.brands_strip)
        return block

    def _brand_circle(self, name: str, image: str | None = None) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(8)
        wrap.setFixedWidth(64)

        circle = QFrame()
        circle.setFixedSize(52, 52)
        if image and Path(image).exists():
            from .widgets import round_pixmap
            lbl = QLabel(circle)
            lbl.setPixmap(round_pixmap(Path(image), 52, 52, 26))
            lbl.setFixedSize(52, 52)
        else:
            circle.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {t.CARD_LAVENDER}, stop:1 {t.ACCENT_BG});"
                f"border: 1px solid {t.BORDER_MUTED}; border-radius: 26px;"
            )
        col.addWidget(circle, alignment=Qt.AlignCenter)

        lbl = QLabel(name[:8])
        lbl.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px; font-weight: 500;")
        lbl.setAlignment(Qt.AlignCenter)
        col.addWidget(lbl)

        wrap.setCursor(Qt.PointingHandCursor)
        wrap.mousePressEvent = lambda _ev: self.open_brands.emit()
        return wrap

    def _add_brand_circle(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(8)
        wrap.setFixedWidth(64)

        circle = QFrame()
        circle.setFixedSize(52, 52)
        circle.setStyleSheet(
            f"background: {t.BG_CANVAS}; "
            f"border: 1px dashed {t.ACCENT}; border-radius: 26px;"
        )
        cl = QVBoxLayout(circle); cl.setContentsMargins(0, 0, 0, 0)
        plus = QLabel("+")
        plus.setAlignment(Qt.AlignCenter)
        plus.setStyleSheet(f"color: {t.ACCENT_STRONG}; font-size: 22px; font-weight: 500;")
        cl.addWidget(plus)
        col.addWidget(circle, alignment=Qt.AlignCenter)

        lbl = QLabel("Add")
        lbl.setStyleSheet(f"color: {t.ACCENT_STRONG}; font-size: 12px; font-weight: 500;")
        lbl.setAlignment(Qt.AlignCenter)
        col.addWidget(lbl)

        wrap.setCursor(Qt.PointingHandCursor)
        wrap.mousePressEvent = lambda _ev: self.open_brands.emit()
        return wrap

    # ── Refresh ─────────────────────────────────────────────────────────────

    def refresh(self):
        runs = core.list_runs()

        # Active provider chip
        active = core.get_active_provider_name()
        active_label = core.PROVIDER_LABELS.get(active, active.title())
        self.provider_chip.setText(active_label)

        # Spend (computed from runs filtered by period)
        self._all_runs = runs
        self._refresh_spend()

        # Recent runs grid
        while self.runs_grid.count():
            item = self.runs_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        for r in runs[:4]:
            self.runs_grid.addWidget(self._run_card(r), 1)
        # Pad with empty placeholders so grid stays at 4 cells
        for _ in range(max(0, 4 - len(runs[:4]))):
            placeholder = QFrame()
            placeholder.setObjectName("RunCard")
            placeholder.setMinimumHeight(220)
            pl = QVBoxLayout(placeholder); pl.setContentsMargins(14, 14, 14, 14)
            empty = QLabel("No run yet")
            empty.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
            empty.setAlignment(Qt.AlignCenter)
            pl.addStretch(); pl.addWidget(empty); pl.addStretch()
            self.runs_grid.addWidget(placeholder, 1)

        # Brands strip
        while self.brands_strip.count():
            item = self.brands_strip.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        brands = core.load_brands()
        names = sorted(brands.keys(), key=lambda s: s.lower())[:6]
        for n in names:
            img = brands[n].get("product_image", "")
            self.brands_strip.addWidget(self._brand_circle(n, img))
        self.brands_strip.addWidget(self._add_brand_circle())
        self.brands_strip.addStretch()

    def _refresh_spend(self):
        """Compute spend over the selected period."""
        from datetime import timedelta
        runs = getattr(self, "_all_runs", []) or []
        cutoff_days = {"1D": 1, "1W": 7, "1M": 30, "1Y": 365}.get(self._spend_period, 30)
        cutoff = datetime.now() - timedelta(days=cutoff_days)
        total = 0.0
        for r in runs:
            dt = core.parse_run_dt(r.get("timestamp", ""))
            if dt and dt >= cutoff:
                total += core.cost_for_run(r)
        self.spend_amount.setText(f"${total:.2f}")


# ─── Generate ───────────────────────────────────────────────────────────────

class GenerateWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, image, n, res, aspects, languages, workers, output_root, image_model):
        super().__init__()
        self._args = (image, n, res, aspects, languages, workers)
        self._output_root = output_root
        self._image_model = image_model
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        out = core.run_generation(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            on_out_dir=lambda p: self.out_dir_signal.emit(str(p)),
            should_cancel=lambda: self._cancel,
            output_root=self._output_root,
            image_model=self._image_model,
        )
        self.finished.emit(str(out) if out else "")


class GeneratePage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._worker: GenerateWorker | None = None
        self._thread: QThread | None = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Generate Variations"); h1.setObjectName("H1")
        sub = QLabel("Drop one reference ad, pick your params, get N variations.")
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        body = QHBoxLayout(); body.setSpacing(14)

        # Left: form (scrollable)
        form_card = Card()
        form_card.setMinimumWidth(520)
        card_lay = QVBoxLayout(form_card)
        card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        form_inner = QWidget()
        form = QVBoxLayout(form_inner)
        form.setContentsMargins(22, 20, 22, 20); form.setSpacing(16)
        scroll.setWidget(form_inner)
        card_lay.addWidget(scroll)

        l1 = QLabel("REFERENCE"); l1.setObjectName("Muted")
        form.addWidget(l1)
        self.drop = DropZone()
        form.addWidget(self.drop)

        params_row = QHBoxLayout(); params_row.setSpacing(14)
        col_n = QVBoxLayout(); col_n.setSpacing(6)
        col_n.addWidget(_field_label("Variations"))
        self.n = QSpinBox(); self.n.setRange(1, 15); self.n.setValue(5)
        col_n.addWidget(self.n)
        col_w = QVBoxLayout(); col_w.setSpacing(6)
        col_w.addWidget(_field_label("Workers"))
        self.workers = QSpinBox(); self.workers.setRange(1, 16); self.workers.setValue(8)
        col_w.addWidget(self.workers)
        params_row.addLayout(col_n, 1); params_row.addLayout(col_w, 1)
        form.addLayout(params_row)

        res_model_row = QHBoxLayout(); res_model_row.setSpacing(14)
        res_col = QVBoxLayout(); res_col.setSpacing(6)
        res_col.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS); self.res.setCurrentText("1k")
        res_col.addWidget(self.res)
        model_col = QVBoxLayout(); model_col.setSpacing(6)
        model_col.addWidget(_field_label("Model"))
        self.model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.model.addItem(label, userData=slug)
        self.model.setCurrentIndex(0)
        model_col.addWidget(self.model)
        res_model_row.addLayout(res_col, 1); res_model_row.addLayout(model_col, 1)
        form.addLayout(res_model_row)

        asp_l = QLabel("OUTPUT FORMATS  ·  pick one or more"); asp_l.setObjectName("Muted")
        form.addWidget(asp_l)
        self.asp = ChipGroup(core.ASPECTS, default=["1:1"])
        form.addWidget(self.asp)

        lang_l = QLabel("LANGUAGES  ·  pick one or more"); lang_l.setObjectName("Muted")
        form.addWidget(lang_l)
        self.lang = ChipGroup(core.LANGUAGES, default=["English"])
        form.addWidget(self.lang)

        out_l = QLabel("OUTPUT FOLDER"); out_l.setObjectName("Muted")
        form.addWidget(out_l)
        self.out_row = OutputFolderRow()
        form.addWidget(self.out_row)

        self.cost_label = QLabel()
        self.cost_label.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        form.addWidget(self.cost_label)
        self._update_cost()
        self.n.valueChanged.connect(self._update_cost)
        self.res.currentTextChanged.connect(self._update_cost)
        self.model.currentIndexChanged.connect(self._update_cost)
        self.asp.changed.connect(self._update_cost)
        self.lang.changed.connect(self._update_cost)

        form.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.go_btn = QPushButton("Generate")
        self.go_btn.setObjectName("PrimaryBtn")
        self.go_btn.setCursor(Qt.PointingHandCursor)
        self.go_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("GhostBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.hide()
        btn_row.addWidget(self.go_btn)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addStretch()
        form.addLayout(btn_row)
        form.addStretch()

        body.addWidget(form_card, 5)

        # Right: log + results
        right = QVBoxLayout(); right.setSpacing(14)

        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 18, 20, 18); llay.setSpacing(10)
        lhead = QHBoxLayout()
        lh = QLabel("Activity"); lh.setObjectName("H2")
        lhead.addWidget(lh); lhead.addStretch()
        self.live_pill = StatusPill("Idle", t.TEXT_MUTED)
        lhead.addWidget(self.live_pill)
        llay.addLayout(lhead)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(180)
        llay.addWidget(self.log)
        right.addWidget(log_card, 1)

        res_card = Card()
        rlay = QVBoxLayout(res_card); rlay.setContentsMargins(20, 18, 20, 18); rlay.setSpacing(10)
        rhead = QHBoxLayout()
        rh = QLabel("Results"); rh.setObjectName("H2")
        rhead.addWidget(rh); rhead.addStretch()
        self.open_folder_btn = QPushButton("Open folder")
        self.open_folder_btn.setObjectName("GhostBtn")
        self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_folder)
        rhead.addWidget(self.open_folder_btn)
        rlay.addLayout(rhead)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(12); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.grid_container)
        scroll.setMinimumHeight(220)
        rlay.addWidget(scroll)
        right.addWidget(res_card, 2)

        right_w = QWidget(); right_w.setLayout(right)
        body.addWidget(right_w, 5)

        root.addLayout(body, 1)

        self._out_dir: Path | None = None
        self._results_count = 0

    def _update_cost(self):
        n = self.n.value()
        m = max(1, len(self.asp.selected()))
        l = max(1, len(self.lang.selected()))
        provider = core.get_active_provider_name()
        model = self.model.currentData() or core.DEFAULT_IMAGE_MODEL
        price = core.cost_per_image(provider, model, self.res.currentText())
        total = n * m * l
        self.cost_label.setText(
            f"{total} images  ·  estimated ${total * price:.2f}  "
            f"({n} var × {l} lang × {m} format × ${price:.2f})"
        )

    def _start(self):
        path = self.drop.path()
        if not path:
            QMessageBox.warning(self, "Missing reference", "Drop a reference image first.")
            return
        aspects = self.asp.selected()
        if not aspects:
            QMessageBox.warning(self, "No format", "Pick at least one output format.")
            return
        languages = self.lang.selected()
        if not languages:
            QMessageBox.warning(self, "No language", "Pick at least one language.")
            return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first.")
            return

        self._clear_grid()
        self.log.clear()
        self._out_dir = None
        self._results_count = 0
        self.open_folder_btn.setEnabled(False)
        self.go_btn.hide(); self.cancel_btn.show()
        self.live_pill.setText("Running"); self.live_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

        self._thread = QThread()
        self._worker = GenerateWorker(
            path, self.n.value(), self.res.currentText(),
            aspects, languages, self.workers.value(),
            self.out_row.path(),
            self.model.currentData() or core.DEFAULT_IMAGE_MODEL,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._on_log)
        self._worker.result.connect(self._on_result)
        self._worker.out_dir_signal.connect(self._on_out_dir)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_out_dir(self, p: str):
        self._out_dir = Path(p)
        self.open_folder_btn.setEnabled(True)

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setText("Cancelling…")

    def _on_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        self.log.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    def _on_result(self, r: dict):
        if r.get("status") != "ok": return
        self._results_count += 1
        if self._out_dir:
            local = self._out_dir / r.get("file", "")
            if local.exists():
                thumb = ThumbLabel(local, 160, 160, 10)
                thumb.clicked.connect(lambda path=local: open_path(path))
                row = (self._results_count - 1) // 4
                col = (self._results_count - 1) % 4
                self.grid.addWidget(thumb, row, col)

    def _on_finished(self, out_dir: str):
        self._thread.quit()
        self._thread.wait()
        self.go_btn.show(); self.cancel_btn.hide()
        self.cancel_btn.setEnabled(True); self.cancel_btn.setText("Cancel")
        self.live_pill.setText("Done"); self.live_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )
        if out_dir:
            self._out_dir = Path(out_dir)
            self.open_folder_btn.setEnabled(True)

    def _open_folder(self):
        if self._out_dir: open_path(self._out_dir)

    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()


def _field_label(txt: str) -> QLabel:
    l = QLabel(txt); l.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px; font-weight: 600;")
    return l


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ─── History ────────────────────────────────────────────────────────────────

class HistoryPage(QWidget):
    open_run = Signal(object)

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(18)

        head = QHBoxLayout()
        tl = QVBoxLayout(); tl.setSpacing(2)
        h1 = QLabel("History"); h1.setObjectName("H1")
        sub = QLabel("Browse all your past generation runs.")
        sub.setObjectName("Dim")
        tl.addWidget(h1); tl.addWidget(sub)
        head.addLayout(tl); head.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(self.refresh)
        head.addWidget(self.search)
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("GhostBtn")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh)
        head.addWidget(refresh_btn)
        root.addLayout(head)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(14); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.container)
        root.addWidget(scroll, 1)

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        q = self.search.text().strip().lower()
        runs = core.list_runs()
        if q:
            runs = [r for r in runs if q in Path(r.get("reference", "")).name.lower()
                    or q in r["timestamp"].lower()]

        if not runs:
            empty = QLabel("No runs yet. Generate your first batch from the Generate page.")
            empty.setStyleSheet(f"color: {t.TEXT_MUTED}; padding: 40px;")
            empty.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(empty, 0, 0)
            return

        col_count = 3
        for i, r in enumerate(runs):
            card = self._run_card(r)
            self.grid.addWidget(card, i // col_count, i % col_count)

    def _run_card(self, r: dict) -> QWidget:
        card = Card()
        card.setCursor(Qt.PointingHandCursor)
        card.setFixedHeight(280)
        lay = QVBoxLayout(card); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)

        # thumbnail strip
        strip = QHBoxLayout(); strip.setSpacing(6)
        thumbs = r["images"][:3]
        if thumbs:
            for p in thumbs:
                t_ = ThumbLabel(p, 96, 110, 8)
                strip.addWidget(t_)
        else:
            ph = QLabel(); ph.setFixedHeight(110)
            ph.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 8px;")
            strip.addWidget(ph)
        strip.addStretch()
        lay.addLayout(strip)

        name_row = QHBoxLayout()
        name = Path(r.get("reference", "Reference")).name or "Reference"
        name_lbl = QLabel(name); name_lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        name_lbl.setWordWrap(False)
        name_row.addWidget(name_lbl); name_row.addStretch()
        p = r.get("params", {})
        ok = sum(1 for rr in r.get("results", []) if rr.get("status") == "ok")
        total = p.get("iterations", len(r.get("results", [])))
        status = "Completed" if ok == total and ok else ("Partial" if ok else "Failed")
        color = t.GREEN if status == "Completed" else (t.YELLOW if status == "Partial" else t.RED)
        name_row.addWidget(StatusPill(status, color))
        lay.addLayout(name_row)

        dt = core.parse_run_dt(r["timestamp"])
        meta = QLabel(
            f"{dt.strftime('%d %b %Y · %H:%M') if dt else r['timestamp']}  ·  "
            f"{ok}/{total} var  ·  {p.get('resolution','?')}  ·  {p.get('aspect_ratio','?')}"
        )
        meta.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        lay.addWidget(meta)

        actions = QHBoxLayout()
        open_btn = QPushButton("Open folder")
        open_btn.setObjectName("GhostBtn")
        open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(lambda _=None, path=r["dir"]: open_path(path))
        actions.addWidget(open_btn)
        view_btn = QPushButton("View")
        view_btn.setObjectName("PrimaryBtn")
        view_btn.setCursor(Qt.PointingHandCursor)
        view_btn.clicked.connect(lambda _=None, run=r: self.open_run.emit(run))
        actions.addWidget(view_btn)
        actions.addStretch()
        lay.addLayout(actions)

        card.mouseDoubleClickEvent = lambda _ev, run=r: self.open_run.emit(run)
        return card


# ─── Run Detail ─────────────────────────────────────────────────────────────

class RunDetailPage(QWidget):
    back = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(14)

        head = QHBoxLayout()
        back_btn = QPushButton("← Back")
        back_btn.setObjectName("GhostBtn")
        back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(self.back.emit)
        head.addWidget(back_btn); head.addSpacing(10)
        self.title = QLabel(""); self.title.setObjectName("H1")
        head.addWidget(self.title); head.addStretch()
        self.open_btn = QPushButton("Open folder"); self.open_btn.setObjectName("GhostBtn")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        head.addWidget(self.open_btn)
        root.addLayout(head)

        self.meta = QLabel(""); self.meta.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 13px;")
        root.addWidget(self.meta)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(14); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.container)
        root.addWidget(scroll, 1)

    def set_run(self, r: dict):
        self.title.setText(Path(r.get("reference", "Run")).name)
        dt = core.parse_run_dt(r["timestamp"])
        p = r.get("params", {})
        ok = sum(1 for rr in r.get("results", []) if rr.get("status") == "ok")
        total = p.get("iterations", len(r.get("results", [])))
        self.meta.setText(
            f"{dt.strftime('%d %b %Y · %H:%M') if dt else r['timestamp']}  ·  "
            f"{ok}/{total} variations  ·  {p.get('resolution','?')}  ·  {p.get('aspect_ratio','?')}  "
            f"·  ${core.cost_for_run(r):.2f}"
        )
        try:
            self.open_btn.clicked.disconnect()
        except Exception: pass
        self.open_btn.clicked.connect(lambda _=None, path=r["dir"]: open_path(path))

        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        brand_name = r.get("brand", "")
        default_aspect_list = p.get("aspects", [p.get("aspect_ratio", "1:1")])
        default_aspect = default_aspect_list[0] if isinstance(default_aspect_list, list) and default_aspect_list else "1:1"
        default_lang_list = p.get("languages", [p.get("language", "English")])
        default_lang = default_lang_list[0] if isinstance(default_lang_list, list) and default_lang_list else "English"
        by_file = {rr.get("file"): rr for rr in r.get("results", []) if rr.get("file")}

        cols = 4
        for i, img in enumerate(r["images"]):
            thumb = ThumbLabel(img, 180, 180, 12, show_fix=bool(brand_name))
            thumb.clicked.connect(lambda path=img: open_path(path))
            if brand_name:
                meta_r = by_file.get(Path(img).name, {})
                meta = {
                    "brand": brand_name,
                    "aspect": meta_r.get("aspect", default_aspect),
                    "language": meta_r.get("language", default_lang),
                }
                thumb.fix_requested.connect(
                    lambda path=img, m=meta: self._open_fix_dialog(path, m)
                )
            self.grid.addWidget(thumb, i // cols, i % cols)

    def _open_fix_dialog(self, path: Path, meta: dict):
        dlg = FixDialog(
            self, Path(path),
            default_brand=meta.get("brand", ""),
            default_aspect=meta.get("aspect", "1:1"),
            default_language=meta.get("language", "English"),
        )
        dlg.exec()


# ─── Settings ───────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    provider_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._key_inputs: dict[str, QLineEdit] = {}
        self._key_status: dict[str, QLabel] = {}
        self._radios: dict[str, QRadioButton] = {}
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Settings"); h1.setObjectName("H1")
        sub = QLabel("Pick your provider and store the keys you need.")
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        # Provider selector card
        prov_card = Card()
        plv = QVBoxLayout(prov_card); plv.setContentsMargins(22, 20, 22, 20); plv.setSpacing(10)
        plabel = QLabel("ACTIVE PROVIDER"); plabel.setObjectName("Muted")
        plv.addWidget(plabel)

        self._radio_group = QButtonGroup(self)
        self._radio_group.setExclusive(True)
        radio_row = QHBoxLayout(); radio_row.setSpacing(18)
        active = core.get_active_provider_name()
        for name in core.PROVIDERS:
            rb = QRadioButton(core.PROVIDER_LABELS[name])
            rb.setCursor(Qt.PointingHandCursor)
            rb.setChecked(name == active)
            rb.toggled.connect(lambda checked, n=name: checked and self._on_provider_changed(n))
            self._radio_group.addButton(rb)
            self._radios[name] = rb
            radio_row.addWidget(rb)
        radio_row.addStretch()
        plv.addLayout(radio_row)

        prov_tip = QLabel(
            "The active provider routes both image generation and the LLM that writes prompts."
        )
        prov_tip.setWordWrap(True)
        prov_tip.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        plv.addWidget(prov_tip)
        root.addWidget(prov_card)

        # Key cards (one per provider)
        for name in core.PROVIDERS:
            root.addWidget(self._build_key_card(name))

        # Anthropic key (Brand DNA Generator only — independent of provider)
        root.addWidget(self._build_anthropic_card())

        root.addStretch()

    def _build_anthropic_card(self) -> Card:
        card = Card()
        lay = QVBoxLayout(card); lay.setContentsMargins(22, 20, 22, 20); lay.setSpacing(10)

        title = QLabel("ANTHROPIC KEY  ·  Brand DNA Generator"); title.setObjectName("Muted")
        lay.addWidget(title)

        row = QHBoxLayout()
        self._anthropic_key = QLineEdit()
        self._anthropic_key.setEchoMode(QLineEdit.Password)
        self._anthropic_key.setPlaceholderText("paste your Anthropic API key (sk-ant-...)")
        self._anthropic_key.setText(core.get_anthropic_key())
        row.addWidget(self._anthropic_key)

        toggle = QPushButton("Show"); toggle.setObjectName("GhostBtn")
        toggle.setCursor(Qt.PointingHandCursor); toggle.setCheckable(True)
        def _tog(checked, e=self._anthropic_key, b=toggle):
            e.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            b.setText("Hide" if checked else "Show")
        toggle.toggled.connect(_tog)
        row.addWidget(toggle)

        save = QPushButton("Save"); save.setObjectName("PrimaryBtn")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._save_anthropic_key)
        row.addWidget(save)
        lay.addLayout(row)

        self._anthropic_status = QLabel("")
        self._anthropic_status.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        lay.addWidget(self._anthropic_status)

        tip = QLabel(
            "Used only by the Brand DNA Generator. Stored locally in <b>.env</b>; sent only to "
            "api.anthropic.com over HTTPS for vision analysis. Independent of the active image provider above."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        lay.addWidget(tip)
        return card

    def _save_anthropic_key(self) -> None:
        v = self._anthropic_key.text().strip()
        if not v:
            QMessageBox.warning(self, "Empty key", "Paste a key before saving.")
            return
        core.save_anthropic_key(v)
        self._anthropic_status.setText("Saved.")
        self._anthropic_status.setStyleSheet(f"color: {t.GREEN}; font-size: 12px;")
        QTimer.singleShot(2500, lambda: self._anthropic_status.setText(""))

    def _build_key_card(self, name: str) -> Card:
        card = Card()
        lay = QVBoxLayout(card); lay.setContentsMargins(22, 20, 22, 20); lay.setSpacing(10)

        title = QLabel(f"{core.PROVIDER_LABELS[name].upper()} KEY")
        title.setObjectName("Muted")
        lay.addWidget(title)

        row = QHBoxLayout()
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.Password)
        edit.setPlaceholderText(f"paste your {core.PROVIDER_LABELS[name]} key")
        edit.setText(core.get_provider_key(name))
        self._key_inputs[name] = edit
        row.addWidget(edit)

        toggle = QPushButton("Show"); toggle.setObjectName("GhostBtn")
        toggle.setCursor(Qt.PointingHandCursor); toggle.setCheckable(True)
        def _tog(checked, e=edit, b=toggle):
            e.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            b.setText("Hide" if checked else "Show")
        toggle.toggled.connect(_tog)
        row.addWidget(toggle)

        save = QPushButton("Save"); save.setObjectName("PrimaryBtn")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(lambda _=False, n=name: self._save_key(n))
        row.addWidget(save)

        lay.addLayout(row)

        status = QLabel(""); status.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        self._key_status[name] = status
        lay.addWidget(status)

        host = "api.muapi.ai" if name == "muapi" else "api.kie.ai"
        tip = QLabel(
            f"Key is stored locally in <b>.env</b>. It is sent only to {host} "
            f"over HTTPS for uploads, LLM prompting, and image generation."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        lay.addWidget(tip)
        return card

    def _on_provider_changed(self, name: str) -> None:
        core.save_active_provider(name)
        self.provider_changed.emit(name)

    def _save_key(self, name: str) -> None:
        edit = self._key_inputs[name]
        status = self._key_status[name]
        v = edit.text().strip()
        if not v:
            QMessageBox.warning(self, "Empty key", "Paste a key before saving.")
            return
        core.save_provider_key(name, v)
        status.setText("Saved.")
        status.setStyleSheet(f"color: {t.GREEN}; font-size: 12px;")
        QTimer.singleShot(2500, lambda s=status: s.setText(""))
        self.provider_changed.emit(core.get_active_provider_name())

    def refresh(self) -> None:
        active = core.get_active_provider_name()
        for name, rb in self._radios.items():
            rb.blockSignals(True)
            rb.setChecked(name == active)
            rb.blockSignals(False)
        for name, edit in self._key_inputs.items():
            edit.setText(core.get_provider_key(name))


# ─── Brand editor dialog ────────────────────────────────────────────────────

class BrandEditorDialog(QDialog):
    def __init__(self, parent=None, brand: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Brand DNA")
        self.setModal(True)
        self.resize(680, 720)
        self._original_name = (brand or {}).get("name")
        initial_paths = (brand or {}).get("product_images") or (
            [(brand or {}).get("product_image")] if (brand or {}).get("product_image") else []
        )
        self._product_paths: list[str] = [p for p in initial_paths if p and Path(p).exists()]
        self._build(brand or {})

    def _build(self, brand: dict):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24); root.setSpacing(14)

        title = QLabel("Edit Brand DNA" if self._original_name else "New Brand DNA")
        title.setObjectName("H1")
        root.addWidget(title)
        sub = QLabel("One Brand DNA = one brand + its product. Used to adapt ads at scale.")
        sub.setObjectName("Dim")
        root.addWidget(sub)
        root.addSpacing(4)

        name_lbl = QLabel("NAME"); name_lbl.setObjectName("Muted")
        root.addWidget(name_lbl)
        self.name = QLineEdit(brand.get("name", ""))
        self.name.setPlaceholderText("e.g. Atlas Eyewear")
        root.addWidget(self.name)

        dna_lbl = QLabel("BRAND DNA (TEXT)"); dna_lbl.setObjectName("Muted")
        root.addWidget(dna_lbl)
        self.dna = QTextEdit()
        self.dna.setPlainText(brand.get("dna", ""))
        self.dna.setPlaceholderText(
            "Everything that defines this brand + product: name, product name/description, "
            "color palette, typography, tone of voice, target language, copy style, signature phrases, "
            "things to avoid…"
        )
        self.dna.setMinimumHeight(220)
        root.addWidget(self.dna, 1)

        prod_lbl = QLabel("PRODUCT IMAGES  ·  pouch, stick, bottle, sachet, …")
        prod_lbl.setObjectName("Muted")
        root.addWidget(prod_lbl)
        self.products = ProductImagesEditor(self._product_paths)
        self.products.changed.connect(self._on_products_changed)
        root.addWidget(self.products)
        prod_tip = QLabel(
            "Add every form your product can appear in. Ads with multiple forms "
            "(pouch + stick) will be mapped to your available images."
        )
        prod_tip.setWordWrap(True)
        prod_tip.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        root.addWidget(prod_tip)

        root.addSpacing(6)
        btns = QHBoxLayout(); btns.setSpacing(10)
        if self._original_name:
            del_btn = QPushButton("Delete")
            del_btn.setObjectName("GhostBtn")
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(
                f"QPushButton#GhostBtn {{ color: {t.RED}; border-color: {t.RED}44; }}"
                f"QPushButton#GhostBtn:hover {{ background: {t.RED}22; }}"
            )
            del_btn.clicked.connect(self._delete)
            btns.addWidget(del_btn)
        btns.addStretch()
        cancel = QPushButton("Cancel"); cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save"); save.setObjectName("PrimaryBtn")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._save)
        btns.addWidget(cancel); btns.addWidget(save)
        root.addLayout(btns)

    def _on_products_changed(self, paths: list):
        self._product_paths = list(paths)

    def _save(self):
        name = self.name.text().strip()
        dna = self.dna.toPlainText().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Enter a brand name.")
            return
        if not dna:
            QMessageBox.warning(self, "Missing DNA", "Describe the brand DNA.")
            return
        paths = self.products.paths()
        if not paths:
            QMessageBox.warning(self, "Missing product image",
                                "Add at least one product image.")
            return
        try:
            core.save_brand(name, dna, paths, original_name=self._original_name)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.accept()

    def _delete(self):
        if not self._original_name:
            return
        ok = QMessageBox.question(
            self, "Delete brand",
            f"Delete '{self._original_name}'? This cannot be undone.",
        )
        if ok == QMessageBox.Yes:
            core.delete_brand(self._original_name)
            self.done(2)  # sentinel: deleted


# ─── Brands page ────────────────────────────────────────────────────────────

class BrandsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QHBoxLayout()
        tl = QVBoxLayout(); tl.setSpacing(2)
        h1 = QLabel("Brands"); h1.setObjectName("H1")
        sub = QLabel("Reusable Brand DNA presets — used by the Adapt feature.")
        sub.setObjectName("Dim")
        tl.addWidget(h1); tl.addWidget(sub)
        head.addLayout(tl); head.addStretch()

        gen_btn = QPushButton("  Generate from sources")
        gen_btn.setObjectName("GhostBtn")
        gen_btn.setCursor(Qt.PointingHandCursor)
        gen_btn.clicked.connect(self._generate_dna)
        head.addWidget(gen_btn)

        new_btn = QPushButton("  + New Brand")
        new_btn.setObjectName("PrimaryBtn")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self._new)
        head.addWidget(new_btn)
        root.addLayout(head)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(14); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.container)
        root.addWidget(scroll, 1)

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        brands = core.load_brands()
        if not brands:
            empty = Card()
            el = QVBoxLayout(empty); el.setContentsMargins(40, 40, 40, 40); el.setAlignment(Qt.AlignCenter)
            ic = icon_label("brand", 36, t.TEXT_MUTED); ic.setAlignment(Qt.AlignCenter)
            el.addWidget(ic, alignment=Qt.AlignCenter)
            t1 = QLabel("No brands yet"); t1.setObjectName("H2"); t1.setAlignment(Qt.AlignCenter)
            el.addWidget(t1)
            t2 = QLabel("Create a Brand DNA to start adapting ads at scale.")
            t2.setStyleSheet(f"color: {t.TEXT_MUTED};"); t2.setAlignment(Qt.AlignCenter)
            el.addWidget(t2)
            go = QPushButton("+ New Brand"); go.setObjectName("PrimaryBtn")
            go.setCursor(Qt.PointingHandCursor); go.setFixedWidth(160)
            go.clicked.connect(self._new)
            el.addWidget(go, alignment=Qt.AlignCenter)
            self.grid.addWidget(empty, 0, 0)
            return

        col_count = 3
        for i, (name, brand) in enumerate(sorted(brands.items(), key=lambda kv: kv[0].lower())):
            self.grid.addWidget(self._brand_card(name, brand), i // col_count, i % col_count)

    def _brand_card(self, name: str, brand: dict) -> QWidget:
        card = Card()
        card.setCursor(Qt.PointingHandCursor)
        card.setFixedHeight(260)
        lay = QVBoxLayout(card); lay.setContentsMargins(14, 14, 14, 14); lay.setSpacing(10)

        imgs = [Path(p) for p in brand.get("product_images", []) if Path(p).exists()][:3]
        row = QHBoxLayout(); row.setSpacing(6)
        if imgs:
            for p in imgs:
                row.addWidget(ThumbLabel(p, 76, 76, 8))
        else:
            ph = QLabel(); ph.setFixedSize(76, 76)
            ph.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 8px;")
            row.addWidget(ph)
        row.addStretch()
        row_host = QWidget(); row_host.setLayout(row)
        lay.addWidget(row_host)

        title = QLabel(name); title.setStyleSheet("font-weight: 700; font-size: 14px;")
        lay.addWidget(title)

        dna = (brand.get("dna", "") or "").strip().replace("\n", " ")
        snippet = (dna[:110] + "…") if len(dna) > 110 else dna
        snippet_lbl = QLabel(snippet)
        snippet_lbl.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        snippet_lbl.setWordWrap(True)
        lay.addWidget(snippet_lbl, 1)

        actions = QHBoxLayout()
        edit_btn = QPushButton("Edit"); edit_btn.setObjectName("GhostBtn")
        edit_btn.setCursor(Qt.PointingHandCursor)
        edit_btn.clicked.connect(lambda _=None, n=name: self._edit(n))
        actions.addWidget(edit_btn); actions.addStretch()
        lay.addLayout(actions)

        card.mouseDoubleClickEvent = lambda _ev, n=name: self._edit(n)
        return card

    def _new(self):
        dlg = BrandEditorDialog(self)
        if dlg.exec() in (QDialog.Accepted, 2):
            self.refresh()

    def _edit(self, name: str):
        brand = core.load_brands().get(name)
        if not brand: return
        dlg = BrandEditorDialog(self, brand)
        if dlg.exec() in (QDialog.Accepted, 2):
            self.refresh()

    def _generate_dna(self):
        if not core.is_anthropic_configured():
            QMessageBox.warning(
                self,
                "Anthropic key required",
                "The Brand DNA Generator uses Claude directly for vision analysis. "
                "Add your Anthropic API key in Settings to continue.",
            )
            return
        dlg = BrandDNAGeneratorDialog(self)
        if dlg.exec() in (QDialog.Accepted, 2):
            self.refresh()


# ─── Brand DNA Generator dialog ─────────────────────────────────────────────

class BrandDNAWorker(QObject):
    log = Signal(str, str)
    finished = Signal(object, str)   # (BrandDNAResult or None, error message)

    def __init__(self, sources, output_root: str | None):
        super().__init__()
        self._sources = sources
        self._output_root = output_root
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            import brand_dna
            result = brand_dna.generate(
                self._sources,
                output_root=Path(self._output_root) if self._output_root else None,
                on_log=lambda lvl, msg: self.log.emit(lvl, msg),
                should_cancel=lambda: self._cancel,
            )
            self.finished.emit(result, "")
        except Exception as e:
            self.finished.emit(None, str(e))


class BrandDNAGeneratorDialog(QDialog):
    DOC_EXTS = {".pdf", ".docx", ".txt", ".md"}
    IMG_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Brand DNA")
        self.setModal(True)
        self.resize(820, 720)
        self._creative_paths: list[str] = []
        self._document_paths: list[str] = []
        self._result = None
        self._worker: BrandDNAWorker | None = None
        self._thread: QThread | None = None
        self._candidate_checks: list[tuple[QPushButton, object]] = []
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(20, 20, 20, 20); root.setSpacing(14)

        title = QLabel("Generate Brand DNA"); title.setObjectName("H1")
        sub = QLabel("Drop a website URL, creative assets, or a guidelines document. "
                     "Claude reads everything and writes a structured Brand DNA.")
        sub.setObjectName("Dim"); sub.setWordWrap(True)
        root.addWidget(title); root.addWidget(sub)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step_sources())
        self._stack.addWidget(self._build_step_progress())
        self._stack.addWidget(self._build_step_review())
        root.addWidget(self._stack, 1)

    # ── Step 1: Sources ────────────────────────────────────────────────────

    def _build_step_sources(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(14)

        url_lbl = QLabel("WEBSITE URLs  ·  one per line, optional"); url_lbl.setObjectName("Muted")
        lay.addWidget(url_lbl)
        self._urls_edit = QPlainTextEdit()
        self._urls_edit.setPlaceholderText("https://brand.com\nhttps://brand.com/about")
        self._urls_edit.setMaximumHeight(90)
        lay.addWidget(self._urls_edit)

        # Two columns: creatives + documents
        cols = QHBoxLayout(); cols.setSpacing(14)

        cre_card = Card()
        cre_lay = QVBoxLayout(cre_card); cre_lay.setContentsMargins(14, 14, 14, 14); cre_lay.setSpacing(8)
        cre_lay.addWidget(_field_label("CREATIVE ASSETS  ·  PNG, JPG, WEBP"))
        self._cre_list = QListWidget()
        self._cre_list.setMinimumHeight(140)
        cre_lay.addWidget(self._cre_list, 1)
        cre_btns = QHBoxLayout()
        add_cre = QPushButton("Add files…"); add_cre.setObjectName("GhostBtn")
        add_cre.clicked.connect(lambda: self._pick_files(self._cre_list, self._creative_paths,
                                                          "Add creative files",
                                                          "Images (*.png *.jpg *.jpeg *.webp *.bmp)"))
        rm_cre = QPushButton("Remove"); rm_cre.setObjectName("GhostBtn")
        rm_cre.clicked.connect(lambda: self._remove_selected(self._cre_list, self._creative_paths))
        cre_btns.addWidget(add_cre); cre_btns.addWidget(rm_cre); cre_btns.addStretch()
        cre_lay.addLayout(cre_btns)
        cols.addWidget(cre_card, 1)

        doc_card = Card()
        doc_lay = QVBoxLayout(doc_card); doc_lay.setContentsMargins(14, 14, 14, 14); doc_lay.setSpacing(8)
        doc_lay.addWidget(_field_label("BRAND DOCUMENTS  ·  PDF, DOCX, TXT"))
        self._doc_list = QListWidget()
        self._doc_list.setMinimumHeight(140)
        doc_lay.addWidget(self._doc_list, 1)
        doc_btns = QHBoxLayout()
        add_doc = QPushButton("Add files…"); add_doc.setObjectName("GhostBtn")
        add_doc.clicked.connect(lambda: self._pick_files(self._doc_list, self._document_paths,
                                                          "Add documents",
                                                          "Documents (*.pdf *.docx *.txt *.md)"))
        rm_doc = QPushButton("Remove"); rm_doc.setObjectName("GhostBtn")
        rm_doc.clicked.connect(lambda: self._remove_selected(self._doc_list, self._document_paths))
        doc_btns.addWidget(add_doc); doc_btns.addWidget(rm_doc); doc_btns.addStretch()
        doc_lay.addLayout(doc_btns)
        cols.addWidget(doc_card, 1)

        lay.addLayout(cols, 1)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancel"); cancel.setObjectName("GhostBtn")
        cancel.clicked.connect(self.reject)
        gen = QPushButton("Generate"); gen.setObjectName("PrimaryBtn")
        gen.setCursor(Qt.PointingHandCursor)
        gen.clicked.connect(self._start_generation)
        actions.addStretch(); actions.addWidget(cancel); actions.addWidget(gen)
        lay.addLayout(actions)

        return w

    def _pick_files(self, lst: QListWidget, store: list[str], title: str, filt: str):
        files, _ = QFileDialog.getOpenFileNames(self, title, "", filt)
        for f in files:
            if f and f not in store:
                store.append(f)
                lst.addItem(Path(f).name)

    def _remove_selected(self, lst: QListWidget, store: list[str]):
        for item in lst.selectedItems():
            row = lst.row(item)
            lst.takeItem(row)
            if 0 <= row < len(store):
                store.pop(row)

    # ── Step 2: Progress ───────────────────────────────────────────────────

    def _build_step_progress(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(14)

        head = QHBoxLayout()
        h = QLabel("Analyzing sources…"); h.setObjectName("H2")
        self._pill = StatusPill("Running", t.ACCENT)
        head.addWidget(h); head.addStretch(); head.addWidget(self._pill)
        lay.addLayout(head)

        self._log = QPlainTextEdit(); self._log.setReadOnly(True); self._log.setMinimumHeight(360)
        lay.addWidget(self._log, 1)

        actions = QHBoxLayout()
        self._cancel_run = QPushButton("Cancel"); self._cancel_run.setObjectName("GhostBtn")
        self._cancel_run.clicked.connect(self._cancel_generation)
        actions.addStretch(); actions.addWidget(self._cancel_run)
        lay.addLayout(actions)
        return w

    def _start_generation(self):
        try:
            import brand_dna
        except ImportError as e:
            QMessageBox.critical(self, "Missing dependency",
                                  f"brand_dna package failed to import: {e}")
            return

        urls = [u.strip() for u in self._urls_edit.toPlainText().splitlines() if u.strip()]
        for u in urls:
            if not u.startswith(("http://", "https://")):
                QMessageBox.warning(self, "Invalid URL",
                                    f"URL must start with http:// or https://\n→ {u}")
                return
        if not (urls or self._creative_paths or self._document_paths):
            QMessageBox.warning(self, "No sources",
                                "Add at least one URL, creative file, or document.")
            return

        sources = brand_dna.Sources(
            urls=urls,
            creative_files=[Path(p) for p in self._creative_paths],
            document_files=[Path(p) for p in self._document_paths],
        )
        self._stack.setCurrentIndex(1)
        self._log.clear()
        self._cancel_run.setEnabled(True); self._cancel_run.setText("Cancel")

        self._thread = QThread()
        self._worker = BrandDNAWorker(sources, str(core.get_output_dir()))
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        self._log.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    def _cancel_generation(self):
        if self._worker:
            self._worker.cancel()
        self._cancel_run.setEnabled(False)
        self._cancel_run.setText("Cancelling…")

    def _on_finished(self, result, error: str):
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        if error or result is None or not getattr(result, "dna_text", ""):
            self._pill.setText("Failed")
            self._pill.setStyleSheet(
                f"background: {t.RED}22; color: {t.RED}; padding: 4px 10px; "
                f"border-radius: 10px; font-size: 11px; font-weight: 600;"
            )
            self._cancel_run.setEnabled(True); self._cancel_run.setText("Back")
            self._cancel_run.clicked.disconnect()
            self._cancel_run.clicked.connect(lambda: self._stack.setCurrentIndex(0))
            if error:
                QMessageBox.critical(self, "Brand DNA failed", error)
            else:
                QMessageBox.warning(self, "Brand DNA cancelled",
                                     "No result was produced.")
            return
        self._result = result
        self._pill.setText("Done")
        self._pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )
        self._populate_review()
        self._stack.setCurrentIndex(2)

    # ── Step 3: Review ─────────────────────────────────────────────────────

    def _build_step_review(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(14)

        cols = QHBoxLayout(); cols.setSpacing(14)

        # Left: name + DNA editor
        left = QVBoxLayout(); left.setSpacing(10)
        left.addWidget(_field_label("BRAND NAME"))
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Atlas Eyewear")
        left.addWidget(self._name_edit)
        left.addWidget(_field_label("BRAND DNA  ·  edit before saving"))
        self._dna_edit = QTextEdit()
        self._dna_edit.setMinimumHeight(420)
        left.addWidget(self._dna_edit, 1)
        left_w = QWidget(); left_w.setLayout(left)
        cols.addWidget(left_w, 6)

        # Right: candidate images
        right = QVBoxLayout(); right.setSpacing(10)
        right.addWidget(_field_label("PRODUCT IMAGE CANDIDATES  ·  pick the ones to attach"))
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self._cand_container = QWidget()
        self._cand_grid = QGridLayout(self._cand_container)
        self._cand_grid.setSpacing(8); self._cand_grid.setContentsMargins(0, 0, 0, 0)
        self._cand_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self._cand_container)
        scroll.setMinimumWidth(280)
        right.addWidget(scroll, 1)
        right_w = QWidget(); right_w.setLayout(right)
        cols.addWidget(right_w, 4)

        lay.addLayout(cols, 1)

        actions = QHBoxLayout()
        back = QPushButton("Back"); back.setObjectName("GhostBtn")
        back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        save = QPushButton("Save brand"); save.setObjectName("PrimaryBtn")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._save_brand)
        actions.addWidget(back); actions.addStretch(); actions.addWidget(save)
        lay.addLayout(actions)
        return w

    def _populate_review(self):
        self._dna_edit.setPlainText(self._result.dna_text)
        # Clear existing
        while self._cand_grid.count():
            item = self._cand_grid.takeAt(0)
            wid = item.widget()
            if wid: wid.deleteLater()
        self._candidate_checks.clear()

        # Show product-tagged candidates first, then others.
        cands = sorted(
            self._result.candidates,
            key=lambda c: (0 if c.tag == "product" else 1 if c.tag == "lifestyle" else 2),
        )
        for i, cand in enumerate(cands[:24]):
            wrap = QFrame()
            wrap.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 10px; padding: 6px;")
            wl = QVBoxLayout(wrap); wl.setSpacing(4); wl.setContentsMargins(6, 6, 6, 6)
            try:
                thumb = ThumbLabel(Path(cand.path), 110, 110, 8)
                wl.addWidget(thumb, alignment=Qt.AlignCenter)
            except Exception:
                ph = QLabel("?"); ph.setFixedSize(110, 110)
                ph.setAlignment(Qt.AlignCenter)
                wl.addWidget(ph)
            tag_lbl = QLabel(cand.tag or "?")
            tag_lbl.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 10px;")
            tag_lbl.setAlignment(Qt.AlignCenter)
            wl.addWidget(tag_lbl)
            chk = QPushButton("✓ Keep" if cand.tag == "product" else "Keep")
            chk.setCheckable(True)
            chk.setChecked(cand.tag == "product")
            chk.setCursor(Qt.PointingHandCursor)
            chk.setObjectName("PrimaryBtn" if cand.tag == "product" else "GhostBtn")
            chk.toggled.connect(
                lambda checked, b=chk: (
                    b.setObjectName("PrimaryBtn" if checked else "GhostBtn"),
                    b.setText("✓ Keep" if checked else "Keep"),
                    b.style().unpolish(b), b.style().polish(b),
                )
            )
            wl.addWidget(chk)
            self._cand_grid.addWidget(wrap, i // 2, i % 2)
            self._candidate_checks.append((chk, cand))

    def _save_brand(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Give the brand a name.")
            return
        dna_text = self._dna_edit.toPlainText().strip()
        if not dna_text:
            QMessageBox.warning(self, "Empty DNA", "The DNA text is empty.")
            return
        kept = [str(cand.path) for chk, cand in self._candidate_checks if chk.isChecked()]
        if not kept:
            QMessageBox.warning(self, "No product image",
                                "Pick at least one image to use as the brand's reference.")
            return
        try:
            core.save_brand(name=name, dna=dna_text, product_image_sources=kept)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.accept()


# ─── Fix tool ───────────────────────────────────────────────────────────────

FIX_PRESETS = {
    "Wrong size":       "The product is the wrong size in the scene — adjust its scale to fit naturally.",
    "Wrong design":     "The product packaging / design was altered — re-render it to match the brand product images exactly.",
    "Text overlaps product": "A copy / text element overlaps the product. Reposition or resize only the conflicting element so the text is fully legible and does not touch the product. Keep the text content identical.",
    "Wrong colors":     "The colors of the product or a specific element drifted — fix only that element's color.",
    "Missing element":  "An element is missing from the scene — add it back while keeping everything else unchanged.",
}


class FixWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    finished = Signal(str)

    def __init__(self, image_path, brand_name, issue, resolution, aspect, language, image_model):
        super().__init__()
        self._args = (image_path, brand_name, issue, resolution, aspect, language)
        self._image_model = image_model
        self._cancel = False

    def cancel(self): self._cancel = True

    def run(self):
        out = core.run_fix(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            should_cancel=lambda: self._cancel,
            image_model=self._image_model,
        )
        self.finished.emit(str(out) if out else "")


class FixDialog(QDialog):
    fixed_path = Signal(str)

    def __init__(self, parent, image_path: Path, default_brand: str = "",
                 default_aspect: str = "1:1", default_language: str = "English"):
        super().__init__(parent)
        self.setWindowTitle("Fix creative")
        self.setModal(True)
        self.resize(640, 760)
        self._image_path = Path(image_path)
        self._default_brand = default_brand
        self._default_aspect = default_aspect
        self._default_language = default_language
        self._worker = None
        self._thread = None
        self._build()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(22, 20, 22, 20); root.setSpacing(14)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Fix creative"); h1.setObjectName("H1")
        sub = QLabel("Describe only what's wrong. Everything else stays identical.")
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        prev_wrap = QHBoxLayout(); prev_wrap.setSpacing(12)
        self.preview = ThumbLabel(self._image_path, 140, 140, 10)
        prev_wrap.addWidget(self.preview)
        info_box = QVBoxLayout(); info_box.setSpacing(4)
        fname = QLabel(self._image_path.name)
        fname.setStyleSheet("font-weight: 600; font-size: 13px;")
        info_box.addWidget(fname)
        fmeta = QLabel(f"{self._default_language}  ·  {self._default_aspect}")
        fmeta.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        info_box.addWidget(fmeta)
        info_box.addStretch()
        prev_wrap.addLayout(info_box, 1)
        root.addLayout(prev_wrap)

        bl = QLabel("BRAND"); bl.setObjectName("Muted")
        root.addWidget(bl)
        self.brand_combo = QComboBox()
        brands = core.load_brands()
        names = sorted(brands.keys(), key=lambda s: s.lower())
        if not names:
            self.brand_combo.addItem("— No brands —"); self.brand_combo.setEnabled(False)
        else:
            self.brand_combo.addItems(names)
            if self._default_brand in names:
                self.brand_combo.setCurrentText(self._default_brand)
        root.addWidget(self.brand_combo)

        root.addSpacing(4)
        pl = QLabel("QUICK ISSUES"); pl.setObjectName("Muted")
        root.addWidget(pl)
        preset_row = QHBoxLayout(); preset_row.setSpacing(6)
        for label in FIX_PRESETS:
            btn = QPushButton(label); btn.setObjectName("ChipOff")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=None, lbl=label: self._apply_preset(lbl))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        preset_wrap = QWidget(); preset_wrap.setLayout(preset_row)
        root.addWidget(preset_wrap)

        il = QLabel("WHAT NEEDS TO BE FIXED"); il.setObjectName("Muted")
        root.addWidget(il)
        self.issue = QTextEdit()
        self.issue.setPlaceholderText(
            "e.g., the sachet is too small — make it fill the bottom-right corner, "
            "match the packaging of the second brand image exactly."
        )
        self.issue.setMinimumHeight(120)
        root.addWidget(self.issue, 1)

        row = QHBoxLayout(); row.setSpacing(14)
        col_a = QVBoxLayout(); col_a.setSpacing(6)
        col_a.addWidget(_field_label("Aspect"))
        self.asp = QComboBox(); self.asp.addItems(core.ASPECTS)
        if self._default_aspect in core.ASPECTS:
            self.asp.setCurrentText(self._default_aspect)
        col_a.addWidget(self.asp)
        col_r = QVBoxLayout(); col_r.setSpacing(6)
        col_r.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS)
        self.res.setCurrentText("1k")
        col_r.addWidget(self.res)
        col_m = QVBoxLayout(); col_m.setSpacing(6)
        col_m.addWidget(_field_label("Model"))
        self.model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.model.addItem(label, userData=slug)
        self.model.setCurrentIndex(0)
        col_m.addWidget(self.model)
        row.addLayout(col_a, 1); row.addLayout(col_r, 1); row.addLayout(col_m, 1)
        root.addLayout(row)

        log_head = QHBoxLayout()
        lh = QLabel("Activity"); lh.setObjectName("H3")
        log_head.addWidget(lh); log_head.addStretch()
        self.pill = StatusPill("Idle", t.TEXT_MUTED)
        log_head.addWidget(self.pill)
        root.addLayout(log_head)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(120)
        root.addWidget(self.log)

        btns = QHBoxLayout(); btns.setSpacing(10)
        cancel = QPushButton("Cancel"); cancel.setObjectName("GhostBtn")
        cancel.setCursor(Qt.PointingHandCursor); cancel.clicked.connect(self.reject)
        btns.addWidget(cancel); btns.addStretch()
        self.go_btn = QPushButton("Fix"); self.go_btn.setObjectName("PrimaryBtn")
        self.go_btn.setCursor(Qt.PointingHandCursor); self.go_btn.clicked.connect(self._start)
        btns.addWidget(self.go_btn)
        root.addLayout(btns)

    def _apply_preset(self, label: str):
        current = self.issue.toPlainText().strip()
        boiler = FIX_PRESETS[label]
        self.issue.setPlainText(current + "\n\n" + boiler if current else boiler)
        self.issue.setFocus()
        c = self.issue.textCursor(); c.movePosition(c.MoveOperation.End); self.issue.setTextCursor(c)

    def _start(self):
        if not self.brand_combo.isEnabled():
            QMessageBox.warning(self, "No brand", "Create a Brand DNA first."); return
        issue = self.issue.toPlainText().strip()
        if not issue:
            QMessageBox.warning(self, "Describe the issue", "Write what needs to be fixed."); return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first."); return

        self.go_btn.setEnabled(False); self.go_btn.setText("Fixing…")
        self.pill.setText("Running")
        self.pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

        self._thread = QThread()
        self._worker = FixWorker(
            str(self._image_path), self.brand_combo.currentText(), issue,
            self.res.currentText(), self.asp.currentText(), self._default_language,
            self.model.currentData() or core.DEFAULT_IMAGE_MODEL,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._on_log)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _on_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        self.log.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    def _on_finished(self, out_path: str):
        self._thread.quit(); self._thread.wait()
        self.go_btn.setEnabled(True); self.go_btn.setText("Fix")
        if out_path:
            self.pill.setText("Done")
            self.pill.setStyleSheet(
                f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
                f"border-radius: 10px; font-size: 11px; font-weight: 600;"
            )
            self.fixed_path.emit(out_path)
            QTimer.singleShot(600, self.accept)
        else:
            self.pill.setText("Failed")
            self.pill.setStyleSheet(
                f"background: {t.RED}22; color: {t.RED}; padding: 4px 10px; "
                f"border-radius: 10px; font-size: 11px; font-weight: 600;"
            )


class BatchFixWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    finished = Signal(int)

    def __init__(self, image_paths, brand_name, issue, resolution, aspect, language, workers, image_model):
        super().__init__()
        self._args = (image_paths, brand_name, issue, resolution, aspect, language, workers)
        self._image_model = image_model
        self._cancel = False

    def cancel(self): self._cancel = True

    def run(self):
        out = core.run_batch_fix(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            should_cancel=lambda: self._cancel,
            image_model=self._image_model,
        )
        self.finished.emit(len(out))


class BatchFixPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._worker: BatchFixWorker | None = None
        self._thread: QThread | None = None
        self._results_count = 0
        self._build()
        self.refresh_brands()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Fix creatives"); h1.setObjectName("H1")
        sub = QLabel("Drop one or many images, describe the common issue, fix them in one batch.")
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        body = QHBoxLayout(); body.setSpacing(14)

        form_card = Card()
        form_card.setMinimumWidth(520)
        card_lay = QVBoxLayout(form_card); card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        form_inner = QWidget()
        form = QVBoxLayout(form_inner)
        form.setContentsMargins(22, 20, 22, 20); form.setSpacing(16)
        scroll.setWidget(form_inner)
        card_lay.addWidget(scroll)

        bl = QLabel("BRAND DNA"); bl.setObjectName("Muted")
        form.addWidget(bl)
        self.brand_combo = QComboBox()
        form.addWidget(self.brand_combo)

        il = QLabel("IMAGES TO FIX  ·  files only"); il.setObjectName("Muted")
        form.addWidget(il)
        self.drop = FolderDropZone()
        form.addWidget(self.drop)

        pl = QLabel("QUICK ISSUES"); pl.setObjectName("Muted")
        form.addWidget(pl)
        preset_row = QHBoxLayout(); preset_row.setSpacing(6)
        for label in FIX_PRESETS:
            btn = QPushButton(label); btn.setObjectName("ChipOff")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=None, lbl=label: self._apply_preset(lbl))
            preset_row.addWidget(btn)
        preset_row.addStretch()
        preset_wrap = QWidget(); preset_wrap.setLayout(preset_row)
        form.addWidget(preset_wrap)

        tl = QLabel("WHAT NEEDS TO BE FIXED  ·  applied to all dropped images"); tl.setObjectName("Muted")
        form.addWidget(tl)
        self.issue = QTextEdit()
        self.issue.setPlaceholderText(
            "e.g., the sachet is too small and deformed on all of these ads — "
            "scale it up and render it exactly like the brand's packaging."
        )
        self.issue.setMinimumHeight(130)
        form.addWidget(self.issue)

        params = QHBoxLayout(); params.setSpacing(14)
        c1 = QVBoxLayout(); c1.setSpacing(6)
        c1.addWidget(_field_label("Workers"))
        self.workers = QSpinBox(); self.workers.setRange(1, 16); self.workers.setValue(8)
        c1.addWidget(self.workers)
        c2 = QVBoxLayout(); c2.setSpacing(6)
        c2.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS); self.res.setCurrentText("1k")
        c2.addWidget(self.res)
        c3 = QVBoxLayout(); c3.setSpacing(6)
        c3.addWidget(_field_label("Aspect"))
        self.asp = QComboBox(); self.asp.addItems(core.ASPECTS); self.asp.setCurrentText("1:1")
        c3.addWidget(self.asp)
        c4 = QVBoxLayout(); c4.setSpacing(6)
        c4.addWidget(_field_label("Language"))
        self.lang = QComboBox(); self.lang.addItems(core.LANGUAGES); self.lang.setCurrentText("English")
        c4.addWidget(self.lang)
        c5 = QVBoxLayout(); c5.setSpacing(6)
        c5.addWidget(_field_label("Model"))
        self.model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.model.addItem(label, userData=slug)
        self.model.setCurrentIndex(0)
        c5.addWidget(self.model)
        params.addLayout(c1, 1); params.addLayout(c2, 1); params.addLayout(c3, 1)
        params.addLayout(c4, 1); params.addLayout(c5, 1)
        form.addLayout(params)

        self.cost_label = QLabel()
        self.cost_label.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        form.addWidget(self.cost_label)

        form.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.go_btn = QPushButton("Fix all"); self.go_btn.setObjectName("PrimaryBtn")
        self.go_btn.setCursor(Qt.PointingHandCursor); self.go_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.setObjectName("GhostBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor); self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.hide()
        btn_row.addWidget(self.go_btn); btn_row.addWidget(self.cancel_btn); btn_row.addStretch()
        form.addLayout(btn_row)
        form.addStretch()

        body.addWidget(form_card, 5)

        right = QVBoxLayout(); right.setSpacing(14)
        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 18, 20, 18); llay.setSpacing(10)
        lhead = QHBoxLayout()
        lh = QLabel("Activity"); lh.setObjectName("H2")
        lhead.addWidget(lh); lhead.addStretch()
        self.live_pill = StatusPill("Idle", t.TEXT_MUTED)
        lhead.addWidget(self.live_pill)
        llay.addLayout(lhead)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(180)
        llay.addWidget(self.log)
        right.addWidget(log_card, 1)

        res_card = Card()
        rlay = QVBoxLayout(res_card); rlay.setContentsMargins(20, 18, 20, 18); rlay.setSpacing(10)
        rhead = QHBoxLayout()
        rh = QLabel("Fixed"); rh.setObjectName("H2")
        rhead.addWidget(rh); rhead.addStretch()
        rlay.addLayout(rhead)
        scroll2 = QScrollArea(); scroll2.setWidgetResizable(True)
        scroll2.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(12); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll2.setWidget(self.grid_container)
        scroll2.setMinimumHeight(240)
        rlay.addWidget(scroll2)
        right.addWidget(res_card, 2)

        right_w = QWidget(); right_w.setLayout(right)
        body.addWidget(right_w, 5)
        root.addLayout(body, 1)

        self.drop.paths_changed.connect(lambda _=None: self._update_cost())
        self.res.currentTextChanged.connect(self._update_cost)
        self.model.currentIndexChanged.connect(self._update_cost)
        self._update_cost()

    def refresh_brands(self):
        current = self.brand_combo.currentText()
        self.brand_combo.blockSignals(True)
        self.brand_combo.clear()
        brands = core.load_brands()
        names = sorted(brands.keys(), key=lambda s: s.lower())
        if not names:
            self.brand_combo.addItem("— No brands (open Brands first) —")
            self.brand_combo.setEnabled(False)
        else:
            self.brand_combo.setEnabled(True)
            self.brand_combo.addItems(names)
            if current in names:
                self.brand_combo.setCurrentText(current)
        self.brand_combo.blockSignals(False)

    def _apply_preset(self, label: str):
        current = self.issue.toPlainText().strip()
        boiler = FIX_PRESETS[label]
        self.issue.setPlainText(current + "\n\n" + boiler if current else boiler)
        self.issue.setFocus()
        c = self.issue.textCursor(); c.movePosition(c.MoveOperation.End); self.issue.setTextCursor(c)

    def _update_cost(self):
        n = len(self.drop.paths())
        provider = core.get_active_provider_name()
        model = self.model.currentData() or core.DEFAULT_IMAGE_MODEL
        price = core.cost_per_image(provider, model, self.res.currentText())
        if n > 0:
            self.cost_label.setText(
                f"{n} image{'s' if n != 1 else ''}  ·  estimated ${n * price:.2f} (+ {n} LLM calls)"
            )
        else:
            self.cost_label.setText("Drop images to estimate cost.")

    def _start(self):
        images = self.drop.paths()
        if not images:
            QMessageBox.warning(self, "No images", "Drop files to fix first."); return
        if not self.brand_combo.isEnabled():
            QMessageBox.warning(self, "No brand", "Create a Brand DNA first."); return
        issue = self.issue.toPlainText().strip()
        if not issue:
            QMessageBox.warning(self, "Describe the issue", "Write what needs to be fixed."); return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first."); return

        self._clear_grid()
        self.log.clear()
        self._results_count = 0
        self.go_btn.hide(); self.cancel_btn.show()
        self.live_pill.setText("Running")
        self.live_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

        self._thread = QThread()
        self._worker = BatchFixWorker(
            images, self.brand_combo.currentText(), issue,
            self.res.currentText(), self.asp.currentText(),
            self.lang.currentText(), self.workers.value(),
            self.model.currentData() or core.DEFAULT_IMAGE_MODEL,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._on_log)
        self._worker.result.connect(self._on_result)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _cancel(self):
        if self._worker: self._worker.cancel()
        self.cancel_btn.setEnabled(False); self.cancel_btn.setText("Cancelling…")

    def _on_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        self.log.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    def _on_result(self, r: dict):
        if r.get("status") != "ok": return
        self._results_count += 1
        local = Path(r.get("path", ""))
        if local.exists():
            thumb = ThumbLabel(local, 160, 160, 10)
            thumb.clicked.connect(lambda path=local: open_path(path))
            thumb.setToolTip(r.get("source", ""))
            row = (self._results_count - 1) // 4
            col = (self._results_count - 1) % 4
            self.grid.addWidget(thumb, row, col)

    def _on_finished(self, count: int):
        self._thread.quit(); self._thread.wait()
        self.go_btn.show(); self.cancel_btn.hide()
        self.cancel_btn.setEnabled(True); self.cancel_btn.setText("Cancel")
        color = t.GREEN if count else t.RED
        label = "Done" if count else "Failed"
        self.live_pill.setText(label)
        self.live_pill.setStyleSheet(
            f"background: {color}22; color: {color}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()


# ─── Adapt page ─────────────────────────────────────────────────────────────

class AdaptWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, ad_paths, brand_name, res, aspects, languages, workers, output_root, image_model):
        super().__init__()
        self._args = (ad_paths, brand_name, res, aspects, languages, workers)
        self._output_root = output_root
        self._image_model = image_model
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        out = core.run_adapt(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            on_out_dir=lambda p: self.out_dir_signal.emit(str(p)),
            should_cancel=lambda: self._cancel,
            output_root=self._output_root,
            image_model=self._image_model,
        )
        self.finished.emit(str(out) if out else "")


class AdaptPage(QWidget):
    open_brands = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._worker: AdaptWorker | None = None
        self._thread: QThread | None = None
        self._out_dir: Path | None = None
        self._results_count = 0
        self._build()
        self.refresh_brands()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Adapt Ads"); h1.setObjectName("H1")
        sub = QLabel("Drop a folder of ads. They get recreated for the selected brand — product, copy, DA, language.")
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        body = QHBoxLayout(); body.setSpacing(14)

        # Left: form (scrollable)
        form_card = Card()
        form_card.setMinimumWidth(520)
        card_lay = QVBoxLayout(form_card)
        card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        form_inner = QWidget()
        form = QVBoxLayout(form_inner)
        form.setContentsMargins(22, 20, 22, 20); form.setSpacing(16)
        scroll.setWidget(form_inner)
        card_lay.addWidget(scroll)

        bl = QLabel("BRAND DNA"); bl.setObjectName("Muted")
        form.addWidget(bl)
        brow = QHBoxLayout(); brow.setSpacing(8)
        self.brand_combo = QComboBox()
        brow.addWidget(self.brand_combo, 1)
        manage_btn = QPushButton("Manage")
        manage_btn.setObjectName("GhostBtn")
        manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.clicked.connect(self.open_brands.emit)
        brow.addWidget(manage_btn)
        form.addLayout(brow)

        self.brand_preview = QFrame()
        self.brand_preview.setObjectName("CardFlat")
        self.brand_preview.setStyleSheet(
            f"background: {t.BG_INPUT}; border-radius: 12px;"
        )
        bp = QHBoxLayout(self.brand_preview); bp.setContentsMargins(12, 12, 12, 12); bp.setSpacing(12)
        self.brand_thumb = QLabel()
        self.brand_thumb.setFixedSize(52, 52)
        self.brand_thumb.setStyleSheet(f"background: {t.BORDER}; border-radius: 8px;")
        bp.addWidget(self.brand_thumb)
        bdesc = QVBoxLayout(); bdesc.setSpacing(2)
        self.brand_name_lbl = QLabel(""); self.brand_name_lbl.setStyleSheet("font-weight: 600; font-size: 13px;")
        self.brand_dna_lbl = QLabel(""); self.brand_dna_lbl.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        self.brand_dna_lbl.setWordWrap(True)
        bdesc.addWidget(self.brand_name_lbl); bdesc.addWidget(self.brand_dna_lbl)
        bp.addLayout(bdesc, 1)
        form.addWidget(self.brand_preview)

        sl = QLabel("SOURCE ADS  ·  files or folder"); sl.setObjectName("Muted")
        form.addWidget(sl)
        self.drop = FolderDropZone()
        form.addWidget(self.drop)

        params_row = QHBoxLayout(); params_row.setSpacing(14)
        col_w = QVBoxLayout(); col_w.setSpacing(6)
        col_w.addWidget(_field_label("Workers"))
        self.workers = QSpinBox(); self.workers.setRange(1, 16); self.workers.setValue(8)
        col_w.addWidget(self.workers)
        col_r = QVBoxLayout(); col_r.setSpacing(6)
        col_r.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS); self.res.setCurrentText("1k")
        col_r.addWidget(self.res)
        col_m = QVBoxLayout(); col_m.setSpacing(6)
        col_m.addWidget(_field_label("Model"))
        self.model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.model.addItem(label, userData=slug)
        self.model.setCurrentIndex(0)
        col_m.addWidget(self.model)
        params_row.addLayout(col_w, 1); params_row.addLayout(col_r, 1); params_row.addLayout(col_m, 1)
        form.addLayout(params_row)

        asp_l = QLabel("OUTPUT FORMATS  ·  pick one or more"); asp_l.setObjectName("Muted")
        form.addWidget(asp_l)
        self.asp = ChipGroup(core.ASPECTS, default=["1:1"])
        form.addWidget(self.asp)

        lang_l = QLabel("LANGUAGES  ·  pick one or more"); lang_l.setObjectName("Muted")
        form.addWidget(lang_l)
        self.lang = ChipGroup(core.LANGUAGES, default=["English"])
        form.addWidget(self.lang)

        out_l = QLabel("OUTPUT FOLDER"); out_l.setObjectName("Muted")
        form.addWidget(out_l)
        self.out_row = OutputFolderRow()
        form.addWidget(self.out_row)

        self.cost_label = QLabel()
        self.cost_label.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        form.addWidget(self.cost_label)
        form.addSpacing(8)

        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.go_btn = QPushButton("Adapt folder")
        self.go_btn.setObjectName("PrimaryBtn")
        self.go_btn.setCursor(Qt.PointingHandCursor)
        self.go_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("GhostBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel)
        self.cancel_btn.hide()
        btn_row.addWidget(self.go_btn); btn_row.addWidget(self.cancel_btn); btn_row.addStretch()
        form.addLayout(btn_row)
        form.addStretch()

        body.addWidget(form_card, 5)

        # Right: log + results
        right = QVBoxLayout(); right.setSpacing(14)

        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 18, 20, 18); llay.setSpacing(10)
        lhead = QHBoxLayout()
        lh = QLabel("Activity"); lh.setObjectName("H2")
        lhead.addWidget(lh); lhead.addStretch()
        self.live_pill = StatusPill("Idle", t.TEXT_MUTED)
        lhead.addWidget(self.live_pill)
        llay.addLayout(lhead)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(180)
        llay.addWidget(self.log)
        right.addWidget(log_card, 1)

        res_card = Card()
        rlay = QVBoxLayout(res_card); rlay.setContentsMargins(20, 18, 20, 18); rlay.setSpacing(10)
        rhead = QHBoxLayout()
        rh = QLabel("Results"); rh.setObjectName("H2")
        rhead.addWidget(rh); rhead.addStretch()
        self.open_folder_btn = QPushButton("Open folder"); self.open_folder_btn.setObjectName("GhostBtn")
        self.open_folder_btn.setCursor(Qt.PointingHandCursor); self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_folder)
        rhead.addWidget(self.open_folder_btn)
        rlay.addLayout(rhead)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(12); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.grid_container)
        scroll.setMinimumHeight(220)
        rlay.addWidget(scroll)
        right.addWidget(res_card, 2)

        right_w = QWidget(); right_w.setLayout(right)
        body.addWidget(right_w, 5)

        root.addLayout(body, 1)

        self.brand_combo.currentIndexChanged.connect(self._on_brand_changed)
        self.drop.paths_changed.connect(lambda _=None: self._update_cost())
        self.res.currentTextChanged.connect(self._update_cost)
        self.model.currentIndexChanged.connect(self._update_cost)
        self.asp.changed.connect(self._update_cost)
        self.lang.changed.connect(self._update_cost)

    def refresh_brands(self):
        current = self.brand_combo.currentText()
        self.brand_combo.blockSignals(True)
        self.brand_combo.clear()
        brands = core.load_brands()
        names = sorted(brands.keys(), key=lambda s: s.lower())
        if not names:
            self.brand_combo.addItem("— No brands yet (Manage →) —")
            self.brand_combo.setEnabled(False)
        else:
            self.brand_combo.setEnabled(True)
            self.brand_combo.addItems(names)
            if current in names:
                self.brand_combo.setCurrentText(current)
        self.brand_combo.blockSignals(False)
        self._on_brand_changed()

    def _on_brand_changed(self):
        brands = core.load_brands()
        name = self.brand_combo.currentText() if self.brand_combo.isEnabled() else ""
        b = brands.get(name)
        if not b:
            self.brand_name_lbl.setText("No brand selected")
            self.brand_dna_lbl.setText("Create a Brand DNA from the Brands page first.")
            self.brand_thumb.clear()
            self.brand_thumb.setStyleSheet(f"background: {t.BORDER}; border-radius: 8px;")
        else:
            self.brand_name_lbl.setText(b["name"])
            dna = b["dna"].replace("\n", " ")
            self.brand_dna_lbl.setText((dna[:140] + "…") if len(dna) > 140 else dna)
            pi = b.get("product_image", "")
            if pi and Path(pi).exists():
                from .widgets import round_pixmap
                self.brand_thumb.setPixmap(round_pixmap(Path(pi), 52, 52, 8))
                self.brand_thumb.setStyleSheet("background: transparent;")
            else:
                self.brand_thumb.clear()
                self.brand_thumb.setStyleSheet(f"background: {t.BORDER}; border-radius: 8px;")
        self._update_cost()

    def _update_cost(self):
        from .widgets import round_pixmap  # noqa
        n = len(self.drop.paths())
        m = max(1, len(self.asp.selected()))
        l = max(1, len(self.lang.selected()))
        provider = core.get_active_provider_name()
        model = self.model.currentData() or core.DEFAULT_IMAGE_MODEL
        price = core.cost_per_image(provider, model, self.res.currentText())
        if n > 0:
            total = n * m * l
            self.cost_label.setText(
                f"{n} ads × {l} lang × {m} format = {total} images  ·  "
                f"estimated ${total * price:.2f} (+ {n * l} LLM calls)"
            )
        else:
            self.cost_label.setText("Drop files or a folder to estimate cost.")

    def _start(self):
        ad_paths = self.drop.paths()
        if not ad_paths:
            QMessageBox.warning(self, "Missing ads", "Drop files or a folder first."); return
        if not self.brand_combo.isEnabled():
            QMessageBox.warning(self, "No brand", "Create a Brand DNA first."); return
        aspects = self.asp.selected()
        if not aspects:
            QMessageBox.warning(self, "No format", "Pick at least one output format."); return
        languages = self.lang.selected()
        if not languages:
            QMessageBox.warning(self, "No language", "Pick at least one language."); return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first."); return

        self._clear_grid()
        self.log.clear()
        self._out_dir = None
        self._results_count = 0
        self.open_folder_btn.setEnabled(False)
        self.go_btn.hide(); self.cancel_btn.show()
        self.live_pill.setText("Running")
        self.live_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

        self._thread = QThread()
        self._worker = AdaptWorker(
            ad_paths, self.brand_combo.currentText(),
            self.res.currentText(), aspects, languages, self.workers.value(),
            self.out_row.path(),
            self.model.currentData() or core.DEFAULT_IMAGE_MODEL,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._on_log)
        self._worker.result.connect(self._on_result)
        self._worker.out_dir_signal.connect(self._on_out_dir)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _cancel(self):
        if self._worker: self._worker.cancel()
        self.cancel_btn.setEnabled(False); self.cancel_btn.setText("Cancelling…")

    def _on_out_dir(self, p: str):
        self._out_dir = Path(p)
        self.open_folder_btn.setEnabled(True)

    def _on_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        self.log.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    def _on_result(self, r: dict):
        if r.get("status") != "ok": return
        self._results_count += 1
        if self._out_dir:
            local = self._out_dir / r.get("file", "")
            if local.exists():
                thumb = ThumbLabel(local, 160, 160, 10, show_fix=True)
                thumb.clicked.connect(lambda path=local: open_path(path))
                meta = {
                    "brand": self.brand_combo.currentText(),
                    "aspect": r.get("aspect", "1:1"),
                    "language": r.get("language", "English"),
                }
                thumb.fix_requested.connect(
                    lambda path=local, m=meta: self._open_fix_dialog(path, m)
                )
                thumb.setToolTip(r.get("source", ""))
                row = (self._results_count - 1) // 4
                col = (self._results_count - 1) % 4
                self.grid.addWidget(thumb, row, col)

    def _open_fix_dialog(self, path: Path, meta: dict):
        dlg = FixDialog(
            self, Path(path),
            default_brand=meta.get("brand", ""),
            default_aspect=meta.get("aspect", "1:1"),
            default_language=meta.get("language", "English"),
        )
        dlg.fixed_path.connect(lambda p: self._on_log("OK", f"Fix saved: {Path(p).name}"))
        dlg.exec()

    def _on_finished(self, out_dir: str):
        self._thread.quit(); self._thread.wait()
        self.go_btn.show(); self.cancel_btn.hide()
        self.cancel_btn.setEnabled(True); self.cancel_btn.setText("Cancel")
        self.live_pill.setText("Done")
        self.live_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )
        if out_dir:
            self._out_dir = Path(out_dir)
            self.open_folder_btn.setEnabled(True)

    def _open_folder(self):
        if self._out_dir: open_path(self._out_dir)

    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
