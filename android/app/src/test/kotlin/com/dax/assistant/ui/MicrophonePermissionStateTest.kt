package com.dax.assistant.ui

import org.junit.Assert.assertEquals
import org.junit.Test

class MicrophonePermissionStateTest {
    @Test
    fun `first denial remains requestable for rationale`() {
        assertEquals(
            MicrophonePermissionState.Requestable,
            microphonePermissionState(
                granted = false,
                requestedBefore = false,
                shouldShowRationale = false,
            ),
        )
    }

    @Test
    fun `do not ask again denial routes to app settings`() {
        assertEquals(
            MicrophonePermissionState.PermanentlyDenied,
            microphonePermissionState(
                granted = false,
                requestedBefore = true,
                shouldShowRationale = false,
            ),
        )
    }

    @Test
    fun `system rationale keeps permission request available`() {
        assertEquals(
            MicrophonePermissionState.Requestable,
            microphonePermissionState(
                granted = false,
                requestedBefore = true,
                shouldShowRationale = true,
            ),
        )
    }
}
