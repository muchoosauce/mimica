from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize, Signal, QPoint
from PySide6.QtGui import (
    QBrush, QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
    QDragEnterEvent, QDropEvent, QMouseEvent
)
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget
)

from . import theme as t


def svg_icon(path: str, size: int, color: str = t.TEXT) -> QPixmap:
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import QByteArray
    svg = path.replace('currentColor', color)
    r = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size, size); pm.fill(Qt.transparent)
    p = QPainter(pm); r.render(p); p.end()
    return pm


ICONS = {
    "dashboard": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></g></svg>',
    "generate": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/><circle cx="12" cy="12" r="4"/></g></svg>',
    "history": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></g></svg>',
    "gallery": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="M3 17l5-5 7 7"/><path d="M14 14l3-3 4 4"/></g></svg>',
    "settings": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3h0a1.6 1.6 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8v0a1.6 1.6 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></g></svg>',
    "search": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></g></svg>',
    "plus": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></g></svg>',
    "image": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M3 17l5-5 7 7M14 14l3-3 4 4"/></g></svg>',
    "folder": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></g></svg>',
    "zap": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M13 3L4 14h7l-1 7 9-11h-7z"/></g></svg>',
    "wallet": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M16 12h3"/></g></svg>',
    "chart": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/></g></svg>',
    "refresh": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 0 1 15.5-6.3L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.3L3 16"/><path d="M3 21v-5h5"/></g></svg>',
    "check": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5L20 7"/></g></svg>',
    "alert": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></g></svg>',
    "logo": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L2 8v8l10 6 10-6V8z" fill="currentColor"/><path d="M12 6l-6 3.5v5L12 18l6-3.5v-5z" fill="#0A0A0A"/><path d="M12 9l-3 1.75v2.5L12 15l3-1.75v-2.5z" fill="currentColor"/></svg>',
    "arrow_right": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></g></svg>',
    "chevron_right": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></g></svg>',
    "open": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M10 14L21 3"/><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></g></svg>',
    "adapt": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 3l5 5-5 5"/><path d="M21 8H9a4 4 0 0 0-4 4v1"/><path d="M8 21l-5-5 5-5"/><path d="M3 16h12a4 4 0 0 0 4-4v-1"/></g></svg>',
    "brand": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M20.6 13.4L13.4 20.6a2 2 0 0 1-2.8 0L2 12V2h10l8.6 8.6a2 2 0 0 1 0 2.8z"/><circle cx="7" cy="7" r="1.5" fill="currentColor"/></g></svg>',
    "trash": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></g></svg>',
    "edit": '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><g fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4z"/></g></svg>',
}


def icon_label(name: str, size: int = 16, color: str = t.TEXT) -> QLabel:
    lbl = QLabel()
    lbl.setPixmap(svg_icon(ICONS[name], size, color))
    lbl.setFixedSize(size, size)
    return lbl


def icon_button(name: str, size: int = 18, color: str = t.TEXT_DIM, tooltip: str = "") -> QPushButton:
    btn = QPushButton()
    btn.setObjectName("IconBtn")
    btn.setIcon(_pixmap_to_icon(svg_icon(ICONS[name], size, color)))
    btn.setIconSize(QSize(size, size))
    btn.setCursor(Qt.PointingHandCursor)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


def _pixmap_to_icon(pix: QPixmap):
    from PySide6.QtGui import QIcon
    return QIcon(pix)


