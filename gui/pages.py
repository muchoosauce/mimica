from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
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
        self._apply_welcome_name()
        QTimer.singleShot(0, self._prompt_for_name_if_missing)

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

        self.welcome = QLabel("Welcome back")
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

        # Active provider chip (kept visible — used by refresh() to show which
        # provider is in use). The balance figure used to live next to it but
        # was hardcoded; no provider exposes a public balance endpoint, so it
        # has been removed rather than show stale numbers.
        self.provider_chip = QLabel("MuAPI")
        self.provider_chip.setStyleSheet(
            f"background: {t.ACCENT_BG}; color: {t.ACCENT_STRONG}; "
            f"padding: 4px 10px; border-radius: 9999px; "
            f"font-size: 11px; font-weight: 600;"
        )
        self.provider_chip.setFixedHeight(22)
        prov_chip_row = QHBoxLayout(); prov_chip_row.setContentsMargins(0, 0, 0, 0)
        prov_chip_row.addWidget(QLabel("ACTIVE PROVIDER"), alignment=Qt.AlignVCenter)
        prov_chip_row.itemAt(0).widget().setObjectName("Muted")
        prov_chip_row.addSpacing(8)
        prov_chip_row.addWidget(self.provider_chip, alignment=Qt.AlignVCenter)
        prov_chip_row.addStretch()
        lay.addLayout(prov_chip_row)

        lay.addWidget(self._divider())

        # Estimated spend with period segmented control
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

    def _apply_welcome_name(self):
        name = core.load_user_name()
        self.welcome.setText(f"Welcome back, {name}" if name else "Welcome back")

    def _prompt_for_name_if_missing(self):
        if core.load_user_name():
            return
        name, ok = QInputDialog.getText(
            self, "Welcome", "What's your name?\nWe'll greet you on the dashboard.",
        )
        if ok and name.strip():
            core.save_user_name(name)
            self._apply_welcome_name()

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
        # Dark elevated bg with mono-style number — readable on the dark cards.
        badge.setStyleSheet(
            f"background: {t.BG_ELEVATED}; color: {t.TEXT_MUTED}; "
            f"border: 1px solid {t.BORDER_MUTED}; "
            f"border-radius: 16px; font-size: 12px; font-weight: 600;"
        )
        top.addWidget(badge); top.addStretch()

        halo = QFrame()
        halo.setFixedSize(56, 56)
        # Subtle violet glass tint instead of opaque white — sits clean
        # on the dark cards.
        halo.setStyleSheet(
            f"background: rgba(124, 92, 255, 0.14); "
            f"border: 1px solid rgba(124, 92, 255, 0.22); "
            f"border-radius: 28px;"
        )
        hl = QVBoxLayout(halo); hl.setContentsMargins(0, 0, 0, 0)
        ic = icon_label(icon, 24, t.ACCENT_SOFT); ic.setAlignment(Qt.AlignCenter)
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
    resume_broll = Signal(dict)  # Emit when user wants to resume a B-roll image
                                 # run at the approval / video-generation step.

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._current_run: dict | None = None
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
        # Visible only on B-roll image runs that haven't generated videos yet —
        # lets the user pick up where they left off (approve + animate) instead
        # of orphaning the run.
        self.continue_btn = QPushButton("Continue to videos →")
        self.continue_btn.setObjectName("PrimaryBtn")
        self.continue_btn.setCursor(Qt.PointingHandCursor)
        self.continue_btn.clicked.connect(self._emit_resume)
        self.continue_btn.hide()
        head.addWidget(self.continue_btn)
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
        self._current_run = r
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

        # Show the Continue-to-videos shortcut iff this is a B-roll image run
        # whose images haven't been animated yet (no .mp4 files in the dir).
        is_broll_images = r.get("type") == "broll_images"
        has_videos = any(str(img).lower().endswith(".mp4") for img in r.get("images", []))
        if is_broll_images and not has_videos and ok > 0:
            self.continue_btn.show()
        else:
            self.continue_btn.hide()

    def _emit_resume(self):
        if self._current_run:
            self.resume_broll.emit(self._current_run)

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
                f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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

        # Right: manual product image upload (you attach your own packshot —
        # we don't pre-pick from scraped candidates).
        right = QVBoxLayout(); right.setSpacing(10)
        right.addWidget(_field_label("PRODUCT IMAGES  ·  attach your own packshots"))
        hint = QLabel(
            "Click + to upload your own product photos. The Brand DNA above was "
            "generated from the sources you provided — these images are what the "
            "brand will use as references for ad generation."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        right.addWidget(hint)
        self._product_images_editor = ProductImagesEditor()
        right.addWidget(self._product_images_editor)
        right.addStretch()
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
        # Scraped candidates are intentionally not surfaced to the user —
        # they were used in-memory by Claude for visual context during DNA
        # generation, then the on-disk copies are wiped. The user attaches
        # their own product images via the editor on the right.

    def _save_brand(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Give the brand a name.")
            return
        dna_text = self._dna_edit.toPlainText().strip()
        if not dna_text:
            QMessageBox.warning(self, "Empty DNA", "The DNA text is empty.")
            return
        kept = self._product_images_editor.paths()
        if not kept:
            QMessageBox.warning(self, "No product image",
                                "Upload at least one product image (click + on the right).")
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
                f"border-radius: 999px; font-size: 11px; font-weight: 600;"
            )
            self.fixed_path.emit(out_path)
            QTimer.singleShot(600, self.accept)
        else:
            self.pill.setText("Failed")
            self.pill.setStyleSheet(
                f"background: {t.RED}22; color: {t.RED}; padding: 4px 10px; "
                f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
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


# ─── B-Roll ─────────────────────────────────────────────────────────────────

class BRollImageWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, brand_name, specs, counts, res, aspect, workers, output_root, image_model):
        super().__init__()
        self._args = (brand_name, specs, counts, res, aspect, workers)
        self._output_root = output_root
        self._image_model = image_model
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        out = core.run_broll_images(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            on_out_dir=lambda p: self.out_dir_signal.emit(str(p)),
            should_cancel=lambda: self._cancel,
            output_root=self._output_root,
            image_model=self._image_model,
        )
        self.finished.emit(str(out) if out else "")


class BRollVideoWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, images_run_dir, approved_indexes, duration, aspect, workers,
                 video_model, sound):
        super().__init__()
        self._args = (images_run_dir, approved_indexes, duration, aspect, workers)
        self._video_model = video_model
        self._sound = sound
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        out = core.run_broll_videos(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            on_out_dir=lambda p: self.out_dir_signal.emit(str(p)),
            should_cancel=lambda: self._cancel,
            video_model=self._video_model,
            sound=self._sound,
        )
        self.finished.emit(str(out) if out else "")


class _ApprovalThumb(QFrame):
    """Image thumbnail with an Approve / Reject toggle. Default = approved."""
    toggled = Signal(int, bool)

    def __init__(self, idx: int, path: Path, category: str, parent=None):
        super().__init__(parent)
        self.idx = idx
        self._approved = True
        self.setFixedSize(180, 220)
        self.setStyleSheet(
            f"background: {t.BG_INPUT}; border: 2px solid {t.GREEN}; border-radius: 14px;"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8); lay.setSpacing(6)

        thumb = ThumbLabel(path, 164, 164, 10)
        thumb.clicked.connect(lambda p=path: open_path(p))
        lay.addWidget(thumb, alignment=Qt.AlignCenter)

        meta = QHBoxLayout(); meta.setSpacing(6); meta.setContentsMargins(0, 0, 0, 0)
        cat_lbl = QLabel(core.BROLL_CATEGORY_LABELS.get(category, category.upper()))
        cat_lbl.setStyleSheet(
            f"color: {t.TEXT_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 0.05em;"
        )
        meta.addWidget(cat_lbl)
        meta.addStretch()
        self.toggle_btn = QPushButton("Approved")
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFixedHeight(24)
        self._restyle_btn()
        self.toggle_btn.clicked.connect(self._toggle)
        meta.addWidget(self.toggle_btn)
        lay.addLayout(meta)

    def _toggle(self):
        self._approved = not self._approved
        self._restyle_card()
        self._restyle_btn()
        self.toggled.emit(self.idx, self._approved)

    def _restyle_card(self):
        color = t.GREEN if self._approved else t.TEXT_MUTED
        self.setStyleSheet(
            f"background: {t.BG_INPUT}; border: 2px solid {color}; border-radius: 14px;"
        )

    def _restyle_btn(self):
        if self._approved:
            self.toggle_btn.setText("Approved")
            self.toggle_btn.setStyleSheet(
                f"QPushButton {{ background: {t.GREEN}22; color: {t.GREEN}; "
                f"border: 1px solid {t.GREEN}55; border-radius: 12px; "
                f"font-size: 10px; font-weight: 700; padding: 0 10px; }}"
                f"QPushButton:hover {{ background: {t.GREEN}33; }}"
            )
        else:
            self.toggle_btn.setText("Rejected")
            self.toggle_btn.setStyleSheet(
                f"QPushButton {{ background: {t.BG_HOVER}; color: {t.TEXT_DIM}; "
                f"border: 1px solid {t.BORDER}; border-radius: 12px; "
                f"font-size: 10px; font-weight: 700; padding: 0 10px; }}"
                f"QPushButton:hover {{ background: {t.BG_HOVER}; }}"
            )

    def is_approved(self) -> bool:
        return self._approved


