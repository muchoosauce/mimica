# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Ad Variator (.app bundle).

Build with build.command — it installs Chromium into ./build_browsers/ first
and PyInstaller bundles that directory inside the .app.
"""
from pathlib import Path

HERE = Path.cwd()

# Chromium is NOT bundled via PyInstaller because it has its own internal
# signature that breaks under PyInstaller's ad-hoc resigning. The build
# script copies build_browsers/ into Contents/Resources/ post-build.
datas = []

hiddenimports = [
    # PySide6 plugins / modules
    "PySide6.QtSvg",
    "PySide6.QtPrintSupport",
    # Optional deps that PyInstaller may not auto-detect
    "anthropic",
    "anthropic._client",
    "pypdf",
    "docx",
    "bs4",
    "playwright",
    "playwright.sync_api",
    "PIL",
    "PIL._imaging",
    # First-party
    "providers",
    "providers.muapi",
    "providers.kie",
    "providers.base",
    "providers.errors",
    "providers.parsing",
    "providers.prompts",
    "brand_dna",
    "brand_dna.anthropic_client",
    "brand_dna.candidates",
    "brand_dna.documents",
    "brand_dna.scraper",
    "brand_dna.types",
    "gui",
    "gui.core",
    "gui.main",
    "gui.pages",
    "gui.theme",
    "gui.widgets",
]

excludes = [
    "tkinter",
    "matplotlib",
    "scipy",
    "numpy.testing",
    "tornado",
    "pytest",
    "IPython",
    "jupyter",
]


a = Analysis(
    ["app.py"],
    pathex=[str(HERE)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AdVariator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AdVariator",
)

app = BUNDLE(
    coll,
    name="Ad Variator.app",
    icon=None,
    bundle_identifier="com.sofiane.advariator",
    info_plist={
        "CFBundleName": "Ad Variator",
        "CFBundleDisplayName": "Ad Variator",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "11.0",
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
    },
)
