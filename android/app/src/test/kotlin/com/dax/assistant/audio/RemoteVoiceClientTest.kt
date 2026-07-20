package com.dax.assistant.audio

import kotlinx.coroutines.CancellationException
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class RemoteVoiceClientTest {
    @Test
    fun `cancellation is never wrapped as a remote voice failure`() {
        val cancellation = CancellationException("cancelled")

        assertSame(cancellation, remoteVoiceFailure(cancellation))
        assertTrue(remoteVoiceFailure(IllegalStateException("broken")) is RemoteVoiceException)
    }
}