class BRollPage(QWidget):
    open_brands = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._image_worker: BRollImageWorker | None = None
        self._video_worker: BRollVideoWorker | None = None
        self._thread: QThread | None = None

        self._images_dir: Path | None = None
        self._videos_dir: Path | None = None
        self._image_results: list[dict] = []
        self._approval_thumbs: dict[int, _ApprovalThumb] = {}
        self._video_count = 0

        self._build()
        self.refresh_brands()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("B-Roll"); h1.setObjectName("H1")
        sub = QLabel(
            "Generate UGC-style still B-rolls from a Brand DNA, approve the keepers, "
            "then animate them into Kling 3 clips."
        )
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        self.stepper = QHBoxLayout()
        self.stepper.setSpacing(8); self.stepper.setContentsMargins(0, 0, 0, 0)
        self._step_pills: list[QLabel] = []
        for name in ("1. Setup", "2. Approve", "3. Videos"):
            pill = QLabel(name)
            pill.setStyleSheet(
                f"background: {t.BG_INPUT}; color: {t.TEXT_DIM}; padding: 6px 14px; "
                f"border-radius: 999px; font-size: 11px; font-weight: 700;"
            )
            self._step_pills.append(pill)
            self.stepper.addWidget(pill)
        self.stepper.addStretch()
        root.addLayout(self.stepper)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_setup_panel())
        self.stack.addWidget(self._build_approve_panel())
        self.stack.addWidget(self._build_videos_panel())
        root.addWidget(self.stack, 1)

        self._set_step(0)

    def _set_step(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, pill in enumerate(self._step_pills):
            if i == idx:
                pill.setStyleSheet(
                    f"background: {t.ACCENT}; color: #FFFFFF; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )
            elif i < idx:
                pill.setStyleSheet(
                    f"background: {t.SUCCESS_BG}; color: {t.SUCCESS}; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )
            else:
                pill.setStyleSheet(
                    f"background: {t.BG_INPUT}; color: {t.TEXT_DIM}; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )

    def _build_setup_panel(self) -> QWidget:
        wrap = QWidget()
        body = QHBoxLayout(wrap); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(14)

        form_card = Card()
        form_card.setMinimumWidth(520)
        card_lay = QVBoxLayout(form_card)
        card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
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
        manage_btn.setObjectName("GhostBtn"); manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.clicked.connect(self.open_brands.emit)
        brow.addWidget(manage_btn)
        form.addLayout(brow)

        self.brand_preview = QFrame()
        self.brand_preview.setObjectName("CardFlat")
        self.brand_preview.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 12px;")
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

        sl = QLabel("SPECIFICATIONS  ·  optional"); sl.setObjectName("Muted")
        form.addWidget(sl)
        self.specs = QTextEdit()
        self.specs.setPlaceholderText(
            "Optional notes on top of the Brand DNA: creator profile (skin tone, age, "
            "style, clothing), location, mood directives, anything to avoid… "
            "For SELFIE shots, describe the person in detail (face, age, ethnicity, "
            "hair, outfit, accessories, vibe) — they will be visible holding the product."
        )
        self.specs.setMinimumHeight(96); self.specs.setMaximumHeight(140)
        form.addWidget(self.specs)

        cnt_l = QLabel("SHOTS PER CATEGORY"); cnt_l.setObjectName("Muted")
        form.addWidget(cnt_l)
        cnt_row = QHBoxLayout(); cnt_row.setSpacing(10)
        self.cnt_usage = self._count_spinner("USAGE")
        self.cnt_pres = self._count_spinner("PRESENTATION")
        self.cnt_ecu = self._count_spinner("ECU")
        self.cnt_inact = self._count_spinner("IN-ACTION")
        self.cnt_selfie = self._count_spinner("SELFIE")
        for col in (self.cnt_usage, self.cnt_pres, self.cnt_ecu,
                    self.cnt_inact, self.cnt_selfie):
            cnt_row.addLayout(col["layout"], 1)
        form.addLayout(cnt_row)

        params_row = QHBoxLayout(); params_row.setSpacing(14)
        col_w = QVBoxLayout(); col_w.setSpacing(6)
        col_w.addWidget(_field_label("Workers"))
        self.workers = QSpinBox(); self.workers.setRange(1, 16); self.workers.setValue(6)
        col_w.addWidget(self.workers)
        col_r = QVBoxLayout(); col_r.setSpacing(6)
        col_r.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS); self.res.setCurrentText("1k")
        col_r.addWidget(self.res)
        col_a = QVBoxLayout(); col_a.setSpacing(6)
        col_a.addWidget(_field_label("Aspect"))
        self.asp = QComboBox(); self.asp.addItems(["9:16", "1:1", "4:5", "16:9"])
        col_a.addWidget(self.asp)
        params_row.addLayout(col_w, 1); params_row.addLayout(col_r, 1); params_row.addLayout(col_a, 1)
        form.addLayout(params_row)

        models_row = QHBoxLayout(); models_row.setSpacing(14)
        col_im = QVBoxLayout(); col_im.setSpacing(6)
        col_im.addWidget(_field_label("Image model"))
        self.image_model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.image_model.addItem(label, userData=slug)
        self.image_model.setCurrentIndex(0)
        col_im.addWidget(self.image_model)
        col_vm = QVBoxLayout(); col_vm.setSpacing(6)
        col_vm.addWidget(_field_label("Video model (phase 2)"))
        self.video_model = QComboBox()
        for slug, label in core.VIDEO_MODEL_CHOICES:
            self.video_model.addItem(label, userData=slug)
        self.video_model.setCurrentIndex(0)
        col_vm.addWidget(self.video_model)
        models_row.addLayout(col_im, 1); models_row.addLayout(col_vm, 1)
        form.addLayout(models_row)

        out_l = QLabel("OUTPUT FOLDER"); out_l.setObjectName("Muted")
        form.addWidget(out_l)
        self.out_row = OutputFolderRow()
        form.addWidget(self.out_row)

        self.cost_label = QLabel()
        self.cost_label.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        form.addWidget(self.cost_label)
        self._update_cost()
        for c in (self.cnt_usage["combo"], self.cnt_pres["combo"],
                  self.cnt_ecu["combo"], self.cnt_inact["combo"],
                  self.cnt_selfie["combo"]):
            c.currentIndexChanged.connect(self._update_cost)
        self.res.currentTextChanged.connect(self._update_cost)
        self.image_model.currentIndexChanged.connect(self._update_cost)

        form.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.go_btn = QPushButton("Generate B-roll images")
        self.go_btn.setObjectName("PrimaryBtn"); self.go_btn.setCursor(Qt.PointingHandCursor)
        self.go_btn.clicked.connect(self._start_images)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("GhostBtn"); self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel_images); self.cancel_btn.hide()
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

        live_card = Card()
        rlay = QVBoxLayout(live_card); rlay.setContentsMargins(20, 18, 20, 18); rlay.setSpacing(10)
        rh = QLabel("Live previews"); rh.setObjectName("H2")
        rlay.addWidget(rh)
        scroll2 = QScrollArea(); scroll2.setWidgetResizable(True)
        scroll2.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.live_grid_container = QWidget()
        self.live_grid = QGridLayout(self.live_grid_container)
        self.live_grid.setSpacing(10); self.live_grid.setContentsMargins(0, 0, 0, 0)
        self.live_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll2.setWidget(self.live_grid_container)
        scroll2.setMinimumHeight(220)
        rlay.addWidget(scroll2)
        right.addWidget(live_card, 2)

        right_w = QWidget(); right_w.setLayout(right)
        body.addWidget(right_w, 5)
        return wrap

    def _count_spinner(self, label_text: str) -> dict:
        col = QVBoxLayout(); col.setSpacing(6)
        col.addWidget(_field_label(label_text))
        combo = QComboBox()
        for i in range(0, 11):
            combo.addItem(str(i), userData=i)
        combo.setCurrentIndex(0)
        col.addWidget(combo)
        return {"layout": col, "combo": combo}

    def _build_approve_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head_card = Card()
        hl = QHBoxLayout(head_card); hl.setContentsMargins(20, 16, 20, 16); hl.setSpacing(12)
        title = QLabel("Approve images for animation"); title.setObjectName("H2")
        hl.addWidget(title); hl.addStretch()
        self.approve_count_lbl = QLabel("")
        self.approve_count_lbl.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        hl.addWidget(self.approve_count_lbl)
        all_btn = QPushButton("Approve all")
        all_btn.setObjectName("GhostBtn"); all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: self._set_all_approved(True))
        hl.addWidget(all_btn)
        none_btn = QPushButton("Reject all")
        none_btn.setObjectName("GhostBtn"); none_btn.setCursor(Qt.PointingHandCursor)
        none_btn.clicked.connect(lambda: self._set_all_approved(False))
        hl.addWidget(none_btn)
        self.images_open_btn = QPushButton("Open folder")
        self.images_open_btn.setObjectName("GhostBtn"); self.images_open_btn.setCursor(Qt.PointingHandCursor)
        self.images_open_btn.clicked.connect(self._open_images_folder)
        hl.addWidget(self.images_open_btn)
        back_btn = QPushButton("← Back to setup")
        back_btn.setObjectName("GhostBtn"); back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._set_step(0))
        hl.addWidget(back_btn)
        self.animate_btn = QPushButton("Animate approved")
        self.animate_btn.setObjectName("PrimaryBtn"); self.animate_btn.setCursor(Qt.PointingHandCursor)
        self.animate_btn.clicked.connect(self._start_videos)
        hl.addWidget(self.animate_btn)
        col.addWidget(head_card)

        # Per-clip settings — duration + native-audio toggle. Placed right above
        # the approval grid so the user can tweak both before clicking Animate.
        settings_card = Card()
        sl = QHBoxLayout(settings_card); sl.setContentsMargins(20, 14, 20, 14); sl.setSpacing(20)

        dur_col = QVBoxLayout(); dur_col.setSpacing(4)
        dur_top = QHBoxLayout(); dur_top.setContentsMargins(0, 0, 0, 0); dur_top.setSpacing(8)
        dur_top.addWidget(_field_label("Duration"))
        dur_top.addStretch()
        self.duration_value_lbl = QLabel("5s")
        self.duration_value_lbl.setStyleSheet(
            f"background: {t.BG_INPUT}; color: {t.TEXT}; padding: 2px 10px; "
            f"border-radius: 8px; font-size: 12px; font-weight: 600;"
        )
        dur_top.addWidget(self.duration_value_lbl)
        dur_col.addLayout(dur_top)
        self.duration_slider = QSlider(Qt.Horizontal)
        self.duration_slider.setRange(5, 10)
        self.duration_slider.setSingleStep(1)
        self.duration_slider.setPageStep(1)
        self.duration_slider.setTickPosition(QSlider.NoTicks)
        self.duration_slider.setValue(5)
        self.duration_slider.valueChanged.connect(self._on_duration_changed)
        dur_col.addWidget(self.duration_slider)
        sl.addLayout(dur_col, 3)

        aud_col = QVBoxLayout(); aud_col.setSpacing(4)
        aud_col.addWidget(_field_label("Native audio (Kling — costs more)"))
        self.audio_toggle = QPushButton("Audio OFF")
        self.audio_toggle.setCheckable(True)
        self.audio_toggle.setChecked(False)
        self.audio_toggle.setCursor(Qt.PointingHandCursor)
        self.audio_toggle.setMinimumWidth(120)
        self.audio_toggle.setStyleSheet(
            f"QPushButton {{ background: {t.BG_INPUT}; color: {t.TEXT_DIM}; "
            f"border: 1px solid {t.BORDER}; border-radius: 14px; padding: 6px 14px; "
            f"font-size: 12px; font-weight: 600; }}"
            f"QPushButton:checked {{ background: {t.ACCENT}; color: white; "
            f"border: 1px solid {t.ACCENT}; }}"
            f"QPushButton:hover {{ border-color: {t.ACCENT}; }}"
        )
        self.audio_toggle.toggled.connect(self._on_audio_toggled)
        aud_col.addWidget(self.audio_toggle)
        sl.addLayout(aud_col, 1)

        col.addWidget(settings_card)

        grid_card = Card()
        gl = QVBoxLayout(grid_card); gl.setContentsMargins(20, 18, 20, 18); gl.setSpacing(10)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.approve_grid_container = QWidget()
        self.approve_grid = QGridLayout(self.approve_grid_container)
        self.approve_grid.setSpacing(14); self.approve_grid.setContentsMargins(0, 0, 0, 0)
        self.approve_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.approve_grid_container)
        gl.addWidget(scroll)
        col.addWidget(grid_card, 1)
        return wrap

    def _build_videos_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head_card = Card()
        hl = QHBoxLayout(head_card); hl.setContentsMargins(20, 16, 20, 16); hl.setSpacing(12)
        title = QLabel("Animated B-roll"); title.setObjectName("H2")
        hl.addWidget(title); hl.addStretch()
        self.video_pill = StatusPill("Idle", t.TEXT_MUTED)
        hl.addWidget(self.video_pill)
        self.video_cancel_btn = QPushButton("Cancel")
        self.video_cancel_btn.setObjectName("GhostBtn"); self.video_cancel_btn.setCursor(Qt.PointingHandCursor)
        self.video_cancel_btn.clicked.connect(self._cancel_videos); self.video_cancel_btn.hide()
        hl.addWidget(self.video_cancel_btn)
        self.video_open_btn = QPushButton("Open folder")
        self.video_open_btn.setObjectName("GhostBtn"); self.video_open_btn.setCursor(Qt.PointingHandCursor)
        self.video_open_btn.setEnabled(False)
        self.video_open_btn.clicked.connect(self._open_videos_folder)
        hl.addWidget(self.video_open_btn)
        back_btn = QPushButton("← Back to approve")
        back_btn.setObjectName("GhostBtn"); back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._set_step(1))
        hl.addWidget(back_btn)
        new_btn = QPushButton("New B-roll run")
        new_btn.setObjectName("GhostBtn"); new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(lambda: self._set_step(0))
        hl.addWidget(new_btn)
        col.addWidget(head_card)

        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 18, 20, 18); llay.setSpacing(10)
        lh = QLabel("Activity"); lh.setObjectName("H2")
        llay.addWidget(lh)
        self.video_log = QPlainTextEdit(); self.video_log.setReadOnly(True)
        self.video_log.setMinimumHeight(140)
        llay.addWidget(self.video_log)
        col.addWidget(log_card, 1)

        grid_card = Card()
        gl = QVBoxLayout(grid_card); gl.setContentsMargins(20, 18, 20, 18); gl.setSpacing(10)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.video_grid_container = QWidget()
        self.video_grid = QGridLayout(self.video_grid_container)
        self.video_grid.setSpacing(12); self.video_grid.setContentsMargins(0, 0, 0, 0)
        self.video_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.video_grid_container)
        gl.addWidget(scroll)
        col.addWidget(grid_card, 2)
        return wrap

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
        if not getattr(self, "_brand_combo_wired", False):
            self.brand_combo.currentIndexChanged.connect(self._on_brand_changed)
            self._brand_combo_wired = True
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

    def _counts(self) -> dict[str, int]:
        return {
            "usage": int(self.cnt_usage["combo"].currentText()),
            "presentation": int(self.cnt_pres["combo"].currentText()),
            "ecu": int(self.cnt_ecu["combo"].currentText()),
            "in_action": int(self.cnt_inact["combo"].currentText()),
            "selfie": int(self.cnt_selfie["combo"].currentText()),
        }

    def _update_cost(self):
        counts = self._counts()
        total = sum(counts.values())
        provider = core.get_active_provider_name()
        model = self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL
        price = core.cost_per_image(provider, model, self.res.currentText())
        if total <= 0:
            self.cost_label.setText("Pick at least one shot count to estimate cost.")
        else:
            self.cost_label.setText(
                f"{total} images  ·  estimated ${total * price:.2f} (+ 1 LLM call)  ·  "
                f"phase 2 video cost shown after approval."
            )

    def _start_images(self):
        if not self.brand_combo.isEnabled():
            QMessageBox.warning(self, "No brand", "Create a Brand DNA first."); return
        counts = self._counts()
        if sum(counts.values()) <= 0:
            QMessageBox.warning(self, "No shots", "Pick at least one shot count > 0."); return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first."); return

        self._clear_live_grid()
        self.log.clear()
        self._images_dir = None
        self._image_results = []
        self.go_btn.hide(); self.cancel_btn.show()
        self.live_pill.setText("Running")
        self.live_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )

        self._thread = QThread()
        self._image_worker = BRollImageWorker(
            self.brand_combo.currentText(),
            self.specs.toPlainText(),
            counts,
            self.res.currentText(),
            self.asp.currentText(),
            self.workers.value(),
            self.out_row.path(),
            self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL,
        )
        self._image_worker.moveToThread(self._thread)
        self._thread.started.connect(self._image_worker.run)
        self._image_worker.log.connect(self._on_image_log)
        self._image_worker.result.connect(self._on_image_result)
        self._image_worker.out_dir_signal.connect(self._on_images_out_dir)
        self._image_worker.finished.connect(self._on_images_finished)
        self._thread.start()

    def _cancel_images(self):
        if self._image_worker:
            self._image_worker.cancel()
        self.cancel_btn.setEnabled(False); self.cancel_btn.setText("Cancelling…")

    def load_run(self, run: dict) -> bool:
        """Re-hydrate the page at the approval step from a previously generated
        B-roll image run on disk. Returns True if the run was loaded.

        Used when the user reopens a run from History whose images were
        generated but never animated — they pick up exactly where they left off.
        """
        run_dir = Path(run.get("dir") or "")
        if not run_dir.exists():
            QMessageBox.warning(self, "Run unavailable",
                                f"Folder not found:\n{run_dir}")
            return False
        results = list(run.get("results") or [])
        ok_results = [r for r in results if r.get("status") == "ok"]
        if not ok_results:
            QMessageBox.information(self, "Nothing to approve",
                                    "This run has no successful images to animate.")
            return False

        self._images_dir = run_dir
        self._image_results = results
        self._videos_dir = None
        self._video_count = 0
        self._clear_video_grid()
        self.video_log.clear()
        self.video_pill.setText("Idle")
        self.video_pill.setStyleSheet(
            f"background: {t.BG_INPUT}; color: {t.TEXT_DIM}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        self._populate_approval_grid()
        self._set_step(1)
        return True

    def _on_image_log(self, level: str, msg: str):
        self._append_log(self.log, level, msg)

    def _on_image_result(self, r: dict):
        self._image_results.append(r)
        if r.get("status") != "ok":
            return
        if not self._images_dir:
            return
        local = self._images_dir / r.get("file", "")
        if not local.exists():
            return
        thumb = ThumbLabel(local, 140, 140, 10)
        thumb.clicked.connect(lambda p=local: open_path(p))
        n = sum(1 for x in self._image_results if x.get("status") == "ok")
        row = (n - 1) // 4
        col = (n - 1) % 4
        self.live_grid.addWidget(thumb, row, col)

    def _on_images_out_dir(self, p: str):
        self._images_dir = Path(p)

    def _on_images_finished(self, out_dir: str):
        self._thread.quit(); self._thread.wait()
        self.go_btn.show(); self.cancel_btn.hide()
        self.cancel_btn.setEnabled(True); self.cancel_btn.setText("Cancel")
        self.live_pill.setText("Done")
        self.live_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        if out_dir:
            self._images_dir = Path(out_dir)
        self._populate_approval_grid()
        self._set_step(1)

    def _populate_approval_grid(self):
        while self.approve_grid.count():
            item = self.approve_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        self._approval_thumbs.clear()

        ok_results = sorted(
            (r for r in self._image_results if r.get("status") == "ok"),
            key=lambda r: r.get("index", 0),
        )
        for i, r in enumerate(ok_results):
            local = (self._images_dir / r.get("file", "")) if self._images_dir else None
            if not local or not local.exists():
                continue
            tile = _ApprovalThumb(r["index"], local, r.get("category", "usage"))
            tile.toggled.connect(self._on_approval_toggled)
            row = i // 5
            col = i % 5
            self.approve_grid.addWidget(tile, row, col)
            self._approval_thumbs[r["index"]] = tile
        self._refresh_approval_count()

    def _on_approval_toggled(self, _idx: int, _approved: bool):
        self._refresh_approval_count()

    def _on_duration_changed(self, value: int):
        self.duration_value_lbl.setText(f"{value}s")
        self._refresh_approval_count()

    def _on_audio_toggled(self, checked: bool):
        self.audio_toggle.setText("Audio ON" if checked else "Audio OFF")
        self._refresh_approval_count()

    def _refresh_approval_count(self):
        approved = sum(1 for tile in self._approval_thumbs.values() if tile.is_approved())
        total = len(self._approval_thumbs)
        provider = core.get_active_provider_name()
        video_model = self.video_model.currentData() or core.DEFAULT_VIDEO_MODEL
        duration = self.duration_slider.value() if hasattr(self, "duration_slider") else 5
        # Native audio on Kling roughly 1.5×s the clip cost — see pricing page.
        sound_mult = 1.5 if (hasattr(self, "audio_toggle") and self.audio_toggle.isChecked()) else 1.0
        price = core.cost_per_video(provider, video_model, duration) * sound_mult
        self.approve_count_lbl.setText(
            f"{approved}/{total} approved  ·  estimated ${approved * price:.2f} "
            f"for phase 2 ({duration}s clips)"
        )
        self.animate_btn.setEnabled(approved > 0)

    def _set_all_approved(self, approved: bool):
        for tile in self._approval_thumbs.values():
            if tile.is_approved() != approved:
                tile._toggle()

    def _start_videos(self):
        approved = [idx for idx, tile in self._approval_thumbs.items() if tile.is_approved()]
        if not approved:
            QMessageBox.warning(self, "No approved", "Approve at least one image."); return
        if not self._images_dir:
            QMessageBox.warning(self, "No run", "Image run not found."); return

        self.video_log.clear()
        self._clear_video_grid()
        self._videos_dir = None
        self._video_count = 0
        self.video_open_btn.setEnabled(False)
        self.animate_btn.setEnabled(False)
        self.video_cancel_btn.show()
        self.video_cancel_btn.setEnabled(True); self.video_cancel_btn.setText("Cancel")
        self.video_pill.setText("Running")
        self.video_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        self._set_step(2)

        self._thread = QThread()
        self._video_worker = BRollVideoWorker(
            str(self._images_dir),
            sorted(approved),
            self.duration_slider.value(),
            self.asp.currentText(),
            min(4, self.workers.value()),
            self.video_model.currentData() or core.DEFAULT_VIDEO_MODEL,
            self.audio_toggle.isChecked(),
        )
        self._video_worker.moveToThread(self._thread)
        self._thread.started.connect(self._video_worker.run)
        self._video_worker.log.connect(self._on_video_log)
        self._video_worker.result.connect(self._on_video_result)
        self._video_worker.out_dir_signal.connect(self._on_videos_out_dir)
        self._video_worker.finished.connect(self._on_videos_finished)
        self._thread.start()

    def _cancel_videos(self):
        if self._video_worker:
            self._video_worker.cancel()
        self.video_cancel_btn.setEnabled(False); self.video_cancel_btn.setText("Cancelling…")

    def _on_video_log(self, level: str, msg: str):
        self._append_log(self.video_log, level, msg)

    def _on_video_result(self, r: dict):
        if r.get("status") != "ok":
            return
        if not self._videos_dir:
            return
        local = self._videos_dir / r.get("file", "")
        if not local.exists():
            return
        self._video_count += 1
        src_thumb: Path | None = None
        src_file = r.get("source_file", "")
        if self._images_dir and src_file:
            cand = self._images_dir / src_file
            if cand.exists():
                src_thumb = cand

        tile = QFrame()
        tile.setFixedSize(180, 220)
        tile.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 14px;")
        tlay = QVBoxLayout(tile); tlay.setContentsMargins(8, 8, 8, 8); tlay.setSpacing(6)
        if src_thumb:
            thumb = ThumbLabel(src_thumb, 164, 164, 10)
            thumb.clicked.connect(lambda p=local: open_path(p))
            tlay.addWidget(thumb, alignment=Qt.AlignCenter)
        else:
            ph = QLabel("Video")
            ph.setFixedSize(164, 164); ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet(f"background: {t.BORDER}; color: {t.TEXT}; border-radius: 10px; font-weight: 700;")
            tlay.addWidget(ph, alignment=Qt.AlignCenter)
        play = QPushButton(f"▶  {local.name}")
        play.setCursor(Qt.PointingHandCursor)
        play.setStyleSheet(
            f"QPushButton {{ background: {t.BG_HOVER}; color: {t.TEXT}; "
            f"border: 1px solid {t.BORDER}; border-radius: 10px; "
            f"font-size: 10px; font-weight: 700; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background: {t.ACCENT}22; color: {t.ACCENT}; border-color: {t.ACCENT}55; }}"
        )
        play.clicked.connect(lambda p=local: open_path(p))
        tlay.addWidget(play)

        row = (self._video_count - 1) // 4
        col = (self._video_count - 1) % 4
        self.video_grid.addWidget(tile, row, col)

    def _on_videos_out_dir(self, p: str):
        self._videos_dir = Path(p)
        self.video_open_btn.setEnabled(True)

    def _on_videos_finished(self, out_dir: str):
        self._thread.quit(); self._thread.wait()
        self.video_cancel_btn.hide()
        self.animate_btn.setEnabled(True)
        self.video_pill.setText("Done")
        self.video_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        if out_dir:
            self._videos_dir = Path(out_dir)
            self.video_open_btn.setEnabled(True)

    def _open_videos_folder(self):
        if self._videos_dir:
            open_path(self._videos_dir)

    def _open_images_folder(self):
        if self._images_dir:
            open_path(self._images_dir)

    def _append_log(self, target: QPlainTextEdit, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        target.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    def _clear_live_grid(self):
        while self.live_grid.count():
            item = self.live_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

    def _clear_video_grid(self):
        while self.video_grid.count():
            item = self.video_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()


# ─── Funnel Ads ─────────────────────────────────────────────────────────────

class FunnelAdsWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, brand_name, funnel_stage, form_fields, resolution, aspect,
                 workers, output_root, image_model):
        super().__init__()
        self._args = (brand_name, funnel_stage, form_fields, resolution, aspect, workers)
        self._output_root = output_root
        self._image_model = image_model
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        out = core.run_funnel_ads(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            on_out_dir=lambda p: self.out_dir_signal.emit(str(p)),
            should_cancel=lambda: self._cancel,
            output_root=self._output_root,
            image_model=self._image_model,
        )
        self.finished.emit(str(out) if out else "")


class FunnelAdsPage(QWidget):
    open_brands = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._worker: FunnelAdsWorker | None = None
        self._thread: QThread | None = None
        self._out_dir: Path | None = None
        self._results_count = 0
        self._stage = "TOF"
        self._build()
        self.refresh_brands()

    # ── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Funnel Ads"); h1.setObjectName("H1")
        sub = QLabel(
            "Generate static ads for a specific funnel stage — Top, Middle or Bottom — "
            "from a Brand DNA. Pick a segment, dial in the angle, get N scroll-stop creatives."
        )
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        # Stage selector — segmented control
        stage_row = QHBoxLayout(); stage_row.setSpacing(8); stage_row.setContentsMargins(0, 0, 0, 0)
        self._stage_btns: dict[str, QPushButton] = {}
        for stage in core.FUNNEL_STAGES:
            btn = QPushButton(f"{stage}  ·  {core.FUNNEL_LABELS.get(stage, stage)}")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(36)
            btn.clicked.connect(lambda _=False, s=stage: self._set_stage(s))
            stage_row.addWidget(btn, 1)
            self._stage_btns[stage] = btn
        stage_row.addStretch()
        root.addLayout(stage_row)

        body = QHBoxLayout(); body.setSpacing(14)

        # Left: form
        form_card = Card()
        form_card.setMinimumWidth(560)
        card_lay = QVBoxLayout(form_card)
        card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        form_inner = QWidget()
        form = QVBoxLayout(form_inner)
        form.setContentsMargins(22, 20, 22, 20); form.setSpacing(16)
        scroll.setWidget(form_inner)
        card_lay.addWidget(scroll)

        # Brand DNA picker (same pattern as Adapt / B-Roll)
        bl = QLabel("BRAND DNA"); bl.setObjectName("Muted")
        form.addWidget(bl)
        brow = QHBoxLayout(); brow.setSpacing(8)
        self.brand_combo = QComboBox()
        brow.addWidget(self.brand_combo, 1)
        manage_btn = QPushButton("Manage")
        manage_btn.setObjectName("GhostBtn"); manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.clicked.connect(self.open_brands.emit)
        brow.addWidget(manage_btn)
        form.addLayout(brow)

        self.brand_preview = QFrame()
        self.brand_preview.setObjectName("CardFlat")
        self.brand_preview.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 12px;")
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

        # Segments — checkable list with per-segment count
        seg_head = QHBoxLayout(); seg_head.setContentsMargins(0, 0, 0, 0)
        seg_l = QLabel("SEGMENTS  ·  cocher et choisir le nombre de creas par segment")
        seg_l.setObjectName("Muted")
        seg_head.addWidget(seg_l); seg_head.addStretch()
        self.seg_total_lbl = QLabel("Total : 0 creas")
        self.seg_total_lbl.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px; font-weight: 600;")
        seg_head.addWidget(self.seg_total_lbl)
        form.addLayout(seg_head)

        self._segments_card = QFrame()
        self._segments_card.setObjectName("CardFlat")
        self._segments_card.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 12px;")
        self._segments_layout = QVBoxLayout(self._segments_card)
        self._segments_layout.setContentsMargins(12, 8, 12, 8)
        self._segments_layout.setSpacing(2)
        self._segment_rows: dict[str, dict] = {}
        # Filled by _set_stage()
        form.addWidget(self._segments_card)

        params_row = QHBoxLayout(); params_row.setSpacing(14)
        col_a = QVBoxLayout(); col_a.setSpacing(6)
        col_a.addWidget(_field_label("Aspect"))
        self.asp = QComboBox(); self.asp.addItems(core.FUNNEL_ASPECTS); self.asp.setCurrentText("1:1")
        col_a.addWidget(self.asp)
        col_r = QVBoxLayout(); col_r.setSpacing(6)
        col_r.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS); self.res.setCurrentText("1k")
        col_r.addWidget(self.res)
        col_w = QVBoxLayout(); col_w.setSpacing(6)
        col_w.addWidget(_field_label("Workers"))
        self.workers = QSpinBox(); self.workers.setRange(1, 16); self.workers.setValue(6)
        col_w.addWidget(self.workers)
        params_row.addLayout(col_a, 1); params_row.addLayout(col_r, 1); params_row.addLayout(col_w, 1)
        form.addLayout(params_row)

        plang_row = QHBoxLayout(); plang_row.setSpacing(14)
        col_pf = QVBoxLayout(); col_pf.setSpacing(6)
        col_pf.addWidget(_field_label("Platform"))
        self.platform = QComboBox(); self.platform.addItems(core.FUNNEL_PLATFORMS)
        self.platform.setCurrentText("Meta")
        col_pf.addWidget(self.platform)
        col_lg = QVBoxLayout(); col_lg.setSpacing(6)
        col_lg.addWidget(_field_label("Language"))
        self.language = QComboBox(); self.language.addItems(core.FUNNEL_LANGUAGES)
        self.language.setCurrentText("English")
        col_lg.addWidget(self.language)
        col_im = QVBoxLayout(); col_im.setSpacing(6)
        col_im.addWidget(_field_label("Image model"))
        self.image_model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.image_model.addItem(label, userData=slug)
        self.image_model.setCurrentIndex(0)
        col_im.addWidget(self.image_model)
        plang_row.addLayout(col_pf, 1); plang_row.addLayout(col_lg, 1); plang_row.addLayout(col_im, 1)
        form.addLayout(plang_row)

        # Free-text fields
        form.addWidget(self._textarea_label("MARKETING ANGLE  ·  optional"))
        self.marketing_angle = self._textarea(
            "Strategic angle for this batch. Ex: 'Mirror the daily frustration' / 'Lead with the BOGO offer'"
        )
        form.addWidget(self.marketing_angle)

        form.addWidget(self._textarea_label("TARGET PERSONA  ·  optional"))
        self.target_persona = self._textarea(
            "Avatar name from Brand DNA, or 'Mix'. Ex: 'The Frustrated Fighter' / 'Mix'"
        )
        form.addWidget(self.target_persona)

        form.addWidget(self._textarea_label("SPECIFICATIONS  ·  optional"))
        self.specifications = self._textarea(
            "Additional creative direction. Ex: 'Bold typography only' / 'Dark backgrounds' / 'Native screenshot aesthetic'"
        )
        form.addWidget(self.specifications)

        form.addWidget(self._textarea_label("CLAIMS / HEADLINES REFERENCES  ·  optional"))
        self.claims_refs = self._textarea(
            "Specific claims or hooks to prioritize. Ex: '47 massage points' / '97% saw results'"
        )
        form.addWidget(self.claims_refs)

        # BOF-only fields (created always, hidden/shown by _set_stage)
        self.promo_label = self._textarea_label("PROMOTIONAL OFFER  ·  optional · BOF only")
        form.addWidget(self.promo_label)
        self.promotional_offer = self._textarea(
            "Active offer. Ex: 'BUY 1 GET 1 FREE — $49.90 for 2' / '50% OFF — was $69.90 now $34.95'"
        )
        form.addWidget(self.promotional_offer)

        self.guarantee_label = self._textarea_label("GUARANTEE  ·  optional · BOF only")
        form.addWidget(self.guarantee_label)
        self.guarantee = self._textarea(
            "Guarantee badge. Ex: '90-day satisfaction guarantee — full refund, no questions asked'"
        )
        form.addWidget(self.guarantee)

        # Output folder
        out_l = QLabel("OUTPUT FOLDER"); out_l.setObjectName("Muted")
        form.addWidget(out_l)
        self.out_row = OutputFolderRow()
        form.addWidget(self.out_row)

        self.cost_label = QLabel()
        self.cost_label.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        form.addWidget(self.cost_label)
        self._update_cost()
        self.res.currentTextChanged.connect(self._update_cost)
        self.image_model.currentIndexChanged.connect(self._update_cost)

        form.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.go_btn = QPushButton("Generate funnel ads")
        self.go_btn.setObjectName("PrimaryBtn"); self.go_btn.setCursor(Qt.PointingHandCursor)
        self.go_btn.clicked.connect(self._start)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("GhostBtn"); self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self._cancel); self.cancel_btn.hide()
        btn_row.addWidget(self.go_btn); btn_row.addWidget(self.cancel_btn); btn_row.addStretch()
        form.addLayout(btn_row)
        form.addStretch()

        body.addWidget(form_card, 5)

        # Right: log + result grid
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
        self.open_folder_btn.setObjectName("GhostBtn"); self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_folder)
        rhead.addWidget(self.open_folder_btn)
        rlay.addLayout(rhead)

        scroll2 = QScrollArea(); scroll2.setWidgetResizable(True)
        scroll2.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.grid_container = QWidget()
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(12); self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll2.setWidget(self.grid_container)
        scroll2.setMinimumHeight(220)
        rlay.addWidget(scroll2)
        right.addWidget(res_card, 2)

        right_w = QWidget(); right_w.setLayout(right)
        body.addWidget(right_w, 5)
        root.addLayout(body, 1)

        self._set_stage("TOF")

    def _textarea(self, placeholder: str) -> QTextEdit:
        ta = QTextEdit()
        ta.setPlaceholderText(placeholder)
        ta.setMinimumHeight(64); ta.setMaximumHeight(96)
        return ta

    def _textarea_label(self, txt: str) -> QLabel:
        l = QLabel(txt); l.setObjectName("Muted")
        return l

    # ── Stage switching ─────────────────────────────────────────────────────

    def _set_stage(self, stage: str):
        self._stage = stage
        for s, btn in self._stage_btns.items():
            active = (s == stage)
            btn.setChecked(active)
            if active:
                # Match PrimaryBtn: violet→pink gradient + white text + pill.
                # Explicit `:checked` rule prevents Qt's default checked-state
                # cascade from bleeding through (the green-ish flash seen
                # before came from that interaction).
                btn.setStyleSheet(
                    "QPushButton {"
                    f" background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                    f" stop:0 {t.ACCENT}, stop:1 {t.ACCENT_PINK});"
                    f" color: #FFFFFF;"
                    f" border: 1px solid transparent;"
                    f" border-radius: 999px;"
                    f" font-size: 12px; font-weight: 700;"
                    f" padding: 0 16px;"
                    " }"
                    "QPushButton:checked {"
                    f" background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                    f" stop:0 {t.ACCENT}, stop:1 {t.ACCENT_PINK});"
                    f" color: #FFFFFF;"
                    f" border: 1px solid transparent;"
                    " }"
                    "QPushButton:hover {"
                    f" background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
                    f" stop:0 {t.ACCENT_STRONG}, stop:1 {t.ACCENT_PINK});"
                    " }"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton {"
                    f" background: {t.BG_INPUT}; color: {t.TEXT_DIM};"
                    f" border: 1px solid {t.BORDER};"
                    f" border-radius: 999px;"
                    f" font-size: 12px; font-weight: 600;"
                    f" padding: 0 16px;"
                    " }"
                    "QPushButton:hover {"
                    f" background: {t.BG_HOVER}; color: {t.TEXT};"
                    f" border: 1px solid {t.ACCENT};"
                    " }"
                )

        # Rebuild segment rows for the chosen stage. Preserve previously
        # checked segments + their counts so switching back keeps selections.
        prev_state: dict[str, tuple[bool, int]] = {
            name: (row["chk"].isChecked(), row["spin"].value())
            for name, row in self._segment_rows.items()
        }
        # Clear out current rows
        while self._segments_layout.count():
            item = self._segments_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        self._segment_rows = {}

        segments = core.FUNNEL_SEGMENTS.get(stage, ["Mix"])
        for name in segments:
            row_w = QWidget()
            row = QHBoxLayout(row_w); row.setContentsMargins(0, 4, 0, 4); row.setSpacing(10)
            chk = QCheckBox(name)
            chk.setCursor(Qt.PointingHandCursor)
            chk.setStyleSheet(f"QCheckBox {{ color: {t.TEXT}; font-size: 12px; }}")
            row.addWidget(chk, 1)
            spin = QSpinBox(); spin.setRange(1, 12); spin.setValue(1)
            spin.setFixedWidth(72)
            spin.setEnabled(False)
            row.addWidget(spin)
            self._segments_layout.addWidget(row_w)
            self._segment_rows[name] = {"chk": chk, "spin": spin}

            # Re-apply previous state if this segment existed before.
            was_checked, was_value = prev_state.get(name, (False, 1))
            chk.setChecked(was_checked)
            spin.setValue(was_value)
            spin.setEnabled(was_checked)
            chk.toggled.connect(lambda on, s=spin: (s.setEnabled(on), self._update_segment_total()))
            spin.valueChanged.connect(self._update_segment_total)
        self._update_segment_total()

        # Show / hide BOF-only fields
        bof = (stage == "BOF")
        for w in (self.promo_label, self.promotional_offer, self.guarantee_label, self.guarantee):
            w.setVisible(bof)

    def _segment_breakdown(self) -> list[dict]:
        """Return [{name, count}] for every checked segment with count > 0."""
        out = []
        for name, row in self._segment_rows.items():
            if row["chk"].isChecked() and row["spin"].value() > 0:
                out.append({"name": name, "count": row["spin"].value()})
        return out

    def _segment_total(self) -> int:
        return sum(item["count"] for item in self._segment_breakdown())

    def _update_segment_total(self):
        total = self._segment_total()
        self.seg_total_lbl.setText(f"Total : {total} crea{'s' if total > 1 else ''}")
        self._update_cost()

    # ── Brand picker ────────────────────────────────────────────────────────

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
        if not getattr(self, "_brand_combo_wired", False):
            self.brand_combo.currentIndexChanged.connect(self._on_brand_changed)
            self._brand_combo_wired = True
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

    # ── Cost ────────────────────────────────────────────────────────────────

    def _update_cost(self):
        n = self._segment_total()
        provider = core.get_active_provider_name()
        model = self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL
        price = core.cost_per_image(provider, model, self.res.currentText())
        if n <= 0:
            self.cost_label.setText("Coche au moins un segment et choisis un nombre.")
        else:
            self.cost_label.setText(
                f"{n} image{'s' if n > 1 else ''}  ·  estimated ${n * price:.2f}  (+ 1 LLM call)"
            )

    # ── Run ─────────────────────────────────────────────────────────────────

    def _form_fields(self) -> dict:
        breakdown = self._segment_breakdown()
        return {
            "segment_breakdown": breakdown,
            "n_creatives": sum(item["count"] for item in breakdown),
            "marketing_angle": self.marketing_angle.toPlainText(),
            "aspect_ratio": self.asp.currentText(),
            "platform": self.platform.currentText(),
            "target_persona": self.target_persona.toPlainText(),
            "specifications": self.specifications.toPlainText(),
            "claims_refs": self.claims_refs.toPlainText(),
            "language": self.language.currentText(),
            "promotional_offer": self.promotional_offer.toPlainText() if self._stage == "BOF" else "",
            "guarantee": self.guarantee.toPlainText() if self._stage == "BOF" else "",
        }

    def _start(self):
        if not self.brand_combo.isEnabled():
            QMessageBox.warning(self, "No brand", "Create a Brand DNA first."); return
        if self._segment_total() <= 0:
            QMessageBox.warning(
                self, "No segment",
                "Coche au moins un segment et choisis le nombre de creas voulues."
            ); return
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
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )

        self._thread = QThread()
        self._worker = FunnelAdsWorker(
            self.brand_combo.currentText(),
            self._stage,
            self._form_fields(),
            self.res.currentText(),
            self.asp.currentText(),
            self.workers.value(),
            self.out_row.path(),
            self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._on_log)
        self._worker.result.connect(self._on_result)
        self._worker.out_dir_signal.connect(self._on_out_dir)
        self._worker.finished.connect(self._on_finished)
        self._thread.start()

    def _cancel(self):
        if self._worker:
            self._worker.cancel()
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
        if r.get("status") != "ok":
            return
        self._results_count += 1
        if self._out_dir:
            local = self._out_dir / r.get("file", "")
            if local.exists():
                thumb = ThumbLabel(local, 160, 160, 10)
                thumb.clicked.connect(lambda path=local: open_path(path))
                row = (self._results_count - 1) // 4
                col = (self._results_count - 1) % 4
                self.grid.addWidget(thumb, row, col)

    def _on_out_dir(self, p: str):
        self._out_dir = Path(p)
        self.open_folder_btn.setEnabled(True)

    def _on_finished(self, out_dir: str):
        self._thread.quit(); self._thread.wait()
        self.go_btn.show(); self.cancel_btn.hide()
        self.cancel_btn.setEnabled(True); self.cancel_btn.setText("Cancel")
        self.live_pill.setText("Done")
        self.live_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        if out_dir:
            self._out_dir = Path(out_dir)
            self.open_folder_btn.setEnabled(True)

    def _open_folder(self):
        if self._out_dir:
            open_path(self._out_dir)

    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()


