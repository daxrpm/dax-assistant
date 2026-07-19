# Voice WebSocket protocol

`/ws/voice` is an authenticated, bidirectional WebSocket. Authentication is the
same as the other sockets: session cookie, `?token=`, or bearer header.
Server-to-client JSON events are `state`, `level`, `transcript`, `speech`,
`speaker`, and `error`.

Each `level` event preserves `source: input|output` and carries RMS, peak, and
spectrum data. Desktop renderers keep those sources separate: input represents
microphone energy and output represents server-side TTS playback energy. Level
frames are high-frequency presentation data and must reach the Canvas sink
imperatively rather than through React state. The complete desktop rendering
invariants live in [`desktop-architecture.md`](desktop-architecture.md).

`state.data` includes `state`, `conversation_id`, and `session_expires_at`.
`conversation_id` is the voice `session_id` used as the agent conversation key;
consecutive turns reuse it until the configured inactivity TTL expires or an
explicit farewell ends the session. `session_expires_at` is an absolute Unix
timestamp, or `null` when there is no active session, so clients do not need to
estimate expiry.

`transcript` is recognized user speech. `speech` is the assistant sentence whose
synthesized audio is about to play on the backend host:

```json
{"type":"speech","data":{"text":"Ahora mismo está sonando.","language":"es"}}
```

Kokoro responses are synthesized sentence by sentence. The backend emits each
`speech` event after synthesis and immediately before playback, allowing the
command deck and HUD to show the phrase aligned with audible output. Clients
clear it when state leaves `speaking`.

## Remote input v1

Only one authenticated connection can own remote input at a time. A lease lasts
until an explicit release or until that connection closes or errors. Control
messages and acknowledgements are JSON; audio frames are binary.

1. Client sends `remote_audio.acquire` with the exact format below.
2. Server responds with `remote_audio.acquired`, including limits and output capabilities.
3. Client sends `remote_audio.start`; server responds with `remote_audio.started` after PTT is active.
4. Client sends binary PCM frames only while started.
5. Client sends `remote_audio.stop`; the server ends PTT and processes the utterance.
6. The lease may be reused from step 3 or released with `remote_audio.release`.

```json
{
  "type": "remote_audio.acquire",
  "format": {
    "sample_rate": 16000,
    "channels": 1,
    "sample_format": "pcm_s16le"
  }
}
```

PCM is mono, 16 kHz, signed 16-bit little endian. Each binary frame is non-empty,
sample-aligned, and at most 3,200 bytes (100 ms). An utterance is at most 30
seconds. The server queue holds at most 50 frames and never blocks the audio or
event loop; overflow terminates the stream with a `backpressure` error.

Protocol violations produce `remote_audio.error` with stable `code` and
human-readable `message`, followed by a policy/size/retry close code. Binary data
before `start`, duplicate/out-of-order controls, unsupported formats, malformed
JSON, oversized frames, duration overflow, and a busy lease are rejected.

Remote input is PTT-only. It does not run remote wake-word detection or
continuous capture.

## Output ownership

`remote_audio.acquire` may include an optional `output` object choosing which
side speaks the reply. Omit it and nothing changes from v1.

```json
{
  "type": "remote_audio.acquire",
  "format": {"sample_rate": 16000, "channels": 1, "sample_format": "pcm_s16le"},
  "output": {"mode": "client_text"}
}
```

| Mode | Behaviour |
| --- | --- |
| `server` (default) | The backend host synthesizes and plays the reply on its own speakers. |
| `client_text` | The backend emits `speech` events per sentence and does **no** synthesis, playback, or earcon. The client synthesizes locally. |

`client_text` exists for clients that are not in the same room as the backend —
a phone, primarily. It is also the cheaper path on the server: Kokoro never
runs. Spoken tool confirmations follow output ownership too, so a voice-gated
tool asks the person actually holding the device instead of timing out into a
denial.

Ownership is held for the lifetime of the lease, not one utterance, because the
reply arrives asynchronously. It is released on `remote_audio.release` and on
disconnect — including crash paths, so a dropped client cannot leave the
backend permanently mute.

An unsupported mode is rejected with `unsupported_output_mode` rather than
silently downgraded, so a client can distinguish "not supported" from
"ignored". Streaming server-synthesized PCM to the client is **not**
implemented; `client_audio_supported` stays `false` and `supported_modes` lists
what the server actually honours.

Desktop clients permit `ws://` only for loopback hosts. Non-loopback backend
URLs must use HTTPS and the derived voice socket must use WSS.

## Reproducible checks

```bash
~/.local/bin/uv run pytest -q tests/unit/test_voice.py tests/unit/test_voice_ws.py
cd desktop
npm test -- src/audio/remoteAudio.test.ts src/hooks/useVoiceSocket.test.ts
```