class Card(QFrame):
    def __init__(self, hero: bool = False, flat: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("CardHero" if hero else ("CardFlat" if flat else "Card"))
        self.setAttribute(Qt.WA_StyledBackground, True)


class StatCard(Card):
    def __init__(self, icon: str, title: str, subtitle: str, value: str,
                 hero: bool = False, trend: str = "", action: str = ""):
        super().__init__(hero=hero)
        self.setMinimumHeight(150)
        self.setCursor(Qt.PointingHandCursor if action else Qt.ArrowCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 18)
        outer.setSpacing(0)

        head = QHBoxLayout(); head.setSpacing(10)
        icon_bg = "#FFFFFF1E" if hero else "#FFFFFF08"
        icon_container = QFrame()
        icon_container.setStyleSheet(f"background: {icon_bg}; border-radius: 10px;")
        icon_container.setFixedSize(42, 42)
        ic_l = QVBoxLayout(icon_container); ic_l.setContentsMargins(0, 0, 0, 0)
        ic_color = "white" if hero else t.TEXT
        ic = icon_label(icon, 20, ic_color); ic.setAlignment(Qt.AlignCenter)
        ic_l.addWidget(ic, alignment=Qt.AlignCenter)

        title_box = QVBoxLayout(); title_box.setSpacing(1)
        t_lbl = QLabel(title)
        t_lbl.setObjectName("HeroTitle" if hero else "H3")
        s_lbl = QLabel(subtitle)
        s_lbl.setObjectName("HeroSub" if hero else "Dim")
        s_lbl.setStyleSheet(f"color: {'rgba(255,255,255,0.75)' if hero else t.TEXT_DIM}; font-size: 11px;")
        title_box.addWidget(t_lbl); title_box.addWidget(s_lbl)

        head.addWidget(icon_container)
        head.addLayout(title_box)
        head.addStretch()
        outer.addLayout(head)
        outer.addStretch()

        val_row = QHBoxLayout(); val_row.setSpacing(8)
        v_lbl = QLabel(value)
        v_lbl.setObjectName("HeroBig" if hero else "Big")
        if hero: v_lbl.setStyleSheet("color: white; font-size: 28px; font-weight: 800;")
        val_row.addWidget(v_lbl)
        if trend:
            tr = QLabel(trend)
            tr.setStyleSheet(
                f"background: {'rgba(255,255,255,0.18)' if hero else '#22C55E22'}; "
                f"color: {'white' if hero else t.GREEN}; "
                f"padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 700;"
            )
            val_row.addWidget(tr)
        val_row.addStretch()
        outer.addLayout(val_row)

        if action:
            outer.addSpacing(12)
            row = QHBoxLayout()
            link = QLabel(action)
            link.setStyleSheet(f"color: {'white' if hero else t.TEXT_DIM}; font-size: 12px; font-weight: 500;")
            row.addWidget(link); row.addStretch()
            arrow = icon_label("arrow_right", 14, "white" if hero else t.TEXT_DIM)
            row.addWidget(arrow)
            outer.addLayout(row)


class BarChart(QWidget):
    def __init__(self, data: list[tuple[str, float]], highlight_index: int = -1, unit: str = ""):
        super().__init__()
        self.data = data
        self.highlight = highlight_index
        self.unit = unit
        self.setMinimumHeight(260)
        self.setMouseTracking(True)
        self._hover = -1
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def mouseMoveEvent(self, ev):
        idx = self._idx_at(ev.position().x())
        if idx != self._hover:
            self._hover = idx
            self.update()

    def leaveEvent(self, ev):
        self._hover = -1
        self.update()

    def _layout(self):
        w, h = self.width(), self.height()
        pad = (36, 20, 14, 34)
        chart_w = w - pad[0] - pad[2]
        chart_h = h - pad[1] - pad[3]
        n = max(1, len(self.data))
        gap = 14
        bar_w = max(8, (chart_w - gap * (n - 1)) / n)
        return pad, chart_w, chart_h, bar_w, gap

    def _idx_at(self, x: float) -> int:
        pad, _, _, bar_w, gap = self._layout()
        rel = x - pad[0]
        if rel < 0: return -1
        i = int(rel // (bar_w + gap))
        return i if 0 <= i < len(self.data) else -1

    def paintEvent(self, _ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.data:
            p.setPen(QPen(QColor(t.TEXT_MUTED)))
            f = QFont(); f.setPointSize(11); p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "No data yet")
            return

        pad, chart_w, chart_h, bar_w, gap = self._layout()
        max_val = max((v for _, v in self.data), default=1) or 1

        p.setPen(QPen(QColor(t.TEXT_MUTED)))
        f = QFont(); f.setPointSize(9); p.setFont(f)
        for i in range(5):
            y = pad[1] + chart_h * (i / 4)
            val = max_val * (1 - i / 4)
            label = f"{int(val/1000)}k" if val >= 1000 else f"{int(val)}"
            p.drawText(QRectF(0, y - 8, pad[0] - 6, 16), Qt.AlignRight | Qt.AlignVCenter, label)

        for i, (lbl, val) in enumerate(self.data):
            x = pad[0] + i * (bar_w + gap)
            bh = max(2, chart_h * (val / max_val)) if val > 0 else 0
            y = pad[1] + chart_h - bh
            path = QPainterPath()
            path.addRoundedRect(QRectF(x, y, bar_w, bh), 8, 8) if bh > 0 else None
            highlighted = (i == self.highlight) or (i == self._hover)
            if highlighted and bh > 0:
                g = QLinearGradient(x, y, x, y + bh)
                g.setColorAt(0, QColor(t.ACCENT))
                g.setColorAt(1, QColor("#FFB088"))
                p.fillPath(path, QBrush(g))
            elif bh > 0:
                p.fillPath(path, QBrush(QColor("#242424")))
            p.setPen(QPen(QColor(t.TEXT_MUTED if i != self._hover else t.TEXT)))
            p.drawText(QRectF(x, pad[1] + chart_h + 6, bar_w, 18), Qt.AlignCenter, lbl)

        if self._hover >= 0:
            lbl, val = self.data[self._hover]
            x = pad[0] + self._hover * (bar_w + gap) + bar_w / 2
            bh = max(2, chart_h * (val / max_val)) if val > 0 else 0
            y = pad[1] + chart_h - bh
            txt = f"{lbl} · {int(val)}{self.unit}"
            tw = p.fontMetrics().horizontalAdvance(txt) + 20
            th = 28
            tx = min(self.width() - tw - 6, max(6, x - tw / 2))
            ty = max(6, y - th - 8)
            p.setBrush(QColor(t.BG_CARD))
            p.setPen(QPen(QColor(t.BORDER)))
            p.drawRoundedRect(QRectF(tx, ty, tw, th), 8, 8)
            p.setPen(QPen(QColor(t.TEXT)))
            p.drawText(QRectF(tx, ty, tw, th), Qt.AlignCenter, txt)


def round_pixmap(path: Path, w: int, h: int, radius: int = 12) -> QPixmap:
    src = QPixmap(str(path))
    out = QPixmap(w, h); out.fill(Qt.transparent)
    if src.isNull():
        return out
    src = src.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    sx = (src.width() - w) // 2
    sy = (src.height() - h) // 2
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path_ = QPainterPath()
    path_.addRoundedRect(0, 0, w, h, radius, radius)
    p.setClipPath(path_)
    p.drawPixmap(-sx, -sy, src)
    p.end()
    return out


class ThumbLabel(QLabel):
    clicked = Signal()

    def __init__(self, path: Path, w: int = 170, h: int = 170, radius: int = 12):
        super().__init__()
        self.setFixedSize(w, h)
        self.setCursor(Qt.PointingHandCursor)
        self.path = path
        self.setPixmap(round_pixmap(path, w, h, radius))

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() == Qt.LeftButton:
            self.clicked.emit()


class DropZone(QFrame):
    file_dropped = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(220)
        self._path: str = ""
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
        self.icon = icon_label("image", 36, t.TEXT_MUTED)
        self.icon.setAlignment(Qt.AlignCenter)
        self.title = QLabel("Drop an image here")
        self.title.setStyleSheet(f"color: {t.TEXT}; font-size: 14px; font-weight: 600;")
        self.title.setAlignment(Qt.AlignCenter)
        self.sub = QLabel("or click to browse · PNG, JPG, up to 10 MB")
        self.sub.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 12px;")
        self.sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.icon, alignment=Qt.AlignCenter)
        lay.addWidget(self.title)
        lay.addWidget(self.sub)
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.hide()
        lay.addWidget(self.preview, alignment=Qt.AlignCenter)

    def set_file(self, path: str):
        self._path = path
        p = Path(path)
        if not p.exists():
            return
        pm = round_pixmap(p, 160, 160, 10)
        self.preview.setPixmap(pm)
        self.preview.show()
        self.icon.hide()
        self.title.setText(p.name)
        self.sub.setText(f"{p.stat().st_size / 1024:.0f} KB — click to replace")
        self.file_dropped.emit(path)

    def path(self) -> str:
        return self._path

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() != Qt.LeftButton: return
        from PySide6.QtWidgets import QFileDialog
        p, _ = QFileDialog.getOpenFileName(
            self, "Select reference image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if p:
            self.set_file(p)

    def dragEnterEvent(self, ev: QDragEnterEvent):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            self.setObjectName("DropZoneActive")
            self.style().unpolish(self); self.style().polish(self)

    def dragLeaveEvent(self, ev):
        self.setObjectName("DropZone")
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, ev: QDropEvent):
        for url in ev.mimeData().urls():
            p = url.toLocalFile()
            if p:
                self.set_file(p)
                break
        self.setObjectName("DropZone")
        self.style().unpolish(self); self.style().polish(self)


class ProductImagesEditor(QWidget):
    """Horizontal row of small product thumbnails with add / remove controls."""

    changed = Signal(list)

    def __init__(self, initial: list[str] | None = None, thumb: int = 76, parent=None):
        super().__init__(parent)
        self._paths: list[str] = [p for p in (initial or []) if p and Path(p).exists()]
        self._thumb = thumb
        from PySide6.QtWidgets import QHBoxLayout
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0); outer.setSpacing(8)
        self._row_host = QWidget()
        self._row = QHBoxLayout(self._row_host)
        self._row.setContentsMargins(0, 0, 0, 0); self._row.setSpacing(8)
        outer.addWidget(self._row_host)
        outer.addStretch()
        self._refresh()

    def paths(self) -> list[str]:
        return list(self._paths)

    def _refresh(self):
        while self._row.count():
            item = self._row.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()
        for i, p in enumerate(self._paths):
            self._row.addWidget(self._make_thumb(p, i))
        self._row.addWidget(self._make_add())

    def _make_thumb(self, path: str, idx: int) -> QWidget:
        frame = QFrame()
        frame.setFixedSize(self._thumb, self._thumb)
        frame.setStyleSheet("background: transparent;")
        img = QLabel(frame)
        img.setPixmap(round_pixmap(Path(path), self._thumb, self._thumb, 10))
        img.setGeometry(0, 0, self._thumb, self._thumb)
        x = QPushButton("×", frame)
        x.setFixedSize(20, 20)
        x.setStyleSheet(
            f"background: rgba(0,0,0,200); color: white; border: none; "
            f"border-radius: 10px; font-size: 14px; font-weight: 700;"
        )
        x.setCursor(Qt.PointingHandCursor)
        x.setGeometry(self._thumb - 24, 4, 20, 20)
        x.clicked.connect(lambda _=None, i=idx: self._remove(i))
        return frame

    def _make_add(self) -> QWidget:
        btn = QPushButton("+")
        btn.setFixedSize(self._thumb, self._thumb)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ border: 1.5px dashed {t.BORDER_LIGHT}; border-radius: 10px; "
            f"background: {t.BG_INPUT}; color: {t.TEXT_MUTED}; font-size: 26px; font-weight: 300; }}"
            f"QPushButton:hover {{ border-color: {t.ACCENT}; color: {t.ACCENT}; }}"
        )
        btn.clicked.connect(self._pick)
        return btn

    def _pick(self):
        from PySide6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add product images", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if paths:
            self._paths.extend(paths)
            self._refresh()
            self.changed.emit(list(self._paths))

    def _remove(self, idx: int):
        if 0 <= idx < len(self._paths):
            del self._paths[idx]
            self._refresh()
            self.changed.emit(list(self._paths))


