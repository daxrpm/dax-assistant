package com.dax.assistant.data.auth

import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.core.network.BackendEndpointPolicy
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

sealed interface AuthResult {
    data class Success(val token: String) : AuthResult
    data class Failed(val reason: String) : AuthResult
    data object NotEnrolled : AuthResult
}

sealed interface EnrolResult {
    data object Success : EnrolResult
    data class Failed(val reason: String) : EnrolResult
}

@Serializable
private data class EnrolRequest(
    val code: String,
    val name: String,
    val platform: String = "android",
    @SerialName("expected_kind") val expectedKind: String = "client",
)

@Serializable
private data class EnrolResponse(
    val ok: Boolean = false,
    @SerialName("device_id") val deviceId: String? = null,
    @SerialName("device_secret") val deviceSecret: String? = null,
    @SerialName("instance_id") val instanceId: String? = null,
    val kind: String? = null,
)

@Serializable
private data class TokenRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_secret") val deviceSecret: String,
)

@Serializable
private data class TokenResponse(
    val ok: Boolean = false,
    val token: String? = null,
    @SerialName("expires_in_seconds") val expiresInSeconds: Int? = null,
)

@Serializable
private data class BackendHealth(
    @SerialName("instance_id") val instanceId: String,
    val role: String,
    @SerialName("api_protocol") val apiProtocol: String,
)

/**
 * Enrolment and token exchange against the backend's device endpoints.
 *
 * The phone never learns the account password. A client that is already signed
 * in mints a one-time pairing code, this device redeems it once for a secret it
 * keeps in the keystore, and every later request rides a short-lived token that
 * the backend can revoke the moment the phone is lost.
 */
class BackendAuth(
    private val client: OkHttpClient,
    private val credentials: CredentialStore,
) {

    private val json = Json { ignoreUnknownKeys = true }
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()
    private val tokenMutex = Mutex()

    /** Redeems a pairing code. The secret is stored and never returned. */
    suspend fun enrol(code: String, deviceName: String): EnrolResult = withContext(Dispatchers.IO) {
        val base = credentials.backendUrl
        if (base.isBlank()) return@withContext EnrolResult.Failed("No backend URL configured")

        val body = json.encodeToString(
            EnrolRequest(code.trim().uppercase(), deviceName),
        ).toRequestBody(jsonMedia)

        runCatching {
            client.newCall(
                Request.Builder().url("$base/api/auth/devices/enroll").post(body).build(),
            ).execute().use { response ->
                val payload = response.body?.string().orEmpty()
                if (!response.isSuccessful) {
                    return@use EnrolResult.Failed(
                        when (response.code) {
                            401 -> "That pairing code is wrong or has expired"
                            503 -> "The backend has no device registry configured"
                            else -> "Enrolment failed (${response.code})"
                        },
                    )
                }
                val result = json.decodeFromString<EnrolResponse>(payload)
                if (!result.ok || result.kind != "client" || result.deviceId.isNullOrBlank() ||
                    result.deviceSecret.isNullOrBlank() || result.instanceId.isNullOrBlank()
                ) {
                    EnrolResult.Failed("Backend returned an incomplete enrolment")
                } else {
                    credentials.saveEnrolment(
                        result.deviceId,
                        result.deviceSecret,
                        result.instanceId,
                        base,
                    )
                    EnrolResult.Success
                }
            }
        }.getOrElse { error ->
            DaxLog.w(TAG, "Enrolment request failed", error)
            EnrolResult.Failed(error.message ?: "Could not reach the backend")
        }
    }

    /**
     * A live access token, minting a fresh one when the cached one is spent.
     *
     * A 401 clears the cached token and reports failure rather than retrying:
     * repeatedly presenting a secret the backend has revoked is how a lost
     * phone keeps knocking.
     */
    suspend fun accessToken(): AuthResult = tokenMutex.withLock {
        withContext(Dispatchers.IO) {
            val deviceId = credentials.deviceId
            val secret = credentials.deviceSecret
            if (deviceId.isNullOrBlank() || secret.isNullOrBlank()) {
                return@withContext AuthResult.NotEnrolled
            }
            val base = credentials.backendUrl
            if (base.isBlank()) return@withContext AuthResult.Failed("No backend URL configured")
            val identityError = verifyIdentity(base)
            if (identityError != null) return@withContext AuthResult.Failed(identityError)
            credentials.validToken()?.let { return@withContext AuthResult.Success(it) }

            val body = json.encodeToString(TokenRequest(deviceId, secret)).toRequestBody(jsonMedia)

            runCatching {
                client.newCall(
                    Request.Builder().url("$base/api/auth/devices/token").post(body).build(),
                ).execute().use { response ->
                    if (response.code == 401) {
                        credentials.invalidateToken()
                        return@use AuthResult.Failed("This device has been revoked")
                    }
                    if (!response.isSuccessful) {
                        return@use AuthResult.Failed("Token request failed (${response.code})")
                    }
                    val result = json.decodeFromString<TokenResponse>(response.body?.string().orEmpty())
                    if (!result.ok || result.token.isNullOrBlank()) {
                        AuthResult.Failed("Backend returned no token")
                    } else {
                        credentials.cacheToken(result.token, result.expiresInSeconds ?: 900)
                        AuthResult.Success(result.token)
                    }
                }
            }.getOrElse { error ->
                DaxLog.w(TAG, "Token request failed", error)
                AuthResult.Failed(error.message ?: "Could not reach the backend")
            }
        }
    }

    private fun verifyIdentity(base: String): String? {
        val normalized = BackendEndpointPolicy.normalize(base)
            ?: return "Backend URL is invalid"
        val storedOrigin = credentials.enrollmentOrigin
        if (storedOrigin != null && normalized != storedOrigin) return "Backend origin changed; pair again"
        return runCatching {
            client.newCall(Request.Builder().url("$base/api/health").get().build())
                .execute().use { response ->
                    if (!response.isSuccessful) return@use "Could not verify backend identity"
                    val health = json.decodeFromString<BackendHealth>(response.body?.string().orEmpty())
                    val storedInstance = credentials.instanceId
                    if (health.role != "authoritative" ||
                        health.apiProtocol != "dax"
                    ) {
                        "Backend identity changed; pair again"
                    } else if (storedInstance != null && health.instanceId != storedInstance) {
                        "Backend identity changed; pair again"
                    } else {
                        if (storedOrigin == null || storedInstance == null) {
                            credentials.bindAuthority(health.instanceId, normalized)
                        }
                        null
                    }
                }
        }.getOrElse { "Could not verify backend identity" }
    }

    private companion object {
        const val TAG = "BackendAuth"
    }
}
