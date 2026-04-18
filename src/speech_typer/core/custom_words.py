from __future__ import annotations

import math
import wave
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

from speech_typer.core.config_store import ConfigStore


@dataclass
class CustomWordEntry:
    target: str
    audio_samples: list[str] = field(default_factory=list)


@dataclass
class DetectionMatch:
    target: str
    confidence: float


def normalize_phrase(value: str) -> str:
    filtered = "".join(char.lower() if char.isalnum() or char.isspace() else " " for char in value or "")
    return " ".join(filtered.split())


def relativize_audio_paths(paths: Iterable[str], base_dir: Path) -> list[str]:
    relative_paths: list[str] = []
    for item in paths:
        value = str(item).strip()
        if not value:
            continue
        path = Path(value)
        try:
            relative_paths.append(str(path.relative_to(base_dir)))
        except ValueError:
            relative_paths.append(path.name)
    return relative_paths


def preprocess_audio_file(path: Path, sample_rate: int = 16000) -> bool:
    if not path.exists():
        return False
    try:
        with wave.open(str(path), "rb") as handle:
            if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                return False
            frame_rate = handle.getframerate()
            raw = handle.readframes(handle.getnframes())
    except (wave.Error, OSError):
        return False

    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    cleaned = _clean_audio_samples(samples, frame_rate, sample_rate)
    if cleaned is None:
        return False

    try:
        with wave.open(str(path), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(cleaned.astype(np.int16).tobytes())
    except (wave.Error, OSError):
        return False
    return True


def _clean_audio_samples(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray | None:
    if samples.size == 0:
        return None

    if source_rate != target_rate and source_rate > 0:
        target_size = int(samples.size * target_rate / source_rate)
        if target_size <= 0:
            return None
        samples = np.interp(
            np.linspace(0, samples.size - 1, target_size),
            np.arange(samples.size),
            samples,
        ).astype(np.float32)

    amplitude = np.abs(samples)
    if amplitude.size == 0 or float(amplitude.max()) < 120.0:
        return None

    trim_threshold = max(float(amplitude.max()) * 0.12, 160.0)
    active = np.flatnonzero(amplitude >= trim_threshold)
    if active.size == 0:
        return None

    padding = int(target_rate * 0.04)
    start = max(int(active[0]) - padding, 0)
    end = min(int(active[-1]) + padding, samples.size - 1)
    return samples[start:end + 1]


class AudioTemplateEngine:
    def __init__(self, sample_rate: int = 16000) -> None:
        self.sample_rate = sample_rate
        self.frame_size = 400
        self.hop_size = 160
        self.coefficient_count = 13
        self.filter_count = 26
        self.max_frames = 96

    def features_wav(self, path: Path) -> np.ndarray | None:
        if not path.exists():
            return None
        try:
            with wave.open(str(path), "rb") as handle:
                if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
                    return None
                frame_rate = handle.getframerate()
                raw = handle.readframes(handle.getnframes())
        except (wave.Error, OSError):
            return None

        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        return self.features_from_samples(samples, frame_rate)

    def features_bytes(self, audio_bytes: bytes) -> np.ndarray | None:
        if not audio_bytes:
            return None
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        return self.features_from_samples(samples, self.sample_rate)

    def has_speech(self, audio_bytes: bytes) -> bool:
        if not audio_bytes:
            return False
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
        if samples.size < self.frame_size * 3:
            return False

        amplitude = np.abs(samples - np.mean(samples))
        peak = float(amplitude.max()) if amplitude.size else 0.0
        if peak < 850.0:
            return False

        rms = float(np.sqrt(np.mean(samples ** 2)))
        if rms < 170.0:
            return False

        active_threshold = max(peak * 0.18, 260.0)
        active_ratio = float(np.count_nonzero(amplitude >= active_threshold)) / float(max(amplitude.size, 1))
        if active_ratio < 0.08:
            return False

        duration_seconds = samples.size / float(self.sample_rate)
        return duration_seconds >= 0.2

    def dtw_similarity(self, first: np.ndarray | None, second: np.ndarray | None) -> float:
        if first is None or second is None or first.size == 0 or second.size == 0:
            return 0.0

        cost = self._dtw_cost(first, second)
        if not math.isfinite(cost):
            return 0.0
        return max(0.0, min(1.0, 1.0 / (1.0 + cost * 0.85)))

    def features_from_samples(self, samples: np.ndarray, sample_rate: int) -> np.ndarray | None:
        if samples.size < self.frame_size:
            return None

        if sample_rate != self.sample_rate and sample_rate > 0:
            target_size = int(samples.size * self.sample_rate / sample_rate)
            if target_size < self.frame_size:
                return None
            samples = np.interp(
                np.linspace(0, samples.size - 1, target_size),
                np.arange(samples.size),
                samples,
            ).astype(np.float32)

        trimmed = self._trim_silence(samples)
        if trimmed.size < self.frame_size:
            return None

        normalized = trimmed - np.mean(trimmed)
        peak = max(float(np.max(np.abs(normalized))), 1.0)
        normalized = normalized / peak

        spectrogram = self._power_spectrogram(normalized)
        if spectrogram.size == 0:
            return None

        mel = self._mel_filterbank(spectrogram.shape[1])
        mel_energy = np.maximum(spectrogram @ mel.T, 1e-10)
        log_mel = np.log(mel_energy)
        mfcc = self._dct(log_mel, self.coefficient_count)

        delta = self._delta(mfcc)
        delta_delta = self._delta(delta)
        features = np.hstack((mfcc, delta, delta_delta)).astype(np.float32)

        if features.shape[0] > self.max_frames:
            step = np.linspace(0, features.shape[0] - 1, self.max_frames).astype(np.int32)
            features = features[step]

        features -= features.mean(axis=0, keepdims=True)
        std = features.std(axis=0, keepdims=True)
        std[std < 1e-5] = 1.0
        return features / std

    def _trim_silence(self, samples: np.ndarray) -> np.ndarray:
        amplitude = np.abs(samples)
        threshold = max(float(amplitude.max()) * 0.12, 180.0)
        active = np.flatnonzero(amplitude >= threshold)
        if active.size == 0:
            return samples
        padding = int(self.sample_rate * 0.05)
        start = max(int(active[0]) - padding, 0)
        end = min(int(active[-1]) + padding, samples.size - 1)
        return samples[start:end + 1]

    def _power_spectrogram(self, samples: np.ndarray) -> np.ndarray:
        window = np.hanning(self.frame_size).astype(np.float32)
        frames: list[np.ndarray] = []
        for start in range(0, samples.size - self.frame_size + 1, self.hop_size):
            frame = samples[start:start + self.frame_size] * window
            spectrum = np.fft.rfft(frame)
            frames.append((np.abs(spectrum) ** 2).astype(np.float32))
        if not frames:
            return np.empty((0, self.frame_size // 2 + 1), dtype=np.float32)
        return np.vstack(frames)

    def _mel_filterbank(self, spectrum_size: int) -> np.ndarray:
        low_mel = self._hz_to_mel(20.0)
        high_mel = self._hz_to_mel(self.sample_rate / 2.0)
        mel_points = np.linspace(low_mel, high_mel, self.filter_count + 2)
        hz_points = self._mel_to_hz(mel_points)
        bins = np.floor((self.frame_size + 1) * hz_points / self.sample_rate).astype(int)
        bins = np.clip(bins, 0, spectrum_size - 1)

        filters = np.zeros((self.filter_count, spectrum_size), dtype=np.float32)
        for index in range(self.filter_count):
            left, center, right = bins[index], bins[index + 1], bins[index + 2]
            if center <= left:
                center = min(left + 1, spectrum_size - 1)
            if right <= center:
                right = min(center + 1, spectrum_size - 1)
            if center > left:
                filters[index, left:center] = np.linspace(0.0, 1.0, center - left, endpoint=False)
            if right > center:
                filters[index, center:right] = np.linspace(1.0, 0.0, right - center, endpoint=False)
        return filters

    def _dct(self, values: np.ndarray, coefficient_count: int) -> np.ndarray:
        frame_count, input_count = values.shape
        output = np.empty((frame_count, coefficient_count), dtype=np.float32)
        indices = np.arange(input_count, dtype=np.float32)
        scale = math.pi / input_count
        for coeff in range(coefficient_count):
            basis = np.cos((indices + 0.5) * coeff * scale)
            output[:, coeff] = values @ basis
        return output

    def _delta(self, features: np.ndarray) -> np.ndarray:
        if features.shape[0] < 3:
            return np.zeros_like(features)
        padded = np.pad(features, ((1, 1), (0, 0)), mode="edge")
        return (padded[2:] - padded[:-2]) * 0.5

    def _dtw_cost(self, first: np.ndarray, second: np.ndarray) -> float:
        rows, cols = first.shape[0], second.shape[0]
        costs = np.full((rows + 1, cols + 1), np.inf, dtype=np.float32)
        costs[0, 0] = 0.0

        for row in range(1, rows + 1):
            row_feature = first[row - 1]
            col_start = max(1, row - 24)
            col_end = min(cols + 1, row + 24)
            for col in range(col_start, col_end):
                distance = float(np.linalg.norm(row_feature - second[col - 1]))
                costs[row, col] = distance + min(
                    costs[row - 1, col],
                    costs[row, col - 1],
                    costs[row - 1, col - 1],
                )

        return float(costs[rows, cols] / max(rows + cols, 1))

    def _hz_to_mel(self, hz: float) -> float:
        return 2595.0 * math.log10(1.0 + hz / 700.0)

    def _mel_to_hz(self, mel: np.ndarray) -> np.ndarray:
        return 700.0 * (10 ** (mel / 2595.0) - 1.0)


class CustomWordsManager:
    def __init__(self, store: ConfigStore) -> None:
        self.store = store
        self.entries: list[CustomWordEntry] = []
        self.template_engine = AudioTemplateEngine()
        self._templates: dict[str, list[np.ndarray]] = {}
        self.confidence_level = 55
        self.reload()

    def reload(self) -> None:
        payload = self.store.load_custom_words_payload()
        entries: list[CustomWordEntry] = []
        for item in payload.get("words", []):
            target = str(item.get("target", "")).strip()
            if not target:
                continue
            audio_samples = [str(sample).strip() for sample in item.get("audio_samples", []) if str(sample).strip()]
            entries.append(CustomWordEntry(target=target, audio_samples=audio_samples))
        self.entries = sorted(entries, key=lambda item: item.target.lower())
        self._rebuild_templates()

    def save(self) -> None:
        payload = {"words": [asdict(entry) for entry in self.entries]}
        self.store.save_custom_words_payload(payload)
        self.reload()

    def list_entries(self) -> list[CustomWordEntry]:
        return list(self.entries)

    def list_targets(self) -> list[str]:
        return [entry.target for entry in self.entries if entry.audio_samples]

    def set_confidence_level(self, value: int) -> None:
        self.confidence_level = max(0, min(100, int(value)))

    def upsert(self, entry: CustomWordEntry, original_target: str | None = None) -> None:
        normalized_original = normalize_phrase(original_target or entry.target)
        replaced = False
        next_entries: list[CustomWordEntry] = []

        for existing in self.entries:
            if normalize_phrase(existing.target) == normalized_original and not replaced:
                next_entries.append(entry)
                replaced = True
            else:
                next_entries.append(existing)

        if not replaced:
            next_entries.append(entry)

        self.entries = sorted(next_entries, key=lambda item: item.target.lower())
        self.save()

    def delete(self, target: str) -> None:
        normalized_target = normalize_phrase(target)
        self.entries = [entry for entry in self.entries if normalize_phrase(entry.target) != normalized_target]
        self.save()

    def filter_entries(self, query: str) -> list[CustomWordEntry]:
        normalized_query = normalize_phrase(query)
        if not normalized_query:
            return self.list_entries()
        return [entry for entry in self.entries if normalized_query in normalize_phrase(entry.target)]

    def detect_in_audio(self, audio_bytes: bytes) -> DetectionMatch | None:
        if not self.template_engine.has_speech(audio_bytes):
            return None
        segment_features = self.template_engine.features_bytes(audio_bytes)
        if segment_features is None:
            return None

        best_target = ""
        best_confidence = 0.0

        for entry in self.entries:
            target_key = normalize_phrase(entry.target)
            templates = self._templates.get(target_key, [])
            if not templates:
                continue

            scores = [self.template_engine.dtw_similarity(segment_features, template) for template in templates]
            confidence = self._score_similarity(scores)
            if confidence > best_confidence:
                best_target = entry.target
                best_confidence = confidence

        if not best_target:
            return None
        return DetectionMatch(target=best_target, confidence=best_confidence)

    def apply_to_segment(self, text: str, audio_bytes: bytes) -> str:
        cleaned = normalize_phrase(text)
        if not cleaned:
            return ""

        detection = self.detect_in_audio(audio_bytes)
        if detection is None:
            return text.strip()

        target_normalized = normalize_phrase(detection.target)
        if target_normalized in cleaned:
            return text.strip()

        phonetic_similarity = self._best_phonetic_similarity(cleaned, detection.target)
        strongest_threshold, moderate_threshold, replacement_threshold = self._confidence_thresholds()

        if detection.confidence < moderate_threshold:
            return text.strip()
        if phonetic_similarity < replacement_threshold:
            return text.strip()

        tokens = text.split()
        target_tokens = detection.target.split()
        if detection.confidence >= strongest_threshold and len(tokens) <= max(len(target_tokens) + 1, 4):
            return detection.target

        replacement = self._replace_best_span(text, detection.target, require_similarity=replacement_threshold)
        return replacement if replacement is not None else text.strip()

    def _replace_best_span(self, text: str, target: str, require_similarity: float) -> str | None:
        tokens = text.split()
        target_tokens = target.split()
        target_signature = self._phrase_signature(target)
        best_range: tuple[int, int] | None = None
        best_score = 0.0

        min_length = max(1, len(target_tokens) - 1)
        max_length = min(len(tokens), len(target_tokens) + 1)

        for length in range(min_length, max_length + 1):
            for start in range(0, len(tokens) - length + 1):
                candidate = " ".join(tokens[start:start + length])
                score = self._signature_similarity(target_signature, self._phrase_signature(candidate))
                if score > best_score:
                    best_score = score
                    best_range = (start, start + length)

        if best_range is None or best_score < require_similarity:
            return None

        start, end = best_range
        return " ".join(tokens[:start] + [target] + tokens[end:])

    def _best_phonetic_similarity(self, text: str, target: str) -> float:
        tokens = text.split()
        target_tokens = target.split()
        target_signature = self._phrase_signature(target)
        best_score = 0.0

        min_length = max(1, len(target_tokens) - 1)
        max_length = min(len(tokens), len(target_tokens) + 1)
        for length in range(min_length, max_length + 1):
            for start in range(0, len(tokens) - length + 1):
                candidate = " ".join(tokens[start:start + length])
                score = self._signature_similarity(target_signature, self._phrase_signature(candidate))
                best_score = max(best_score, score)
        return best_score

    def _phrase_signature(self, text: str) -> str:
        words = [self._word_signature(word) for word in normalize_phrase(text).split()]
        return " ".join(filter(None, words))

    def _word_signature(self, word: str) -> str:
        if not word:
            return ""
        chars = [char for char in word.lower() if char.isalpha() or char.isdigit()]
        if not chars:
            return ""
        head = chars[0]
        tail = [char for char in chars[1:] if char not in "aeiouy"]
        collapsed: list[str] = []
        for char in tail:
            if not collapsed or collapsed[-1] != char:
                collapsed.append(char)
        return head + "".join(collapsed[:6])

    def _signature_similarity(self, first: str, second: str) -> float:
        if not first or not second:
            return 0.0
        first_tokens = first.split()
        second_tokens = second.split()
        total = 0.0
        comparisons = 0
        for left, right in zip(first_tokens, second_tokens):
            total += self._normalized_edit_similarity(left, right)
            comparisons += 1
        if comparisons == 0:
            return 0.0
        length_penalty = abs(len(first_tokens) - len(second_tokens)) * 0.08
        return max(total / comparisons - length_penalty, 0.0)

    def _normalized_edit_similarity(self, first: str, second: str) -> float:
        distance = self._levenshtein_distance(first, second)
        scale = max(len(first), len(second), 1)
        return 1.0 - (distance / scale)

    def _levenshtein_distance(self, first: str, second: str) -> int:
        if first == second:
            return 0
        if not first:
            return len(second)
        if not second:
            return len(first)

        previous = list(range(len(second) + 1))
        for index, left in enumerate(first, start=1):
            current = [index]
            for sub_index, right in enumerate(second, start=1):
                insert_cost = current[sub_index - 1] + 1
                delete_cost = previous[sub_index] + 1
                replace_cost = previous[sub_index - 1] + (0 if left == right else 1)
                current.append(min(insert_cost, delete_cost, replace_cost))
            previous = current
        return previous[-1]

    def _score_similarity(self, scores: list[float]) -> float:
        if not scores:
            return 0.0
        best = max(scores)
        average = sum(scores) / len(scores)
        return max(0.0, min(1.0, best * 0.82 + average * 0.18))

    def _confidence_thresholds(self) -> tuple[float, float, float]:
        delta = (self.confidence_level - 55) / 100.0
        strongest = min(max(0.74 + delta * 0.26, 0.62), 0.92)
        moderate = min(max(0.62 + delta * 0.22, 0.5), strongest - 0.04)
        replacement = min(max(0.58 + delta * 0.28, 0.46), 0.88)
        return strongest, moderate, replacement

    def _rebuild_templates(self) -> None:
        sample_dir = self.store.ensure_custom_audio_dir()
        templates: dict[str, list[np.ndarray]] = {}

        for entry in self.entries:
            target_key = normalize_phrase(entry.target)
            entry_templates: list[np.ndarray] = []
            for sample_name in entry.audio_samples:
                sample_path = sample_dir / sample_name
                template = self.template_engine.features_wav(sample_path)
                if template is not None:
                    entry_templates.append(template)
            if entry_templates:
                templates[target_key] = entry_templates

        self._templates = templates
