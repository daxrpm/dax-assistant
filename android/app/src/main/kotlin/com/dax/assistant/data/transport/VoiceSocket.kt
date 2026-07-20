package com.dax.assistant.data.transport

import com.dax.assistant.data.protocol.VoiceFrame
import com.dax.assistant.data.protocol.VoiceFrames
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString

sealed interface VoiceSocketEvent {
    data class Frame(val frame: VoiceFrame) : VoiceSocketEvent
    data class Closed(val reason: String) : VoiceSocketEvent
}

class VoiceSocket(private val client: OkHttpClient) {
    private enum class Phase { NEW, OPEN, ACQUIRING, ACQUIRED, STARTING, STREAMING, STOPPING, STOPPED, RELEASING, CLOSED }

    private val phase = AtomicReference(Phase.NEW)
    private val opened = CompletableDeferred<Unit>()
    private val buffer = Channel<VoiceSocketEvent>(64)
    val events: ReceiveChannel<VoiceSocketEvent> = buffer
    private var socket: WebSocket? = null

    suspend fun connect(baseUrl: String, token: String) {
        check(phase.compareAndSet(Phase.NEW, Phase.OPEN)) { "Voice socket already used" }
        val url = baseUrl.replaceFirst(
            Regex("^https?"),
            if (baseUrl.startsWith("https")) "wss" else "ws",
        ) + "/ws/voice"
        val request = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer $token")
            .build()
        socket = client.newWebSocket(request, listener)
        withTimeout(CONNECT_TIMEOUT_MILLIS) { opened.await() }
    }

    fun acquire() = sendControl(Phase.OPEN, Phase.ACQUIRING, VoiceFrames.acquire())
    fun start() = sendControl(Phase.ACQUIRED, Phase.STARTING, VoiceFrames.start())
    fun stop() = sendControl(Phase.STREAMING, Phase.STOPPING, VoiceFrames.stop())
    fun release() = sendControl(Phase.STOPPED, Phase.RELEASING, VoiceFrames.release())

    fun sendAudio(bytes: ByteArray) {
        check(bytes.isNotEmpty() && bytes.size <= MAX_FRAME_BYTES) { "PCM frame exceeds 3200 bytes" }
        check(phase.get() == Phase.STREAMING) { "Voice stream is not started" }
        val current = socket ?: error("Voice socket is closed")
        check(current.queueSize() <= MAX_QUEUED_BYTES) { "Voice socket backpressure limit reached" }
        check(current.send(bytes.toByteString())) { "Voice socket rejected PCM" }
    }

    fun close(reason: String = "turn complete") {
        val previous = phase.getAndSet(Phase.CLOSED)
        if (previous != Phase.CLOSED) socket?.close(NORMAL_CLOSURE, reason)
        socket = null
        buffer.close()
    }

    private fun sendControl(expected: Phase, next: Phase, payload: String) {
        check(phase.compareAndSet(expected, next)) { "Invalid voice control order: ${phase.get()}" }
        check(socket?.send(payload) == true) { "Voice socket rejected control frame" }
    }

    private fun accept(frame: VoiceFrame) {
        val valid = when (frame) {
            is VoiceFrame.Acquired -> phase.compareAndSet(Phase.ACQUIRING, Phase.ACQUIRED)
            is VoiceFrame.Started -> phase.compareAndSet(Phase.STARTING, Phase.STREAMING)
            is VoiceFrame.Stopped -> phase.compareAndSet(Phase.STOPPING, Phase.STOPPED)
            VoiceFrame.Released -> phase.compareAndSet(Phase.RELEASING, Phase.OPEN)
            is VoiceFrame.State, is VoiceFrame.Transcript, is VoiceFrame.Speech,
            is VoiceFrame.Error, is VoiceFrame.Level, is VoiceFrame.Speaker -> true
        }
        if (!valid || !buffer.trySend(VoiceSocketEvent.Frame(frame)).isSuccess) {
            protocolFailure("Unexpected or overflowing voice frame: ${frame::class.simpleName}")
        }
    }

    private fun protocolFailure(reason: String) {
        buffer.trySend(VoiceSocketEvent.Closed(reason))
        socket?.close(PROTOCOL_ERROR, reason.take(123))
        phase.set(Phase.CLOSED)
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            opened.complete(Unit)
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            runCatching { VoiceFrames.parse(text) }
                .onSuccess(::accept)
                .onFailure { protocolFailure(it.message ?: "Malformed voice frame") }
        }

        override fun onFailure(webSocket: WebSocket, error: Throwable, response: Response?) {
            val reason = if (response?.code == 401 || response?.code == 403) {
                "Voice authentication rejected"
            } else {
                error.message ?: "Voice connection failed"
            }
            opened.completeExceptionally(IllegalStateException(reason, error))
            phase.set(Phase.CLOSED)
            buffer.trySend(VoiceSocketEvent.Closed(reason))
            buffer.close()
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            phase.set(Phase.CLOSED)
            buffer.trySend(VoiceSocketEvent.Closed(reason.ifBlank { "Voice socket closed ($code)" }))
            buffer.close()
        }
    }

    private companion object {
        const val MAX_FRAME_BYTES = 3_200
        const val MAX_QUEUED_BYTES = 32_000L
        const val CONNECT_TIMEOUT_MILLIS = 15_000L
        const val NORMAL_CLOSURE = 1000
        const val PROTOCOL_ERROR = 1002
    }
}
