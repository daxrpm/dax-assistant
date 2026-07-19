# Dax Android

The mobile client. A voice-first assistant that speaks to the same FastAPI
backend as `desktop/`, with the Órbita design language carried over and the
layout rebuilt for one hand and one thumb.

The backend stays the source of truth. Nothing here re-implements the agent
loop, tool policy, or conversation storage.

## Building

The toolchain lives on the external volume because the primary disk sits at
~94% and Gradle caches plus AGP intermediates would fill it.

```bash
cd android
source ./env.sh          # JAVA_HOME, ANDROID_HOME, GRADLE_USER_HOME, PATH
gradle :app:assembleDebug
gradle :app:testDebugUnitTest
```

`env.sh` points at:

| Component | Location |
| --- | --- |
| JDK 21 (Temurin) | `~/toolchain/jdk-21.0.11+10` on the fedora volume |
| Gradle 8.11.1 | `~/toolchain/gradle-8.11.1` |
| Android SDK | `~/Android/Sdk` (pre-existing: platforms 34/36, build-tools 35/36) |
| Gradle home | `~/toolchain/gradle-home` — **not** `~/.gradle` |

`local.properties` is generated and gitignored; recreate it with
`sdk.dir=<ANDROID_HOME>` if you clone fresh.

Versions: AGP 8.10.0, Kotlin 2.1.20, compileSdk 36, **minSdk 31**. 31 is where
`AudioManager.setCommunicationDevice()` lands; supporting anything older would
mean carrying the deprecated `startBluetoothSco()` path for devices this app
will never run on.

## Layout

One Gradle module with strictly layered packages. Multi-module Gradle buys
parallel build time at a real configuration cost, and this is a single-user
app; the boundaries below are enforced by review and package structure rather
than by the build graph.

```
com.dax.assistant
  core/log          structured logging with credential + voice redaction
  ui/design         Órbita tokens and theme, ported from desktop/src/design
  audio             route model; SCO detection and selection
  diagnostics       on-device capability probe
  assistant         state machine and domain types
```

## Watch audio is a runtime feature, never an assumption

Public sources confirm the Redmi Watch 5 Lite registers as a Bluetooth
audio/calls device, and that Android exposes SCO devices through
`AudioManager.getAvailableCommunicationDevices()`. **Neither confirms that this
watch will open a SCO link outside a phone call for a third-party app.** That
is unproven until measured on the physical device.

So the app never branches on "is a watch paired". It branches on
`CapabilityReport.watchAudioUsable`, which is set only after
`CapabilityProbe` has observed selection, capture, *and* playback succeed. A
route that records but cannot answer is worse than no route, because the user
talks into it and hears nothing back — hence all three, not any.

Run the probe from Diagnostics before trusting watch audio. It restores prior
routing in a `finally`, so a failed probe cannot leave the phone on a dead SCO
link.

The seven checks map to the hardware questions:

| Check | Answers |
| --- | --- |
| `HFP_PROFILE` | Is it connected as a headset, or only over a proprietary link? |
| `SCO_DEVICE_PRESENT` | Does Android expose it as `TYPE_BLUETOOTH_SCO`? |
| `COMMUNICATION_DEVICE_SELECTABLE` | **The decisive one.** Does SCO open outside a call? |
| `MICROPHONE_CAPTURE` | Do frames arrive, and is there signal in them? |
| `SPEAKER_PLAYBACK` | Does the engine render into the voice-call stream? |
| `AUDIO_FORMAT` | Observed sample rate — 8 kHz CVSD vs 16 kHz mSBC changes STT accuracy |
| `MEDIA_BUTTON` | Does a watch media key relayed by Gadgetbridge reach us? |

`SPEAKER_PLAYBACK` proves the engine finished rendering; it cannot prove a
human heard it. The UI says so and asks the user to confirm.

## Security posture

* No backend credential is compiled in. The device enrols against a running
  backend with a one-time pairing code and receives its own secret.
* The device secret goes to the Android Keystore. Backup and device transfer
  are excluded wholesale in `data_extraction_rules.xml` — everything is
  excluded rather than selectively included, so a new file cannot be captured
  by accident.
* Access tokens are short-lived and revocable server-side; see
  `src/dax/storage/devices.py`.
* `DaxLog` redacts credentials and never logs transcript content in release.
  Redaction runs on every message, not only at call sites thought to be risky.
* The microphone indicator is never suppressed, and no attempt is made to.
