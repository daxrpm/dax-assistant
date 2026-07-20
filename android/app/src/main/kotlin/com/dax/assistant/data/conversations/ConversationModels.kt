package com.dax.assistant.data.conversations

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ConversationSummary(
    val id: String,
    @SerialName("session_key") val sessionKey: String,
    val title: String = "",
    val preview: String = "",
    @SerialName("updated_at") val updatedAt: String,
    @SerialName("message_count") val messageCount: Int = 0,
)

@Serializable
data class ConversationMessage(
    val id: String,
    val role: String,
    val content: String,
    val timestamp: String,
)

@Serializable
data class ConversationDetail(
    val id: String,
    @SerialName("session_key") val sessionKey: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    val messages: List<ConversationMessage> = emptyList(),
)

data class ChatActivity(
    val type: String,
    val toolName: String? = null,
    val serverName: String? = null,
    val ok: Boolean? = null,
    val arguments: Map<String, String> = emptyMap(),
    val preview: String? = null,
    val elapsedSeconds: Double? = null,
)

data class ChatMessage(
    val id: String,
    val role: String,
    val content: String,
    val timestamp: String,
    val pending: Boolean = false,
    val failed: Boolean = false,
    val activity: List<ChatActivity> = emptyList(),
)

data class ChatApproval(
    val approvalId: String,
    val toolName: String,
    val serverName: String,
    val arguments: Map<String, String>,
    val options: List<String>,
    val timeoutSeconds: Int,
    val requestedAtMillis: Long,
)

data class ConversationChatState(
    val sessionId: String,
    val messages: List<ChatMessage> = emptyList(),
    val liveActivity: List<ChatActivity> = emptyList(),
    val thinking: Boolean = false,
    val approval: ChatApproval? = null,
    val error: String? = null,
)
