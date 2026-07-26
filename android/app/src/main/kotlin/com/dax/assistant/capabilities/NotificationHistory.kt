package com.dax.assistant.capabilities

import android.content.Context
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.dax.assistant.data.protocol.DaxJson
import kotlinx.serialization.Serializable
import java.util.concurrent.atomic.AtomicLong

@Serializable
data class NotificationHistoryEntry(
    val key: String,
    val packageName: String,
    val app: String,
    val title: String,
    val text: String,
    val postedAt: Long,
    val ongoing: Boolean,
    val active: Boolean = true,
)

/** Encrypted, bounded notification history used only after an approved read. */
class NotificationHistory(context: Context) {
    private val epoch = AtomicLong(0)
    private val prefs by lazy {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            "dax_notification_history",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    @Synchronized
    fun record(entry: NotificationHistoryEntry, eventEpoch: Long = epoch.get()) {
        if (eventEpoch != epoch.get()) return
        val entries = load().filterNot { it.key == entry.key } + entry
        if (eventEpoch != epoch.get()) return
        save(prune(entries))
    }

    @Synchronized
    fun markRemoved(key: String, eventEpoch: Long = epoch.get()) {
        if (eventEpoch != epoch.get()) return
        save(prune(load().map { if (it.key == key) it.copy(active = false) else it }))
    }

    @Synchronized
    fun recent(limit: Int, includeOngoing: Boolean): List<NotificationHistoryEntry> =
        prune(load())
            .asSequence()
            .filter { includeOngoing || !it.ongoing }
            .sortedByDescending(NotificationHistoryEntry::postedAt)
            .take(limit.coerceIn(1, MAX_ENTRIES))
            .toList()

    @Synchronized
    fun clear() {
        epoch.incrementAndGet()
        prefs.edit().remove(KEY_ENTRIES).apply()
    }

    fun currentEpoch(): Long = epoch.get()

    private fun load(): List<NotificationHistoryEntry> = runCatching {
        val raw = prefs.getString(KEY_ENTRIES, null) ?: return emptyList()
        DaxJson.decodeFromString<List<NotificationHistoryEntry>>(raw)
    }.getOrDefault(emptyList())

    private fun save(entries: List<NotificationHistoryEntry>) {
        prefs.edit().putString(KEY_ENTRIES, DaxJson.encodeToString(entries)).apply()
    }

    private fun prune(entries: List<NotificationHistoryEntry>): List<NotificationHistoryEntry> {
        val cutoff = System.currentTimeMillis() - RETENTION_MILLIS
        return entries.filter { it.postedAt >= cutoff }
            .sortedByDescending(NotificationHistoryEntry::postedAt)
            .take(MAX_ENTRIES)
    }

    private companion object {
        const val KEY_ENTRIES = "entries"
        const val MAX_ENTRIES = 200
        const val RETENTION_MILLIS = 24 * 60 * 60 * 1_000L
    }
}
