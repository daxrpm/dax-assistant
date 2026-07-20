package com.dax.assistant.data.transport

import com.dax.assistant.data.protocol.ServerFrame
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ChatSocketDeliveryPolicyTest {
    @Test
    fun `intermediate activity is transient but completion is critical`() {
        assertTrue(agentEvent("thinking").isTransientChatFrame())
        assertTrue(agentEvent("tool_call").isTransientChatFrame())
        assertFalse(agentEvent("done").isTransientChatFrame())
    }

    @Test
    fun `messages and approvals are critical`() {
        assertFalse(ServerFrame.Message("answer", "assistant", "session", null).isTransientChatFrame())
        assertFalse(
            ServerFrame.ToolConfirmation(
                approvalId = "approval",
                toolName = "write",
                serverName = "files",
                arguments = JsonObject(emptyMap()),
                options = listOf("approve", "deny"),
                timeoutSeconds = 120,
                sessionId = "session",
                timestamp = null,
            ).isTransientChatFrame(),
        )
    }

    private fun agentEvent(type: String) = ServerFrame.AgentEvent(
        eventType = type,
        sessionId = "session",
        toolName = null,
        serverName = null,
        ok = null,
        args = JsonObject(emptyMap()),
        preview = null,
        error = null,
        elapsedSeconds = null,
        timestamp = null,
    )
}
