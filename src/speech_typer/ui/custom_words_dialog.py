from __future__ import annotations

import threading
import uuid
import wave
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from speech_typer.core.config_store import ConfigStore
from speech_typer.core.custom_words import CustomWordEntry, preprocess_audio_file, relativize_audio_paths
from speech_typer.core.dictation_controller import DictationController

try:
    import winsound
except ImportError:  # pragma: no cover - Windows-only playback path
    winsound = None


class FlowLayout(QLayout):
    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items = []
        self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: D401
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        x = rect.x()
        y = rect.y()
        line_height = 0
        for item in self._items:
            next_x = x + item.sizeHint().width() + self.spacing()
            if next_x - self.spacing() > rect.right() and line_height > 0:
                x = rect.x()
                y += line_height + self.spacing()
                next_x = x + item.sizeHint().width() + self.spacing()
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, item.sizeHint().width(), item.sizeHint().height()))
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        return y + line_height - rect.y()


class SampleChip(QFrame):
    def __init__(self, text: str, on_remove, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sampleChip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 8, 6)
        layout.setSpacing(6)
        layout.addWidget(QLabel(text))
        close_button = QToolButton()
        close_button.setText("x")
        close_button.clicked.connect(on_remove)
        layout.addWidget(close_button)


class SampleCloud(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sampleCloud")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        self.wrap = QWidget()
        self.flow = FlowLayout(self.wrap, spacing=8)
        self.wrap.setLayout(self.flow)
        layout.addWidget(self.wrap)

    def set_labels(self, labels: list[str], on_remove) -> None:
        while self.flow.count():
            item = self.flow.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for index, label in enumerate(labels):
            self.flow.addWidget(SampleChip(label, lambda checked=False, i=index: on_remove(i)))


class AudioRecorder:
    def __init__(self) -> None:
        self.frames: list[bytes] = []
        self.stream: sd.RawInputStream | None = None
        self.lock = threading.Lock()
        self.sample_rate = 16000

    def start(self) -> None:
        self.frames = []
        self.stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="int16",
            callback=self._callback,
        )
        self.stream.start()

    def stop(self, destination: Path) -> None:
        if self.stream is None:
            return
        self.stream.stop()
        self.stream.close()
        self.stream = None
        destination.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(destination), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(self.sample_rate)
            handle.writeframes(b"".join(self.frames))

    def _callback(self, indata, frames, time, status) -> None:
        if status:
            return
        with self.lock:
            self.frames.append(bytes(indata))


