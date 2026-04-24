from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
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


# ─── Dashboard ──────────────────────────────────────────────────────────────

class DashboardPage(QWidget):
    open_generate = Signal()
    open_history = Signal()
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
        h1 = QLabel("Overview"); h1.setObjectName("H1")
        sub = QLabel("Here is the summary of your ad variation production")
        sub.setObjectName("Dim")
        tl.addWidget(h1); tl.addWidget(sub)
        head.addLayout(tl)
        head.addStretch()

        period = QComboBox()
        period.addItems(["This Month", "Last 3 Months", "All Time"])
        period.setFixedWidth(160)
        period.currentIndexChanged.connect(lambda _: self.refresh())
        self.period = period
        head.addWidget(period)

        refresh_btn = QPushButton("  Refresh")
        refresh_btn.setObjectName("GhostBtn")
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh)
        head.addWidget(refresh_btn)

        root.addLayout(head)

        self.stats_row = QHBoxLayout(); self.stats_row.setSpacing(14)
        self.stats_container = QWidget(); self.stats_container.setLayout(self.stats_row)
        root.addWidget(self.stats_container)

        mid = QHBoxLayout(); mid.setSpacing(14)

        wallet = Card()
        wallet.setMinimumHeight(330)
        wlay = QVBoxLayout(wallet); wlay.setContentsMargins(20, 18, 20, 18); wlay.setSpacing(10)
        whead = QHBoxLayout()
        wt = QLabel("Reference Library"); wt.setObjectName("H2")
        whead.addWidget(wt); whead.addStretch()
        new_btn = QPushButton("+ New")
        new_btn.setObjectName("PrimaryBtn")
        new_btn.setCursor(Qt.PointingHandCursor)
        new_btn.clicked.connect(self.open_generate.emit)
        whead.addWidget(new_btn)
        wlay.addLayout(whead)
        wlay.addSpacing(4)
        self.wallet_body = QVBoxLayout(); self.wallet_body.setSpacing(10)
        wlay.addLayout(self.wallet_body)
        wlay.addStretch()
        mid.addWidget(wallet, 45)

        cash = Card()
        cash.setMinimumHeight(330)
        clay = QVBoxLayout(cash); clay.setContentsMargins(22, 20, 22, 18); clay.setSpacing(6)
        ch = QHBoxLayout()
        ct = QLabel("Generation Flow"); ct.setObjectName("Dim"); ct.setStyleSheet(f"color:{t.TEXT_DIM}; font-size: 13px;")
        ch.addWidget(ct); ch.addStretch()
        self.tab_monthly = QPushButton("Monthly"); self.tab_yearly = QPushButton("Yearly")
        for b, active in [(self.tab_monthly, True), (self.tab_yearly, False)]:
            b.setObjectName("TabBtnActive" if active else "TabBtn")
            b.setCursor(Qt.PointingHandCursor)
        self.tab_monthly.clicked.connect(lambda: self._set_tab("monthly"))
        self.tab_yearly.clicked.connect(lambda: self._set_tab("yearly"))
        ch.addWidget(self.tab_monthly); ch.addWidget(self.tab_yearly)
        clay.addLayout(ch)
        self.chart_total = QLabel("$0.00")
        self.chart_total.setObjectName("Huge")
        clay.addWidget(self.chart_total)
        self.chart_wrap = QVBoxLayout()
        clay.addLayout(self.chart_wrap, 1)
        self.chart = BarChart([], unit=" imgs")
        self.chart_wrap.addWidget(self.chart)
        mid.addWidget(cash, 55)

        root.addLayout(mid)

        bottom = Card()
        blay = QVBoxLayout(bottom); blay.setContentsMargins(20, 18, 20, 18); blay.setSpacing(10)
        bh = QHBoxLayout()
        bt = QLabel("Recent Runs"); bt.setObjectName("H2")
        bh.addWidget(bt); bh.addStretch()
        see_all = QPushButton("  See all")
        see_all.setObjectName("GhostBtn")
        see_all.setCursor(Qt.PointingHandCursor)
        see_all.clicked.connect(self.open_history.emit)
        bh.addWidget(see_all)
        blay.addLayout(bh)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Run", "Date", "Iterations", "Resolution", "Aspect", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setShowGrid(False)
        self.table.cellDoubleClicked.connect(self._open_row)
        blay.addWidget(self.table)

        root.addWidget(bottom, 1)

        self._tab = "monthly"

    def _set_tab(self, which: str):
        self._tab = which
        self.tab_monthly.setObjectName("TabBtnActive" if which == "monthly" else "TabBtn")
        self.tab_yearly.setObjectName("TabBtnActive" if which == "yearly" else "TabBtn")
        for b in (self.tab_monthly, self.tab_yearly):
            b.style().unpolish(b); b.style().polish(b)
        self.refresh()

    def refresh(self):
        runs = core.list_runs()
        self._runs = runs

        total_runs = len(runs)
        total_vars = sum(sum(1 for r in run.get("results", []) if r.get("status") == "ok") for run in runs)
        total_cost = sum(core.cost_for_run(r) for r in runs)

        # Stats row
        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        hero = StatCard("zap", "Variations", "All images generated", str(total_vars),
                        hero=True, action="See details")
        c1 = StatCard("wallet", "Total Spend", "Cumulative MuAPI cost",
                      f"${total_cost:.2f}", trend=f"+{len(runs[:5])*0}%" if False else "+0%")
        c1.findChild(QLabel, "HeroBig")  # noop
        c2 = StatCard("chart", "Total Runs", "Batches launched", str(total_runs), trend="")
        self.stats_row.addWidget(hero, 1)
        self.stats_row.addWidget(c1, 1)
        self.stats_row.addWidget(c2, 1)

        # Chart
        self.chart_wrap.removeWidget(self.chart)
        self.chart.deleteLater()

        now = datetime.now()
        if self._tab == "monthly":
            bins = []
            for delta in range(6, -1, -1):
                y = now.year; m = now.month - delta
                while m <= 0:
                    m += 12; y -= 1
                bins.append((y, m, MONTHS[m - 1]))
            counts = {f"{y}-{m}": 0 for y, m, _ in bins}
            costs = {f"{y}-{m}": 0.0 for y, m, _ in bins}
            for r in runs:
                dt = core.parse_run_dt(r["timestamp"])
                if not dt: continue
                k = f"{dt.year}-{dt.month}"
                if k in counts:
                    done = sum(1 for rr in r.get("results", []) if rr.get("status") == "ok")
                    counts[k] += done
                    costs[k] += core.cost_for_run(r)
            labels = [label for _, _, label in bins]
            vals = [counts[f"{y}-{m}"] for y, m, _ in bins]
            # highlight current month
            hi = len(bins) - 1
            unit = " imgs"
            period_cost = sum(costs.values())
        else:
            bins = list(range(now.year - 4, now.year + 1))
            counts = {y: 0 for y in bins}
            costs = {y: 0.0 for y in bins}
            for r in runs:
                dt = core.parse_run_dt(r["timestamp"])
                if not dt or dt.year not in counts: continue
                done = sum(1 for rr in r.get("results", []) if rr.get("status") == "ok")
                counts[dt.year] += done
                costs[dt.year] += core.cost_for_run(r)
            labels = [str(y) for y in bins]
            vals = [counts[y] for y in bins]
            hi = len(bins) - 1
            unit = " imgs"
            period_cost = sum(costs.values())

        self.chart = BarChart(list(zip(labels, vals)), highlight_index=hi, unit=unit)
        self.chart_wrap.addWidget(self.chart)
        self.chart_total.setText(f"${period_cost:.2f}")

        # Reference library (last 4 runs, thumb of ref)
        while self.wallet_body.count():
            item = self.wallet_body.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        shown = runs[:4]
        if not shown:
            empty = QLabel("No runs yet. Click + New to generate your first batch.")
            empty.setObjectName("Dim"); empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {t.TEXT_MUTED}; padding: 30px 0;")
            self.wallet_body.addWidget(empty)
        else:
            for r in shown:
                self.wallet_body.addWidget(self._library_row(r))

        # Recent Runs table
        self.table.setRowCount(0)
        for r in runs[:8]:
            self._insert_run_row(r)

    def _library_row(self, r: dict) -> QWidget:
        row = QFrame()
        row.setStyleSheet(f"background: {t.BG_INPUT}; border-radius: 12px;")
        row.setFixedHeight(68)
        rl = QHBoxLayout(row); rl.setContentsMargins(10, 10, 14, 10); rl.setSpacing(12)
        img_path = r["images"][0] if r["images"] else None
        thumb = ThumbLabel(img_path, 48, 48, 8) if img_path else QLabel()
        if not img_path:
            thumb.setFixedSize(48, 48)
            thumb.setStyleSheet(f"background: {t.BORDER}; border-radius: 8px;")
        rl.addWidget(thumb)
        tx = QVBoxLayout(); tx.setSpacing(2)
        name = Path(r.get("reference") or "Reference").name or "Reference"
        t1 = QLabel(name); t1.setStyleSheet(f"font-weight: 600; font-size: 13px;")
        dt = core.parse_run_dt(r["timestamp"])
        dt_txt = dt.strftime("%d %b %Y · %H:%M") if dt else r["timestamp"]
        p = r.get("params", {})
        t2 = QLabel(f"{dt_txt}  ·  {p.get('iterations','?')} var  ·  {p.get('resolution','?')}  ·  {p.get('aspect_ratio','?')}")
        t2.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        tx.addWidget(t1); tx.addWidget(t2)
        rl.addLayout(tx); rl.addStretch()
        open_btn = icon_button("open", 14, t.TEXT_DIM, "Open folder")
        open_btn.clicked.connect(lambda _=None, path=r["dir"]: open_path(path))
        rl.addWidget(open_btn)
        row.mouseDoubleClickEvent = lambda _ev, run=r: self.open_run.emit(run)
        return row

    def _insert_run_row(self, r: dict):
        row = self.table.rowCount()
        self.table.insertRow(row)
        dt = core.parse_run_dt(r["timestamp"])
        name = Path(r.get("reference") or "Reference").name
        p = r.get("params", {})
        ok = sum(1 for rr in r.get("results", []) if rr.get("status") == "ok")
        fail = sum(1 for rr in r.get("results", []) if rr.get("status") != "ok")
        status_txt = "Completed" if fail == 0 and ok else ("Partial" if ok else "Failed")
        color = t.GREEN if status_txt == "Completed" else (t.YELLOW if status_txt == "Partial" else t.RED)

        cells = [
            name,
            dt.strftime("%d %b %Y · %H:%M") if dt else r["timestamp"],
            f"{ok}/{p.get('iterations','?')}",
            p.get("resolution", "—"),
            p.get("aspect_ratio", "—"),
        ]
        for i, txt in enumerate(cells):
            item = QTableWidgetItem(str(txt))
            if i == 0:
                item.setFont(QFont("Inter", 12, QFont.DemiBold))
            else:
                item.setForeground(QColor(t.TEXT_DIM))
            item.setData(Qt.UserRole, r)
            self.table.setItem(row, i, item)
        pill = StatusPill(status_txt, color)
        wrap = QWidget(); wl = QHBoxLayout(wrap); wl.setContentsMargins(8, 0, 8, 0)
        wl.addWidget(pill); wl.addStretch()
        self.table.setCellWidget(row, 5, wrap)

    def _open_row(self, row: int, _col: int):
        item = self.table.item(row, 0)
        if not item: return
        run = item.data(Qt.UserRole)
        if run: self.open_run.emit(run)


