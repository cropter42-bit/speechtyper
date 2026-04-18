from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path

from vosk import KaldiRecognizer, Model


@dataclass
class Hypothesis:
    partial_text: str = ""
    final_text: str = ""


class SpeechEngine:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.profile: dict | None = None
        self.model: Model | None = None
        self.recognizer: KaldiRecognizer | None = None

    def load_profile(self, profile: dict) -> None:
        model_path = self.project_root / profile["model_path"]
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")
        self.profile = profile
        self.model = Model(str(model_path))
        self.reset()

    def reset(self) -> None:
        if not self.profile or not self.model:
            raise RuntimeError("Speech profile has not been loaded.")
        self.recognizer = KaldiRecognizer(self.model, self.profile.get("sample_rate", 16000))
        self.recognizer.SetWords(True)
        self.recognizer.SetPartialWords(True)

    def accept_audio(self, chunk: bytes) -> Hypothesis:
        if self.recognizer is None:
            raise RuntimeError("Recognizer is not initialized.")
        accepted = self.recognizer.AcceptWaveform(chunk)
        if accepted:
            result = json.loads(self.recognizer.Result())
            return Hypothesis(final_text=result.get("text", ""))
        partial = json.loads(self.recognizer.PartialResult())
        return Hypothesis(partial_text=partial.get("partial", ""))

    def finalize(self) -> Hypothesis:
        if self.recognizer is None:
            return Hypothesis()
        result = json.loads(self.recognizer.FinalResult())
        return Hypothesis(final_text=result.get("text", ""))
