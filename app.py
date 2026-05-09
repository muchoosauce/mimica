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
            # override=True so values saved via Settings always win over any
            # empty/stale shell env vars the user may have in their profile.
            load_dotenv(env_file, override=True)
        except Exception:
            pass

    # Search common bundled locations for the Playwright browsers dir.
    candidates = []
    mei = getattr(sys, "_MEIPASS", "")
    if mei:
        mei_path = Path(mei)
        candidates.append(mei_path / "playwright_browsers")
        # When packaged as .app, MEIPASS is .app/Contents/Frameworks; browsers
        # live next door in .app/Contents/Resources.
        if mei_path.parent.name == "Contents":
            candidates.append(mei_path.parent / "Resources" / "playwright_browsers")
    for browsers_dir in candidates:
        if browsers_dir.exists():
            os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browsers_dir))
            break


_bootstrap_frozen()


from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui import theme
from gui.main import MainWindow


def _load_fonts() -> None:
    """Register Inter (4 weights) + Caveat from gui/fonts/."""
    fonts_dir = Path(__file__).resolve().parent / "gui" / "fonts"
    if not fonts_dir.exists():
        return
    for f in fonts_dir.iterdir():
        if f.suffix.lower() in (".ttf", ".otf"):
            QFontDatabase.addApplicationFont(str(f))


def _load_app_icon(app: QApplication) -> None:
    """Set the dock / window icon from gui/assets/icon.png.

    On macOS this swaps the rocket-launcher icon out of the Dock while the
    app is running. Note: the wrapper .app's static icon (used in Finder
    when the app isn't running) comes from wrapper/AppIcon.icns instead.
    """
    icon_path = Path(__file__).resolve().parent / "gui" / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Mimica")
    app.setOrganizationName("mimica")

    _load_fonts()
    _load_app_icon(app)

    f = QFont("Inter")
    if not f.exactMatch():
        f = QFont("SF Pro Display")
    f.setPointSize(12)
    app.setFont(f)

    app.setStyleSheet(theme.STYLESHEET)

    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
