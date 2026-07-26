package com.dax.assistant.capabilities

import android.Manifest
import android.app.NotificationManager
import android.app.NotificationChannel
import android.app.KeyguardManager
import android.app.PendingIntent
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.MediaMetadata
import android.media.session.MediaController
import android.media.session.MediaSessionManager
import android.media.session.PlaybackState
import android.net.Uri
import android.telecom.TelecomManager
import android.telephony.TelephonyManager
import android.os.Bundle
import android.os.Build
import androidx.core.content.ContextCompat
import androidx.core.app.NotificationCompat
import com.dax.assistant.R
import com.dax.assistant.data.protocol.CapabilityServerFrame
import com.dax.assistant.data.protocol.CapabilityTool
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import kotlinx.coroutines.CancellationException

data class CapabilityExecutionResult(
    val success: Boolean,
    val content: String = "",
    val error: String? = null,
)

/** Fixed Android tools. Availability is derived from grants before each hello. */
class AndroidCapabilityExecutor(
    private val context: Context,
    private val notificationHistory: NotificationHistory,
    private val appVisibility: AppVisibility,
) {
    val tools: List<CapabilityTool>
        get() = buildList {
            add(tool("app_open", schema(mapOf("app" to "string"), setOf("app"))))
            add(tool("app_deeplink", schema(mapOf("url" to "string", "package" to "string"), setOf("url"))))
            if (hasNotificationAccess()) {
                add(tool("media_status", schema(emptyMap())))
                add(tool("media_control", schema(mapOf("action" to "string", "position_ms" to "integer"), setOf("action"))))
                add(tool("notifications_read", schema(mapOf("limit" to "integer", "include_ongoing" to "boolean"))))
            }
            if (supportsCalling()) {
                add(tool("call_dial", schema(mapOf("phone_number" to "string"), setOf("phone_number"))))
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
                    add(tool("call_place", schema(mapOf("phone_number" to "string"), setOf("phone_number"))))
                }
            }
            if (supportsMessaging()) {
                add(tool("sms_compose", schema(mapOf("phone_number" to "string", "message" to "string"), setOf("phone_number", "message"))))
            }
        }

    suspend fun execute(request: CapabilityServerFrame.Execute): CapabilityExecutionResult {
        if (request.toolName !in tools.mapTo(mutableSetOf()) { it.name }) {
            return failure("Capability is unavailable or its permission was revoked")
        }
        if (request.toolName in APPROVAL_REQUIRED && !request.approved) {
            return failure("This phone action requires one-time human approval")
        }
        return try {
            when (request.toolName) {
                "app_open" -> openApp(request.arguments.requiredString("app"))
                "app_deeplink" -> openDeepLink(
                    request.arguments.requiredString("url"),
                    request.arguments.string("package"),
                )
                "media_status" -> mediaStatus()
                "media_control" -> mediaControl(
                    request.arguments.requiredString("action"),
                    request.arguments.long("position_ms"),
                )
                "notifications_read" -> notificationsRead(
                    request.arguments.int("limit") ?: 20,
                    request.arguments.boolean("include_ongoing") ?: false,
                )
                "call_dial" -> dial(request.arguments.requiredString("phone_number"))
                "call_place" -> placeCall(request.arguments.requiredString("phone_number"))
                "sms_compose" -> composeSms(
                    request.arguments.requiredString("phone_number"),
                    request.arguments.requiredString("message"),
                )
                else -> failure("Unsupported Android capability: ${request.toolName}")
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (error: Exception) {
            failure(error.message ?: "Android rejected the action")
        }
    }

    private suspend fun openApp(app: String): CapabilityExecutionResult = withContext(Dispatchers.Main) {
        val query = app.trim()
        require(query.isNotBlank() && query.length <= 128) { "App name is invalid" }
        val packageName = resolvePackage(query)
            ?: return@withContext failure("Application is not installed, visible, or has an ambiguous name")
        val intent = context.packageManager.getLaunchIntentForPackage(packageName)
            ?: return@withContext failure("Application has no launchable activity")
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        launchUiOrNotify(intent, "Open $query", "Unlock the phone to open $query")
    }

    private suspend fun openDeepLink(url: String, packageName: String?): CapabilityExecutionResult =
        withContext(Dispatchers.Main) {
            require(url.length <= 2_048) { "Deep link is too long" }
            val uri = Uri.parse(url)
            require(uri.scheme?.lowercase() in ALLOWED_SCHEMES) { "Deep-link scheme is not allowed" }
            val intent = Intent(Intent.ACTION_VIEW, uri).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            packageName?.trim()?.takeIf(String::isNotEmpty)?.let { requested ->
                require(requested.length <= 255 && resolvePackage(requested) == requested) {
                    "Requested application is not installed or visible"
                }
                intent.setPackage(requested)
            }
            launchUiOrNotify(intent, "Open link", "Unlock the phone to open the requested link")
        }

    @Suppress("DEPRECATION")
    private fun resolvePackage(query: String): String? {
        runCatching { context.packageManager.getApplicationInfo(query, 0) }.getOrNull()?.let {
            return query
        }
        val launcher = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val matches = context.packageManager.queryIntentActivities(launcher, 0)
            .mapNotNull { info ->
                val packageName = info.activityInfo?.packageName ?: return@mapNotNull null
                val label = info.loadLabel(context.packageManager).toString()
                if (label.equals(query, ignoreCase = true)) packageName else null
            }
            .distinct()
        return matches.singleOrNull()
    }

    private fun mediaStatus(): CapabilityExecutionResult {
        val controller = activeMediaController() ?: return failure("No active media session")
        val metadata = controller.metadata
        val state = controller.playbackState
        return success(
            buildJsonObject {
                put("package", controller.packageName)
                put("title", metadata?.getString(MediaMetadata.METADATA_KEY_TITLE).orEmpty().take(2_048))
                put("artist", metadata?.getString(MediaMetadata.METADATA_KEY_ARTIST).orEmpty().take(2_048))
                put("album", metadata?.getString(MediaMetadata.METADATA_KEY_ALBUM).orEmpty().take(2_048))
                put("state", playbackStateName(state?.state))
                put("position_ms", state?.position ?: 0L)
                put("actions", state?.actions ?: 0L)
            }.toString(),
        )
    }

    private fun mediaControl(action: String, positionMs: Long?): CapabilityExecutionResult {
        val controller = activeMediaController() ?: return failure("No active media session")
        val available = controller.playbackState?.actions ?: 0L
        val controls = controller.transportControls
        when (action.lowercase()) {
            "play" -> {
                if (available and PlaybackState.ACTION_PLAY == 0L) return failure("Active session does not support play")
                controls.play()
            }
            "pause" -> {
                if (available and PlaybackState.ACTION_PAUSE == 0L) return failure("Active session does not support pause")
                controls.pause()
            }
            "next" -> {
                if (available and PlaybackState.ACTION_SKIP_TO_NEXT == 0L) return failure("Active session does not support next")
                controls.skipToNext()
            }
            "previous" -> {
                if (available and PlaybackState.ACTION_SKIP_TO_PREVIOUS == 0L) return failure("Active session does not support previous")
                controls.skipToPrevious()
            }
            "stop" -> {
                if (available and PlaybackState.ACTION_STOP == 0L) return failure("Active session does not support stop")
                controls.stop()
            }
            "seek" -> {
                require(positionMs != null && positionMs >= 0) { "seek requires a non-negative position_ms" }
                if (available and PlaybackState.ACTION_SEEK_TO == 0L) return failure("Active session does not support seek")
                controls.seekTo(positionMs)
            }
            else -> return failure("Unsupported media action")
        }
        return success("Media action sent to ${controller.packageName}")
    }

    private fun activeMediaController(): MediaController? {
        if (!hasNotificationAccess()) return null
        val manager = context.getSystemService(MediaSessionManager::class.java)
        val component = ComponentName(context, DaxNotificationListenerService::class.java)
        val sessions = manager.getActiveSessions(component)
        return sessions.firstOrNull { it.playbackState?.state == PlaybackState.STATE_PLAYING }
            ?: sessions.firstOrNull()
    }

    private fun notificationsRead(limit: Int, includeOngoing: Boolean): CapabilityExecutionResult {
        val bounded = limit.coerceIn(1, 50)
        val entries = notificationHistory.recent(bounded, includeOngoing)
        return success(boundedNotificationPayload(entries))
    }

    private suspend fun dial(number: String): CapabilityExecutionResult = withContext(Dispatchers.Main) {
        val normalized = validatedPhoneNumber(number)
        launchUiOrNotify(
            Intent(Intent.ACTION_DIAL, Uri.fromParts("tel", normalized, null))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            "Call $normalized",
            "Unlock the phone to review and place this call",
        )
    }

    private suspend fun placeCall(number: String): CapabilityExecutionResult = withContext(Dispatchers.Main) {
        val normalized = validatedPhoneNumber(number)
        require(!context.getSystemService(TelephonyManager::class.java).isEmergencyNumber(normalized)) {
            "Emergency calls are not allowed"
        }
        require(ContextCompat.checkSelfPermission(context, Manifest.permission.CALL_PHONE) == PackageManager.PERMISSION_GRANTED) {
            "Phone-call permission is not granted"
        }
        context.getSystemService(TelecomManager::class.java).placeCall(
            Uri.fromParts("tel", normalized, null),
            Bundle(),
        )
        success("Call requested. The carrier and Android dialer determine final call state.")
    }

    private suspend fun composeSms(number: String, message: String): CapabilityExecutionResult =
        withContext(Dispatchers.Main) {
            val normalized = validatedPhoneNumber(number)
            require(message.isNotBlank() && message.length <= 2_000) { "SMS message is invalid" }
            val intent = Intent(Intent.ACTION_SENDTO, Uri.fromParts("smsto", normalized, null))
                .putExtra("sms_body", message)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            launchUiOrNotify(
                intent,
                "Message $normalized",
                "Unlock the phone to review and send this message",
            )
        }

    private fun launchUiOrNotify(
        intent: Intent,
        title: String,
        lockedMessage: String,
    ): CapabilityExecutionResult {
        val locked = context.getSystemService(KeyguardManager::class.java).isDeviceLocked
        if (intent.resolveActivity(context.packageManager) == null) {
            return failure("No installed application can handle this action")
        }
        if (!locked && appVisibility.isResumed) {
            context.startActivity(intent)
            return success("Action opened on the phone for user confirmation.")
        }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            return failure("Phone is locked and notification permission is not granted")
        }
        val manager = context.getSystemService(NotificationManager::class.java)
        if (!manager.areNotificationsEnabled()) {
            return failure("Notifications are disabled, so Android cannot present this background action")
        }
        manager.createNotificationChannel(
            NotificationChannel(
                ACTION_CHANNEL_ID,
                context.getString(R.string.notification_action_channel_name),
                NotificationManager.IMPORTANCE_DEFAULT,
            ),
        )
        if (manager.getNotificationChannel(ACTION_CHANNEL_ID)?.importance == NotificationManager.IMPORTANCE_NONE) {
            return failure("The phone-action notification channel is disabled")
        }
        val pending = PendingIntent.getActivity(
            context,
            nextNotificationId.get(),
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, ACTION_CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title.take(128))
            .setContentText(lockedMessage.take(256))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setCategory(NotificationCompat.CATEGORY_RECOMMENDATION)
            .build()
        manager.notify(nextNotificationId.getAndIncrement(), notification)
        return success("Phone is locked; a notification was posted for user confirmation.")
    }

    private fun validatedPhoneNumber(number: String): String {
        val value = number.trim()
        require(value.isNotBlank() && value.length <= 64) { "Phone number is invalid" }
        require(value.matches(Regex("[+0-9() .-]+"))) { "Phone number contains unsupported characters" }
        return value
    }

    private fun hasNotificationAccess(): Boolean =
        context.getSystemService(NotificationManager::class.java)
            .isNotificationListenerAccessGranted(
                ComponentName(context, DaxNotificationListenerService::class.java),
            )

    private fun supportsCalling(): Boolean = if (Build.VERSION.SDK_INT >= 33) {
        context.packageManager.hasSystemFeature(PackageManager.FEATURE_TELEPHONY_CALLING)
    } else {
        context.packageManager.hasSystemFeature(PackageManager.FEATURE_TELEPHONY)
    }

    private fun supportsMessaging(): Boolean = if (Build.VERSION.SDK_INT >= 33) {
        context.packageManager.hasSystemFeature(PackageManager.FEATURE_TELEPHONY_MESSAGING)
    } else {
        context.packageManager.hasSystemFeature(PackageManager.FEATURE_TELEPHONY)
    }

    private fun success(content: String) = CapabilityExecutionResult(true, content = content)
    private fun failure(error: String) = CapabilityExecutionResult(false, error = error)

    private fun JsonObject.requiredString(key: String): String =
        string(key)?.takeIf(String::isNotBlank) ?: error("$key is required")

    private fun JsonObject.string(key: String): String? =
        (this[key] as? JsonPrimitive)?.contentOrNull

    private fun JsonObject.int(key: String): Int? =
        (this[key] as? JsonPrimitive)?.intOrNull

    private fun JsonObject.long(key: String): Long? =
        (this[key] as? JsonPrimitive)?.longOrNull

    private fun JsonObject.boolean(key: String): Boolean? =
        (this[key] as? JsonPrimitive)?.contentOrNull?.toBooleanStrictOrNull()

    private companion object {
        val APPROVAL_REQUIRED = setOf(
            "app_open",
            "app_deeplink",
            "media_control",
            "notifications_read",
            "call_dial",
            "call_place",
            "sms_compose",
        )
        val ALLOWED_SCHEMES = setOf("https", "http", "spotify", "geo")
        const val ACTION_CHANNEL_ID = "dax_phone_actions"
        val nextNotificationId = java.util.concurrent.atomic.AtomicInteger(2_000)

        fun tool(name: String, schema: JsonObject) = CapabilityTool(name, schema)

        fun schema(properties: Map<String, String>, required: Set<String> = emptySet()) =
            buildJsonObject {
                put("type", "object")
                put("properties", buildJsonObject {
                    properties.forEach { (name, type) ->
                        put(name, buildJsonObject { put("type", type) })
                    }
                })
                put("additionalProperties", false)
                if (required.isNotEmpty()) {
                    put("required", buildJsonArray { required.forEach { add(JsonPrimitive(it)) } })
                }
            }

        fun playbackStateName(state: Int?): String = when (state) {
            PlaybackState.STATE_PLAYING -> "playing"
            PlaybackState.STATE_PAUSED -> "paused"
            PlaybackState.STATE_STOPPED -> "stopped"
            PlaybackState.STATE_BUFFERING -> "buffering"
            PlaybackState.STATE_CONNECTING -> "connecting"
            PlaybackState.STATE_ERROR -> "error"
            else -> "unknown"
        }
    }
}

internal fun boundedNotificationPayload(
    entries: List<NotificationHistoryEntry>,
    maxBytes: Int = 60 * 1024,
): String {
    val accepted = mutableListOf<kotlinx.serialization.json.JsonElement>()
    for (entry in entries) {
        val item = buildJsonObject {
            put("app", entry.app)
            put("package", entry.packageName)
            put("title", entry.title)
            put("text", entry.text)
            put("posted_at", entry.postedAt)
            put("active", entry.active)
            put("ongoing", entry.ongoing)
        }
        val candidate = kotlinx.serialization.json.JsonArray(accepted + item).toString()
        if (candidate.toByteArray(Charsets.UTF_8).size > maxBytes) break
        accepted += item
    }
    return kotlinx.serialization.json.JsonArray(accepted).toString()
}
