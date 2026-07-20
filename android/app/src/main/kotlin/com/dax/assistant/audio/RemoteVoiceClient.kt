package com.dax.assistant.audio

import com.dax.assistant.data.auth.AuthResult
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.data.protocol.VoiceFrame
import com.dax.assistant.data.transport.VoiceSocket
import com.dax.assistant.data.transport.VoiceSocketEvent
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient
import java.util.concurrent.atomic.AtomicReference

sealed interface RemoteVoiceEvent {
    data class Listening(val level: Float, val speechDetected: Boolean) : RemoteVoiceEvent
    data object Transcribing : RemoteVoiceEvent
    data class Transcript(val text: String, val language: String?) : RemoteVoiceEvent
    data object Processing : RemoteVoiceEvent
    data class Speech(val text: String, val language: String?) : RemoteVoiceEvent
    data class Approval(
        val approvalId: String,
        val toolName: String,
        val serverName: String,
        val arguments: Map<String, String>,
        val options: List<String>,
        val timeoutSeconds: Int,
    ) : RemoteVoiceEvent
    data object Completed : RemoteVoiceEvent
}

class RemoteVoiceClient(
    private val client: OkHttpClient,
    private val credentials: CredentialStore,
    private val auth: BackendAuth,
    private val capture: NativeAudioCapture,
) {
    private val activeSocket = AtomicReference<VoiceSocket?>(null)
    private val activeApproval = AtomicReference<VoiceFrame.ApprovalRequest?>(null)

    fun resolveApproval(approvalId: String, decision: String): Boolean {
        val pending = activeApproval.get()
        if (pending?.approvalId != approvalId || decision !in pending.options + "deny") return false
        if (!activeApproval.compareAndSet(pending, null)) return false
        return runCatching {
            activeSocket.get()?.approve(approvalId, decision)
                ?: error("Remote voice socket is closed")
            true
        }.getOrDefault(false)
    }

    /** Invalidates delivery only; backend agent/tool work may continue. */
    fun interruptCurrent(): Boolean = runCatching {
        activeSocket.get()?.interrupt() ?: return false
        true
    }.getOrDefault(false)

    suspend fun runTurn(onEvent: suspend (RemoteVoiceEvent) -> Unit) {
        val token = when (val result = auth.accessToken()) {
            is AuthResult.Success -> result.token
            is AuthResult.Failed -> throw RemoteVoiceException(result.reason)
            AuthResult.NotEnrolled -> throw RemoteVoiceException("This device is not paired")
        }
        val socket = VoiceSocket(client)
        var stopped = false
        var released = false
        try {
            socket.connect(credentials.backendUrl, token)
            activeSocket.set(socket)
            socket.acquire()
            val acquired = awaitFrame<VoiceFrame.Acquired>(socket) {}
            check(
                acquired.maxFrameBytes >= MAX_FRAME_BYTES &&
                    acquired.maxDurationSeconds >= MAX_DURATION_SECONDS &&
                    acquired.outputMode == "client_text",
            ) { "Backend did not accept the required remote voice contract" }

            socket.start()
            awaitFrame<VoiceFrame.Started>(socket) {}
            val captureResult = capture.capture(
                onFrame = socket::sendAudio,
                onLevel = { level, speech ->
                    onEvent(RemoteVoiceEvent.Listening(level, speech))
                },
            )
            if (captureResult == CaptureResult.NoSpeech) {
                throw RemoteNoSpeechException()
            }

            onEvent(RemoteVoiceEvent.Transcribing)
            socket.stop()
            var hasTranscript = false
            var hasSpeech = false
            var turnComplete = false
            awaitFrame<VoiceFrame.Stopped>(socket) { frame ->
                when (frame) {
                    is VoiceFrame.Transcript -> if (frame.final && frame.text.isNotBlank()) {
                        hasTranscript = true
                        onEvent(RemoteVoiceEvent.Transcript(frame.text, frame.language))
                        onEvent(RemoteVoiceEvent.Processing)
                    }
                    is VoiceFrame.State -> if (frame.state == "processing") {
                        onEvent(RemoteVoiceEvent.Processing)
                    }
                    is VoiceFrame.Speech -> if (frame.text.isNotBlank()) {
                        hasSpeech = true
                        onEvent(RemoteVoiceEvent.Speech(frame.text, frame.language))
                    }
                    is VoiceFrame.TurnComplete -> turnComplete = true
                    is VoiceFrame.ApprovalRequest -> {
                        activeApproval.set(frame)
                        onEvent(frame.toRemoteEvent())
                    }
                    else -> Unit
                }
            }
            stopped = true

            withTimeout(RESPONSE_TIMEOUT_MILLIS) {
                while (true) {
                    if (turnComplete && hasTranscript && hasSpeech) break
                    val next = if (turnComplete) {
                        // Completion and speech are emitted by adjacent backend
                        // tasks. Give an already completed turn a short drain
                        // window, then finish cleanly even if it has no speech.
                        withTimeoutOrNull(TURN_COMPLETION_GRACE_MILLIS) { nextFrame(socket) } ?: break
                    } else {
                        nextFrame(socket)
                    }
                    when (val frame = next) {
                        is VoiceFrame.Transcript -> if (frame.final && frame.text.isNotBlank()) {
                            hasTranscript = true
                            onEvent(RemoteVoiceEvent.Transcript(frame.text, frame.language))
                            onEvent(RemoteVoiceEvent.Processing)
                        }
                        is VoiceFrame.Speech -> if (frame.text.isNotBlank()) {
                            hasSpeech = true
                            onEvent(RemoteVoiceEvent.Speech(frame.text, frame.language))
                        }
                        is VoiceFrame.TurnComplete -> turnComplete = true
                        is VoiceFrame.ApprovalRequest -> {
                            activeApproval.set(frame)
                            onEvent(frame.toRemoteEvent())
                        }
                        is VoiceFrame.State -> {
                            if (frame.state == "processing") onEvent(RemoteVoiceEvent.Processing)
                        }
                        is VoiceFrame.Error -> throw RemoteVoiceException(frame.message)
                        is VoiceFrame.Interrupted -> throw RemoteTurnInterruptedException()
                        is VoiceFrame.Level, is VoiceFrame.Speaker -> Unit
                        is VoiceFrame.Acquired, is VoiceFrame.Started, is VoiceFrame.Stopped,
                        VoiceFrame.Released -> throw RemoteVoiceException("Unexpected server voice frame")
                    }
                    // The backend can publish speech and completion from
                    // adjacent tasks, so either ordering is valid.
                }
            }

            socket.release()
            awaitFrame<VoiceFrame.Released>(socket) {}
            released = true
            onEvent(RemoteVoiceEvent.Completed)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: RemoteVoiceException) {
            throw error
        } catch (error: Exception) {
            throw remoteVoiceFailure(error)
        } finally {
            activeSocket.compareAndSet(socket, null)
            activeApproval.set(null)
            // Closing an active socket invokes the backend's cancellation cleanup;
            // never turn silence or cancellation into a real stop that STT processes.
            if (stopped && !released) runCatching { socket.release() }
            socket.close(if (released) "turn complete" else "turn cancelled")
        }
    }

    private fun VoiceFrame.ApprovalRequest.toRemoteEvent() = RemoteVoiceEvent.Approval(
        approvalId, toolName, serverName, arguments, options, timeoutSeconds,
    )

    private suspend inline fun <reified T : VoiceFrame> awaitFrame(
        socket: VoiceSocket,
        crossinline onOther: suspend (VoiceFrame) -> Unit,
    ): T = withTimeout(CONTROL_TIMEOUT_MILLIS) {
        while (true) {
            val frame = nextFrame(socket)
            if (frame is VoiceFrame.Error) throw RemoteVoiceException(frame.message)
            if (frame is T) return@withTimeout frame
            onOther(frame)
        }
        error("unreachable")
    }

    private suspend fun nextFrame(socket: VoiceSocket): VoiceFrame {
        val result = socket.events.receiveCatching()
        val event = result.getOrNull()
            ?: throw RemoteVoiceException(result.exceptionOrNull()?.message ?: "Voice socket closed")
        return when (event) {
        is VoiceSocketEvent.Frame -> event.frame
        is VoiceSocketEvent.Closed -> throw RemoteVoiceException(
            event.reason.ifBlank { "Voice socket closed (${event.code})" },
        )
        }
    }

    private companion object {
        const val MAX_FRAME_BYTES = 3_200
        const val MAX_DURATION_SECONDS = 30
        const val CONTROL_TIMEOUT_MILLIS = 15_000L
        const val RESPONSE_TIMEOUT_MILLIS = 120_000L
        const val TURN_COMPLETION_GRACE_MILLIS = 10_000L
    }
}

open class RemoteVoiceException(message: String, cause: Throwable? = null) : Exception(message, cause)

class RemoteNoSpeechException : RemoteVoiceException("I didn't hear anything")

class RemoteTurnInterruptedException : RemoteVoiceException("Remote turn delivery interrupted")

internal fun remoteVoiceFailure(error: Exception): Exception = when (error) {
    is CancellationException -> error
    is RemoteVoiceException -> error
    else -> RemoteVoiceException(error.message ?: "Remote voice failed", error)
}
