package com.dax.assistant.audio

import com.dax.assistant.data.auth.AuthResult
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import com.dax.assistant.di.IoDispatcher
import java.io.IOException
import java.util.concurrent.atomic.AtomicReference
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Call
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

data class SynthesizedSpeech(
    val wav: ByteArray,
    val engine: String?,
    val voice: String?,
    val fingerprint: String?,
)

@Serializable
private data class SynthesisRequest(val text: String, val language: String)

class BackendSpeechClient(
    private val client: OkHttpClient,
    private val credentials: CredentialStore,
    private val auth: BackendAuth,
    @IoDispatcher private val io: CoroutineDispatcher,
) {
    private val json = Json
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()
    private val activeCall = AtomicReference<Call?>(null)

    fun cancel() {
        activeCall.getAndSet(null)?.cancel()
    }

    suspend fun synthesize(text: String, language: String): SynthesizedSpeech {
        val token = when (val result = auth.accessToken()) {
            is AuthResult.Success -> result.token
            is AuthResult.Failed -> throw IOException(result.reason)
            AuthResult.NotEnrolled -> throw IOException("This device is not paired")
        }
        val body = json.encodeToString(SynthesisRequest(text, language)).toRequestBody(jsonMedia)
        val request = Request.Builder()
            .url("${credentials.backendUrl.trimEnd('/')}/api/voice/synthesize")
            .header("Authorization", "Bearer $token")
            .post(body)
            .build()
        val call = client.newCall(request)
        activeCall.set(call)
        val response = try {
            withContext(io) {
                suspendCancellableCoroutine { continuation ->
                    continuation.invokeOnCancellation { call.cancel() }
                    try {
                        continuation.resume(call.execute())
                    } catch (error: Exception) {
                        if (continuation.isActive) continuation.resumeWithException(error)
                    }
                }
            }
        } finally {
            activeCall.compareAndSet(call, null)
        }
        response.use {
            if (!it.isSuccessful) throw IOException("Backend speech failed (${it.code})")
            val contentType = it.body?.contentType()?.toString().orEmpty()
            if (!contentType.startsWith("audio/wav")) throw IOException("Backend returned $contentType instead of WAV")
            val wav = it.body?.bytes() ?: throw IOException("Backend returned no audio")
            if (wav.size < 12 || !wav.copyOfRange(0, 4).contentEquals("RIFF".encodeToByteArray())) {
                throw IOException("Backend returned an invalid WAV")
            }
            return SynthesizedSpeech(
                wav = wav,
                engine = it.header("X-Dax-TTS-Engine"),
                voice = it.header("X-Dax-TTS-Voice"),
                fingerprint = it.header("X-Dax-TTS-Fingerprint"),
            )
        }
    }
}
