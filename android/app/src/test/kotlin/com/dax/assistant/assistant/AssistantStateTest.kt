package com.dax.assistant.assistant

import com.dax.assistant.audio.AudioRoute
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The invariants that keep the UI honest: never invite speech into a dead
 * microphone, never strand the user without a cancel, never claim to be
 * listening before the route is open.
 */
class AssistantStateTest {

    private val phone = AudioRoute.Phone

    @Test
    fun `a turn may start only from a resting state`() {
        assertTrue(AssistantState.Idle.canStartTurn)
        assertTrue(AssistantState.Failed(AssistantError.Cancelled, true).canStartTurn)
        // Barge-in: speaking is interruptible by design.
        assertTrue(AssistantState.Speaking("hi", route = phone).canStartTurn)
    }

    @Test
    fun `a turn may not start while one is already in flight`() {
        assertFalse(AssistantState.ConnectingAudio(phone).canStartTurn)
        assertFalse(AssistantState.Listening(phone).canStartTurn)
        assertFalse(AssistantState.Transcribing().canStartTurn)
        assertFalse(AssistantState.Processing("x").canStartTurn)
    }

    @Test
    fun `a turn may not start while a confirmation is pending`() {
        val state = AssistantState.AwaitingApproval(
            request = approval(),
            transcript = "borra el archivo",
        )

        assertFalse(
            "starting a new turn would abandon a gated tool decision",
            state.canStartTurn,
        )
    }

    @Test
    fun `disconnected does not permit a turn`() {
        val state = AssistantState.Disconnected("network lost", reconnecting = true)

        assertFalse(
            "idle-looking UI would invite the user to talk to nothing",
            state.canStartTurn,
        )
    }

    @Test
    fun `every state that holds a resource is cancellable`() {
        val holding = listOf(
            AssistantState.ConnectingAudio(phone),
            AssistantState.Listening(phone),
            AssistantState.Transcribing(),
            AssistantState.Processing("x"),
            AssistantState.AwaitingApproval(approval(), "x"),
            AssistantState.Speaking("x", route = phone),
        )

        holding.forEach { assertTrue("$it must be cancellable", it.cancellable) }
    }

    @Test
    fun `resting states are not cancellable`() {
        assertFalse(AssistantState.Idle.cancellable)
        assertFalse(AssistantState.Disconnected("x", false).cancellable)
        assertFalse(AssistantState.Failed(AssistantError.Cancelled, true).cancellable)
    }

    @Test
    fun `the microphone indicator covers route setup as well as listening`() {
        // The window where the SCO link is opening is exactly when a user
        // starts talking and loses their first word. It must read as live.
        assertTrue(AssistantState.ConnectingAudio(phone).microphoneActive)
        assertTrue(AssistantState.Listening(phone).microphoneActive)
    }

    @Test
    fun `the microphone indicator is off once capture has ended`() {
        assertFalse(AssistantState.Transcribing().microphoneActive)
        assertFalse(AssistantState.Processing("x").microphoneActive)
        assertFalse(AssistantState.Speaking("x", route = phone).microphoneActive)
        assertFalse(AssistantState.Idle.microphoneActive)
    }

    @Test
    fun `listening distinguishes silence from detected speech`() {
        val quiet = AssistantState.Listening(phone)
        val heard = quiet.copy(speechDetected = true, partialTranscript = "hola")

        assertFalse(quiet.speechDetected)
        assertTrue(heard.speechDetected)
    }

    private fun approval() = ApprovalRequest(
        approvalId = "a1",
        toolName = "fs_delete",
        serverName = "dax-system",
        arguments = mapOf("path" to "/home/dax/notes.md"),
        options = listOf("approve", "deny"),
        timeoutSeconds = 120,
        requestedAtEpochMillis = 0L,
    )
}
