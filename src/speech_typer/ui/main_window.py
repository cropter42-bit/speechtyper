from __future__ import annotations

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QSequentialAnimationGroup, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QKeyEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from speech_typer.core.config_store import ConfigStore
from speech_typer.core.dictation_controller import DictationController
from speech_typer.ui.styles import build_stylesheet


class HeroToggleButton(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._knob_offset = 0.0
        self._press_depth = 0.0

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        from PySide6.QtCore import QSize
        return QSize(280, 92)

    def get_knob_offset(self) -> float:
        return self._knob_offset

    def set_knob_offset(self, value: float) -> None:
        self._knob_offset = value
        self.update()

    def get_press_depth(self) -> float:
        return self._press_depth

    def set_press_depth(self, value: float) -> None:
        self._press_depth = value
        self.update()

    knobOffset = Property(float, get_knob_offset, set_knob_offset)
    pressDepth = Property(float, get_press_depth, set_press_depth)

    def set_on_state(self, enabled: bool) -> None:
        self.setChecked(enabled)
        self.setText("ON" if enabled else "OFF")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.set_press_depth(0.98)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        self.set_press_depth(0.0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)
        rect.translate(0, 2 if self._press_depth else 0)
        radius = rect.height() / 2

        if self.isChecked():
            base = QColor("#65f0dc")
            accent = QColor("#51d8ff")
            border = QColor(154, 252, 230, 135)
        else:
            base = QColor("#2b3447")
            accent = QColor("#3d4a60")
            border = QColor(255, 255, 255, 24)

        painter.setPen(QPen(border, 1))
        painter.setBrush(QColor(base))
        painter.drawRoundedRect(rect, radius, radius)

        inner = rect.adjusted(1, 1, -1, -1)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent if self.isChecked() else QColor("#364357"))
        painter.drawRoundedRect(inner, radius - 1, radius - 1)

        margin = 10
        knob_size = rect.height() - margin * 2
        min_x = rect.left() + margin
        max_x = rect.right() - margin - knob_size
        knob_x = min_x + (max_x - min_x) * self._knob_offset
        knob_rect = rect.adjusted(0, margin, 0, -margin)
        knob_rect.setLeft(int(knob_x))
        knob_rect.setWidth(knob_size)

        painter.setBrush(QColor("#f8fcff"))
        painter.drawEllipse(knob_rect)

        painter.setPen(QColor("#07101d" if self.isChecked() else "#ecf2ff"))
        font = QFont("Segoe UI", 11)
        font.setWeight(QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "ON" if self.isChecked() else "OFF")


