package com.dax.assistant.audio

import com.dax.assistant.data.auth.AuthResult
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import io.mockk.coEvery
import io.mockk.every
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import okhttp3.OkHttpClient
import okhttp3.ExperimentalOkHttpApi
import okio.Buffer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalOkHttpApi::class)
class BackendSpeechClientTest {
    private val server = MockWebServer()

    @Before
    fun startServer() = server.start()

    @After
    fun stopServer() = server.close()

    @Test
    fun `sends authenticated synthesis request and reads diagnostics`() = runTest {
        val wav = "RIFF1234WAVEdata".encodeToByteArray()
        server.enqueue(
            MockResponse.Builder()
                .code(200)
                .addHeader("Content-Type", "audio/wav")
                .addHeader("X-Dax-TTS-Engine", "kokoro")
                .addHeader("X-Dax-TTS-Voice", "af_heart")
                .addHeader("X-Dax-TTS-Fingerprint", "abc")
                .body(Buffer().write(wav))
                .build(),
        )
        val credentials = mockk<CredentialStore> {
            every { backendUrl } returns server.url("/").toString().removeSuffix("/")
        }
        val auth = mockk<BackendAuth> {
            coEvery { accessToken() } returns AuthResult.Success("short-token")
        }
        val client = BackendSpeechClient(OkHttpClient(), credentials, auth, Dispatchers.IO)

        val result = client.synthesize("Hola", "es-ES")
        val request = server.takeRequest()
        val body = Json.parseToJsonElement(request.body.readUtf8()).jsonObject

        assertEquals("POST", request.method)
        assertEquals("/api/voice/synthesize", request.requestUrl?.encodedPath)
        assertEquals("Bearer short-token", request.headers["Authorization"])
        assertEquals("Hola", body.getValue("text").jsonPrimitive.content)
        assertEquals("es-ES", body.getValue("language").jsonPrimitive.content)
        assertTrue(wav.contentEquals(result.wav))
        assertEquals("kokoro", result.engine)
        assertEquals("af_heart", result.voice)
        assertEquals("abc", result.fingerprint)
    }
}
