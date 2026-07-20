package com.dax.assistant.data.conversations

import com.dax.assistant.data.protocol.ClientFrames
import com.dax.assistant.data.protocol.ServerFrame
import com.dax.assistant.data.transport.ChatSocket
import com.dax.assistant.data.transport.ConnectionState
import com.dax.assistant.di.AppScope
import java.time.Instant
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive

@Singleton
class ChatRepository @Inject constructor(
    private val socket: ChatSocket,
    @AppScope scope: CoroutineScope,
) {
    private data class Store(
        val state: MutableStateFlow<ConversationChatState>,
        var references: Int = 0,
        var lastUsed: Long = 0,
    )

    private val lock = Any()
    private val stores = linkedMapOf<String, Store>()
    private var sequence = 0L

    val connection: StateFlow<ConnectionState> = socket.state

    init {
        scope.launch { socket.frames.collect(::dispatch) }
    }

    fun retain(
        sessionId: String,
        initialMessages: List<ChatMessage> = emptyList(),
    ): StateFlow<ConversationChatState>? {
        if (sessionId.isBlank()) return null
        val store = synchronized(lock) {
            val existing = stores[sessionId]
            if (existing != null) {
                existing.references++
                existing.lastUsed = ++sequence
                if (initialMessages.isNotEmpty() && existing.state.value.messages.isEmpty()) {
                    existing.state.value = existing.state.value.copy(
                        messages = initialMessages.takeLast(MAX_MESSAGES),
                    )
                }
                existing
            } else {
                evictIfNeeded() ?: return null
                Store(
                    MutableStateFlow(
                        ConversationChatState(
                            sessionId = sessionId,
                            messages = initialMessages.takeLast(MAX_MESSAGES),
                        ),
                    ),
                    references = 1,
                    lastUsed = ++sequence,
                ).also { stores[sessionId] = it }
            }
        }
        if (store.references == 1 && !socket.retainSession(sessionId)) {
            synchronized(lock) { stores.remove(sessionId) }
            return null
        }
        return store.state.asStateFlow()
    }

    fun release(sessionId: String) {
        val releaseSocket = synchronized(lock) {
            val store = stores[sessionId] ?: return
            if (store.references <= 0) return
            store.references--
            store.lastUsed = ++sequence
            store.references == 0
        }
        if (releaseSocket) socket.releaseSession(sessionId)
    }

    fun send(sessionId: String, content: String, language: String = "auto"): Boolean {
        val text = content.trim()
        if (text.isEmpty()) return false
        val store = synchronized(lock) { stores[sessionId] } ?: return false
        val messageId = UUID.randomUUID().toString()
        store.state.update { current ->
            current.copy(
                messages = appendMessage(
                    current.messages,
                    ChatMessage(messageId, "user", text, Instant.now().toString(), pending = true),
                ),
                liveActivity = emptyList(),
                thinking = true,
                approval = null,
                error = null,
            )
        }
        val sent = socket.send(ClientFrames.userMessage(text, sessionId, language))
        if (!sent) {
            store.state.update { current ->
                current.copy(
                    messages = current.messages.map {
                        if (it.id == messageId) it.copy(pending = false, failed = true) else it
                    },
                    thinking = false,
                    error = "Message was not sent",
                )
            }
        }
        return sent
    }

    fun resolveApproval(sessionId: String, approvalId: String, decision: String): Boolean {
        val store = synchronized(lock) { stores[sessionId] } ?: return false
        val pending = store.state.value.approval
        if (pending?.approvalId != approvalId) return false
        val sent = socket.send(ClientFrames.toolConfirmation(approvalId, decision, sessionId))
        store.state.update {
            it.copy(
                approval = null,
                thinking = sent,
                error = if (sent) null else "The decision could not be sent; the action will be denied",
            )
        }
        return sent
    }

    fun expireApproval(sessionId: String, approvalId: String) {
        synchronized(lock) { stores[sessionId] }?.state?.update {
            if (it.approval?.approvalId == approvalId) it.copy(approval = null) else it
        }
    }

    private fun dispatch(frame: ServerFrame) {
        val sessionId = when (frame) {
            is ServerFrame.Message -> frame.sessionId
            is ServerFrame.AgentEvent -> frame.sessionId
            is ServerFrame.ToolConfirmation -> frame.sessionId
            is ServerFrame.SessionSubscriptionAck, is ServerFrame.Unknown -> null
        } ?: return
        val store = synchronized(lock) { stores[sessionId] } ?: return

        when (frame) {
            is ServerFrame.Message -> {
                if (frame.role != "assistant") return
                store.state.update { current ->
                    current.copy(
                        messages = appendMessage(
                            current.messages.map { if (it.pending) it.copy(pending = false) else it },
                            ChatMessage(
                                UUID.randomUUID().toString(),
                                "assistant",
                                frame.content,
                                frame.timestamp ?: Instant.now().toString(),
                                activity = current.liveActivity,
                            ),
                        ),
                        liveActivity = emptyList(),
                        thinking = false,
                        approval = null,
                        error = null,
                    )
                }
            }
            is ServerFrame.AgentEvent -> {
                val activity = ChatActivity(
                    type = frame.eventType,
                    toolName = frame.toolName,
                    serverName = frame.serverName,
                    ok = frame.ok,
                    arguments = frame.args.mapValues { (_, value) ->
                        (value as? JsonPrimitive)?.content ?: value.toString()
                    },
                    preview = frame.preview,
                    elapsedSeconds = frame.elapsedSeconds,
                )
                store.state.update { current ->
                    current.copy(
                        liveActivity = (current.liveActivity + activity).takeLast(MAX_ACTIVITY),
                        thinking = frame.eventType != "done",
                    )
                }
            }
            is ServerFrame.ToolConfirmation -> store.state.update { current ->
                current.copy(
                    approval = ChatApproval(
                        frame.approvalId,
                        frame.toolName,
                        frame.serverName,
                        frame.arguments.mapValues { (_, value) ->
                            (value as? JsonPrimitive)?.content ?: value.toString()
                        },
                        frame.options,
                        frame.timeoutSeconds,
                        System.currentTimeMillis(),
                    ),
                )
            }
            is ServerFrame.SessionSubscriptionAck, is ServerFrame.Unknown -> Unit
        }
    }

    /** Returns null only when all 32 stores are actively retained. */
    private fun evictIfNeeded(): Unit? {
        if (stores.size < MAX_STORES) return Unit
        val candidate = stores.entries
            .filter { it.value.references == 0 }
            .minByOrNull { it.value.lastUsed }
            ?: return null
        stores.remove(candidate.key)
        return Unit
    }

    private fun appendMessage(messages: List<ChatMessage>, message: ChatMessage): List<ChatMessage> =
        (messages + message).takeLast(MAX_MESSAGES)

    private companion object {
        const val MAX_STORES = 32
        const val MAX_MESSAGES = 500
        const val MAX_ACTIVITY = 100
    }
}
