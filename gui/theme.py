"""Mimica light-mode lavender theme — design tokens + Qt stylesheet.

Mirrors the design system produced by Claude Design (see Mimica dashboard
mock). Translated to Qt's stylesheet language: solid colors, simple
gradients, border-radius, padding, hover states. No backdrop blur, no
real-time animations.
"""

# ─── Design tokens ──────────────────────────────────────────────────────────

BG_CANVAS       = "#FFFFFF"
BG_SIDEBAR      = "#F2F0F7"
BG_ELEVATED     = "#FAF8FF"
BG_HOVER        = "#F4F1FF"
BG_INPUT        = "#FAF8FF"

CARD_LAVENDER   = "#EEEAFF"
CARD_ROSE       = "#FCE7F0"
CARD_VIOLET     = "#E5DEFF"

TEXT            = "#1B1A2E"
TEXT_MUTED      = "#6E6A8A"
TEXT_DIM        = "#A29DC4"
TEXT_INVERSE    = "#FFFFFF"

ACCENT          = "#A78BFA"
ACCENT_SOFT     = "#C4B5FD"
ACCENT_STRONG   = "#8B6FE8"
ACCENT_BG       = "#F4F1FF"

SUCCESS         = "#10B981"
SUCCESS_BG      = "#E7F8F0"
WARNING         = "#F59E0B"
ERROR           = "#EF4444"

BORDER          = "#E9E4FF"
BORDER_MUTED    = "#EAEAF2"

# Back-compat aliases (older modules reference these names)
BG              = BG_CANVAS
BG_CARD         = BG_CANVAS
BORDER_LIGHT    = BORDER_MUTED
ACCENT_LIGHT    = ACCENT_SOFT
ACCENT_DEEP     = ACCENT_STRONG
GREEN           = SUCCESS
RED             = ERROR
YELLOW          = WARNING

R_SM   = 8
R_MD   = 14
R_LG   = 20
R_XL   = 28
R_PILL = 9999


# ─── Stylesheet ─────────────────────────────────────────────────────────────

