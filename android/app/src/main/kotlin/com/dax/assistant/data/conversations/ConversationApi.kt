package com.dax.assistant.data.conversations

import com.dax.assistant.data.auth.AuthResult
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import okhttp3.Request

sealed interface ConversationApiResult<out T> {
    data class Success<T>(val value: T) : ConversationApiResult<T>
    data class Failed(val reason: String, val statusCode: Int? = null) : ConversationApiResult<Nothing>
}

@Singleton
class ConversationApi @Inject constructor(
    private val client: OkHttpClient,
    private val credentials: CredentialStore,
    private val auth: BackendAuth,
) {
    private val json = Json { ignoreUnknownKeys = true }

    suspend fun list(limit: Int = 50): ConversationApiResult<List<ConversationSummary>> =
        request("/api/conversations?limit=${limit.coerceIn(1, 100)}") { payload ->
            json.decodeFromString<List<ConversationSummary>>(payload)
        }

    suspend fun get(id: String): ConversationApiResult<ConversationDetail> =
        request("/api/conversations/${pathSegment(id)}") { payload ->
            json.decodeFromString<ConversationDetail>(payload)
        }

    suspend fun delete(id: String): ConversationApiResult<Unit> =
        request("/api/conversations/${pathSegment(id)}", "DELETE", expectedEmpty = true) { Unit }

    private suspend fun <T> request(
        path: String,
        method: String = "GET",
        expectedEmpty: Boolean = false,
        decode: (String) -> T,
    ): ConversationApiResult<T> = withContext(Dispatchers.IO) {
        var token = when (val result = auth.accessToken()) {
            is AuthResult.Success -> result.token
            is AuthResult.Failed -> return@withContext ConversationApiResult.Failed(result.reason)
            AuthResult.NotEnrolled -> return@withContext ConversationApiResult.Failed("Device is not paired")
        }

        repeat(2) { attempt ->
            val request = Request.Builder()
                .url(credentials.backendUrl + path)
                .header("Authorization", "Bearer $token")
                .method(method, null)
                .build()
            val outcome = runCatching {
                client.newCall(request).execute().use { response ->
                    val payload = response.body?.string().orEmpty()
                    if (response.code == 401 && attempt == 0) return@use null
                    if (!response.isSuccessful) {
                        return@use ConversationApiResult.Failed(
                            "Request failed (${response.code})",
                            response.code,
                        )
                    }
                    if (expectedEmpty && response.code != 204) {
                        return@use ConversationApiResult.Failed(
                            "Expected an empty response (${response.code})",
                            response.code,
                        )
                    }
                    if (!expectedEmpty && payload.isBlank()) {
                        return@use ConversationApiResult.Failed("Backend returned an empty response")
                    }
                    ConversationApiResult.Success(decode(payload))
                }
            }.getOrElse {
                return@withContext ConversationApiResult.Failed(it.message ?: "Could not reach the backend")
            }
            if (outcome != null) return@withContext outcome

            credentials.invalidateToken()
            token = when (val refreshed = auth.accessToken()) {
                is AuthResult.Success -> refreshed.token
                is AuthResult.Failed -> return@withContext ConversationApiResult.Failed(refreshed.reason, 401)
                AuthResult.NotEnrolled -> return@withContext ConversationApiResult.Failed("Device is not paired", 401)
            }
        }
        ConversationApiResult.Failed("Authentication failed", 401)
    }

    private fun pathSegment(value: String): String =
        java.net.URLEncoder.encode(value, Charsets.UTF_8.name()).replace("+", "%20")
}
