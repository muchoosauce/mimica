"""ImageGeneratorPage — free-form "describe & generate" image surface.

The simplest entry into the Mimica image stack: no brand DNA required, no
source ad required. The user types what they want, optionally drops up to
8 reference images, picks a model + aspect + resolution + N variants,
and hits Generate.

Reference UX:
- Each uploaded reference gets a numbered chip (Reference 1, 2, ...).
- Clicking a chip inserts `@imageN` at the current cursor position in
  the prompt textarea. The image-gen providers (NanoBanana, GPT Image 2,
  Seedream, ...) parse those tokens natively and bind them to the
  matching uploaded image.

Pattern parity with IterationPage / GeneratePage / etc.: same QThread +
worker pattern, same log widget, same results grid.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QVBoxLayout, QWidget,
)

from . import core
from . import theme as t
from .widgets import Card, StatusPill


# Helpers — duplicated from pages.py to keep this module self-contained.
def _field_label(text: str) -> QLabel:
    lab = QLabel(text); lab.setObjectName("Muted"); return lab


def open_path(p: Path) -> None:
    """Open a file or folder in the OS file manager."""
    import subprocess, sys as _sys
    p = Path(p)
    if _sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    elif _sys.platform == "win32":
        subprocess.Popen(["explorer", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])


MAX_REFERENCES = 8


class ImageGenerateWorker(QObject):
    """Drives one run_image_generate call on a QThread."""
    log = Signal(str, str)
    result = Signal(dict)
    finished = Signal(str, int)   # out_dir, count_ok

    def __init__(
        self,
        prompt: str,
        references: list[str],
        n_variants: int,
        image_model: str,
        resolution: str,
        aspect: str,
        workers: int,
    ):
        super().__init__()
        self._prompt = prompt
        self._references = references
        self._n = n_variants
        self._image_model = image_model
        self._resolution = resolution
        self._aspect = aspect
        self._workers = workers
        self._cancel = False
        self._out_dir = ""
        self._count_ok = 0

    def cancel(self):
        self._cancel = True

    def _on_result(self, r: dict):
        if r.get("status") == "ok":
            self._count_ok += 1
        self.result.emit(r)

    def _on_out_dir(self, p):
        self._out_dir = str(p)

    def run(self):
        try:
            core.run_image_generate(
                self._prompt,
                self._n,
                self._resolution,
                self._aspect,
                self._workers,
                on_log=lambda lvl, msg: self.log.emit(lvl, msg),
                on_result=self._on_result,
                references=self._references,
                on_out_dir=self._on_out_dir,
                should_cancel=lambda: self._cancel,
                image_model=self._image_model,
            )
        except Exception as e:
            self.log.emit("ERR", str(e))
        self.finished.emit(self._out_dir, self._count_ok)


class ImageGeneratorPage(QWidget):
    """Free-form image generation. Inspired by Higgsfield's Image Generator
    panel but tuned for Mimica's models and conventions."""

    open_brands = Signal()   # never emitted — kept for sidebar parity

    def __init__(self):
        super().__init__()
        self.setObjectName("Root")
        # List of {"path": str, "thumb_widget": QLabel, "row_widget": QFrame}
        self._references: list[dict] = []
        self._thread: Optional[QThread] = None
        self._worker: Optional[ImageGenerateWorker] = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 20, 28, 20); root.setSpacing(18)

        head = QVBoxLayout(); head.setSpacing(2)
        h1 = QLabel("Generate"); h1.setObjectName("H1")
        sub = QLabel(
            "Describe what you want. Drop up to 8 reference images to anchor "
            "the result — click a reference chip to insert @imageN into your "
            "prompt at the cursor."
        )
        sub.setObjectName("Dim")
        head.addWidget(h1); head.addWidget(sub)
        root.addLayout(head)

        # Two-column body: left = form, right = log + results.
        body = QHBoxLayout(); body.setSpacing(18)

        # ── LEFT: form ─────────────────────────────────────────────────
        form_card = Card()
        form = QVBoxLayout(form_card); form.setContentsMargins(20, 18, 20, 18); form.setSpacing(14)

        # Model picker
        form.addWidget(_field_label("MODEL"))
        self.image_model = QComboBox()
        for slug, label in core.IMAGE_MODEL_CHOICES:
            self.image_model.addItem(label, userData=slug)
        # Default to GPT Image 2 — same default as Iteration.
        for i in range(self.image_model.count()):
            if self.image_model.itemData(i) == "gpt_image_2":
                self.image_model.setCurrentIndex(i); break
        self.image_model.setMinimumWidth(220)
        form.addWidget(self.image_model)

        # References zone
        refs_head = QHBoxLayout(); refs_head.setSpacing(8)
        refs_head.addWidget(_field_label("REFERENCES"))
        self.refs_count_lbl = QLabel(f"0 / {MAX_REFERENCES}")
        self.refs_count_lbl.setStyleSheet(f"color: {t.TEXT_DIM}; font-size: 11px;")
        refs_head.addStretch(); refs_head.addWidget(self.refs_count_lbl)
        form.addLayout(refs_head)

        self.refs_container = QFrame()
        self.refs_layout = QHBoxLayout(self.refs_container)
        self.refs_layout.setContentsMargins(0, 0, 0, 0); self.refs_layout.setSpacing(8)
        # "+ Add" button always at the tail.
        self.add_ref_btn = QPushButton("+ Add")
        self.add_ref_btn.setObjectName("GhostBtn")
        self.add_ref_btn.setCursor(Qt.PointingHandCursor)
        self.add_ref_btn.setFixedSize(86, 86)
        self.add_ref_btn.clicked.connect(self._on_add_reference)
        self.refs_layout.addWidget(self.add_ref_btn)
        self.refs_layout.addStretch()
        form.addWidget(self.refs_container)

        # Prompt
        form.addWidget(_field_label("PROMPT"))
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText(
            "Describe your image — click a reference above to insert @imageN"
        )
        self.prompt.setMinimumHeight(140)
        form.addWidget(self.prompt)

        # Bottom row: count + aspect + resolution
        controls = QHBoxLayout(); controls.setSpacing(10)
        controls.addWidget(_field_label("Variants"))
        self.n_spin = QSpinBox(); self.n_spin.setRange(1, 8); self.n_spin.setValue(1)
        self.n_spin.setFixedWidth(72)
        controls.addWidget(self.n_spin)
        controls.addSpacing(12)
        controls.addWidget(_field_label("Aspect"))
        self.aspect = QComboBox(); self.aspect.addItems(core.ASPECTS); self.aspect.setCurrentText("1:1")
        self.aspect.setFixedWidth(80)
        controls.addWidget(self.aspect)
        controls.addSpacing(12)
        controls.addWidget(_field_label("Resolution"))
        self.resolution = QComboBox(); self.resolution.addItems(core.RESOLUTIONS); self.resolution.setCurrentText("1k")
        self.resolution.setFixedWidth(80)
        controls.addWidget(self.resolution)
        controls.addStretch()
        form.addLayout(controls)

        # Generate button
        self.run_btn = QPushButton("Generate")
        self.run_btn.setObjectName("PrimaryBtn")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.setFixedHeight(40)
        self.run_btn.clicked.connect(self._on_generate)
        form.addWidget(self.run_btn)

        body.addWidget(form_card, 4)

        # ── RIGHT: log + results ──────────────────────────────────────
        right = QVBoxLayout(); right.setSpacing(14)

        log_card = Card()
        ll = QVBoxLayout(log_card); ll.setContentsMargins(20, 14, 20, 14); ll.setSpacing(8)
        head_log = QHBoxLayout()
        head_log.addWidget(QLabel("Activity", objectName="H2"))
        head_log.addStretch()
        self.status_pill = StatusPill("Idle", t.TEXT_MUTED)
        head_log.addWidget(self.status_pill)
        ll.addLayout(head_log)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True); self.log.setFixedHeight(160)
        ll.addWidget(self.log)
        right.addWidget(log_card)

        res_card = Card()
        rl = QVBoxLayout(res_card); rl.setContentsMargins(20, 18, 20, 18); rl.setSpacing(10)
        rhead = QHBoxLayout()
        rhead.addWidget(QLabel("Results", objectName="H2"))
        rhead.addStretch()
        self.open_folder_btn = QPushButton("Open folder")
        self.open_folder_btn.setObjectName("GhostBtn")
        self.open_folder_btn.setCursor(Qt.PointingHandCursor)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_out_dir)
        rhead.addWidget(self.open_folder_btn)
        rl.addLayout(rhead)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.results_container = QWidget()
        self.results_grid = QGridLayout(self.results_container)
        self.results_grid.setSpacing(10); self.results_grid.setContentsMargins(0, 0, 0, 0)
        self.results_grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(self.results_container)
        scroll.setMinimumHeight(280)
        rl.addWidget(scroll)
        right.addWidget(res_card, 1)

        right_w = QWidget(); right_w.setLayout(right)
        body.addWidget(right_w, 5)
        root.addLayout(body, 1)

        self._refresh_refs_count()

    # ── References ────────────────────────────────────────────────────

    def _on_add_reference(self):
        if len(self._references) >= MAX_REFERENCES:
            QMessageBox.information(self, "Max references", f"{MAX_REFERENCES} max — remove one first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Pick reference images",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        for p in paths:
            if len(self._references) >= MAX_REFERENCES:
                break
            self._add_reference_widget(p)
        self._refresh_refs_count()

    def _add_reference_widget(self, path: str):
        idx = len(self._references) + 1
        chip = QFrame()
        chip.setStyleSheet(
            f"QFrame {{ background: {t.BG_INPUT}; border: 1px solid {t.BORDER};"
            f" border-radius: 10px; }}"
            f"QFrame:hover {{ border: 1px solid {t.ACCENT}; }}"
        )
        chip.setFixedSize(86, 86)
        chip.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(chip); lay.setContentsMargins(4, 4, 4, 4); lay.setSpacing(2)
        thumb = QLabel(); thumb.setAlignment(Qt.AlignCenter)
        thumb.setFixedSize(78, 56)
        thumb.setStyleSheet(f"background: {t.BG_HOVER}; border-radius: 6px;")
        pm = QPixmap(path)
        if not pm.isNull():
            thumb.setPixmap(pm.scaled(78, 56, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(thumb)
        cap = QLabel(f"@image{idx}")
        cap.setStyleSheet(f"color: {t.ACCENT_SOFT}; font-size: 10px; font-weight: 600;")
        cap.setAlignment(Qt.AlignCenter)
        lay.addWidget(cap)

        # Whole chip is clickable → insert @imageN at cursor + small "x" to remove
        # accessible via right-click context (Qt MouseButton). To keep it simple
        # in UI we wire a single-click to insert and a long-press / shift-click
        # to remove — but for clarity we add a small "X" button at the top-right.
        x_btn = QPushButton("×", chip)
        x_btn.setObjectName("OnCardBtn")
        x_btn.setCursor(Qt.PointingHandCursor)
        x_btn.setFixedSize(18, 18)
        x_btn.move(64, 2)
        x_btn.setStyleSheet(
            f"QPushButton#OnCardBtn {{ background: rgba(0,0,0,0.55); color: white;"
            f" border-radius: 9px; font-size: 12px; font-weight: 700; }}"
            f"QPushButton#OnCardBtn:hover {{ background: rgba(0,0,0,0.85); }}"
        )

        def _insert_token(_ev=None):
            self._insert_at_cursor(f"@image{self._index_of(path)} ")
        chip.mousePressEvent = lambda ev: _insert_token() if ev.button() == Qt.LeftButton else None

        def _remove():
            self._remove_reference(path)
        x_btn.clicked.connect(_remove)

        # Insert chip BEFORE the trailing "+ Add" button.
        insert_pos = self.refs_layout.indexOf(self.add_ref_btn)
        self.refs_layout.insertWidget(insert_pos, chip)

        self._references.append({"path": path, "widget": chip, "x_btn": x_btn})

    def _remove_reference(self, path: str):
        # Find + remove + relabel chips so @image numbers stay contiguous.
        for entry in self._references:
            if entry["path"] == path:
                entry["widget"].setParent(None)
                self._references.remove(entry)
                break
        # Relabel all remaining refs.
        for i, entry in enumerate(self._references, 1):
            chip = entry["widget"]
            cap = chip.findChildren(QLabel)
            if cap and len(cap) >= 2:
                cap[1].setText(f"@image{i}")
        self._refresh_refs_count()

    def _index_of(self, path: str) -> int:
        for i, entry in enumerate(self._references, 1):
            if entry["path"] == path:
                return i
        return 0

    def _insert_at_cursor(self, text: str):
        cur = self.prompt.textCursor()
        cur.insertText(text)
        self.prompt.setTextCursor(cur)
        self.prompt.setFocus()

    def _refresh_refs_count(self):
        n = len(self._references)
        self.refs_count_lbl.setText(f"{n} / {MAX_REFERENCES}")
        self.add_ref_btn.setEnabled(n < MAX_REFERENCES)

    # ── Run ───────────────────────────────────────────────────────────

    def _append_log(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{ts}] {level:<4} {msg}")

    def _clear_results(self):
        while self.results_grid.count():
            it = self.results_grid.takeAt(0)
            w = it.widget()
            if w:
                w.setParent(None)

    def _on_generate(self):
        prompt = self.prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Empty prompt", "Type a prompt first."); return
        if not core.is_active_provider_configured():
            label = core.PROVIDER_LABELS[core.get_active_provider_name()]
            QMessageBox.warning(self, "Missing key", f"Set your {label} key in Settings first.")
            return

        self.run_btn.setEnabled(False); self.run_btn.setText("Running…")
        self.status_pill.setText("Running")
        self.status_pill.setStyleSheet(
            f"background: {t.ACCENT}22; color: {t.ACCENT}; padding: 4px 10px; "
            f"border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        self._clear_results()
        self.open_folder_btn.setEnabled(False)

        thread = QThread()
        worker = ImageGenerateWorker(
            prompt=prompt,
            references=[r["path"] for r in self._references],
            n_variants=int(self.n_spin.value()),
            image_model=(self.image_model.currentData() or core.DEFAULT_IMAGE_MODEL),
            resolution=self.resolution.currentText() or "1k",
            aspect=self.aspect.currentText() or "1:1",
            workers=min(4, int(self.n_spin.value())),
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.log.connect(self._append_log)
        worker.result.connect(self._on_variant_result)
        worker.finished.connect(self._on_run_finished)
        self._thread = thread; self._worker = worker
        thread.start()

    def _on_variant_result(self, r: dict):
        if r.get("status") != "ok":
            return
        out_dir = self._worker._out_dir if self._worker else ""
        if not out_dir:
            return
        local = Path(out_dir) / r.get("file", "")
        if not local.exists():
            return
        thumb = QLabel(); thumb.setFixedSize(220, 220)
        thumb.setAlignment(Qt.AlignCenter)
        pm = QPixmap(str(local))
        if not pm.isNull():
            thumb.setPixmap(pm.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        thumb.setStyleSheet(f"border: 1px solid {t.BORDER_MUTED}; border-radius: 10px;")
        thumb.setCursor(Qt.PointingHandCursor)
        thumb.setToolTip(r.get("prompt", "")[:200])
        thumb.mousePressEvent = lambda _ev, p=local: open_path(p)
        # Place into grid 3-cols.
        idx = self.results_grid.count()
        row, col = divmod(idx, 3)
        self.results_grid.addWidget(thumb, row, col)

    def _on_run_finished(self, out_dir: str, count_ok: int):
        self.run_btn.setEnabled(True); self.run_btn.setText("Generate")
        self.status_pill.setText("Done" if count_ok else "Failed")
        self.status_pill.setStyleSheet(
            f"background: {t.GREEN if count_ok else t.RED}22; color: {t.GREEN if count_ok else t.RED};"
            f" padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;"
        )
        self.open_folder_btn.setEnabled(bool(out_dir and Path(out_dir).exists()))
        self._out_dir = out_dir
        try:
            self._thread.quit(); self._thread.wait()
        except Exception:
            pass

    def _open_out_dir(self):
        if hasattr(self, "_out_dir") and self._out_dir and Path(self._out_dir).exists():
            open_path(Path(self._out_dir))
