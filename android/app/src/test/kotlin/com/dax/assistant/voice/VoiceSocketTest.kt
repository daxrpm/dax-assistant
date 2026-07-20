package com.dax.assistant.data.transport

import com.dax.assistant.data.protocol.VoiceFrame
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceSocketTest {
    @Test
    fun `level burst cannot close socket or displace turn completion`() = runTest {
        val socket = VoiceSocket(OkHttpClient())

        repeat(128) { socket.accept(VoiceFrame.Level(it.toFloat(), "output")) }
        socket.accept(VoiceFrame.TurnComplete("9"))

        assertEquals(
            VoiceSocketEvent.Frame(VoiceFrame.TurnComplete("9")),
            socket.events.receive(),
        )
    }
}
