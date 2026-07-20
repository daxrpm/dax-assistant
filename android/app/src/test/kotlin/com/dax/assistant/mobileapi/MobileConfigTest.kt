package com.dax.assistant.mobileapi

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MobileConfigTest {
    @Test
    fun `parses nested mobile config and ignores secret fields`() {
        val config = MobileConfig.parse(
            """{
                "llm": {
                    "provider": "ollama",
                    "models": {"ollama": "qwen3", "openai": "gpt-5-mini"},
                    "fallback": ["openai"]
                },
                "voice": {
                    "stt": {"provider": "local", "model": "small", "api_key": "hidden"},
                    "tts": {"engine": "kokoro", "model": "v1", "voice": "ef_dora"}
                }
            }""".trimIndent(),
        )

        assertEquals("ollama", config.provider)
        assertEquals("qwen3", config.models["ollama"])
        assertEquals(listOf("openai"), config.fallbackOrder)
        assertEquals("local", config.sttBackend)
        assertEquals("kokoro", config.ttsEngine)
        assertFalse(config.toJson().contains("api_key"))
        assertFalse(config.toJson().contains("hidden"))
    }

    @Test
    fun `round trips canonical config`() {
        val original = MobileConfig(
            provider = "anthropic",
            models = mapOf("anthropic" to "claude-sonnet"),
            fallbackOrder = listOf("ollama"),
            sttBackend = "openai",
            sttModel = "gpt-4o-mini-transcribe",
            sttFallbackToLocal = false,
            ttsEngine = "openai",
            ttsModel = "gpt-4o-mini-tts",
            ttsVoice = "coral",
        )

        assertEquals(original, MobileConfig.parse(original.toJson()))
        assertTrue(original.toJson().contains("fallback_order"))
    }

    @Test
    fun `parses backend flat model contract and emits split safe updates`() {
        val config = MobileConfig.parse(
            """{
                "llm": {
                    "default_provider": "openai",
                    "fallback_order": ["ollama"],
                    "openai_model": "gpt-5-mini",
                    "ollama_model": "qwen3",
                    "openai_configured": true
                },
                "voice": {
                    "stt_backend": "openai",
                    "stt_openai_model": "gpt-4o-mini-transcribe",
                    "tts_engine": "openai",
                    "tts_openai_model": "gpt-4o-mini-tts",
                    "tts_openai_voice": "coral"
                }
            }""".trimIndent(),
        )

        assertEquals("gpt-5-mini", config.models["openai"])
        assertEquals("gpt-4o-mini-transcribe", config.sttModel)
        assertEquals("gpt-4o-mini-tts", config.ttsModel)
        assertFalse(config.llmJson().contains("configured"))
        assertFalse(config.voiceJson().contains("api_key"))
    }
}