# ─── Generate ───────────────────────────────────────────────────────────────

class GenerateWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, image, n, res, aspects, languages, workers, output_root):
        super().__init__()
        self._args = (image, n, res, aspects, languages, workers)
        self._output_root = output_root
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

        res_col = QVBoxLayout(); res_col.setSpacing(6)
        res_col.addWidget(_field_label("Resolution"))
        self.res = QComboBox(); self.res.addItems(core.RESOLUTIONS); self.res.setCurrentText("1k")
        res_col.addWidget(self.res)
        form.addLayout(res_col)

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

        body.addWidget(form_card, 40)

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
        body.addWidget(right_w, 60)

        root.addLayout(body, 1)

        self._out_dir: Path | None = None
        self._results_count = 0

    def _update_cost(self):
        n = self.n.value()
        m = max(1, len(self.asp.selected()))
        l = max(1, len(self.lang.selected()))
        price = core.COST_PER_IMAGE.get(self.res.currentText(), 0.06)
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
        if not core.get_api_key():
            QMessageBox.warning(self, "Missing key", "Set your MuAPI key in Settings first.")
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
        cols = 4
        for i, img in enumerate(r["images"]):
            thumb = ThumbLabel(img, 180, 180, 12)
            thumb.clicked.connect(lambda path=img: open_path(path))
            self.grid.addWidget(thumb, i // cols, i % cols)


# ─── Settings ───────────────────────────────────────────────────────────────

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20)
        root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Settings"); h1.setObjectName("H1")
        sub = QLabel("Configure your MuAPI credentials and defaults.")
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        card = Card()
        lay = QVBoxLayout(card); lay.setContentsMargins(22, 20, 22, 20); lay.setSpacing(14)

        sect = QLabel("MUAPI KEY"); sect.setObjectName("Muted")
        lay.addWidget(sect)
        row = QHBoxLayout()
        self.key = QLineEdit()
        self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText("paste your MuAPI key")
        self.key.setText(core.get_api_key())
        row.addWidget(self.key)
        toggle = QPushButton("Show"); toggle.setObjectName("GhostBtn")
        toggle.setCursor(Qt.PointingHandCursor); toggle.setCheckable(True)
        def _tog():
            self.key.setEchoMode(QLineEdit.Normal if toggle.isChecked() else QLineEdit.Password)
            toggle.setText("Hide" if toggle.isChecked() else "Show")
        toggle.clicked.connect(_tog)
        row.addWidget(toggle)
        save = QPushButton("Save"); save.setObjectName("PrimaryBtn")
        save.setCursor(Qt.PointingHandCursor)
        save.clicked.connect(self._save)
        row.addWidget(save)
        lay.addLayout(row)

        self.status = QLabel(""); self.status.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        lay.addWidget(self.status)

        tip = QLabel(
            "Key is stored locally in <b>.env</b>. It is sent only to api.muapi.ai "
            "over HTTPS for uploads, LLM prompting, and image generation."
        )
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px; padding-top: 4px;")
        lay.addWidget(tip)

        root.addWidget(card)
        root.addStretch()

    def _save(self):
        v = self.key.text().strip()
        if not v:
            QMessageBox.warning(self, "Empty key", "Paste a key before saving.")
            return
        core.save_api_key(v)
        self.status.setText("Saved.")
        self.status.setStyleSheet(f"color: {t.GREEN}; font-size: 12px;")
        QTimer.singleShot(2500, lambda: self.status.setText(""))


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


