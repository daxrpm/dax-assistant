package com.dax.assistant.audio

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import com.dax.assistant.core.log.DaxLog
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Chooses where the conversation happens, and never fails to have an answer.
 *
 * Bluetooth is opportunistic. Earbuds advertise an audio Class of Device, so
 * Android activates them and they appear here as a selectable communication
 * device — those get the full route. The Redmi Watch 5 Lite does not: it
 * advertises `0x001F00` with no audio service-class bit, is never promoted to
 * active, and the only public workaround (`startVoiceRecognition()`) opens a
 * link its firmware ends about a second later. That was measured, not assumed;
 * see android/README.md.
 *
 * So this class asks the platform rather than the device list. If a route
 * cannot be opened and verified, it falls back to the phone silently, because a
 * conversation that happens is worth more than one that was supposed to happen
 * on the wrist.
 */
class AudioRouteManager(context: Context) {

    private val audioManager = context.getSystemService(AudioManager::class.java)

    private val _activeRoute = MutableStateFlow(AudioRoute.Phone)
    val activeRoute: StateFlow<AudioRoute> = _activeRoute.asStateFlow()

    private var previousMode: Int? = null

    /** Bluetooth routes the platform is currently willing to hand out. */
    fun availableBluetoothRoutes(): List<AudioRoute> = runCatching {
        audioManager.availableCommunicationDevices
            .mapNotNull(AudioRoute::fromDeviceInfo)
            .filter { it.kind == AudioRouteKind.BLUETOOTH_SCO }
    }.getOrDefault(emptyList())

    /**
     * Opens the best available route and returns what was actually obtained.
     *
     * Verification is the point: `setCommunicationDevice` returning true means
     * the request was accepted, not that the link came up. Callers get the
     * phone route unless Bluetooth was confirmed live.
     */
    suspend fun acquireBestRoute(): AudioRoute {
        val bluetooth = availableBluetoothRoutes().firstOrNull()
        if (bluetooth == null) {
            _activeRoute.value = AudioRoute.Phone
            return AudioRoute.Phone
        }

        val device = runCatching {
            audioManager.availableCommunicationDevices.firstOrNull { it.id == bluetooth.id }
        }.getOrNull()
        if (device == null) {
            _activeRoute.value = AudioRoute.Phone
            return AudioRoute.Phone
        }

        return runCatching {
            previousMode = audioManager.mode
            audioManager.mode = AudioManager.MODE_IN_COMMUNICATION
            if (!audioManager.setCommunicationDevice(device)) {
                restoreMode()
                _activeRoute.value = AudioRoute.Phone
                return@runCatching AudioRoute.Phone
            }
            val live = withTimeoutOrNull(ROUTE_SETTLE_MILLIS) {
                while (
                    audioManager.communicationDevice?.type != AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                ) {
                    delay(100)
                }
                true
            } == true

            if (live) {
                DaxLog.i(TAG, "Using Bluetooth route: ${bluetooth.productName}")
                _activeRoute.value = bluetooth
                bluetooth
            } else {
                DaxLog.i(TAG, "Bluetooth route did not come up; using the phone")
                release()
                AudioRoute.Phone
            }
        }.getOrElse {
            DaxLog.w(TAG, "Route acquisition failed; using the phone", it)
            release()
            AudioRoute.Phone
        }
    }

    /**
     * Whether the Bluetooth route is still live.
     *
     * Called mid-turn: a link that dies while the user is talking must demote
     * the UI to the phone route rather than leave it claiming a wrist mic.
     */
    fun bluetoothStillLive(): Boolean =
        runCatching {
            audioManager.communicationDevice?.type == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
        }.getOrDefault(false)

    /** Always safe to call, including when nothing was acquired. */
    fun release() {
        runCatching { audioManager.clearCommunicationDevice() }
        restoreMode()
        _activeRoute.value = AudioRoute.Phone
    }

    private fun restoreMode() {
        previousMode?.let { mode ->
            runCatching { audioManager.mode = mode }
            previousMode = null
        }
    }

    private companion object {
        const val TAG = "AudioRouteManager"
        const val ROUTE_SETTLE_MILLIS = 2_500L
    }
}
