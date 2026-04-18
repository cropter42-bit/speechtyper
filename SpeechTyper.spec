# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.building.datastruct import Tree
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


project_root = Path.cwd().resolve()
site_packages = (project_root / ".venv" / "Lib" / "site-packages").resolve()

vosk_datas = collect_data_files("vosk")
vosk_binaries = collect_dynamic_libs("vosk")
vosk_hiddenimports = collect_submodules("vosk")

vosk_tree = Tree(str(site_packages / "vosk"), prefix="vosk")
config_tree = Tree(str(project_root / "config"), prefix="config")
models_tree = Tree(str(project_root / "models" / "vosk-model-en-us-0.22"), prefix="models\\vosk-model-en-us-0.22")


a = Analysis(
    ['src\\main.py'],
    pathex=[],
    binaries=vosk_binaries,
    datas=vosk_datas,
    hiddenimports=vosk_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SpeechTyper',
    icon='assets\\app-icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    a.datas,
    vosk_tree,
    config_tree,
    models_tree,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SpeechTyper',
)
