package com.dax.assistant.data.auth

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.dax.assistant.core.log.DaxLog
import java.util.UUID

/**
 * Where the device credential lives.
 *
 * The device secret is the phone's standing authority over a backend that can
 * reach PC-control tools, so it is held in [EncryptedSharedPreferences] under a
 * hardware-backed [MasterKey] rather than in plain preferences. Backup and
 * device transfer are excluded wholesale in `data_extraction_rules.xml`, so it
 * cannot leave the device that enrolled it.
 *
 * Short-lived access tokens are cached in memory only. Persisting them would
 * add a second credential at rest to save one cheap round trip against a
 * backend the app is about to talk to anyway.
 */
class CredentialStore(context: Context) {

    private val prefs: SharedPreferences by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "dax_credentials",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    @Volatile
    private var cachedToken: String? = null

    @Volatile
    private var tokenExpiresAtMillis: Long = 0L

    var backendUrl: String
        get() = prefs.getString(KEY_BACKEND_URL, "").orEmpty()
        set(value) = prefs.edit().putString(KEY_BACKEND_URL, value.trimEnd('/')).apply()

    val deviceId: String?
        get() = prefs.getString(KEY_DEVICE_ID, null)

    val deviceSecret: String?
        get() = prefs.getString(KEY_DEVICE_SECRET, null)

    val isEnrolled: Boolean
        get() = !deviceId.isNullOrBlank() && !deviceSecret.isNullOrBlank()

    /** Stable conversation identity for this installation. */
    val sessionId: String
        get() = prefs.getString(KEY_SESSION_ID, null)?.takeIf { it.isNotBlank() }
            ?: synchronized(this) {
                prefs.getString(KEY_SESSION_ID, null)?.takeIf { it.isNotBlank() }
                    ?: "android-${UUID.randomUUID()}".also {
                        prefs.edit().putString(KEY_SESSION_ID, it).commit()
                    }
            }

    fun saveEnrolment(deviceId: String, deviceSecret: String) {
        prefs.edit()
            .putString(KEY_DEVICE_ID, deviceId)
            .putString(KEY_DEVICE_SECRET, deviceSecret)
            .apply()
        DaxLog.i(TAG, "Device enrolment stored")
    }

    /**
     * The cached access token, or null when absent or near expiry.
     *
     * The skew means a token is never handed out with so little life left that
     * it expires mid-request; a spurious refresh is cheaper than a failed turn.
     */
    fun validToken(): String? {
        val token = cachedToken ?: return null
        return if (System.currentTimeMillis() < tokenExpiresAtMillis - EXPIRY_SKEW_MILLIS) {
            token
        } else {
            null
        }
    }

    fun cacheToken(token: String, expiresInSeconds: Int) {
        cachedToken = token
        tokenExpiresAtMillis = System.currentTimeMillis() + expiresInSeconds * 1_000L
    }

    fun invalidateToken() {
        cachedToken = null
        tokenExpiresAtMillis = 0L
    }

    /** Forgets remote credentials while retaining this installation's identity. */
    fun clear() {
        invalidateToken()
        prefs.edit()
            .remove(KEY_BACKEND_URL)
            .remove(KEY_DEVICE_ID)
            .remove(KEY_DEVICE_SECRET)
            .apply()
        DaxLog.i(TAG, "Credentials cleared")
    }

    private companion object {
        const val TAG = "CredentialStore"
        const val KEY_BACKEND_URL = "backend_url"
        const val KEY_DEVICE_ID = "device_id"
        const val KEY_DEVICE_SECRET = "device_secret"
        const val KEY_SESSION_ID = "session_id"
        const val EXPIRY_SKEW_MILLIS = 30_000L
    }
}
