package com.dax.assistant.data.protocol

import org.junit.Assert.assertEquals
import org.junit.Test

class VoiceFramesTest {
    @Test
    fun `parses explicit turn completion`() {
        val frame = VoiceFrames.parse(
            """{"type":"turn_complete","data":{"voice_turn":"17"}}""",
        )

        assertEquals(VoiceFrame.TurnComplete("17"), frame)
    }

    @Test
    fun `parses remote approval with offered options`() {
        val frame = VoiceFrames.parse(
            """{"type":"approval_request","data":{"approval_id":"a1","tool_name":"shell_run","server_name":"system","arguments":{"command":"date"},"options":["once","save"],"timeout_seconds":30}}""",
        )

        assertEquals(
            VoiceFrame.ApprovalRequest(
                "a1", "shell_run", "system", mapOf("command" to "date"),
                listOf("once", "save"), 30,
            ),
            frame,
        )
    }

    @Test
    fun `encodes approval decision on the voice socket`() {
        assertEquals(
            """{"type":"voice.approval","approval_id":"a1","decision":"once"}""",
            VoiceFrames.approval("a1", "once"),
        )
    }

    @Test
    fun `parses delivery-only interruption acknowledgement`() {
        assertEquals(
            VoiceFrame.Interrupted("idle", agentCancelled = false),
            VoiceFrames.parse(
                """{"type":"remote_audio.interrupted","data":{"state":"idle","agent_cancelled":false}}""",
            ),
        )
    }
}