# ─── Adapt page ─────────────────────────────────────────────────────────────

class AdaptWorker(QObject):
    log = Signal(str, str)
    result = Signal(dict)
    out_dir_signal = Signal(str)
    finished = Signal(str)

    def __init__(self, ad_paths, brand_name, res, aspects, languages, workers, output_root):
        super().__init__()
        self._args = (ad_paths, brand_name, res, aspects, languages, workers)
        self._output_root = output_root
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
        params_row.addLayout(col_w, 1); params_row.addLayout(col_r, 1)
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

        body.addWidget(form_card, 40)

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
        body.addWidget(right_w, 60)

        root.addLayout(body, 1)

        self.brand_combo.currentIndexChanged.connect(self._on_brand_changed)
        self.drop.paths_changed.connect(lambda _=None: self._update_cost())
        self.res.currentTextChanged.connect(self._update_cost)
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
        price = core.COST_PER_IMAGE.get(self.res.currentText(), 0.06)
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
        if not core.get_api_key():
            QMessageBox.warning(self, "Missing key", "Set your MuAPI key in Settings first."); return

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
                thumb = ThumbLabel(local, 160, 160, 10)
                thumb.clicked.connect(lambda path=local: open_path(path))
                thumb.setToolTip(r.get("source", ""))
                row = (self._results_count - 1) // 4
                col = (self._results_count - 1) % 4
                self.grid.addWidget(thumb, row, col)

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
