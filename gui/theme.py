BG = "#0A0A0A"
BG_CARD = "#161616"
BG_HOVER = "#1F1F1F"
BG_INPUT = "#121212"
BORDER = "#262626"
BORDER_LIGHT = "#2E2E2E"
TEXT = "#FAFAFA"
TEXT_DIM = "#A3A3A3"
TEXT_MUTED = "#525252"
ACCENT = "#FF5A1F"
ACCENT_LIGHT = "#FF7847"
ACCENT_DEEP = "#E64A0A"
GREEN = "#22C55E"
RED = "#EF4444"
YELLOW = "#F59E0B"

STYLESHEET = f"""
* {{
    font-family: "Inter", "SF Pro Display", "Helvetica Neue", sans-serif;
    color: {TEXT};
    outline: none;
}}

QMainWindow, QWidget#Root {{ background: {BG}; }}

QWidget#Sidebar {{
    background: {BG};
    border-right: 1px solid {BORDER};
}}

QFrame#Card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 16px;
}}

QFrame#CardFlat {{
    background: {BG_CARD};
    border-radius: 14px;
}}

QFrame#CardHero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {ACCENT_DEEP}, stop:1 {ACCENT_LIGHT});
    border-radius: 16px;
}}

QPushButton#SidebarItem {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    color: {TEXT_DIM};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#SidebarItem:hover {{
    background: {BG_HOVER};
    color: {TEXT};
}}
QPushButton#SidebarItemActive {{
    background: {BORDER};
    border: none;
    border-radius: 10px;
    padding: 10px 12px;
    text-align: left;
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}

QPushButton#PrimaryBtn {{
    background: {ACCENT};
    border: none;
    border-radius: 10px;
    padding: 10px 18px;
    color: white;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton#PrimaryBtn:hover {{ background: {ACCENT_LIGHT}; }}
QPushButton#PrimaryBtn:pressed {{ background: {ACCENT_DEEP}; }}
QPushButton#PrimaryBtn:disabled {{ background: #5A2A15; color: #888; }}

QPushButton#GhostBtn {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 8px 14px;
    color: {TEXT};
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#GhostBtn:hover {{ background: {BG_HOVER}; border-color: {BORDER_LIGHT}; }}

QPushButton#IconBtn {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px;
    min-width: 36px; min-height: 36px;
    max-width: 36px; max-height: 36px;
}}
QPushButton#IconBtn:hover {{ background: {BG_HOVER}; }}

QPushButton#TabBtn {{
    background: transparent; border: none; border-radius: 8px;
    padding: 6px 14px; color: {TEXT_DIM}; font-size: 12px; font-weight: 500;
}}
QPushButton#TabBtn:hover {{ color: {TEXT}; }}
QPushButton#TabBtnActive {{
    background: {ACCENT};
    border: none; border-radius: 8px;
    padding: 6px 14px; color: white; font-size: 12px; font-weight: 600;
}}

QLineEdit, QComboBox, QSpinBox {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 9px 12px;
    color: {TEXT};
    font-size: 13px;
    min-height: 20px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {ACCENT};
}}
QLineEdit#Search {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    padding-left: 32px;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {BG_HOVER};
    color: {TEXT};
    padding: 4px;
}}

QPlainTextEdit, QTextEdit {{
    background: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 10px;
    color: {TEXT_DIM};
    padding: 10px;
    font-family: "SF Mono", "Menlo", "Consolas", monospace;
    font-size: 11px;
    selection-background-color: {ACCENT};
}}

QTableWidget {{
    background: transparent;
    border: none;
    gridline-color: transparent;
    selection-background-color: {BG_HOVER};
}}
QTableWidget::item {{ padding: 12px 8px; border: none; border-bottom: 1px solid {BORDER}; }}
QTableWidget::item:selected {{ background: {BG_HOVER}; color: {TEXT}; }}
QHeaderView::section {{
    background: transparent;
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 10px 8px;
    font-weight: 500;
    font-size: 11px;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {BORDER_LIGHT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; background: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 4px; min-width: 30px; }}

QLabel#H1 {{ font-size: 22px; font-weight: 700; }}
QLabel#H2 {{ font-size: 18px; font-weight: 600; }}
QLabel#H3 {{ font-size: 15px; font-weight: 600; }}
QLabel#Dim {{ color: {TEXT_DIM}; font-size: 13px; }}
QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 11px; font-weight: 500; letter-spacing: 0.5px; }}
QLabel#Big {{ font-size: 26px; font-weight: 700; }}
QLabel#Huge {{ font-size: 30px; font-weight: 800; }}
QLabel#HeroTitle {{ color: white; font-weight: 600; font-size: 14px; }}
QLabel#HeroSub {{ color: rgba(255,255,255,0.85); font-size: 11px; }}
QLabel#HeroBig {{ color: white; font-size: 28px; font-weight: 800; }}

QLabel#SectionLabel {{
    color: {TEXT_MUTED};
    font-size: 10px; font-weight: 600;
    letter-spacing: 1.2px;
    padding: 4px 12px;
}}

QPushButton#ChipOn {{
    background: {ACCENT};
    color: white;
    border: none; border-radius: 10px;
    padding: 6px 12px;
    font-size: 12px; font-weight: 600;
}}
QPushButton#ChipOn:hover {{ background: {ACCENT_LIGHT}; }}
QPushButton#ChipOff {{
    background: transparent;
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 6px 12px;
    font-size: 12px; font-weight: 500;
}}
QPushButton#ChipOff:hover {{ background: {BG_HOVER}; color: {TEXT}; border-color: {BORDER_LIGHT}; }}

QProgressBar {{
    background: {BG_INPUT};
    border: none;
    border-radius: 6px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT_DEEP}, stop:1 {ACCENT_LIGHT});
    border-radius: 6px;
}}

QToolTip {{
    background: {BG_CARD};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 10px;
}}
"""
