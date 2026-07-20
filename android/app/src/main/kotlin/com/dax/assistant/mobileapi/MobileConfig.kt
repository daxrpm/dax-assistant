package com.dax.assistant.mobileapi

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

data class MobileConfig(
    val provider: String = "",
    val models: Map<String, String> = emptyMap(),
    val providerConfigured: Map<String, Boolean> = emptyMap(),
    val fallbackOrder: List<String> = emptyList(),
    val sttBackend: String = "",
    val sttModel: String = "",
    val sttFallbackToLocal: Boolean = true,
    val ttsEngine: String = "",
    val ttsModel: String = "",
    val ttsVoice: String = "",
    val ttsFallbackToLocal: Boolean = true,
    val nodesEnabled: Boolean = true,
    val nodesPreferWhenAvailable: Boolean = true,
    /** Reported by the backend, not editable here: is a laptop up right now. */
    val nodeAvailable: Boolean = false,
    /** The node that would serve this phone, when one would. */
    val nodeName: String = "",
) {
    /** Canonical payload for the intentionally secret-free mobile endpoint. */
    fun toJson(): String = buildJsonObject {
        put("provider", provider)
        put("models", JsonObject(models.mapValues { JsonPrimitive(it.value) }))
        put("fallback_order", JsonArray(fallbackOrder.map(::JsonPrimitive)))
        put("voice", buildJsonObject {
            put("stt_backend", sttBackend)
            put("stt_model", sttModel)
            put("stt_fallback_to_local", sttFallbackToLocal)
            put("tts_engine", ttsEngine)
            put("tts_model", ttsModel)
            put("tts_voice", ttsVoice)
            put("tts_fallback_to_local", ttsFallbackToLocal)
        })
    }.toString()

    fun llmJson(): String = buildJsonObject {
        put("default_provider", provider)
        put("fallback_order", JsonArray(fallbackOrder.map(::JsonPrimitive)))
        models.forEach { (provider, model) ->
            if (provider in supportedModelProviders) put("${provider}_model", model)
        }
    }.toString()

    /** Only the two switches; the rest of the node summary is read-only. */
    fun nodesJson(): String = buildJsonObject {
        put("enabled", nodesEnabled)
        put("prefer_when_available", nodesPreferWhenAvailable)
    }.toString()

    fun voiceJson(): String = buildJsonObject {
        put("stt_backend", sttBackend)
        put("stt_model", sttModel)
        if (sttBackend == "openai") put("stt_openai_model", sttModel)
        put("stt_fallback_to_local", sttFallbackToLocal)
        put("tts_engine", ttsEngine)
        if (ttsModel.isNotBlank()) put("tts_openai_model", ttsModel)
        if (ttsVoice.isNotBlank()) put("tts_openai_voice", ttsVoice)
        put("tts_fallback_to_local", ttsFallbackToLocal)
    }.toString()

    companion object {
        private val json = Json { ignoreUnknownKeys = true }

        fun parse(payload: String): MobileConfig {
            val root = json.parseToJsonElement(payload).jsonObject
            val llm = root.objectOrEmpty("llm")
            val nodes = root.objectOrEmpty("nodes")
            val voice = root.objectOrEmpty("voice")
            val stt = voice.objectOrEmpty("stt")
            val tts = voice.objectOrEmpty("tts")
            val modelObject = root["models"] as? JsonObject ?: llm["models"] as? JsonObject
            val nestedModels = modelObject.orEmpty().mapNotNull { (key, value) ->
                value.primitiveContent()?.let { key to it }
            }.toMap()
            val flatModels = supportedModelProviders.mapNotNull { provider ->
                llm.string("${provider}_model")?.let { provider to it }
            }.toMap()
            val models = nestedModels + flatModels
            val configured = supportedModelProviders.mapNotNull { provider ->
                llm.bool("${provider}_configured")?.let { provider to it }
            }.toMap()
            return MobileConfig(
                provider = root.string("provider") ?: llm.string("provider")
                    ?: llm.string("default_provider").orEmpty(),
                models = models,
                providerConfigured = configured,
                fallbackOrder = root.strings("fallback_order").ifEmpty {
                    llm.strings("fallback_order").ifEmpty { llm.strings("fallback") }
                },
                sttBackend = voice.string("stt_backend") ?: stt.string("backend")
                    ?: stt.string("provider").orEmpty(),
                sttModel = if ((voice.string("stt_backend") ?: stt.string("provider")) == "openai") {
                    voice.string("stt_openai_model") ?: voice.string("stt_model")
                } else {
                    voice.string("stt_model")
                } ?: stt.string("model").orEmpty(),
                sttFallbackToLocal = voice.bool("stt_fallback_to_local")
                    ?: stt.bool("fallback_to_local") ?: true,
                ttsEngine = voice.string("tts_engine") ?: tts.string("engine")
                    ?: tts.string("provider").orEmpty(),
                ttsModel = voice.string("tts_openai_model") ?: voice.string("tts_model")
                    ?: tts.string("model").orEmpty(),
                ttsVoice = voice.string("tts_openai_voice") ?: voice.string("tts_voice")
                    ?: tts.string("voice").orEmpty(),
                ttsFallbackToLocal = voice.bool("tts_fallback_to_local")
                    ?: tts.bool("fallback_to_local") ?: true,
                nodesEnabled = nodes.bool("enabled") ?: true,
                nodesPreferWhenAvailable = nodes.bool("prefer_when_available") ?: true,
                nodeAvailable = nodes.bool("available") ?: false,
                nodeName = nodes.string("name").orEmpty(),
            )
        }

        private fun JsonObject.objectOrEmpty(key: String) = this[key] as? JsonObject ?: JsonObject(emptyMap())
        private fun JsonObject.string(key: String) = this[key]?.primitiveContent()
        private fun JsonObject.bool(key: String) = (this[key] as? JsonPrimitive)?.booleanOrNull
        private fun JsonObject.strings(key: String) = (this[key] as? JsonArray).orEmpty().mapNotNull { it.primitiveContent() }
        private fun JsonElement.primitiveContent() = (this as? JsonPrimitive)?.contentOrNull
        private val supportedModelProviders = setOf(
            "ollama", "anthropic", "openai", "gemini", "deepseek", "codex",
        )
    }
}
