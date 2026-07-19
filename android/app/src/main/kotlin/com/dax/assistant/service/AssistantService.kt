package com.dax.assistant.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import com.dax.assistant.R
import com.dax.assistant.assistant.AssistantController
import com.dax.assistant.assistant.AssistantState
import com.dax.assistant.core.log.DaxLog
import com.dax.assistant.data.transport.ChatSocket
import com.dax.assistant.ui.MainActivity
import dagger.hilt.android.AndroidEntryPoint
import javax.inject.Inject
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Keeps the assistant reachable while the app is not in front.
 *
 * A microphone foreground service cannot be started from the background on
 * Android 14+ unless the app holds a while-in-use exemption, and being the
 * `VoiceInteractionService` provider is one of the documented ones. That is why
 * this app registers as an assistant rather than only offering an in-app
 * button — the role is what makes a trigger from a locked screen legal.
 *
 * The notification is not decoration. It is the honest surface for "this app
 * can hear you", and it always reflects the real state rather than a generic
 * "running" string.
 */
@AndroidEntryPoint
class AssistantService : LifecycleService() {

    @Inject
    lateinit var controller: AssistantController

    @Inject
    lateinit var socket: ChatSocket

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(
            NOTIFICATION_ID,
            buildNotification(AssistantState.Idle),
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE or
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE
            } else {
                0
            },
        )
        socket.connect()

        lifecycleScope.launch {
            controller.state.collectLatest { state ->
                notificationManager.notify(NOTIFICATION_ID, buildNotification(state))
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        if (intent?.action == ACTION_START_TURN) {
            DaxLog.i(TAG, "Turn triggered by ${intent.getStringExtra(EXTRA_SOURCE) ?: "unknown"}")
            controller.startTurn()
        }
        // Restarted after process death so a trigger still works when the user
        // reaches for it, rather than silently doing nothing until the app is
        // opened again.
        return START_STICKY
    }

    override fun onDestroy() {
        socket.disconnect()
        super.onDestroy()
    }

    private val notificationManager: NotificationManager
        get() = getSystemService(NotificationManager::class.java)

    private fun createChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notification_channel_name),
            // Low: this is a persistent status surface, not an interruption.
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.notification_channel_description)
            setShowBadge(false)
        }
        notificationManager.createNotificationChannel(channel)
    }

    private fun buildNotification(state: AssistantState): Notification {
        val text = when (state) {
            is AssistantState.Idle -> getString(R.string.status_ready)
            is AssistantState.ConnectingAudio -> getString(R.string.status_connecting_audio)
            is AssistantState.Listening -> getString(R.string.status_listening)
            is AssistantState.Transcribing -> getString(R.string.status_transcribing)
            is AssistantState.Processing -> getString(R.string.status_thinking)
            is AssistantState.AwaitingApproval -> getString(R.string.status_needs_approval)
            is AssistantState.Speaking -> getString(R.string.status_speaking)
            is AssistantState.Disconnected -> getString(R.string.status_disconnected)
            is AssistantState.Failed -> getString(R.string.status_failed)
        }

        val open = PendingIntent.getActivity(
            this,
            0,
            Intent(this, MainActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE,
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setContentIntent(open)
            .setOngoing(true)
            .setSilent(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    companion object {
        private const val TAG = "AssistantService"
        private const val CHANNEL_ID = "dax_assistant_status"
        private const val NOTIFICATION_ID = 1001

        const val ACTION_START_TURN = "com.dax.assistant.action.START_TURN"
        const val EXTRA_SOURCE = "source"

        /** Starts the service and immediately begins a turn. */
        fun triggerTurn(context: Context, source: String) {
            val intent = Intent(context, AssistantService::class.java).apply {
                action = ACTION_START_TURN
                putExtra(EXTRA_SOURCE, source)
            }
            context.startForegroundService(intent)
        }

        fun ensureRunning(context: Context) {
            context.startForegroundService(Intent(context, AssistantService::class.java))
        }
    }
}
