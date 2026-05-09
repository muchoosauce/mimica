"""Mimica dark violet theme — design tokens + Qt stylesheet.

Translation of the C2 web mockup (Atlas-inspired dark + violet) to Qt's
stylesheet language. Token names are preserved from the previous lavender
theme so existing pages and widgets keep working — only the values change.

What carries over from the web mockup:
  - Ink near-black canvas (#0A0A0F) with subtle warmth.
  - Violet electric accent (#7C5CFF) with violet→pink secondary gradient.
  - Hairline borders rgba(255,255,255,~6%).
  - Mono numerics via JetBrains Mono is intentionally NOT bundled here —
    the desktop app sticks to Inter to keep the bundle lean. Numbers stay
    legible without a mono swap.

What does NOT translate (Qt stylesheet limitations):
  - SVG noise grain → omitted; flat dark surfaces instead.
  - Outer drop-shadows and bloom glows → stylesheet box-shadow doesn't exist
    in QSS. Where a shadow really matters (primary CTA), apply
    QGraphicsDropShadowEffect at the widget level — not done here, kept for
    a follow-up if it's missed visually.
  - Backdrop-blur and animated pulse keyframes → not in QSS. Static states.
"""

# ─── Design tokens ──────────────────────────────────────────────────────────

BG_CANVAS       = "#0A0A0F"   # ink, near-black with warmth
BG_SIDEBAR      = "#0C0C12"   # slightly darker than canvas
BG_ELEVATED     = "#1A1A22"   # popovers, hover surfaces
BG_HOVER        = "#1A1A22"
BG_INPUT        = "#131318"

CARD_LAVENDER   = "#1A1530"   # tinted dark surface (was light lavender)
CARD_ROSE       = "#2A1A22"   # tinted dark rose
CARD_VIOLET     = "#1F1A30"   # tinted dark violet

TEXT            = "#F4F4F6"
TEXT_MUTED      = "#9999A0"
TEXT_DIM        = "#5C5C66"
TEXT_INVERSE    = "#0A0A0F"   # text on accent (dark on violet)

ACCENT          = "#7C5CFF"   # electric violet — primary
ACCENT_SOFT     = "#9C84FF"
ACCENT_STRONG   = "#6A4CFF"
ACCENT_BG       = "rgba(124, 92, 255, 0.12)"   # subtle accent fill (sidebar active)
ACCENT_PINK     = "#EC4899"   # secondary, used in the violet→pink gradient

BORDER          = "rgba(255, 255, 255, 0.10)"
BORDER_MUTED    = "rgba(255, 255, 255, 0.06)"

SUCCESS         = "#10B981"
SUCCESS_BG      = "rgba(16, 185, 129, 0.12)"
WARNING         = "#F59E0B"
ERROR           = "#EF4444"

# Back-compat aliases (older modules reference these names)
BG              = BG_CANVAS
BG_CARD         = BG_ELEVATED
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
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_MUTED};
    border-radius: 20px;
}}

QFrame#CardFlat {{
    background: {BG_INPUT};
    border-radius: 14px;
}}

QFrame#CardHero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {CARD_LAVENDER}, stop:1 {BG_ELEVATED});
    border: 1px solid {BORDER_MUTED};
    border-radius: 20px;
}}

QFrame#StatCard {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_MUTED};
    border-radius: 28px;
}}

QFrame#CardLavender {{
    background: {CARD_LAVENDER};
    border: 1px solid {BORDER_MUTED};
    border-radius: 28px;
}}

QFrame#CardRose {{
    background: {CARD_ROSE};
    border: 1px solid {BORDER_MUTED};
    border-radius: 28px;
}}

QFrame#CardViolet {{
    background: {CARD_VIOLET};
    border: 1px solid {BORDER_MUTED};
    border-radius: 28px;
}}

QFrame#RunCard {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_MUTED};
    border-radius: 20px;
}}

QFrame#ProviderStatusCard {{
    background: {BG_ELEVATED};
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
    color: {TEXT_MUTED};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#SidebarItem:hover {{
    background: {BG_HOVER};
    color: {TEXT};
}}

QPushButton#SidebarItemActive {{
    background: {ACCENT_BG};
    border: 1px solid {ACCENT_BG};
    border-radius: 22px;
    padding: 10px 14px;
    text-align: left;
    color: {ACCENT_SOFT};
    font-size: 13px;
    font-weight: 600;
}}

/* ─── Buttons ─────────────────────────────────────────────────────────── */

QPushButton#PrimaryBtn {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_PINK});
    border: 1px solid transparent;
    border-radius: 22px;
    padding: 10px 18px;
    color: #FFFFFF;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#PrimaryBtn:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT_STRONG}, stop:1 {ACCENT_PINK});
}}
QPushButton#PrimaryBtn:pressed {{
    background: {ACCENT_STRONG};
}}
QPushButton#PrimaryBtn:disabled {{
    background: {BG_HOVER};
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
    color: {ACCENT_SOFT};
}}

QPushButton#OnCardBtn {{
    background: {BG_INPUT};
    border: 1px solid {BORDER_MUTED};
    border-radius: 22px;
    padding: 9px 16px;
    color: {TEXT};
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#OnCardBtn:hover {{
    border: 1px solid {ACCENT};
    color: {ACCENT_SOFT};
}}

QPushButton#SearchBtn {{
    background: {BG_INPUT};
    border: 1px solid {BORDER_MUTED};
    border-radius: 22px;
    padding: 9px 14px;
    color: {TEXT_MUTED};
    font-weight: 500;
    font-size: 12px;
}}
QPushButton#SearchBtn:hover {{
    background: {BG_HOVER};
    color: {TEXT};
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
    color: {ACCENT_SOFT};
}}

/* ─── Chips ───────────────────────────────────────────────────────────── */

QPushButton#ChipOff {{
    background: {BG_INPUT};
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
    border: 1px solid {ACCENT};
    border-radius: 22px;
    padding: 6px 12px;
    color: {ACCENT_SOFT};
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
    selection-color: {ACCENT_SOFT};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
    background: {BG_ELEVATED};
}}

QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 4px;
    selection-background-color: {ACCENT_BG};
    selection-color: {ACCENT_SOFT};
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
    background: {BG_INPUT};
}}
QRadioButton::indicator:checked {{
    border: 1.5px solid {ACCENT};
    border-radius: 8px;
    background: {ACCENT};
    image: none;
}}

/* ─── Tables / Lists ──────────────────────────────────────────────────── */

QListWidget, QTableWidget {{
    background: {BG_ELEVATED};
    border: 1px solid {BORDER_MUTED};
    border-radius: 14px;
    padding: 4px;
    selection-background-color: {ACCENT_BG};
    selection-color: {ACCENT_SOFT};
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
    color: {ACCENT_SOFT};
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
    color: {ACCENT_SOFT};
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
