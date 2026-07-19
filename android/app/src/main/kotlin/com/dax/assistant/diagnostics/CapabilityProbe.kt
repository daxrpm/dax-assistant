package com.dax.assistant.diagnostics

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothHeadset
import android.bluetooth.BluetoothProfile
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.core.content.ContextCompat
import com.dax.assistant.audio.AudioRoute
import com.dax.assistant.audio.AudioRouteKind
import com.dax.assistant.core.log.DaxLog
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine
import kotlin.math.abs

/**
 * Answers, on the real device, whether Bluetooth audio is actually usable.
 *
 * Every claim this app makes about the watch is unproven until this runs.
 * Public sources establish that the Redmi Watch 5 Lite registers as a
 * Bluetooth audio/calls device and that Android exposes SCO devices through
 * [AudioManager.getAvailableCommunicationDevices]; neither establishes that
 * *this* watch will open a SCO link outside a phone call for a third-party
 * app. That is the question [COMMUNICATION_DEVICE_SELECTABLE][CheckId] exists
 * to settle, and the reason the whole app treats watch audio as a runtime
 * feature rather than a configuration option.
 *
 * The probe is deliberately conservative:
 *
 *  * It restores the prior audio routing in a `finally`, so a failed probe
 *    never leaves the phone stuck on a dead SCO link.
 *  * It stops at the first prerequisite failure and marks the rest SKIPPED
 *    rather than reporting cascading falsehoods.
 *  * It never asserts silence is failure without saying so: an all-zero
 *    capture is reported as "no signal", which on a muted or distant mic is a
 *    legitimate result the user needs to interpret.
 */
