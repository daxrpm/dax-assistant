package com.dax.assistant.data.transport

import com.dax.assistant.capabilities.AndroidCapabilityExecutor
import com.dax.assistant.data.auth.CapabilityNodeAuth
import com.dax.assistant.data.auth.CapabilityNodeCredentialStore
import com.dax.assistant.data.auth.CapabilityTokenResult
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.data.protocol.CapabilityFrames
import com.dax.assistant.data.protocol.CapabilityServerFrame
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.ConcurrentHashMap
import kotlin.math.min
import kotlin.math.pow
import kotlin.random.Random
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeout
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

sealed interface CapabilityConnectionState {
    data object Disabled : CapabilityConnectionState
    data object Disconnected : CapabilityConnectionState
    data object Connecting : CapabilityConnectionState
    data class Connected(val generation: Int) : CapabilityConnectionState
    data class Failed(val reason: String, val retryInSeconds: Int) : CapabilityConnectionState
    data class Revoked(val reason: String) : CapabilityConnectionState
}

class CapabilityNodeSocket(
    private val client: OkHttpClient,
    private val clientCredentials: CredentialStore,
    private val credentials: CapabilityNodeCredentialStore,
    private val auth: CapabilityNodeAuth,
    private val executor: AndroidCapabilityExecutor,
    private val scope: CoroutineScope,
) {
    private val _state = MutableStateFlow<CapabilityConnectionState>(
        if (credentials.enabled) CapabilityConnectionState.Disconnected
        else CapabilityConnectionState.Disabled,
    )
    val state: StateFlow<CapabilityConnectionState> = _state.asStateFlow()

    private val shouldRun = AtomicBoolean(false)
    private val connectionEpoch = AtomicLong(0)
    @Volatile private var connectJob: Job? = null
    @Volatile private var socket: WebSocket? = null
    private var attempt = 0

    fun connect() {
        if (!credentials.enabled || !credentials.isEnrolled) return
        if (!shouldRun.compareAndSet(false, true)) return
        connectJob = scope.launch { runConnectionLoop() }
    }

    fun disconnect() {
        shouldRun.set(false)
        connectionEpoch.incrementAndGet()
        connectJob?.cancel()
        connectJob = null
        socket?.close(NORMAL_CLOSURE, "node disconnect")
        socket = null
        _state.value = if (credentials.enabled) CapabilityConnectionState.Disconnected
        else CapabilityConnectionState.Disabled
    }

    fun setEnabled(enabled: Boolean) {
        credentials.enabled = enabled
        if (enabled) connect() else disconnect()
    }

    /** Reconnects so the backend receives the inventory after a grant changes. */
    fun refreshInventory() {
        if (!credentials.enabled || !credentials.isEnrolled) return
        val current = socket
        if (current != null) current.close(NORMAL_CLOSURE, "inventory changed") else connect()
    }

    private suspend fun runConnectionLoop() {
        while (scope.isActive && shouldRun.get()) {
            _state.value = CapabilityConnectionState.Connecting
            when (val token = auth.accessToken()) {
                CapabilityTokenResult.NotEnrolled -> {
                    shouldRun.set(false)
                    _state.value = CapabilityConnectionState.Disconnected
                    return
                }
                is CapabilityTokenResult.Failed -> {
                    if (token.revoked) {
                        shouldRun.set(false)
                        _state.value = CapabilityConnectionState.Revoked(token.reason)
                        return
                    }
                    val wait = backoffSeconds(++attempt)
                    _state.value = CapabilityConnectionState.Failed(token.reason, wait)
                    delay(jitteredDelayMillis(wait))
                }
                is CapabilityTokenResult.Success -> {
                    val reason = openSocket(token.token.value, token.token.expiresInSeconds)
                    if (!shouldRun.get()) return
                    val wait = backoffSeconds(++attempt)
                    _state.value = CapabilityConnectionState.Failed(reason, wait)
                    delay(jitteredDelayMillis(wait))
                }
            }
        }
    }

    private suspend fun openSocket(token: String, expiresInSeconds: Int): String = coroutineScope {
        val epoch = connectionEpoch.incrementAndGet()
        fun isCurrentConnection(): Boolean = shouldRun.get() && connectionEpoch.get() == epoch
        val wsUrl = clientCredentials.backendUrl.replaceFirst(
            Regex("^https?"),
            if (clientCredentials.backendUrl.startsWith("https")) "wss" else "ws",
        ) + "/ws/capabilities"
        val incoming = Channel<String>(capacity = FRAME_BUFFER_CAPACITY)
        val closed = CompletableDeferred<String>()
        val work = ConcurrentHashMap.newKeySet<Job>()
        val seenRequests = mutableSetOf<String>()
        val inFlight = AtomicInteger(0)
        var activeGeneration = 0
        val request = Request.Builder().url(wsUrl)
            .header("Authorization", "Bearer $token")
            .build()

        val webSocket = client.newWebSocket(
            request,
            object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    if (!isCurrentConnection()) {
                        webSocket.cancel()
                        return
                    }
                    socket = webSocket
                    val hello = CapabilityFrames.hello(credentials.nodeName, executor.tools)
                    if (!isCurrentConnection()) {
                        webSocket.cancel()
                        return
                    }
                    if (!webSocket.send(hello)) closed.complete("Could not send node hello")
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    if (!isCurrentConnection()) return
                    if (!incoming.trySend(text).isSuccess) {
                        closed.complete("Capability frame buffer overflow")
                        webSocket.close(POLICY_VIOLATION, "frame buffer overflow")
                    }
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    if (isCurrentConnection() && (response?.code == 401 || response?.code == 403)) {
                        credentials.invalidateToken()
                    }
                    closed.complete(t.message ?: "Capability connection lost")
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    if (isCurrentConnection() && code == POLICY_VIOLATION) credentials.invalidateToken()
                    closed.complete(reason.ifBlank { "Capability connection closed" })
                }
            },
        )
        if (isCurrentConnection()) socket = webSocket else webSocket.cancel()

        val receiver = launch {
            for (raw in incoming) {
                if (!isCurrentConnection()) return@launch
                when (val frame = CapabilityFrames.parse(raw)) {
                    null -> {
                        closed.complete("Malformed capability frame")
                        webSocket.close(POLICY_VIOLATION, "malformed frame")
                        return@launch
                    }
                    CapabilityServerFrame.Heartbeat -> webSocket.send(CapabilityFrames.heartbeat())
                    CapabilityServerFrame.Ignored -> Unit
                    is CapabilityServerFrame.Ready -> {
                        if (!isCurrentConnection()) return@launch
                        if (activeGeneration != 0 && activeGeneration != frame.generation) {
                            closed.complete("Capability generation changed unexpectedly")
                            webSocket.close(POLICY_VIOLATION, "generation mismatch")
                            continue
                        }
                        activeGeneration = frame.generation
                        attempt = 0
                        _state.value = CapabilityConnectionState.Connected(frame.generation)
                    }
                    is CapabilityServerFrame.Execute -> {
                        if (!isCurrentConnection()) return@launch
                        if (activeGeneration == 0) activeGeneration = frame.generation
                        if (frame.generation != activeGeneration) continue
                        if (!seenRequests.add(frame.requestId)) {
                            closed.complete("Duplicate capability request")
                            webSocket.close(POLICY_VIOLATION, "duplicate request")
                            continue
                        }
                        if (inFlight.incrementAndGet() > MAX_IN_FLIGHT) {
                            inFlight.decrementAndGet()
                            webSocket.send(
                                CapabilityFrames.result(
                                    frame.generation,
                                    frame.requestId,
                                    false,
                                    error = "Node is busy",
                                ),
                            )
                            continue
                        }
                        val job = launch {
                            try {
                                val result = withTimeout(frame.timeoutSeconds * 1_000L) {
                                    executor.execute(frame)
                                }
                                webSocket.send(
                                    CapabilityFrames.result(
                                        frame.generation,
                                        frame.requestId,
                                        result.success,
                                        result.content,
                                        result.error,
                                    ),
                                )
                            } catch (_: kotlinx.coroutines.TimeoutCancellationException) {
                                webSocket.send(
                                    CapabilityFrames.result(
                                        frame.generation,
                                        frame.requestId,
                                        false,
                                        error = "Execution timed out",
                                    ),
                                )
                            } finally {
                                inFlight.decrementAndGet()
                            }
                        }
                        work += job
                        job.invokeOnCompletion { work -= job }
                    }
                }
            }
        }
        val heartbeat = launch {
            while (isActive) {
                delay(HEARTBEAT_MILLIS)
                if (!webSocket.send(CapabilityFrames.heartbeat())) {
                    closed.complete("Could not send capability heartbeat")
                }
            }
        }
        val refresh = launch {
            delay(((expiresInSeconds - 30).coerceAtLeast(1)) * 1_000L)
            closed.complete("Refreshing capability token")
            webSocket.close(NORMAL_CLOSURE, "token refresh")
        }

        try {
            closed.await()
        } finally {
            incoming.cancel()
            receiver.cancelAndJoin()
            heartbeat.cancelAndJoin()
            refresh.cancelAndJoin()
            val pendingWork = work.toList()
            pendingWork.forEach { it.cancel() }
            pendingWork.forEach { it.join() }
            webSocket.cancel()
            if (socket === webSocket) socket = null
        }
    }

    private companion object {
        const val NORMAL_CLOSURE = 1000
        const val POLICY_VIOLATION = 1008
        const val FRAME_BUFFER_CAPACITY = 64
        const val MAX_IN_FLIGHT = 4
        const val HEARTBEAT_MILLIS = 20_000L
    }
}

internal fun backoffSeconds(attempt: Int): Int =
    min(60, 2.0.pow((attempt - 1).coerceIn(0, 10)).toInt())

internal fun jitteredDelayMillis(seconds: Int): Long =
    (seconds * 1_000L * Random.nextDouble(0.8, 1.2)).toLong()
