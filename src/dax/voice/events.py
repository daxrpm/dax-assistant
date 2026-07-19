"""Audio metering — turn raw capture chunks into compact waveform frames.

The transport half (``VoiceEventHub``, event types) lives in
:mod:`dax.core.voice_events` so it stays importable without the optional
``voice`` extra. This module is the numpy-dependent half: it reduces an audio
chunk to something small enough to push over a WebSocket many times a second.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from dax.core.voice_events import LevelSource, VoiceEvent, VoiceEventType

if TYPE_CHECKING:
    from dax.core.voice_events import VoiceEventHub

# Level frames are emitted per captured chunk (80 ms). Each chunk is split into
# this many sub-windows so the client receives ~50 envelope points per second —
# enough for the UI to interpolate a smooth 60 fps waveform from sparse data.
SUB_WINDOWS = 4

# Spectrum resolution sent to the client. Eight logarithmically spaced bands is
# the sweet spot: enough structure to look alive, small enough that a frame
# stays well under the size where JSON encoding would show up in a profile.
SPECTRUM_BANDS = 8


def compute_level_frame(
    chunk: np.ndarray,
    source: LevelSource = LevelSource.INPUT,
) -> dict[str, Any]:
    """Reduce a raw audio chunk to a compact envelope + spectrum frame.

    Args:
        chunk: Mono ``int16`` (or float) samples straight off the capture queue.
        source: Whether this is microphone input or TTS output.

    Returns:
        A JSON-ready dict with an ``rms`` envelope of :data:`SUB_WINDOWS`
        points, a ``peak``, and a :data:`SPECTRUM_BANDS`-band ``spectrum``.
        All values are normalized to 0.0-1.0.
    """
    raw = np.asarray(chunk)
    if raw.size == 0:
        return {
            "source": str(source),
            "rms": [0.0] * SUB_WINDOWS,
            "peak": 0.0,
            "spectrum": [0.0] * SPECTRUM_BANDS,
        }

    samples = raw.astype(np.float32)
    # int16 capture arrives unnormalized; scale to -1.0..1.0 so the UI never
    # has to know the capture dtype.
    if np.issubdtype(raw.dtype, np.integer):
        samples = samples / 32768.0

    # Envelope: split the chunk into equal sub-windows and take RMS of each.
    windows = np.array_split(samples, SUB_WINDOWS)
    rms = [float(np.sqrt(np.mean(np.square(w)))) if w.size else 0.0 for w in windows]
    peak = float(np.max(np.abs(samples)))

    # Spectrum: magnitude of the real FFT, folded into logarithmic bands so low
    # frequencies (where speech energy lives) get the resolution they deserve.
    magnitudes = np.abs(np.fft.rfft(samples * np.hanning(samples.size)))
    if magnitudes.size > 1:
        edges = np.clip(
            np.geomspace(1, magnitudes.size, SPECTRUM_BANDS + 1).astype(int),
            1,
            magnitudes.size,
        )
        bands = [
            float(np.mean(magnitudes[edges[i]: edges[i + 1]]))
            if edges[i + 1] > edges[i]
            else 0.0
            for i in range(SPECTRUM_BANDS)
        ]
        # Normalized against the frame's own maximum: the UI wants relative
        # shape, and absolute FFT magnitude depends on mic gain anyway.
        ceiling = max(bands) or 1.0
        spectrum = [min(1.0, b / ceiling) for b in bands]
    else:
        spectrum = [0.0] * SPECTRUM_BANDS

    return {
        "source": str(source),
        "rms": [min(1.0, v) for v in rms],
        "peak": min(1.0, peak),
        "spectrum": spectrum,
    }


def emit_level(hub: VoiceEventHub, chunk: np.ndarray, source: LevelSource) -> None:
    """Emit a level frame for *chunk* on *hub*. No-op with no subscribers.

    The subscriber check happens here rather than at the call site so the
    pipeline never pays for the FFT on an unwatched backend.
    """
    if not hub.has_subscribers:
        return
    hub.emit(
        VoiceEvent(type=VoiceEventType.LEVEL, data=compute_level_frame(chunk, source))
    )
