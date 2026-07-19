package com.dax.assistant.assistant

import com.dax.assistant.audio.AudioRoute

/**
 * The assistant's lifecycle.
 *
 * ```
 * Idle → ConnectingAudio → Listening → Transcribing → Processing
 *                                                        ├→ AwaitingApproval → Processing
 *                                                        └→ Speaking → Idle
 * ```
 *
 * Two states exist because of hardware reality rather than product design:
 *
 *  * [ConnectingAudio] — opening a Bluetooth SCO link takes a few hundred
 *    milliseconds. Without a state for it the UI would claim to be listening
 *    while the microphone was not yet live, and the user's first word would be
 *    lost. This is the single most common bug in voice apps on Bluetooth.
 *  * [Transcribing] — on-device recognition finishes measurably after the user
 *    stops speaking. Collapsing it into [Processing] would make the assistant
 *    look like it was thinking when it was still reading.
 *
 * [Disconnected] and [Failed] are not part of the happy path but are states,
 * not flags: a disconnected assistant must not render as idle, because idle
 * invites the user to speak into something that cannot hear them.
 */
sealed interface AssistantState {

    /** Nothing in progress. The only state from which a turn may start. */
    data object Idle : AssistantState

    /** Opening the audio route. [route] is the destination being opened. */
    data class ConnectingAudio(val route: AudioRoute) : AssistantState

    /**
     * Capturing speech.
     *
     * @param partialTranscript recognition so far, for live display
     * @param speechDetected whether VAD has heard voice yet; drives the
     *   "I can hear you" affordance and distinguishes a silent room from a
     *   broken microphone
     */
    data class Listening(
        val route: AudioRoute,
        val partialTranscript: String = "",
        val speechDetected: Boolean = false,
    ) : AssistantState

    /** Endpointed; finishing recognition. */
    data class Transcribing(val partialTranscript: String = "") : AssistantState

    /**
     * The backend is working.
     *
     * @param transcript what was sent, kept so the UI can keep showing it
     * @param activity the most recent agent event, e.g. a running tool
     * @param streamedReply assistant text accumulated so far
     */
    data class Processing(
        val transcript: String,
        val activity: AgentActivity? = null,
        val streamedReply: String = "",
    ) : AssistantState

    /**
     * A gated tool needs confirmation.
     *
     * Blocking here is the point: the backend fails the gate closed on
     * timeout, so a request that is never answered denies rather than runs.
     */
    data class AwaitingApproval(
        val request: ApprovalRequest,
        val transcript: String,
        val streamedReply: String = "",
    ) : AssistantState

    /** Speaking the reply. [spokenText] is the sentence currently audible. */
    data class Speaking(
        val fullReply: String,
        val spokenText: String = "",
        val route: AudioRoute,
    ) : AssistantState

    /** No usable backend connection. Distinct from [Idle] on purpose. */
    data class Disconnected(val reason: String, val reconnecting: Boolean) : AssistantState

    /** A turn failed. [recoverable] decides whether retry is offered. */
    data class Failed(val error: AssistantError, val recoverable: Boolean) : AssistantState

    /** Whether a new turn may begin. */
    val canStartTurn: Boolean
        get() = this is Idle || this is Failed || this is Speaking

    /**
     * Whether the user can cancel. True for every state that holds a
     * resource — a live microphone, an open socket, or a pending decision.
     */
    val cancellable: Boolean
        get() = this is ConnectingAudio || this is Listening || this is Transcribing ||
            this is Processing || this is AwaitingApproval || this is Speaking

    /** Whether the microphone is or is about to be live. Drives the UI indicator. */
    val microphoneActive: Boolean
        get() = this is ConnectingAudio || this is Listening
}

/** The most recent thing the agent reported doing. */
sealed interface AgentActivity {
    data object Thinking : AgentActivity
    data class RunningTool(val toolName: String, val serverName: String) : AgentActivity
    data class ToolFinished(val toolName: String, val ok: Boolean) : AgentActivity
}

/**
 * A pending tool confirmation.
 *
 * [arguments] is shown in full. A confirmation that hides what it authorizes
 * is not a confirmation, and this is the app's main defence against a prompt
 * injection talking the agent into a destructive call.
 */
data class ApprovalRequest(
    val approvalId: String,
    val toolName: String,
    val serverName: String,
    val arguments: Map<String, String>,
    val options: List<String>,
    val timeoutSeconds: Int,
    val requestedAtEpochMillis: Long,
)

/** A failure the user might need to act on. */
sealed interface AssistantError {
    data class Network(val detail: String) : AssistantError
    data class Authentication(val detail: String) : AssistantError
    data class Audio(val detail: String) : AssistantError
    data class Recognition(val detail: String) : AssistantError
    data class Backend(val detail: String) : AssistantError
    data object PermissionDenied : AssistantError
    data object Cancelled : AssistantError
}
