from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class Settings:
    hotkey: str = "alt"
    selected_profile_id: str = "accurate-en"
    microphone_device: str = ""
    app_enabled: bool = False
    custom_word_confidence: int = 55


class ConfigStore:
    def __init__(self, asset_root: Path, data_root: Path) -> None:
        self.asset_root = asset_root
        self.data_root = data_root
        self.config_dir = asset_root / "config"
        self.data_dir = data_root
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data_dir / "settings.json"
        self.custom_words_path = self.data_dir / "custom_words.json"
        self.custom_audio_dir = self.data_dir / "custom-word-audio"
        self.models_path = self.config_dir / "models.json"

    def load_settings(self) -> Settings:
        if not self.settings_path.exists():
            settings = Settings()
            self.save_settings(settings)
            return settings

        payload = self._read_json(self.settings_path, {})
        return Settings(**{**asdict(Settings()), **payload})

    def save_settings(self, settings: Settings) -> None:
        self._write_json(self.settings_path, asdict(settings))

    def load_models(self) -> list[dict[str, Any]]:
        payload = self._read_json(self.models_path, {"profiles": []})
        return payload.get("profiles", [])

    def load_custom_words_payload(self) -> dict[str, Any]:
        payload = self._read_json(self.custom_words_path, {"words": []})
        if not isinstance(payload, dict):
            return {"words": []}
        words = payload.get("words", [])
        if not isinstance(words, list):
            words = []
        return {"words": words}

    def save_custom_words_payload(self, payload: dict[str, Any]) -> None:
        normalized = {"words": payload.get("words", [])}
        self._write_json(self.custom_words_path, normalized)

    def ensure_custom_audio_dir(self) -> Path:
        self.custom_audio_dir.mkdir(parents=True, exist_ok=True)
        return self.custom_audio_dir

    def _read_json(self, path: Path, fallback: Any) -> Any:
        if not path.exists():
            return fallback
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return fallback

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
