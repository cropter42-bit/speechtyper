from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from speech_typer.core.config_store import ConfigStore
from speech_typer.core.dictation_controller import DictationController
from speech_typer.ui.main_window import MainWindow


APP_NAME = "SpeechTyper"


def resolve_asset_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [exe_dir / "_internal", exe_dir, exe_dir.parent]
        for candidate in candidates:
            if (candidate / "config").exists() and (candidate / "models").exists():
                return candidate
        return exe_dir

    return Path(__file__).resolve().parents[2]


def resolve_data_root() -> Path:
    if getattr(sys, "frozen", False):
        local_app_data = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local_app_data / APP_NAME

    return resolve_asset_root() / "data"


def create_loading_splash() -> QSplashScreen:
    pixmap = QPixmap(440, 240)
    pixmap.fill(QColor("#07101d"))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(15, 25, 44, 236))
    painter.drawRoundedRect(14, 14, 412, 212, 24, 24)

    painter.setPen(QColor("#8bb9ff"))
    eyebrow_font = QFont("Segoe UI", 9)
    eyebrow_font.setBold(True)
    painter.setFont(eyebrow_font)
    painter.drawText(34, 56, "SPEECHTYPER")

    painter.setPen(QColor("#f4f8ff"))
    title_font = QFont("Segoe UI", 24)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.drawText(34, 112, "Loading...")

    painter.setPen(QColor("#9db2d8"))
    copy_font = QFont("Segoe UI", 11)
    painter.setFont(copy_font)
    painter.drawText(34, 162, "The app will open automatically when ready.")
    painter.end()

    splash = QSplashScreen(pixmap)
    splash.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    return splash


def main() -> int:
    asset_root = resolve_asset_root()
    data_root = resolve_data_root()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)

    splash = create_loading_splash()
    splash.show()
    app.processEvents()

    store = ConfigStore(asset_root, data_root)
    controller = DictationController(asset_root, store)
    window = MainWindow(store, controller)
    window.show()
    splash.finish(window)

    exit_code = app.exec()
    controller.shutdown()
    return exit_code
