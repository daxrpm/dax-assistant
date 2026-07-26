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

data class CapabilityToken(val value: String, val expiresInSeconds: Int)

sealed interface CapabilityTokenResult {
    data class Success(val token: CapabilityToken) : CapabilityTokenResult
    data class Failed(val reason: String, val revoked: Boolean = false) : CapabilityTokenResult
    data object NotEnrolled : CapabilityTokenResult
}

@Serializable
private data class CapabilityEnrolRequest(
    val code: String,
    val name: String,
    val platform: String = "android",
    @SerialName("expected_kind") val expectedKind: String = "capability_node",
)

@Serializable
private data class CapabilityEnrolResponse(
    val ok: Boolean = false,
    @SerialName("device_id") val deviceId: String? = null,
    @SerialName("device_secret") val deviceSecret: String? = null,
    @SerialName("instance_id") val instanceId: String? = null,
    val kind: String? = null,
)

@Serializable
private data class CapabilityTokenRequest(
    @SerialName("device_id") val deviceId: String,
    @SerialName("device_secret") val deviceSecret: String,
)

@Serializable
private data class CapabilityTokenResponse(
    val ok: Boolean = false,
    val token: String? = null,
    @SerialName("expires_in_seconds") val expiresInSeconds: Int? = null,
)

@Serializable
private data class CapabilityBackendHealth(
    @SerialName("instance_id") val instanceId: String,
    val role: String,
    @SerialName("api_protocol") val apiProtocol: String,
)

class CapabilityNodeAuth(
    private val client: OkHttpClient,
    private val clientCredentials: CredentialStore,
    private val credentials: CapabilityNodeCredentialStore,
) {
    private val json = Json { ignoreUnknownKeys = true }
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()
    private val tokenMutex = Mutex()

    suspend fun enrol(code: String, nodeName: String): EnrolResult = withContext(Dispatchers.IO) {
        val base = clientCredentials.backendUrl
        if (base.isBlank()) return@withContext EnrolResult.Failed("No backend URL configured")
        if (!BackendEndpointPolicy.allowsCapabilityNode(base)) {
            return@withContext EnrolResult.Failed(
                "Capability nodes require HTTPS; cleartext is accepted only on loopback",
            )
        }
        val body = json.encodeToString(
            CapabilityEnrolRequest(code.trim().uppercase(), nodeName),
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
                            409 -> "That code is for a client, not a capability node"
                            else -> "Node enrolment failed (${response.code})"
                        },
                    )
                }
                val result = json.decodeFromString<CapabilityEnrolResponse>(payload)
                if (!result.ok || result.kind != "capability_node" ||
                    result.deviceId.isNullOrBlank() || result.deviceSecret.isNullOrBlank() ||
                    result.instanceId.isNullOrBlank()
                ) {
                    EnrolResult.Failed("Backend returned an incomplete node enrolment")
                } else {
                    credentials.saveEnrolment(
                        result.deviceId,
                        result.deviceSecret,
                        result.instanceId,
                        nodeName,
                        base,
                    )
                    EnrolResult.Success
                }
            }
        }.getOrElse { error ->
            DaxLog.w(TAG, "Capability-node enrolment failed", error)
            EnrolResult.Failed(error.message ?: "Could not reach the backend")
        }
    }

    suspend fun accessToken(): CapabilityTokenResult = tokenMutex.withLock {
        withContext(Dispatchers.IO) {
            val deviceId = credentials.deviceId
            val secret = credentials.deviceSecret
            if (deviceId.isNullOrBlank() || secret.isNullOrBlank()) {
                return@withContext CapabilityTokenResult.NotEnrolled
            }
            val base = clientCredentials.backendUrl
            if (base.isBlank()) {
                return@withContext CapabilityTokenResult.Failed("No backend URL configured")
            }
            if (!BackendEndpointPolicy.allowsCapabilityNode(base)) {
                return@withContext CapabilityTokenResult.Failed(
                    "Capability nodes require HTTPS; cleartext is accepted only on loopback",
                )
            }
            val identityError = verifyIdentity(base)
            if (identityError != null) return@withContext CapabilityTokenResult.Failed(identityError)
            credentials.validToken()?.let { return@withContext CapabilityTokenResult.Success(it) }
            val body = json.encodeToString(
                CapabilityTokenRequest(deviceId, secret),
            ).toRequestBody(jsonMedia)
            runCatching {
                client.newCall(
                    Request.Builder().url("$base/api/auth/devices/token").post(body).build(),
                ).execute().use { response ->
                    if (response.code == 401) {
                        credentials.invalidateToken()
                        return@use CapabilityTokenResult.Failed(
                            "This capability node has been revoked",
                            revoked = true,
                        )
                    }
                    if (!response.isSuccessful) {
                        return@use CapabilityTokenResult.Failed(
                            "Node token request failed (${response.code})",
                        )
                    }
                    val result = json.decodeFromString<CapabilityTokenResponse>(
                        response.body?.string().orEmpty(),
                    )
                    if (!result.ok || result.token.isNullOrBlank()) {
                        CapabilityTokenResult.Failed("Backend returned no node token")
                    } else {
                        val token = CapabilityToken(
                            result.token,
                            (result.expiresInSeconds ?: 300).coerceAtLeast(60),
                        )
                        credentials.cacheToken(token)
                        CapabilityTokenResult.Success(token)
                    }
                }
            }.getOrElse { error ->
                DaxLog.w(TAG, "Capability-node token request failed", error)
                CapabilityTokenResult.Failed(error.message ?: "Could not reach the backend")
            }
        }
    }

    private fun verifyIdentity(base: String): String? {
        val normalized = BackendEndpointPolicy.normalize(base)
            ?: return "Backend URL is invalid"
        if (normalized != credentials.enrollmentOrigin) {
            return "Backend origin changed; enrol this node again"
        }
        return runCatching {
            client.newCall(Request.Builder().url("$base/api/health").get().build())
                .execute().use { response ->
                    if (!response.isSuccessful) return@use "Could not verify backend identity"
                    val health = json.decodeFromString<CapabilityBackendHealth>(
                        response.body?.string().orEmpty(),
                    )
                    if (health.instanceId != credentials.instanceId ||
                        health.role != "authoritative" || health.apiProtocol != "dax"
                    ) "Backend identity changed; enrol this node again" else null
                }
        }.getOrElse { "Could not verify backend identity" }
    }

    private companion object {
        const val TAG = "CapabilityNodeAuth"
    }
}
