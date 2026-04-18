from __future__ import annotations

import re
from dataclasses import dataclass

from speech_typer.core.personalization import PersonalizationStore


VOICE_COMMANDS = {
    "new line": "\n",
    "newline": "\n",
    "comma": ",",
    "period": ".",
    "full stop": ".",
    "question mark": "?",
    "exclamation mark": "!",
}


@dataclass
class ProcessedText:
    text: str


class TextPostProcessor:
    def __init__(self, personalization: PersonalizationStore) -> None:
        self.personalization = personalization

    def process(self, text: str, auto_punctuation: bool) -> ProcessedText:
        normalized = self._normalize_space(text)
        normalized = self._apply_voice_commands(normalized)
        normalized = self.personalization.apply(normalized)
        if auto_punctuation:
            normalized = self._auto_punctuate(normalized)
        return ProcessedText(text=normalized)

    def merge(self, committed: str, addition: str) -> str:
        addition = addition.strip()
        if not addition:
            return committed
        if not committed:
            return addition
        if addition.startswith((".", ",", "?", "!", "\n")):
            return committed + addition
        if committed.endswith("\n"):
            return committed + addition
        return f"{committed} {addition}"

    def _normalize_space(self, text: str) -> str:
        collapsed = re.sub(r"\s+", " ", text or "").strip()
        collapsed = collapsed.replace(" ,", ",").replace(" .", ".").replace(" !", "!").replace(" ?", "?")
        return collapsed

    def _apply_voice_commands(self, text: str) -> str:
        lowered = text.lower().strip()
        return VOICE_COMMANDS.get(lowered, text)

    def _auto_punctuate(self, text: str) -> str:
        if not text or text.endswith(("\n", ".", ",", "!", "?")):
            return text
        if len(text.split()) >= 8:
            return f"{text}."
        return text
