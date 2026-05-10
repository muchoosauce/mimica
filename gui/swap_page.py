"""Swap Product page — Seedance v2.0 video-to-video edit.

Workflow (mirrors TwinPage's two-phase pattern):
  Step 1 (Setup)   → drop source video + product packshot, click Analyze
  Step 2 (Review)  → review the LLM-generated swap brief, edit if needed,
                     click Generate to call Seedance
  Step 3 (Result)  → side-by-side preview (system player) + open output folder

The brief contains the literal `@image1` token that Seedance resolves to the
user's packshot at request time. The generation step uploads the source video
and the product image, then calls `seedance-v2.0-video-edit` which preserves
the source's faces / motion / decor / audio sync — only the targeted product
is replaced.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSpinBox, QStackedWidget, QTextEdit,
    QVBoxLayout, QWidget
)

from . import core
from . import theme as t
from .widgets import Card, OutputFolderRow, StatusPill, icon_label, open_path


# ─── Helpers ────────────────────────────────────────────────────────────────

def _field_label(txt: str) -> QLabel:
    l = QLabel(txt)
    l.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px; font-weight: 600;")
    return l


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _append_log(widget: QPlainTextEdit, level: str, msg: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    color = {
        "INFO": t.TEXT_DIM, "OK": t.GREEN, "ERR": t.RED, "WARN": "#F59E0B",
    }.get(level, t.TEXT_DIM)
    widget.appendHtml(
        f'<span style="color:{t.TEXT_MUTED};">[{ts}]</span> '
        f'<span style="color:{color}; font-weight:600;">{level:<4}</span> '
        f'<span style="color:{t.TEXT_DIM};">{_esc(msg)}</span>'
    )


# ─── Drop zones (one for video, one for image) ──────────────────────────────

_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi")
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


class _MediaDropZone(QFrame):
    """Drop zone that accepts either a video or an image, configured per-instance.

    Mirrors the visual language of widgets.DropZone but with a simpler preview
    surface (filename + size — no thumbnail render, since QPixmap can't preview
    videos and a thumbnail for the packshot is good-enough as text + a small icon).
    """
    file_dropped = Signal(str)

    def __init__(self, *, kind: str, parent=None):
        super().__init__(parent)
        if kind not in ("video", "image"):
            raise ValueError(f"_MediaDropZone kind must be 'video' or 'image', got {kind!r}")
        self._kind = kind
        self._path: str = ""
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)
        self.setObjectName("DropZone")
        self.setStyleSheet(f"""
            QFrame#DropZone {{
                background: {t.BG_INPUT};
                border: 1.5px dashed {t.BORDER_LIGHT};
                border-radius: 14px;
            }}
            QFrame#DropZoneActive {{
                background: {t.BG_HOVER};
                border: 1.5px dashed {t.ACCENT};
                border-radius: 14px;
            }}
        """)
        lay = QVBoxLayout(self); lay.setAlignment(Qt.AlignCenter); lay.setSpacing(10)
        icon_name = "broll" if kind == "video" else "image"
        self.icon = icon_label(icon_name, 36, t.TEXT_MUTED)
        self.icon.setAlignment(Qt.AlignCenter)
        self.title = QLabel(
            "Drop the source video here" if kind == "video"
            else "Drop the product packshot here"
        )
        self.title.setStyleSheet(f"color: {t.TEXT}; font-size: 14px; font-weight: 600;")
        self.title.setAlignment(Qt.AlignCenter)
        self.sub = QLabel(
            "or click to browse · MP4 / MOV / WEBM, ≤10 MB, ≤15 s"
            if kind == "video"
            else "or click to browse · PNG / JPG / WEBP, ≤10 MB"
        )
        self.sub.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        self.sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.icon, alignment=Qt.AlignCenter)
        lay.addWidget(self.title)
        lay.addWidget(self.sub)

    def set_file(self, path: str) -> None:
        p = Path(path)
        if not p.exists():
            return
        ext = p.suffix.lower()
        if self._kind == "video" and ext not in _VIDEO_EXTS:
            QMessageBox.warning(
                self, "Unsupported video file",
                f"{p.name} doesn't look like a video. Accepted: {', '.join(_VIDEO_EXTS)}",
            )
            return
        if self._kind == "image" and ext not in _IMAGE_EXTS:
            QMessageBox.warning(
                self, "Unsupported image file",
                f"{p.name} doesn't look like an image. Accepted: {', '.join(_IMAGE_EXTS)}",
            )
            return
        self._path = str(p)
        try:
            sz = p.stat().st_size
        except OSError:
            sz = 0
        self.title.setText(p.name)
        self.sub.setText(
            f"{sz/1e6:.1f} MB — click to replace"
            if sz >= 1e6 else f"{sz/1e3:.0f} KB — click to replace"
        )
        self.file_dropped.emit(self._path)

    def path(self) -> str:
        return self._path

    # --- Mouse / DnD plumbing (same shape as widgets.DropZone) ---

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        if ev.button() != Qt.LeftButton:
            return
        if self._kind == "video":
            filt = "Videos (*.mp4 *.mov *.webm *.mkv *.m4v *.avi)"
            title = "Select source video"
        else:
            filt = "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
            title = "Select product image"
        p, _ = QFileDialog.getOpenFileName(self, title, "", filt)
        if p:
            self.set_file(p)

    def dragEnterEvent(self, ev: QDragEnterEvent) -> None:
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            self.setObjectName("DropZoneActive")
            self.style().unpolish(self); self.style().polish(self)

    def dragLeaveEvent(self, ev) -> None:
        self.setObjectName("DropZone")
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, ev: QDropEvent) -> None:
        for url in ev.mimeData().urls():
            p = url.toLocalFile()
            if p:
                self.set_file(p)
                break
        self.setObjectName("DropZone")
        self.style().unpolish(self); self.style().polish(self)


# ─── Background workers ─────────────────────────────────────────────────────

class SwapAnalyzeWorker(QObject):
    """Phase A — extract keyframes + Vision call. Returns the swap brief."""
    log = Signal(str, str)
    finished = Signal(dict)  # full result dict from core.run_swap_analyze (or {} on error)

    def __init__(self, source_path: str, product_path: str, hint: str, output_root: str):
        super().__init__()
        self._source = source_path
        self._product = product_path
        self._hint = hint
        self._output_root = output_root

    def run(self) -> None:
        result = core.run_swap_analyze(
            self._source,
            self._product,
            self._hint,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            output_root=self._output_root,
        )
        self.finished.emit(result or {})


class SwapGenerateWorker(QObject):
    """Phase B — upload + Seedance video-edit. Returns the output mp4 path."""
    log = Signal(str, str)
    finished = Signal(str)  # absolute output path, or "" on error

    def __init__(
        self,
        work_dir: str,
        source_path: str,
        product_path: str,
        brief: str,
        duration: int,
        aspect_ratio: str,
        quality: str,
        video_info: dict,
    ):
        super().__init__()
        self._work_dir = work_dir
        self._source = source_path
        self._product = product_path
        self._brief = brief
        self._duration = duration
        self._aspect = aspect_ratio
        self._quality = quality
        self._info = video_info

    def run(self) -> None:
        out = core.run_swap_generate(
            self._work_dir,
            self._source,
            self._product,
            self._brief,
            self._duration,
            on_log=lambda lvl, msg: self.log.emit(lvl, msg),
            aspect_ratio=self._aspect,
            quality=self._quality,
            video_info=self._info,
        )
        self.finished.emit(str(out) if out else "")


# ─── Page ───────────────────────────────────────────────────────────────────

class SwapPage(QWidget):
    """Two-step page: Setup → Result.

    Step 1 has source + product drop zones, options, and an Analyze button.
    Step 2 (revealed after analysis) has the editable brief + Generate button.
    Once a swap is done, the result section appears with playback shortcuts
    and a Regenerate button that re-runs Seedance with the (possibly edited)
    brief — no need to redo the Vision pass.
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")

        # State
        self._analyze_worker: SwapAnalyzeWorker | None = None
        self._generate_worker: SwapGenerateWorker | None = None
        self._thread: QThread | None = None
        self._work_dir: str = ""
        self._source_path: str = ""
        self._product_path: str = ""
        self._video_info: dict = {}
        self._output_path: str = ""

        self._build()

    # ── Build ───────────────────────────────────────────────────────────────

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Swap product"); h1.setObjectName("H1")
        sub = QLabel(
            "Drop a competitor's video and your own product packshot. Seedance 2.0 "
            "renders the same video — same person, same gestures, same audio — with "
            "your product in hand."
        )
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        # Stepper pills
        self.stepper = QHBoxLayout()
        self.stepper.setSpacing(8); self.stepper.setContentsMargins(0, 0, 0, 0)
        self._step_pills: list[QLabel] = []
        for name in ("1. Setup", "2. Review brief", "3. Result"):
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
        self.stack.addWidget(self._build_result_panel())
        root.addWidget(self.stack, 1)
        self._set_step(0)

    def _set_step(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)
        for i, pill in enumerate(self._step_pills):
            if i == idx:
                pill.setStyleSheet(
                    f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 6px 14px; "
                    f"border-radius: 999px; font-size: 11px; font-weight: 700;"
                )
            elif i < idx:
                pill.setStyleSheet(
                    f"background: {t.GREEN}22; color: {t.GREEN}; padding: 6px 14px; "
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

        # --- Drop zones ---
        drops_row = QHBoxLayout(); drops_row.setSpacing(12)
        col_v = QVBoxLayout(); col_v.setSpacing(6)
        col_v.addWidget(_field_label("SOURCE VIDEO"))
        self.video_drop = _MediaDropZone(kind="video")
        col_v.addWidget(self.video_drop)
        drops_row.addLayout(col_v, 1)

        col_p = QVBoxLayout(); col_p.setSpacing(6)
        col_p.addWidget(_field_label("YOUR PRODUCT"))
        self.product_drop = _MediaDropZone(kind="image")
        col_p.addWidget(self.product_drop)
        drops_row.addLayout(col_p, 1)
        form.addLayout(drops_row)

        # --- Hint (optional) ---
        form.addWidget(_field_label("HINT  ·  optional"))
        self.hint = QTextEdit()
        self.hint.setPlaceholderText(
            "Optional directive for Vision. Ex: 'keep the bottle upright' / "
            "'show the label clearly' / 'frame the product slightly larger'"
        )
        self.hint.setMinimumHeight(56); self.hint.setMaximumHeight(96)
        form.addWidget(self.hint)

        # --- Params ---
        params_row = QHBoxLayout(); params_row.setSpacing(14)
        col_d = QVBoxLayout(); col_d.setSpacing(6)
        col_d.addWidget(_field_label("Output duration (s)"))
        self.duration = QSpinBox(); self.duration.setRange(4, 15); self.duration.setValue(5)
        col_d.addWidget(self.duration)
        col_q = QVBoxLayout(); col_q.setSpacing(6)
        col_q.addWidget(_field_label("Quality"))
        self.quality = QComboBox(); self.quality.addItems(["basic", "high"])
        self.quality.setCurrentText("basic")
        col_q.addWidget(self.quality)
        params_row.addLayout(col_d, 1); params_row.addLayout(col_q, 1)
        form.addLayout(params_row)

        # --- Output folder ---
        form.addWidget(_field_label("OUTPUT FOLDER"))
        self.out_row = OutputFolderRow()
        form.addWidget(self.out_row)

        # --- Cost line ---
        self.cost_label = QLabel()
        self.cost_label.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        form.addWidget(self.cost_label)
        self._update_cost()
        self.duration.valueChanged.connect(self._update_cost)

        form.addSpacing(8)
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self.analyze_btn = QPushButton("Analyze video")
        self.analyze_btn.setObjectName("PrimaryBtn")
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._start_analyze)
        btn_row.addWidget(self.analyze_btn); btn_row.addStretch()
        form.addLayout(btn_row)
        form.addStretch()

        body.addWidget(form_card, 5)

        # --- Activity log on the right ---
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

    def _update_cost(self) -> None:
        provider = core.get_active_provider_name()
        rate = core.cost_per_video(provider, "seedance_2", 1)
        d = self.duration.value()
        self.cost_label.setText(
            f"≈ ${rate * d:.2f} for {d}s of Seedance video-edit (+ 1 LLM Vision call)"
        )

    # --- Phase A: analyze ---

    def _start_analyze(self) -> None:
        src = self.video_drop.path()
        prod = self.product_drop.path()
        if not src or not prod:
            QMessageBox.warning(
                self, "Missing inputs",
                "Drop both a source video and a product packshot first.",
            )
            return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first.")
            return

        self.log.clear()
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing…")
        self._set_pill_running()

        self._thread = QThread()
        self._analyze_worker = SwapAnalyzeWorker(
            src, prod,
            self.hint.toPlainText().strip(),
            self.out_row.path(),
        )
        self._analyze_worker.moveToThread(self._thread)
        self._thread.started.connect(self._analyze_worker.run)
        self._analyze_worker.log.connect(self._on_log)
        self._analyze_worker.finished.connect(self._on_analyze_finished)
        self._thread.start()

    def _on_log(self, level: str, msg: str) -> None:
        _append_log(self.log, level, msg)

    def _on_analyze_finished(self, result: dict) -> None:
        self._thread.quit(); self._thread.wait()
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Analyze video")
        if not result or not result.get("brief"):
            self._set_pill_failed()
            return
        self._set_pill_done()
        self._work_dir = result.get("work_dir", "")
        self._source_path = result.get("source_path", "")
        self._product_path = result.get("product_path", "")
        self._video_info = result.get("video_info", {}) or {}
        self.brief_edit.setPlainText(result["brief"])
        self._set_step(1)

    # ── Step 2: Review brief ────────────────────────────────────────────────

    def _build_review_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head_card = Card()
        hl = QHBoxLayout(head_card); hl.setContentsMargins(20, 16, 20, 16); hl.setSpacing(12)
        title = QLabel("Review the swap brief"); title.setObjectName("H2")
        hl.addWidget(title); hl.addStretch()
        regen_btn = QPushButton("Re-analyze")
        regen_btn.setObjectName("GhostBtn"); regen_btn.setCursor(Qt.PointingHandCursor)
        regen_btn.clicked.connect(self._start_analyze)
        hl.addWidget(regen_btn)
        back_btn = QPushButton("← Back to setup")
        back_btn.setObjectName("GhostBtn"); back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._set_step(0))
        hl.addWidget(back_btn)
        self.generate_btn = QPushButton("Generate swap")
        self.generate_btn.setObjectName("PrimaryBtn"); self.generate_btn.setCursor(Qt.PointingHandCursor)
        self.generate_btn.clicked.connect(self._start_generate)
        hl.addWidget(self.generate_btn)
        col.addWidget(head_card)

        prompt_card = Card()
        pl = QVBoxLayout(prompt_card); pl.setContentsMargins(20, 18, 20, 18); pl.setSpacing(10)
        helper = QLabel(
            "This is the brief Seedance will follow. Keep <code>@image1</code> in the text — "
            "it's the placeholder for your product packshot. Edit anything else: gestures, "
            "what to preserve, label visibility, grip adjustments…"
        )
        helper.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        helper.setTextFormat(Qt.RichText)
        helper.setWordWrap(True)
        pl.addWidget(helper)
        self.brief_edit = QTextEdit()
        self.brief_edit.setMinimumHeight(220)
        pl.addWidget(self.brief_edit, 1)
        col.addWidget(prompt_card, 1)

        log_card = Card()
        llay = QVBoxLayout(log_card); llay.setContentsMargins(20, 18, 20, 18); llay.setSpacing(10)
        lh = QLabel("Activity"); lh.setObjectName("H2")
        llay.addWidget(lh)
        self.gen_log = QPlainTextEdit(); self.gen_log.setReadOnly(True); self.gen_log.setMinimumHeight(120)
        llay.addWidget(self.gen_log)
        col.addWidget(log_card)
        return wrap

    # --- Phase B: generate ---

    def _start_generate(self) -> None:
        brief = self.brief_edit.toPlainText().strip()
        if not brief:
            QMessageBox.warning(self, "Empty brief", "The swap brief cannot be empty.")
            return
        if "@image1" not in brief:
            ans = QMessageBox.question(
                self, "Brief is missing @image1",
                "Without `@image1` Seedance won't know what product to swap to. "
                "Generate anyway?",
            )
            if ans != QMessageBox.Yes:
                return

        self.gen_log.clear()
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating… (~2-6 min)")

        self._thread = QThread()
        self._generate_worker = SwapGenerateWorker(
            self._work_dir,
            self._source_path,
            self._product_path,
            brief,
            self.duration.value(),
            "9:16",  # default — _swap_aspect_for picks the actual one in core
            self.quality.currentText(),
            self._video_info,
        )
        self._generate_worker.moveToThread(self._thread)
        self._thread.started.connect(self._generate_worker.run)
        self._generate_worker.log.connect(
            lambda lvl, msg: _append_log(self.gen_log, lvl, msg)
        )
        self._generate_worker.finished.connect(self._on_generate_finished)
        self._thread.start()

    def _on_generate_finished(self, out_path: str) -> None:
        self._thread.quit(); self._thread.wait()
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate swap")
        if not out_path:
            return
        self._output_path = out_path
        self.result_path_lbl.setText(out_path)
        self._set_step(2)

    # ── Step 3: Result ──────────────────────────────────────────────────────

    def _build_result_panel(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(14)

        head_card = Card()
        hl = QHBoxLayout(head_card); hl.setContentsMargins(20, 16, 20, 16); hl.setSpacing(12)
        title = QLabel("Swap ready"); title.setObjectName("H2")
        hl.addWidget(title); hl.addStretch()

        back_btn = QPushButton("← Tweak brief")
        back_btn.setObjectName("GhostBtn"); back_btn.setCursor(Qt.PointingHandCursor)
        back_btn.clicked.connect(lambda: self._set_step(1))
        hl.addWidget(back_btn)
        regen_btn = QPushButton("Regenerate")
        regen_btn.setObjectName("GhostBtn"); regen_btn.setCursor(Qt.PointingHandCursor)
        regen_btn.clicked.connect(self._start_generate)
        hl.addWidget(regen_btn)
        col.addWidget(head_card)

        body_card = Card()
        bl = QVBoxLayout(body_card); bl.setContentsMargins(22, 20, 22, 20); bl.setSpacing(12)
        lbl = QLabel("Output mp4")
        lbl.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px; font-weight: 600;")
        bl.addWidget(lbl)
        self.result_path_lbl = QLabel("—")
        self.result_path_lbl.setStyleSheet(
            f"color: {t.TEXT}; font-size: 13px; "
            f"background: {t.BG_INPUT}; padding: 10px 12px; border-radius: 8px;"
        )
        self.result_path_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.result_path_lbl.setWordWrap(True)
        bl.addWidget(self.result_path_lbl)

        actions = QHBoxLayout(); actions.setSpacing(10)
        play_btn = QPushButton("▶  Play swapped")
        play_btn.setObjectName("PrimaryBtn"); play_btn.setCursor(Qt.PointingHandCursor)
        play_btn.clicked.connect(self._play_output)
        actions.addWidget(play_btn)
        play_src_btn = QPushButton("▶  Play source")
        play_src_btn.setObjectName("GhostBtn"); play_src_btn.setCursor(Qt.PointingHandCursor)
        play_src_btn.clicked.connect(self._play_source)
        actions.addWidget(play_src_btn)
        folder_btn = QPushButton("Open folder")
        folder_btn.setObjectName("GhostBtn"); folder_btn.setCursor(Qt.PointingHandCursor)
        folder_btn.clicked.connect(self._open_folder)
        actions.addWidget(folder_btn)
        actions.addStretch()
        bl.addLayout(actions)

        bl.addSpacing(6)
        info = QLabel(
            "Compare side-by-side in your system player. The audio of the source "
            "video is preserved verbatim — lip-sync stays intact."
        )
        info.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 12px;")
        info.setWordWrap(True)
        bl.addWidget(info)
        col.addWidget(body_card)

        col.addStretch()
        return wrap

    def _play_output(self) -> None:
        if self._output_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._output_path))

    def _play_source(self) -> None:
        if self._source_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._source_path))

    def _open_folder(self) -> None:
        if self._work_dir:
            open_path(Path(self._work_dir))

    # ── Status pill helpers ─────────────────────────────────────────────────

    def _set_pill_running(self) -> None:
        self.live_pill.setText("Running")
        self.live_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

    def _set_pill_done(self) -> None:
        self.live_pill.setText("Done")
        self.live_pill.setStyleSheet(
            f"background: {t.GREEN}22; color: {t.GREEN}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )

    def _set_pill_failed(self) -> None:
        self.live_pill.setText("Failed")
        self.live_pill.setStyleSheet(
            f"background: {t.RED}22; color: {t.RED}; padding: 4px 10px; "
            f"border-radius: 10px; font-size: 11px; font-weight: 600;"
        )
