package com.dax.assistant.capabilities

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import dagger.hilt.android.AndroidEntryPoint
import com.dax.assistant.data.auth.CapabilityNodeCredentialStore
import com.dax.assistant.data.transport.CapabilityNodeSocket
import javax.inject.Inject
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.launch

@AndroidEntryPoint
class DaxNotificationListenerService : NotificationListenerService() {
    @Inject
    lateinit var history: NotificationHistory

    @Inject
    lateinit var nodeCredentials: CapabilityNodeCredentialStore

    @Inject
    lateinit var nodeSocket: CapabilityNodeSocket

    private val workerScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val events = Channel<HistoryEvent>(
        capacity = 128,
        onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )

    override fun onCreate() {
        super.onCreate()
        workerScope.launch {
            for (event in events) {
                when (event) {
                    is HistoryEvent.Record -> history.record(event.entry, event.epoch)
                    is HistoryEvent.Removed -> history.markRemoved(event.key, event.epoch)
                }
            }
        }
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (!nodeCredentials.isEnrolled || !nodeCredentials.enabled || sbn.packageName == packageName) return
        val extras = sbn.notification.extras
        val app = runCatching {
            val info = packageManager.getApplicationInfo(sbn.packageName, 0)
            packageManager.getApplicationLabel(info).toString()
        }.getOrDefault(sbn.packageName)
        events.trySend(HistoryEvent.Record(
            NotificationHistoryEntry(
                key = sbn.key,
                packageName = sbn.packageName,
                app = app.take(128),
                title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty().take(512),
                text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty().take(2_048),
                postedAt = sbn.postTime,
                ongoing = sbn.isOngoing,
            ),
            history.currentEpoch(),
        ))
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        if (!nodeCredentials.isEnrolled || !nodeCredentials.enabled) return
        events.trySend(HistoryEvent.Removed(sbn.key, history.currentEpoch()))
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        nodeSocket.refreshInventory()
    }

    override fun onListenerDisconnected() {
        nodeSocket.refreshInventory()
        super.onListenerDisconnected()
    }

    override fun onDestroy() {
        events.close()
        workerScope.cancel()
        super.onDestroy()
    }

    private sealed interface HistoryEvent {
        data class Record(val entry: NotificationHistoryEntry, val epoch: Long) : HistoryEvent
        data class Removed(val key: String, val epoch: Long) : HistoryEvent
    }
}
