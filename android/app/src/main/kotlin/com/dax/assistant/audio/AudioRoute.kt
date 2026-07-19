package com.dax.assistant.audio

import android.media.AudioDeviceInfo

/**
 * Where the assistant's microphone and speaker currently are.
 *
 * The watch is not assumed to work. Nothing in this app may branch on "is a
 * Redmi Watch paired"; it branches on "did opening a communication route to
 * this device actually succeed", which is a question only the running system
 * can answer. See [com.dax.assistant.diagnostics.CapabilityProbe].
 */
enum class AudioRouteKind {
    /** Built-in mic and speaker. Always available, always the fallback. */
    PHONE,

    /**
     * A Bluetooth hands-free unit reached over SCO — earbuds, a headset, or
     * the watch. Android does not tell us which, and for audio purposes it
     * does not matter: the capability is identical.
     */
    BLUETOOTH_SCO,

    /** Wired headset. */
    WIRED,
}

/**
 * A selectable audio route.
 *
 * @param id the platform device id, stable for the lifetime of the connection
 * @param productName as reported by the device; used only for display
 */
data class AudioRoute(
    val id: Int,
    val kind: AudioRouteKind,
    val productName: String,
) {
    /** True when this route requires an SCO link that must be opened and torn down. */
    val requiresCommunicationLink: Boolean
        get() = kind == AudioRouteKind.BLUETOOTH_SCO

    companion object {
        /**
         * The route used when nothing else is available or selection failed.
         * Never absent, which is what lets the assistant always remain usable.
         */
        val Phone = AudioRoute(id = 0, kind = AudioRouteKind.PHONE, productName = "Phone")

        fun fromDeviceInfo(info: AudioDeviceInfo): AudioRoute? {
            val kind = when (info.type) {
                AudioDeviceInfo.TYPE_BLUETOOTH_SCO,
                AudioDeviceInfo.TYPE_BLE_HEADSET,
                -> AudioRouteKind.BLUETOOTH_SCO

                AudioDeviceInfo.TYPE_WIRED_HEADSET,
                AudioDeviceInfo.TYPE_USB_HEADSET,
                -> AudioRouteKind.WIRED

                AudioDeviceInfo.TYPE_BUILTIN_MIC,
                AudioDeviceInfo.TYPE_BUILTIN_EARPIECE,
                AudioDeviceInfo.TYPE_BUILTIN_SPEAKER,
                -> AudioRouteKind.PHONE

                else -> return null
            }
            return AudioRoute(
                id = info.id,
                kind = kind,
                productName = info.productName?.toString().orEmpty().ifBlank { "Unknown device" },
            )
        }
    }
}
