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
import os
import shutil
import sys
import urllib.request
from pathlib import Path

MODELS_DIR = Path(os.environ.get("DAX_MODELS_DIR", "models"))

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
    temporary = dest.with_suffix(f"{dest.suffix}.part")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Dax-Installer/1"})
        with (
            urllib.request.urlopen(request, timeout=60) as response,
            temporary.open("wb") as output,
        ):
            shutil.copyfileobj(response, output)
            output.flush()
            os.fsync(output.fileno())
        if temporary.stat().st_size == 0:
            raise OSError("downloaded file is empty")
        os.replace(temporary, dest)
    except Exception as exc:  # pragma: no cover - network
        print(f"  ERROR downloading {url}: {exc}", file=sys.stderr)
        temporary.unlink(missing_ok=True)
        return False
    return True


def download_kokoro() -> bool:
    """Download the Kokoro neural TTS model and voice bank."""
    kokoro_dir = MODELS_DIR / "kokoro"
    success = True
    for name, url in KOKORO_FILES.items():
        dest = kokoro_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            print(f"[kokoro] {name} already downloaded")
            continue
        print(f"[kokoro] Downloading {name} (this can take a while)…")
        if _download(url, dest):
            print(f"[kokoro] {name} done")
        else:
            success = False
    return success


def download_piper_voices(languages: list[str]) -> bool:
    """Download Piper ONNX voice models from Hugging Face."""
    piper_dir = MODELS_DIR / "piper"
    success = True
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
        success = success and ok
    return success


def download_whisper(model: str) -> bool:
    """Pre-download the faster-whisper STT model (multilingual)."""
    print(f"[stt] Caching faster-whisper '{model}' (large download)…")
    try:
        from faster_whisper import WhisperModel

        WhisperModel(model, device="cpu", compute_type="int8")
        print(f"[stt] '{model}' ready")
        return True
    except Exception as exc:  # pragma: no cover - network/runtime
        print(f"[stt] ERROR caching '{model}': {exc}", file=sys.stderr)
        return False


def download_wake_word() -> bool:
    """Download OpenWakeWord pretrained models."""
    print("[wake] Downloading OpenWakeWord models…")
    try:
        import openwakeword.utils

        openwakeword.utils.download_models()
        print("[wake] Done")
        return True
    except Exception as exc:  # pragma: no cover
        print(f"[wake] ERROR: {exc}", file=sys.stderr)
        return False


def main() -> int:
    global MODELS_DIR
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
    parser.add_argument(
        "--models-dir", type=Path, default=MODELS_DIR,
        help="destination for Dax-managed model files",
    )
    args = parser.parse_args()
    MODELS_DIR = args.models_dir.expanduser().resolve()

    languages = ["es", "en"] if args.language == "both" else [args.language]

    results: list[bool] = []
    if not args.no_kokoro:
        results.append(download_kokoro())
    results.append(download_piper_voices(languages))
    if not args.no_stt:
        results.append(download_whisper(args.stt_model))
    results.append(download_wake_word())

    if all(results):
        print("\nAll models downloaded!")
        return 0
    print("\nOne or more required model downloads failed.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