# ─── Twin ───────────────────────────────────────────────────────────────────

class TwinAnalyzeWorker(QObject):
    log = Signal(str, str)
    finished = Signal(str)  # emits the generated prompt, or "" on error

    def __init__(self, image_path: str, hint: str):
        super().__init__()
        self._image_path = image_path
        self._hint = hint

    def run(self):
        prompt = core.run_twin_analyze(
            self._image_path,
            self._hint,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
        ) or ""
        self.finished.emit(prompt)


class TwinGenerateWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, image_path, prompt, n_variants, resolution, aspect, workers,
                 output_root, image_model, hint):
        super().__init__()
        self._args = (image_path, prompt, n_variants, resolution, aspect, workers)
        self._output_root = output_root
        self._image_model = image_model
        self._hint = hint
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        out = core.run_twin_generate(
            *self._args,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            on_result=lambda r: self.result.emit(r),
            on_out_dir=lambda p: self.out_dir_signal.emit(str(p)),
            should_cancel=lambda: self._cancel,
            output_root=self._output_root,
            image_model=self._image_model,
            hint=self._hint,
        )
        self.finished.emit(str(out) if out else "")


class TwinPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._analyze_worker: TwinAnalyzeWorker | None = None
        self._generate_worker: TwinGenerateWorker | None = None
        self._video_worker: BRollVideoWorker | None = None
        self._thread: QThread | None = None

        self._images_dir: Path | None = None
        self._videos_dir: Path | None = None
        self._image_results: list[dict] = []
        self._approval_thumbs: dict[int, _ApprovalThumb] = {}
        self._video_count = 0

        self._build()

    # ── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Twin"); h1.setObjectName("H1")
        sub = QLabel(
            "Drop any reference image. The LLM analyzes its style, you review the "
            "generated text-to-image prompt, then N variants are recreated from scratch — "
            "and animated with Kling 3 if you want."
        )
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        self.stepper = QHBoxLayout()
        self.stepper.setSpacing(8); self.stepper.setContentsMargins(0, 0, 0, 0)
        self._step_pills: list[QLabel] = []
        for name in ("1. Setup", "2. Review prompt", "3. Approve", "4. Videos"):
            pill = QLabel(name)
            pill.setStyleSheet(
                f"background: {t.BG_INPUT}; color: {t.TEXT_DIM}; padding: 6px 14px; "
                f"border-radius: 999px; font-size: 11px; font-weight: 700;"
            )
            self._step_pills.append(pill)
            self.stepper.addWidget(pill)
        self.stepper.addStretch()
        root.addLayout(self.stepper)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_setup_panel())
        self.stack.addWidget(self._build_review_panel())
        self.stack.addWidget(self._build_approve_panel())
        self.stack.addWidget(self._build_videos_panel())
        root.addWidget(self.stack, 1)
        self._set_step(0)

    def _set_step(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, pill in enumerate(self._step_pills):
            if i == idx:
                pill.setStyleSheet(
                    f"background: {t.ACCENT}; color: #FFFFFF; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )
            elif i < idx:
                pill.setStyleSheet(
                    f"background: {t.SUCCESS_BG}; color: {t.SUCCESS}; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )
            else:
                pill.setStyleSheet(
                    f"background: {t.BG_INPUT}; color: {t.TEXT_DIM}; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )

    # ── Step 1: Setup ───────────────────────────────────────────────────────

    def _build_setup_panel(self) -> QWidget:
        wrap = QWidget()
        body = QHBoxLayout(wrap); body.setContentsMargins(0, 0, 0, 0); body.setSpacing(14)

        form_card = Card()
        form_card.setMinimumWidth(520)
        card_lay = QVBoxLayout(form_card)
        card_lay.setContentsMargins(0, 0, 0, 0); card_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        form_inner = QWidget()
        form = QVBoxLayout(form_inner)
        form.setContentsMargins(22, 20, 22, 20); form.setSpacing(16)
        scroll.setWidget(form_inner)
        card_lay.addWidget(scroll)

        ref_l = QLabel("REFERENCE IMAGE"); ref_l.setObjectName("Muted")
        form.addWidget(ref_l)
        self.drop = DropZone()
        form.addWidget(self.drop)

        hint_l = QLabel("HINT  ·  optional"); hint_l.setObjectName("Muted")
        form.addWidget(hint_l)
        self.hint = QTextEdit()
        self.hint.setPlaceholderText(
            "Optional directive applied during analysis. Ex: 'use a blue/orange palette' / "
            "'make the subject male' / 'wider shot showing more environment' / 'shift to night scene'"
        )
        self.hint.setMinimumHeight(64); self.hint.setMaximumHeight(96)
        form.addWidget(self.hint)

        params_row = QHBoxLayout(); params_row.setSpacing(14)
        col_n = QVBoxLayout(); col_n.setSpacing(6)
        col_n.addWidget(_field_label("Variants"))
        self.n = QSpinBox(); self.n.setRange(1, 12); self.n.setValue(4)
        col_n.addWidget(self.n)
        col_a = QVBoxLayout(); col_a.setSpacing(6)
        col_a.addWidget(_field_label("Aspect"))
        self.asp = QComboBox(); self.asp.addItems(["1:1", "4:5", "9:16", "16:9", "3:4", "4:3"])
        self.asp.setCurrentText("1:1")
        col_a.addWidget(self.asp)
        col_r = QVBoxLayout(); col_r.setSpacing(6)
        col_r.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS); self.res.setCurrentText("1k")
        col_r.addWidget(self.res)
        col_w = QVBoxLayout(); col_w.setSpacing(6)
        col_w.addWidget(_field_label("Workers"))
        self.workers = QSpinBox(); self.workers.setRange(1, 16); self.workers.setValue(6)
        col_w.addWidget(self.workers)
        params_row.addLayout(col_n, 1); params_row.addLayout(col_a, 1)
        params_row.addLayout(col_r, 1); params_row.addLayout(col_w, 1)
        form.addLayout(params_row)

        col_im = QVBoxLayout(); col_im.setSpacing(6)
        col_im.addWidget(_field_label("Image model (text-to-image)"))
        self.image_model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.image_model.addItem(label, userData=slug)
        self.image_model.setCurrentIndex(0)
        col_im.addWidget(self.image_model)
        form.addLayout(col_im)

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
        self.image_model.currentIndexChanged.connect(self._update_cost)

        form.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.analyze_btn = QPushButton("Analyze image")
        self.analyze_btn.setObjectName("PrimaryBtn"); self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._start_analyze)
        btn_row.addWidget(self.analyze_btn); btn_row.addStretch()
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
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMinimumHeight(220)
        llay.addWidget(self.log)
        right.addWidget(log_card, 1)

        right_w = QWidget(); right_w.setLayout(right)
        body.addWidget(right_w, 4)
        return wrap

    def _update_cost(self):
        n = self.n.value()
        provider = core.get_active_provider_name()
        model = self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL
        price = core.cost_per_image(provider, model, self.res.currentText())
        self.cost_label.setText(
            f"{n} image{'s' if n > 1 else ''}  ·  estimated ${n * price:.2f}  (+ 1 LLM call for analysis)"
        )

    def _start_analyze(self):
        path = self.drop.path()
        if not path:
            QMessageBox.warning(self, "Missing reference", "Drop a reference image first.")
            return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first.")
            return

        self.log.clear()
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing…")
        self.live_pill.setText("Running")
        self.live_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )

        self._thread = QThread()
        self._analyze_worker = TwinAnalyzeWorker(path, self.hint.toPlainText())
        self._analyze_worker.moveToThread(self._thread)
        self._thread.started.connect(self._analyze_worker.run)
        self._analyze_worker.log.connect(self._on_log)
        self._analyze_worker.finished.connect(self._on_analyze_finished)
        self._thread.start()

    def _on_log(self, level: str, msg: str):
        self._append_log(self.log, level, msg)

    def _on_analyze_finished(self, prompt: str):
        self._thread.quit(); self._thread.wait()
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze image")
        if not prompt:
            self.live_pill.setText("Failed")
            self.live_pill.setStyleSheet(
                f"background: {t.RED}22; color: {t.RED}; padding: 4px 10px; "
                f"border-radius: 999px; font-size: 11px; font-weight: 600;"
            )
            return
        self.live_pill.setText("Done")
        self.live_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        self.prompt_edit.setPlainText(prompt)
        self._set_step(1)

    # ── Step 2: Review prompt ───────────────────────────────────────────────

    def _build_review_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head_card = Card()
        hl = QHBoxLayout(head_card); hl.setContentsMargins(20, 16, 20, 16); hl.setSpacing(12)
        title = QLabel("Review the LLM-generated prompt"); title.setObjectName("H2")
        hl.addWidget(title); hl.addStretch()
        regen_btn = QPushButton("Regenerate analysis")
        regen_btn.setObjectName("GhostBtn"); regen_btn.setCursor(Qt.PointingHandCursor)
        regen_btn.clicked.connect(self._start_analyze)
        hl.addWidget(regen_btn)
        back_btn = QPushButton("← Back to setup")
        back_btn.setObjectName("GhostBtn"); back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._set_step(0))
        hl.addWidget(back_btn)
        self.generate_btn = QPushButton("Generate variants")
        self.generate_btn.setObjectName("PrimaryBtn"); self.generate_btn.setCursor(Qt.PointingHandCursor)
        self.generate_btn.clicked.connect(self._start_generate)
        hl.addWidget(self.generate_btn)
        col.addWidget(head_card)

        prompt_card = Card()
        pl = QVBoxLayout(prompt_card); pl.setContentsMargins(20, 18, 20, 18); pl.setSpacing(10)
        helper = QLabel(
            "This is what the LLM saw. Edit anything — colors, subject, framing, mood — "
            "before generating the variants. The reference image is NOT passed to the image model."
        )
        helper.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        helper.setWordWrap(True)
        pl.addWidget(helper)
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setMinimumHeight(280)
        pl.addWidget(self.prompt_edit, 1)
        col.addWidget(prompt_card, 1)

        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 18, 20, 18); llay.setSpacing(10)
        lh = QLabel("Activity"); lh.setObjectName("H2")
        llay.addWidget(lh)
        self.gen_log = QPlainTextEdit(); self.gen_log.setReadOnly(True); self.gen_log.setMinimumHeight(120)
        llay.addWidget(self.gen_log)
        col.addWidget(log_card)
        return wrap

    def _start_generate(self):
        path = self.drop.path()
        prompt = self.prompt_edit.toPlainText().strip()
        if not path or not prompt:
            QMessageBox.warning(self, "Nothing to generate", "Both reference and prompt are required."); return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first."); return

        self.gen_log.clear()
        self._image_results = []
        self._images_dir = None
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating…")

        self._thread = QThread()
        self._generate_worker = TwinGenerateWorker(
            path, prompt, self.n.value(),
            self.res.currentText(), self.asp.currentText(), self.workers.value(),
            self.out_row.path(),
            self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL,
            self.hint.toPlainText(),
        )
        self._generate_worker.moveToThread(self._thread)
        self._thread.started.connect(self._generate_worker.run)
        self._generate_worker.log.connect(lambda lvl, msg: self._append_log(self.gen_log, lvl, msg))
        self._generate_worker.result.connect(self._on_generate_result)
        self._generate_worker.out_dir_signal.connect(self._on_images_out_dir)
        self._generate_worker.finished.connect(self._on_generate_finished)
        self._thread.start()

    def _on_generate_result(self, r: dict):
        self._image_results.append(r)

    def _on_images_out_dir(self, p: str):
        self._images_dir = Path(p)

    def _on_generate_finished(self, out_dir: str):
        self._thread.quit(); self._thread.wait()
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate variants")
        if out_dir:
            self._images_dir = Path(out_dir)
        self._populate_approval_grid()
        self._set_step(2)

    # ── Step 3: Approve ─────────────────────────────────────────────────────

    def _build_approve_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head_card = Card()
        hl = QHBoxLayout(head_card); hl.setContentsMargins(20, 16, 20, 16); hl.setSpacing(12)
        title = QLabel("Approve images for animation"); title.setObjectName("H2")
        hl.addWidget(title); hl.addStretch()
        self.approve_count_lbl = QLabel("")
        self.approve_count_lbl.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        hl.addWidget(self.approve_count_lbl)
        all_btn = QPushButton("Approve all")
        all_btn.setObjectName("GhostBtn"); all_btn.setCursor(Qt.PointingHandCursor)
        all_btn.clicked.connect(lambda: self._set_all_approved(True))
        hl.addWidget(all_btn)
        none_btn = QPushButton("Reject all")
        none_btn.setObjectName("GhostBtn"); none_btn.setCursor(Qt.PointingHandCursor)
        none_btn.clicked.connect(lambda: self._set_all_approved(False))
        hl.addWidget(none_btn)
        self.images_open_btn = QPushButton("Open folder")
        self.images_open_btn.setObjectName("GhostBtn"); self.images_open_btn.setCursor(Qt.PointingHandCursor)
        self.images_open_btn.clicked.connect(self._open_images_folder)
        hl.addWidget(self.images_open_btn)
        back_btn = QPushButton("← Back to review")
        back_btn.setObjectName("GhostBtn"); back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._set_step(1))
        hl.addWidget(back_btn)

        # Video model + sound — same as B-Roll
        col_vm = QVBoxLayout(); col_vm.setSpacing(2); col_vm.setContentsMargins(0, 0, 0, 0)
        self.video_model = QComboBox()
        for slug, label in core.VIDEO_MODEL_CHOICES:
            self.video_model.addItem(label, userData=slug)
        self.video_model.setCurrentIndex(0)
        self.video_model.setFixedWidth(180)
        col_vm.addWidget(self.video_model)
        self.sound_chk = QCheckBox("With sound (×1.5)")
        self.sound_chk.setStyleSheet(f"QCheckBox {{ color: {t.TEXT_DIM}; font-size: 11px; }}")
        col_vm.addWidget(self.sound_chk)
        hl.addLayout(col_vm)

        self.animate_btn = QPushButton("Animate approved")
        self.animate_btn.setObjectName("PrimaryBtn"); self.animate_btn.setCursor(Qt.PointingHandCursor)
        self.animate_btn.clicked.connect(self._start_videos)
        hl.addWidget(self.animate_btn)
        col.addWidget(head_card)

        grid_card = Card()
        gl = QVBoxLayout(grid_card); gl.setContentsMargins(20, 18, 20, 18); gl.setSpacing(10)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.approve_grid_container = QWidget()
        self.approve_grid = QGridLayout(self.approve_grid_container)
        self.approve_grid.setSpacing(14); self.approve_grid.setContentsMargins(0, 0, 0, 0)
        self.approve_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.approve_grid_container)
        gl.addWidget(scroll)
        col.addWidget(grid_card, 1)
        return wrap

    def _populate_approval_grid(self):
        while self.approve_grid.count():
            item = self.approve_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        self._approval_thumbs.clear()

        ok_results = sorted(
            (r for r in self._image_results if r.get("status") == "ok"),
            key=lambda r: r.get("index", 0),
        )
        for i, r in enumerate(ok_results):
            local = (self._images_dir / r.get("file", "")) if self._images_dir else None
            if not local or not local.exists():
                continue
            tile = _ApprovalThumb(r["index"], local, "twin")
            tile.toggled.connect(self._on_approval_toggled)
            row = i // 5
            col = i % 5
            self.approve_grid.addWidget(tile, row, col)
            self._approval_thumbs[r["index"]] = tile
        self._refresh_approval_count()

    def _on_approval_toggled(self, _idx: int, _approved: bool):
        self._refresh_approval_count()

    def _refresh_approval_count(self):
        approved = sum(1 for tile in self._approval_thumbs.values() if tile.is_approved())
        total = len(self._approval_thumbs)
        provider = core.get_active_provider_name()
        video_model = self.video_model.currentData() or core.DEFAULT_VIDEO_MODEL
        price = core.cost_per_video(provider, video_model, 5)
        self.approve_count_lbl.setText(
            f"{approved}/{total} approved  ·  estimated ${approved * price:.2f} for animation (5s clips)"
        )
        self.animate_btn.setEnabled(approved > 0)

    def _set_all_approved(self, approved: bool):
        for tile in self._approval_thumbs.values():
            if tile.is_approved() != approved:
                tile._toggle()

    def _open_images_folder(self):
        if self._images_dir:
            open_path(self._images_dir)

    # ── Step 4: Videos ──────────────────────────────────────────────────────

    def _build_videos_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head_card = Card()
        hl = QHBoxLayout(head_card); hl.setContentsMargins(20, 16, 20, 16); hl.setSpacing(12)
        title = QLabel("Animated twins"); title.setObjectName("H2")
        hl.addWidget(title); hl.addStretch()
        self.video_pill = StatusPill("Idle", t.TEXT_MUTED)
        hl.addWidget(self.video_pill)
        self.video_cancel_btn = QPushButton("Cancel")
        self.video_cancel_btn.setObjectName("GhostBtn"); self.video_cancel_btn.setCursor(Qt.PointingHandCursor)
        self.video_cancel_btn.clicked.connect(self._cancel_videos); self.video_cancel_btn.hide()
        hl.addWidget(self.video_cancel_btn)
        self.video_open_btn = QPushButton("Open folder")
        self.video_open_btn.setObjectName("GhostBtn"); self.video_open_btn.setCursor(Qt.PointingHandCursor)
        self.video_open_btn.setEnabled(False)
        self.video_open_btn.clicked.connect(self._open_videos_folder)
        hl.addWidget(self.video_open_btn)
        back_btn = QPushButton("← Back to approve")
        back_btn.setObjectName("GhostBtn"); back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._set_step(2))
        hl.addWidget(back_btn)
        new_btn = QPushButton("New twin run")
        new_btn.setObjectName("GhostBtn"); new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(lambda: self._set_step(0))
        hl.addWidget(new_btn)
        col.addWidget(head_card)

        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 18, 20, 18); llay.setSpacing(10)
        lh = QLabel("Activity"); lh.setObjectName("H2")
        llay.addWidget(lh)
        self.video_log = QPlainTextEdit(); self.video_log.setReadOnly(True); self.video_log.setMinimumHeight(140)
        llay.addWidget(self.video_log)
        col.addWidget(log_card, 1)

        grid_card = Card()
        gl = QVBoxLayout(grid_card); gl.setContentsMargins(20, 18, 20, 18); gl.setSpacing(10)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.video_grid_container = QWidget()
        self.video_grid = QGridLayout(self.video_grid_container)
        self.video_grid.setSpacing(12); self.video_grid.setContentsMargins(0, 0, 0, 0)
        self.video_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.video_grid_container)
        gl.addWidget(scroll)
        col.addWidget(grid_card, 2)
        return wrap

    def _start_videos(self):
        approved = [idx for idx, tile in self._approval_thumbs.items() if tile.is_approved()]
        if not approved:
            QMessageBox.warning(self, "No approved", "Approve at least one image."); return
        if not self._images_dir:
            QMessageBox.warning(self, "No run", "Image run not found."); return

        self.video_log.clear()
        self._clear_video_grid()
        self._videos_dir = None
        self._video_count = 0
        self.video_open_btn.setEnabled(False)
        self.animate_btn.setEnabled(False)
        self.video_cancel_btn.show()
        self.video_cancel_btn.setEnabled(True); self.video_cancel_btn.setText("Cancel")
        self.video_pill.setText("Running")
        self.video_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        self._set_step(3)

        self._thread = QThread()
        self._video_worker = BRollVideoWorker(
            str(self._images_dir),
            sorted(approved),
            5,
            self.asp.currentText(),
            min(4, self.workers.value()),
            self.video_model.currentData() or core.DEFAULT_VIDEO_MODEL,
            self.sound_chk.isChecked(),
        )
        self._video_worker.moveToThread(self._thread)
        self._thread.started.connect(self._video_worker.run)
        self._video_worker.log.connect(lambda lvl, msg: self._append_log(self.video_log, lvl, msg))
        self._video_worker.result.connect(self._on_video_result)
        self._video_worker.out_dir_signal.connect(self._on_videos_out_dir)
        self._video_worker.finished.connect(self._on_videos_finished)
        self._thread.start()

    def _cancel_videos(self):
        if self._video_worker:
            self._video_worker.cancel()
        self.video_cancel_btn.setEnabled(False); self.video_cancel_btn.setText("Cancelling…")

    def _on_video_result(self, r: dict):
        if r.get("status") != "ok":
            return
        if not self._videos_dir:
            return
        local = self._videos_dir / r.get("file", "")
        if not local.exists():
            return
        self._video_count += 1
        src_thumb: Path | None = None
        src_file = r.get("source_file", "")
        if self._images_dir and src_file:
            cand = self._images_dir / src_file
            if cand.exists():
                src_thumb = cand

        tile = QFrame()
        tile.setFixedSize(180, 220)
        tile.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 14px;")
        tlay = QVBoxLayout(tile); tlay.setContentsMargins(8, 8, 8, 8); tlay.setSpacing(6)
        if src_thumb:
            thumb = ThumbLabel(src_thumb, 164, 164, 10)
            thumb.clicked.connect(lambda p=local: open_path(p))
            tlay.addWidget(thumb, alignment=Qt.AlignCenter)
        else:
            ph = QLabel("Video"); ph.setFixedSize(164, 164); ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet(f"background: {t.BORDER}; color: {t.TEXT}; border-radius: 10px; font-weight: 700;")
            tlay.addWidget(ph, alignment=Qt.AlignCenter)
        play = QPushButton(f"▶  {local.name}")
        play.setCursor(Qt.PointingHandCursor)
        play.setStyleSheet(
            f"QPushButton {{ background: {t.BG_HOVER}; color: {t.TEXT}; "
            f"border: 1px solid {t.BORDER}; border-radius: 10px; "
            f"font-size: 10px; font-weight: 700; padding: 4px 8px; }}"
            f"QPushButton:hover {{ background: {t.ACCENT}22; color: {t.ACCENT}; border-color: {t.ACCENT}55; }}"
        )
        play.clicked.connect(lambda p=local: open_path(p))
        tlay.addWidget(play)

        row = (self._video_count - 1) // 4
        col = (self._video_count - 1) % 4
        self.video_grid.addWidget(tile, row, col)

    def _on_videos_out_dir(self, p: str):
        self._videos_dir = Path(p)
        self.video_open_btn.setEnabled(True)

    def _on_videos_finished(self, out_dir: str):
        self._thread.quit(); self._thread.wait()
        self.video_cancel_btn.hide()
        self.animate_btn.setEnabled(True)
        self.video_pill.setText("Done")
        self.video_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        if out_dir:
            self._videos_dir = Path(out_dir)
            self.video_open_btn.setEnabled(True)

    def _open_videos_folder(self):
        if self._videos_dir:
            open_path(self._videos_dir)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _append_log(self, target: QPlainTextEdit, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        target.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    def _clear_video_grid(self):
        while self.video_grid.count():
            item = self.video_grid.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()


# ─── Animation (multi-shot narrative video) ──────────────────────────────────

class AnimationOpWorker(QObject):
    """Generic worker that runs one core.run_animation_* call in a QThread.
    Emits log/finished signals. The op callable receives only on_log."""
    log = Signal(str, str)
    finished = Signal(str)  # error string ("" on success)

    def __init__(self, op_callable):
        super().__init__()
        self._op = op_callable

    def run(self):
        try:
            self._op(lambda lvl, msg: self.log.emit(lvl, msg))
            self.finished.emit("")
        except Exception as e:
            self.log.emit("ERR", str(e))
            self.finished.emit(str(e))


class AnimationPage(QWidget):
    """6-panel storyboard pipeline. All state is persisted to state.json."""

    open_brands = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._project_dir: Path | None = None
        self._state: dict = {}
        self._thread: QThread | None = None
        self._worker: "AnimationOpWorker | None" = None
        self._pending_resume: Path | None = None
        self._pending_on_finish = None
        self._build()
        self.refresh_brands()

    # ── Build ───────────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Animation"); h1.setObjectName("H1")
        sub = QLabel(
            "Multi-shot video ad. Brief → scenario → characters → anchor → shots → export."
        )
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        self._step_pills: list[QLabel] = []
        stepper = QHBoxLayout(); stepper.setSpacing(8); stepper.setContentsMargins(0, 0, 0, 0)
        for name in ("1. Brief", "2. Scenario", "3. Characters", "4. Anchor", "5. Shots", "6. Export"):
            pill = QLabel(name)
            pill.setStyleSheet(
                f"background: {t.BG_INPUT}; color: {t.TEXT_DIM}; padding: 6px 14px; "
                f"border-radius: 999px; font-size: 11px; font-weight: 700;"
            )
            self._step_pills.append(pill)
            stepper.addWidget(pill)
        stepper.addStretch()
        root.addLayout(stepper)

        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 14, 20, 14); llay.setSpacing(8)
        lhead = QHBoxLayout(); lhead.setSpacing(8)
        lh = QLabel("Activity"); lh.setObjectName("H2")
        lhead.addWidget(lh); lhead.addStretch()
        self.live_pill = StatusPill("Idle", t.TEXT_MUTED)
        lhead.addWidget(self.live_pill)
        llay.addLayout(lhead)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFixedHeight(110)
        llay.addWidget(self.log)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_brief_panel())
        self.stack.addWidget(self._build_scenario_panel())
        self.stack.addWidget(self._build_characters_panel())
        self.stack.addWidget(self._build_anchor_panel())
        self.stack.addWidget(self._build_shots_panel())
        self.stack.addWidget(self._build_export_panel())

        body = QVBoxLayout(); body.setSpacing(12)
        body.addWidget(self.stack, 1)
        body.addWidget(log_card)
        root.addLayout(body, 1)

        self._set_step(0)

    def _set_step(self, idx: int):
        idx = max(0, min(5, idx))
        self.stack.setCurrentIndex(idx)
        for i, pill in enumerate(self._step_pills):
            if i == idx:
                pill.setStyleSheet(
                    f"background: {t.ACCENT}; color: #FFFFFF; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )
            elif i < idx:
                pill.setStyleSheet(
                    f"background: {t.SUCCESS_BG}; color: {t.SUCCESS}; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )
            else:
                pill.setStyleSheet(
                    f"background: {t.BG_INPUT}; color: {t.TEXT_DIM}; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )

    # ── Panel 1: Brief ──────────────────────────────────────────────────────

    def _build_brief_panel(self) -> QWidget:
        wrap = QScrollArea(); wrap.setWidgetResizable(True); wrap.setFrameShape(QFrame.NoFrame)
        wrap.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        inner = QWidget()
        form = QVBoxLayout(inner); form.setContentsMargins(0, 0, 0, 0); form.setSpacing(14)

        self.resume_card = QFrame()
        self.resume_card.setObjectName("CardFlat")
        self.resume_card.setStyleSheet(
            f"background: {t.ACCENT}11; border: 1px solid {t.ACCENT}55; border-radius: 12px;"
        )
        rc = QHBoxLayout(self.resume_card); rc.setContentsMargins(16, 12, 16, 12); rc.setSpacing(10)
        self.resume_label = QLabel("")
        self.resume_label.setStyleSheet(f"color: {t.TEXT}; font-size: 12px; font-weight: 600;")
        rc.addWidget(self.resume_label, 1)
        self.resume_btn = QPushButton("Resume")
        self.resume_btn.setObjectName("PrimaryBtn"); self.resume_btn.setCursor(Qt.PointingHandCursor)
        self.resume_btn.clicked.connect(self._on_resume_clicked)
        rc.addWidget(self.resume_btn)
        form.addWidget(self.resume_card)
        self.resume_card.hide()

        form_card = Card()
        fl = QVBoxLayout(form_card); fl.setContentsMargins(22, 20, 22, 20); fl.setSpacing(14)

        nl = QLabel("PROJECT"); nl.setObjectName("Muted")
        fl.addWidget(nl)
        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("e.g. Glow Serum · Q2")
        fl.addWidget(self.project_name)

        bl = QLabel("BRAND DNA"); bl.setObjectName("Muted")
        fl.addWidget(bl)
        brow = QHBoxLayout(); brow.setSpacing(8)
        self.brand_combo = QComboBox()
        brow.addWidget(self.brand_combo, 1)
        manage_btn = QPushButton("Manage")
        manage_btn.setObjectName("GhostBtn"); manage_btn.setCursor(Qt.PointingHandCursor)
        manage_btn.clicked.connect(self.open_brands.emit)
        brow.addWidget(manage_btn)
        fl.addLayout(brow)

        params = QHBoxLayout(); params.setSpacing(12)
        col_im = QVBoxLayout(); col_im.setSpacing(6)
        col_im.addWidget(_field_label("Image model"))
        self.image_model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.image_model.addItem(label, userData=slug)
        col_im.addWidget(self.image_model)
        col_vm = QVBoxLayout(); col_vm.setSpacing(6)
        col_vm.addWidget(_field_label("Video model"))
        self.video_model = QComboBox()
        for slug, label in core.VIDEO_MODEL_CHOICES:
            self.video_model.addItem(label, userData=slug)
        col_vm.addWidget(self.video_model)
        col_a = QVBoxLayout(); col_a.setSpacing(6)
        col_a.addWidget(_field_label("Aspect"))
        self.aspect = QComboBox(); self.aspect.addItems(core.ANIMATION_ASPECTS)
        col_a.addWidget(self.aspect)
        col_d = QVBoxLayout(); col_d.setSpacing(6)
        col_d.addWidget(_field_label("Default duration (s)"))
        self.duration = QSpinBox()
        self.duration.setRange(core.ANIMATION_DURATION_MIN, core.ANIMATION_DURATION_MAX)
        self.duration.setValue(core.ANIMATION_DEFAULT_DURATION)
        col_d.addWidget(self.duration)
        params.addLayout(col_im, 1); params.addLayout(col_vm, 1); params.addLayout(col_a, 1); params.addLayout(col_d, 1)
        fl.addLayout(params)

        bl2 = QLabel("BRIEF  ·  one shot per line"); bl2.setObjectName("Muted")
        fl.addWidget(bl2)
        self.brief = QTextEdit()
        self.brief.setPlaceholderText(
            "Plan 1 (3s) — A hand opens the cream jar in a soft morning bathroom.\n"
            "Plan 2 (4s) — Macro of cream applied to the cheek.\n"
            "Plan 3 (4s) — Smiling face in the mirror, natural light."
        )
        self.brief.setMinimumHeight(140)
        fl.addWidget(self.brief)

        pl = QLabel("PRODUCT  ·  optional"); pl.setObjectName("Muted")
        fl.addWidget(pl)
        prow = QHBoxLayout(); prow.setSpacing(8)
        self.product_name = QLineEdit()
        self.product_name.setPlaceholderText("Product name")
        prow.addWidget(self.product_name, 1)
        self.product_image_path = QLineEdit()
        self.product_image_path.setPlaceholderText("Pick a product image…")
        self.product_image_path.setReadOnly(True)
        prow.addWidget(self.product_image_path, 2)
        pick_p = QPushButton("Pick")
        pick_p.setObjectName("GhostBtn"); pick_p.setCursor(Qt.PointingHandCursor)
        pick_p.clicked.connect(self._pick_product_image)
        prow.addWidget(pick_p)
        fl.addLayout(prow)

        sl = QLabel("STYLE REFERENCES  ·  optional, up to 6 images"); sl.setObjectName("Muted")
        fl.addWidget(sl)
        self.style_refs_paths: list[str] = []
        self.style_refs_label = QLabel("(none picked)")
        self.style_refs_label.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        srow = QHBoxLayout(); srow.setSpacing(8)
        srow.addWidget(self.style_refs_label, 1)
        pick_s = QPushButton("Pick images")
        pick_s.setObjectName("GhostBtn"); pick_s.setCursor(Qt.PointingHandCursor)
        pick_s.clicked.connect(self._pick_style_refs)
        srow.addWidget(pick_s)
        clear_s = QPushButton("Clear")
        clear_s.setObjectName("GhostBtn"); clear_s.setCursor(Qt.PointingHandCursor)
        clear_s.clicked.connect(self._clear_style_refs)
        srow.addWidget(clear_s)
        fl.addLayout(srow)

        fl.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        btn_row.addStretch()
        self.parse_btn = QPushButton("Parse brief →")
        self.parse_btn.setObjectName("PrimaryBtn"); self.parse_btn.setCursor(Qt.PointingHandCursor)
        self.parse_btn.clicked.connect(self._on_parse_clicked)
        btn_row.addWidget(self.parse_btn)
        fl.addLayout(btn_row)

        form.addWidget(form_card)
        form.addStretch()
        wrap.setWidget(inner)
        return wrap

    def _pick_product_image(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Pick product image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if f:
            self.product_image_path.setText(f)

    def _pick_style_refs(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Pick style references", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if files:
            self.style_refs_paths = files[:6]
            self.style_refs_label.setText(
                f"{len(self.style_refs_paths)} image{'s' if len(self.style_refs_paths) > 1 else ''} picked"
            )

    def _clear_style_refs(self):
        self.style_refs_paths = []
        self.style_refs_label.setText("(none picked)")

    # ── Panel 2: Scenario ───────────────────────────────────────────────────

    def _build_scenario_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head = Card()
        hl = QHBoxLayout(head); hl.setContentsMargins(20, 14, 20, 14); hl.setSpacing(10)
        self.scenario_title = QLabel("Scenario"); self.scenario_title.setObjectName("H2")
        hl.addWidget(self.scenario_title); hl.addStretch()
        back = QPushButton("← Brief"); back.setObjectName("GhostBtn"); back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._set_step(0))
        hl.addWidget(back)
        cont = QPushButton("Continue →"); cont.setObjectName("PrimaryBtn"); cont.setCursor(Qt.PointingHandCursor)
        cont.clicked.connect(self._on_scenario_continue)
        hl.addWidget(cont)
        col.addWidget(head)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scenario_inner = QWidget()
        self.scenario_layout = QVBoxLayout(self.scenario_inner)
        self.scenario_layout.setContentsMargins(0, 0, 0, 0); self.scenario_layout.setSpacing(8)
        self.scenario_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.scenario_inner)
        col.addWidget(scroll, 1)
        return wrap

    def _populate_scenario(self):
        while self.scenario_layout.count():
            item = self.scenario_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        if not self._state:
            return

        scenario = self._state.get("scenario") or {}
        style = scenario.get("style") or "—"
        shots = self._state.get("shots") or {}
        n = len(shots)
        total_dur = sum(int(s.get("duration", 0) or 0) for s in shots.values())
        self.scenario_title.setText(f"Scenario · {n} shots · {total_dur}s · style: {style}")

        for sid in sorted(shots.keys(), key=int):
            s = shots[sid]
            row = QFrame()
            row.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 10px;")
            rl = QVBoxLayout(row); rl.setContentsMargins(14, 10, 14, 10); rl.setSpacing(6)
            top = QHBoxLayout(); top.setSpacing(8)
            id_lbl = QLabel(f"shot_{int(sid):03d}")
            id_lbl.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px; font-weight: 700;")
            top.addWidget(id_lbl)
            desc_edit = QLineEdit(s.get("description", ""))
            desc_edit.editingFinished.connect(
                lambda sid=sid, e=desc_edit: self._on_shot_field_changed(sid, "description", e.text())
            )
            top.addWidget(desc_edit, 1)
            dur_edit = QSpinBox()
            dur_edit.setRange(core.ANIMATION_DURATION_MIN, core.ANIMATION_DURATION_MAX)
            dur_edit.setValue(int(s.get("duration", 4)))
            dur_edit.valueChanged.connect(
                lambda v, sid=sid: self._on_shot_field_changed(sid, "duration", v)
            )
            top.addWidget(dur_edit)
            top.addWidget(QLabel("s"))
            chars = ", ".join(s.get("characters") or []) or "—"
            chars_lbl = QLabel(chars)
            chars_lbl.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
            chars_lbl.setMinimumWidth(120)
            top.addWidget(chars_lbl)
            rl.addLayout(top)
            self.scenario_layout.addWidget(row)

    def _on_shot_field_changed(self, sid: str, field: str, value):
        if not self._state or not self._project_dir:
            return
        s = (self._state.get("shots") or {}).get(sid)
        if not s:
            return
        s[field] = int(value) if field == "duration" else value
        core.save_animation_state(self._project_dir, self._state)

    # ── Panel 3: Characters ─────────────────────────────────────────────────

    def _build_characters_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head = Card()
        hl = QHBoxLayout(head); hl.setContentsMargins(20, 14, 20, 14); hl.setSpacing(10)
        self.char_title = QLabel("Characters"); self.char_title.setObjectName("H2")
        hl.addWidget(self.char_title); hl.addStretch()
        back = QPushButton("← Scenario"); back.setObjectName("GhostBtn"); back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._set_step(1))
        hl.addWidget(back)
        gen_all = QPushButton("Generate all"); gen_all.setObjectName("GhostBtn"); gen_all.setCursor(Qt.PointingHandCursor)
        gen_all.clicked.connect(self._on_generate_all_characters)
        hl.addWidget(gen_all)
        cont = QPushButton("Continue →"); cont.setObjectName("PrimaryBtn"); cont.setCursor(Qt.PointingHandCursor)
        cont.clicked.connect(self._on_characters_continue)
        hl.addWidget(cont)
        col.addWidget(head)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.char_inner = QWidget()
        self.char_layout = QGridLayout(self.char_inner)
        self.char_layout.setContentsMargins(0, 0, 0, 0); self.char_layout.setSpacing(12)
        self.char_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.char_inner)
        col.addWidget(scroll, 1)
        return wrap

    def _populate_characters(self):
        while self.char_layout.count():
            item = self.char_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        if not self._state:
            return

        chars = self._state.get("characters") or {}
        if not chars:
            empty = QLabel("No characters detected — you can skip to Anchor.")
            empty.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
            self.char_layout.addWidget(empty, 0, 0)
            self.char_title.setText("Characters · 0")
            return

        approved = sum(1 for c in chars.values() if c.get("status") == "approved")
        self.char_title.setText(f"Characters · {approved}/{len(chars)} approved")

        for i, (cid, c) in enumerate(sorted(chars.items())):
            tile = self._build_character_tile(cid, c)
            row = i // 3
            col = i % 3
            self.char_layout.addWidget(tile, row, col)

    def _build_character_tile(self, cid: str, c: dict) -> QWidget:
        tile = QFrame()
        tile.setObjectName("CardFlat")
        tile.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 12px;")
        tile.setFixedWidth(280)
        lay = QVBoxLayout(tile); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)

        img_path = ""
        if c.get("image") and self._project_dir:
            p = self._project_dir / c["image"]
            if p.exists():
                img_path = str(p)
        if img_path:
            thumb = ThumbLabel(Path(img_path), 256, 256, 10)
            thumb.clicked.connect(lambda _=None, p=Path(img_path): open_path(p))
            lay.addWidget(thumb, alignment=Qt.AlignCenter)
        else:
            ph = QLabel("No portrait yet")
            ph.setFixedSize(256, 256)
            ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet(f"background: {t.BORDER}; color: {t.TEXT_DIM}; border-radius: 10px;")
            lay.addWidget(ph, alignment=Qt.AlignCenter)

        meta = QHBoxLayout(); meta.setSpacing(6)
        name = QLabel(cid); name.setStyleSheet(f"color: {t.TEXT}; font-size: 12px; font-weight: 700;")
        meta.addWidget(name); meta.addStretch()
        status = c.get("status") or "draft"
        status_color = {"approved": t.GREEN, "draft": t.TEXT_MUTED, "generating": t.ACCENT, "failed": t.RED}.get(status, t.TEXT_MUTED)
        status_lbl = QLabel(status)
        status_lbl.setStyleSheet(
            f"background: {status_color}22; color: {status_color}; padding: 2px 8px; "
            f"border-radius: 8px; font-size: 10px; font-weight: 700;"
        )
        meta.addWidget(status_lbl)
        lay.addLayout(meta)

        desc = QLabel(c.get("description", ""))
        desc.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        btns = QHBoxLayout(); btns.setSpacing(6)
        if status == "approved":
            ok = QPushButton("✓ Approved"); ok.setEnabled(False)
            ok.setStyleSheet(
                f"background: {t.GREEN}22; color: {t.GREEN}; border: 1px solid {t.GREEN}55; "
                f"border-radius: 8px; padding: 4px 10px; font-size: 10px; font-weight: 700;"
            )
            btns.addWidget(ok)
        else:
            approve = QPushButton("Approve")
            approve.setObjectName("GhostBtn"); approve.setCursor(Qt.PointingHandCursor)
            approve.setEnabled(bool(img_path))
            approve.clicked.connect(lambda _=None, cid=cid: self._on_approve_character(cid))
            btns.addWidget(approve)
        regen = QPushButton("Regen" if img_path else "Generate")
        regen.setObjectName("GhostBtn"); regen.setCursor(Qt.PointingHandCursor)
        regen.clicked.connect(lambda _=None, cid=cid: self._on_generate_character(cid))
        btns.addWidget(regen)
        lay.addLayout(btns)
        return tile

    # ── Panel 4: Anchor ─────────────────────────────────────────────────────

    def _build_anchor_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head = Card()
        hl = QHBoxLayout(head); hl.setContentsMargins(20, 14, 20, 14); hl.setSpacing(10)
        self.anchor_title = QLabel("Anchor frame · shot 1"); self.anchor_title.setObjectName("H2")
        hl.addWidget(self.anchor_title); hl.addStretch()
        back = QPushButton("← Characters"); back.setObjectName("GhostBtn"); back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._set_step(2))
        hl.addWidget(back)
        col.addWidget(head)

        body = Card()
        bl = QVBoxLayout(body); bl.setContentsMargins(20, 18, 20, 18); bl.setSpacing(10)
        self.anchor_thumb_holder = QHBoxLayout()
        self.anchor_thumb_holder.setAlignment(Qt.AlignCenter)
        bl.addLayout(self.anchor_thumb_holder)
        self.anchor_desc = QLabel("")
        self.anchor_desc.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        self.anchor_desc.setWordWrap(True)
        self.anchor_desc.setAlignment(Qt.AlignCenter)
        bl.addWidget(self.anchor_desc)

        btns = QHBoxLayout(); btns.setSpacing(10); btns.setAlignment(Qt.AlignCenter)
        self.anchor_gen_btn = QPushButton("Generate anchor")
        self.anchor_gen_btn.setObjectName("PrimaryBtn"); self.anchor_gen_btn.setCursor(Qt.PointingHandCursor)
        self.anchor_gen_btn.clicked.connect(self._on_generate_anchor)
        btns.addWidget(self.anchor_gen_btn)
        self.anchor_regen_btn = QPushButton("Regen")
        self.anchor_regen_btn.setObjectName("GhostBtn"); self.anchor_regen_btn.setCursor(Qt.PointingHandCursor)
        self.anchor_regen_btn.clicked.connect(self._on_generate_anchor)
        btns.addWidget(self.anchor_regen_btn)
        self.anchor_approve_btn = QPushButton("✓ Approve & continue")
        self.anchor_approve_btn.setObjectName("PrimaryBtn"); self.anchor_approve_btn.setCursor(Qt.PointingHandCursor)
        self.anchor_approve_btn.clicked.connect(self._on_approve_anchor)
        btns.addWidget(self.anchor_approve_btn)
        bl.addLayout(btns)
        col.addWidget(body, 1)
        return wrap

    def _populate_anchor(self):
        while self.anchor_thumb_holder.count():
            item = self.anchor_thumb_holder.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        if not self._state or not self._project_dir:
            self.anchor_desc.setText("(no project)")
            return
        shot1 = (self._state.get("shots") or {}).get("1")
        if not shot1:
            self.anchor_desc.setText("(no shot 1 in scenario)")
            return
        self.anchor_desc.setText(shot1.get("description", ""))
        img_status = shot1.get("image_status") or "pending"
        img_path = self._project_dir / shot1.get("image_file", "") if shot1.get("image_file") else None
        self.anchor_title.setText(f"Anchor frame · shot 1 · {shot1.get('duration', 0)}s · {img_status}")

        if img_path and img_path.exists():
            thumb = ThumbLabel(Path(img_path), 360, 480, 12)
            thumb.clicked.connect(lambda _=None, p=Path(img_path): open_path(p))
            self.anchor_thumb_holder.addWidget(thumb)
            self.anchor_gen_btn.setVisible(False)
            self.anchor_regen_btn.setVisible(True)
            self.anchor_approve_btn.setVisible(img_status != "approved")
            self.anchor_approve_btn.setEnabled(img_status in ("review", "approved"))
        else:
            ph = QLabel("No anchor yet")
            ph.setFixedSize(360, 480); ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet(f"background: {t.BORDER}; color: {t.TEXT_DIM}; border-radius: 12px;")
            self.anchor_thumb_holder.addWidget(ph)
            self.anchor_gen_btn.setVisible(True)
            self.anchor_regen_btn.setVisible(False)
            self.anchor_approve_btn.setVisible(False)

    # ── Panel 5: Shots ──────────────────────────────────────────────────────

    def _build_shots_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head = Card()
        hl = QHBoxLayout(head); hl.setContentsMargins(20, 14, 20, 14); hl.setSpacing(10)
        self.shots_title = QLabel("Shots"); self.shots_title.setObjectName("H2")
        hl.addWidget(self.shots_title); hl.addStretch()
        back = QPushButton("← Anchor"); back.setObjectName("GhostBtn"); back.setCursor(Qt.PointingHandCursor)
        back.clicked.connect(lambda: self._set_step(3))
        hl.addWidget(back)
        gen_imgs = QPushButton("Generate missing images"); gen_imgs.setObjectName("GhostBtn"); gen_imgs.setCursor(Qt.PointingHandCursor)
        gen_imgs.clicked.connect(self._on_generate_missing_images)
        hl.addWidget(gen_imgs)
        gen_vids = QPushButton("Generate approved videos"); gen_vids.setObjectName("GhostBtn"); gen_vids.setCursor(Qt.PointingHandCursor)
        gen_vids.clicked.connect(self._on_generate_all_videos)
        hl.addWidget(gen_vids)
        cont = QPushButton("Continue →"); cont.setObjectName("PrimaryBtn"); cont.setCursor(Qt.PointingHandCursor)
        cont.clicked.connect(lambda: (self._set_step(5), self._populate_export()))
        hl.addWidget(cont)
        col.addWidget(head)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.shots_inner = QWidget()
        self.shots_layout = QGridLayout(self.shots_inner)
        self.shots_layout.setContentsMargins(0, 0, 0, 0); self.shots_layout.setSpacing(12)
        self.shots_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.shots_inner)
        col.addWidget(scroll, 1)
        return wrap

    def _populate_shots(self):
        while self.shots_layout.count():
            item = self.shots_layout.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        if not self._state:
            return
        shots = self._state.get("shots") or {}
        done = sum(1 for s in shots.values() if s.get("video_status") == "approved")
        self.shots_title.setText(f"Shots · {done}/{len(shots)} done")
        for i, sid in enumerate(sorted(shots.keys(), key=int)):
            tile = self._build_shot_tile(sid, shots[sid])
            row = i // 3
            col_i = i % 3
            self.shots_layout.addWidget(tile, row, col_i)

    def _build_shot_tile(self, sid: str, s: dict) -> QWidget:
        tile = QFrame()
        tile.setObjectName("CardFlat")
        tile.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 12px;")
        tile.setFixedWidth(300)
        lay = QVBoxLayout(tile); lay.setContentsMargins(12, 12, 12, 12); lay.setSpacing(8)

        hdr = QHBoxLayout(); hdr.setSpacing(6)
        title = QLabel(f"shot_{int(sid):03d} · {s.get('duration', 0)}s")
        title.setStyleSheet(f"color: {t.TEXT}; font-size: 11px; font-weight: 700;")
        hdr.addWidget(title); hdr.addStretch()
        for kind, key in (("IMG", "image_status"), ("VID", "video_status")):
            v = s.get(key) or "pending"
            color = {
                "approved": t.GREEN, "review": "#d97706", "generating": t.ACCENT,
                "pending": t.TEXT_MUTED, "failed": t.RED,
            }.get(v, t.TEXT_MUTED)
            badge = QLabel(f"{kind} {v}")
            badge.setStyleSheet(
                f"background: {color}22; color: {color}; padding: 2px 6px; "
                f"border-radius: 6px; font-size: 9px; font-weight: 700;"
            )
            hdr.addWidget(badge)
        lay.addLayout(hdr)

        img_path = self._project_dir / s.get("image_file", "") if (self._project_dir and s.get("image_file")) else None
        if img_path and img_path.exists():
            thumb = ThumbLabel(Path(img_path), 276, 280, 10)
            thumb.clicked.connect(lambda _=None, p=Path(img_path): open_path(p))
            lay.addWidget(thumb, alignment=Qt.AlignCenter)
        else:
            ph = QLabel(s.get("image_status") or "pending")
            ph.setFixedSize(276, 280); ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet(f"background: {t.BORDER}; color: {t.TEXT_DIM}; border-radius: 10px;")
            lay.addWidget(ph, alignment=Qt.AlignCenter)

        desc = QLabel(s.get("description", ""))
        desc.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        vid_path = self._project_dir / s.get("video_file", "") if (self._project_dir and s.get("video_file")) else None
        if vid_path and vid_path.exists():
            play = QPushButton(f"▶  {vid_path.name}")
            play.setObjectName("GhostBtn"); play.setCursor(Qt.PointingHandCursor)
            play.clicked.connect(lambda _=None, p=Path(vid_path): open_path(p))
            lay.addWidget(play)

        btns = QHBoxLayout(); btns.setSpacing(6)
        img_status = s.get("image_status") or "pending"
        vid_status = s.get("video_status") or "pending"
        sid_int = int(sid)

        if img_status == "review":
            ap = QPushButton("Approve image")
            ap.setObjectName("PrimaryBtn"); ap.setCursor(Qt.PointingHandCursor)
            ap.clicked.connect(lambda _=None, sid_int=sid_int: self._on_approve_shot_image(sid_int))
            btns.addWidget(ap)
        elif img_status == "approved" and vid_status in ("pending", "failed"):
            gen = QPushButton("Generate video →")
            gen.setObjectName("PrimaryBtn"); gen.setCursor(Qt.PointingHandCursor)
            gen.clicked.connect(lambda _=None, sid_int=sid_int: self._on_generate_shot_video(sid_int))
            btns.addWidget(gen)
        elif img_status == "approved" and vid_status == "approved":
            ok = QPushButton("✓ Done"); ok.setEnabled(False)
            ok.setStyleSheet(
                f"background: {t.GREEN}22; color: {t.GREEN}; border: 1px solid {t.GREEN}55; "
                f"border-radius: 8px; padding: 4px 10px; font-size: 10px; font-weight: 700;"
            )
            btns.addWidget(ok)
        elif img_status == "failed":
            retry = QPushButton("↻ Retry image")
            retry.setObjectName("GhostBtn"); retry.setCursor(Qt.PointingHandCursor)
            retry.clicked.connect(lambda _=None, sid_int=sid_int: self._on_generate_shot_image(sid_int))
            btns.addWidget(retry)
        else:
            gen = QPushButton("Generate image")
            gen.setObjectName("GhostBtn"); gen.setCursor(Qt.PointingHandCursor)
            gen.clicked.connect(lambda _=None, sid_int=sid_int: self._on_generate_shot_image(sid_int))
            btns.addWidget(gen)

        regen = QPushButton("Regen img")
        regen.setObjectName("GhostBtn"); regen.setCursor(Qt.PointingHandCursor)
        regen.clicked.connect(lambda _=None, sid_int=sid_int: self._on_generate_shot_image(sid_int))
        btns.addWidget(regen)
        if vid_status == "approved":
            rv = QPushButton("Regen vid")
            rv.setObjectName("GhostBtn"); rv.setCursor(Qt.PointingHandCursor)
            rv.clicked.connect(lambda _=None, sid_int=sid_int: self._on_generate_shot_video(sid_int))
            btns.addWidget(rv)
        lay.addLayout(btns)
        return tile

    # ── Panel 6: Export ─────────────────────────────────────────────────────

    def _build_export_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        card = Card()
        cl = QVBoxLayout(card); cl.setContentsMargins(40, 36, 40, 36); cl.setSpacing(14)
        cl.setAlignment(Qt.AlignCenter)
        h = QLabel("Ready"); h.setObjectName("H1")
        h.setAlignment(Qt.AlignCenter)
        cl.addWidget(h)
        self.export_summary = QLabel("")
        self.export_summary.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 13px;")
        self.export_summary.setAlignment(Qt.AlignCenter)
        cl.addWidget(self.export_summary)

        cl.addSpacing(20)
        open_btn = QPushButton("Open folder")
        open_btn.setObjectName("PrimaryBtn"); open_btn.setCursor(Qt.PointingHandCursor)
        open_btn.clicked.connect(self._open_project_folder)
        cl.addWidget(open_btn, alignment=Qt.AlignCenter)
        new_btn = QPushButton("Start new project")
        new_btn.setObjectName("GhostBtn"); new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self._start_new_project)
        cl.addWidget(new_btn, alignment=Qt.AlignCenter)
        col.addWidget(card)
        col.addStretch()
        return wrap

    def _populate_export(self):
        if not self._state:
            self.export_summary.setText("(no project)")
            return
        shots = self._state.get("shots") or {}
        n = len(shots)
        ok = sum(1 for s in shots.values() if s.get("video_status") == "approved")
        total = sum(int(s.get("duration", 0) or 0) for s in shots.values())
        self.export_summary.setText(
            f"{ok}/{n} shots done · {total}s · {self._state.get('aspect_ratio', '—')}"
        )

    def _open_project_folder(self):
        if self._project_dir and self._project_dir.exists():
            open_path(self._project_dir)

    def _start_new_project(self):
        self._project_dir = None
        self._state = {}
        self.project_name.clear()
        self.brief.clear()
        self.product_name.clear()
        self.product_image_path.clear()
        self.style_refs_paths = []
        self.style_refs_label.setText("(none picked)")
        self._set_step(0)
        self._refresh_resume_card()

    # ── Brand picker ────────────────────────────────────────────────────────

    def refresh_brands(self):
        current = self.brand_combo.currentText() if hasattr(self, "brand_combo") else ""
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
        self._refresh_resume_card()

    def _refresh_resume_card(self):
        entry = core.latest_unfinished_animation()
        if not entry:
            self.resume_card.hide()
            return
        st = entry["state"]
        self.resume_label.setText(
            f"Unfinished project: {st.get('project_name') or entry['dir'].name}  ·  "
            f"step: {st.get('status', 'brief')}"
        )
        self._pending_resume = entry["dir"]
        self.resume_card.show()

    def _on_resume_clicked(self):
        d = self._pending_resume
        if not d:
            return
        self._project_dir = Path(d)
        self._state = core.load_animation_state(self._project_dir)
        self._sync_form_from_state()
        self._populate_all()
        status_to_step = {
            "brief": 0, "scenario": 1, "characters": 2,
            "anchor": 3, "shots": 4, "done": 5,
        }
        self._set_step(status_to_step.get(self._state.get("status", "brief"), 0))

    def _sync_form_from_state(self):
        self.project_name.setText(self._state.get("project_name", ""))
        brand = self._state.get("brand", "")
        if brand:
            i = self.brand_combo.findText(brand)
            if i >= 0:
                self.brand_combo.setCurrentIndex(i)
        for slug in core.IMAGE_MODELS:
            if slug == self._state.get("image_model"):
                idx = list(core.IMAGE_MODELS).index(slug)
                self.image_model.setCurrentIndex(idx)
                break
        for slug in core.VIDEO_MODELS:
            if slug == self._state.get("video_model"):
                idx = list(core.VIDEO_MODELS).index(slug)
                self.video_model.setCurrentIndex(idx)
                break
        i = self.aspect.findText(self._state.get("aspect_ratio", "9:16"))
        if i >= 0:
            self.aspect.setCurrentIndex(i)
        self.duration.setValue(int(self._state.get("default_duration", 4)))
        self.brief.setPlainText(self._state.get("brief_text", ""))
        prod = self._state.get("product") or {}
        self.product_name.setText(prod.get("name", ""))
        self.product_image_path.setText(prod.get("image", ""))
        refs = self._state.get("style_refs") or []
        self.style_refs_paths = list(refs)
        self.style_refs_label.setText(
            f"{len(refs)} image{'s' if len(refs) > 1 else ''} loaded" if refs else "(none picked)"
        )

    def _populate_all(self):
        self._populate_scenario()
        self._populate_characters()
        self._populate_anchor()
        self._populate_shots()
        self._populate_export()

    # ── Worker dispatch ─────────────────────────────────────────────────────

    def _is_busy(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _run_op(self, op_callable, on_finish=lambda err: None):
        if self._is_busy():
            QMessageBox.information(self, "Busy", "An operation is already running.")
            return
        self.live_pill.setText("Running")
        self.live_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        self._thread = QThread()
        self._worker = AnimationOpWorker(op_callable)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.log.connect(self._append_log)
        # Stash on_finish on the page so the slot stays a bound method on
        # this QObject — that gives the connection a real receiver thread
        # (main). Connecting to a lambda gives the connection no receiver
        # affinity and Qt invokes it on the *emitter's* thread, which here
        # is the worker thread; calling self._thread.wait() from inside
        # self._thread is what crashed Mimica with "Thread tried to wait
        # on itself" earlier.
        self._pending_on_finish = on_finish
        self._worker.finished.connect(self._on_op_finished)
        self._thread.start()

    def _on_op_finished(self, err: str):
        on_finish = self._pending_on_finish or (lambda _e: None)
        self._pending_on_finish = None
        if self._thread:
            self._thread.quit()
            self._thread.wait()
        self._thread = None
        self._worker = None
        if err:
            self.live_pill.setText("Error")
            self.live_pill.setStyleSheet(
                f"background: {t.RED}22; color: {t.RED}; padding: 4px 10px; "
                f"border-radius: 999px; font-size: 11px; font-weight: 600;"
            )
        else:
            self.live_pill.setText("Done")
            self.live_pill.setStyleSheet(
                f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
                f"border-radius: 999px; font-size: 11px; font-weight: 600;"
            )
        if self._project_dir:
            self._state = core.load_animation_state(self._project_dir)
            self._populate_all()
        try:
            on_finish(err)
        except Exception as e:
            self._append_log("ERR", str(e))

    def _append_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        color = {"INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": t.YELLOW}.get(level, t.TEXT_DIM)
        self.log.appendHtml(
            f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
            f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
            f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
        )

    # ── Brief actions ──────────────────────────────────────────────────────

    def _on_parse_clicked(self):
        if self._is_busy():
            return
        if not self.project_name.text().strip():
            QMessageBox.warning(self, "Project name", "Give the project a name first."); return
        if not self.brand_combo.isEnabled():
            QMessageBox.warning(self, "No brand", "Create a Brand DNA first."); return
        if not self.brief.toPlainText().strip():
            QMessageBox.warning(self, "Brief", "Write a brief — one shot per line."); return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first."); return

        try:
            self._project_dir = core.create_animation_project(
                project_name=self.project_name.text(),
                brand_name=self.brand_combo.currentText(),
                brief_text=self.brief.toPlainText(),
                image_model=self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL,
                video_model=self.video_model.currentData() or core.DEFAULT_VIDEO_MODEL,
                aspect_ratio=self.aspect.currentText(),
                product_name=self.product_name.text(),
                product_image=self.product_image_path.text() or None,
                style_refs=self.style_refs_paths,
                default_duration=self.duration.value(),
            )
        except Exception as e:
            QMessageBox.critical(self, "Project init failed", str(e)); return

        self._state = core.load_animation_state(self._project_dir)
        self._append_log("INFO", f"Project created at {self._project_dir.name}")

        def op(on_log):
            core.run_animation_parse(self._project_dir, on_log)

        self._run_op(op, on_finish=lambda err: (self._set_step(1) if not err else None))

    def _on_scenario_continue(self):
        if not self._state:
            return
        if not (self._state.get("characters") or {}):
            self._set_step(3)
            self._populate_anchor()
            return
        self._set_step(2)
        self._populate_characters()

    # ── Character actions ─────────────────────────────────────────────────

    def _on_generate_character(self, cid: str):
        if not self._project_dir or self._is_busy():
            return
        def op(on_log):
            core.run_animation_character(self._project_dir, cid, on_log)
        self._run_op(op)

    def _on_approve_character(self, cid: str):
        if not self._project_dir:
            return
        try:
            core.approve_animation_character(self._project_dir, cid)
            self._state = core.load_animation_state(self._project_dir)
            self._populate_characters()
        except Exception as e:
            QMessageBox.warning(self, "Approve failed", str(e))

    def _on_generate_all_characters(self):
        if not self._project_dir or self._is_busy():
            return
        chars = (self._state.get("characters") or {})
        def op(on_log):
            for cid, c in chars.items():
                if c.get("status") == "approved":
                    continue
                core.run_animation_character(self._project_dir, cid, on_log)
        self._run_op(op)

    def _on_characters_continue(self):
        if not self._state:
            return
        chars = (self._state.get("characters") or {})
        unapproved = [c for c in chars.values() if c.get("status") != "approved"]
        if unapproved:
            res = QMessageBox.question(
                self, "Some characters not approved",
                f"{len(unapproved)} character(s) are not yet approved. Continue anyway?",
            )
            if res != QMessageBox.Yes:
                return
        self._set_step(3)
        self._populate_anchor()

    # ── Anchor actions ────────────────────────────────────────────────────

    def _on_generate_anchor(self):
        if not self._project_dir or self._is_busy():
            return
        def op(on_log):
            core.run_animation_shot_image(self._project_dir, 1, on_log, use_anchor=False)
        self._run_op(op)

    def _on_approve_anchor(self):
        if not self._project_dir:
            return
        try:
            core.approve_animation_shot_image(self._project_dir, 1)
            self._state = core.load_animation_state(self._project_dir)
            self._populate_anchor()
            self._set_step(4)
            self._populate_shots()
        except Exception as e:
            QMessageBox.warning(self, "Approve failed", str(e))

    # ── Shots actions ─────────────────────────────────────────────────────

    def _on_generate_shot_image(self, sid: int):
        if not self._project_dir or self._is_busy():
            return
        def op(on_log):
            core.run_animation_shot_image(self._project_dir, sid, on_log, use_anchor=True)
        self._run_op(op)

    def _on_approve_shot_image(self, sid: int):
        if not self._project_dir:
            return
        try:
            core.approve_animation_shot_image(self._project_dir, sid)
            self._state = core.load_animation_state(self._project_dir)
            self._populate_shots()
        except Exception as e:
            QMessageBox.warning(self, "Approve failed", str(e))

    def _on_generate_shot_video(self, sid: int):
        if not self._project_dir or self._is_busy():
            return
        def op(on_log):
            core.run_animation_shot_video(self._project_dir, sid, on_log)
        self._run_op(op)

    def _on_generate_missing_images(self):
        if not self._project_dir or self._is_busy():
            return
        shots = (self._state.get("shots") or {})
        targets = [int(sid) for sid, s in shots.items()
                   if int(sid) > 1 and s.get("image_status") in ("pending", "failed")]
        if not targets:
            QMessageBox.information(self, "Nothing to do", "All shots have an image.")
            return
        def op(on_log):
            for sid in sorted(targets):
                core.run_animation_shot_image(self._project_dir, sid, on_log, use_anchor=True)
        self._run_op(op)

    def _on_generate_all_videos(self):
        if not self._project_dir or self._is_busy():
            return
        shots = (self._state.get("shots") or {})
        targets = [int(sid) for sid, s in shots.items()
                   if s.get("image_status") == "approved" and s.get("video_status") in ("pending", "failed")]
        if not targets:
            QMessageBox.information(self, "Nothing to do", "No approved images awaiting video.")
            return
        def op(on_log):
            for sid in sorted(targets):
                core.run_animation_shot_video(self._project_dir, sid, on_log)
            core.finalize_animation_project(self._project_dir)
        self._run_op(op)
