"""Speaker verification (Voice ID) via Resemblyzer.

Optional, Alexa-style "only respond to the owner" gate. After the wake word
fires we embed the captured utterance and compare it (cosine similarity) to a
pre-enrolled owner profile; commands from other voices are ignored.

Design choices:
- **Fail open.** If the encoder can't load or no profile is enrolled, every
  utterance is accepted — the feature never silently bricks the assistant.
- **Lightweight.** Resemblyzer is a small pretrained model; its embeddings are
  unit-normalised so a dot product is the cosine similarity.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from resemblyzer import VoiceEncoder

logger = logging.getLogger(__name__)

# Resemblyzer expects 16 kHz mono float audio — same as our capture rate.
_SAMPLE_RATE = 16_000


class SpeakerVerifier:
    """Verify that an utterance matches the enrolled owner's voice."""

    def __init__(self, profile_path: str, threshold: float = 0.65) -> None:
        self._profile_path = Path(profile_path).expanduser()
        self._threshold = threshold
        self._encoder: VoiceEncoder | None = None
        self._reference: np.ndarray | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def start(self) -> None:
        """Load the encoder and the enrolled profile (best-effort)."""
        try:
            from resemblyzer import VoiceEncoder

            self._encoder = VoiceEncoder(verbose=False)
        except Exception:
            logger.warning(
                "Speaker verification unavailable (resemblyzer failed to load) "
                "— accepting all voices",
                exc_info=True,
            )
            self._encoder = None
            return

        if self._profile_path.is_file():
            try:
                self._reference = np.load(self._profile_path)
                logger.info("Loaded voice profile from %s", self._profile_path)
            except Exception:
                logger.warning("Failed to read voice profile", exc_info=True)
                self._reference = None
        else:
            logger.info(
                "No voice profile enrolled at %s — accepting all voices",
                self._profile_path,
            )

    def stop(self) -> None:
        self._encoder = None
        self._reference = None

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def active(self) -> bool:
        """True only when both the encoder and an enrolled profile are ready."""
        return self._encoder is not None and self._reference is not None

    # ── Public API ─────────────────────────────────────────────────────────

    def embed(self, audio: np.ndarray) -> np.ndarray | None:
        """Compute a voice embedding for *audio* (float32, 16 kHz mono)."""
        if self._encoder is None:
            return None
        try:
            from resemblyzer import preprocess_wav

            wav = preprocess_wav(audio.astype(np.float32), source_sr=_SAMPLE_RATE)
            return np.asarray(self._encoder.embed_utterance(wav), dtype=np.float32)
        except Exception:
            logger.warning("Failed to embed utterance", exc_info=True)
            return None

    def verify(self, audio: np.ndarray) -> bool:
        """Return True if *audio* matches the owner (or if verification is off).

        Fails open: with no encoder or no enrolled profile, always True.
        """
        if not self.active:
            return True
        embedding = self.embed(audio)
        if embedding is None or self._reference is None:
            return True
        similarity = float(np.dot(embedding, self._reference))
        accepted = similarity >= self._threshold
        logger.info(
            "Speaker similarity %.3f (threshold %.2f) → %s",
            similarity, self._threshold, "accept" if accepted else "reject",
        )
        return accepted

    def enroll(self, samples: list[np.ndarray]) -> bool:
        """Build and persist an owner profile from one or more recordings.

        The reference embedding is the mean of the per-sample embeddings,
        re-normalised to unit length. Returns True on success.
        """
        if self._encoder is None:
            logger.error("Cannot enroll: encoder not loaded")
            return False
        embeddings = [e for s in samples if (e := self.embed(s)) is not None]
        if not embeddings:
            logger.error("Cannot enroll: no usable audio")
            return False
        mean = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(mean)
        reference = (mean / norm) if norm > 0 else mean
        self._profile_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(self._profile_path, reference.astype(np.float32))
        self._reference = reference.astype(np.float32)
        logger.info("Enrolled voice profile → %s", self._profile_path)
        return True
