#!/usr/bin/env python3
"""Ad Variator — PySide6 desktop dashboard."""
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui import theme
from gui.main import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Ad Variator")
    app.setOrganizationName("ad-variator")

    f = QFont("Inter")
    if f.exactMatch() is False:
        f = QFont("SF Pro Display")
    f.setPointSize(12)
    app.setFont(f)

    app.setStyleSheet(theme.STYLESHEET)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