class ChipGroup(QWidget):
    changed = Signal()

    def __init__(self, options: list[str], default: list[str] | None = None,
                 columns: int = 4, parent=None):
        super().__init__(parent)
        self.options = list(options)
        self._selected: set[str] = set(default or [])
        from PySide6.QtWidgets import QGridLayout
        lay = QGridLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setHorizontalSpacing(6); lay.setVerticalSpacing(6)
        self._btns: dict[str, QPushButton] = {}
        for i, opt in enumerate(self.options):
            b = QPushButton(opt)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setChecked(opt in self._selected)
            b.setObjectName("ChipOn" if b.isChecked() else "ChipOff")
            b.toggled.connect(lambda checked, o=opt: self._toggle(o, checked))
            self._btns[opt] = b
            lay.addWidget(b, i // columns, i % columns)

    def _toggle(self, opt: str, checked: bool):
        if checked:
            self._selected.add(opt)
        else:
            self._selected.discard(opt)
        b = self._btns[opt]
        b.setObjectName("ChipOn" if checked else "ChipOff")
        b.style().unpolish(b); b.style().polish(b)
        self.changed.emit()

    def selected(self) -> list[str]:
        return [o for o in self.options if o in self._selected]

    def set_selected(self, values: list[str]):
        for opt, b in self._btns.items():
            want = opt in values
            b.blockSignals(True); b.setChecked(want); b.blockSignals(False)
            b.setObjectName("ChipOn" if want else "ChipOff")
            b.style().unpolish(b); b.style().polish(b)
        self._selected = set(values)
        self.changed.emit()


class FolderDropZone(QFrame):
    """Accepts a folder, one or many image files, or a mix. Emits the flat list of image paths."""

    paths_changed = Signal(list)
    folder_dropped = Signal(str)  # legacy alias, emits first path or folder

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(140)
        self._paths: list[Path] = []
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
        lay = QVBoxLayout(self); lay.setAlignment(Qt.AlignCenter); lay.setSpacing(8)
        self.icon = icon_label("folder", 28, t.TEXT_MUTED)
        self.icon.setAlignment(Qt.AlignCenter)
        self.title = QLabel("Drop files or a folder")
        self.title.setStyleSheet(f"color: {t.TEXT}; font-size: 13px; font-weight: 600;")
        self.title.setAlignment(Qt.AlignCenter)
        self.sub = QLabel("or click to browse")
        self.sub.setStyleSheet(f"color: {t.TEXT_MUTED}; font-size: 11px;")
        self.sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.icon, alignment=Qt.AlignCenter)
        lay.addWidget(self.title)
        lay.addWidget(self.sub)

    def _expand(self, paths: list[Path]) -> list[Path]:
        from . import core
        flat: list[Path] = []
        for p in paths:
            p = Path(p)
            if p.is_dir():
                flat.extend(core.list_ads_in_folder(p))
            elif p.is_file() and p.suffix.lower() in core.AD_EXTS:
                flat.append(p)
        seen = set(); out = []
        for p in flat:
            k = str(p.resolve())
            if k not in seen:
                seen.add(k); out.append(p)
        return out

    def set_paths(self, raw_paths: list):
        raw = [Path(p) for p in raw_paths]
        expanded = self._expand(raw)
        self._paths = expanded
        n = len(expanded)
        single_folder = len(raw) == 1 and raw[0].is_dir()
        if n == 0:
            self.title.setText("No images found")
            self.sub.setText("Try another folder or files · click to browse")
        elif single_folder:
            self.title.setText(raw[0].name)
            self.sub.setText(f"{n} image{'s' if n != 1 else ''} · click to change")
        else:
            self.title.setText(f"{n} file{'s' if n != 1 else ''}")
            head = raw[0].name if raw else ""
            extra = f", +{n - 1} more" if n > 1 else ""
            self.sub.setText(f"{head}{extra} · click to change")
        self.paths_changed.emit([str(p) for p in expanded])
        self.folder_dropped.emit(str(raw[0]) if raw else "")

    def paths(self) -> list[str]:
        return [str(p) for p in self._paths]

    # legacy single-path getter used elsewhere
    def path(self) -> str:
        return str(self._paths[0].parent) if self._paths else ""

    def mousePressEvent(self, ev: QMouseEvent):
        if ev.button() != Qt.LeftButton: return
        from PySide6.QtWidgets import QFileDialog, QMenu
        menu = QMenu(self)
        files_act = menu.addAction("Select files…")
        folder_act = menu.addAction("Select folder…")
        pos = ev.globalPosition().toPoint() if hasattr(ev, "globalPosition") else ev.globalPos()
        chosen = menu.exec(pos)
        if chosen is files_act:
            files, _ = QFileDialog.getOpenFileNames(
                self, "Select ad files", "",
                "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
            )
            if files:
                self.set_paths(files)
        elif chosen is folder_act:
            p = QFileDialog.getExistingDirectory(self, "Select folder of ads")
            if p:
                self.set_paths([p])

    def dragEnterEvent(self, ev: QDragEnterEvent):
        from . import core
        if not ev.mimeData().hasUrls(): return
        for url in ev.mimeData().urls():
            lp = Path(url.toLocalFile())
            if lp.is_dir() or (lp.is_file() and lp.suffix.lower() in core.AD_EXTS):
                ev.acceptProposedAction()
                self.setObjectName("DropZoneActive")
                self.style().unpolish(self); self.style().polish(self)
                return

    def dragLeaveEvent(self, ev):
        self.setObjectName("DropZone")
        self.style().unpolish(self); self.style().polish(self)

    def dropEvent(self, ev: QDropEvent):
        paths = [url.toLocalFile() for url in ev.mimeData().urls() if url.toLocalFile()]
        if paths:
            self.set_paths(paths)
        self.setObjectName("DropZone")
        self.style().unpolish(self); self.style().polish(self)


