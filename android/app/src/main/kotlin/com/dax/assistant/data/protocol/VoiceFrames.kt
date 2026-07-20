package com.dax.assistant.data.protocol

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.floatOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

sealed interface VoiceFrame {
    data class State(val state: String) : VoiceFrame
    data class Acquired(
        val maxFrameBytes: Int,
        val maxDurationSeconds: Int,
        val outputMode: String,
    ) : VoiceFrame
    data class Started(val state: String) : VoiceFrame
    data class Stopped(val state: String) : VoiceFrame
    data object Released : VoiceFrame
    data class Transcript(val text: String, val language: String?, val final: Boolean) : VoiceFrame
    data class Speech(val text: String, val language: String?) : VoiceFrame
    data class TurnComplete(val voiceTurn: String) : VoiceFrame
    data class ApprovalRequest(
        val approvalId: String,
        val toolName: String,
        val serverName: String,
        val arguments: Map<String, String>,
        val options: List<String>,
        val timeoutSeconds: Int,
    ) : VoiceFrame
    data class Interrupted(val state: String, val agentCancelled: Boolean) : VoiceFrame
    data class Error(val code: String?, val message: String) : VoiceFrame
    data class Level(val value: Float, val source: String) : VoiceFrame
    data class Speaker(val verified: Boolean) : VoiceFrame
}

object VoiceFrames {
    fun acquire(): String = encode("remote_audio.acquire") {
        put("format", buildJsonObject {
            put("sample_rate", 16_000)
            put("channels", 1)
            put("sample_format", "pcm_s16le")
        })
        put("output", buildJsonObject { put("mode", "client_text") })
    }

    fun start(): String = encode("remote_audio.start")
    fun stop(): String = encode("remote_audio.stop")
    fun release(): String = encode("remote_audio.release")
    fun interrupt(): String = encode("remote_audio.interrupt")
    fun approval(approvalId: String, decision: String): String = encode("voice.approval") {
        put("approval_id", approvalId)
        put("decision", decision)
    }

    fun parse(text: String): VoiceFrame {
        val root = DaxJson.parseToJsonElement(text).jsonObject
        val type = root.requiredString("type")
        val data = root["data"]?.let { it as? JsonObject }
            ?: throw IllegalArgumentException("Voice frame $type has no data object")
        return when (type) {
            "state" -> VoiceFrame.State(data.requiredString("state"))
            "remote_audio.acquired" -> {
                val output = data["output"]?.jsonObject
                    ?: throw IllegalArgumentException("Acquired frame has no output")
                VoiceFrame.Acquired(
                    maxFrameBytes = data.requiredInt("max_frame_bytes"),
                    maxDurationSeconds = data.requiredInt("max_duration_seconds"),
                    outputMode = output.requiredString("mode"),
                )
            }
            "remote_audio.started" -> VoiceFrame.Started(data.requiredString("state"))
            "remote_audio.stopped" -> VoiceFrame.Stopped(data.requiredString("state"))
            "remote_audio.released" -> VoiceFrame.Released
            "transcript" -> VoiceFrame.Transcript(
                text = data.requiredString("text"),
                language = data.string("language"),
                final = data.boolean("final")
                    ?: throw IllegalArgumentException("Transcript has no final flag"),
            )
            "speech" -> VoiceFrame.Speech(
                text = data.requiredString("text"),
                language = data.string("language"),
            )
            "turn_complete" -> VoiceFrame.TurnComplete(data.requiredString("voice_turn"))
            "approval_request" -> VoiceFrame.ApprovalRequest(
                approvalId = data.requiredString("approval_id"),
                toolName = data.requiredString("tool_name"),
                serverName = data.requiredString("server_name"),
                arguments = data["arguments"]?.jsonObject?.mapValues { (_, value) ->
                    (value as? JsonPrimitive)?.contentOrNull ?: value.toString()
                } ?: throw IllegalArgumentException("Approval has no arguments"),
                options = data["options"]?.jsonArray?.map { it.jsonPrimitive.content }
                    ?: throw IllegalArgumentException("Approval has no options"),
                timeoutSeconds = data.requiredInt("timeout_seconds"),
            )
            "remote_audio.interrupted" -> VoiceFrame.Interrupted(
                state = data.requiredString("state"),
                agentCancelled = data.boolean("agent_cancelled")
                    ?: throw IllegalArgumentException("Interrupt has no agent cancellation flag"),
            )
            "remote_audio.error" -> VoiceFrame.Error(data.string("code"), data.requiredString("message"))
            "error" -> VoiceFrame.Error(data.string("code"), data.requiredString("message"))
            "level" -> VoiceFrame.Level(
                value = data["rms"]?.let { element ->
                    runCatching { element.jsonArray.mapNotNull { it.jsonPrimitive.floatOrNull }.maxOrNull() }
                        .getOrNull()
                } ?: data.number("rms") ?: data.number("level")
                    ?: throw IllegalArgumentException("Level frame has no value"),
                source = data.string("source") ?: "input",
            )
            "speaker" -> VoiceFrame.Speaker(
                data.boolean("verified")
                    ?: throw IllegalArgumentException("Speaker frame has no verdict"),
            )
            else -> throw IllegalArgumentException("Unknown voice frame: $type")
        }
    }

    private fun encode(type: String, content: kotlinx.serialization.json.JsonObjectBuilder.() -> Unit = {}): String =
        DaxJson.encodeToString(
            JsonObject.serializer(),
            buildJsonObject {
                put("type", type)
                content()
            },
        )

    private fun JsonObject.requiredString(key: String): String =
        string(key)?.takeIf { it.isNotBlank() }
            ?: throw IllegalArgumentException("Missing $key")

    private fun JsonObject.requiredInt(key: String): Int =
        this[key]?.jsonPrimitive?.intOrNull ?: throw IllegalArgumentException("Missing $key")

    private fun JsonObject.string(key: String): String? =
        (this[key] as? JsonPrimitive)?.contentOrNull

    private fun JsonObject.boolean(key: String): Boolean? =
        string(key)?.toBooleanStrictOrNull()

    private fun JsonObject.number(key: String): Float? = string(key)?.toFloatOrNull()
}
