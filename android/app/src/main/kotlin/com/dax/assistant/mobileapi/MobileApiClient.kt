package com.dax.assistant.mobileapi

import com.dax.assistant.data.auth.AuthResult
import com.dax.assistant.data.auth.BackendAuth
import com.dax.assistant.data.auth.CredentialStore
import javax.inject.Inject
import javax.inject.Singleton
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

sealed interface MobileApiResult<out T> {
    data class Success<T>(val value: T) : MobileApiResult<T>
    data class Failed(val reason: String) : MobileApiResult<Nothing>
}

@Singleton
class MobileApiClient @Inject constructor(
    private val client: OkHttpClient,
    private val credentials: CredentialStore,
    private val auth: BackendAuth,
) {
    private val jsonMedia = "application/json; charset=utf-8".toMediaType()

    suspend fun loadConfig(): MobileApiResult<MobileConfig> = request { token ->
        Request.Builder().url("${credentials.backendUrl}/api/mobile/config")
            .header("Authorization", "Bearer $token").get().build()
    }

    suspend fun saveConfig(config: MobileConfig): MobileApiResult<MobileConfig> =
        withContext(Dispatchers.IO) {
            val token = when (val result = auth.accessToken()) {
                is AuthResult.Success -> result.token
                is AuthResult.Failed -> return@withContext MobileApiResult.Failed(result.reason)
                AuthResult.NotEnrolled -> return@withContext MobileApiResult.Failed("Device is not paired")
            }
            val updates = listOf(
                "llm" to config.llmJson(),
                "voice" to config.voiceJson(),
                "nodes" to config.nodesJson(),
            )
            runCatching {
                updates.forEach { (section, payload) ->
                    client.newCall(
                        Request.Builder().url("${credentials.backendUrl}/api/mobile/config/$section")
                            .header("Authorization", "Bearer $token")
                            .patch(payload.toRequestBody(jsonMedia)).build(),
                    ).execute().use { response ->
                        if (!response.isSuccessful) error("$section update failed (${response.code})")
                    }
                }
                MobileApiResult.Success(config)
            }.getOrElse { MobileApiResult.Failed(it.message ?: "Could not update configuration") }
        }

    private suspend fun request(
        build: (String) -> Request,
    ): MobileApiResult<MobileConfig> =
        withContext(Dispatchers.IO) {
            val token = when (val result = auth.accessToken()) {
                is AuthResult.Success -> result.token
                is AuthResult.Failed -> return@withContext MobileApiResult.Failed(result.reason)
                AuthResult.NotEnrolled -> return@withContext MobileApiResult.Failed("Device is not paired")
            }
            runCatching {
                client.newCall(build(token)).execute().use { response ->
                    val payload = response.body?.string().orEmpty()
                    if (!response.isSuccessful) {
                        MobileApiResult.Failed("Request failed (${response.code})")
                    } else if (payload.isBlank()) {
                        MobileApiResult.Failed("Backend returned an empty configuration")
                    } else {
                        MobileApiResult.Success(MobileConfig.parse(payload))
                    }
                }
            }.getOrElse { MobileApiResult.Failed(it.message ?: "Could not reach the backend") }
        }
}
