package com.dax.assistant.assistant

import com.dax.assistant.audio.AudioRouteManager
import com.dax.assistant.audio.RecognitionEvent
import com.dax.assistant.audio.Speaker
import com.dax.assistant.audio.SpeechRecognition
import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.data.protocol.ClientFrames
import com.dax.assistant.data.protocol.ServerFrame
import com.dax.assistant.data.transport.ChatSocket
import com.dax.assistant.data.transport.ConnectionState
import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** One settled exchange, for the compact history. */
data class Turn(
    val id: String,
    val userText: String,
    val assistantText: String,
    val timestampMillis: Long,
)

/**
 * Drives the assistant state machine.
 *
 * Everything the UI shows comes from [state]; everything the user does arrives
 * as a method here. Keeping the machine in one place is what makes the
 * transitions checkable — the alternative is state smeared across a ViewModel,
 * a service, and three callbacks, which is how voice apps end up listening
 * when they claim to be idle.
 *
 * The turn always ends. Every failure path lands in [AssistantState.Failed] or
 * [AssistantState.Idle] and releases the audio route, because a leaked route
 * means a live microphone the user cannot see a reason for.
 */
class AssistantController(
    private val socket: ChatSocket,
    private val routes: AudioRouteManager,
    private val recognition: SpeechRecognition,
    private val speaker: Speaker,
    private val scope: CoroutineScope,
    private val languageTag: String = "es-ES",
) {

    private val _state = MutableStateFlow<AssistantState>(AssistantState.Idle)
    val state: StateFlow<AssistantState> = _state.asStateFlow()

    private val _history = MutableStateFlow<List<Turn>>(emptyList())
    val history: StateFlow<List<Turn>> = _history.asStateFlow()

    /**
     * Stable per-install conversation key.
     *
     * The backend keys persisted conversations on this and scopes frame
     * delivery to it, so the phone sees its own conversation and not the
     * desktop's. It also claims the session, which is what lets the phone
     * answer its own tool confirmations and nobody else's.
     */
    val sessionId: String = "android-" + UUID.randomUUID().toString().take(8)

    private var turnJob: Job? = null
    private var pendingUserText: String = ""
    private var streamedReply: String = ""

    init {
        scope.launch { collectFrames() }
        scope.launch { watchConnection() }
    }

    /** Begins a turn. Ignored unless the machine is at rest. */
    fun startTurn() {
        if (!_state.value.canStartTurn) {
            DaxLog.d(TAG, "Ignoring trigger in state ${_state.value::class.simpleName}")
            return
        }
        // Barge-in: a trigger during playback interrupts the reply.
        speaker.stop()
        turnJob?.cancel()
        turnJob = scope.launch { runTurn() }
    }

    /** Cancels whatever is in flight and returns to rest. */
    fun cancel() {
        turnJob?.cancel()
        turnJob = null
        speaker.stop()
        routes.release()
        streamedReply = ""
        pendingUserText = ""
        _state.value = AssistantState.Idle
    }

    /** Answers a pending tool confirmation. */
    fun resolveApproval(decision: String) {
        val current = _state.value as? AssistantState.AwaitingApproval ?: return
        val sent = socket.send(
            ClientFrames.toolConfirmation(current.request.approvalId, decision),
        )
        if (!sent) {
            // The backend denies on timeout, so a lost confirmation fails
            // closed rather than silently running the tool.
            _state.value = AssistantState.Failed(
                AssistantError.Network("Could not send the decision — it will be denied"),
                recoverable = true,
            )
            return
        }
        _state.value = AssistantState.Processing(
            transcript = current.transcript,
            streamedReply = current.streamedReply,
        )
    }

    private suspend fun runTurn() {
        val route = try {
            _state.value = AssistantState.ConnectingAudio(routes.activeRoute.value)
            routes.acquireBestRoute()
        } catch (error: Exception) {
            fail(AssistantError.Audio(error.message ?: "Could not open the microphone"))
            return
        }

        _state.value = AssistantState.Listening(route)
        streamedReply = ""

        var finalText: String? = null
        try {
            recognition.listen(languageTag).collect { event ->
                when (event) {
                    is RecognitionEvent.ReadyForSpeech -> Unit

                    is RecognitionEvent.SpeechStarted ->
                        _state.update {
                            (it as? AssistantState.Listening)?.copy(speechDetected = true) ?: it
                        }

                    is RecognitionEvent.Partial ->
                        _state.update {
                            (it as? AssistantState.Listening)
                                ?.copy(partialTranscript = event.text, speechDetected = true) ?: it
                        }

                    is RecognitionEvent.Final -> finalText = event.text

                    is RecognitionEvent.Failed -> {
                        routes.release()
                        fail(AssistantError.Recognition(event.reason), event.recoverable)
                        return@collect
                    }
                }
            }
        } catch (error: Exception) {
            routes.release()
            fail(AssistantError.Recognition(error.message ?: "Recognition failed"))
            return
        }

        val text = finalText?.trim()
        if (text.isNullOrBlank()) {
            routes.release()
            if (_state.value !is AssistantState.Failed) {
                fail(AssistantError.Recognition("I didn't catch that"))
            }
            return
        }

        _state.value = AssistantState.Transcribing(text)
        pendingUserText = text

        // The route is released before the backend round trip. Holding an SCO
        // link open across an LLM call would burn battery on both devices for
        // the several seconds nobody is speaking.
        routes.release()

        _state.value = AssistantState.Processing(text)
        val sent = socket.send(ClientFrames.userMessage(text, sessionId, LANGUAGE_AUTO))
        if (!sent) {
            fail(AssistantError.Network("Not connected to Dax"))
        }
    }

    private suspend fun collectFrames() {
        socket.frames.collect { frame ->
            when (frame) {
                is ServerFrame.Message -> onAssistantMessage(frame)
                is ServerFrame.AgentEvent -> onAgentEvent(frame)
                is ServerFrame.ToolConfirmation -> onConfirmation(frame)
                is ServerFrame.Unknown -> Unit
            }
        }
    }

    private suspend fun onAssistantMessage(frame: ServerFrame.Message) {
        if (frame.sessionId != null && frame.sessionId != sessionId) return
        if (frame.role != "assistant") return

        val reply = frame.content
        _history.update { turns ->
            (turns + Turn(
                id = UUID.randomUUID().toString(),
                userText = pendingUserText,
                assistantText = reply,
                timestampMillis = System.currentTimeMillis(),
            )).takeLast(MAX_HISTORY)
        }

        val route = routes.activeRoute.value
        _state.value = AssistantState.Speaking(fullReply = reply, spokenText = reply, route = route)
        speaker.setLanguage(languageTag)
        speaker.speak(reply)

        // Only settle to idle if nothing else moved the machine on — a barge-in
        // during playback has already started the next turn.
        _state.update { if (it is AssistantState.Speaking) AssistantState.Idle else it }
        pendingUserText = ""
    }

    private fun onAgentEvent(frame: ServerFrame.AgentEvent) {
        if (frame.sessionId != null && frame.sessionId != sessionId) return
        val activity = when (frame.eventType) {
            "thinking" -> AgentActivity.Thinking
            "tool_call" -> AgentActivity.RunningTool(
                frame.toolName.orEmpty(),
                frame.serverName.orEmpty(),
            )

            "tool_result" -> AgentActivity.ToolFinished(
                frame.toolName.orEmpty(),
                frame.ok ?: true,
            )

            else -> null
        } ?: return

        _state.update { current ->
            (current as? AssistantState.Processing)?.copy(activity = activity) ?: current
        }
    }

    private fun onConfirmation(frame: ServerFrame.ToolConfirmation) {
        if (frame.sessionId != null && frame.sessionId != sessionId) return
        _state.value = AssistantState.AwaitingApproval(
            request = ApprovalRequest(
                approvalId = frame.approvalId,
                toolName = frame.toolName,
                serverName = frame.serverName,
                arguments = frame.arguments,
                options = frame.options,
                timeoutSeconds = frame.timeoutSeconds,
                requestedAtEpochMillis = System.currentTimeMillis(),
            ),
            transcript = pendingUserText,
            streamedReply = streamedReply,
        )
    }

    private suspend fun watchConnection() {
        socket.state.collect { connection ->
            when (connection) {
                is ConnectionState.Failed -> _state.update { current ->
                    // Never overwrite a live turn with a connection banner; the
                    // turn's own failure path will report it if it matters.
                    if (current is AssistantState.Idle || current is AssistantState.Disconnected) {
                        AssistantState.Disconnected(connection.reason, connection.retryInSeconds > 0)
                    } else {
                        current
                    }
                }

                is ConnectionState.Connected -> _state.update { current ->
                    if (current is AssistantState.Disconnected) AssistantState.Idle else current
                }

                else -> Unit
            }
        }
    }

    private fun fail(error: AssistantError, recoverable: Boolean = true) {
        _state.value = AssistantState.Failed(error, recoverable)
    }

    private companion object {
        const val TAG = "AssistantController"
        const val MAX_HISTORY = 40
        // The backend detects language per turn; pinning it here would break
        // the mixed Spanish/English use the agent already handles.
        const val LANGUAGE_AUTO = "auto"
    }
}
