package com.dax.assistant.data.transport

import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.data.auth.AuthResult
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.data.protocol.FrameParser
import com.dax.assistant.data.protocol.ClientFrames
import com.dax.assistant.data.protocol.ServerFrame
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.min
import kotlin.math.pow
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlin.random.Random
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

sealed interface ConnectionState {
    data object Disconnected : ConnectionState
    data object Connecting : ConnectionState
    data object Connected : ConnectionState
    data class Failed(val reason: String, val retryInSeconds: Int) : ConnectionState
}

/**
 * The chat WebSocket, kept alive across the app's lifetime.
 *
 * Reconnection is the whole job. A phone loses its network constantly — walking
 * out of Wi-Fi, dozing, switching cells — and an assistant that needs manual
 * reconnection after each is not an assistant. Backoff is exponential and
 * capped, and reconnection is silent until it has failed long enough that the
 * user would want to know.
 *
 * Frames arrive as a [SharedFlow] rather than a callback so the state machine
 * can collect them with structured concurrency and drop them cleanly when the
 * conversation ends.
 */
class ChatSocket(
    private val client: OkHttpClient,
    private val credentials: CredentialStore,
    private val auth: BackendAuth,
    private val scope: CoroutineScope,
) {

    private val _state = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val _frames = MutableSharedFlow<ServerFrame>(extraBufferCapacity = 64)
    val frames: SharedFlow<ServerFrame> = _frames.asSharedFlow()

    private val sessionLock = Any()
    private val retainedSessions = linkedMapOf<String, Int>()

    private var socket: WebSocket? = null
    private var connectJob: Job? = null
    private val shouldRun = AtomicBoolean(false)
    private var attempt = 0

    fun connect() {
        if (!shouldRun.compareAndSet(false, true)) return
        connectJob = scope.launch { runConnectionLoop() }
    }

    fun disconnect() {
        shouldRun.set(false)
        connectJob?.cancel()
        socket?.close(NORMAL_CLOSURE, "client disconnect")
        socket = null
        _state.value = ConnectionState.Disconnected
    }

    /** Queues text for the backend. False when the socket is not up. */
    fun send(payload: String): Boolean = socket?.send(payload) ?: false

    /** Retains a routed session. The backend allows at most 32 per socket. */
    fun retainSession(sessionId: String): Boolean {
        if (sessionId.isBlank()) return false
        val shouldSubscribe = synchronized(sessionLock) {
            val count = retainedSessions[sessionId]
            if (count == null && retainedSessions.size >= MAX_SESSIONS) return false
            retainedSessions[sessionId] = (count ?: 0) + 1
            count == null
        }
        if (shouldSubscribe) send(ClientFrames.sessionSubscription(listOf(sessionId), true))
        return true
    }

    fun releaseSession(sessionId: String) {
        val shouldUnsubscribe = synchronized(sessionLock) {
            val count = retainedSessions[sessionId] ?: return
            if (count > 1) {
                retainedSessions[sessionId] = count - 1
                false
            } else {
                retainedSessions.remove(sessionId)
                true
            }
        }
        if (shouldUnsubscribe) send(ClientFrames.sessionSubscription(listOf(sessionId), false))
    }

    private suspend fun runConnectionLoop() {
        while (scope.isActive && shouldRun.get()) {
            _state.value = ConnectionState.Connecting

            when (val token = auth.accessToken()) {
                is AuthResult.NotEnrolled -> {
                    // Nothing to retry: this needs the user to pair the device.
                    _state.value = ConnectionState.Failed("This device is not paired yet", 0)
                    shouldRun.set(false)
                    return
                }

                is AuthResult.Failed -> {
                    val wait = backoffSeconds(++attempt)
                    _state.value = ConnectionState.Failed(token.reason, wait)
                    delay(jitteredDelayMillis(wait))
                    continue
                }

                is AuthResult.Success -> {
                    val closed = openSocket(token.token)
                    if (!shouldRun.get()) return
                    val wait = backoffSeconds(++attempt)
                    _state.value = ConnectionState.Failed(closed, wait)
                    delay(jitteredDelayMillis(wait))
                }
            }
        }
    }

    /** Opens the socket and suspends until it closes, returning why. */
    private suspend fun openSocket(token: String): String = coroutineScope {
        val base = credentials.backendUrl
        val wsUrl = base.replaceFirst(
            Regex("^https?"),
            if (base.startsWith("https")) "wss" else "ws",
        ) + "/ws/chat"
        val request = Request.Builder()
            .url(wsUrl)
            .header("Authorization", "Bearer $token")
            .build()

        val closeReason = kotlinx.coroutines.CompletableDeferred<String>()
        // This queue belongs to exactly one WebSocket generation. Closing that
        // generation cancels queued delivery before a reconnect can start.
        val frameBuffer = Channel<ServerFrame>(capacity = FRAME_BUFFER_CAPACITY)
        val deliveryJob = launch {
            for (frame in frameBuffer) _frames.emit(frame)
        }

        socket = client.newWebSocket(
            request,
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    DaxLog.i(TAG, "Chat socket open")
                    attempt = 0
                    _state.value = ConnectionState.Connected
                    val sessions = synchronized(sessionLock) { retainedSessions.keys.toList() }
                    if (sessions.isNotEmpty()) {
                        webSocket.send(ClientFrames.sessionSubscription(sessions, true))
                    }
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    FrameParser.parse(text)?.let { frame ->
                        if (frame is ServerFrame.Unknown) return
                        if (frame.isTransientChatFrame()) {
                            // Activity is transient and may be dropped under pressure.
                            frameBuffer.trySend(frame)
                        } else {
                            // Backpressure the serialized OkHttp callback rather than
                            // spawning unbounded application-scope delivery jobs.
                            val delivered = runCatching {
                                runBlocking { frameBuffer.send(frame) }
                            }.isSuccess
                            if (!delivered) {
                                DaxLog.i(TAG, "Discarded critical frame from closed connection")
                            }
                        }
                    }
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    DaxLog.w(TAG, "Chat socket failed: ${t.message}")
                    if (response?.code == 401 || response?.code == 403) {
                        // The token was rejected — force a fresh one rather
                        // than reconnecting with the same dead credential.
                        credentials.invalidateToken()
                    }
                    closeReason.complete(t.message ?: "Connection lost")
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    if (code == POLICY_VIOLATION) credentials.invalidateToken()
                    closeReason.complete(reason.ifBlank { "Connection closed" })
                }
            },
        )

        try {
            closeReason.await()
        } finally {
            frameBuffer.cancel()
            deliveryJob.cancelAndJoin()
            socket?.cancel()
            socket = null
        }
    }

    /** 1s, 2s, 4s… capped, so a long outage does not become a hot loop. */
    private fun backoffSeconds(attempt: Int): Int =
        min(MAX_BACKOFF_SECONDS, 2.0.pow((attempt - 1).coerceIn(0, 10)).toInt())

    private fun jitteredDelayMillis(seconds: Int): Long =
        (seconds * 1_000L * Random.nextDouble(0.8, 1.2)).toLong()

    private companion object {
        const val TAG = "ChatSocket"
        const val NORMAL_CLOSURE = 1000
        const val POLICY_VIOLATION = 1008
        const val MAX_BACKOFF_SECONDS = 30
        const val MAX_SESSIONS = 32
        const val FRAME_BUFFER_CAPACITY = 128
    }
}

internal fun ServerFrame.isTransientChatFrame(): Boolean =
    this is ServerFrame.AgentEvent && eventType != "done"