class CustomWordEditDialog(QDialog):
    def __init__(
        self,
        controller: DictationController,
        store: ConfigStore,
        entry: CustomWordEntry | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.store = store
        self.original_target = entry.target if entry else None
        self.recorder = AudioRecorder()
        self.recording = False
        self.recorded_samples = list(entry.audio_samples) if entry else []

        self.setModal(True)
        self.setWindowTitle("Add Custom Word" if entry is None else "Edit Custom Word")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("Custom Word")
        title.setObjectName("dialogTitle")
        copy = QLabel("Save the exact word or phrase, then record a few examples in your own voice.")
        copy.setObjectName("dialogCopy")
        copy.setWordWrap(True)

        form = QFormLayout()
        form.setSpacing(14)

        self.target_input = QLineEdit()
        self.target_input.setPlaceholderText("Your custom word")
        if entry:
            self.target_input.setText(entry.target)

        audio_box = QFrame()
        audio_box.setObjectName("glassCard")
        audio_layout = QVBoxLayout(audio_box)
        audio_layout.setContentsMargins(14, 14, 14, 14)
        audio_layout.setSpacing(10)

        self.record_status = QLabel("Record at least three samples in your normal speaking voice")
        self.record_status.setObjectName("muted")
        self.record_timer = QLabel("00:00")
        self.record_timer.setObjectName("previewLabel")
        self.sample_count = QLabel(self._build_sample_label())
        self.sample_count.setObjectName("muted")
        self.sample_cloud = SampleCloud()
        self.sample_cloud.set_labels(self._sample_labels(), self.remove_sample_at)

        controls = QHBoxLayout()
        self.record_button = QPushButton("Record sample")
        self.record_button.clicked.connect(self.toggle_recording)
        self.play_button = QPushButton("Play latest")
        self.play_button.setObjectName("ghostButton")
        self.play_button.clicked.connect(self.play_latest_sample)
        self.play_button.setEnabled(bool(self.recorded_samples))
        controls.addWidget(self.record_button)
        controls.addWidget(self.play_button)

        audio_layout.addWidget(self.record_status)
        audio_layout.addWidget(self.record_timer)
        audio_layout.addWidget(self.sample_count)
        audio_layout.addWidget(self.sample_cloud)
        audio_layout.addLayout(controls)

        form.addRow("Word to type", self.target_input)
        form.addRow("Voice samples", audio_box)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("ghostButton")
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)

        layout.addWidget(title)
        layout.addWidget(copy)
        layout.addLayout(form)
        layout.addLayout(buttons)

        self.elapsed_seconds = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self.opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b"opacity", self)
        self.fade.setDuration(220)
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self.fade.start()

    def toggle_recording(self) -> None:
        if not self.recording:
            try:
                self.recorder.start()
            except Exception as exc:
                QMessageBox.information(self, "SpeechTyper", f"Could not start recording: {exc}")
                return
            self.recording = True
            self.elapsed_seconds = 0
            self.timer.start(1000)
            self.record_button.setText("Stop recording")
            self.record_status.setText("Recording sample...")
            return

        sample_dir = self.store.ensure_custom_audio_dir()
        filename = f"{uuid.uuid4().hex}.wav"
        destination = sample_dir / filename
        try:
            self.recorder.stop(destination)
        except Exception as exc:
            QMessageBox.information(self, "SpeechTyper", f"Could not save recording: {exc}")
            return

        preprocess_audio_file(destination)
        self.recording = False
        self.timer.stop()
        self.record_button.setText("Record sample")
        self.record_status.setText("Sample recorded")
        self.recorded_samples.append(filename)
        self.play_button.setEnabled(True)
        self._refresh_samples()

    def play_latest_sample(self) -> None:
        if not self.recorded_samples or winsound is None:
            return
        sample_dir = self.store.ensure_custom_audio_dir()
        sample_path = sample_dir / self.recorded_samples[-1]
        if sample_path.exists():
            winsound.PlaySound(str(sample_path), winsound.SND_ASYNC)

    def remove_sample_at(self, index: int) -> None:
        if index < 0 or index >= len(self.recorded_samples):
            return
        sample_dir = self.store.ensure_custom_audio_dir()
        sample_path = sample_dir / self.recorded_samples[index]
        if sample_path.exists():
            try:
                sample_path.unlink()
            except OSError:
                pass
        self.recorded_samples.pop(index)
        self.play_button.setEnabled(bool(self.recorded_samples))
        self._refresh_samples()

    def save(self) -> None:
        target = self.target_input.text().strip()
        if not target:
            QMessageBox.information(self, "SpeechTyper", "Word to type is required.")
            return
        if len(self.recorded_samples) < 3:
            QMessageBox.information(self, "SpeechTyper", "Record at least three samples before saving.")
            return
        entry = CustomWordEntry(
            target=target,
            audio_samples=relativize_audio_paths(self.recorded_samples, self.store.ensure_custom_audio_dir()),
        )
        self.controller.save_custom_word(entry, original_target=self.original_target)
        self.accept()

    def _tick(self) -> None:
        self.elapsed_seconds += 1
        minutes, seconds = divmod(self.elapsed_seconds, 60)
        self.record_timer.setText(f"{minutes:02d}:{seconds:02d}")

    def _refresh_samples(self) -> None:
        self.sample_count.setText(self._build_sample_label())
        self.sample_cloud.set_labels(self._sample_labels(), self.remove_sample_at)

    def _sample_labels(self) -> list[str]:
        return [f"Sample {index}" for index in range(1, len(self.recorded_samples) + 1)]

    def _build_sample_label(self) -> str:
        count = len(self.recorded_samples)
        return "1 sample saved" if count == 1 else f"{count} samples saved"