class CapabilityProbe(
    private val context: Context,
    private val io: CoroutineDispatcher,
) {

    /** How long to wait for an SCO link to come up. */
    private val scoSettleTimeoutMillis = 4_000L

    /** How much audio to capture when testing the microphone. */
    private val captureDurationMillis = 1_500L

    /**
     * How long the route must hold to count as usable.
     *
     * Six seconds covers a spoken request plus the pause before a reply. The
     * observed failure tore down at roughly 1.4s, so this is comfortably past
     * the boundary rather than tuned to just clear it.
     */
    private val requiredHoldMillis = 6_000L

    private val audioManager: AudioManager
        get() = context.getSystemService(AudioManager::class.java)

    suspend fun run(onProgress: (CapabilityReport) -> Unit = {}): CapabilityReport =
        withContext(io) {
            var report = CapabilityReport()

            if (!hasPermission(Manifest.permission.RECORD_AUDIO)) {
                return@withContext report
                    .skipRemaining(CheckId.HFP_PROFILE, "Microphone permission not granted")
                    .copy(completedAtEpochMillis = System.currentTimeMillis())
            }

            report = checkHfpProfile(report).also(onProgress)

            var scoRoute = findScoRoute()

            // A device can be connected on HFP yet absent here, because
            // getAvailableCommunicationDevices() only offers a headset once
            // the profile has made it the *active* device. Devices that
            // advertise an uncategorized Class of Device — the Redmi Watch 5
            // Lite reports 0x001F00, with no Audio service-class bit — are not
            // promoted automatically, and setActiveDevice() is @SystemApi.
            //
            // startVoiceRecognition() is the public way out: it sends AT+BVRA
            // and asks the stack to bring up the audio connection, which
            // promotes the device as a side effect. Worth trying before
            // concluding the hardware cannot do it.
            var openedViaVoiceRecognition = false
            if (scoRoute == null) {
                openedViaVoiceRecognition = tryStartVoiceRecognition()
                if (openedViaVoiceRecognition) {
                    scoRoute = awaitScoRoute()
                }
            }

            report = if (scoRoute == null) {
                report
                    .with(
                        CheckId.SCO_DEVICE_PRESENT,
                        CheckStatus.FAIL,
                        buildString {
                            append("Absent from getAvailableCommunicationDevices()")
                            if (openedViaVoiceRecognition) {
                                append(" even after startVoiceRecognition() succeeded")
                            } else {
                                append("; startVoiceRecognition() also failed")
                            }
                            append(". Audio devices seen: ")
                            append(describeAllAudioDevices())
                        },
                    )
                    .skipRemaining(
                        CheckId.COMMUNICATION_DEVICE_SELECTABLE,
                        "No SCO device to test",
                    )
                    .also(onProgress)
            } else {
                report.with(
                    CheckId.SCO_DEVICE_PRESENT,
                    CheckStatus.PASS,
                    buildString {
                        append("${scoRoute.productName} (id ${scoRoute.id})")
                        if (openedViaVoiceRecognition) {
                            append(" — required startVoiceRecognition() to appear")
                        }
                    },
                ).also(onProgress)
            }

            if (scoRoute != null) {
                report = probeWithScoRoute(report, scoRoute, onProgress)
            }

            // The media-button check cannot be automated: it needs a physical
            // press on the watch. The UI arms a listener and reports the
            // result separately; see MediaButtonProbe.
            report.copy(
                deviceName = scoRoute?.productName.orEmpty(),
                completedAtEpochMillis = System.currentTimeMillis(),
            )
        }

    /**
     * Runs the checks that require an open communication route, restoring the
     * previous routing whatever happens.
     */
    private suspend fun probeWithScoRoute(
        initial: CapabilityReport,
        route: AudioRoute,
        onProgress: (CapabilityReport) -> Unit,
    ): CapabilityReport {
        var report = initial
        val manager = audioManager
        val device = manager.availableCommunicationDevices.firstOrNull { it.id == route.id }
            ?: return report.skipRemaining(
                CheckId.COMMUNICATION_DEVICE_SELECTABLE,
                "Device disappeared between enumeration and selection",
            ).also(onProgress)

        val previousMode = manager.mode
        var selected = false
        try {
            // MODE_IN_COMMUNICATION is what makes the platform treat this as a
            // voice route rather than media playback; without it SCO will not
            // come up outside a call on many devices.
            manager.mode = AudioManager.MODE_IN_COMMUNICATION
            selected = manager.setCommunicationDevice(device)

            report = if (selected) {
                report.with(
                    CheckId.COMMUNICATION_DEVICE_SELECTABLE,
                    CheckStatus.PASS,
                    "setCommunicationDevice() accepted outside a call",
                )
            } else {
                report
                    .with(
                        CheckId.COMMUNICATION_DEVICE_SELECTABLE,
                        CheckStatus.FAIL,
                        "setCommunicationDevice() returned false",
                    )
                    .skipRemaining(CheckId.MICROPHONE_CAPTURE, "Route could not be opened")
            }
            onProgress(report)
            if (!selected) return report

            // Let the SCO link actually establish. Selecting the device is a
            // request, not a completed connection.
            awaitScoRouting(route.id)

            // The VR session that promoted the device is about to end, because
            // the watch has no recognizer to run. Whether the route survives
            // that is the question everything else depends on, so measure it
            // with a live capture stream anchoring the link — an idle route
            // and a route carrying audio are not the same thing to the audio
            // policy manager.
            val stability = measureRouteStability()
            report = report.with(
                CheckId.ROUTE_STABILITY,
                if (stability.usable) CheckStatus.PASS else CheckStatus.FAIL,
                stability.detail,
            )
            onProgress(report)

            val capture = captureFromRoute()
            report = report
                .with(CheckId.MICROPHONE_CAPTURE, capture.status, capture.detail)
                .with(
                    CheckId.AUDIO_FORMAT,
                    if (capture.sampleRate > 0) CheckStatus.PASS else CheckStatus.FAIL,
                    capture.formatDetail,
                )
            onProgress(report)

            // The link is short-lived on some devices — the Redmi Watch 5 Lite
            // tears SCO down about 1.4s after startVoiceRecognition(), because
            // it has no voice-recognition session of its own to run. Checking
            // the route is still ours before speaking is what stops a reply
            // being reported as delivered when it actually came out of the
            // phone.
            val routeStillOurs =
                manager.communicationDevice?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
            report = if (!routeStillOurs) {
                report.with(
                    CheckId.SPEAKER_PLAYBACK,
                    CheckStatus.FAIL,
                    "The Bluetooth route dropped before playback — audio would " +
                        "come out of the phone. Current route: " +
                        (manager.communicationDevice?.productName?.toString() ?: "none"),
                )
            } else {
                val spoke = speakThroughRoute()
                val heldThroughout =
                    manager.communicationDevice?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                when {
                    !spoke.first -> report.with(
                        CheckId.SPEAKER_PLAYBACK, CheckStatus.FAIL, spoke.second,
                    )
                    !heldThroughout -> report.with(
                        CheckId.SPEAKER_PLAYBACK,
                        CheckStatus.FAIL,
                        "The route dropped while speaking, so playback finished on " +
                            "the phone rather than the Bluetooth device",
                    )
                    else -> report.with(
                        CheckId.SPEAKER_PLAYBACK,
                        CheckStatus.PASS,
                        "Rendered with the Bluetooth route held throughout " +
                            "(confirm you heard it on the device)",
                    )
                }
            }
            onProgress(report)
            return report
        } catch (error: SecurityException) {
            DaxLog.w(TAG, "Capability probe blocked by permissions")
            return report.skipRemaining(
                CheckId.COMMUNICATION_DEVICE_SELECTABLE,
                "Permission denied: ${error.javaClass.simpleName}",
            )
        } finally {
            // Must run even on the exception path: leaving the phone on a
            // half-open SCO link breaks normal calls until reboot.
            if (selected) runCatching { manager.clearCommunicationDevice() }
            runCatching { manager.mode = previousMode }
        }
    }

    private fun findScoRoute(): AudioRoute? = runCatching {
        audioManager.availableCommunicationDevices
            .mapNotNull(AudioRoute::fromDeviceInfo)
            .firstOrNull { it.kind == AudioRouteKind.BLUETOOTH_SCO }
    }.getOrNull()

    /**
     * Polls for the SCO route to appear after asking the stack to open it.
     *
     * Promotion is asynchronous: startVoiceRecognition() returns as soon as
     * the request is accepted, well before the device shows up as a
     * communication device.
     */
    private suspend fun awaitScoRoute(): AudioRoute? = withTimeoutOrNull(scoSettleTimeoutMillis) {
        var found: AudioRoute? = null
        while (found == null) {
            found = findScoRoute()
            if (found == null) delay(150)
        }
        found
    }

    /**
     * Asks the headset profile to open a voice-recognition audio session.
     *
     * This is the public equivalent of the privileged setActiveDevice(): the
     * platform sends AT+BVRA to the headset and brings up SCO. For a wearable
     * that Android declines to auto-activate, it is the only third-party route
     * to an audio link outside a call.
     *
     * Failure is expected and survivable — the caller falls back to the phone.
     */
    @SuppressLint("MissingPermission") // guarded by hasPermission() below
    private suspend fun tryStartVoiceRecognition(): Boolean {
        if (!hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) return false
        val adapter = context.getSystemService(android.bluetooth.BluetoothManager::class.java)
            ?.adapter ?: return false

        return withTimeoutOrNull(6_000L) {
            suspendCoroutine { continuation ->
                val listener = object : BluetoothProfile.ServiceListener {
                    override fun onServiceConnected(profile: Int, proxy: BluetoothProfile?) {
                        val headset = proxy as? BluetoothHeadset
                        val target = runCatching { headset?.connectedDevices?.firstOrNull() }
                            .getOrNull()
                        val started = if (headset != null && target != null) {
                            runCatching { headset.startVoiceRecognition(target) }
                                .onFailure { DaxLog.w(TAG, "startVoiceRecognition threw", it) }
                                .getOrDefault(false)
                        } else {
                            false
                        }
                        DaxLog.i(TAG, "startVoiceRecognition() returned $started")
                        // The proxy is intentionally left open: closing it here
                        // can tear down the very SCO link we just asked for.
                        // It is released when the probe's process scope ends.
                        continuation.resume(started)
                    }

                    override fun onServiceDisconnected(profile: Int) = Unit
                }
                if (!adapter.getProfileProxy(context, listener, BluetoothProfile.HEADSET)) {
                    continuation.resume(false)
                }
            }
        } ?: false
    }

    /**
     * Every audio device the platform knows about.
     *
     * When the SCO check fails this is the difference between "the watch is
     * invisible to the audio HAL" and "the HAL sees it but will not offer it
     * for communication" — which point to completely different fixes.
     */
    private fun describeAllAudioDevices(): String = runCatching {
        val manager = audioManager
        val inputs = manager.getDevices(AudioManager.GET_DEVICES_INPUTS)
        val outputs = manager.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
        val relevant = (inputs + outputs)
            .filter { it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO ||
                it.type == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP ||
                it.type == AudioDeviceInfo.TYPE_BLE_HEADSET }
            .joinToString { "${it.productName}/type=${it.type}" }
        relevant.ifBlank { "no Bluetooth audio device in the HAL at all" }
    }.getOrDefault("enumeration failed")

    /**
     * Waits until the platform reports the requested device as current.
     *
     * Returns whether it settled; a timeout is informative rather than fatal,
     * because some devices route correctly without ever reporting it.
     */
    private suspend fun awaitScoRouting(deviceId: Int): Boolean {
        val settled = withTimeoutOrNull(scoSettleTimeoutMillis) {
            while (audioManager.communicationDevice?.id != deviceId) {
                delay(100)
            }
            true
        }
        return settled == true
    }

    private data class StabilityOutcome(val usable: Boolean, val detail: String)

    /**
     * How long the Bluetooth route survives while audio is flowing.
     *
     * Two things are being tested at once. First, whether a live
     * [AudioRecord] keeps the link alive after the voice-recognition session
     * that opened it goes away — an active capture stream is what turns a
     * speculative route request into one the policy manager has a reason to
     * keep. Second, if it does drop, whether re-asserting
     * setCommunicationDevice() brings it back now that the headset has been
     * promoted to active, since promotion is the part that needed VR and it
     * should persist.
     *
     * A route that has to be re-established every second is not a usable one,
     * so the bar is holding continuously for [requiredHoldMillis].
     */
    @SuppressLint("MissingPermission") // guarded by hasPermission() before use
    private suspend fun measureRouteStability(): StabilityOutcome {
        val manager = audioManager
        val sampleRate = 16_000
        val minBuffer = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        ).coerceAtLeast(3_200)

        var recorder: AudioRecord? = null
        return try {
            recorder = AudioRecord(
                MediaRecorder.AudioSource.VOICE_COMMUNICATION,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                minBuffer * 2,
            )
            if (recorder.state != AudioRecord.STATE_INITIALIZED) {
                return StabilityOutcome(false, "AudioRecord would not initialise")
            }
            recorder.startRecording()

            val buffer = ShortArray(minBuffer)
            val started = System.currentTimeMillis()
            var heldUntil = started
            var firstDropAt: Long? = null
            var recovered = false

            while (System.currentTimeMillis() - started < requiredHoldMillis) {
                // Keep draining, or the stream stalls and stops anchoring.
                recorder.read(buffer, 0, buffer.size)
                val onSco =
                    manager.communicationDevice?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO &&
                        recorder.routedDevice?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                val now = System.currentTimeMillis()
                if (onSco) {
                    heldUntil = now
                } else if (firstDropAt == null) {
                    firstDropAt = now
                    // The headset should still be the active device even
                    // though the VR session ended, so a fresh request ought to
                    // bring SCO back on its own terms rather than VR's.
                    recovered = reassertRoute()
                }
                delay(200)
            }

            val heldMillis = heldUntil - started
            when {
                firstDropAt == null -> StabilityOutcome(
                    true,
                    "Held the Bluetooth route continuously for ${heldMillis}ms " +
                        "with capture running",
                )
                recovered -> StabilityOutcome(
                    false,
                    "Dropped after ${firstDropAt - started}ms and was recovered by " +
                        "re-asserting the route — usable only with reconnection logic",
                )
                else -> StabilityOutcome(
                    false,
                    "Dropped after ${firstDropAt - started}ms and could not be " +
                        "recovered; the watch ends the session it never had",
                )
            }
        } catch (error: Exception) {
            StabilityOutcome(false, "${error.javaClass.simpleName}: ${error.message.orEmpty()}")
        } finally {
            runCatching { recorder?.stop() }
            runCatching { recorder?.release() }
        }
    }

    /**
     * Re-requests the Bluetooth route after a drop.
     *
     * Clearing first matters: the broker treats a repeated request for the
     * device it already believes is selected as a no-op, so without the clear
     * nothing is actually retried.
     */
    private suspend fun reassertRoute(): Boolean {
        val manager = audioManager
        return runCatching {
            manager.clearCommunicationDevice()
            delay(150)
            val device = manager.availableCommunicationDevices
                .firstOrNull { it.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO }
                ?: return false
            val ok = manager.setCommunicationDevice(device)
            if (ok) delay(400)
            ok && manager.communicationDevice?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
        }.getOrDefault(false)
    }

    private data class CaptureOutcome(
        val status: CheckStatus,
        val detail: String,
        val sampleRate: Int,
        val formatDetail: String,
    )

    /**
     * Records a short buffer and reports both whether capture worked and what
     * the audio actually looked like.
     *
     * HFP negotiates either 8 kHz CVSD or 16 kHz mSBC, and the difference
     * materially changes speech-recognition accuracy. Android does not expose
     * the negotiated codec, so the observed rate is the closest honest proxy —
     * this reports what was requested and accepted, not a codec name it cannot
     * actually see.
     */
    @SuppressLint("MissingPermission") // guarded by hasPermission() before use
    private fun captureFromRoute(): CaptureOutcome {
        val sampleRate = 16_000
        val minBuffer = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        if (minBuffer <= 0) {
            return CaptureOutcome(
                CheckStatus.FAIL,
                "getMinBufferSize() returned $minBuffer",
                0,
                "Unavailable",
            )
        }

        val bufferSize = minBuffer * 2
        var recorder: AudioRecord? = null
        return try {
            recorder = AudioRecord(
                // VOICE_RECOGNITION asks the platform not to apply the
                // aggressive AGC and echo cancellation tuned for telephony,
                // which is what a recognizer wants.
                MediaRecorder.AudioSource.VOICE_RECOGNITION,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize,
            )
            if (recorder.state != AudioRecord.STATE_INITIALIZED) {
                return CaptureOutcome(
                    CheckStatus.FAIL,
                    "AudioRecord failed to initialise",
                    0,
                    "Unavailable",
                )
            }

            recorder.startRecording()
            val buffer = ShortArray(bufferSize / 2)
            var frames = 0
            var peak = 0
            val deadline = System.currentTimeMillis() + captureDurationMillis
            while (System.currentTimeMillis() < deadline) {
                val read = recorder.read(buffer, 0, buffer.size)
                if (read <= 0) break
                frames += read
                for (i in 0 until read) {
                    val magnitude = abs(buffer[i].toInt())
                    if (magnitude > peak) peak = magnitude
                }
            }
            recorder.stop()

            val actualRate = recorder.sampleRate
            // Where the frames actually came from. Reading this is the whole
            // point: an AudioRecord whose SCO link dropped keeps delivering
            // audio from the phone microphone, so frame count and amplitude
            // alone will happily "prove" a route that is not being used.
            val routedDevice = recorder.routedDevice
            val routedToSco = routedDevice?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
            val routedName = routedDevice?.productName?.toString().orEmpty()
            val formatDetail = buildString {
                append("$actualRate Hz mono PCM16")
                append(
                    when {
                        routedDevice == null -> ", routed device unknown"
                        else -> ", routed to $routedName (type ${routedDevice.type})"
                    },
                )
                append(
                    if (actualRate >= 16_000) {
                        " — 16 kHz implies wideband mSBC"
                    } else {
                        " — 8 kHz implies narrowband CVSD, weaker for recognition"
                    },
                )
            }

            when {
                frames == 0 -> CaptureOutcome(
                    CheckStatus.FAIL,
                    "No frames read from the device",
                    actualRate,
                    formatDetail,
                )
                // The failure this probe previously reported as success: the
                // SCO link dropped mid-capture and the phone microphone
                // silently took over.
                !routedToSco -> CaptureOutcome(
                    CheckStatus.FAIL,
                    "Captured $frames frames, but from " +
                        (routedName.ifBlank { "an unknown device" }) +
                        " — not the Bluetooth route",
                    actualRate,
                    formatDetail,
                )
                // Silence is a real answer, not a crash. Reported distinctly so
                // the user knows to check whether the mic was covered or muted.
                peak == 0 -> CaptureOutcome(
                    CheckStatus.FAIL,
                    "Captured $frames frames from the watch but the signal was pure silence",
                    actualRate,
                    formatDetail,
                )
                else -> CaptureOutcome(
                    CheckStatus.PASS,
                    "Captured $frames frames from $routedName, peak amplitude $peak",
                    actualRate,
                    formatDetail,
                )
            }
        } catch (error: Exception) {
            CaptureOutcome(
                CheckStatus.FAIL,
                "${error.javaClass.simpleName}: ${error.message.orEmpty()}",
                0,
                "Unavailable",
            )
        } finally {
            runCatching { recorder?.release() }
        }
    }

    /**
     * Speaks a short phrase and waits for the engine to report completion.
     *
     * Completion proves the engine rendered audio into the voice-call stream;
     * it cannot prove a human heard it come out of the watch. The UI says so,
     * and asks the user to confirm.
     */
    private suspend fun speakThroughRoute(): Pair<Boolean, String> {
        val engine = CompletableDeferred<TextToSpeech?>()
        val tts = TextToSpeech(context) { status ->
            engine.complete(null)
            if (status != TextToSpeech.SUCCESS) {
                DaxLog.w(TAG, "TTS engine unavailable during probe")
            }
        }
        return try {
            val ready = withTimeoutOrNull(5_000L) { engine.await() ; true } ?: false
            if (!ready) return false to "TTS engine did not initialise within 5s"

            val done = CompletableDeferred<Boolean>()
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) = Unit
                override fun onDone(utteranceId: String?) {
                    done.complete(true)
                }

                @Deprecated("Required override", ReplaceWith(""))
                override fun onError(utteranceId: String?) {
                    done.complete(false)
                }

                override fun onError(utteranceId: String?, errorCode: Int) {
                    done.complete(false)
                }
            })
            tts.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build(),
            )

            val queued = tts.speak(PROBE_PHRASE, TextToSpeech.QUEUE_FLUSH, null, PROBE_UTTERANCE)
            if (queued != TextToSpeech.SUCCESS) return false to "speak() rejected the request"

            val finished = withTimeoutOrNull(10_000L) { done.await() } ?: false
            if (finished) {
                true to "Engine rendered speech into the voice-call stream " +
                    "(confirm you heard it on the device)"
            } else {
                false to "Playback did not complete within 10s"
            }
        } catch (error: Exception) {
            false to "${error.javaClass.simpleName}: ${error.message.orEmpty()}"
        } finally {
            runCatching { tts.stop() }
            runCatching { tts.shutdown() }
        }
    }

    /**
     * Whether the device is connected under the HFP/headset profile.
     *
     * This is the check that distinguishes "paired" from "paired and offering
     * audio". A watch bound only over a proprietary link — Gadgetbridge's
     * SPP channel, for instance — is fully functional for notifications and
     * still absent here.
     */
    private suspend fun checkHfpProfile(report: CapabilityReport): CapabilityReport {
        if (!hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
            return report.with(
                CheckId.HFP_PROFILE,
                CheckStatus.SKIPPED,
                "BLUETOOTH_CONNECT permission not granted",
            )
        }
        val adapter = context.getSystemService(android.bluetooth.BluetoothManager::class.java)
            ?.adapter
            ?: return report.with(CheckId.HFP_PROFILE, CheckStatus.FAIL, "No Bluetooth adapter")

        val names = connectedHeadsetNames(adapter)
            ?: return report.with(
                CheckId.HFP_PROFILE,
                CheckStatus.FAIL,
                "Could not query the headset profile",
            )

        return if (names.isEmpty()) {
            report.with(
                CheckId.HFP_PROFILE,
                CheckStatus.FAIL,
                "No device connected under the headset profile",
            )
        } else {
            report.with(CheckId.HFP_PROFILE, CheckStatus.PASS, names.joinToString(", "))
        }
    }

    @SuppressLint("MissingPermission") // guarded by hasPermission() above
    private suspend fun connectedHeadsetNames(adapter: BluetoothAdapter): List<String>? =
        withTimeoutOrNull(5_000L) {
            suspendCoroutine { continuation ->
                val listener = object : BluetoothProfile.ServiceListener {
                    override fun onServiceConnected(profile: Int, proxy: BluetoothProfile?) {
                        val names = runCatching {
                            (proxy as? BluetoothHeadset)?.connectedDevices
                                ?.map { it.name ?: it.address }
                                .orEmpty()
                        }.getOrDefault(emptyList())
                        runCatching {
                            adapter.closeProfileProxy(BluetoothProfile.HEADSET, proxy)
                        }
                        continuation.resume(names)
                    }

                    override fun onServiceDisconnected(profile: Int) = Unit
                }
                if (!adapter.getProfileProxy(context, listener, BluetoothProfile.HEADSET)) {
                    continuation.resume(emptyList())
                }
            }
        }

    private fun hasPermission(permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    private companion object {
        const val TAG = "CapabilityProbe"
        const val PROBE_UTTERANCE = "dax-capability-probe"
        const val PROBE_PHRASE = "Dax audio check."
    }
}
