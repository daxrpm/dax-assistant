package com.dax.assistant.data.auth

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.dax.assistant.core.network.BackendEndpointPolicy

/** Credentials for the phone's capability-node identity, separate from its client identity. */
class CapabilityNodeCredentialStore(context: Context) {
    private val prefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "dax_capability_node_credentials",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    @Volatile
    private var cachedToken: String? = null

    @Volatile
    private var tokenExpiresAtMillis: Long = 0L

    val deviceId: String?
        get() = prefs.getString(KEY_DEVICE_ID, null)

    val deviceSecret: String?
        get() = prefs.getString(KEY_DEVICE_SECRET, null)

    val instanceId: String?
        get() = prefs.getString(KEY_INSTANCE_ID, null)

    val enrollmentOrigin: String?
        get() = prefs.getString(KEY_ENROLLMENT_ORIGIN, null)

    val nodeName: String
        get() = prefs.getString(KEY_NODE_NAME, null).orEmpty()

    var enabled: Boolean
        get() = prefs.getBoolean(KEY_ENABLED, true)
        set(value) = prefs.edit().putBoolean(KEY_ENABLED, value).apply()

    val isEnrolled: Boolean
        get() = !deviceId.isNullOrBlank() && !deviceSecret.isNullOrBlank()

    fun saveEnrolment(
        deviceId: String,
        deviceSecret: String,
        instanceId: String,
        nodeName: String,
        enrollmentOrigin: String,
    ) {
        invalidateToken()
        prefs.edit()
            .putString(KEY_DEVICE_ID, deviceId)
            .putString(KEY_DEVICE_SECRET, deviceSecret)
            .putString(KEY_INSTANCE_ID, instanceId)
            .putString(KEY_NODE_NAME, nodeName)
            .putString(
                KEY_ENROLLMENT_ORIGIN,
                BackendEndpointPolicy.normalize(enrollmentOrigin) ?: enrollmentOrigin,
            )
            .putBoolean(KEY_ENABLED, true)
            .apply()
    }

    fun validToken(): CapabilityToken? {
        val token = cachedToken ?: return null
        val remaining = tokenExpiresAtMillis - System.currentTimeMillis()
        return if (remaining > EXPIRY_SKEW_MILLIS) {
            CapabilityToken(token, (remaining / 1_000L).coerceAtLeast(1L).toInt())
        } else {
            null
        }
    }

    fun cacheToken(token: CapabilityToken) {
        cachedToken = token.value
        tokenExpiresAtMillis = System.currentTimeMillis() + token.expiresInSeconds * 1_000L
    }

    fun invalidateToken() {
        cachedToken = null
        tokenExpiresAtMillis = 0L
    }

    fun clear() {
        invalidateToken()
        prefs.edit().clear().apply()
    }

    private companion object {
        const val KEY_DEVICE_ID = "device_id"
        const val KEY_DEVICE_SECRET = "device_secret"
        const val KEY_INSTANCE_ID = "instance_id"
        const val KEY_NODE_NAME = "node_name"
        const val KEY_ENROLLMENT_ORIGIN = "enrollment_origin"
        const val KEY_ENABLED = "enabled"
        const val EXPIRY_SKEW_MILLIS = 30_000L
    }
}
