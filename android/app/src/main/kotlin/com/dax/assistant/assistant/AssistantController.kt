package com.dax.assistant.assistant

import com.dax.assistant.audio.AudioRouteManager
import com.dax.assistant.audio.RecognitionEvent
import com.dax.assistant.audio.RemoteVoiceClient
import com.dax.assistant.audio.RemoteVoiceEvent
import com.dax.assistant.audio.Speaker
import com.dax.assistant.audio.SpeechRecognition
import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.data.protocol.ClientFrames
import com.dax.assistant.data.protocol.ServerFrame
import com.dax.assistant.data.transport.ChatSocket
import com.dax.assistant.data.transport.ConnectionState
import com.dax.assistant.preferences.AppPreferences
import com.dax.assistant.preferences.RecognitionMode
import java.util.UUID
import kotlinx.coroutines.CancellationException
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
    private val remoteVoice: RemoteVoiceClient,
    private val speaker: Speaker,
    private val scope: CoroutineScope,
    val sessionId: String,
    private val preferences: AppPreferences,
) {

    private val _state = MutableStateFlow<AssistantState>(AssistantState.Idle)
    val state: StateFlow<AssistantState> = _state.asStateFlow()

    private val _history = MutableStateFlow<List<Turn>>(emptyList())
    val history: StateFlow<List<Turn>> = _history.asStateFlow()

    private var turnJob: Job? = null
    private var playbackJob: Job? = null
    private var pendingUserText: String = ""
    private var streamedReply: String = ""
    private var acceptingResponse = false

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
        playbackJob?.cancel()
        turnJob?.cancel()
        turnJob = scope.launch { runTurn() }
    }

    /** Cancels whatever is in flight and returns to rest. */
    fun cancel() {
        turnJob?.cancel()
        turnJob = null
        playbackJob?.cancel()
        playbackJob = null
        speaker.stop()
        routes.release()
        streamedReply = ""
        pendingUserText = ""
        acceptingResponse = false
        _state.value = AssistantState.Idle
    }

    /** Answers a pending tool confirmation. */
    fun resolveApproval(decision: String) {
        val current = _state.value as? AssistantState.AwaitingApproval ?: return
        val sent = socket.send(
            ClientFrames.toolConfirmation(current.request.approvalId, decision, sessionId),
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
        pendingUserText = ""

        try {
            when (preferences.state.value.recognitionMode) {
                RecognitionMode.ANDROID -> runAndroidTurn()
                RecognitionMode.SERVER -> runRemoteTurn(route)
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            fail(AssistantError.Backend(error.message ?: "Remote voice failed"))
        } finally {
            routes.release()
        }
    }

    private suspend fun runAndroidTurn() {
        var finalText: String? = null
        try {
            recognition.listen(currentLanguageTag()).collect { event ->
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
                        fail(AssistantError.Recognition(event.reason), event.recoverable)
                        return@collect
                    }
                }
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            fail(AssistantError.Recognition(error.message ?: "Recognition failed"))
            return
        }

        val text = finalText?.trim()
        if (text.isNullOrBlank()) {
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
        acceptingResponse = true
        val sent = socket.send(ClientFrames.userMessage(text, sessionId, LANGUAGE_AUTO))
        if (!sent) {
            acceptingResponse = false
            fail(AssistantError.Network("Not connected to Dax"))
        }
    }

    private suspend fun runRemoteTurn(route: com.dax.assistant.audio.AudioRoute) {
        remoteVoice.runTurn { event ->
            when (event) {
                is RemoteVoiceEvent.Listening -> _state.update { current ->
                    (current as? AssistantState.Listening)?.copy(
                        route = route,
                        speechDetected = event.speechDetected,
                        inputLevel = event.level,
                    ) ?: current
                }
                RemoteVoiceEvent.Transcribing -> {
                    routes.release()
                    _state.value = AssistantState.Transcribing(pendingUserText)
                }
                is RemoteVoiceEvent.Transcript -> {
                    pendingUserText = event.text.trim()
                    _state.value = AssistantState.Transcribing(pendingUserText)
                }
                RemoteVoiceEvent.Processing ->
                    _state.value = AssistantState.Processing(pendingUserText, streamedReply = streamedReply)
                is RemoteVoiceEvent.Speech -> {
                    val sentence = event.text.trim()
                    if (sentence.isBlank()) return@runTurn
                    streamedReply = listOf(streamedReply, sentence)
                        .filter { it.isNotBlank() }
                        .joinToString(" ")
                    _state.value = AssistantState.Speaking(
                        fullReply = streamedReply,
                        spokenText = sentence,
                        route = routes.activeRoute.value,
                    )
                    speaker.setLanguage(event.language?.takeIf { it.isNotBlank() } ?: currentLanguageTag())
                    speaker.speak(sentence)
                }
                RemoteVoiceEvent.Completed -> {
                    if (pendingUserText.isNotBlank() && streamedReply.isNotBlank()) {
                        appendHistory(pendingUserText, streamedReply)
                    }
                    pendingUserText = ""
                    streamedReply = ""
                    _state.value = AssistantState.Idle
                }
            }
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

    private fun onAssistantMessage(frame: ServerFrame.Message) {
        if (frame.sessionId != sessionId || !acceptingResponse) return
        if (frame.role != "assistant") return
        acceptingResponse = false

        val reply = frame.content
        appendHistory(pendingUserText, reply)

        val route = routes.activeRoute.value
        _state.value = AssistantState.Speaking(fullReply = reply, spokenText = reply, route = route)
        speaker.setLanguage(currentLanguageTag())
        pendingUserText = ""
        playbackJob?.cancel()
        playbackJob = scope.launch {
            speaker.speak(reply)
            // Barge-in may already have moved the machine to the next turn.
            _state.update { if (it is AssistantState.Speaking) AssistantState.Idle else it }
        }
    }

    private fun onAgentEvent(frame: ServerFrame.AgentEvent) {
        if (frame.sessionId != sessionId || !acceptingResponse) return
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

    private fun currentLanguageTag(): String {
        val state = preferences.state.value
        return state.recognitionLanguage.languageTag(state.appLanguage)
    }

    private fun appendHistory(userText: String, assistantText: String) {
        _history.update { turns ->
            (turns + Turn(
                id = UUID.randomUUID().toString(),
                userText = userText,
                assistantText = assistantText,
                timestampMillis = System.currentTimeMillis(),
            )).takeLast(MAX_HISTORY)
        }
    }

    private fun onConfirmation(frame: ServerFrame.ToolConfirmation) {
        if (frame.sessionId != sessionId || !acceptingResponse) return
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
