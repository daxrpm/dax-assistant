"""Download voice models for Dax Assistant.

Downloads Piper TTS voices and OpenWakeWord models into the local
``models/`` directory. Safe to run multiple times — already-downloaded
models are skipped.

Usage::

    python scripts/download_models.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MODELS_DIR = Path("models")

PIPER_VOICES: dict[str, dict[str, str]] = {
    "es": {
        "name": "es_ES-davefx-medium",
        "url": (
            "https://huggingface.co/rhasspy/piper-voices"
            "/resolve/main/es/es_ES/davefx/medium"
        ),
    },
    "en": {
        "name": "en_US-lessac-medium",
        "url": (
            "https://huggingface.co/rhasspy/piper-voices"
            "/resolve/main/en/en_US/lessac/medium"
        ),
    },
}


def download_piper_voices() -> None:
    """Download Piper ONNX voice models from Hugging Face."""
    piper_dir = MODELS_DIR / "piper"
    piper_dir.mkdir(parents=True, exist_ok=True)

    for lang, info in PIPER_VOICES.items():
        onnx_path = piper_dir / f"{info['name']}.onnx"

        if onnx_path.exists():
            print(f"[{lang}] {info['name']} already downloaded")
            continue

        print(f"[{lang}] Downloading {info['name']}...")
        for suffix in (".onnx", ".onnx.json"):
            url = f"{info['url']}/{info['name']}{suffix}"
            dest = piper_dir / f"{info['name']}{suffix}"
            result = subprocess.run(
                ["wget", "-q", "-O", str(dest), url],
                check=False,
            )
            if result.returncode != 0:
                print(f"[{lang}] ERROR: Failed to download {url}", file=sys.stderr)
                return
        print(f"[{lang}] Done")


def download_wake_word() -> None:
    """Download OpenWakeWord pretrained models."""
    import openwakeword.utils

    print("Downloading OpenWakeWord models...")
    openwakeword.utils.download_models()
    print("Done")


if __name__ == "__main__":
    download_piper_voices()
    download_wake_word()
    print("\nAll models downloaded!")
