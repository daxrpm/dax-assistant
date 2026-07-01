"""Download voice models for Dax Assistant.

Fetches everything the voice pipeline needs into the local ``models/`` dir:
- the Kokoro neural TTS model + voices (default engine),
- Piper TTS voices (fast fallback) for the chosen language(s),
- the faster-whisper STT model (default ``large-v3-turbo``),
- the OpenWakeWord wake-word models.

Safe to re-run — already-downloaded files are skipped.

Usage::

    python scripts/download_models.py                 # both languages, turbo STT
    python scripts/download_models.py --language es    # Spanish only
    python scripts/download_models.py --stt-model small --no-kokoro
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
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

# Kokoro ONNX model + combined voice bank (v1.0).
_KOKORO_BASE = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
)
KOKORO_FILES = {
    "kokoro-v1.0.onnx": f"{_KOKORO_BASE}/kokoro-v1.0.onnx",
    "voices-v1.0.bin": f"{_KOKORO_BASE}/voices-v1.0.bin",
}


def _download(url: str, dest: Path) -> bool:
    """Download *url* to *dest*; return True on success."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        urllib.request.urlretrieve(url, dest)
    except Exception as exc:  # pragma: no cover - network
        print(f"  ERROR downloading {url}: {exc}", file=sys.stderr)
        if dest.exists():
            dest.unlink()
        return False
    return True


def download_kokoro() -> None:
    """Download the Kokoro neural TTS model and voice bank."""
    kokoro_dir = MODELS_DIR / "kokoro"
    for name, url in KOKORO_FILES.items():
        dest = kokoro_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[kokoro] {name} already downloaded")
            continue
        print(f"[kokoro] Downloading {name} (this can take a while)…")
        if _download(url, dest):
            print(f"[kokoro] {name} done")


def download_piper_voices(languages: list[str]) -> None:
    """Download Piper ONNX voice models from Hugging Face."""
    piper_dir = MODELS_DIR / "piper"
    for lang in languages:
        info = PIPER_VOICES[lang]
        onnx_path = piper_dir / f"{info['name']}.onnx"
        if onnx_path.exists():
            print(f"[{lang}] {info['name']} already downloaded")
            continue
        print(f"[{lang}] Downloading {info['name']}…")
        ok = True
        for suffix in (".onnx", ".onnx.json"):
            url = f"{info['url']}/{info['name']}{suffix}"
            ok = _download(url, piper_dir / f"{info['name']}{suffix}") and ok
        if ok:
            print(f"[{lang}] Done")


def download_whisper(model: str) -> None:
    """Pre-download the faster-whisper STT model (multilingual)."""
    print(f"[stt] Caching faster-whisper '{model}' (large download)…")
    try:
        from faster_whisper import WhisperModel

        WhisperModel(model, device="cpu", compute_type="int8")
        print(f"[stt] '{model}' ready")
    except Exception as exc:  # pragma: no cover - network/runtime
        print(f"[stt] ERROR caching '{model}': {exc}", file=sys.stderr)


def download_wake_word() -> None:
    """Download OpenWakeWord pretrained models."""
    print("[wake] Downloading OpenWakeWord models…")
    try:
        import openwakeword.utils

        openwakeword.utils.download_models()
        print("[wake] Done")
    except Exception as exc:  # pragma: no cover
        print(f"[wake] ERROR: {exc}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Dax voice models")
    parser.add_argument(
        "--language", choices=["es", "en", "both"], default="both",
        help="which language voices to fetch (STT model is multilingual)",
    )
    parser.add_argument(
        "--stt-model", default="large-v3-turbo",
        help="faster-whisper model to pre-cache",
    )
    parser.add_argument("--no-kokoro", action="store_true", help="skip Kokoro TTS")
    parser.add_argument("--no-stt", action="store_true", help="skip STT pre-cache")
    args = parser.parse_args()

    languages = ["es", "en"] if args.language == "both" else [args.language]

    if not args.no_kokoro:
        download_kokoro()
    download_piper_voices(languages)
    if not args.no_stt:
        download_whisper(args.stt_model)
    download_wake_word()

    print("\nAll models downloaded!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