class TranscriptPreview(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("glassCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self.body = QLabel("Live transcript preview")
        self.body.setObjectName("muted")
        self.body.setWordWrap(True)
        self.body.setMinimumHeight(118)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.body)

        self.cursor_visible = True
        self.current_text = ""
        self.cursor_timer = QTimer(self)
        self.cursor_timer.timeout.connect(self._toggle_cursor)
        self.cursor_timer.start(530)

        self.fade_shadow = QGraphicsDropShadowEffect(self)
        self.fade_shadow.setBlurRadius(26)
        self.fade_shadow.setOffset(0, 12)
        self.fade_shadow.setColor(QColor(9, 16, 29, 170))
        self.setGraphicsEffect(self.fade_shadow)

        self.fade_anim = QPropertyAnimation(self.fade_shadow, b"blurRadius", self)
        self.fade_anim.setDuration(220)
        self.fade_anim.setStartValue(20)
        self.fade_anim.setEndValue(34)
        self.fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_transcript(self, text: str) -> None:
        self.current_text = text
        self._render()
        self.fade_anim.stop()
        self.fade_anim.start()

    def _toggle_cursor(self) -> None:
        self.cursor_visible = not self.cursor_visible
        self._render()

    def _render(self) -> None:
        cursor = "<span style='color:#7bd6ff;'>|</span>" if self.cursor_visible else "<span style='color:transparent;'>|</span>"
        safe_text = self.current_text or "<span style='color:#7387ae;'>Live transcript preview</span>"
        self.body.setText(f"{safe_text} {cursor}")


class HotkeyCaptureButton(QPushButton):
    hotkey_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ghostButton")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._hotkey = "alt"
        self._capturing = False
        self.clicked.connect(self._begin_capture)
        self._update_text()

    def set_hotkey(self, hotkey: str) -> None:
        self._hotkey = (hotkey or "alt").lower()
        if not self._capturing:
            self._update_text()

    def hotkey(self) -> str:
        return self._hotkey

    def _begin_capture(self) -> None:
        self._capturing = True
        self.setText("Press a key...")
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key_name = self._normalize_key(event)
        if key_name:
            self._hotkey = key_name
            self._capturing = False
            self._update_text()
            self.hotkey_changed.emit(self._hotkey)
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        if self._capturing:
            self._capturing = False
            self._update_text()
        super().focusOutEvent(event)

    def _update_text(self) -> None:
        self.setText(self._hotkey.upper())

    def _normalize_key(self, event: QKeyEvent) -> str | None:
        key = event.key()
        mapping = {
            Qt.Key.Key_Alt: "alt",
            Qt.Key.Key_Control: "ctrl",
            Qt.Key.Key_Shift: "shift",
            Qt.Key.Key_Meta: "win",
            Qt.Key.Key_Space: "space",
            Qt.Key.Key_Tab: "tab",
            Qt.Key.Key_Return: "enter",
            Qt.Key.Key_Enter: "enter",
            Qt.Key.Key_Escape: "esc",
        }
        if key in mapping:
            return mapping[key]
        text = event.text().strip().lower()
        if len(text) == 1 and text.isprintable():
            return text
        return None


class SettingsPage(QWidget):
    back_requested = Signal()

    def __init__(self, controller: DictationController, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("pageSurface")
        self.controller = controller
        self.store = store

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Settings")
        title.setObjectName("dialogTitle")
        copy = QLabel("Choose the microphone and the hotkey SpeechTyper should use in the background.")
        copy.setObjectName("dialogCopy")
        copy.setWordWrap(True)
        title_block.addWidget(title)
        title_block.addWidget(copy)
        header.addLayout(title_block, 1)

        form_card = QWidget()
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.setSpacing(14)

        self.hotkey_button = HotkeyCaptureButton()
        self.microphone_combo = QComboBox()
        form.addRow("Hotkey", self.hotkey_button)
        form.addRow("Mic", self.microphone_combo)
        form_layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("ghostButton")
        cancel_button.clicked.connect(self._reset)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)

        layout.addLayout(header)
        layout.addWidget(form_card)
        layout.addLayout(buttons)
        layout.addStretch()

        self.controller.settings_changed.connect(self._sync_settings)
        self._populate_microphones()
        self._sync_settings(self.controller.serialize_settings())

    def _populate_microphones(self) -> None:
        current = self.microphone_combo.currentData() or ""
        self.microphone_combo.clear()
        self.microphone_combo.addItem("Default", userData="")
        for device in self.controller.list_microphones():
            self.microphone_combo.addItem(device, userData=device)
        index = self.microphone_combo.findData(current)
        if index >= 0:
            self.microphone_combo.setCurrentIndex(index)

    def _sync_settings(self, payload: dict) -> None:
        self._populate_microphones()
        self.hotkey_button.set_hotkey(payload.get("hotkey", "alt"))
        index = self.microphone_combo.findData(payload.get("microphone_device", ""))
        if index >= 0:
            self.microphone_combo.setCurrentIndex(index)

    def _reset(self) -> None:
        self._sync_settings(self.controller.serialize_settings())
        self.back_requested.emit()

    def _save(self) -> None:
        self.controller.apply_settings(
            hotkey=self.hotkey_button.hotkey(),
            profile_id=self.controller.settings.selected_profile_id,
            microphone_device=self.microphone_combo.currentData() or "",
        )
        self.back_requested.emit()


class MainWindow(QMainWindow):
    def __init__(self, store: ConfigStore, controller: DictationController) -> None:
        super().__init__()
        self.store = store
        self.controller = controller
        self.setWindowTitle("SpeechTyper")
        self.setFixedSize(620, 520)
        self.setStyleSheet(build_stylesheet())

        self._build_ui()
        self._build_tray()
        self._bind_signals()
        self._build_animations()
        self._sync_settings(self.controller.serialize_settings())

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            super().closeEvent(event)

    def _build_ui(self) -> None:
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 20, 20, 20)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(24, 24, 24, 24)

        self.pages = QStackedWidget()
        self.pages.setObjectName("contentStack")
        self.home_page = self._build_home_page()
        self.settings_page = SettingsPage(self.controller, self.store)
        self.settings_page.back_requested.connect(self._show_home)

        self.pages.addWidget(self.home_page)
        self.pages.addWidget(self.settings_page)
        panel_layout.addWidget(self.pages)

        outer.addWidget(self.panel)
        self.setCentralWidget(central)

        self._apply_shadow(self.panel, blur=50, color="#020714", y_offset=18)
        self._apply_shadow(self.transcript_box, blur=26, color="#050b15", y_offset=12)
        self._apply_shadow(self.toggle_button, blur=30, color="#1b5f74", y_offset=14)

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("pageSurface")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)

        self.toggle_button = HeroToggleButton()
        self.toggle_button.clicked.connect(self._toggle_enabled)

        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.clicked.connect(lambda: self.pages.setCurrentWidget(self.settings_page))

        self.transcript_box = TranscriptPreview()

        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self.toggle_button, 5)
        row.addWidget(self.settings_button, 1)

        layout.addLayout(row)
        layout.addWidget(self.transcript_box)
        return page

    def _show_home(self) -> None:
        self.pages.setCurrentWidget(self.home_page)

    def _build_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setToolTip("SpeechTyper")
        self.tray_icon.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_MediaVolume))

        menu = QMenu(self)
        show_action = QAction("Open", self)
        show_action.triggered.connect(self.showNormal)
        toggle_action = QAction("Toggle On/Off", self)
        toggle_action.triggered.connect(self._toggle_enabled)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(show_action)
        menu.addAction(toggle_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray_icon.setContextMenu(menu)
        self.tray_icon.activated.connect(self._handle_tray_activation)
        self.tray_icon.show()

    def _bind_signals(self) -> None:
        self.controller.status_changed.connect(self._on_status_changed)
        self.controller.transcript_changed.connect(self.transcript_box.set_transcript)
        self.controller.settings_changed.connect(self._sync_settings)
        self.controller.enabled_changed.connect(self._on_enabled_changed)
        self.controller.alert_raised.connect(self._show_alert)

    def _sync_settings(self, payload: dict) -> None:
        self._on_enabled_changed(payload["app_enabled"])

    def _toggle_enabled(self) -> None:
        self.controller.set_enabled(not self.controller.enabled)

    def _on_enabled_changed(self, enabled: bool) -> None:
        self.toggle_button.set_on_state(enabled)
        self._animate_toggle(enabled)

    def _on_status_changed(self, status: str) -> None:
        if "Listening" in status:
            self.panel_breathe.start()
        else:
            self.panel_breathe.stop()

    def _show_alert(self, message: str) -> None:
        QMessageBox.information(self, "SpeechTyper", message)

    def _handle_tray_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()
            self.activateWindow()

    def _quit_from_tray(self) -> None:
        self.tray_icon.hide()
        self.close()
        QApplication.quit()

    def _build_animations(self) -> None:
        self.toggle_knob = QPropertyAnimation(self.toggle_button, b"knobOffset", self)
        self.toggle_knob.setDuration(240)
        self.toggle_knob.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.toggle_shadow_anim = QPropertyAnimation(self.toggle_shadow, b"blurRadius", self)
        self.toggle_shadow_anim.setDuration(300)
        self.toggle_shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.panel_breathe = QSequentialAnimationGroup(self)
        for start, end in ((28, 36), (36, 28)):
            anim = QPropertyAnimation(self.preview_shadow, b"blurRadius", self)
            anim.setDuration(520)
            anim.setStartValue(start)
            anim.setEndValue(end)
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.panel_breathe.addAnimation(anim)
        self.panel_breathe.setLoopCount(-1)

    def _apply_shadow(self, widget: QWidget, blur: int, color: str, y_offset: int) -> None:
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(blur)
        shadow.setOffset(0, y_offset)
        shadow.setColor(QColor(color))
        widget.setGraphicsEffect(shadow)
        if widget is self.toggle_button:
            self.toggle_shadow = shadow
        if widget is self.transcript_box:
            self.preview_shadow = shadow

    def _animate_toggle(self, enabled: bool) -> None:
        self.toggle_knob.stop()
        self.toggle_shadow_anim.stop()
        self.toggle_knob.setStartValue(self.toggle_button.get_knob_offset())
        self.toggle_knob.setEndValue(1.0 if enabled else 0.0)
        self.toggle_knob.start()
        self.toggle_shadow_anim.setStartValue(self.toggle_shadow.blurRadius())
        self.toggle_shadow_anim.setEndValue(24 if enabled else 22)
        self.toggle_shadow_anim.start()