class CustomWordCard(QFrame):
    def __init__(self, entry: CustomWordEntry, on_edit, on_delete, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("customWordCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        content = QVBoxLayout()
        title = QLabel(entry.target)
        title.setObjectName("cardTitle")
        sample_count = len(entry.audio_samples)
        subtitle = QLabel("1 voice sample" if sample_count == 1 else f"{sample_count} voice samples")
        subtitle.setObjectName("muted")
        content.addWidget(title)
        content.addWidget(subtitle)

        actions = QHBoxLayout()
        edit_button = QToolButton()
        edit_button.setText("Edit")
        edit_button.clicked.connect(lambda: on_edit(entry))
        delete_button = QToolButton()
        delete_button.setText("Delete")
        delete_button.clicked.connect(lambda: on_delete(entry))
        actions.addWidget(edit_button)
        actions.addWidget(delete_button)

        layout.addLayout(content, 1)
        layout.addLayout(actions)


class CustomWordsPage(QWidget):
    back_requested = Signal()

    def __init__(self, controller: DictationController, store: ConfigStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        header_row = QHBoxLayout()
        back_button = QPushButton("Back")
        back_button.setObjectName("ghostButton")
        back_button.clicked.connect(self.back_requested.emit)
        title_block = QVBoxLayout()
        title = QLabel("Custom Words")
        title.setObjectName("dialogTitle")
        copy = QLabel("Save words or phrases you want typed exactly, then support them with short recordings.")
        copy.setObjectName("dialogCopy")
        copy.setWordWrap(True)
        title_block.addWidget(title)
        title_block.addWidget(copy)
        self.add_button = QPushButton("+ Add Word")
        self.add_button.clicked.connect(self.add_word)
        header_row.addWidget(back_button)
        header_row.addLayout(title_block, 1)
        header_row.addWidget(self.add_button)

        confidence_card = QFrame()
        confidence_card.setObjectName("glassCard")
        confidence_layout = QVBoxLayout(confidence_card)
        confidence_layout.setContentsMargins(16, 16, 16, 16)
        confidence_layout.setSpacing(8)
        confidence_title = QLabel("Custom word confidence")
        confidence_title.setObjectName("cardTitle")
        confidence_copy = QLabel("Lower values make custom words easier to trigger. Higher values make replacements stricter.")
        confidence_copy.setObjectName("muted")
        confidence_copy.setWordWrap(True)
        slider_row = QHBoxLayout()
        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setRange(0, 100)
        self.confidence_slider.valueChanged.connect(self._update_confidence_label)
        self.confidence_slider.sliderReleased.connect(self._save_confidence)
        self.confidence_value = QLabel("55")
        self.confidence_value.setObjectName("previewLabel")
        slider_row.addWidget(self.confidence_slider, 1)
        slider_row.addWidget(self.confidence_value)
        confidence_layout.addWidget(confidence_title)
        confidence_layout.addWidget(confidence_copy)
        confidence_layout.addLayout(slider_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search custom words")
        self.search_input.textChanged.connect(self.refresh)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(12)
        self.scroll.setWidget(self.content)

        self.empty_state = QFrame()
        self.empty_state.setObjectName("glassCard")
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(22, 22, 22, 22)
        empty_layout.setSpacing(10)
        empty_title = QLabel("No custom words yet")
        empty_title.setObjectName("cardTitle")
        empty_copy = QLabel("Add your first word and record a few examples so SpeechTyper can recognize it more confidently.")
        empty_copy.setObjectName("muted")
        empty_copy.setWordWrap(True)
        empty_button = QPushButton("Add your first word")
        empty_button.clicked.connect(self.add_word)
        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_copy)
        empty_layout.addWidget(empty_button, 0, Qt.AlignmentFlag.AlignLeft)

        root.addLayout(header_row)
        root.addWidget(confidence_card)
        root.addWidget(self.search_input)
        root.addWidget(self.scroll, 1)

        self.controller.custom_words_changed.connect(lambda _: self.refresh())
        self.controller.settings_changed.connect(self._sync_settings)
        self._sync_settings(self.controller.serialize_settings())
        self.refresh()

    def _sync_settings(self, payload: dict) -> None:
        level = int(payload.get("custom_word_confidence", 55))
        self.confidence_slider.blockSignals(True)
        self.confidence_slider.setValue(level)
        self.confidence_slider.blockSignals(False)
        self._update_confidence_label(level)

    def _update_confidence_label(self, value: int) -> None:
        self.confidence_value.setText(str(value))

    def _save_confidence(self) -> None:
        self.controller.set_custom_word_confidence(self.confidence_slider.value())

    def refresh(self) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        entries = self.controller.search_custom_words(self.search_input.text())
        if not entries:
            self.content_layout.addWidget(self.empty_state)
            self.content_layout.addStretch()
            return

        for entry in entries:
            self.content_layout.addWidget(CustomWordCard(entry, self.edit_word, self.delete_word))
        self.content_layout.addStretch()

    def add_word(self) -> None:
        dialog = CustomWordEditDialog(self.controller, self.store, parent=self)
        dialog.exec()

    def edit_word(self, entry: CustomWordEntry) -> None:
        dialog = CustomWordEditDialog(self.controller, self.store, entry=entry, parent=self)
        dialog.exec()

    def delete_word(self, entry: CustomWordEntry) -> None:
        result = QMessageBox.question(self, "SpeechTyper", f"Delete '{entry.target}'?")
        if result == QMessageBox.StandardButton.Yes:
            self.controller.delete_custom_word(entry.target)
