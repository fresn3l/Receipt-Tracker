# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Finance.app (unsigned local build)."""

from pathlib import Path

block_cipher = None
root = Path(SPECPATH).resolve().parent.parent

a = Analysis(
    [str(root / "app" / "main.py")],
    pathex=[str(root), str(root / "packages")],
    binaries=[],
    datas=[
        (str(root / "web"), "web"),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "sqlalchemy.dialects.sqlite",
        "webview",
        "banking",
        "banking.service",
        "banking.routes",
        "banking.workflow",
        "banking.storage",
        "receipts",
        "receipts.routes",
        "receipts.database",
        "receipts.parser",
        "app.server",
        "app.migrate",
        "app.paths",
        "multipart",
        "openai",
        "pandas",
        "yaml",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["eel", "tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Finance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
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
    upx=True,
    upx_exclude=[],
    name="Finance",
)

app = BUNDLE(
    coll,
    name="Finance.app",
    icon=None,
    bundle_identifier="local.financeapp",
    info_plist={
        "CFBundleName": "Finance",
        "CFBundleDisplayName": "Finance App",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
    },
)
