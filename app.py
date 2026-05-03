#!/usr/bin/env python3
"""Ad Variator — PySide6 desktop dashboard."""
import os
import sys
from pathlib import Path


def _bootstrap_frozen() -> None:
    """Set up paths and env for the bundled .app: writable user-data dir, env file, Playwright browsers."""
    if not getattr(sys, "frozen", False):
        return

    user_data = Path.home() / "Library" / "Application Support" / "Ad Variator"
    user_data.mkdir(parents=True, exist_ok=True)

    env_file = user_data / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except Exception:
            pass

    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    browsers_dir = bundle_root / "playwright_browsers"
    if browsers_dir.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir))


_bootstrap_frozen()


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
