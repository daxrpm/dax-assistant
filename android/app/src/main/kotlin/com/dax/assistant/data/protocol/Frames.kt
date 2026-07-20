package com.dax.assistant.data.protocol

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/**
 * The `/ws/chat` wire format, as the backend actually speaks it.
 *
 * Parsed permissively on purpose. The backend is versioned independently and
 * adds fields over time; a strict decoder would turn a harmless new key into a
 * dropped conversation. Unknown frame types become [ServerFrame.Unknown] and
 * are ignored rather than throwing.
 */
val DaxJson: Json = Json {
    ignoreUnknownKeys = true
    isLenient = true
    encodeDefaults = true
}

/** Anything the server sends on the chat socket. */
sealed interface ServerFrame {

    /** A completed assistant turn. */
    data class Message(
        val content: String,
        val role: String,
        val sessionId: String?,
        val timestamp: String?,
    ) : ServerFrame

    /** Agent activity: thinking, tool_call, tool_result, done. */
    data class AgentEvent(
        val eventType: String,
        val sessionId: String?,
        val toolName: String?,
        val serverName: String?,
        val ok: Boolean?,
        val args: JsonObject,
        val preview: String?,
        val error: Boolean?,
        val elapsedSeconds: Double?,
        val timestamp: String?,
    ) : ServerFrame

    /** A gated tool needs confirmation before it runs. */
    data class ToolConfirmation(
        val approvalId: String,
        val toolName: String,
        val serverName: String,
        val arguments: JsonObject,
        val options: List<String>,
        val timeoutSeconds: Int,
        val sessionId: String?,
        val timestamp: String?,
    ) : ServerFrame

    /** Optional acknowledgement for session subscription control frames. */
    data class SessionSubscriptionAck(
        val subscribed: Boolean,
        val ok: Boolean,
        val sessionIds: List<String>,
        val error: String?,
    ) : ServerFrame

    data class Unknown(val type: String) : ServerFrame
}

object FrameParser {

    fun parse(text: String): ServerFrame? = runCatching {
        val root = DaxJson.parseToJsonElement(text).jsonObject
        val type = root.str("type")
        when {
            type == "message" || (type == null && root.str("content") != null) -> {
                val content = root.str("content") ?: return null
                ServerFrame.Message(
                    content = content,
                    role = root.str("role") ?: "assistant",
                    sessionId = root.str("session_id"),
                    timestamp = root.str("timestamp"),
                )
            }

            type == "agent_event" -> {
                val event = (root["event"] as? JsonObject) ?: JsonObject(emptyMap())
                ServerFrame.AgentEvent(
                    eventType = event.str("type").orEmpty(),
                    sessionId = root.str("session_id") ?: event.str("session_id"),
                    toolName = event.str("tool") ?: event.str("tool_name"),
                    serverName = event.str("server") ?: event.str("server_name"),
                    ok = event.bool("ok") ?: event.bool("error")?.not(),
                    args = event["args"] as? JsonObject ?: JsonObject(emptyMap()),
                    preview = event.str("preview"),
                    error = event.bool("error"),
                    elapsedSeconds = event.number("elapsed_s"),
                    timestamp = root.str("timestamp") ?: event.str("timestamp"),
                )
            }

            type == "tool_confirmation_request" -> ServerFrame.ToolConfirmation(
                approvalId = root.str("approval_id")?.takeIf { it.isNotBlank() } ?: return null,
                toolName = root.str("tool_name").orEmpty(),
                serverName = root.str("server_name").orEmpty(),
                arguments = root["arguments"] as? JsonObject ?: JsonObject(emptyMap()),
                options = root["options"]
                    ?.let { element -> runCatching { element.jsonArray }.getOrNull() }
                    ?.map { it.asDisplayString() }
                    ?.takeIf { it.isNotEmpty() }
                    // The backend always sends at least ["approve"]; a deny
                    // option is synthesised here so the sheet can never render
                    // without a way to refuse.
                    ?: listOf("approve", "deny"),
                timeoutSeconds = root["timeout_seconds"]?.jsonPrimitive?.contentOrNull
                    ?.toIntOrNull() ?: 120,
                sessionId = root.str("session_id"),
                timestamp = root.str("timestamp"),
            )

            type == "session_subscribe_ack" || type == "session_unsubscribe_ack" ->
                ServerFrame.SessionSubscriptionAck(
                    subscribed = type == "session_subscribe_ack",
                    ok = root.bool("ok") ?: false,
                    sessionIds = root["session_ids"]
                        ?.let { runCatching { it.jsonArray }.getOrNull() }
                        ?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
                        .orEmpty(),
                    error = root.str("error"),
                )

            else -> ServerFrame.Unknown(type.orEmpty())
        }
    }.getOrNull()

    private fun JsonObject.str(key: String): String? =
        (this[key] as? JsonPrimitive)?.contentOrNull

    private fun JsonObject.bool(key: String): Boolean? =
        (this[key] as? JsonPrimitive)?.contentOrNull?.toBooleanStrictOrNull()

    private fun JsonObject.number(key: String): Double? =
        (this[key] as? JsonPrimitive)?.contentOrNull?.toDoubleOrNull()

    private fun JsonElement.asDisplayString(): String =
        (this as? JsonPrimitive)?.contentOrNull ?: toString()
}

/** Client-to-server frames. */
object ClientFrames {

    fun userMessage(content: String, sessionId: String, language: String): String =
        DaxJson.encodeToString(
            JsonObject.serializer(),
            buildJsonObject {
                put("content", content)
                put("session_id", sessionId)
                put("language", language)
            },
        )

    /**
     * Answers a pending confirmation.
     *
     * The backend binds the approval to the session that raised it and settles
     * it exactly once, so a duplicate frame from a retry cannot run the tool
     * twice.
     */
    fun toolConfirmation(approvalId: String, decision: String, sessionId: String? = null): String =
        DaxJson.encodeToString(
            JsonObject.serializer(),
            buildJsonObject {
                put("type", "tool_confirmation")
                put("approval_id", approvalId)
                put("decision", decision)
                if (sessionId != null) put("session_id", sessionId)
            },
        )

    fun sessionSubscription(sessionIds: Collection<String>, subscribe: Boolean): String =
        DaxJson.encodeToString(
            JsonObject.serializer(),
            buildJsonObject {
                put("type", if (subscribe) "session_subscribe" else "session_unsubscribe")
                put("ack", true)
                put("session_ids", kotlinx.serialization.json.buildJsonArray {
                    sessionIds.forEach { add(JsonPrimitive(it)) }
                })
            },
        )
}
