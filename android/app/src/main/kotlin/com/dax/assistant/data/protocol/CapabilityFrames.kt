package com.dax.assistant.data.protocol

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put

data class CapabilityTool(
    val name: String,
    val inputSchema: JsonObject,
)

sealed interface CapabilityServerFrame {
    data class Ready(val generation: Int) : CapabilityServerFrame
    data object Heartbeat : CapabilityServerFrame
    data class Execute(
        val generation: Int,
        val requestId: String,
        val toolName: String,
        val arguments: JsonObject,
        val approved: Boolean,
        val timeoutSeconds: Int,
    ) : CapabilityServerFrame
    data object Ignored : CapabilityServerFrame
}

object CapabilityFrames {
    fun hello(nodeName: String, tools: List<CapabilityTool>): String = encode(
        buildJsonObject {
            put("type", "hello")
            put("version", 1)
            put("node_name", nodeName.take(64))
            put("tools", buildJsonArray {
                tools.forEach { tool ->
                    add(buildJsonObject {
                        put("name", tool.name)
                        put("input_schema", tool.inputSchema)
                    })
                }
            })
            put("endpoints", buildJsonArray {})
            put("features", buildJsonObject {})
        },
    )

    fun heartbeat(): String = encode(buildJsonObject { put("type", "heartbeat") })

    fun result(
        generation: Int,
        requestId: String,
        success: Boolean,
        content: String = "",
        error: String? = null,
    ): String = encode(
        buildJsonObject {
            put("type", "result")
            put("generation", generation)
            put("request_id", requestId.take(128))
            put("content", truncateUtf8(content, MAX_RESULT_BYTES))
            put("success", success)
            if (error != null) put("error", truncateUtf8(error, MAX_RESULT_BYTES))
        },
    )

    fun parse(text: String): CapabilityServerFrame? = runCatching {
        if (text.toByteArray().size > MAX_FRAME_BYTES) return null
        val root = DaxJson.parseToJsonElement(text).jsonObject
        when (root.string("type")) {
            "ready" -> {
                val version = root.int("version") ?: return null
                val generation = root.int("generation") ?: return null
                if (version != 1 || generation < 1) return null
                CapabilityServerFrame.Ready(generation)
            }
            "heartbeat" -> CapabilityServerFrame.Heartbeat
            "execute" -> {
                val generation = root.int("generation") ?: return null
                val requestId = root.string("request_id") ?: return null
                val toolName = root.string("tool_name") ?: return null
                val arguments = root["arguments"] as? JsonObject ?: return null
                val approved = root.boolean("approved") ?: false
                val timeout = root.int("timeout_seconds") ?: 60
                if (generation < 1 || requestId.isBlank() || requestId.length > 128 ||
                    toolName.isBlank() || toolName.length > 64 || timeout !in 1..60
                ) return null
                CapabilityServerFrame.Execute(
                    generation,
                    requestId,
                    toolName,
                    arguments,
                    approved,
                    timeout,
                )
            }
            else -> CapabilityServerFrame.Ignored
        }
    }.getOrNull()

    private fun encode(value: JsonObject): String =
        DaxJson.encodeToString(JsonObject.serializer(), value)

    private fun JsonObject.string(key: String): String? =
        (this[key] as? JsonPrimitive)?.contentOrNull

    private fun JsonObject.int(key: String): Int? =
        (this[key] as? JsonPrimitive)?.intOrNull

    private fun JsonObject.boolean(key: String): Boolean? =
        (this[key] as? JsonPrimitive)?.contentOrNull?.toBooleanStrictOrNull()

    private const val MAX_FRAME_BYTES = 256 * 1024
    private const val MAX_RESULT_BYTES = 64 * 1024
}

internal fun truncateUtf8(value: String, maxBytes: Int): String {
    if (value.toByteArray(Charsets.UTF_8).size <= maxBytes) return value
    var low = 0
    var high = value.length.coerceAtMost(maxBytes)
    while (low < high) {
        val middle = (low + high + 1) / 2
        val end = if (middle < value.length && middle > 0 &&
            value[middle - 1].isHighSurrogate() && value[middle].isLowSurrogate()
        ) middle - 1 else middle
        if (value.substring(0, end).toByteArray(Charsets.UTF_8).size <= maxBytes) {
            low = middle
        } else {
            high = middle - 1
        }
    }
    var end = low
    if (end < value.length && end > 0 && value[end - 1].isHighSurrogate() && value[end].isLowSurrogate()) {
        end -= 1
    }
    return value.substring(0, end)
}