class OutputFolderRow(QWidget):
    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from . import core
        self._path = str(core.get_output_dir())

        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(8)
        self.path_lbl = QPushButton()
        self.path_lbl.setObjectName("GhostBtn")
        self.path_lbl.setCursor(Qt.PointingHandCursor)
        self.path_lbl.setStyleSheet(
            self.path_lbl.styleSheet() +
            f" QPushButton {{ text-align: left; padding: 9px 12px; }}"
        )
        self.path_lbl.clicked.connect(self._pick)
        lay.addWidget(self.path_lbl, 1)

        reset = QPushButton("Reset"); reset.setObjectName("GhostBtn")
        reset.setCursor(Qt.PointingHandCursor); reset.setToolTip("Use project default (outputs/)")
        reset.clicked.connect(self._reset)
        lay.addWidget(reset)

        self._refresh()

    def _friendly(self, p: str) -> str:
        s = str(Path(p))
        home = str(Path.home())
        if s.startswith(home):
            s = "~" + s[len(home):]
        return s

    def _refresh(self):
        self.path_lbl.setText(f"📁  {self._friendly(self._path)}")

    def path(self) -> str:
        return self._path

    def set_path(self, p: str, persist: bool = True):
        from . import core
        self._path = str(Path(p).expanduser())
        if persist:
            core.save_output_dir(self._path)
        self._refresh()
        self.changed.emit(self._path)

    def _pick(self):
        from PySide6.QtWidgets import QFileDialog
        p = QFileDialog.getExistingDirectory(self, "Select output folder", self._path)
        if p:
            self.set_path(p)

    def _reset(self):
        from . import core
        self.set_path(str(core.DEFAULT_OUTPUT_DIR))


class StatusPill(QLabel):
    def __init__(self, text: str, color: str = t.GREEN):
        super().__init__(text)
        self.setStyleSheet(
            f"background: {color}22; color: {color};"
            f" padding: 4px 10px; border-radius: 10px; font-size: 11px; font-weight: 600;"
        )
        self.setFixedHeight(22)


def open_path(path: Path):
    if not path.exists(): return
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(path)], check=False)
    else:
        import os as _os
        _os.startfile(str(path))  # type: ignore