STYLESHEET = f"""
* {{
    font-family: "Inter", "SF Pro Display", "Helvetica Neue", sans-serif;
    color: {TEXT};
    outline: none;
}}

QMainWindow, QWidget#Root, QWidget#TopBar, QWidget#PageHost {{
    background: {BG_CANVAS};
}}

QStackedWidget, QStackedWidget > QWidget {{
    background: {BG_CANVAS};
}}

QScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget {{
    background: {BG_CANVAS};
    border: none;
}}

QWidget#Sidebar {{
    background: {BG_SIDEBAR};
    border-right: 1px solid {BORDER_MUTED};
}}

QWidget#Sidebar QPushButton#GhostBtn {{
    background: transparent;
}}

QFrame#Card {{
    background: {BG_CANVAS};
    border: 1px solid {BORDER};
    border-radius: 20px;
}}

QFrame#CardFlat {{
    background: {BG_CANVAS};
    border-radius: 14px;
}}

QFrame#CardHero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {CARD_LAVENDER}, stop:1 {ACCENT_BG});
    border-radius: 20px;
}}

QFrame#StatCard {{
    background: {BG_CANVAS};
    border: 1px solid {BORDER};
    border-radius: 28px;
}}

QFrame#CardLavender {{
    background: {CARD_LAVENDER};
    border: 1px solid transparent;
    border-radius: 28px;
}}

QFrame#CardRose {{
    background: {CARD_ROSE};
    border: 1px solid transparent;
    border-radius: 28px;
}}

QFrame#CardViolet {{
    background: {CARD_VIOLET};
    border: 1px solid transparent;
    border-radius: 28px;
}}

QFrame#RunCard {{
    background: {BG_CANVAS};
    border: 1px solid {BORDER_MUTED};
    border-radius: 20px;
}}

QFrame#ProviderStatusCard {{
    background: {BG_CANVAS};
    border: 1px solid {BORDER_MUTED};
    border-radius: 14px;
}}

/* ─── Sidebar nav items ──────────────────────────────────────────────── */

QPushButton#SidebarItem {{
    background: transparent;
    border: none;
    border-radius: 22px;
    padding: 10px 14px;
    text-align: left;
    color: {TEXT};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#SidebarItem:hover {{
    background: {BG_HOVER};
}}

QPushButton#SidebarItemActive {{
    background: {ACCENT_BG};
    border: none;
    border-radius: 22px;
    padding: 10px 14px;
    text-align: left;
    color: {ACCENT_STRONG};
    font-size: 13px;
    font-weight: 600;
}}

/* ─── Buttons ─────────────────────────────────────────────────────────── */

QPushButton#PrimaryBtn {{
    background: {ACCENT};
    border: 1px solid transparent;
    border-radius: 22px;
    padding: 10px 18px;
    color: {TEXT_INVERSE};
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#PrimaryBtn:hover {{
    background: {ACCENT_STRONG};
}}
QPushButton#PrimaryBtn:pressed {{
    background: {ACCENT_STRONG};
}}
QPushButton#PrimaryBtn:disabled {{
    background: {BORDER};
    color: {TEXT_DIM};
}}

QPushButton#GhostBtn {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 22px;
    padding: 9px 16px;
    color: {TEXT};
    font-weight: 500;
    font-size: 13px;
}}
QPushButton#GhostBtn:hover {{
    background: {BG_HOVER};
    border: 1px solid {ACCENT};
}}

QPushButton#OnCardBtn {{
    background: {BG_CANVAS};
    border: 1px solid transparent;
    border-radius: 22px;
    padding: 9px 16px;
    color: {TEXT};
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#OnCardBtn:hover {{
    border: 1px solid {ACCENT};
}}

QPushButton#SearchBtn {{
    background: {BG_ELEVATED};
    border: 1px solid transparent;
    border-radius: 22px;
    padding: 9px 14px;
    color: {TEXT_MUTED};
    font-weight: 500;
    font-size: 12px;
}}
QPushButton#SearchBtn:hover {{
    background: {BG_HOVER};
}}

QPushButton {{
    background: transparent;
    border: 1px solid {BORDER};
    border-radius: 22px;
    padding: 8px 14px;
    color: {TEXT};
    font-weight: 500;
    font-size: 13px;
}}
QPushButton:hover {{
    background: {BG_HOVER};
    border: 1px solid {ACCENT};
}}

/* ─── Chips ───────────────────────────────────────────────────────────── */

QPushButton#ChipOff {{
    background: {BG_CANVAS};
    border: 1px solid {BORDER_MUTED};
    border-radius: 22px;
    padding: 6px 12px;
    color: {TEXT_MUTED};
    font-weight: 500;
    font-size: 12px;
}}
QPushButton#ChipOff:hover {{
    background: {BG_HOVER};
    color: {TEXT};
}}

QPushButton#ChipOn {{
    background: {ACCENT_BG};
    border: 1px solid transparent;
    border-radius: 22px;
    padding: 6px 12px;
    color: {ACCENT_STRONG};
    font-weight: 600;
    font-size: 12px;
}}

/* ─── Inputs ──────────────────────────────────────────────────────────── */

QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox {{
    background: {BG_INPUT};
    border: 1px solid {BORDER_MUTED};
    border-radius: 14px;
    padding: 10px 14px;
    color: {TEXT};
    font-size: 13px;
    selection-background-color: {ACCENT_BG};
    selection-color: {ACCENT_STRONG};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
    background: {BG_CANVAS};
}}

QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {BG_CANVAS};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 4px;
    selection-background-color: {ACCENT_BG};
    selection-color: {ACCENT_STRONG};
}}

QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; }}

/* ─── Radio + Checkbox ────────────────────────────────────────────────── */

QRadioButton, QCheckBox {{
    color: {TEXT};
    font-size: 13px;
    spacing: 8px;
    background: transparent;
}}
QRadioButton::indicator, QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}
QRadioButton::indicator:unchecked {{
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    background: {BG_CANVAS};
}}
QRadioButton::indicator:checked {{
    border: 1.5px solid {ACCENT};
    border-radius: 8px;
    background: {BG_CANVAS};
    image: none;
}}

/* ─── Tables / Lists ──────────────────────────────────────────────────── */

QListWidget, QTableWidget {{
    background: {BG_CANVAS};
    border: 1px solid {BORDER_MUTED};
    border-radius: 14px;
    padding: 4px;
    selection-background-color: {ACCENT_BG};
    selection-color: {ACCENT_STRONG};
}}
QListWidget::item, QTableWidget::item {{
    padding: 8px 10px;
    border-radius: 8px;
}}
QListWidget::item:hover, QTableWidget::item:hover {{
    background: {BG_HOVER};
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background: {ACCENT_BG};
    color: {ACCENT_STRONG};
}}

QHeaderView::section {{
    background: {BG_SIDEBAR};
    border: none;
    padding: 8px 10px;
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}

/* ─── Scrollbars ──────────────────────────────────────────────────────── */

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT_SOFT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 0 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {ACCENT_SOFT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ─── Typography labels ───────────────────────────────────────────────── */

QLabel#H1 {{
    color: {TEXT};
    font-size: 38px;
    font-weight: 700;
    letter-spacing: -0.02em;
}}
QLabel#H2 {{
    color: {TEXT};
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.015em;
}}
QLabel#H3 {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 600;
}}
QLabel#Dim {{
    color: {TEXT_MUTED};
    font-size: 13px;
}}
QLabel#Muted {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
}}
QLabel#Cursive {{
    font-family: "Caveat", "Inter", cursive;
    color: {ACCENT_STRONG};
    font-size: 32px;
    font-weight: 500;
}}
QLabel#BigNumber {{
    color: {TEXT};
    font-size: 28px;
    font-weight: 700;
    letter-spacing: -0.02em;
}}

/* ─── Dialogs ─────────────────────────────────────────────────────────── */

QDialog {{
    background: {BG_CANVAS};
}}

QMessageBox {{
    background: {BG_CANVAS};
}}
QMessageBox QLabel {{
    color: {TEXT};
}}

QLabel#SectionLabel {{
    color: {TEXT_DIM};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    padding: 4px 14px;
}}
"""
