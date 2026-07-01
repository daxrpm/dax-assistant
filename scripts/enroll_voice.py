"""Enroll the owner's voice for speaker verification (Voice ID).

Records a few short samples from the default microphone, builds a voice
embedding, and saves it to ``<models>/voice_profile.npy``. Once enrolled and
``[voice].speaker_verification = true`` is set, Dax ignores commands from
other voices.

Usage::

    ~/.local/bin/uv run python scripts/enroll_voice.py
    ~/.local/bin/uv run python scripts/enroll_voice.py --samples 4 --seconds 4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd

from dax.voice.speaker import SpeakerVerifier

SAMPLE_RATE = 16_000
PHRASES = [
    "Hola, soy yo, este es mi asistente personal.",
    "Hey Jarvis, qué hora es y qué tengo agendado hoy.",
    "Reproduce música y sube el volumen, por favor.",
    "This is my voice, please remember it.",
]


def _record(seconds: float) -> np.ndarray:
    audio = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return audio[:, 0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Enroll your voice for Voice ID")
    parser.add_argument("--samples", type=int, default=3, help="number of clips")
    parser.add_argument("--seconds", type=float, default=4.0, help="seconds per clip")
    parser.add_argument(
        "--models", default="models", help="models directory (profile is saved here)"
    )
    args = parser.parse_args()

    profile = str(Path(args.models) / "voice_profile.npy")
    verifier = SpeakerVerifier(profile_path=profile)
    verifier.start()
    if verifier.embed(np.zeros(SAMPLE_RATE, dtype=np.float32)) is None:
        print("ERROR: speaker encoder unavailable (install the 'voice' extra).")
        return 1

    print(f"Recording {args.samples} clips of {args.seconds:.0f}s each.\n")
    clips: list[np.ndarray] = []
    for i in range(args.samples):
        phrase = PHRASES[i % len(PHRASES)]
        input(f"[{i + 1}/{args.samples}] Press Enter, then say: \"{phrase}\"")
        print("  recording…")
        clips.append(_record(args.seconds))
        print("  done.\n")

    if verifier.enroll(clips):
        print(f"Voice profile saved → {profile}")
        print("Set [voice].speaker_verification = true to enable Voice ID.")
        return 0
    print("ERROR: enrollment failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
