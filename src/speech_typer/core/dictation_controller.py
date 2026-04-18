from __future__ import annotations

import re
import threading
import time
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QObject, Signal

from speech_typer.core.audio_capture import AudioCaptureService
from speech_typer.core.config_store import ConfigStore, Settings
from speech_typer.core.custom_words import CustomWordEntry, CustomWordsManager
from speech_typer.core.hotkey_service import GlobalHotkeyService
from speech_typer.core.keyboard_injector import KeyboardInjector
from speech_typer.core.speech_engine import Hypothesis, SpeechEngine


class DictationController(QObject):
    status_changed = Signal(str)
    transcript_changed = Signal(str)
    microphone_changed = Signal(str)
    profiles_changed = Signal(list)
    devices_changed = Signal(list)
    settings_changed = Signal(dict)
    enabled_changed = Signal(bool)
    alert_raised = Signal(str)
    custom_words_changed = Signal(list)

    def __init__(self, project_root: Path, store: ConfigStore) -> None:
        super().__init__()
        self.project_root = project_root
        self.store = store
        self.settings: Settings = store.load_settings()
        self.speech_engine = SpeechEngine(project_root)
        self.audio = AudioCaptureService()
        self.keyboard = KeyboardInjector()
        self.custom_words = CustomWordsManager(store)
        self.profiles = self.store.load_models()
        self.enabled = False
        self.model_ready = False
        self.microphone_ready = False

        self._committed_text = ""
        self._last_partial_text = ""
        self._segment_audio = bytearray()
        self._typed_segments: set[str] = set()
        self.session_active = threading.Event()
        self.shutdown_event = threading.Event()
        self.engine_lock = threading.Lock()
        self.session_lock = threading.Lock()

        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()

        self.hotkey_service = GlobalHotkeyService(self.settings.hotkey, self._handle_hotkey_state)
        self.hotkey_service.start()

        self._load_profile(self.settings.selected_profile_id)
        self._configure_microphone(self.settings.microphone_device)

        self.profiles_changed.emit(self.profiles)
        self.devices_changed.emit(self.list_microphones())
        self.settings_changed.emit(self.serialize_settings())
        self.custom_words.set_confidence_level(self.settings.custom_word_confidence)
        self.custom_words_changed.emit(self.custom_words.list_entries())
        self.set_enabled(self.settings.app_enabled, persist=False)

    def serialize_settings(self) -> dict:
        return {
            "hotkey": self.settings.hotkey,
            "selected_profile_id": self.settings.selected_profile_id,
            "microphone_device": self.settings.microphone_device,
            "app_enabled": self.settings.app_enabled,
            "custom_word_confidence": self.settings.custom_word_confidence,
        }

    def list_microphones(self) -> list[str]:
        devices = []
        for device in sd.query_devices():
            if device["max_input_channels"] > 0:
                devices.append(device["name"])
        return devices

    def set_enabled(self, enabled: bool, persist: bool = True) -> None:
        self.enabled = enabled and self.model_ready and self.microphone_ready
        self.settings.app_enabled = self.enabled
        if not self.enabled:
            self.end_dictation()
        if persist:
            self.store.save_settings(self.settings)
        self.enabled_changed.emit(self.enabled)
        self.settings_changed.emit(self.serialize_settings())
        self._emit_status()

    def apply_settings(self, hotkey: str, profile_id: str, microphone_device: str) -> None:
        self.settings.hotkey = hotkey.strip().lower() or "alt"
        self.settings.selected_profile_id = profile_id or self.settings.selected_profile_id
        self.settings.microphone_device = microphone_device

        self.hotkey_service.update_hotkey(self.settings.hotkey)
        self._configure_microphone(self.settings.microphone_device)

        self.settings.app_enabled = self.enabled and self.model_ready and self.microphone_ready
        self.store.save_settings(self.settings)
        self.devices_changed.emit(self.list_microphones())
        self.settings_changed.emit(self.serialize_settings())
        self._emit_status()

    def set_custom_word_confidence(self, value: int) -> None:
        self.settings.custom_word_confidence = max(0, min(100, int(value)))
        self.custom_words.set_confidence_level(self.settings.custom_word_confidence)
        self.store.save_settings(self.settings)
        self.settings_changed.emit(self.serialize_settings())

    def shutdown(self) -> None:
        self.shutdown_event.set()
        self.session_active.clear()
        self.audio.end_session()
        self.audio.stop()
        self.hotkey_service.stop()
        self.processing_thread.join(timeout=1.0)

    def list_custom_words(self) -> list[CustomWordEntry]:
        return self.custom_words.list_entries()

    def search_custom_words(self, query: str) -> list[CustomWordEntry]:
        return self.custom_words.filter_entries(query)

    def save_custom_word(self, entry: CustomWordEntry, original_target: str | None = None) -> None:
        self.custom_words.upsert(entry, original_target=original_target)
        self.custom_words_changed.emit(self.custom_words.list_entries())

    def delete_custom_word(self, target: str) -> None:
        self.custom_words.delete(target)
        self.custom_words_changed.emit(self.custom_words.list_entries())

    def begin_dictation(self) -> None:
        with self.session_lock:
            if not self.enabled or not self.model_ready or not self.microphone_ready:
                return
            if self.session_active.is_set():
                return
            try:
                with self.engine_lock:
                    self.speech_engine.reset()
                self.audio.begin_session()
                self.keyboard.finalize_session()
                self._committed_text = ""
                self._last_partial_text = ""
                self._segment_audio = bytearray()
                self._typed_segments = set()
                self.session_active.set()
                self.transcript_changed.emit("")
                self._emit_status("Listening...")
            except Exception as exc:
                self.alert_raised.emit(f"Could not start listening: {exc}")
                self._emit_status()

    def end_dictation(self) -> None:
        with self.session_lock:
            if not self.session_active.is_set():
                self._emit_status()
                return
            self.session_active.clear()
            self.audio.end_session()
            self._flush_final_result()
            self.keyboard.finalize_session()
            self._emit_status()

    def _handle_hotkey_state(self, active: bool) -> None:
        if not self.enabled:
            return
        if active:
            self.begin_dictation()
        else:
            self.end_dictation()

    def _processing_loop(self) -> None:
        while not self.shutdown_event.is_set():
            if not self.session_active.is_set():
                time.sleep(0.05)
                continue

            chunk = self.audio.read_chunk(timeout=0.1)
            if not chunk:
                continue

            try:
                self._segment_audio.extend(chunk)
                with self.engine_lock:
                    if not self.session_active.is_set():
                        continue
                    hypothesis = self.speech_engine.accept_audio(chunk)
                self._apply_hypothesis(hypothesis)
            except Exception as exc:
                self.alert_raised.emit(f"Speech processing error: {exc}")
                self.end_dictation()

    def _apply_hypothesis(self, hypothesis: Hypothesis) -> None:
        if hypothesis.final_text:
            segment_audio = bytes(self._segment_audio)
            finalized = self._apply_custom_words(hypothesis.final_text, segment_audio)
            self._committed_text = self._merge_text(self._committed_text, finalized)
            self._last_partial_text = ""
            self._segment_audio = bytearray()
            live_text = self._committed_text
            self.transcript_changed.emit(live_text)
            self._type_finalized_segment(finalized)
            return

        if hypothesis.partial_text:
            self._last_partial_text = self._clean_text(hypothesis.partial_text)
            live_text = self._build_live_text()
            self.transcript_changed.emit(live_text)

    def _flush_final_result(self) -> None:
        try:
            with self.engine_lock:
                final_result = self.speech_engine.finalize()
        except Exception:
            final_result = Hypothesis()

        if final_result.final_text:
            finalized = self._apply_custom_words(final_result.final_text, bytes(self._segment_audio))
            self._committed_text = self._merge_text(self._committed_text, finalized)
            self._type_finalized_segment(finalized)

        self._segment_audio = bytearray()
        final_text = self._committed_text
        self.transcript_changed.emit(final_text)

    def _build_live_text(self) -> str:
        if not self._last_partial_text:
            return self._committed_text
        return self._merge_text(self._committed_text, self._last_partial_text)

    def _merge_text(self, base: str, addition: str) -> str:
        base = self._clean_text(base)
        addition = self._clean_text(addition)
        if not addition:
            return base
        if not base:
            return addition
        return f"{base} {addition}"

    def _clean_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip()

    def _apply_custom_words(self, text: str, audio_bytes: bytes) -> str:
        cleaned = self._clean_text(text)
        if not cleaned:
            return ""
        return self.custom_words.apply_to_segment(cleaned, audio_bytes)

    def _type_finalized_segment(self, text: str) -> None:
        text = self._clean_text(text)
        if not text:
            return
        if text in self._typed_segments:
            return
        prefix = "" if not self._typed_segments else " "
        try:
            self.keyboard.type_text(f"{prefix}{text}")
            self._typed_segments.add(text)
        except Exception as exc:
            self.alert_raised.emit(f"Typing error: {exc}")

    def _load_profile(self, profile_id: str) -> None:
        self.model_ready = False
        if not self.profiles:
            self.alert_raised.emit("No Vosk models are configured.")
            return

        selected = next((profile for profile in self.profiles if profile["id"] == profile_id), None)
        if selected is None:
            selected = self.profiles[0]
            self.settings.selected_profile_id = selected["id"]

        try:
            self.speech_engine.load_profile(selected)
            self.settings.selected_profile_id = selected["id"]
            self.model_ready = True
        except FileNotFoundError as exc:
            self.alert_raised.emit(str(exc))

    def _configure_microphone(self, microphone_device: str) -> None:
        self.microphone_ready = False
        self.audio.stop()
        try:
            self.audio.configure(self.current_profile["sample_rate"], microphone_device)
            self.audio.start()
            self.microphone_ready = True
            self.microphone_changed.emit("Ready")
        except Exception as exc:
            self.microphone_changed.emit("Unavailable")
            self.alert_raised.emit(f"Microphone error: {exc}")

    @property
    def current_profile(self) -> dict:
        for profile in self.profiles:
            if profile["id"] == self.settings.selected_profile_id:
                return profile
        return self.profiles[0]

    def _emit_status(self, override: str | None = None) -> None:
        if override:
            self.status_changed.emit(override)
            return
        if not self.model_ready:
            self.status_changed.emit("Model not ready")
            return
        if not self.microphone_ready:
            self.status_changed.emit("Microphone not ready")
            return
        if self.session_active.is_set():
            self.status_changed.emit("Listening...")
            return
        if self.enabled:
            self.status_changed.emit(f"On - hold {self.settings.hotkey} to speak")
            return
        self.status_changed.emit("Off")
