package com.dax.assistant.audio

import com.dax.assistant.data.auth.AuthResult
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.data.protocol.VoiceFrame
import com.dax.assistant.data.transport.VoiceSocket
import com.dax.assistant.data.transport.VoiceSocketEvent
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient

sealed interface RemoteVoiceEvent {
    data class Listening(val level: Float, val speechDetected: Boolean) : RemoteVoiceEvent
    data object Transcribing : RemoteVoiceEvent
    data class Transcript(val text: String, val language: String?) : RemoteVoiceEvent
    data object Processing : RemoteVoiceEvent
    data class Speech(val text: String, val language: String?) : RemoteVoiceEvent
    data object Completed : RemoteVoiceEvent
}

class RemoteVoiceClient(
    private val client: OkHttpClient,
    private val credentials: CredentialStore,
    private val auth: BackendAuth,
    private val capture: NativeAudioCapture,
) {
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
                throw RemoteVoiceException("I didn't hear anything")
            }

            onEvent(RemoteVoiceEvent.Transcribing)
            socket.stop()
            var hasTranscript = false
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
                    else -> Unit
                }
            }
            stopped = true

            var hasSpeech = false
            withTimeout(RESPONSE_TIMEOUT_MILLIS) {
                while (true) {
                    when (val frame = nextFrame(socket)) {
                        is VoiceFrame.Transcript -> if (frame.final && frame.text.isNotBlank()) {
                            hasTranscript = true
                            onEvent(RemoteVoiceEvent.Transcript(frame.text, frame.language))
                            onEvent(RemoteVoiceEvent.Processing)
                        }
                        is VoiceFrame.Speech -> if (frame.text.isNotBlank()) {
                            hasSpeech = true
                            onEvent(RemoteVoiceEvent.Speech(frame.text, frame.language))
                        }
                        is VoiceFrame.State -> {
                            if (frame.state == "processing") onEvent(RemoteVoiceEvent.Processing)
                            if (frame.state in TERMINAL_STATES && hasTranscript && hasSpeech) break
                            if (frame.state == "idle" && !hasTranscript) {
                                throw RemoteVoiceException("Server could not transcribe the audio")
                            }
                        }
                        is VoiceFrame.Error -> throw RemoteVoiceException(frame.message)
                        is VoiceFrame.Level, is VoiceFrame.Speaker -> Unit
                        is VoiceFrame.Acquired, is VoiceFrame.Started, is VoiceFrame.Stopped,
                        VoiceFrame.Released -> throw RemoteVoiceException("Unexpected server voice frame")
                    }
                }
            }

            socket.release()
            awaitFrame<VoiceFrame.Released>(socket) {}
            released = true
            onEvent(RemoteVoiceEvent.Completed)
        } catch (timeout: TimeoutCancellationException) {
            throw RemoteVoiceException("Timed out waiting for the server voice response", timeout)
        } catch (error: RemoteVoiceException) {
            throw error
        } catch (error: Exception) {
            throw RemoteVoiceException(error.message ?: "Remote voice failed", error)
        } finally {
            // Closing an active socket invokes the backend's cancellation cleanup;
            // never turn silence or cancellation into a real stop that STT processes.
            if (stopped && !released) runCatching { socket.release() }
            socket.close(if (released) "turn complete" else "turn cancelled")
        }
    }

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

    private suspend fun nextFrame(socket: VoiceSocket): VoiceFrame = when (val event = socket.events.receive()) {
        is VoiceSocketEvent.Frame -> event.frame
        is VoiceSocketEvent.Closed -> throw RemoteVoiceException(event.reason)
    }

    private companion object {
        const val MAX_FRAME_BYTES = 3_200
        const val MAX_DURATION_SECONDS = 30
        const val CONTROL_TIMEOUT_MILLIS = 15_000L
        const val RESPONSE_TIMEOUT_MILLIS = 120_000L
        // Wait through the backend follow-up window. Releasing in "conversing"
        // would ask it to restore the local source while that source is active.
        val TERMINAL_STATES = setOf("idle")
    }
}

class RemoteVoiceException(message: String, cause: Throwable? = null) : Exception(message, cause)
