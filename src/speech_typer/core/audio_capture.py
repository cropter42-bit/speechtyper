from __future__ import annotations

import queue
import threading
from typing import Optional

import sounddevice as sd


class AudioCaptureService:
    def __init__(self, sample_rate: int = 16000, channels: int = 1, block_ms: int = 250) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_size = int(sample_rate * block_ms / 1000)
        self.device: Optional[str] = None
        self.queue: queue.Queue[bytes] = queue.Queue()
        self.listening = threading.Event()
        self.stream: sd.RawInputStream | None = None

    def configure(self, sample_rate: int, device: str = "") -> None:
        self.sample_rate = sample_rate
        self.device = device or None
        self.block_size = int(sample_rate * 0.25)

    def start(self) -> None:
        if self.stream is not None:
            return
        self.stream = sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self.block_size,
            device=self.device,
            channels=self.channels,
            dtype="int16",
            callback=self._audio_callback,
        )
        self.stream.start()

    def stop(self) -> None:
        self.listening.clear()
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def begin_session(self) -> None:
        self._clear_queue()
        self.listening.set()

    def end_session(self) -> None:
        self.listening.clear()

    def read_chunk(self, timeout: float = 0.25) -> bytes | None:
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _audio_callback(self, indata, frames, time, status) -> None:
        if status:
            return
        if self.listening.is_set():
            self.queue.put(bytes(indata))

    def _clear_queue(self) -> None:
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                return
