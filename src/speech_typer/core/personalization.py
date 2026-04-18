from __future__ import annotations

from difflib import get_close_matches

from speech_typer.core.config_store import ConfigStore


class PersonalizationStore:
    def __init__(self, config_store: ConfigStore) -> None:
        self.config_store = config_store
        self.corrections = config_store.load_corrections()
        self.custom_words = config_store.load_custom_words()
        self.training_sessions = config_store.load_training_sessions()

    def reload(self) -> None:
        self.corrections = self.config_store.load_corrections()
        self.custom_words = self.config_store.load_custom_words()
        self.training_sessions = self.config_store.load_training_sessions()

    def add_custom_word(self, word: str) -> None:
        words = list(self.custom_words)
        words.append(word)
        self.config_store.save_custom_words(words)
        self.custom_words = self.config_store.load_custom_words()

    def add_correction(self, spoken: str, corrected: str) -> None:
        normalized_key = spoken.strip().lower()
        if not normalized_key:
            return
        self.corrections[normalized_key] = corrected.strip()
        self.config_store.save_corrections(self.corrections)

    def add_training_session(self, session: dict) -> None:
        sessions = self.training_sessions
        sessions.append(session)
        self.config_store.save_training_sessions(sessions)
        self.training_sessions = sessions

    def apply(self, text: str) -> str:
        words = text.split()
        updated: list[str] = []
        vocabulary_lookup = {word.lower(): word for word in self.custom_words}

        for word in words:
            cleaned = word.strip().lower()
            if cleaned in self.corrections:
                updated.append(self.corrections[cleaned])
                continue

            if cleaned in vocabulary_lookup:
                updated.append(vocabulary_lookup[cleaned])
                continue

            close_match = get_close_matches(cleaned, vocabulary_lookup.keys(), n=1, cutoff=0.88)
            if close_match:
                updated.append(vocabulary_lookup[close_match[0]])
                continue

            updated.append(word)

        return " ".join(updated)
